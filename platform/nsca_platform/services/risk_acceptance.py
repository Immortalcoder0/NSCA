"""Risk acceptance — 09-findings-lifecycle.md §7, backend-02 M2.

Rules (§7), enforced here plus at the request-schema layer
(`api/findings.py`'s `RiskAcceptanceRequest`):

- Expiry is mandatory — no indefinite acceptance.
- Only a Lead Assessor may accept risk (enforced at the API layer via
  `require_role(Role.LEAD_ASSESSOR)`, same as `campaign.issue`/`adjudicate`).
- On expiry the finding automatically returns to `Confirmed`.

`auto_reopen_expired` is the function a scheduler will call once one
exists. **No scheduler is wired up in this milestone** — backend-02's
module layout reserves `platform/nsca_platform/jobs/` for the Postgres
`SKIP LOCKED` queue (§4.1), and that package does not exist yet as of M2
(only `api/`, `services/`, `db/`, `audit/`, `auth/`, `tests/` do). Per the
M2 task brief: "you don't need a real job-queue scheduler wired to run it
automatically this milestone, just the function + a test proving it works
when called." See the TODO at the bottom of this module for the follow-up.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from nsca_platform.audit import log as audit_log
from nsca_platform.db.models.finding import finding as finding_table
from nsca_platform.db.models.lifecycle import risk_acceptance as risk_acceptance_table
from nsca_platform.services import dispute as dispute_service
from nsca_platform.services import finding_lifecycle
from nsca_platform.services.finding_lifecycle import FindingNotFound, IllegalTransition


def _next_public_id(conn: Connection) -> str:
    count = conn.execute(select(risk_acceptance_table.c.id)).fetchall()
    return f"RA-{len(count) + 1:06d}"


def accept_risk(
    conn: Connection,
    finding_public_id: str,
    expires_at: datetime,
    justification: str,
    compensating_control: dict[str, Any] | None,
    actor: str,
) -> dict[str, Any]:
    finding_row = conn.execute(select(finding_table).where(finding_table.c.public_id == finding_public_id)).first()
    if finding_row is None:
        raise FindingNotFound(finding_public_id)
    if finding_row.state not in finding_lifecycle.ALLOWED_TRANSITIONS or "Risk Accepted" not in (
        finding_lifecycle.ALLOWED_TRANSITIONS.get(finding_row.state, frozenset())
    ):
        raise IllegalTransition(finding_row.state, "Risk Accepted")

    stored_control = dict(compensating_control) if compensating_control else None
    if stored_control and stored_control.get("claim"):
        # Same machine-verification path a dispute uses (§6) — a risk
        # acceptance's claimed compensating control gets the same scrutiny
        # as a disputed one, per §7's `compensating_control: { claim,
        # verification, verified_at }` shape. M5: also threads through the
        # campaign public id, same as services/dispute.py.raise_dispute,
        # so this call site benefits from the real query_reachability path
        # too when a Graph has been cached for this campaign.
        from nsca_platform.db.models.campaign import campaign as campaign_table
        from nsca_platform.db.models.device import device as device_table

        device_hostname_row = conn.execute(
            select(device_table.c.hostname).where(device_table.c.id == finding_row.device_id)
        ).first()
        hostname = device_hostname_row.hostname if device_hostname_row else ""
        campaign_row = conn.execute(
            select(campaign_table.c.public_id).where(campaign_table.c.id == finding_row.campaign_id)
        ).first()
        campaign_public_id = campaign_row.public_id if campaign_row else None
        verification = dispute_service.verify_compensating_control(
            hostname, stored_control["claim"], campaign_public_id,
        )
        stored_control["verification"] = verification.get("result")
        stored_control["verified_at"] = datetime.now(UTC).isoformat()

    public_id = _next_public_id(conn)
    ra_id = uuid.uuid4()
    conn.execute(
        risk_acceptance_table.insert().values(
            id=ra_id,
            public_id=public_id,
            finding_id=finding_row.id,
            accepted_by=actor,
            expires_at=expires_at,
            justification=justification,
            compensating_control=stored_control,
        )
    )
    finding_lifecycle.transition(
        conn,
        finding_row.id,
        finding_public_id,
        finding_row.state,
        "Risk Accepted",
        actor,
        reason=justification,
    )
    audit_log.record(
        conn,
        actor=actor,
        action="risk_acceptance.create",
        entity_type="risk_acceptance",
        entity_id=public_id,
        details={"finding": finding_public_id, "expires_at": expires_at.isoformat()},
    )

    result = finding_lifecycle.get_finding(conn, finding_public_id)
    result["risk_acceptance"] = {
        "id": public_id,
        "expires_at": expires_at.date().isoformat() if hasattr(expires_at, "date") else expires_at.isoformat(),
        "justification": justification,
        "compensating_control": stored_control,
        "accepted_by": actor,
    }
    return result


def auto_reopen_expired(conn: Connection, now: datetime, actor: str = "system") -> list[str]:
    """Finds every `risk_acceptance` row whose `expires_at` is in the past
    relative to `now`, not yet `auto_reopened_at`, whose finding is still
    in `Risk Accepted` — and reopens it (-> `Confirmed`, §7). Returns the
    public ids of every finding reopened, for the caller (a test today; a
    scheduler once `jobs/` exists) to report on.

    Idempotent: a row already marked `auto_reopened_at` is skipped, so
    calling this repeatedly (e.g. once per scheduler tick) never
    double-transitions a finding that was already reopened.
    """

    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    rows = conn.execute(
        select(risk_acceptance_table, finding_table.c.public_id.label("finding_public_id"), finding_table.c.state)
        .join(finding_table, finding_table.c.id == risk_acceptance_table.c.finding_id)
        .where(risk_acceptance_table.c.expires_at < now)
        .where(risk_acceptance_table.c.auto_reopened_at.is_(None))
        .where(finding_table.c.state == "Risk Accepted")
    ).fetchall()

    reopened: list[str] = []
    for row in rows:
        conn.execute(
            risk_acceptance_table.update()
            .where(risk_acceptance_table.c.id == row.id)
            .values(auto_reopened_at=now)
        )
        finding_lifecycle.transition(
            conn,
            row.finding_id,
            row.finding_public_id,
            "Risk Accepted",
            "Confirmed",
            actor,
            reason="risk acceptance expired — automatically reopened",
        )
        audit_log.record(
            conn,
            actor=actor,
            action="risk_acceptance.auto_reopen",
            entity_type="risk_acceptance",
            entity_id=row.public_id,
            details={"finding": row.finding_public_id, "expired_at": row.expires_at.isoformat()},
        )
        reopened.append(row.finding_public_id)
    return reopened


# TODO(M5 or whenever `platform/nsca_platform/jobs/` lands): register
# `auto_reopen_expired` as a recurring job on the Postgres `SKIP LOCKED`
# queue (backend-02 §4.1's job-queue design), called once per day with
# `now=datetime.now(timezone.utc)`. Nothing about this function's contract
# needs to change for that — it already takes `now` as a parameter rather
# than reading the clock internally, so the scheduler owns determinism of
# *when* it runs and this module stays a pure "given now, do the reopen"
# operation.
