"""Full finding state machine — 09-findings-lifecycle.md §4, backend-02 M2.

```
    NEW ──► CONFIRMED ──► ASSIGNED ──► REMEDIATED ──► VERIFIED ──► CLOSED
     │           │            ▲             │             │
     │           │            │             │ (not        │
     │           │            └─────────────┘  confirmed) │
     │           │                                        │
     ├──► DISPUTED ──► adjudicated ──┬──► CONFIRMED       │
     │                               └──► WITHDRAWN ──────┤
     │                                                    │
     └──► RISK_ACCEPTED ──► (expiry) ──► reopens ─────────┘
```

`ALLOWED_TRANSITIONS` below is a direct reproduction of that diagram, read
as: a dispute or a risk acceptance can be raised from either `New` or
`Confirmed` (the diagram's vertical bar spans both rows before branching);
remediation verification either advances to `Verified` or drops back to
`Assigned` "(not confirmed)"; risk-acceptance expiry reopens into
`Confirmed` specifically (09-findings-lifecycle.md §7: "On expiry the
finding automatically returns to `Confirmed`"), not directly to `Closed`.

Every state-changing function here writes both a `finding_transition` row
(the per-finding human-readable log) and an `audit_log` entry, in the same
transaction as the state change itself (backend-02 §2.3).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from nsca_engine.api import DeviceFinding
from sqlalchemy import select
from sqlalchemy.engine import Connection

from nsca_platform.audit import log as audit_log
from nsca_platform.db import mappers
from nsca_platform.db.models.assessment import assessment as assessment_table
from nsca_platform.db.models.campaign import campaign as campaign_table
from nsca_platform.db.models.device import device as device_table
from nsca_platform.db.models.finding import finding as finding_table
from nsca_platform.db.models.finding import finding_transition as transition_table

# 09-findings-lifecycle.md §4's states, spelled exactly as the doc's table.
STATES = frozenset(
    {"New", "Confirmed", "Disputed", "Withdrawn", "Risk Accepted", "Assigned", "Remediated", "Verified", "Closed"}
)

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "New": frozenset({"Confirmed", "Disputed", "Risk Accepted"}),
    "Confirmed": frozenset({"Assigned", "Disputed", "Risk Accepted"}),
    "Disputed": frozenset({"Confirmed", "Withdrawn"}),  # adjudication outcome
    "Withdrawn": frozenset({"Closed"}),
    "Risk Accepted": frozenset({"Confirmed"}),  # expiry auto-reopen only
    "Assigned": frozenset({"Remediated"}),
    "Remediated": frozenset({"Verified", "Assigned"}),  # verified pass / not confirmed
    "Verified": frozenset({"Closed"}),
    "Closed": frozenset(),
}


class FindingNotFound(Exception):
    pass


class IllegalTransition(Exception):
    """Raised when a requested state change is not in `ALLOWED_TRANSITIONS`
    (409 at the API layer)."""

    def __init__(self, from_state: str, to_state: str):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Cannot transition finding from {from_state!r} to {to_state!r}")


def _next_public_id(conn: Connection, campaign_public_id: str) -> str:
    # Same shape as campaign/artifact public ids: a stable prefix plus a
    # sequence number, not a random suffix — 09-findings-lifecycle.md's own
    # example ids (`F-2026Q3-000412`) are `F-<quarter>-<sequence>`.
    prefix = campaign_public_id.replace("CMP-", "F-")
    existing = conn.execute(
        select(finding_table.c.public_id).where(finding_table.c.public_id.like(f"{prefix}-%"))
    ).fetchall()
    seq = len(existing) + 1
    return f"{prefix}-{seq:06d}"


def transition(
    conn: Connection,
    finding_row_id: uuid.UUID,
    finding_public_id: str,
    from_state: str,
    to_state: str,
    actor: str,
    reason: str | None = None,
    *,
    extra_values: dict[str, Any] | None = None,
) -> None:
    """The one place a finding's `state` column is written. Validates the
    transition against `ALLOWED_TRANSITIONS`, updates the row, appends a
    `finding_transition` row, and writes the audit log — all in the
    caller's transaction (backend-02 §2.3)."""

    if to_state not in ALLOWED_TRANSITIONS.get(from_state, frozenset()):
        raise IllegalTransition(from_state, to_state)

    values = {"state": to_state, "updated_at": datetime.now(UTC)}
    if extra_values:
        values.update(extra_values)
    conn.execute(finding_table.update().where(finding_table.c.id == finding_row_id).values(**values))
    conn.execute(
        transition_table.insert().values(
            id=uuid.uuid4(),
            finding_id=finding_row_id,
            from_state=from_state,
            to_state=to_state,
            actor=actor,
            reason=reason,
        )
    )
    audit_log.record(
        conn,
        actor=actor,
        action="finding.transition",
        entity_type="finding",
        entity_id=finding_public_id,
        details={"from_state": from_state, "to_state": to_state, "reason": reason},
    )


