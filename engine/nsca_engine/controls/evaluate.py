"""Control evaluation: applicability, verdict, coverage, vacuity (TRD-05.2).

The single most important property in this module (backend-01 §5.4,
V-05.2-004/V-05.2-001): the ``requires_facts`` knowledge check is a
**structural pre-check**, run before the expression evaluator is invoked at
all. If any fact a control declares as required is missing from the fact set
or has provenance ``default_unknown``, the verdict is ``UNKNOWN``,
unconditionally — never a side effect of the Kleene evaluator happening to
return ``⊥``.

Open question flagged, not silently resolved (see the M1 report): TRD-05.2
§3.1 describes a subtler pipeline where the knowledge gate does *not*
short-circuit a definite Kleene result (`false and ⊥ = false` should still
surface as FAIL per TRD-05.1 DD-05.1-01). backend-01 §5.4 instead asks for an
unconditional pre-check on `requires_facts` membership, independent of what
the expression could otherwise resolve. This module implements backend-01
§5.4 literally, because that is the explicit instruction for this milestone
and because it is the more conservative (G2-safer) of the two readings — but
it means a control whose `requires_facts` includes an unknown fact can never
surface a "real" FAIL that Kleene logic alone would have found from other,
determined facts. This is a genuine tension between TRD-05.1/05.2 and
backend-01 that should be resolved by whoever owns both documents.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from nsca_engine.controls.expression import CompiledExpression, Kleene
from nsca_engine.controls.expression import evaluate as kleene_evaluate
from nsca_engine.types import (
    DeviceFinding,
    DeviceScores,
    Evidence,
    Fact,
    PassQuality,
    ProvenanceSource,
    Severity,
    UnknownReason,
    Verdict,
)

_SCOPE_QUALIFIER = re.compile(r"^vty\[(\d+)\.\.(\d+)\]\.(.+)$")
_INDEXED_PATH = re.compile(r"^(?P<base>.+)\[(?P<idx>\d+)\]\.(?P<field>.+)$")


@dataclass(frozen=True, slots=True)
class Applicability:
    platform_family: tuple[str, ...] = ("*",)  # "*" matches every platform


@dataclass(frozen=True, slots=True)
class VacuitySpec:
    meaningful_when: CompiledExpression | None = None


@dataclass(frozen=True, slots=True)
class NativeControl:
    control_id: str
    title: str
    family: str
    severity_base: Severity
    applies_to: Applicability
    requires_facts: tuple[str, ...]
    assertion: CompiledExpression
    scope_aggregation: str = "all"  # none | all | any — DD-05.1-03 default
    vacuity: VacuitySpec | None = None
    framework_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ControlEvalResult:
    control_id: str
    verdict: Verdict
    pass_quality: PassQuality | None
    unknown_reason: UnknownReason | None
    deciding_fact: str | None
    trace: tuple[str, ...]


def _fact_index(facts: tuple[Fact, ...]) -> dict[str, Fact]:
    return {f.path: f for f in facts}


def _resolve_base_or_scoped(
    base_path: str, by_path: Mapping[str, Fact]
) -> list[Fact]:
    """A control's `requires_facts`/assertion reference plain base paths
    (e.g. `mgmt.protocols.telnet.enabled`). Resolve either the unqualified
    fact, or every VTY-scope-qualified instance of it (TRD-03.1 §3.4,
    TRD-05.1 §3.6)."""

    if base_path in by_path:
        return [by_path[base_path]]
    scoped = [
        f for p, f in by_path.items() if _SCOPE_QUALIFIER.match(p) and p.endswith("." + base_path)
    ]
    return scoped


def _collection_elements(
    base_path: str, by_path: Mapping[str, Fact]
) -> list[dict[str, Any]] | None:
    """Assemble a collection fact path (e.g. `auth.local_users`) from its
    indexed scalar facts (extract/runtime.py's collection-extraction shape)
    into a list of dict-like elements for the expression language's
    quantifiers. Returns ``None`` (⊥) if any contributing field is itself
    unknown (INV-05.1-01: an unknown-valued collection is not empty)."""

    groups: dict[int, dict[str, Any]] = {}
    any_unknown = False
    found = False
    for path, fact in by_path.items():
        m = _INDEXED_PATH.match(path)
        if not m or m.group("base") != base_path:
            continue
        found = True
        idx = int(m.group("idx"))
        groups.setdefault(idx, {})[m.group("field")] = fact.value
        if fact.provenance.source == ProvenanceSource.DEFAULT_UNKNOWN:
            any_unknown = True
    if not found:
        return None
    if any_unknown:
        return None
    return [groups[i] for i in sorted(groups)]


def _make_resolver(
    by_path: Mapping[str, Fact], scope_value_override: dict[str, Any] | None
) -> Callable[[str], Any]:
    scope_value_override = scope_value_override or {}

    def resolve(path: str) -> Any:
        if path in scope_value_override:
            return scope_value_override[path]
        if path in by_path:
            return by_path[path].value
        collection = _collection_elements(path, by_path)
        if collection is not None:
            return collection
        return None  # ⊥ — unresolvable path is treated as unknown, never false

    return resolve


def _knowledge_gate(
    control: NativeControl, by_path: Mapping[str, Fact]
) -> str | None:
    """backend-01 §5.4 structural pre-check. Returns the offending fact path
    if any `requires_facts` entry is missing or `default_unknown`; ``None``
    if the gate passes."""

    for base_path in control.requires_facts:
        instances = _resolve_base_or_scoped(base_path, by_path)
        if not instances:
            # Might be a collection path (auth.local_users) rather than scalar.
            collection = _collection_elements(base_path, by_path)
            if collection is None:
                return base_path
            continue
        for fact in instances:
            if fact.provenance.source == ProvenanceSource.DEFAULT_UNKNOWN:
                return base_path
    return None


def applicable(control: NativeControl, platform: str) -> bool:
    if "*" in control.applies_to.platform_family:
        return True
    return platform in control.applies_to.platform_family


def evaluate_control(
    control: NativeControl,
    facts: tuple[Fact, ...],
    platform: str,
    lookup_tables: Mapping[str, Any] | None = None,
) -> ControlEvalResult:
    by_path = _fact_index(facts)

    if not applicable(control, platform):
        return ControlEvalResult(
            control_id=control.control_id, verdict=Verdict.NOT_APPLICABLE,
            pass_quality=None, unknown_reason=None, deciding_fact=None, trace=(),
        )

    gate_fact = _knowledge_gate(control, by_path)
    if gate_fact is not None:
        return ControlEvalResult(
            control_id=control.control_id, verdict=Verdict.UNKNOWN,
            pass_quality=None, unknown_reason=UnknownReason.DEFAULT_UNKNOWN,
            deciding_fact=gate_fact, trace=(f"required fact {gate_fact} is unknown",),
        )

    # Scope-qualified aggregation (TRD-05.1 §3.6, DD-05.1-03: default "all").
    scoped_bases: list[str] = []
    for bp in control.requires_facts:
        if bp in by_path:
            continue
        instances = _resolve_base_or_scoped(bp, by_path)
        if instances and any(_SCOPE_QUALIFIER.match(f.path) for f in instances):
            scoped_bases.append(bp)

    if scoped_bases:
        instance_keys: set[tuple[int, int]] = set()
        for bp in scoped_bases:
            for f in _resolve_base_or_scoped(bp, by_path):
                m = _SCOPE_QUALIFIER.match(f.path)
                if m:
                    instance_keys.add((int(m.group(1)), int(m.group(2))))
        results: list[tuple[Kleene, tuple[str, ...], str]] = []
        for lo, hi in sorted(instance_keys):
            qualifier = f"vty[{lo}..{hi}]"
            overrides: dict[str, Any] = {}
            for bp in scoped_bases:
                qpath = f"{qualifier}.{bp}"
                if qpath in by_path:
                    overrides[bp] = by_path[qpath].value
            resolver = _make_resolver(by_path, overrides)
            value, trace = kleene_evaluate(control.assertion, resolver, lookup_tables)
            results.append((value, trace, f"vty[{lo}..{hi}]"))
        values = [v for v, _, _ in results]
        agg = control.scope_aggregation
        if agg == "any":
            final = True if any(v is True for v in values) else (
                None if any(v is None for v in values) else False
            )
        elif agg == "none":
            final = False if any(v is True for v in values) else (
                None if any(v is None for v in values) else True
            )
        else:  # "all" default (DD-05.1-03)
            final = False if any(v is False for v in values) else (
                None if any(v is None for v in values) else True
            )
        deciding = next((label for v, _, label in results if v is False), None) or (
            next((label for v, _, label in results if v is None), None)
        )
        trace = tuple(t for _, tr, _ in results for t in tr)
        result_value = final
    else:
        resolver = _make_resolver(by_path, None)
        result_value, trace = kleene_evaluate(control.assertion, resolver, lookup_tables)
        deciding = None

    if result_value is None:
        return ControlEvalResult(
            control_id=control.control_id, verdict=Verdict.UNKNOWN,
            pass_quality=None, unknown_reason=UnknownReason.FACTS_MISSING,
            deciding_fact=deciding, trace=trace,
        )
    if result_value is False:
        return ControlEvalResult(
            control_id=control.control_id, verdict=Verdict.FAIL,
            pass_quality=None, unknown_reason=None, deciding_fact=deciding, trace=trace,
        )

    # PASS — vacuity classification (TRD-05.2 §3.5, DD-05.2-02).
    pass_quality = PassQuality.MEANINGFUL
    if control.vacuity is not None and control.vacuity.meaningful_when is not None:
        resolver = _make_resolver(by_path, None)
        vac_value, _ = kleene_evaluate(control.vacuity.meaningful_when, resolver, lookup_tables)
        if vac_value is False:
            pass_quality = PassQuality.VACUOUS
        # vac_value is None -> stays MEANINGFUL (DD-05.2-02)

    return ControlEvalResult(
        control_id=control.control_id, verdict=Verdict.PASS,
        pass_quality=pass_quality, unknown_reason=None, deciding_fact=None, trace=trace,
    )


# ---------------------------------------------------------------------------
# Coverage / compliance arithmetic (TRD-05.2 §3.4, INV-05.2-02) — D5: exact
# Fraction, never float.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CoverageSummary:
    coverage: Fraction | None
    compliance: Fraction | None
    meaningful_ratio: Fraction | None
    pass_count: int
    fail_count: int
    unknown_count: int
    not_applicable_count: int
    meaningful_count: int


def summarize(results: tuple[ControlEvalResult, ...]) -> CoverageSummary:
    pass_count = sum(1 for r in results if r.verdict == Verdict.PASS)
    fail_count = sum(1 for r in results if r.verdict == Verdict.FAIL)
    unknown_count = sum(1 for r in results if r.verdict == Verdict.UNKNOWN)
    na_count = sum(1 for r in results if r.verdict == Verdict.NOT_APPLICABLE)
    meaningful_count = sum(
        1 for r in results if r.verdict == Verdict.PASS and r.pass_quality == PassQuality.MEANINGFUL
    )

    applicable_n = pass_count + fail_count + unknown_count
    determined_n = pass_count + fail_count

    coverage = Fraction(determined_n, applicable_n) if applicable_n else None
    compliance = Fraction(pass_count, determined_n) if determined_n else None
    meaningful_ratio = Fraction(meaningful_count, pass_count) if pass_count else None

    return CoverageSummary(
        coverage=coverage, compliance=compliance, meaningful_ratio=meaningful_ratio,
        pass_count=pass_count, fail_count=fail_count, unknown_count=unknown_count,
        not_applicable_count=na_count, meaningful_count=meaningful_count,
    )


def to_device_findings(
    results: tuple[ControlEvalResult, ...],
    controls_by_id: Mapping[str, NativeControl],
    facts: tuple[Fact, ...],
) -> tuple[DeviceFinding, ...]:
    by_path = _fact_index(facts)
    _EVIDENCE_ELIGIBLE = (
        ProvenanceSource.EXPLICIT, ProvenanceSource.DEFAULT_KNOWN,
        ProvenanceSource.DERIVED, ProvenanceSource.INHERITED,
        # Phase 3 demo rehearsal fix (finding 11, §9 checklist item 11):
        # DEFAULT_UNKNOWN used to be excluded here, which is exactly the
        # class of absence-based finding the rehearsal caught with empty
        # evidence — a `default_unknown` fact now always carries an
        # `artifact_id` (see `extract/provenance.py::classify_absent`), so
        # it has a real "we looked and found nothing" citation to surface,
        # same as every other source.
        ProvenanceSource.DEFAULT_UNKNOWN,
    )
    out: list[DeviceFinding] = []
    for r in sorted(results, key=lambda x: x.control_id):
        control = controls_by_id[r.control_id]
        evidence: list[Evidence] = []
        for base_path in control.requires_facts:
            scoped = _resolve_base_or_scoped(base_path, by_path)
            if scoped:
                for f in scoped:
                    if f.provenance.source in _EVIDENCE_ELIGIBLE:
                        evidence.append(
                            Evidence(
                                artifact_id=f.provenance.artifact_id or "",
                                lines=f.provenance.lines,
                                highlight_lines=f.provenance.lines,
                                excerpt=f.provenance.excerpt or "",
                                fact_paths=(f.path,),
                            )
                        )
                continue
            # `base_path` names a collection (e.g. `auth.local_users`,
            # `snmp.communities`) rather than a scalar/scope-qualified fact
            # — `_resolve_base_or_scoped` only ever resolves the latter, so
            # a control whose `requires_facts` is a bare collection path
            # (NSCA-AUTH-001's `auth.local_users`, the rehearsal's own
            # example) got zero evidence regardless of provenance, even
            # with real, explicit per-element facts sitting right there.
            # Phase 3 demo rehearsal fix: one evidence entry per collection
            # element/index, from whichever of that element's own fields
            # carries the strongest citation (real lines preferred over a
            # lineless default citation).
            by_index: dict[int, list[Fact]] = {}
            for path, f in by_path.items():
                m = _INDEXED_PATH.match(path)
                if m and m.group("base") == base_path:
                    by_index.setdefault(int(m.group("idx")), []).append(f)
            for idx in sorted(by_index):
                candidates = [
                    f for f in by_index[idx] if f.provenance.source in _EVIDENCE_ELIGIBLE
                ]
                if not candidates:
                    continue
                chosen = next((f for f in candidates if f.provenance.lines), candidates[0])
                evidence.append(
                    Evidence(
                        artifact_id=chosen.provenance.artifact_id or "",
                        lines=chosen.provenance.lines,
                        highlight_lines=chosen.provenance.lines,
                        excerpt=chosen.provenance.excerpt or "",
                        fact_paths=(chosen.path,),
                    )
                )
        out.append(
            DeviceFinding(
                control_id=r.control_id,
                verdict=r.verdict,
                pass_quality=r.pass_quality,
                unknown_reason=r.unknown_reason,
                severity=control.severity_base,
                severity_reason=None,
                evidence=tuple(evidence),
                framework_refs=control.framework_refs,
                contamination_reason=None,
                coverage_inputs={"deciding_fact": r.deciding_fact} if r.deciding_fact else {},
            )
        )
    return tuple(out)


def to_device_scores(summary: CoverageSummary) -> DeviceScores:
    zero = Fraction(0)
    return DeviceScores(
        compliance_score=summary.compliance if summary.compliance is not None else zero,
        coverage_score=summary.coverage if summary.coverage is not None else zero,
        meaningful_ratio=summary.meaningful_ratio if summary.meaningful_ratio is not None else zero,
        security_score=summary.compliance if summary.compliance is not None else zero,
        pass_count=summary.pass_count,
        fail_count=summary.fail_count,
        unknown_count=summary.unknown_count,
        not_applicable_count=summary.not_applicable_count,
        partial_count=0,
    )
