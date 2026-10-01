"""Findings — 15-api-specification.md §5, backend-02 M2: DB-backed via
`services/finding_lifecycle.py`, `services/dispute.py`,
`services/risk_acceptance.py`.

`RiskAcceptanceRequest.expires_at` being a required (non-Optional) field is
already the Pydantic validator FR-FND-008 wants (TECH-STACK.md §4's own
`RiskAcceptanceRequest` example does exactly this — a required field IS a
`model_validator`-equivalent product-meaning check enforced by the type
system, not a service-layer `if`). `no_backdated_expiry` below adds a
second, genuinely cross-field validator on top (expiry must be in the
future relative to submission) using `@model_validator`, since "no
indefinite acceptance" (09-findings-lifecycle.md §7) is naturally read as
"no acceptance that's already meaningless," not just "the field must be
present."
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from nsca_platform.auth.dev_auth import DevUser, Role, get_current_user, require_role
from nsca_platform.db.engine import connect
from nsca_platform.services import dispute as dispute_service
from nsca_platform.services import finding_lifecycle
from nsca_platform.services import graph_cache
from nsca_platform.services import remediation_service
from nsca_platform.services import risk_acceptance as risk_acceptance_service

router = APIRouter(tags=["findings"])


class DisputeRequest(BaseModel):
    type: str
    claim: str


class RiskAcceptanceRequest(BaseModel):
    expires_at: date  # not Optional — FR-FND-008
    justification: str = Field(min_length=20)
    compensating_control: dict[str, Any] | None = None

    @model_validator(mode="after")
    def no_backdated_expiry(self) -> "RiskAcceptanceRequest":
        # 09-findings-lifecycle.md §7: "no indefinite acceptance" — read
        # here as "no acceptance whose expiry has already passed," which
        # is exactly as meaningless as no expiry at all.
        if self.expires_at <= date.today():
            raise ValueError("expires_at must be in the future — indefinite/backdated risk acceptance is not allowed")
        return self


def _handle_common(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except finding_lifecycle.FindingNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except finding_lifecycle.IllegalTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/campaigns/{campaign_id}/findings")
def list_findings(
    campaign_id: str,
    verdict: str | None = None,
    severity: str | None = None,
    state: str | None = None,
    control: str | None = None,
    group_by: str | None = None,
    sort: str | None = None,
    platform: str | None = None,
    user: DevUser = Depends(get_current_user),
) -> dict[str, Any]:
    with connect() as conn:
        if group_by == "device":
            return finding_lifecycle.device_grid(conn, campaign_id, sort=sort, platform=platform)
        filters = {"verdict": verdict, "severity": severity, "state": state, "control": control}
        return finding_lifecycle.list_findings(conn, campaign_id, {k: v for k, v in filters.items() if v})


@router.get("/findings/{finding_id}")
def get_finding(finding_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        return _handle_common(finding_lifecycle.get_finding, conn, finding_id)


@router.post("/findings/{finding_id}/confirm")
def confirm_finding(finding_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        result = _handle_common(finding_lifecycle.confirm, conn, finding_id, user.email)
        conn.commit()
        return result


class AssignRequest(BaseModel):
    assignee: str


@router.post("/findings/{finding_id}/assign")
def assign_finding(
    finding_id: str,
    body: AssignRequest,
    user: DevUser = Depends(get_current_user),
) -> dict[str, Any]:
    with connect() as conn:
        result = _handle_common(finding_lifecycle.assign, conn, finding_id, body.assignee, user.email)
        conn.commit()
        return result


@router.post("/findings/{finding_id}/dispute", status_code=status.HTTP_201_CREATED)
def dispute_finding(
    finding_id: str,
    body: DisputeRequest,
    user: DevUser = Depends(get_current_user),
) -> dict[str, Any]:
    with connect() as conn:
        try:
            result = dispute_service.raise_dispute(conn, finding_id, body.type, body.claim, user.email)
        except finding_lifecycle.FindingNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except finding_lifecycle.IllegalTransition as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except dispute_service.InvalidDisputeType as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        conn.commit()
        return result


class AdjudicateRequest(BaseModel):
    decision: Literal["upheld", "overturned"]
    notes: str | None = None


@router.post("/findings/{finding_id}/adjudicate")
def adjudicate_finding(
    finding_id: str,
    body: AdjudicateRequest,
    user: DevUser = Depends(require_role(Role.LEAD_ASSESSOR)),
) -> dict[str, Any]:
    with connect() as conn:
        try:
            result = dispute_service.adjudicate(conn, finding_id, body.decision, body.notes, user.email)
        except finding_lifecycle.FindingNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except finding_lifecycle.IllegalTransition as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        conn.commit()
        return result


@router.post("/findings/{finding_id}/accept-risk")
def accept_risk(
    finding_id: str,
    body: RiskAcceptanceRequest,
    user: DevUser = Depends(require_role(Role.LEAD_ASSESSOR)),
) -> dict[str, Any]:
    with connect() as conn:
        expires_at = datetime.combine(body.expires_at, datetime.min.time(), tzinfo=timezone.utc)
        try:
            result = risk_acceptance_service.accept_risk(
                conn, finding_id, expires_at, body.justification, body.compensating_control, user.email
            )
        except finding_lifecycle.FindingNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except finding_lifecycle.IllegalTransition as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        conn.commit()
        return result


@router.post("/findings/{finding_id}/mark-remediated")
def mark_remediated(finding_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        result = _handle_common(finding_lifecycle.mark_remediated, conn, finding_id, user.email)
        conn.commit()
        return result


@router.post("/findings/{finding_id}/verify", status_code=status.HTTP_202_ACCEPTED)
def verify_finding(finding_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    # Real remediation verification needs a re-collection + re-assessment
    # round trip (09-findings-lifecycle.md §8) — out of M2 scope
    # (`services/verification.py` is listed in backend-02 §4's module
    # layout but not built this milestone). `finding_lifecycle
    # .apply_verification` implements the three-outcome decision table for
    # when that data exists; this endpoint stays a queued-job stub until
    # the re-collection trigger (M4/M5) exists to call it.
    return {"job_id": "job-2026-005133", "status": "queued", "finding_id": finding_id}


@router.get("/findings/{finding_id}/history")
def finding_history(finding_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        return _handle_common(finding_lifecycle.history, conn, finding_id)


@router.get("/findings/{finding_id}/remediation")
def finding_remediation(
    finding_id: str,
    operator_source: str | None = None,
    user: DevUser = Depends(get_current_user),
) -> dict[str, Any]:
    # Real remediation planner/lockout/dry-run (backend-02 §4.4, M4) —
    # Phase 3 demo rehearsal finding #8: this used to be a byte-identical
    # stub for every finding regardless of control. See
    # services/remediation_service.py for the real wiring.
    with connect() as conn:
        return _handle_common(remediation_service.get_finding_remediation, conn, finding_id, operator_source=operator_source)


class BulkTransitionRequest(BaseModel):
    finding_ids: list[str]
    action: str


@router.post("/findings/bulk")
def bulk_findings(body: BulkTransitionRequest, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        result = finding_lifecycle.bulk_transition(conn, body.finding_ids, body.action, user.email)
        conn.commit()
        return result


@router.get("/campaigns/{campaign_id}/attack-paths")
def campaign_attack_paths(campaign_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    # Real `nsca_engine.api.assess_campaign` output (Phase 3 demo rehearsal
    # gap, related to findings 7/8: this used to be a fixed M0 stub —
    # identical `AP-003` payload regardless of campaign or assessment
    # state). `services/assessment.py.run_assessment` caches the real
    # `CampaignAssessment.attack_paths` in-process, keyed by campaign
    # public id, right after it computes them (services/graph_cache.py —
    # same documented in-process/non-persisted tradeoff as the `Graph`
    # cache it already used). No cache entry means either this campaign has
    # never been assessed, or it was assessed in a different process (the
    # cache does not survive a restart) — reported honestly as an empty
    # list with a note, never a fabricated example.
    cached = graph_cache.get_risk_findings(campaign_id)
    if cached is None:
        return {
            "campaign_id": campaign_id,
            "attack_paths": [],
            "note": (
                "No cached attack-path computation for this campaign in this process. "
                "Run POST /campaigns/{id}/assess first (services/graph_cache.py's "
                "in-process cache is not persisted across restarts)."
            ),
        }
    attack_paths, _systemic_findings = cached
    return {
        "campaign_id": campaign_id,
        "attack_paths": [
            {
                "id": ap.id,
                "hops": len(ap.steps),
                "path": [{"device_id": s.device_id, "node_id": s.node_id, "rule_id": s.rule_id} for s in ap.steps],
                "source": ap.steps[0].node_id if ap.steps else None,
                "target": ap.steps[-1].node_id if ap.steps else None,
                "weakest_link_reason": ap.weakest_link_reason,
            }
            for ap in attack_paths
        ],
    }


@router.get("/campaigns/{campaign_id}/systemic")
def campaign_systemic(campaign_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    # Real `nsca_engine.risk.anomaly.detect_systemic` output via the same
    # cache as attack-paths above — see that route's comment. Used to be a
    # fixed M0 stub (`SYS-000009`, always 41 affected devices) regardless of
    # campaign state.
    cached = graph_cache.get_risk_findings(campaign_id)
    if cached is None:
        return {
            "campaign_id": campaign_id,
            "systemic_findings": [],
            "note": (
                "No cached systemic-finding computation for this campaign in this process. "
                "Run POST /campaigns/{id}/assess first (services/graph_cache.py's "
                "in-process cache is not persisted across restarts)."
            ),
        }
    _attack_paths, systemic_findings = cached
    return {
        "campaign_id": campaign_id,
        "systemic_findings": [
            {
                "id": f"SYS-{sf.control_id}",
                "control": sf.control_id,
                "affected_devices": len(sf.device_ids),
                "device_ids": list(sf.device_ids),
                "pattern": sf.description,
            }
            for sf in systemic_findings
        ],
    }