# ---------------------------------------------------------------------------
# Creation — worker pipeline persistence (backend-02 §3 step 3)
# ---------------------------------------------------------------------------


def create_finding_from_device_finding(
    conn: Connection,
    *,
    campaign_row_id: uuid.UUID,
    campaign_public_id: str,
    device_row_id: uuid.UUID,
    device_hostname: str,
    assessment_row_id: uuid.UUID | None,
    device_finding: DeviceFinding,
    severity_effective: str | None = None,
    severity_effective_reason: str | None = None,
    framework_refs: list[dict[str, Any]] | None = None,
    attack_paths: list[str] | None = None,
    rulepack_trust_tier: str | None = None,
    actor: str = "system",
) -> dict[str, Any]:
    """Persists one `DeviceFinding` (from `assess_device`, real or fixture)
    as a `finding` row in state `New`, with its opening `finding_transition`
    (`None -> New`, actor `system`) and audit log entry.

    `identity_key` is `f"{device_hostname}:{control_id}"` — hostname rather
    than the internal device UUID, so it stays stable across a device being
    re-fingerprinted with a new row in a hypothetical future correlation
    change, matching 14-data-model.md §2's "enables cross-campaign
    tracking" intent.
    """

    public_id = _next_public_id(conn, campaign_public_id)
    identity_key = f"{device_hostname}:{device_finding.control_id}"

    row_values = mappers.device_finding_to_row(
        device_finding,
        campaign_id=campaign_row_id,
        device_id=device_row_id,
        assessment_id=assessment_row_id,
        public_id=public_id,
        identity_key=identity_key,
        severity_effective=severity_effective,
        severity_effective_reason=severity_effective_reason,
        framework_refs=framework_refs,
        attack_paths=attack_paths,
        rulepack_trust_tier=rulepack_trust_tier,
    )
    # Scope contamination (09-findings-lifecycle.md §2.2): a PASS finding
    # with a contamination_reason is reported as PASS_PARTIAL, not a bare
    # PASS — this is Track B's own post-processing of the engine's base
    # DeviceFinding.verdict (PASS/FAIL/UNKNOWN/NOT_APPLICABLE only; the
    # engine intentionally has no PASS_PARTIAL member, see its Verdict
    # docstring), applied at persistence time.
    if row_values["verdict"] == "PASS" and device_finding.contamination_reason:
        row_values["verdict"] = "PASS_PARTIAL"

    finding_row_id: uuid.UUID = row_values["id"]
    conn.execute(finding_table.insert().values(**row_values))
    conn.execute(
        transition_table.insert().values(
            id=uuid.uuid4(),
            finding_id=finding_row_id,
            from_state=None,
            to_state="New",
            actor="system",
            reason="assessment produced this finding",
        )
    )
    audit_log.record(
        conn,
        actor=actor,
        action="finding.create",
        entity_type="finding",
        entity_id=public_id,
        details={"control": device_finding.control_id, "verdict": row_values["verdict"], "device": device_hostname},
    )
    return get_finding(conn, public_id)


# ---------------------------------------------------------------------------
# Row <-> API response shape (15-api-specification.md §5)
# ---------------------------------------------------------------------------


def _row_to_response(row: Any) -> dict[str, Any]:
    return {
        "id": row.public_id,
        "control": row.control_id,
        "verdict": row.verdict,
        "severity": {
            "base": row.severity_base,
            "effective": row.severity_effective,
            "reason": row.severity_reason,
        },
        "evidence": [
            {
                "artifact": e.get("artifact"),
                "lines": e.get("lines", []),
                "highlight": e.get("highlight", []),
                "excerpt": e.get("excerpt"),
                "facts": e.get("facts", []),
            }
            for e in (row.evidence or [])
        ],
        "frameworks": row.framework_refs or [],
        "attack_paths": row.attack_paths or [],
        "rulepack_trust_tier": row.rulepack_trust_tier,
        "state": row.state,
        "owner": row.owner,
        "due_date": row.due_date.isoformat() if row.due_date else None,
    }


def _get_row(conn: Connection, finding_public_id: str) -> Any:
    row = conn.execute(select(finding_table).where(finding_table.c.public_id == finding_public_id)).first()
    if row is None:
        raise FindingNotFound(finding_public_id)
    return row


def get_finding(conn: Connection, finding_public_id: str) -> dict[str, Any]:
    return _row_to_response(_get_row(conn, finding_public_id))


