"""Extractor runtime (TRD-03.1) — executes a rulepack's declarative
extractors against a parse tree + effective config, producing `Fact`s with
full provenance, plus unmatched-construct routing (FR-EXT-009) and conflict
detection (FR-EXT-007, DD-03.1-02).

M1 scope note (flagged, not silently resolved): TRD-03.1 §3.4 describes scope
selection via ``context``/``section``/``xpath`` against the rulepack's
declared grammar. M1 implements two scope kinds — ``any`` (search the whole
tree; each extractor's own ``match`` regex is specific enough not to
false-positive within the small Cisco IOS control set this milestone
targets) and ``vty`` (per-instance search over
``effective_config.EffectiveConfig.vty_instances``, keyed by canonical
attribute name). Full context/section/xpath scope selection is a natural M2
extension once more paradigms exist.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from nsca_engine.extract.provenance import (
    DefaultsTable,
    classify_absent,
    weakest_source,
)
from nsca_engine.extract.value_lang import compile_expr, evaluate_expr
from nsca_engine.parse.effective_config import EffectiveConfig
from nsca_engine.parse.grammar import Node, ParseTree
from nsca_engine.types import Fact, Provenance, ProvenanceSource, UnmatchedConstruct

_IGNORED_HEADS = frozenset({"interface", "!", "end"})


@dataclass(frozen=True, slots=True)
class ElementFieldSpec:
    field: str
    expr: str


@dataclass(frozen=True, slots=True)
class EmitSpec:
    """One ``emit`` entry (07-vendor-rulepacks.md §5). Either a scalar
    (``value_expr`` set) or a collection element (``collection`` +
    ``element_fields`` set) — never both."""

    fact: str
    value_expr: str | None = None
    collection: str | None = None
    element_fields: tuple[ElementFieldSpec, ...] = ()


@dataclass(frozen=True, slots=True)
class ExtractorSpec:
    extractor_id: str
    version: int
    scope_kind: str  # "any" | "vty"
    scope_attribute: str | None
    match: re.Pattern[str]
    emits: tuple[EmitSpec, ...]


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    facts: tuple[Fact, ...]
    unmatched: tuple[UnmatchedConstruct, ...]
    conflicts: tuple[str, ...]


def _extractor_ref(spec: ExtractorSpec) -> str:
    return f"{spec.extractor_id}@v{spec.version}"


def _qualify(base_path: str, qualifier: str | None) -> str:
    return f"{qualifier}.{base_path}" if qualifier else base_path


def _run_emit(
    spec: ExtractorSpec,
    emit: EmitSpec,
    node: Node,
    excerpt: str,
    captures: Mapping[str, str],
    artifact_id: str,
    qualifier: str | None,
    collection_counters: dict[str, int],
    out_facts: list[Fact],
    lookup_tables: Mapping[str, object],
) -> None:
    lines = (node.line_start,) if node.line_start == node.line_end else tuple(
        range(node.line_start, node.line_end + 1)
    )

    def _provenance() -> Provenance:
        # A small factory rather than a shared kwargs dict passed via `**`
        # — a dict built from heterogeneous field types (`str`, `tuple[int,
        # ...]`, `None`, ...) can't be typed precisely enough for `**` to
        # type-check against `Provenance`'s real field types under
        # mypy --strict, and every call site needs an identical Provenance
        # anyway.
        return Provenance(
            source=ProvenanceSource.EXPLICIT, artifact_id=artifact_id, lines=lines,
            excerpt=excerpt, extractor=_extractor_ref(spec), confidence=None,
        )

    if emit.collection is not None:
        idx = collection_counters.get(emit.collection, 0)
        collection_counters[emit.collection] = idx + 1
        for field_spec in emit.element_fields:
            compiled = compile_expr(field_spec.expr)
            value = evaluate_expr(compiled, captures, lookup_tables)
            path = f"{_qualify(emit.collection, qualifier)}[{idx}].{field_spec.field}"
            out_facts.append(
                Fact(path=path, value=value, type="unknown", provenance=_provenance())
            )
        return

    compiled = compile_expr(emit.value_expr or "")
    value = evaluate_expr(compiled, captures, lookup_tables)
    path = _qualify(emit.fact, qualifier)
    out_facts.append(
        Fact(path=path, value=value, type="unknown", provenance=_provenance())
    )


def extract(
    tree: ParseTree,
    effective: EffectiveConfig,
    extractors: tuple[ExtractorSpec, ...],
    artifact_id: str,
    lookup_tables: Mapping[str, object] | None = None,
) -> ExtractionResult:
    """Run every extractor over the tree/effective config (INV-03.1-02:
    order-independent — extractors are independent of each other)."""

    lookup_tables = lookup_tables or {}
    out_facts: list[Fact] = []
    matched_node_ids: set[int] = set()
    collection_counters: dict[str, int] = {}

    for spec in extractors:
        if spec.scope_kind == "any":
            for node in tree.walk():
                if node.kind not in ("statement", "container"):
                    continue
                text = tree.raw(node).strip()
                m = spec.match.match(text)
                if not m:
                    continue
                matched_node_ids.add(node.id)
                captures = m.groupdict()
                for emit in spec.emits:
                    _run_emit(
                        spec, emit, node, text, captures, artifact_id, None,
                        collection_counters, out_facts, lookup_tables,
                    )
        elif spec.scope_kind == "vty":
            instances = effective.vty_instances
            multi = len(instances) > 1
            for inst in instances:
                vty_node = inst.attrs.get(spec.scope_attribute or "")
                if vty_node is None:
                    continue
                text = tree.raw(vty_node).strip()
                m = spec.match.match(text)
                if not m:
                    continue
                matched_node_ids.add(vty_node.id)
                qualifier = f"vty[{inst.lo}..{inst.hi}]" if multi else None
                captures = m.groupdict()
                for emit in spec.emits:
                    _run_emit(
                        spec, emit, vty_node, text, captures, artifact_id, qualifier,
                        collection_counters, out_facts, lookup_tables,
                    )
        else:  # pragma: no cover - defensive
            raise ValueError(f"unknown scope kind: {spec.scope_kind}")

    # Conflict detection (DD-03.1-02): same qualified path, different values
    # from different extractors -> default_unknown, never a winner.
    by_path: dict[str, list[Fact]] = {}
    for f in out_facts:
        by_path.setdefault(f.path, []).append(f)

    final_facts: list[Fact] = []
    conflicts: list[str] = []
    for path in sorted(by_path):
        group = by_path[path]
        values = {repr(f.value) for f in group}
        if len(values) > 1:
            conflicts.append(path)
            final_facts.append(
                Fact(
                    path=path,
                    value=None,
                    type="unknown",
                    provenance=Provenance(source=ProvenanceSource.DEFAULT_UNKNOWN),
                )
            )
        else:
            final_facts.append(group[0])

    unmatched: list[UnmatchedConstruct] = []
    for node in tree.walk():
        if node.kind not in ("statement", "container"):
            continue
        if node.id in matched_node_ids:
            continue
        if node.head.lower() in _IGNORED_HEADS:
            continue
        unmatched.append(
            UnmatchedConstruct(
                artifact_id=artifact_id,
                lines=(node.line_start,),
                excerpt=tree.raw(node),
                parse_path=node.path,
            )
        )

    return ExtractionResult(
        facts=tuple(final_facts), unmatched=tuple(unmatched), conflicts=tuple(conflicts)
    )


# ---------------------------------------------------------------------------
# Derived facts (TRD-03.2 §4.5, DD-03.1-01 — a separate pass after extraction)
# ---------------------------------------------------------------------------

_INDEXED_PATH = re.compile(r"^(?P<base>.+)\[(?P<idx>\d+)\]\.(?P<field>.+)$")

_DEFAULT_COMMUNITY_NAMES = frozenset({"public", "private", "cisco"})
_REVERSIBLE_STORAGE_TYPES = frozenset({"plaintext", "reversible"})


def compute_derived_facts(facts: tuple[Fact, ...], artifact_id: str) -> tuple[Fact, ...]:
    """TRD-03.2 §4.5 derived-fact pass. Only the derived facts M1's control
    set needs are computed here (backend-01 §6 M1 scope: end-to-end on one
    platform, not the full derived-fact catalogue).

    `artifact_id` (Phase 3 demo rehearsal fix, finding 11): the primary
    artifact this device was assessed from, used only by
    `logging.remote_configured`'s absence branch below, so a genuine
    absence-based FAIL ("no `logging host`/`logging trap` construct
    anywhere in this artifact") carries a real citation instead of empty
    evidence — see `to_device_findings`' evidence-eligible source list and
    `extract/provenance.py::classify_absent`'s matching fix."""

    # Group collection elements by (base, index).
    groups: dict[tuple[str, int], dict[str, Fact]] = {}
    for f in facts:
        m = _INDEXED_PATH.match(f.path)
        if not m:
            continue
        base, idx, field = m.group("base"), int(m.group("idx")), m.group("field")
        groups.setdefault((base, idx), {})[field] = f

    derived: list[Fact] = []

    for (base, idx), fields in sorted(groups.items()):
        if base == "auth.local_users" and "storage_type" in fields:
            st = fields["storage_type"]
            source = weakest_source([st.provenance.source])
            value = (
                st.value in _REVERSIBLE_STORAGE_TYPES if source == ProvenanceSource.DERIVED else None
            )
            derived.append(
                Fact(
                    path=f"{base}[{idx}].reversible",
                    value=value,
                    type="boolean",
                    provenance=Provenance(
                        source=source, depends_on=(f"{base}[{idx}].storage_type",)
                    ),
                )
            )
        if base == "snmp.communities" and "name" in fields:
            nm = fields["name"]
            source = weakest_source([nm.provenance.source])
            value = nm.value in _DEFAULT_COMMUNITY_NAMES if source == ProvenanceSource.DERIVED else None
            derived.append(
                Fact(
                    path=f"{base}[{idx}].is_default",
                    value=value,
                    type="boolean",
                    provenance=Provenance(
                        source=source, depends_on=(f"{base}[{idx}].name",)
                    ),
                )
            )

    # logging.remote_configured — derived from presence of logging.remote_servers[*]
    server_facts = [f for f in facts if f.path.startswith("logging.remote_servers[")]
    if server_facts:
        source = weakest_source([f.provenance.source for f in server_facts])
        value = True if source == ProvenanceSource.DERIVED else None
        # Presence case: real evidence exists (the server_facts this was
        # derived from) — surface it rather than leaving the derived fact's
        # own provenance artifact-less (it was DERIVED before this fix too,
        # but with no artifact_id/lines of its own, so evidence built from
        # *this* fact alone came up empty even when the underlying facts had
        # real citations).
        cited = [f for f in server_facts if f.provenance.artifact_id]
        derived_artifact_id = cited[0].provenance.artifact_id if cited else artifact_id
        derived_lines = tuple(sorted({ln for f in cited for ln in f.provenance.lines}))
        derived_excerpt = "; ".join(
            sorted({f.provenance.excerpt for f in cited if f.provenance.excerpt})
        ) or None
    else:
        source = ProvenanceSource.DERIVED
        value = False
        derived_artifact_id = artifact_id
        derived_lines = ()
        derived_excerpt = "no 'logging host'/'logging trap' construct found in this artifact"
    derived.append(
        Fact(
            path="logging.remote_configured",
            value=value,
            type="boolean",
            provenance=Provenance(
                source=source,
                artifact_id=derived_artifact_id,
                lines=derived_lines,
                excerpt=derived_excerpt,
                depends_on=tuple(sorted(f.path for f in server_facts)),
            ),
        )
    )

    return tuple(derived)


def resolve_needed_facts(
    facts: tuple[Fact, ...],
    needed_base_paths: frozenset[str],
    defaults_table: DefaultsTable,
    platform: str,
    os_version: str | None,
    artifact_id: str,
) -> tuple[Fact, ...]:
    """For every control-required base fact path with no explicit/derived
    value already present, resolve via the defaults table or fall through to
    ``default_unknown`` (TRD-03.2 §4.1, INV-03.2-01 default branch).

    `artifact_id` (Phase 3 demo rehearsal fix, finding 11): threaded through
    to `classify_absent` so every absent-fact citation names the artifact
    that was actually searched — see that function's docstring."""

    have = {f.path for f in facts}
    out: list[Fact] = []
    for path in sorted(needed_base_paths):
        if path in have:
            continue
        # scope-qualified variants (vty[..].path) also count as "have"
        if any(p.endswith("." + path) for p in have):
            continue
        # collection base paths (auth.local_users, snmp.communities) are
        # "have" if any indexed element exists, even though the base path
        # itself is never a literal Fact path.
        if any(p.startswith(path + "[") for p in have):
            continue
        out.append(classify_absent(path, defaults_table, platform, os_version, artifact_id))
    return tuple(out)
