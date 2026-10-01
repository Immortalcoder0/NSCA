"""Reports — 15-api-specification.md §8.

M4: wired to real rendering (`services/report_service.py` ->
`reporting/document_model.py` + `pdf.py`/`docx.py`/`exports.py`,
TECH-STACK.md §11). `generate_report` runs synchronously (no job-queue
worker for report generation exists yet — the `job_id`/`status: "queued"`
response shape is kept unchanged from the M0 spec example, but the work is
already done by the time this call returns, so `GET /reports/{id}` is
immediately consistent rather than needing to be polled). `estate_report`
and `export_campaign` (campaign-wide, not per-device) remain M0 stubs —
out of this milestone's scope (per-device reporting was the explicit
focus, matching the problem statement's own "single PDF report for each
device" framing).

M5 (Phase 3 demo-rehearsal Bug 7): `GET /reports` (list, optionally
filtered by `campaign_id`) is new — the module previously had no way to
enumerate previously-generated reports at all, only fetch one by id.
Real query against the `report` table (`services/report_service.list_reports`).
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from nsca_platform.auth.dev_auth import DevUser, get_current_user
from nsca_platform.db.engine import connect
from nsca_platform.services import report_service

router = APIRouter(tags=["reports"])

_MEDIA_TYPES: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "json": "application/json",
    "csv": "text/csv",
    "oscal": "application/json",
}


@router.post("/campaigns/{campaign_id}/reports/generate", status_code=status.HTTP_202_ACCEPTED)
def generate_report(
    campaign_id: str,
    device: str = Query(..., description="device hostname to generate the per-device report for"),
    mode: Literal["draft", "issued"] = Query("draft"),
    user: DevUser = Depends(get_current_user),
) -> dict[str, Any]:
    with connect() as conn:
        try:
            result = report_service.generate_report(conn, campaign_id, device, mode=mode, actor=user.email)
        except report_service.CampaignNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except report_service.DeviceNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except report_service.CampaignNotIssuable as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        conn.commit()
        # Synchronous today (no report-generation worker yet) — response
        # shape kept spec-compatible (`job_id`/`status`) so a future queued
        # implementation is a drop-in change, not a breaking one.
        return {"job_id": result["id"], "status": "done", "report_id": result["id"]}


@router.get("/reports")
def list_reports(
    campaign_id: str | None = Query(None, description="filter to one campaign's reports, by campaign public id"),
    user: DevUser = Depends(get_current_user),
) -> dict[str, Any]:
    with connect() as conn:
        try:
            return report_service.list_reports(conn, campaign_id=campaign_id)
        except report_service.CampaignNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/reports/{report_id}")
def get_report(report_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        try:
            return report_service.get_report_meta(conn, report_id)
        except report_service.ReportNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: str,
    format: Literal["pdf", "docx", "json", "csv", "oscal"] = Query(...),
    user: DevUser = Depends(get_current_user),
) -> Response:
    media_type = _MEDIA_TYPES[format]
    with connect() as conn:
        try:
            body = report_service.download_report_bytes(conn, report_id, format)
        except report_service.ReportNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(content=body, media_type=media_type)


@router.get("/reports/{report_id}/manifest")
def report_manifest(report_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        try:
            return report_service.get_manifest(conn, report_id)
        except report_service.ReportNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/reports/{report_id}/verify")
def verify_report(report_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        try:
            result = report_service.verify_report(conn, report_id, actor=user.email)
        except report_service.ReportNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        conn.commit()
        return result


@router.post("/reports/{report_id}/amend")
def amend_report(report_id: str, body: dict[str, Any], user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    return {"report_id": report_id, "status": "amended", "amendment": body}


@router.get("/campaigns/{campaign_id}/reports/estate")
def estate_report(campaign_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "campaign_id": campaign_id,
        "id": "RPT-2026Q3-ESTATE-001",
        "devices_included": 389,
        "generated_at": "2026-08-15T10:00:00Z",
    }


@router.get("/campaigns/{campaign_id}/export")
def export_campaign(campaign_id: str, user: DevUser = Depends(get_current_user)) -> Response:
    stub_body = f'{{"stub": true, "campaign_id": "{campaign_id}", "contents": ["artifacts", "assessments", "findings", "reports"]}}'.encode()
    return Response(content=stub_body, media_type="application/zip")