def list_findings(conn: Connection, campaign_public_id: str, filters: dict[str, str] | None = None) -> dict[str, Any]:
    campaign_row = conn.execute(
        select(campaign_table.c.id).where(campaign_table.c.public_id == campaign_public_id)
    ).first()
    if campaign_row is None:
        return {"items": [], "next_cursor": None}

    query = select(finding_table).where(finding_table.c.campaign_id == campaign_row.id)
    filters = filters or {}
    column_filters = {
        "verdict": finding_table.c.verdict,
        "state": finding_table.c.state,
        "control": finding_table.c.control_id,
        "severity": finding_table.c.severity_effective,
    }
    for key, column in column_filters.items():
        if filters.get(key):
            query = query.where(column == filters[key])

    rows = conn.execute(query.order_by(finding_table.c.public_id)).fetchall()
    return {"items": [_row_to_response(r) for r in rows], "next_cursor": None}


_DEVICE_SORT_COLUMNS = {
    "compliance_asc": lambda item: item["compliance_score"],
    "coverage_asc": lambda item: item["coverage_score"],
    "hostname": lambda item: item["hostname"],
}


def device_grid(
    conn: Connection, campaign_public_id: str, *, sort: str | None = None, platform: str | None = None,
) -> dict[str, Any]:
    """Real per-device aggregation for the Estate grid (`GET
    /campaigns/{id}/findings?group_by=device`) — closes the gap the
    frontend's own `useEstateDevices.ts` documents: `list_findings` above
    has no `hostname`/`device` field on any row, so there was previously no
    way to build a real device grid from this endpoint for any campaign.

    Every field here is real, joined from `device`/`assessment`/`finding` —
    except `role` and `exposure`, which `device.py`'s own docstring already
    flags as **not a device property at all**: exposure is "derived from
    graph, per campaign" (M3+ risk/graph work), not built in this
    milestone. Rather than fabricate a plausible-looking zone, both are
    reported as `"unknown"` — the frontend renders that state honestly
    (see `estate/types.ts`) instead of a fake perimeter/core label.
    """

    campaign_row = conn.execute(
        select(campaign_table.c.id).where(campaign_table.c.public_id == campaign_public_id)
    ).first()
    if campaign_row is None:
        return {"devices": [], "total": 0}

    assessments = conn.execute(
        select(assessment_table)
        .where(assessment_table.c.campaign_id == campaign_row.id)
        .order_by(assessment_table.c.executed_at.desc())
    ).fetchall()

    # Most recent assessment per device (rows already ordered newest-first).
    latest_by_device: dict[Any, Any] = {}
    for a in assessments:
        latest_by_device.setdefault(a.device_id, a)

    device_ids = list(latest_by_device.keys())
    if not device_ids:
        return {"devices": [], "total": 0}

    devices_by_id = {
        d.id: d for d in conn.execute(select(device_table).where(device_table.c.id.in_(device_ids))).fetchall()
    }

    finding_rows = conn.execute(
        select(finding_table.c.device_id, finding_table.c.severity_effective, finding_table.c.verdict)
        .where(finding_table.c.campaign_id == campaign_row.id)
        .where(finding_table.c.device_id.in_(device_ids))
    ).fetchall()
    critical_counts: dict[Any, int] = {}
    high_counts: dict[Any, int] = {}
    for f in finding_rows:
        if f.verdict != "FAIL":
            continue
        if f.severity_effective == "critical":
            critical_counts[f.device_id] = critical_counts.get(f.device_id, 0) + 1
        elif f.severity_effective == "high":
            high_counts[f.device_id] = high_counts.get(f.device_id, 0) + 1

    items: list[dict[str, Any]] = []
    for device_id, a in latest_by_device.items():
        d = devices_by_id.get(device_id)
        if d is None:
            continue
        rulepacks_used = a.rulepacks_used or []
        primary_rulepack = rulepacks_used[0] if rulepacks_used else {}
        serials = d.serials or []
        items.append(
            {
                "id": d.hostname,
                "hostname": d.hostname,
                "platform": d.platform or primary_rulepack.get("id", "unknown"),
                "os_version": d.os_version or "unknown",
                "serial": serials[0].get("serial") if serials else None,
                "role": "unknown",
                "exposure": "unknown",
                "compliance_score": float(a.compliance_score) if a.compliance_score is not None else 0.0,
                "coverage_score": float(a.coverage_score) if a.coverage_score is not None else 0.0,
                "meaningful_ratio": float(a.meaningful_ratio) if a.meaningful_ratio is not None else None,
                "security_score": float(a.security_score) if a.security_score is not None else None,
                "critical_findings_count": critical_counts.get(device_id, 0),
                "high_findings_count": high_counts.get(device_id, 0),
                "status_annotations": [],
                "rulepack_id": primary_rulepack.get("id", "unknown"),
                "rulepack_trust_tier": primary_rulepack.get("trust_tier", "local"),
            }
        )

    if platform:
        items = [it for it in items if platform.lower() in it["platform"].lower()]

    key_fn = _DEVICE_SORT_COLUMNS.get(sort or "")
    if key_fn is not None:
        items.sort(key=key_fn)
    else:
        # Default: critical findings weighted by exposure — exposure is
        # honestly "unknown" for every device today (see docstring above),
        # so the real signal this can rank on is critical, then high,
        # finding count, not a fabricated exposure weight.
        items.sort(key=lambda it: (it["critical_findings_count"], it["high_findings_count"]), reverse=True)

    return {"devices": items, "total": len(items)}


