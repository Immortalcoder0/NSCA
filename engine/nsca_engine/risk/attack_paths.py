"""Attack path chain computation (TRD-06.2), built on top of M3's
`graph/reachability.py` single-concrete-packet query primitive.

Scope note (flagged, not silently narrowed): TRD-06.2 §3.2 assembles chains
from controls' declared ``attack_semantics: {enables, requires}`` (a
per-control YAML field, like TRD-06.1's ``risk_modifiers``). That field does
not exist yet on `controls/evaluate.py`'s ``NativeControl`` or in
``knowledge/control_packs/*.yaml`` — extending the control-pack schema is a
knowledge-authoring change out of this milestone's scope (same reasoning as
`risk/severity.py`'s modifier-table note). This module instead carries a
small, explicit, built-in ``control_id -> enabling_category`` table
(``_ATTACK_SEMANTICS``) covering the controls actually present in
``knowledge/control_packs/nsca_native.yaml`` that plausibly chain (management
plaintext protocols, source-restriction, reversible credentials). A FAIL
finding whose control is not in this table simply never participates in a
chain — a legitimate, coarse simplification (matching DD-06.2-01's own
"categories are coarse deliberately" philosophy), not a silent narrowing.

Similarly, TRD-06.2 §3.5's breaking-link cost formula needs per-finding
remediation data (command count, impact class, prerequisites) that belongs to
TRD-07.1's remediation planner (Track B / a later milestone, not built yet).
``_COST_HINTS`` is a small, explicit, documented stand-in table for the same
reason — flagged in the M4 report.

Determinism (TRD-06.2 §3.9): pure function of
``(device_assessments, graph, exposures)``. Traversal order is explicit
(sorted device ids); tie-breaks terminate in a stable identifier; no clock,
no randomness. Cost arithmetic uses ``fractions.Fraction`` throughout (D5).
"""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping
from fractions import Fraction
from typing import TYPE_CHECKING

from nsca_engine.graph import reachability
from nsca_engine.graph.exposure import ExposureResult
from nsca_engine.types import DeviceFinding, Verdict

if TYPE_CHECKING:
    from nsca_engine.api import AttackPath, AttackPathStep, DeviceAssessment, Graph

# TRD-06.2 §3.4's ordering: network_reachability -> credential_exposure ->
# authentication_bypass -> privilege_escalation -> lateral_movement, plus the
# two categories not needed for chain ordering here but kept for completeness
# per §3.2's seven-category table.
_ENABLING_ORDER = (
    "network_reachability",
    "credential_exposure",
    "authentication_bypass",
    "privilege_escalation",
    "lateral_movement",
    "code_execution",
    "detection_evasion",
)

# control_id -> enabling category this FAIL would give an attacker, per
# TRD-06.2 §3.2's enabling-condition model. See module docstring.
_ATTACK_SEMANTICS: Mapping[str, str] = {
    "NSCA-MGMT-005": "network_reachability",  # source restriction absent
    "NSCA-MGMT-002": "credential_exposure",   # plaintext mgmt protocol (telnet)
    "NSCA-AUTH-001": "credential_exposure",   # reversible local credential
    "NSCA-SNMP-001": "credential_exposure",   # default SNMP community
    "NSCA-SNMP-003": "credential_exposure",   # SNMP write access present
}

# control_id -> (command_count, impact_class, prerequisite_count). See module
# docstring — a documented stand-in for TRD-07.1's remediation planner.
_IMPACT_WEIGHT: Mapping[str, int] = {"safe": 1, "service_affecting": 3, "lockout_risk": 6}
_COST_HINTS: Mapping[str, tuple[int, str, int]] = {
    "NSCA-MGMT-005": (1, "safe", 0),
    "NSCA-MGMT-002": (3, "lockout_risk", 0),
    "NSCA-AUTH-001": (2, "service_affecting", 0),
    "NSCA-SNMP-001": (1, "safe", 0),
    "NSCA-SNMP-003": (1, "safe", 0),
}
_DEFAULT_COST_HINT = (2, "service_affecting", 0)


def _representative_addresses(graph: Graph, device_id: str) -> tuple[str, ...]:
    """Every deterministic, host address on this device that could plausibly
    be an attack-path *target* (mirrors 04-system-architecture.md §4.5's own
    convention of using an interface's own configured host address, e.g.
    ``10.0.0.1``, rather than a synthesised one). A device typically has
    several interfaces (a transit link, a management subnet, ...) — a
    single-packet concrete query (TRD-04.2's documented simplification, see
    `graph/reachability.py`'s module docstring) can only test one at a time,
    so the caller tries each in a fixed order until one is reachable."""

    candidates = []
    for n in graph.nodes:
        if n.kind != "interface" or n.device_id != device_id:
            continue
        cidr = n.attrs.get("ip_address")
        if not cidr:
            continue
        try:
            ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            continue
        candidates.append((n.node_id, cidr.split("/")[0]))
    candidates.sort(key=lambda t: t[0])
    return tuple(addr for _, addr in candidates)


