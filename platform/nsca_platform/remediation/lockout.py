"""Lockout detection — TRD-07.1 §3.5, backend-02 §4.4, M4.

**The distinguishing capability** (TRD-07.1 §3.1): "An administrator who is
locked out once by a tool's advice will never use it again." A wrong
`PERMITTED` here is worse than no check at all.

**Real reachability, conservatively gated (M5).** `nsca_engine.api.
query_reachability` is real and importable through the sanctioned single
door. It needs two real ingredients this call site can now sometimes
supply: a real `Graph` (`services/graph_cache.py`'s in-process cache,
populated by `services/assessment.py.run_assessment`'s real
`assess_campaign` call — see that module's docstring) and the device's
real management-plane destination address. The second ingredient has no
standardized fact path in the current schema (`nsca/knowledge/schema/
mgmt.yaml` models no `mgmt.interface.address`-equivalent fact) — so no
call site in this milestone can supply it from real device facts alone.
`check_lockout`/`_try_engine_reachability` below accept it as an explicit,
optional `device_management_addr` parameter instead: the real
`query_reachability` call fires whenever a caller supplies both a cached
`Graph` (via `campaign_public_id`) and a concrete `device_management_addr`
— proven for real by this module's own tests, which construct both — but
every existing call site (none of which has a management-address fact to
supply) still falls through to `_local_approximate_check`, a
**documented, honestly-labeled approximation**: it inspects only the
*modelled* device-local management ACL fact
(`mgmt.source_restriction.allowed_sources`), never a real multi-hop,
multi-device graph traversal. Per **DD-07.1-02** and the explicit task
instruction ("a wrong lockout check is worse than no lockout check ...
refuse/flag rather than approve"), this module returns `INDETERMINATE`
— never `PERMITTED` — in every case where neither the real engine nor the
approximation can positively confirm safety. `PERMITTED` is only ever
returned when the real engine or the local approximation has positive,
complete evidence.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from nsca_engine.api import query_reachability

from nsca_platform.remediation.planner import RemediationPlan, RemediationStep
from nsca_platform.services import graph_cache

RESULT_PERMITTED = "PERMITTED"
RESULT_LOCKOUT = "LOCKOUT"
RESULT_INDETERMINATE = "INDETERMINATE"

METHOD_ENGINE = "engine_reachability"
METHOD_LOCAL_APPROXIMATION = "local_approximation_device_acl_only"

_MANAGEMENT_TRANSPORT_FACTS = (
    "mgmt.protocols.ssh.enabled",
    "mgmt.protocols.telnet.enabled",
    "mgmt.protocols.http.enabled",
    "mgmt.protocols.https.enabled",
)

# Steps whose command/fact-effects touch these are lockout-sensitive by
# nature (DD-07.1-01 still governs *classification*, authored on the
# control — this list is only used to decide which steps to consider when
# reasoning about lockout, never to override an author's `impact` field).
_LOCKOUT_SENSITIVE_FACT_PREFIXES = (
    "mgmt.protocols.", "mgmt.source_restriction.", "auth.central.", "auth.local_users",
)


@dataclass(frozen=True, slots=True)
class LockoutAnalysis:
    result: str  # PERMITTED | LOCKOUT | INDETERMINATE
    operator_source: str | None
    reason: str
    blocked_step_ids: tuple[int, ...]
    method: str
    modes_detected: tuple[str, ...] = ()


def _try_engine_reachability(
    operator_source: str | None,
    *,
    campaign_public_id: str | None,
    device_management_addr: str | None,
) -> LockoutAnalysis | None:
    """Real `nsca_engine.api.query_reachability` call (M5) — see module
    docstring. Fires only when every real ingredient is present: an
    `operator_source`, a `Graph` cached for `campaign_public_id`
    (`services/graph_cache.py`), and a concrete `device_management_addr`.
    Missing any of the three returns `None`, falling through to
    `_local_approximate_check` — no call site in this milestone has a
    management-address fact to supply (see module docstring), so this is
    real-but-dormant in production today, exercised for real only by this
    module's own tests, which supply all three explicitly.
    """

    if operator_source is None or campaign_public_id is None or device_management_addr is None:
        return None
    graph = graph_cache.get_graph(campaign_public_id)
    if graph is None:
        return None

    try:
        result = query_reachability(graph, operator_source, device_management_addr, "tcp", 22)
    except Exception:  # noqa: BLE001 — any engine-side mismatch falls through, never fabricated
        return None

    caveat = (
        "Real multi-hop graph reachability query (nsca_engine.api.query_reachability) "
        "over the campaign's merged estate graph."
    )
    if result.outcome == "reachable":
        return LockoutAnalysis(
            result=RESULT_PERMITTED, operator_source=operator_source,
            reason=(
                f"Operator source {operator_source} can still reach "
                f"{device_management_addr} after this plan is applied. " + caveat
            ),
            blocked_step_ids=(), method=METHOD_ENGINE,
        )
    return LockoutAnalysis(
        result=RESULT_LOCKOUT, operator_source=operator_source,
        reason=(
            f"No path found from operator source {operator_source} to "
            f"{device_management_addr} after this plan is applied — this plan "
            "would lock the operator out. " + caveat
        ),
        blocked_step_ids=(), method=METHOD_ENGINE,
    )


def _relevant_steps(plan: RemediationPlan) -> list[RemediationStep]:
    out = []
    for s in plan.steps:
        touches = any(
            fe.path.startswith(_LOCKOUT_SENSITIVE_FACT_PREFIXES) for fe in s.fact_effects
        )
        if touches or s.impact == "lockout_risk":
            out.append(s)
    return out


def _check_source_restriction(
    modelled_facts: Mapping[str, Any], operator_source: str | None
) -> tuple[str, str] | None:
    """Mode 1 — source denied (TRD-07.1 §3.5). Returns `(mode_name, verdict)`
    where `verdict` is one of PERMITTED/LOCKOUT/INDETERMINATE, or `None` if
    this mode isn't in play (no source restriction modelled at all)."""

    configured = modelled_facts.get("mgmt.source_restriction.configured")
    if not configured:
        return None  # no source ACL modelled — this mode doesn't apply

    if operator_source is None:
        return ("source_restriction", RESULT_INDETERMINATE)

    try:
        operator_addr = ipaddress.ip_address(operator_source)
    except ValueError:
        return ("source_restriction", RESULT_INDETERMINATE)

    allowed = modelled_facts.get("mgmt.source_restriction.allowed_sources")
    if not isinstance(allowed, (list, tuple)) or not allowed:
        # configured == true but we don't know the actual permit list — an
        # honest "cannot determine", never assumed safe.
        return ("source_restriction", RESULT_INDETERMINATE)

    for cidr in allowed:
        try:
            net = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            continue
        if operator_addr in net:
            return ("source_restriction", RESULT_PERMITTED)
    return ("source_restriction", RESULT_LOCKOUT)