# ---------------------------------------------------------------------------
# Simple state-changing endpoints
# ---------------------------------------------------------------------------


def confirm(conn: Connection, finding_public_id: str, actor: str) -> dict[str, Any]:
    row = _get_row(conn, finding_public_id)
    transition(conn, row.id, finding_public_id, row.state, "Confirmed", actor)
    return get_finding(conn, finding_public_id)


def assign(conn: Connection, finding_public_id: str, assignee: str, actor: str) -> dict[str, Any]:
    row = _get_row(conn, finding_public_id)
    transition(
        conn,
        row.id,
        finding_public_id,
        row.state,
        "Assigned",
        actor,
        reason=f"assigned to {assignee}",
        extra_values={"owner": assignee},
    )
    return get_finding(conn, finding_public_id)


def mark_remediated(conn: Connection, finding_public_id: str, actor: str) -> dict[str, Any]:
    row = _get_row(conn, finding_public_id)
    transition(conn, row.id, finding_public_id, row.state, "Remediated", actor)
    return get_finding(conn, finding_public_id)


def apply_verification(
    conn: Connection,
    finding_public_id: str,
    verdict_after: str,
    actor: str,
    *,
    knowledge_base_identical: bool = True,
) -> dict[str, Any]:
    """09-findings-lifecycle.md §8's three-outcome remediation verification
    table, applied to a finding currently in `Remediated`:

    | Outcome            | Action                                          |
    |---------------------|--------------------------------------------------|
    | now PASS            | -> Verified -> Closed, new evidence attached     |
    | still FAIL          | -> Assigned, with a note and the new evidence    |
    | now UNKNOWN         | -> Assigned, with a coverage warning             |

    `knowledge_base_identical` must be true for the comparison to be valid
    (§8: "The knowledge base must be identical between assessment and
    verification") — the caller (the fixture-then-real worker) is
    responsible for establishing that; a caller that cannot guarantee it
    should not call this with a real verdict at all.
    """

    row = _get_row(conn, finding_public_id)
    if row.state != "Remediated":
        raise IllegalTransition(row.state, "Verified")

    if not knowledge_base_identical:
        reason = "knowledge base changed since assessment — comparison invalid, cannot verify"
        transition(conn, row.id, finding_public_id, row.state, "Assigned", actor, reason=reason)
        return get_finding(conn, finding_public_id)

    if verdict_after == "PASS":
        transition(
            conn, row.id, finding_public_id, row.state, "Verified", actor, reason="re-assessment confirmed PASS"
        )
        row2 = _get_row(conn, finding_public_id)
        transition(conn, row2.id, finding_public_id, "Verified", "Closed", actor, reason="verified fix retained")
        return get_finding(conn, finding_public_id)

    if verdict_after == "UNKNOWN":
        reason = "re-assessment produced UNKNOWN — a fix must not be accepted on the basis of a device becoming unreadable"
        transition(conn, row.id, finding_public_id, row.state, "Assigned", actor, reason=reason)
        return get_finding(conn, finding_public_id)

    # still FAIL
    transition(conn, row.id, finding_public_id, row.state, "Assigned", actor, reason="re-assessment still FAIL")
    return get_finding(conn, finding_public_id)


def history(conn: Connection, finding_public_id: str) -> dict[str, Any]:
    row = _get_row(conn, finding_public_id)
    rows = conn.execute(
        select(transition_table).where(transition_table.c.finding_id == row.id).order_by(transition_table.c.at)
    ).fetchall()
    return {
        "finding_id": finding_public_id,
        "transitions": [
            {
                "state": t.to_state,
                "actor": t.actor,
                "at": t.at.isoformat(),
                "reason": t.reason,
            }
            for t in rows
        ],
    }


def bulk_transition(conn: Connection, finding_public_ids: list[str], action: str, actor: str) -> dict[str, Any]:
    action_map = {
        "confirm": confirm,
        "mark-remediated": mark_remediated,
    }
    fn = action_map.get(action)
    updated = 0
    if fn is not None:
        for fid in finding_public_ids:
            try:
                fn(conn, fid, actor)
                updated += 1
            except (FindingNotFound, IllegalTransition):
                continue
    return {"updated": updated, "action": action}