def _cost(control_id: str, alt_count: int) -> Fraction:
    """TRD-06.2 §3.5's cost formula, with unit weights (w1..w5 = 1) — the
    TRD does not specify numeric weights (flagged, same "propose a default"
    pattern as elsewhere); unit weights keep the formula's *shape* faithful
    (command count, impact, prerequisites, alternatives all contribute) while
    remaining simple and auditable."""

    cmd_count, impact_class, prereq_count = _COST_HINTS.get(control_id, _DEFAULT_COST_HINT)
    return (
        Fraction(cmd_count)
        + Fraction(_IMPACT_WEIGHT[impact_class])
        + Fraction(prereq_count)
        + Fraction(alt_count)
    )


def compute_attack_paths(
    device_assessments: tuple[DeviceAssessment, ...],
    graph: Graph,
    exposures: Mapping[str, ExposureResult],
) -> tuple[AttackPath, ...]:
    """TRD-06.2 §3.3's ``assemble(findings, graph, targets)``, specialised to
    ``targets`` = every (internet-facing source, other device) pair — the
    estate doesn't declare explicit "protected asset" targets anywhere in the
    current contract, so every non-source device is treated as a candidate
    asset, consistent with INV-06.2-01 (a path is only ever emitted when
    TRD-04.2's ``query`` actually finds a concrete reachable route — an
    unreachable candidate target silently contributes no path).

    Returns a tuple of `api.AttackPath` (local import to avoid an api.py <->
    risk/ import cycle at module load time, same pattern as
    `graph/build.py`).
    """

    from nsca_engine.api import AttackPath, AttackPathStep

    findings_by_device: dict[str, tuple[DeviceFinding, ...]] = {
        da.graph_contribution.device_id: da.findings for da in device_assessments
    }
    device_ids = sorted(findings_by_device)
    internet_facing = sorted(
        d for d in device_ids
        if exposures.get(d) is not None and exposures[d].classification == "internet_facing"
    )

    paths: list[tuple[str, str, tuple[AttackPathStep, ...], str]] = []
    seen_link_sets: set[frozenset[tuple[str, str]]] = set()  # INV: dedupe by link set (§5)

    for src_device in internet_facing:
        for dst_device in device_ids:
            if dst_device == src_device:
                continue
            result = None
            for dst_addr in _representative_addresses(graph, dst_device):
                candidate_result = reachability.query_zone(graph, "external", dst_addr, "tcp", 22)
                if candidate_result.outcome == "reachable" and candidate_result.counterexample is not None:
                    result = candidate_result
                    break
            if result is None or result.counterexample is None:
                continue  # INV-06.2-01: no path without an established reachability result

            ce = result.counterexample
            path_device_ids = {step.device_id for step in ce.chain} | {src_device, dst_device}

            candidates: list[tuple[str, DeviceFinding, str]] = []
            for dev in sorted(path_device_ids):
                for finding in sorted(findings_by_device.get(dev, ()), key=lambda f: f.control_id):
                    if finding.verdict != Verdict.FAIL:
                        continue
                    category = _ATTACK_SEMANTICS.get(finding.control_id)
                    if category is None:
                        continue
                    candidates.append((dev, finding, category))

            if not candidates:
                continue

            link_set = frozenset((dev, f.control_id) for dev, f, _ in candidates)
            if link_set in seen_link_sets:
                continue  # §5 edge case: two paths sharing all links -> deduplicated
            seen_link_sets.add(link_set)

            candidates.sort(
                key=lambda c: (_ENABLING_ORDER.index(c[2]), c[0], c[1].control_id)
            )

            steps = tuple(
                AttackPathStep(
                    device_id=dev, node_id=f"{dev}:finding:{finding.control_id}",
                    rule_id=finding.control_id,
                )
                for dev, finding, _ in candidates
            )

            costs: dict[tuple[str, str], Fraction] = {}
            for dev, finding, category in candidates:
                alt_count = sum(1 for _, _, c in candidates if c == category) - 1
                costs[(dev, finding.control_id)] = _cost(finding.control_id, alt_count)

            breaking = min(
                candidates,
                key=lambda c: (costs[(c[0], c[1].control_id)], c[0], c[1].control_id),
            )
            breaking_dev, breaking_finding, _ = breaking
            breaking_cost = costs[(breaking_dev, breaking_finding.control_id)]
            reason = (
                f"{breaking_finding.control_id} on {breaking_dev} — lowest remediation "
                f"cost ({breaking_cost}); breaking any single link breaks this chain "
                f"(DD-06.2-02: chosen by cost, not severity)."
            )

            paths.append((src_device, dst_device, steps, reason))

    # Deterministic id assignment (D6): sort by (source, target, first step)
    # before naming, so id order never depends on graph/dict iteration.
    paths.sort(key=lambda p: (p[0], p[1], tuple((s.device_id, s.rule_id) for s in p[2])))

    out: list[AttackPath] = []
    for i, (_src, _dst, steps, reason) in enumerate(paths, start=1):
        out.append(AttackPath(id=f"AP-{i:03d}", steps=steps, weakest_link_reason=reason))
    return tuple(out)