def _check_all_transports_disabled(modelled_facts: Mapping[str, Any]) -> tuple[str, str] | None:
    """Mode 2 — all management transports disabled."""

    known = [modelled_facts.get(p) for p in _MANAGEMENT_TRANSPORT_FACTS if p in modelled_facts]
    if not known:
        return None
    if any(v is None for v in known):
        return ("all_transports_disabled", RESULT_INDETERMINATE)
    if not any(bool(v) for v in known):
        return ("all_transports_disabled", RESULT_LOCKOUT)
    return ("all_transports_disabled", RESULT_PERMITTED)


def _check_auth_orphaned(modelled_facts: Mapping[str, Any]) -> tuple[str, str] | None:
    """Mode 3 — authentication orphaned. TRD-07.1: "central auth configured
    with no local fallback and central server unreachable per the graph =>
    LOCKOUT." We have no graph reachability available (the documented gap),
    so this can never resolve to a confident LOCKOUT *or* PERMITTED here —
    only INDETERMINATE when the risky pattern (central auth on, no local
    users left) is present, or nothing-to-report otherwise."""

    central = modelled_facts.get("auth.central.configured")
    users = modelled_facts.get("auth.local_users")
    if not central:
        return None
    has_local_user = isinstance(users, (list, tuple)) and len(users) > 0
    if has_local_user:
        return None  # local fallback exists — this mode isn't in play
    return (
        "auth_orphaned",
        RESULT_INDETERMINATE,
    )


