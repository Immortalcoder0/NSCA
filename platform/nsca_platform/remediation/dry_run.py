"""Dry run — TRD-07.1 §3.6, backend-02 §4.4, M4.

`apply_remediation_to_facts` is Track B's own data transform (DD-07.1-03:
"the plan is translated into fact-level effects declared on the control ...
Dry run mutates facts, not text") — no engine call at all, just applying the
`FactEffect`s the plan already carries to a copy of the fact dict.

Re-evaluation is where the real, flagged contract gap lives. backend-02 §4.4
says: "Dry run re-evaluates using Track A's evaluation function against the
*modelled* post-remediation fact set ... expose whatever narrower entry
point you need for this — propose it as a contract addition if
`assess_device` doesn't already decompose cleanly enough to reuse just the
evaluation stage." Reading `nsca_engine/api.py` in full (this milestone):
`assess_device` runs Ingest -> Fingerprint -> Parse -> Extract -> Evaluate as
one pipeline over raw artifact *bytes*; there is no narrower entry point
that accepts an already-built fact set and control pack and returns
verdicts. **This is the exact gap backend-02 §7 names**: "it may need a
third, narrower engine entry point added to the contract." It does not
exist as of this milestone.

What *is* available and used here: `nsca_engine.api.compile_value_expression`
/ `evaluate_value_expression` — the extractor value-expression language
(TRD-03.1 §3.3). It is sufficient for the simple scalar boolean checks this
control pack's `dry_run_check` blocks declare (`"telnet == false and http ==
false"`), but it is **not** the same language as a control's real
`assert_expression` (`controls/expression.py`, which platform code may not
import) — in particular it has no lambda/list-predicate support
(`any(u => ...)`), so it cannot express `NSCA-AUTH-001`/`NSCA-AUTH-003`'s
real assertions. Those two controls' `dry_run_check` blocks use a
`kind: local_users_predicate` marker instead, evaluated by a small
hand-written Python predicate below (`_local_users_predicate`) that mirrors
— but does not call — the real control semantics.

**This module's dry run is therefore a reduced-fidelity re-evaluation**,
not a real re-assessment: it only knows about the handful of controls whose
`dry_run_check` was authored (a `kind: local_users_predicate` check or a
value_lang-expressible boolean), and every other FAIL/PASS finding on the
device is reported in `unmodelled` rather than silently assumed unchanged.
This is stated in every `DryRunResult` (`fidelity_note`), per the explicit
instruction in TRD-07.1 §3.6 / V-07.1-012: "Output states that the dry run
models the intended effect of the commands, not the device's actual
response, and that command application is not verified."
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from nsca_engine.api import (
    ValueExpressionError,
    compile_value_expression,
    evaluate_value_expression,
)

from nsca_platform.remediation.planner import (
    FactEffect,
    RemediationLibrary,
    RemediationPlan,
    dry_run_check_for,
)

FIDELITY_NOTE = (
    "This dry run models the intended effect of the remediation commands on "
    "the stored fact set; it does not re-run the device's actual assessment "
    "pipeline (no narrower nsca_engine.api entry point for fact-level "
    "re-evaluation exists as of this milestone — a flagged contract gap, see "
    "this module's docstring). Command application on the real device is not "
    "verified. Only controls with an authored `dry_run_check` participate; "
    "every other finding is listed in `unmodelled`, not assumed unchanged."
)


def apply_remediation_to_facts(
    facts: Mapping[str, Any], plan: RemediationPlan, *, only_unblocked: bool = True
) -> dict[str, Any]:
    """Pure data transform — TRD-07.1 DD-07.1-03. Blocked steps (lockout,
    INV-07.1-03) are excluded by default: a step the playbook "cannot be
    executed as written" cannot be assumed to have taken effect."""

    modelled = dict(facts)
    for step in plan.steps:
        if only_unblocked and step.blocked:
            continue
        for effect in step.fact_effects:
            _apply_effect(modelled, effect)
    return modelled


def _apply_effect(facts: dict[str, Any], effect: FactEffect) -> None:
    if effect.op == "set":
        facts[effect.path] = effect.value
    elif effect.op == "remove_admin":
        users = facts.get(effect.path) or []
        facts[effect.path] = [
            u for u in users
            if not (u.get("privilege_level", 0) >= 15 and u.get("username") == "admin")
        ]
    else:  # unrecognised op — leave the fact alone, never guess (fail closed)
        pass


def _local_users_predicate(want: str, users: Any) -> bool | None:
    if not isinstance(users, (list, tuple)):
        return None
    if want == "no_reversible_privileged":
        return not any(
            isinstance(u, Mapping) and u.get("privilege_level", 0) >= 15 and u.get("reversible") is True
            for u in users
        )
    if want == "has_privileged":
        return any(isinstance(u, Mapping) and u.get("privilege_level", 0) >= 15 for u in users)
    return None  # unrecognised predicate kind


