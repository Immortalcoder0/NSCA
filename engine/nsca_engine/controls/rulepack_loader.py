"""Loads ``knowledge/rulepacks/*.yaml`` and ``knowledge/control_packs/*.yaml``
(07-vendor-rulepacks.md, 06-controls-and-frameworks.md §3) into the runtime
shapes ``fingerprint``, ``parse``, ``extract`` and ``controls`` consume.

M1 scope: the Cisco IOS rulepack and the ``nsca_native`` control pack. Only
the YAML fields M1's engine actually reads are parsed; fields present in the
07/06 doc shapes but belonging to later milestones (remediation, risk
modifiers, maps_to beyond the framework-ref list, quirks beyond command
abbreviation) are accepted if present but not required, and simply not
consumed yet — flagged in the M1 report rather than silently dropped without
comment.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml

from nsca_engine.controls.evaluate import Applicability, NativeControl, VacuitySpec
from nsca_engine.controls.expression import compile_expr
from nsca_engine.extract.provenance import DefaultEntry, DefaultsTable
from nsca_engine.extract.runtime import ElementFieldSpec, EmitSpec, ExtractorSpec
from nsca_engine.fingerprint.signatures import PlatformSignatureSet, Signature
from nsca_engine.parse.paradigms.block_keyword import BlockKeywordGrammarSpec
from nsca_engine.parse.paradigms.brace import BraceGrammarSpec
from nsca_engine.parse.paradigms.cloud_json import CloudJsonGrammarSpec
from nsca_engine.parse.paradigms.flat_path import FlatPathGrammarSpec
from nsca_engine.parse.paradigms.indentation import IndentationGrammarSpec, compile_context_blocks
from nsca_engine.parse.paradigms.path_header import PathHeaderGrammarSpec
from nsca_engine.parse.paradigms.xml import XmlGrammarSpec
from nsca_engine.types import Severity

# Every structural paradigm the grammar engine supports (TRD-02.1 §3.3,
# backend-01 M2). One entry per `parse/paradigms/*.py` module — the rulepack
# loader's only job here is to build the right grammar-spec dataclass from
# the YAML `grammar:` block; each paradigm module's own `parse()` function
# does the actual structuring (dispatched generically in `api.py`).
_KNOWN_PARADIGMS = frozenset({
    "indentation", "flat_path", "brace", "block_keyword", "xml",
    "path_header", "cloud_json",
})


class RulepackLoadError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LoadedRulepack:
    platform: str
    vendor: str
    version: str
    trust_tier: str
    signature_set: PlatformSignatureSet
    paradigm: str
    grammar: Any  # one of the paradigm-specific *GrammarSpec dataclasses
    extractors: tuple[ExtractorSpec, ...]
    defaults: DefaultsTable
    lookup_tables: Mapping[str, Any]
    version_pattern: re.Pattern[str] | None = None


def _to_fraction(v: Any) -> Fraction:
    if isinstance(v, str) and "/" in v:
        num, den = v.split("/")
        return Fraction(int(num), int(den))
    return Fraction(str(v))


def _build_grammar_spec(paradigm: str, grammar_doc: Mapping[str, Any]) -> Any:
    if paradigm == "indentation":
        context_blocks = compile_context_blocks(
            tuple((cb["pattern"], cb["context"]) for cb in grammar_doc.get("context_blocks", []))
        )
        return IndentationGrammarSpec(
            comment_char=grammar_doc.get("comment_char", "!"),
            context_blocks=context_blocks,
        )
    if paradigm == "flat_path":
        return FlatPathGrammarSpec(comment_char=grammar_doc.get("comment_char", "#"))
    if paradigm == "brace":
        return BraceGrammarSpec(line_comment_char=grammar_doc.get("comment_char", "#"))
    if paradigm == "block_keyword":
        return BlockKeywordGrammarSpec(comment_char=grammar_doc.get("comment_char", "#"))
    if paradigm == "xml":
        return XmlGrammarSpec()
    if paradigm == "path_header":
        return PathHeaderGrammarSpec(comment_char=grammar_doc.get("comment_char", "#"))
    if paradigm == "cloud_json":
        return CloudJsonGrammarSpec()
    raise RulepackLoadError(f"unknown grammar paradigm: {paradigm!r}")  # pragma: no cover - guarded above


def load_rulepack(path: str | Path) -> LoadedRulepack:
    path = Path(path)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if doc is None:
        raise RulepackLoadError(f"empty rulepack: {path}")

    platform = doc["platform"]
    vendor = doc.get("vendor", platform.split("_")[0])

    sig_entries = doc.get("fingerprint", {}).get("signatures", [])
    signatures = tuple(
        Signature(kind=s["type"], pattern=s.get("pattern", s.get("value", "")), weight=_to_fraction(s["weight"]))
        for s in sig_entries
    )
    sigset = PlatformSignatureSet(platform=platform, vendor=vendor, signatures=signatures)

    grammar_doc = doc.get("grammar", {})
    paradigm = grammar_doc.get("paradigm", "indentation")
    if paradigm not in _KNOWN_PARADIGMS:
        raise RulepackLoadError(
            f"{path}: unknown grammar paradigm {paradigm!r} — must be one of "
            f"{sorted(_KNOWN_PARADIGMS)}"
        )
    grammar = _build_grammar_spec(paradigm, grammar_doc)

    version_pattern = None
    vp = doc.get("fingerprint", {}).get("version_pattern")
    if vp:
        version_pattern = re.compile(vp, re.MULTILINE)

    extractors: list[ExtractorSpec] = []
    for e in doc.get("extractors", []):
        scope = e["scope"]
        scope_kind = scope["kind"]
        scope_attribute = scope.get("attribute")
        match = re.compile(e["match"])
        emits: tuple[EmitSpec, ...]
        if "collection" in e:
            fields = tuple(
                ElementFieldSpec(field=k, expr=v) for k, v in e["element_fields"].items()
            )
            emits = (EmitSpec(fact=e["collection"], collection=e["collection"], element_fields=fields),)
        else:
            emits = tuple(
                EmitSpec(fact=em["fact"], value_expr=em["value"]) for em in e["emit"]
            )
        extractors.append(
            ExtractorSpec(
                extractor_id=e["extractor_id"], version=int(e["version"]),
                scope_kind=scope_kind, scope_attribute=scope_attribute,
                match=match, emits=emits,
            )
        )
    extractors.sort(key=lambda s: s.extractor_id)  # deterministic order (D6)

    defaults: dict[str, tuple[DefaultEntry, ...]] = {}
    for path_key, entries in doc.get("defaults", {}).items():
        defaults[path_key] = tuple(
            DefaultEntry(
                version_range=en["version_range"], value=en["value"],
                source=en["source"], condition=en.get("condition"),
            )
            for en in entries
        )

    lookup_tables = doc.get("lookup_tables", {})

    return LoadedRulepack(
        platform=platform, vendor=vendor, version=str(doc.get("version", "0.0.0")),
        trust_tier=doc.get("trust_tier", "local"), signature_set=sigset, paradigm=paradigm,
        grammar=grammar, extractors=tuple(extractors), defaults=defaults,
        lookup_tables=lookup_tables, version_pattern=version_pattern,
    )


# ---------------------------------------------------------------------------
# Control pack loader (06-controls-and-frameworks.md §3)
# ---------------------------------------------------------------------------

_SEVERITY_MAP = {s.value: s for s in Severity}


@dataclass(frozen=True, slots=True)
class LoadedControlPack:
    pack_id: str
    version: str
    controls: tuple[NativeControl, ...]
    lookup_tables: Mapping[str, Any]


def load_control_pack(path: str | Path) -> LoadedControlPack:
    path = Path(path)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if doc is None:
        raise RulepackLoadError(f"empty control pack: {path}")

    controls: list[NativeControl] = []
    for c in doc.get("controls", []):
        applies = c.get("applies_to", {})
        platform_family = applies.get("platform_family", "*")
        if isinstance(platform_family, str):
            platform_family = (platform_family,)
        else:
            platform_family = tuple(platform_family)

        vacuity_doc = c.get("vacuity")
        vacuity = None
        if vacuity_doc and vacuity_doc.get("meaningful_when"):
            vacuity = VacuitySpec(meaningful_when=compile_expr(vacuity_doc["meaningful_when"]))

        maps_to = c.get("maps_to", {})
        framework_refs: list[str] = []
        for framework, entries in maps_to.items():
            for entry in entries:
                framework_refs.append(f"{framework}:{entry.get('id')}")

        controls.append(
            NativeControl(
                control_id=c["control_id"], title=c["title"], family=c["family"],
                severity_base=_SEVERITY_MAP[c["severity_base"]],
                applies_to=Applicability(platform_family=platform_family),
                requires_facts=tuple(c.get("requires_facts", [])),
                assertion=compile_expr(c["assert"]),
                scope_aggregation=c.get("scope_aggregation", "all"),
                vacuity=vacuity,
                framework_refs=tuple(sorted(framework_refs)),
            )
        )
    controls.sort(key=lambda ctl: ctl.control_id)  # deterministic order (D6)

    return LoadedControlPack(
        pack_id=doc["control_pack_id"], version=str(doc.get("version", "0.0.0")),
        controls=tuple(controls), lookup_tables=doc.get("lookup_tables", {}),
    )
