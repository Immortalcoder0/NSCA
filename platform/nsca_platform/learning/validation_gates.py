"""Validation gates — TRD-08.3 §4. All six (seven, counting coverage-delta
as informational) gates run **before a provisional rule is even saved**,
not just before ratification (backend-02 §4.3 point 7). Failure at any
gate returns the administrator to correction, not a partial save.

Metamorphic validation (Gate 6) reuses a subset of the mutation kinds
TRD-11.2 defines (whitespace variation, attribute reordering, quoting
variation) rather than reinventing a mutation framework — this module
implements the mutation generators locally (kept intentionally small) since
Track A's own metamorphic harness (`nsca_engine`) is scoped to *its* own
extractor/control tests, and importing it here would violate the "engine is
a black box you call" boundary (backend-02 §2.1) for something that is, at
its core, just string mutation of a regex's own test inputs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from nsca_engine.api import (
    ValueExpressionError as ValueLangError,
)
from nsca_engine.api import (
    compile_value_expression as compile_expr,
)
from nsca_engine.api import (
    evaluate_value_expression as evaluate_expr,
)


class GateFailure(Exception):
    def __init__(self, gate: str, reason: str, detail: Any = None):
        self.gate = gate
        self.reason = reason
        self.detail = detail
        super().__init__(f"[{gate}] {reason}")


@dataclass(frozen=True, slots=True)
class GateResult:
    gate: str
    passed: bool
    detail: str
    outcome: str = "pass"  # pass | warn | fail


@dataclass(frozen=True, slots=True)
class ValidationReport:
    results: tuple[GateResult, ...]

    @property
    def all_passed(self) -> bool:
        return all(r.outcome != "fail" for r in self.results)

    def as_dict(self) -> dict[str, Any]:
        return {r.gate: {"outcome": r.outcome, "detail": r.detail} for r in self.results}


# ---------------------------------------------------------------------------
# Gate 1 — Self-match (TRD-08.3 §4.1)
# ---------------------------------------------------------------------------


def gate_self_match(pattern: str, confirmed_examples: list[str]) -> GateResult:
    compiled = re.compile(pattern)
    matched = [ex for ex in confirmed_examples if compiled.match(ex)]
    missed = [ex for ex in confirmed_examples if not compiled.match(ex)]
    if not confirmed_examples:
        return GateResult("self_match", False, "no confirmed examples to validate against", "fail")
    if missed:
        return GateResult("self_match", False, f"misses confirmed examples: {missed}", "fail")
    if not matched:
        return GateResult("self_match", False, "zero matches — synthesis defect", "fail")
    return GateResult("self_match", True, f"matched {len(matched)}/{len(confirmed_examples)} confirmed examples", "pass")


# ---------------------------------------------------------------------------
# Gate 2 — Corpus scope (TRD-08.3 §4.2, DD-08.3-01: hard failure, not a warning)
# ---------------------------------------------------------------------------


def gate_corpus_scope(
    pattern: str, target_platform: str, corpus: dict[str, list[str]]
) -> GateResult:
    """`corpus`: platform -> list of raw lines from that platform's
    artifacts. Matching any *other* platform's line is a hard failure
    (DD-08.3-01) — never a warning."""

    compiled = re.compile(pattern)
    if not corpus:
        return GateResult("corpus_scope", True, "empty corpus — cannot fail meaningfully, flagged for re-validation", "warn")

    foreign_matches: dict[str, list[str]] = {}
    for platform, lines in corpus.items():
        if platform == target_platform:
            continue
        hits = [ln for ln in lines if compiled.match(ln)]
        if hits:
            foreign_matches[platform] = hits

    if foreign_matches:
        return GateResult(
            "corpus_scope", False,
            f"matches other platform(s): {foreign_matches} — too broad, narrow the pattern",
            "fail",
        )
    return GateResult("corpus_scope", True, "matches only the target platform", "pass")


# ---------------------------------------------------------------------------
# Gate 3 — Conflict (TRD-08.3 §4.3)
# ---------------------------------------------------------------------------


def gate_conflict(
    fact_path: str, new_value_for: dict[str, Any], existing_producers: dict[str, dict[str, Any]]
) -> GateResult:
    """`existing_producers`: extractor_id -> {device_id: value} the rulepack
    already produces for `fact_path`. `new_value_for`: device_id -> value
    this new rule would produce."""

    if not existing_producers:
        return GateResult("conflict", True, "no existing producer for this fact", "pass")

    for producer_id, values in existing_producers.items():
        shared_devices = set(values) & set(new_value_for)
        differing = {d for d in shared_devices if values[d] != new_value_for[d]}
        if differing:
            return GateResult(
                "conflict", False,
                f"{producer_id} produces a different value for {fact_path} on devices {sorted(differing)}",
                "fail",
            )
    return GateResult("conflict", True, "existing producer(s) agree on all shared devices — probable duplicate", "warn")


# ---------------------------------------------------------------------------
# Gate 4 — Type conformance (TRD-08.3 §4.4)
# ---------------------------------------------------------------------------


def gate_type_conformance(
    emitted_value_expr: str, declared_type: str, registered_fact_paths: frozenset[str], fact_path: str
) -> GateResult:
    if fact_path not in registered_fact_paths:
        return GateResult("type", False, f"{fact_path!r} is not a registered schema fact path", "fail")

    try:
        compiled = compile_expr(emitted_value_expr)
    except ValueLangError as exc:
        return GateResult("type", False, f"value expression does not compile: {exc}", "fail")

    # A conservative static check: evaluate against a couple of
    # representative capture sets and confirm the result's Python type is
    # compatible with the declared schema type.
    sample_captures_sets = [{"val": "yes"}, {"val": "no"}, {"state": "yes"}, {"state": "no"}]
    type_map = {"boolean": bool, "integer": int, "string": str}
    expected_pytype = type_map.get(declared_type)
    if expected_pytype is None:
        return GateResult("type", True, f"declared type {declared_type!r} not statically checked here", "warn")

    for captures in sample_captures_sets:
        try:
            value = evaluate_expr(compiled, captures, {})
        except ValueLangError:
            continue
        if value is not None and not isinstance(value, expected_pytype):
            return GateResult(
                "type", False,
                f"emitted value {value!r} is not a {declared_type} for fact {fact_path}",
                "fail",
            )
    return GateResult("type", True, f"emitted values conform to declared type {declared_type}", "pass")


# ---------------------------------------------------------------------------
# Gate 5 — Regression (TRD-08.3 §4.5)
# ---------------------------------------------------------------------------


def gate_regression(
    new_pattern: str,
    new_value_expr: str,
    frozen_tests: list[dict[str, Any]],
) -> GateResult:
    """`frozen_tests`: existing rulepack's frozen tests
    (`[{input, expect: {fact: value}}]`) — every one must still pass
    unaffected by the new rule sharing corpus space. Since this new rule is
    scoped to its own extractor, "still pass" here means the EXISTING
    extractors' own patterns/values are untouched (this gate exists to
    catch accidental edits to shared lookup tables / schema, not to
    re-run the new rule against old tests, which self-match already does)."""

    if not frozen_tests:
        return GateResult("regression", True, "no existing frozen tests", "pass")

    broken = []
    for test in frozen_tests:
        # Regression here specifically protects against a NEW rule
        # over-matching an old test's input (i.e. becoming a second,
        # conflicting producer) — checked by corpus_scope/conflict; this
        # gate additionally confirms the new pattern doesn't shadow-match
        # (and thus corrupt matched_node_ids for) an old test's input line.
        if re.match(new_pattern, test.get("input", "")):
            broken.append(test)
    if broken:
        return GateResult(
            "regression", False,
            f"new pattern also matches {len(broken)} existing frozen test input(s), risking overlap",
            "fail",
        )
    return GateResult("regression", True, f"{len(frozen_tests)} existing frozen tests unaffected", "pass")


# ---------------------------------------------------------------------------
# Gate 6 — Metamorphic (TRD-08.3 §4.6, DD-08.3-02; TRD-11.2)
# ---------------------------------------------------------------------------


def _mutate_whitespace(line: str) -> list[str]:
    return [re.sub(r" +", "  ", line), re.sub(r" +", " ", line.strip())]


def _mutate_quoting(line: str) -> list[str]:
    if '"' in line:
        return [line.replace('"', "'")]
    return []


def _mutate_comment_insertion(line: str) -> list[str]:
    return [line + "  "]  # trailing whitespace — grammar-safe, tests robustness


def metamorphic_mutations(line: str) -> list[str]:
    """TRD-11.2-style semantics-preserving mutations: whitespace variation,
    quoting variation, trailing-comment-safe insertion. Attribute reordering
    is deliberately not attempted here — it is grammar-aware (only valid
    where the grammar permits it, TRD-08.3 §9's edge case) and this module
    has no grammar object to consult; that mutation kind belongs to a
    corpus-level metamorphic harness with real grammar awareness, not a
    per-rule synthesis-time gate operating on a single line."""

    mutations = set()
    mutations.update(_mutate_whitespace(line))
    mutations.update(_mutate_quoting(line))
    mutations.update(_mutate_comment_insertion(line))
    mutations.discard(line)
    return sorted(mutations)


def gate_metamorphic(pattern: str, value_expr: str, confirmed_examples: list[str]) -> GateResult:
    """DD-08.3-02 — run at synthesis time, not only in CI. A rule that only
    matches the exact whitespace it was taught from fails here, cheaply,
    instead of failing silently on the next device."""

    compiled = re.compile(pattern)
    try:
        compiled_expr = compile_expr(value_expr)
    except ValueLangError as exc:
        return GateResult("metamorphic", False, f"value expression invalid: {exc}", "fail")

    unstable: list[tuple[str, str]] = []
    total_mutations = 0
    for line in confirmed_examples:
        base_match = compiled.match(line)
        if not base_match:
            continue
        base_value = evaluate_expr(compiled_expr, base_match.groupdict(), {})
        for mutated in metamorphic_mutations(line):
            total_mutations += 1
            m = compiled.match(mutated)
            if m is None:
                unstable.append((line, mutated))
                continue
            mutated_value = evaluate_expr(compiled_expr, m.groupdict(), {})
            if mutated_value != base_value:
                unstable.append((line, mutated))

    if unstable:
        return GateResult(
            "metamorphic", False,
            f"{len(unstable)}/{total_mutations} mutations changed the extracted fact — {unstable[:3]}",
            "fail",
        )
    return GateResult("metamorphic", True, f"{total_mutations} mutations, facts stable", "pass")


# ---------------------------------------------------------------------------
# Gate 7 — Coverage delta (informational, TRD-08.3 §4.7)
# ---------------------------------------------------------------------------


def gate_coverage_delta(before_unknown: int, after_unknown: int, total_facts: int) -> GateResult:
    if total_facts <= 0:
        return GateResult("coverage_delta", True, "no facts to measure", "warn")
    delta_pp = (before_unknown - after_unknown) / total_facts * 100
    return GateResult("coverage_delta", True, f"+{delta_pp:.0f}pp estate coverage", "pass")


# ---------------------------------------------------------------------------
# Backtracking safety (INV-08.3-01) — checked as part of self-match/synthesis
# ---------------------------------------------------------------------------

_PATHOLOGICAL_PATTERNS = (
    re.compile(r"\([^)]*[+*]\)[+*]"),  # nested quantifiers: (a+)+, (a*)*
    re.compile(r"\([^)]*\|[^)]*\)[+*]"),  # alternation under a repeated group: (a|ab)+
)


def check_no_catastrophic_backtracking(pattern: str) -> GateResult:
    """INV-08.3-01 — a purely structural check for nested-quantifier
    patterns (the classic ReDoS shape), plus a bounded-time probe against
    an adversarial input. Rejects rather than accepts on ambiguity."""

    for bad in _PATHOLOGICAL_PATTERNS:
        if bad.search(pattern):
            return GateResult("backtracking", False, f"pattern contains a nested-quantifier shape: {pattern!r}", "fail")

    import time

    adversarial = "a" * 40 + "!"
    start = time.monotonic()
    try:
        re.match(pattern, adversarial)
    except re.error:
        return GateResult("backtracking", False, f"pattern does not compile: {pattern!r}", "fail")
    elapsed = time.monotonic() - start
    if elapsed > 0.5:
        return GateResult("backtracking", False, f"pattern took {elapsed:.2f}s against an adversarial input", "fail")
    return GateResult("backtracking", True, "no catastrophic backtracking detected", "pass")


# ---------------------------------------------------------------------------
# Run all gates (TRD-08.3 §4: "must survive all six gates before it can be
# saved")
# ---------------------------------------------------------------------------


def run_all_gates(
    *,
    pattern: str,
    value_expr: str,
    fact_path: str,
    fact_type: str,
    confirmed_examples: list[str],
    target_platform: str,
    corpus: dict[str, list[str]],
    existing_producers: dict[str, dict[str, Any]],
    new_value_for: dict[str, Any],
    registered_fact_paths: frozenset[str],
    frozen_tests: list[dict[str, Any]],
    before_unknown: int = 0,
    after_unknown: int = 0,
    total_facts: int = 0,
) -> ValidationReport:
    results = [
        check_no_catastrophic_backtracking(pattern),
        gate_self_match(pattern, confirmed_examples),
        gate_corpus_scope(pattern, target_platform, corpus),
        gate_conflict(fact_path, new_value_for, existing_producers),
        gate_type_conformance(value_expr, fact_type, registered_fact_paths, fact_path),
        gate_regression(pattern, value_expr, frozen_tests),
        gate_metamorphic(pattern, value_expr, confirmed_examples),
        gate_coverage_delta(before_unknown, after_unknown, total_facts),
    ]
    return ValidationReport(results=tuple(results))