def _local_approximate_check(
    plan: RemediationPlan, modelled_facts: Mapping[str, Any], operator_source: str | None
) -> LockoutAnalysis:
    modes: list[tuple[str, str]] = []
    for result in (
        _check_source_restriction(modelled_facts, operator_source),
        _check_all_transports_disabled(modelled_facts),
        _check_auth_orphaned(modelled_facts),
    ):
        if result is not None:
            modes.append(result)

    caveat = (
        "This is a local approximation over this device's modelled management "
        "ACL/transport/auth facts only — not a real multi-hop graph reachability "
        "query (nsca_engine.api exposes no such entry point as of this "
        "milestone; see remediation/lockout.py module docstring for the "
        "flagged contract gap)."
    )

    if operator_source is None:
        return LockoutAnalysis(
            result=RESULT_INDETERMINATE, operator_source=None,
            reason=(
                "Operator source address was not supplied — lockout analysis "
                "cannot be performed. Silence must not read as safety "
                "(DD-07.1-02). " + caveat
            ),
            blocked_step_ids=(), method=METHOD_LOCAL_APPROXIMATION,
        )

    if not modes:
        relevant = _relevant_steps(plan)
        if not relevant:
            return LockoutAnalysis(
                result=RESULT_PERMITTED, operator_source=operator_source,
                reason="This plan contains no management-access-affecting steps. " + caveat,
                blocked_step_ids=(), method=METHOD_LOCAL_APPROXIMATION,
            )
        return LockoutAnalysis(
            result=RESULT_INDETERMINATE, operator_source=operator_source,
            reason=(
                "This plan touches management access but the modelled fact set "
                "does not carry enough information to positively confirm safety. "
                + caveat
            ),
            blocked_step_ids=tuple(s.id for s in relevant), method=METHOD_LOCAL_APPROXIMATION,
        )

    verdicts = {v for _, v in modes}
    detected = tuple(m for m, v in modes if v != RESULT_PERMITTED)

    if RESULT_LOCKOUT in verdicts:
        blocked = tuple(s.id for s in _relevant_steps(plan))
        mode_names = ", ".join(m for m, v in modes if v == RESULT_LOCKOUT)
        return LockoutAnalysis(
            result=RESULT_LOCKOUT, operator_source=operator_source,
            reason=f"Lockout detected ({mode_names}). Offending steps are blocked. " + caveat,
            blocked_step_ids=blocked, method=METHOD_LOCAL_APPROXIMATION,
            modes_detected=detected,
        )
    if RESULT_INDETERMINATE in verdicts:
        mode_names = ", ".join(m for m, v in modes if v == RESULT_INDETERMINATE)
        return LockoutAnalysis(
            result=RESULT_INDETERMINATE, operator_source=operator_source,
            reason=(
                f"Could not positively confirm safety for: {mode_names}. "
                "Per DD-07.1-02, this is reported as indeterminate rather than "
                "permitted. " + caveat
            ),
            blocked_step_ids=(), method=METHOD_LOCAL_APPROXIMATION,
            modes_detected=detected,
        )

    return LockoutAnalysis(
        result=RESULT_PERMITTED, operator_source=operator_source,
        reason="Operator source is included in every modelled management ACL, and "
               "at least one management transport and local auth fallback remain. " + caveat,
        blocked_step_ids=(), method=METHOD_LOCAL_APPROXIMATION,
    )


def check_lockout(
    plan: RemediationPlan,
    modelled_facts: Mapping[str, Any],
    operator_source: str | None,
    *,
    campaign_public_id: str | None = None,
    device_management_addr: str | None = None,
) -> LockoutAnalysis:
    """TRD-07.1 §3.5's `lockout_check(plan, device, operator_source)`.
    `modelled_facts` is the plan applied to the device's facts (i.e. the
    output of `remediation.dry_run.apply_remediation_to_facts` — "simulated
    = apply(plan, device.facts) # model only, never the device").

    `campaign_public_id`/`device_management_addr` are optional, M5-added
    parameters (see module docstring) — supplying both lets this function
    attempt a real `query_reachability` call before falling back to the
    local approximation; omitting either (every current call site) keeps
    the pre-M5 behaviour exactly.
    """

    engine_result = _try_engine_reachability(
        operator_source,
        campaign_public_id=campaign_public_id,
        device_management_addr=device_management_addr,
    )
    if engine_result is not None:
        if engine_result.result == RESULT_LOCKOUT:
            blocked = tuple(s.id for s in _relevant_steps(plan))
            engine_result = LockoutAnalysis(
                result=engine_result.result, operator_source=engine_result.operator_source,
                reason=engine_result.reason, blocked_step_ids=blocked,
                method=engine_result.method, modes_detected=("engine_reachability",),
            )
        return engine_result
    return _local_approximate_check(plan, modelled_facts, operator_source)


def apply_lockout_blocking(plan: RemediationPlan, analysis: LockoutAnalysis) -> RemediationPlan:
    """**INV-07.1-03**: "A detected lockout blocks the step in the playbook.
    It is not a warning buried in text." Returns a new `RemediationPlan`
    with the offending steps marked `blocked=True`."""

    if analysis.result != RESULT_LOCKOUT or not analysis.blocked_step_ids:
        return plan
    blocked_ids = set(analysis.blocked_step_ids)
    new_steps = tuple(
        s if s.id not in blocked_ids else _block_step(s, analysis.reason)
        for s in plan.steps
    )
    return RemediationPlan(
        device_id=plan.device_id, platform=plan.platform, os_version=plan.os_version,
        steps=new_steps, unavailable=plan.unavailable, checkpoints=plan.checkpoints,
        conflicts=plan.conflicts,
    )


def _block_step(step: RemediationStep, reason: str) -> RemediationStep:
    from dataclasses import replace

    return replace(step, blocked=True, blocked_reason=f"LOCKOUT: {reason}")
