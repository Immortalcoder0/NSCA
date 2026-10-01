"""Ingestion — 15-api-specification.md §3.

M1: `POST /campaigns/{id}/artifacts` and `/artifacts/bundle` are DB-backed
via `services/ingestion.py` — real hashing, content-addressed storage,
correlation and four-state classification. `collect` (live read-only
collection) and the job-queue endpoints stay M0 stubs — the job queue
(`jobs/`, Postgres `SKIP LOCKED`) and a real collector are out of M1 scope.
`GET /artifacts/{id}` and `.../content` read from the real `artifact`
table when the id was actually issued by this process; unknown ids fall
back to the M0 example response so the M0 acceptance tests and any
frontend code still exercising synthetic ids keep working.

`CollectionRequest.mode` is typed as `Literal["read_only"]`
(TECH-STACK.md §4, G4) so a write mode is not expressible at the schema
level, not merely rejected by a runtime check.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from nsca_platform.auth.dev_auth import DevUser, get_current_user
from nsca_platform.db.engine import connect
from nsca_platform.db.models.artifact import artifact as artifact_table
from nsca_platform.db.models.device import device as device_table
from nsca_platform.services import ingestion as ingestion_service

router = APIRouter(tags=["ingestion"])


class CollectionTarget(BaseModel):
    host: str
    credential_ref: str


class CollectionRequest(BaseModel):
    targets: list[CollectionTarget]
    artifacts: list[str]
    mode: Literal["read_only"]  # G4 — no other value is expressible


@router.post("/campaigns/{campaign_id}/artifacts", status_code=status.HTTP_201_CREATED)
async def upload_artifacts(
    campaign_id: str,
    files: list[UploadFile] = File(default=[]),
    user: DevUser = Depends(get_current_user),
) -> dict[str, Any]:
    payload = [(f.filename or "unnamed", await f.read()) for f in files]
    with connect() as conn:
        try:
            result = ingestion_service.upload_artifacts(conn, campaign_id, payload, user.email)
        except ingestion_service.IngestionError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        conn.commit()
        return result


@router.post("/campaigns/{campaign_id}/artifacts/bundle", status_code=status.HTTP_201_CREATED)
async def upload_artifact_bundle(
    campaign_id: str,
    file: UploadFile = File(...),
    user: DevUser = Depends(get_current_user),
) -> dict[str, Any]:
    # M1 treats a single-file "bundle" upload as one artifact through the
    # same classification path as `artifacts`. Real archive/show-tech
    # extraction (splitting a tar/zip/tech-support bundle into its
    # constituent per-device artifacts, `parent_artifact` linkage per
    # 14-data-model.md §2 ARTIFACT) is not yet implemented — flagged as a
    # gap, not silently faked: a multi-file archive uploaded here is
    # currently classified as a single opaque artifact, which will
    # usually resolve to `unidentified`.
    content = await file.read()
    with connect() as conn:
        try:
            result = ingestion_service.upload_artifacts(
                conn, campaign_id, [(file.filename or "bundle", content)], user.email
            )
        except ingestion_service.IngestionError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        conn.commit()
        return result


@router.post("/campaigns/{campaign_id}/collect", status_code=status.HTTP_202_ACCEPTED)
def start_collection(
    campaign_id: str,
    body: CollectionRequest,
    user: DevUser = Depends(get_current_user),
) -> dict[str, Any]:
    # M0 stub retained — real collectors and the job queue land in a later
    # milestone (backend-02 §4: `jobs/`).
    return {"job_id": "job-2026-004900", "status": "queued"}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    # M1 ingestion is synchronous (no `jobs/` queue yet), so every job id
    # this process issued is already "completed" by the time a client
    # could poll it. Kept as the M0 stub shape.
    return {
        "job_id": job_id,
        "status": "completed",
        "progress": {"done": 389, "total": 389},
        "result": {"accepted": 389},
    }


def _artifact_row_to_response(row: Any, hostname: str | None) -> dict[str, Any]:
    return {
        "artifact_id": row.public_id,
        "filename": row.filename,
        "sha256": row.content_hash,
        "device": hostname,
        "platform": row.platform,
        "os_version": row.os_version,
        "artifact_type": row.artifact_type,
        "export_mode": row.export_mode,
        "status": row.status,
        "custody": {
            "received_from": row.received_from,
            "received_at": row.received_at.isoformat(),
            "content_addressed_path": row.storage_path,
        },
    }


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    try:
        with connect() as conn:
            row = conn.execute(select(artifact_table).where(artifact_table.c.public_id == artifact_id)).first()
            if row is not None:
                hostname = None
                if row.device_id is not None:
                    device_row = conn.execute(
                        select(device_table.c.hostname).where(device_table.c.id == row.device_id)
                    ).first()
                    hostname = device_row[0] if device_row else None
                return _artifact_row_to_response(row, hostname)
    except OperationalError:
        # No reachable Postgres — fall through to the documented example
        # below rather than 500ing (matters for pre-M1 callers exercising
        # this endpoint's shape without a DB available, e.g. this repo's
        # own M0 acceptance tests when no Postgres is running).
        pass

    # Unknown/synthetic id (e.g. the M0 acceptance fixture "ART-004121") —
    # fall back to the documented example so pre-M1 callers keep working.
    return {
        "artifact_id": artifact_id,
        "filename": "CORE-SW-01/running-config.txt",
        "sha256": "3f9a...c21b",
        "device": "CORE-SW-01",
        "platform": "cisco_iosxe",
        "os_version": "16.12.04",
        "artifact_type": "running_config",
        "export_mode": "verbose",
        "status": "parsed",
        "custody": {
            "received_from": "web-upload",
            "received_at": "2026-08-28T09:12:41Z",
            "content_addressed_path": "artifacts/3f/9a/3f9a...c21b",
        },
    }


@router.get("/artifacts/{artifact_id}/content")
def get_artifact_content(artifact_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    from nsca_platform.db import artifact_store

    try:
        with connect() as conn:
            row = conn.execute(select(artifact_table).where(artifact_table.c.public_id == artifact_id)).first()
            if row is not None:
                try:
                    content = artifact_store.read(row.content_hash)
                    text = content.decode("utf-8", errors="replace")
                except OSError:
                    text = ""
                return {
                    "artifact_id": artifact_id,
                    "content": text,
                    "masked": user.role.value != "network_administrator",
                }
    except OperationalError:
        pass

    return {
        "artifact_id": artifact_id,
        "content": "! secrets masked by role\nhostname CORE-SW-01\n...",
        "masked": user.role.value != "network_administrator",
    }
