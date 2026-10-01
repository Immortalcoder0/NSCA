"""Campaigns — 15-api-specification.md §2.

M1: DB-backed via `services/campaign.py`. Response shapes are unchanged
from the M0 stub (backend-02 M1 task instructions: "Keep the response JSON
shapes byte-identical ... only the data source changes from hardcoded to
DB-backed") — `compare` remains a stub returning the spec's literal
example (delta decomposition needs the finding lifecycle and knowledge-base
diffing machinery, both out of M1 scope).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from nsca_platform.auth.dev_auth import DevUser, Role, get_current_user, require_role
from nsca_platform.db.engine import connect
from nsca_platform.services import campaign as campaign_service
from nsca_platform.services.scope_filter import ScopeExpressionError

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_campaign(body: dict[str, Any], user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        try:
            result = campaign_service.create_campaign(conn, body, user.email)
        except campaign_service.UnknownFrameworkError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        conn.commit()
        return result


@router.get("")
def list_campaigns(user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        return campaign_service.list_campaigns(conn)


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        try:
            return campaign_service.get_campaign(conn, campaign_id)
        except campaign_service.CampaignNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{campaign_id}")
def update_campaign(
    campaign_id: str,
    body: dict[str, Any],
    user: DevUser = Depends(get_current_user),
) -> dict[str, Any]:
    with connect() as conn:
        try:
            result = campaign_service.update_campaign(conn, campaign_id, body, user.email)
        except campaign_service.CampaignNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except campaign_service.CampaignStateError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except campaign_service.UnknownFrameworkError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        conn.commit()
        return result


@router.post("/{campaign_id}/scope/resolve")
def resolve_scope(campaign_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        try:
            result = campaign_service.resolve_scope(conn, campaign_id, user.email)
        except campaign_service.CampaignNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ScopeExpressionError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        conn.commit()
        return result


@router.post("/{campaign_id}/issue")
def issue_campaign(
    campaign_id: str,
    user: DevUser = Depends(require_role(Role.LEAD_ASSESSOR)),
) -> dict[str, Any]:
    with connect() as conn:
        try:
            result = campaign_service.issue_campaign(conn, campaign_id, user.email)
        except campaign_service.CampaignNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except campaign_service.CampaignStateError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        conn.commit()
        return result


@router.post("/{campaign_id}/close")
def close_campaign(campaign_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        try:
            result = campaign_service.close_campaign(conn, campaign_id, user.email)
        except campaign_service.CampaignNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except campaign_service.CampaignStateError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        conn.commit()
        return result


@router.get("/{campaign_id}/completeness")
def campaign_completeness(campaign_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        try:
            return campaign_service.completeness(conn, campaign_id)
        except campaign_service.CampaignNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# compare — out of M1 scope (needs finding lifecycle + knowledge-base diff,
# M2/M4). Left as the M0 stub, returning the spec's literal example.
# ---------------------------------------------------------------------------


@router.get("/{campaign_id}/compare/{other}")
def compare_campaigns(
    campaign_id: str,
    other: str,
    user: DevUser = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "from": "Q2-2026",
        "to": "Q3-2026",
        "compliance": {"from": 0.78, "to": 0.81},
        "decomposition": [
            {"cause": "verified_remediation", "delta": 0.05, "findings": 34},
            {
                "cause": "framework_version_change",
                "delta": -0.03,
                "detail": "STIG 2025-10 → 2026-01: 14 added, 6 tightened",
            },
            {"cause": "scope_change", "delta": 0.01, "detail": "12 devices decommissioned"},
            {"cause": "configuration_regression", "delta": 0.00, "findings": 0},
        ],
    }
