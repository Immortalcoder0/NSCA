"""Remediation service — wires `remediation/{planner,lockout,dry_run}.py`
(real, TRD-07.1, backend-02 §4.4 — M4) into live, DB-backed data.

**Phase 3 demo rehearsal fix (findings 7/8 in `nsca/plans/
phase3-demo-rehearsal.md`'s "Summary of genuinely new findings", both
really the same underlying gap):**

1. `GET /findings/{id}/remediation` (`api/findings.py`) returned a fixed,
   byte-identical stub (`"disable telnet"` / `"enable ssh v2 only"`,
   `lockout_risk: false`) for every finding regardless of control. The real
   planner/lockout/dry-run modules were never invoked from any live route.
2. The per-device report's "Remediation Playbook" section always read "No
   remediation plan has been generated for this device" because nothing
   ever `INSERT`ed into the `remediation_plan` table
   (`db/models/lifecycle.py`) from a live code path —
   `services/report_service.py`'s `gather_device_report_data` `SELECT`
   against that table always found nothing.

This module is the "one place this shape is defined" that `db/models/
lifecycle.py`'s own `remediation_plan` table docstring already points to
(a forward reference written before this module existed). It:

- Computes a real `remediation.planner.RemediationPlan` (+ lockout + dry
  run) for a device from its real, stored FAIL findings, real device
  platform/os_version, and real per-assessment facts (the `fact` table,
  `value jsonb NULL = unknown`) — never fabricated.
- Serialises that computation into the exact JSON shape
  `reporting/document_model.py`'s `RemediationPlanView` (+ its block
  dataclasses) already expects on read — `services/report_service.py
  ._remediation_plan_view` does `dm.PlaybookStepBlock(**s)` etc. directly
  against the stored JSONB, so the stored shape *is* the view shape, not
  the raw `remediation.planner` dataclass shape (which carries extra
  fields like `depends_on`/`fact_effects` the view never needed).
- Is called from two places: `services/assessment.py.run_assessment`
  (persists one `remediation_plan` row per device per run, covering every
  FAIL finding just created — what report generation reads) and
  `api/findings.py`'s `/findings/{id}/remediation` route (computed
  on-demand per finding, sliced from the same whole-device plan, since
  dependency chains span controls).

**Known, honest limitation carried over from `remediation/lockout.py`'s own
docstring:** no call site here has a `device_management_addr` fact to
supply (no such fact path exists in the current schema), so the real
`nsca_engine.api.query_reachability` engine path never fires from this
module either — every lockout check here falls through to
`_local_approximate_check`, the documented, honestly-labelled
device-local-ACL approximation. `operator_source` is also not available at
assessment time (no caller-IP concept in a background worker), so the
assessment-time plan's lockout result is `INDETERMINATE` by design
(DD-07.1-02: "silence must not read as safety") unless a caller of
`get_finding_remediation` supplies one explicitly.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from nsca_platform.db.models.assessment import assessment as assessment_table
from nsca_platform.db.models.assessment import fact as fact_table
from nsca_platform.db.models.campaign import campaign as campaign_table
from nsca_platform.db.models.device import device as device_table
from nsca_platform.db.models.finding import finding as finding_table
from nsca_platform.db.models.lifecycle import remediation_plan as remediation_plan_table
from nsca_platform.remediation import dry_run as dryrun_mod
from nsca_platform.remediation import lockout as lockout_mod
from nsca_platform.remediation import planner as planner_mod
from nsca_platform.reporting.document_model import RemediationPlanView, remediation_plan_to_view
from nsca_platform.services import finding_lifecycle


class CampaignNotFound(Exception):
    pass


class DeviceNotFound(Exception):
    pass


# ---------------------------------------------------------------------------
# Shared computation — findings + facts (from the DB) -> real
# RemediationPlan / LockoutAnalysis / DryRunResult
# ---------------------------------------------------------------------------


def _compute(
    *,
    findings: list[dict[str, Any]],
    device_hostname: str,
    platform: str | None,
    os_version: str | None,
    facts: Mapping[str, Any],
    campaign_public_id: str | None,
    operator_source: str | None,
) -> tuple[planner_mod.RemediationPlan, lockout_mod.LockoutAnalysis, dryrun_mod.DryRunResult]:
    library = planner_mod.load_remediation_library()
    plan = planner_mod.plan(
        findings,
        device_id=device_hostname,
        platform=platform or "unknown",
        os_version=os_version,
        facts=facts,
        library=library,
        operator_source=operator_source,
    )
    modelled = dryrun_mod.apply_remediation_to_facts(facts, plan)
    # `device_management_addr` is intentionally omitted — see module
    # docstring's "Known, honest limitation": no call site in this
    # milestone has that fact to supply, so this always falls through to
    # the local approximation. Never fabricated.
    lock = lockout_mod.check_lockout(
        plan, modelled, operator_source, campaign_public_id=campaign_public_id, device_management_addr=None
    )
    plan = lockout_mod.apply_lockout_blocking(plan, lock)
    dr = dryrun_mod.dry_run(findings, facts, plan, library=library)
    return plan, lock, dr


def _facts_for_latest_assessment(conn: Connection, campaign_row_id: Any, device_row_id: Any) -> dict[str, Any]:
    assessment_row = conn.execute(
        select(assessment_table)
        .where(assessment_table.c.campaign_id == campaign_row_id, assessment_table.c.device_id == device_row_id)
        .order_by(assessment_table.c.created_at.desc())
    ).first()
    if assessment_row is None:
        return {}
    fact_rows = conn.execute(select(fact_table).where(fact_table.c.assessment_id == assessment_row.id)).fetchall()
    return {r.path: r.value for r in fact_rows}


# ---------------------------------------------------------------------------
# View -> JSONB row values (the shape `report_service._remediation_plan_view`
# reads back) — see module docstring
# ---------------------------------------------------------------------------


def _view_to_row_values(view: RemediationPlanView, conflicts: tuple[Any, ...]) -> dict[str, Any]:
    steps = [asdict(s) for s in view.steps]
    checkpoints = [asdict(c) for c in view.checkpoints]
    unavailable = [{"control_id": control_id, "reason": reason} for control_id, reason in view.unavailable]
    lockout = asdict(view.lockout) if view.lockout is not None else None
    dry_run = None
    if view.dry_run is not None:
        dry_run = asdict(view.dry_run)
        # JSON has no tuple type — round-trips as lists either way, but
        # write plain lists so a pre-round-trip read (nothing does this
        # today, but a future direct consumer might) doesn't see tuples.
        dry_run["resolved"] = list(dry_run["resolved"])
        dry_run["newly_failing"] = [list(x) for x in dry_run["newly_failing"]]
    conflict_dicts = [asdict(c) for c in conflicts]
    return {
        "steps": steps,
        "checkpoints": checkpoints,
        "unavailable": unavailable,
        "conflicts": conflict_dicts,
        "lockout": lockout,
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# Persistence — called from services/assessment.py.run_assessment
# ---------------------------------------------------------------------------


def persist_plan_for_device(
    conn: Connection,
    *,
    campaign_row: Any,
    device_row: Any,
    findings: list[dict[str, Any]],
    facts: Mapping[str, Any],
    platform: str | None = None,
    os_version: str | None = None,
    operator_source: str | None = None,
    actor: str,
) -> str | None:
    """Computes and persists one `remediation_plan` row covering every FAIL
    finding in `findings` for this device, using `platform`/`os_version`
    when given (the *this-run* fingerprint — preferred, since it is never
    stale) or falling back to the `device` row's own columns (only ever
    populated by a real artifact upload, `services/ingestion.py`).

    Returns the new plan's public id, or `None` when there is nothing to
    remediate (no FAIL finding at all) — no empty row is written for a
    fully-compliant device; `report_service._remediation_plan_view`
    already renders "no remediation plan" correctly for that case, which
    is the semantically correct thing to show.
    """

    fail_findings = [f for f in findings if f.get("verdict") == "FAIL"]
    if not fail_findings:
        return None

    resolved_platform = platform or device_row.platform
    resolved_os_version = os_version if os_version is not None else device_row.os_version

    plan, lock, dr = _compute(
        findings=findings,
        device_hostname=device_row.hostname,
        platform=resolved_platform,
        os_version=resolved_os_version,
        facts=facts,
        campaign_public_id=campaign_row.public_id,
        operator_source=operator_source,
    )
    view = remediation_plan_to_view(plan, lock, dr)
    row_values = _view_to_row_values(view, plan.conflicts)

    plan_uuid = uuid.uuid4()
    public_id = f"RPL-{uuid.uuid4().hex[:10].upper()}"
    conn.execute(
        remediation_plan_table.insert().values(
            id=plan_uuid,
            public_id=public_id,
            campaign_id=campaign_row.id,
            device_id=device_row.id,
            platform=resolved_platform or "unknown",
            os_version=resolved_os_version,
            operator_source=operator_source,
            generated_by=actor,
            **row_values,
        )
    )
    return public_id


# ---------------------------------------------------------------------------
# On-demand, per-finding slice — called from api/findings.py
# ---------------------------------------------------------------------------

_DRY_RUN_RESULT_LABEL = {
    lockout_mod.RESULT_PERMITTED: "no_lockout_detected",
    lockout_mod.RESULT_LOCKOUT: "lockout_detected",
    lockout_mod.RESULT_INDETERMINATE: "indeterminate",
}


def get_finding_remediation(
    conn: Connection, finding_public_id: str, *, operator_source: str | None = None
) -> dict[str, Any]:
    """`GET /findings/{id}/remediation`'s real implementation. Builds the
    whole device's plan (dependency chains span controls — a single
    finding's steps can depend on another control's steps via
    `after_control`) using every FAIL finding currently on the device, then
    returns the slice addressing this specific finding.
    """

    finding_row = conn.execute(select(finding_table).where(finding_table.c.public_id == finding_public_id)).first()
    if finding_row is None:
        raise finding_lifecycle.FindingNotFound(finding_public_id)

    campaign_row = conn.execute(select(campaign_table).where(campaign_table.c.id == finding_row.campaign_id)).first()
    device_row = conn.execute(select(device_table).where(device_table.c.id == finding_row.device_id)).first()

    control_id = finding_row.control_id

    if finding_row.verdict != "FAIL":
        # V-07.1-010: only FAIL findings receive remediation ("you cannot
        # fix what you could not determine") — an honest, differentiated
        # response for this class of finding, not the byte-identical stub
        # every finding used to get regardless of verdict.
        return {
            "finding_id": finding_public_id,
            "control_id": control_id,
            "verdict": finding_row.verdict,
            "plan": {"steps": [], "unavailable": []},
            "dry_run": {"result": "not_applicable", "confidence": "n/a"},
            "lockout_risk": False,
            "note": (
                f"Remediation only applies to FAIL findings (TRD-07.1 §4, V-07.1-010) — "
                f"this finding's verdict is {finding_row.verdict!r}."
            ),
        }

    all_finding_rows = conn.execute(
        select(finding_table).where(
            finding_table.c.campaign_id == finding_row.campaign_id,
            finding_table.c.device_id == finding_row.device_id,
        )
    ).fetchall()
    findings = [{"id": r.public_id, "control": r.control_id, "verdict": r.verdict} for r in all_finding_rows]

    facts = _facts_for_latest_assessment(conn, finding_row.campaign_id, finding_row.device_id)

    plan, lock, dr = _compute(
        findings=findings,
        device_hostname=device_row.hostname if device_row is not None else finding_public_id,
        platform=device_row.platform if device_row is not None else None,
        os_version=device_row.os_version if device_row is not None else None,
        facts=facts,
        campaign_public_id=campaign_row.public_id if campaign_row is not None else None,
        operator_source=operator_source,
    )

    steps = [s for s in plan.steps if s.control_id == control_id]
    unavailable = [u for u in plan.unavailable if u.control_id == control_id and u.finding_id == finding_public_id]
    if not unavailable:
        # Chain-propagation entries (planner.py's "whole chain unavailable"
        # fixed point) are recorded per finding_id already; this is only a
        # fallback for the direct, non-chained refusal case.
        unavailable = [u for u in plan.unavailable if u.control_id == control_id]

    lockout_risk = bool(steps) and (
        any(s.impact == "lockout_risk" or s.blocked for s in steps) or lock.result == lockout_mod.RESULT_LOCKOUT
    )

    return {
        "finding_id": finding_public_id,
        "control_id": control_id,
        "verdict": finding_row.verdict,
        "plan": {
            "steps": [
                {
                    "order": s.id,
                    "action": s.command,
                    "impact": s.impact,
                    "lockout_risk": s.impact == "lockout_risk",
                    "reason": s.reason,
                    "rollback": s.rollback,
                    "rollback_incomplete": s.rollback_incomplete,
                    "requires_verified": s.requires_verified,
                    "blocked": s.blocked,
                    "blocked_reason": s.blocked_reason,
                }
                for s in steps
            ],
            "unavailable": [{"control_id": u.control_id, "reason": u.reason} for u in unavailable],
        },
        "dry_run": {
            "result": _DRY_RUN_RESULT_LABEL[lock.result],
            "confidence": "high" if lock.method == lockout_mod.METHOD_ENGINE else "approximate",
            "reason": lock.reason,
            "method": lock.method,
        },
        "lockout_risk": lockout_risk,
    }
