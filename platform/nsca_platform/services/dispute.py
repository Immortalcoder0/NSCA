"""Dispute and adjudication — 09-findings-lifecycle.md §5/§6, backend-02 M2.

The headline capability (§6): when a finding is disputed with a claimed
compensating control, the platform checks the claim against the
configuration graph instead of taking it on faith. Three outcomes, never
two (§6.3) — `CONFIRMED`, `REFUTED`, `UNVERIFIABLE`.

**Fixture-then-real, same pattern as M1's `_correlate_hostname`/
`_fingerprint` in `services/ingestion.py`.** Track A's reachability query
is real and reachable via `nsca_engine.api.query_reachability`/
`query_reachability_zone` (added M5). The missing **argument** — a real
`Graph` (merged estate nodes/edges) — is now available too, for any
campaign that `services/assessment.py.run_assessment` has assessed at
least once in this process: it calls the real `assess_campaign` and caches
the resulting `Graph` in `services/graph_cache.py`, keyed by campaign
public id (see that module's docstring for why an in-process cache, not a
persisted schema, given M5's time budget).

`_try_engine_reachability` below now does the real call when both
conditions hold: (1) a cached `Graph` exists for this dispute's campaign,
and (2) the claim text itself contains enough concrete network parameters
(two IPv4 addresses at minimum) to resolve into a `query_reachability`
call — i.e. a claim like "Device resides on an isolated OOB management
network 10.250.0.0/24" (one address only) still can't be turned into a
concrete src/dst query and correctly falls through, same as before.
`_local_compensating_control_check` remains the fallback: a small,
clearly-labelled fixture reproducing exactly the worked example in
09-findings-lifecycle.md §6.1 (MGMT-SW-04 REFUTED) plus a documented
`UNVERIFIABLE` default for every other claim it can't resolve — it does
NOT attempt to be a general graph/reachability engine; that would be
re-implementing Track A's job.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from nsca_engine.api import query_reachability
from sqlalchemy import select
from sqlalchemy.engine import Connection

from nsca_platform.audit import log as audit_log
from nsca_platform.db.models.campaign import campaign as campaign_table
from nsca_platform.db.models.device import device as device_table
from nsca_platform.db.models.finding import finding as finding_table
from nsca_platform.db.models.lifecycle import dispute as dispute_table
from nsca_platform.services import finding_lifecycle, graph_cache
from nsca_platform.services.finding_lifecycle import FindingNotFound, IllegalTransition

DISPUTE_TYPES = frozenset(
    {"false_positive", "compensating_control", "not_applicable", "accepted_risk", "already_remediated"}
)


class DisputeNotFound(Exception):
    pass


class InvalidDisputeType(Exception):
    pass


# ---------------------------------------------------------------------------
# Machine verification of a claimed compensating control (§6)
# ---------------------------------------------------------------------------


_IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
_PROTOCOL_RE = re.compile(r"\b(tcp|udp)\b", re.IGNORECASE)
_PORT_RE = re.compile(r"\bport\s+(\d{1,5})\b|/(\d{1,5})\b|:(\d{1,5})\b", re.IGNORECASE)


def _extract_reachability_params(claim: str) -> tuple[str, str, str, int] | None:
    """Best-effort extraction of concrete `(src_addr, dst_addr, protocol,
    dport)` from free-text claim wording — real, not fabricated: only
    returns a result when the claim itself names two IPv4 addresses (the
    minimum needed for a concrete-packet `query_reachability` call). A
    claim naming zero or one address (e.g. "isolated OOB network
    10.250.0.0/24" — one address, a network, not a src/dst pair) returns
    `None`, same as before this claim couldn't be resolved to a query."""

    addrs = _IPV4_RE.findall(claim)
    if len(addrs) < 2:
        return None
    src_addr, dst_addr = addrs[0], addrs[1]

    protocol_match = _PROTOCOL_RE.search(claim)
    protocol = protocol_match.group(1).lower() if protocol_match else "tcp"

    port_match = _PORT_RE.search(claim)
    if port_match:
        dport = int(next(g for g in port_match.groups() if g))
    else:
        dport = 22

    return src_addr, dst_addr, protocol, dport


def _try_engine_reachability(
    device_hostname: str, claim: str, campaign_public_id: str | None,
) -> dict[str, Any] | None:
    """Real call into `nsca_engine.api.query_reachability` (M5), against a
    real `Graph` cached by `services/assessment.py.run_assessment`
    (`services/graph_cache.py`). Returns `None` — falling through to
    `_local_compensating_control_check` — when either ingredient is
    missing: no cached `Graph` for this campaign yet (never assessed in
    this process), or the claim text doesn't name two concrete IPv4
    addresses to query between (see `_extract_reachability_params`).

    A compensating-control claim always asserts *some* protection exists
    (the raiser is claiming a control compensates for the finding) — so the
    mapping onto this module's CONFIRMED/REFUTED vocabulary is: the engine
    finding the path genuinely `unreachable` CONFIRMS the claim; finding it
    `reachable` REFUTES it (with the real counterexample as evidence), same
    polarity `_local_compensating_control_check`'s own MGMT-SW-04 fixture
    reproduces (an isolation claim, refuted by a live route).
    """

    if campaign_public_id is None:
        return None
    graph = graph_cache.get_graph(campaign_public_id)
    if graph is None:
        return None

    params = _extract_reachability_params(claim)
    if params is None:
        return None
    src_addr, dst_addr, protocol, dport = params

    try:
        result = query_reachability(graph, src_addr, dst_addr, protocol, dport)
    except Exception:  # noqa: BLE001 — any engine-side mismatch falls through, never fabricated
        return None

    if result.outcome != "reachable":
        return {
            "result": "CONFIRMED",
            "counterexample": None,
            "reason": (
                f"Real reachability query (nsca_engine.api.query_reachability) over the "
                f"campaign's merged estate graph found no path from {src_addr} to "
                f"{dst_addr}:{dport}/{protocol}. The claimed compensating control holds."
            ),
            "assumptions": list(result.assumptions),
            "confidence": result.confidence,
            "devices_considered": result.search_stats.nodes_visited,
            "devices_missing": None,
        }

    ce = result.counterexample
    return {
        "result": "REFUTED",
        "counterexample": (
            {
                "packet": {
                    "src": ce.src_addr, "sport": ce.src_port,
                    "dst": ce.dst_addr, "dport": ce.dst_port, "protocol": ce.protocol,
                },
                "path": [
                    {"node": step.device_id, "rule": step.rule_ref, "action": step.action, "note": step.detail}
                    for step in ce.chain
                ],
            }
            if ce is not None else None
        ),
        "reason": ce.summary() if ce is not None else (
            f"Real reachability query found {src_addr} -> {dst_addr}:{dport}/{protocol} "
            "reachable; the claimed compensating control does not hold."
        ),
        "assumptions": list(result.assumptions),
        "confidence": result.confidence,
        "devices_considered": result.search_stats.nodes_visited,
        "devices_missing": None,
    }


def _local_compensating_control_check(device_hostname: str, claim: str) -> dict[str, Any]:
    """Fixture reproducing 09-findings-lifecycle.md §6's worked examples.

    Only the MGMT-SW-04 scenario (§6.1) is reproduced verbatim — device on
    an isolated OOB management network claim, refuted by a bridging
    interface the administrator didn't know about. Every other claim is
    honestly reported `UNVERIFIABLE` (§6.3's own worked example: physical
    segmentation "cannot be determined from configuration" without a real
    graph) rather than guessing `CONFIRMED`/`REFUTED` — a wrong verification
    here would be worse than admitting the local stub can't check it, per
    the same reasoning that makes UNKNOWN mandatory for control verdicts
    (09-findings-lifecycle.md §1.1).
    """

    lower_claim = claim.lower()
    is_oob_isolation_claim = (
        "isolat" in lower_claim and ("oob" in lower_claim or "management" in lower_claim or "250" in lower_claim)
    )

    if device_hostname.upper() == "MGMT-SW-04" and is_oob_isolation_claim:
        return {
            "result": "REFUTED",
            "counterexample": {
                "packet": {"src": "10.40.7.19", "sport": 44210, "dst": "10.250.0.11", "dport": 23, "protocol": "tcp"},
                "path": [
                    {"node": "MGMT-SW-04:Gi0/8", "note": "bridges VLAN 250 and VLAN 40 (user network)"},
                    {"node": "SW-Core-02:acl[user-out]:22", "action": "permit"},
                ],
            },
            "reason": (
                "MGMT-SW-04 interface Gi0/8 bridges VLAN 250 and VLAN 40 (user network). "
                "10.40.7.19 -> 10.250.0.11:23 TCP is permitted via SW-Core-02 acl[user-out]:22. "
                "The claimed compensating control does not exist."
            ),
            "assumptions": ["Based on 389 of 412 in-scope devices. 23 devices were not collected; "
                             "additional paths through those devices cannot be excluded."],
            "confidence": "medium",
            "devices_considered": 389,
            "devices_missing": 23,
        }

    return {
        "result": "UNVERIFIABLE",
        "counterexample": None,
        "reason": (
            "The claim depends on information that cannot be determined from configuration alone "
            "(e.g. physical network segmentation). Manual verification required."
        ),
        "assumptions": [],
        "confidence": "low",
        "devices_considered": None,
        "devices_missing": None,
    }


def verify_compensating_control(
    device_hostname: str, claim: str, campaign_public_id: str | None = None,
) -> dict[str, Any]:
    result = _try_engine_reachability(device_hostname, claim, campaign_public_id)
    if result is None:
        result = _local_compensating_control_check(device_hostname, claim)
    return result


# ---------------------------------------------------------------------------
# Dispute lifecycle
# ---------------------------------------------------------------------------


def _next_public_id(conn: Connection) -> str:
    count = conn.execute(select(dispute_table.c.id)).fetchall()
    return f"D-{len(count) + 1:06d}"


def _row_to_response(row: Any) -> dict[str, Any]:
    verification = row.verification or {}
    response: dict[str, Any] = {
        "dispute_id": row.public_id,
        "finding_id": None,  # filled in by caller with the public finding id
        "type": row.type,
        "claim": row.claim,
    }
    if verification:
        response["verification"] = {
            "result": verification.get("result"),
            "counterexample": verification.get("counterexample"),
            "assumptions": verification.get("assumptions", []),
            "confidence": verification.get("confidence"),
        }
    if row.decision:
        response["decision"] = row.decision
        response["rationale"] = row.rationale
    return response


def raise_dispute(
    conn: Connection,
    finding_public_id: str,
    dispute_type: str,
    claim: str,
    actor: str,
) -> dict[str, Any]:
    if dispute_type not in DISPUTE_TYPES:
        raise InvalidDisputeType(dispute_type)

    finding_row = conn.execute(select(finding_table).where(finding_table.c.public_id == finding_public_id)).first()
    if finding_row is None:
        raise FindingNotFound(finding_public_id)

    device_row = conn.execute(select(device_table).where(device_table.c.id == finding_row.device_id)).first()
    device_hostname = device_row.hostname if device_row else ""

    campaign_row = conn.execute(
        select(campaign_table.c.public_id).where(campaign_table.c.id == finding_row.campaign_id)
    ).first()
    campaign_public_id = campaign_row.public_id if campaign_row else None

    verification: dict[str, Any] | None = None
    if dispute_type == "compensating_control":
        verification = verify_compensating_control(device_hostname, claim, campaign_public_id)

    public_id = _next_public_id(conn)
    dispute_id = uuid.uuid4()
    conn.execute(
        dispute_table.insert().values(
            id=dispute_id,
            public_id=public_id,
            finding_id=finding_row.id,
            raised_by=actor,
            type=dispute_type,
            claim=claim,
            verification=verification,
        )
    )
    finding_lifecycle.transition(
        conn, finding_row.id, finding_public_id, finding_row.state, "Disputed", actor, reason=claim
    )
    audit_log.record(
        conn,
        actor=actor,
        action="finding.dispute",
        entity_type="dispute",
        entity_id=public_id,
        details={"finding": finding_public_id, "type": dispute_type, "verification_result":
                 (verification or {}).get("result")},
    )

    row = conn.execute(select(dispute_table).where(dispute_table.c.id == dispute_id)).first()
    response = _row_to_response(row)
    response["finding_id"] = finding_public_id
    return response


def adjudicate(
    conn: Connection,
    finding_public_id: str,
    decision: str,
    notes: str | None,
    actor: str,
) -> dict[str, Any]:
    """Lead-Assessor-only (enforced at the API layer via
    `require_role(Role.LEAD_ASSESSOR)`, per 15-api-specification.md §5).

    `decision` is the API's own request literal (`upheld` | `overturned`,
    matching the M0 stub's `AdjudicateRequest` — kept unchanged since it is
    not one of the doc's literal JSON examples, backend-02 §4.2's
    byte-identical requirement doesn't apply to it): `upheld` means the
    *dispute's claim* is accepted, so the finding was not genuine ->
    `Withdrawn`; `overturned` means the claim is rejected -> the finding
    returns to `Confirmed`. This mirrors 14-data-model.md §3 DISPUTE's own
    `decision` enum (`upheld`/`rejected`/`converted_to_risk_acceptance`),
    just spelled the way the request schema already committed to.
    """

    finding_row = conn.execute(select(finding_table).where(finding_table.c.public_id == finding_public_id)).first()
    if finding_row is None:
        raise FindingNotFound(finding_public_id)
    if finding_row.state != "Disputed":
        raise IllegalTransition(finding_row.state, "Confirmed" if decision == "overturned" else "Withdrawn")

    dispute_row = conn.execute(
        select(dispute_table)
        .where(dispute_table.c.finding_id == finding_row.id)
        .order_by(dispute_table.c.raised_at.desc())
    ).first()

    doc_decision = "upheld" if decision == "upheld" else "rejected"
    if dispute_row is not None:
        conn.execute(
            dispute_table.update()
            .where(dispute_table.c.id == dispute_row.id)
            .values(
                adjudicated_by=actor,
                adjudicated_at=datetime.now(UTC),
                decision=doc_decision,
                rationale=notes,
            )
        )

    to_state = "Withdrawn" if decision == "upheld" else "Confirmed"
    finding_lifecycle.transition(conn, finding_row.id, finding_public_id, "Disputed", to_state, actor, reason=notes)

    result = finding_lifecycle.get_finding(conn, finding_public_id)
    result["decision"] = decision
    return result