def _evaluate_check(check: Mapping[str, Any], facts: Mapping[str, Any]) -> bool | None:
    """Returns True/False, or `None` if the check cannot be evaluated
    against this fact set (e.g. an unknown/missing fact — never guessed)."""

    if check.get("kind") == "local_users_predicate":
        captures = check.get("captures", {})
        path = captures.get("users")
        if path is None:
            return None
        return _local_users_predicate(check.get("want", ""), facts.get(path))

    expr = check.get("expression")
    if not expr:
        return None
    captures_spec: Mapping[str, str] = check.get("captures", {})
    captures: dict[str, Any] = {}
    for name, path in captures_spec.items():
        value = facts.get(path)
        if value is None:
            return None  # unknown fact -> cannot evaluate, never guess
        captures[name] = value
    try:
        compiled = compile_value_expression(expr)
        return bool(evaluate_value_expression(compiled, captures))
    except ValueExpressionError:
        return None


@dataclass(frozen=True, slots=True)
class NewlyFailing:
    control_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class DryRunResult:
    before_pass: int
    before_determined: int
    after_pass: int
    after_determined: int
    before_coverage_determined: int
    before_coverage_applicable: int
    after_coverage_determined: int
    after_coverage_applicable: int
    resolved: tuple[str, ...]
    newly_failing: tuple[NewlyFailing, ...]
    unmodelled: tuple[str, ...]
    fidelity_note: str = FIDELITY_NOTE

    @property
    def before_compliance(self) -> Fraction:
        return Fraction(self.before_pass, self.before_determined) if self.before_determined else Fraction(0)

    @property
    def after_compliance(self) -> Fraction:
        return Fraction(self.after_pass, self.after_determined) if self.after_determined else Fraction(0)

    @property
    def coverage_unchanged(self) -> bool:
        """V-07.1-007: "Coverage must not change during a dry run. If it
        does, the fact-effect declaration is wrong." Both counts are the
        *number of controls this dry run could evaluate at all* (had a
        `dry_run_check` AND resolvable captures) before vs after — since
        remediation never adds or removes facts this module doesn't already
        know about (it only ever `set`s declared paths), this is expected to
        hold by construction; this property is what a caller asserts against
        to catch a defective declaration (the corpus/property test)."""

        return (
            self.before_coverage_determined == self.after_coverage_determined
            and self.before_coverage_applicable == self.after_coverage_applicable
        )


def dry_run(
    device_findings: list[Mapping[str, Any]],
    facts: Mapping[str, Any],
    plan: RemediationPlan,
    *,
    library: RemediationLibrary,
) -> DryRunResult:
    """TRD-07.1 §4's `dry_run(plan, device) -> ⟨before, after, resolved[],
    newly_failing[]⟩`.

    `device_findings` is every current finding on the device (not just the
    ones targeted by `plan`) — needed so newly-failing controls elsewhere
    can be detected (V-07.1-006). Each entry needs `control`/`control_id`
    and `verdict`.
    """

    modelled = apply_remediation_to_facts(facts, plan)

    before_pass = after_pass = 0
    before_determined = after_determined = 0
    before_cov = after_cov = 0
    applicable = 0
    resolved: list[str] = []
    newly_failing: list[NewlyFailing] = []
    unmodelled: list[str] = []

    targeted_controls = {s.control_id for s in plan.steps}

    for f in sorted(device_findings, key=lambda d: d.get("control", d.get("control_id", ""))):
        control_id = f.get("control") or f.get("control_id")
        verdict = f.get("verdict")
        if verdict == "NOT_APPLICABLE":
            continue
        applicable += 1

        check = dry_run_check_for(library, control_id, plan.platform, plan.os_version)
        if check is None:
            unmodelled.append(control_id)
            continue

        before_result = _evaluate_check(check, facts)
        after_result = _evaluate_check(check, modelled)

        if before_result is None or after_result is None:
            unmodelled.append(control_id)
            continue

        before_cov += 1
        after_cov += 1
        before_determined += 1
        after_determined += 1
        if before_result:
            before_pass += 1
        if after_result:
            after_pass += 1

        if not before_result and after_result and control_id in targeted_controls:
            resolved.append(control_id)
        elif before_result and not after_result:
            newly_failing.append(
                NewlyFailing(
                    control_id=control_id,
                    reason=(
                        f"{control_id} was PASS before this plan and FAIL after — a step in "
                        f"this plan modifies a fact this control depends on. Review before applying."
                    ),
                )
            )

    return DryRunResult(
        before_pass=before_pass, before_determined=before_determined,
        after_pass=after_pass, after_determined=after_determined,
        before_coverage_determined=before_cov, before_coverage_applicable=applicable,
        after_coverage_determined=after_cov, after_coverage_applicable=applicable,
        resolved=tuple(sorted(resolved)),
        newly_failing=tuple(sorted(newly_failing, key=lambda n: n.control_id)),
        unmodelled=tuple(sorted(set(unmodelled))),
    )
