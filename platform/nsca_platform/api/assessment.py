"""Assessment — 15-api-specification.md §4.

`POST /campaigns/{id}/assess` and `GET /assessments/{id}` are DB-backed via
`services/assessment.py` (backend-02 M2's fixture-then-real worker
pipeline, §3). `facts`/`facts/{path}`/`unmatched` stay the M0 literal-example
stub — the fixture assessments this milestone builds do carry a handful of
real `fact` rows (persisted by `services/assessment.py`), but reproducing
the full per-fact/`unmatched` endpoints against them field-for-field is not
part of the M2 acceptance criterion (the MGMT-SW-04 dispute reproduction)
and is deferred rather than half-built under time pressure.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from nsca_platform.auth.dev_auth import DevUser, get_current_user
from nsca_platform.db.engine import connect
from nsca_platform.services import assessment as assessment_service

router = APIRouter(tags=["assessment"])

_ASSESSMENT_SUMMARY_EXAMPLE: dict[str, Any] = {
    "id": "ASM-2026Q3-004121",
    "device": "CORE-SW-01",
    "platform": "cisco_iosxe",
    "os_version": "16.12.04",
    "serials": [{"component": "chassis", "serial": "FCW2140L0GH"}],
    "scores": {"compliance": 0.78, "coverage": 0.92, "meaningful_ratio": 0.64, "security": 0.61},
    "counts": {"pass": 112, "fail": 31, "unknown": 12, "not_applicable": 14, "pass_partial": 6},
    "rulepacks_used": [{"id": "cisco_iosxe", "version": "7.2.1", "trust_tier": "certified"}],
    "grammar_coverage": 0.998,
    "unaudited_capabilities": [
        {
            "path": "services.web_mgmt_8443",
            "port": 8443,
            "properties": ["listens", "authenticates", "mutates"],
            "controls_contaminated": 6,
        }
    ],
}

_FACT_WITH_PROVENANCE_EXAMPLE: dict[str, Any] = {
    "path": "mgmt.protocols.telnet.enabled",
    "value": True,
    "provenance": {
        "source": "explicit",
        "artifact": "ART-004121",
        "artifact_hash": "3f9a...c21b",
        "lines": [143],
        "excerpt": " transport input telnet ssh",
        "extractor": "cisco_iosxe.vty.transport_input@7",
        "rulepack": "cisco_iosxe@7.2.1",
        "trust_tier": "certified",
        "confidence": 1.0,
    },
}


@router.post("/campaigns/{campaign_id}/assess", status_code=status.HTTP_202_ACCEPTED)
def run_assessment(campaign_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        try:
            result = assessment_service.run_assessment(conn, campaign_id, user.email)
        except assessment_service.CampaignNotFoundForAssessment as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        conn.commit()
        return result


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        result = assessment_service.get_assessment(conn, assessment_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=assessment_id)
    return result


@router.get("/assessments/{assessment_id}/facts")
def get_assessment_facts(assessment_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    return {"assessment_id": assessment_id, "facts": [_FACT_WITH_PROVENANCE_EXAMPLE]}


@router.get("/assessments/{assessment_id}/facts/{path:path}")
def get_assessment_fact(
    assessment_id: str,
    path: str,
    user: DevUser = Depends(get_current_user),
) -> dict[str, Any]:
    return {**_FACT_WITH_PROVENANCE_EXAMPLE, "path": path}


@router.get("/assessments/{assessment_id}/unmatched")
def get_assessment_unmatched(assessment_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "assessment_id": assessment_id,
        "unmatched_constructs": [
            {
                "line": 214,
                "text": "set queue type=pcq name=mgmt-limit",
                "section": "/queue type",
                "reason": "no extractor registered for this construct",
            }
        ],
    }
