"""Rule synthesis — TRD-08.3, Stage 6 of 08-learning-system.md §2.

Converts a confirmed proposal into a deterministic extraction rule and
writes it into a rulepack YAML file under `knowledge/rulepacks/`. This is
where a model-assisted (or heuristic) *proposal* becomes deterministic
*knowledge*: after this point the platform is consulted for that construct
exactly zero times (TRD-08.3 §1).

**The output shape matches `nsca_engine.controls.rulepack_loader.load_rulepack`
exactly** — not TRD-08.3 §3.1's illustrative Jinja-templated
(`{{ svc | service_map }}`) shape. Reading the real loader
(`nsca/engine/nsca_engine/controls/rulepack_loader.py`) shows it:

- reads `emit[].fact` as a **literal** string (`_qualify(emit.fact, ...)` —
  never templated/interpolated)
- compiles `emit[].value` with `nsca_engine.extract.value_lang.compile_expr`,
  a small AST-walking subset of Python (`ast.parse(..., mode="eval")` with
  an allow-list) — not Jinja2, and it has no `service_map`-style lookup
  filter (it *does* support `map_lookup(table, key)` against a rulepack's
  own `lookup_tables`, which this module uses instead)
- only implements two `scope.kind` values, `"any"` and `"vty"` (M1 scope
  note in `runtime.py`) — a freshly-taught rule always uses `"any"`

so this module synthesises **one extractor per confirmed mapping** (one per
distinct slot value, e.g. one for `telnet`, one for `ssh`), exactly
matching the real `routeros.yaml` rulepack's own pattern — not the
single-extractor-with-a-lookup-table shape TRD-08.3's prose sketches. This
is flagged as a deliberate deviation from the TRD text in favour of the
literal contract backend-02 §2.2 says governs: "Track A's loader ... must
load what you write without modification."
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from nsca_platform.learning.polarity import derive_boolean_value, key_contains_negation
from nsca_platform.learning.template_mining import Slot, Template


class SynthesisError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ConfirmedMapping:
    """One administrator-confirmed slot -> fact mapping (TRD-08.2 §6.4's
    `confirm` / `polarity_inverted` answer, materialised per slot value)."""

    slot_value: str
    fact_path: str
    fact_type: str = "boolean"
    polarity_confirmed: bool = True


@dataclass(frozen=True, slots=True)
class Confirmation:
    template: Template
    mappings: tuple[ConfirmedMapping, ...]
    taught_by: str
    source_artifact: str
    negation_key: str | None  # the key that triggered polarity (e.g. "disabled"), or None


def _escape_literal(tok: str) -> str:
    return re.escape(tok)


def _regex_for_mapping(t: Template, mapping: ConfirmedMapping) -> tuple[str, str]:
    """TRD-08.3 §3.2 — the pattern is derived from the template skeleton,
    not authored freely. Slots become named capture groups; literal tokens
    (including the specific slot value this extractor targets, e.g.
    `telnet`) are anchored. Returns `(pattern, value_capture_group_name)`.

    INV-08.3-01: no unbounded nested quantifiers — every piece here is
    either a literal, `\\S+`, or a small fixed alternation, so there is no
    backtracking hazard to begin with (checked explicitly by
    `validation_gates.check_no_catastrophic_backtracking`).
    """

    parts: list[str] = [r"^"]
    value_group = None
    n = len(t.shape)
    slot_positions = {s.position: s for s in t.slots}

    for i, label in enumerate(t.shape):
        sep = r"\s+" if i > 0 else ""
        if label.startswith("key:"):
            key_name = label[len("key:"):]
            parts.append(sep + _escape_literal(key_name))
            if i + 1 < n and t.shape[i + 1] == "val":
                parts.append("=")
            continue
        if label == "val":
            # Immediately follows its key (joined by "=" above, no
            # separator needed here). The value slot that carries the
            # boolean-ish token (yes/no, true/false, ...) becomes the
            # named capture `val`; any other value-shaped slot is matched
            # but not captured.
            slot = slot_positions.get(i)
            if _is_boolean_domain(slot):
                parts.append(r"(?P<val>\S+)")
                value_group = "val"
            else:
                parts.append(r"\S+")
            continue
        # bare token: either the verb (position 0), the specific slot value
        # this extractor targets (anchored literal), or an unrelated
        # varying bare slot (matched loosely).
        if i == 0:
            parts.append(_escape_literal(t.verb))
            continue
        slot = slot_positions.get(i)
        if slot is not None and mapping.slot_value in slot.observed_values:
            parts.append(sep + _escape_literal(mapping.slot_value))
        elif slot is not None:
            parts.append(sep + r"\S+")
        else:
            parts.append(sep + r"\S+")

    # Trailing optional tokens (e.g. `[port=<n>]`) are made non-capturing
    # optional so the rule is robust across observed variants without
    # requiring every confirmed example to share the same tail.
    parts.append(r"(?: .*)?$")
    pattern = "".join(p for p in parts if p)
    return pattern, (value_group or "val")


def _is_boolean_domain(slot: Slot | None) -> bool:
    if slot is None:
        return False
    vals = {v.lower() for v in slot.observed_values}
    return len(vals) <= 4 and vals <= {"yes", "no", "true", "false", "on", "off", "enable", "disable"}


def _value_expr_for_mapping(t: Template, mapping: ConfirmedMapping, negation_key: str | None) -> str:
    """TRD-08.3 §3.3 — generated from the confirmed polarity and value
    domain, never authored freely. INV-08.3-02: the polarity decision is
    visible in the generated expression."""

    value_slot = next((s for s in t.slots if _is_boolean_domain(s)), None)
    if value_slot is None:
        # No boolean-shaped value slot on this template — the mapping
        # itself is a presence/absence fact (matching -> True).
        return "true"

    observed = {v.lower() for v in value_slot.observed_values}

    # Choose the token that should evaluate to True in the emitted
    # expression: if inverted, the "off-looking" token (no/false/off/
    # disable) is the one that means the target fact is True.
    true_token = None
    for tok in observed:
        as_bool = derive_boolean_value(negation_key or "", tok)
        if as_bool is True:
            true_token = tok
            break
    if true_token is None:
        true_token = "yes" if "yes" in observed else next(iter(observed), "yes")

    return f"val == '{true_token}'"


def synthesize(confirmation: Confirmation) -> list[dict[str, Any]]:
    """TRD-08.3 §3.1 — `synthesise(template, confirmation) -> Extractor`,
    one extractor dict per confirmed mapping, in the exact shape
    `rulepack_loader.load_rulepack` reads (07-vendor-rulepacks.md §5 /
    the real `routeros.yaml`)."""

    if not confirmation.mappings:
        raise SynthesisError("no confirmed mappings to synthesise from")

    for m in confirmation.mappings:
        if confirmation.negation_key and key_contains_negation(confirmation.negation_key) and not m.polarity_confirmed:
            raise SynthesisError(
                f"mapping for {m.slot_value!r} -> {m.fact_path!r} requires explicit polarity "
                "confirmation before synthesis (INV-08.3-02 / V-08.3-002)"
            )

    extractors: list[dict[str, Any]] = []
    for m in confirmation.mappings:
        pattern, value_group = _regex_for_mapping(confirmation.template, m)
        value_expr = _value_expr_for_mapping(confirmation.template, m, confirmation.negation_key)
        slug = re.sub(r"[^a-z0-9]+", "_", m.slot_value.lower()).strip("_") or "value"
        fact_slug = re.sub(r"[^a-z0-9]+", "_", m.fact_path.lower()).strip("_")
        extractor_id = f"{confirmation.template.enclosing_path.strip('/').replace(' ', '_').replace('/', '.')}.{slug}.{fact_slug}"

        extractors.append(
            {
                "extractor_id": extractor_id,
                "version": 1,
                "status": "provisional",
                "scope": {"kind": "any"},
                "match": pattern,
                "emit": [{"fact": m.fact_path, "value": value_expr}],
                "tests": [
                    {
                        "input": excerpt,
                        "expect": {m.fact_path: derive_boolean_value(confirmation.negation_key or "", val)},
                    }
                    for (_art, _lines, excerpt) in confirmation.template.source_lines
                    for val in [_extract_test_value(excerpt, confirmation.template)]
                    if m.slot_value in excerpt
                ],
                "provenance": {
                    "taught_by": confirmation.taught_by,
                    "taught_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "source_artifact": confirmation.source_artifact,
                    "confirmed_examples": len(confirmation.template.source_lines),
                    "polarity_confirmed": bool(m.polarity_confirmed),
                },
            }
        )
    return extractors


def _extract_test_value(excerpt: str, t: Template) -> str:
    """Pulls the observed boolean-domain token (yes/no/...) out of a
    source excerpt, for frozen-test generation (TRD-08.3 §5)."""

    for slot in t.slots:
        if _is_boolean_domain(slot):
            for v in slot.observed_values:
                if re.search(rf"[=\s]{re.escape(v)}(\s|$)", excerpt):
                    return v
    return ""


# ---------------------------------------------------------------------------
# Rulepack file I/O — 07-vendor-rulepacks.md §2's on-disk shape.
# ---------------------------------------------------------------------------


def default_rulepack_path(platform: str, knowledge_dir: Path) -> Path:
    return knowledge_dir / "rulepacks" / f"{platform}.yaml"


def load_or_init_rulepack_doc(path: Path, platform: str, vendor: str, grammar: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        doc = {
            "platform": platform,
            "vendor": vendor,
            "version": "0.1.0",
            "trust_tier": "provisional",
            "fingerprint": {"signatures": []},
            "grammar": grammar,
            "extractors": [],
            "defaults": {},
        }
    return doc


def write_extractors_to_rulepack(
    path: Path,
    platform: str,
    vendor: str,
    grammar: dict[str, Any],
    new_extractors: list[dict[str, Any]],
) -> Path:
    """Merges `new_extractors` into the platform's rulepack YAML (creating
    it if this is the platform's first taught rule) and writes it back.
    Deterministic key ordering / extractor ordering is the *loader's* job
    (`extractors.sort(key=lambda s: s.extractor_id)`, D6) — this writer
    does not need to pre-sort, but does so anyway for readable diffs."""

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = load_or_init_rulepack_doc(path, platform, vendor, grammar)

    existing_ids = {e["extractor_id"] for e in doc.get("extractors", [])}
    for ex in new_extractors:
        if ex["extractor_id"] in existing_ids:
            continue  # idempotent re-synthesis (e.g. re-running the same session)
        doc.setdefault("extractors", []).append(ex)
        existing_ids.add(ex["extractor_id"])

    doc["extractors"].sort(key=lambda e: e["extractor_id"])

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, sort_keys=False, default_flow_style=False)
    return path
