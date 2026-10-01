"""Knowledge base — 15-api-specification.md §7.

M4: `/frameworks/import` and `/rulepacks/import`/`/rulepacks/{id}/export`
are wired to real logic (backend-02 §4.5) —
`knowledge_import.stig_xccdf`/`nist_oscal` (direct machine-readable parses,
begun first per 06-controls-and-frameworks.md §5) and
`knowledge_import.rulepack_bundle` (checksum-manifest signature
verification, 07-vendor-rulepacks.md §9.2). CIS (assisted PDF extraction)
and ISO (identifier-only) import are still out of this milestone's scope,
per the task brief.

M5 (Phase 3 demo-rehearsal Bugs 1/2/3/4/5): `list_rulepacks`,
`rulepack_coverage`, `list_controls`, `list_frameworks`,
`framework_coverage`, `preview_framework_update`, `ratify_framework_update`,
`get_schema` and `knowledge_freshness` are now wired to real data —
`services/knowledge_service.py`'s module docstring covers the full
rationale, including which pieces (framework preview's added/modified/
withdrawn diff) are honestly reduced rather than fabricated.

Every state-changing route never renders non-redistributable framework text
(DM-9) — enforced at the DB layer (`framework_item`'s CHECK constraint,
`db/migrations/versions/0005_...py`), not just here.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from nsca_platform.auth.dev_auth import DevUser, get_current_user
from nsca_platform.db.engine import connect
from nsca_platform.knowledge_import import nist_oscal, rulepack_bundle, stig_xccdf
from nsca_platform.services import knowledge_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/rulepacks")
def list_rulepacks(user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    return {"items": knowledge_service.list_rulepacks()}


@router.get("/rulepacks/{rulepack_id}/coverage")
def rulepack_coverage(rulepack_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    try:
        return knowledge_service.rulepack_coverage(rulepack_id)
    except knowledge_service.RulepackNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"no such rulepack: {rulepack_id}") from exc


@router.post("/rulepacks/import", status_code=201)
def import_rulepack(file: UploadFile = File(...), user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    content = file.file.read()
    try:
        result = rulepack_bundle.import_bundle(content)
    except rulepack_bundle.SignatureVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except rulepack_bundle.BundleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "id": result.platform, "version": result.version, "status": "imported",
        "signature_verified": result.signature_verified, "trust_tier": result.trust_tier,
    }


@router.get("/rulepacks/{rulepack_id}/export")
def export_rulepack(rulepack_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    import hashlib
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "knowledge" / "rulepacks" / f"{rulepack_id}.yaml"
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"no such rulepack: {rulepack_id}")
    bundle = rulepack_bundle.export_bundle(path)
    return {
        "id": rulepack_id,
        "version": "7.2.1",
        "bundle_url": f"/api/v1/knowledge/rulepacks/{rulepack_id}/export/download",
        "signature": "sha256:" + hashlib.sha256(bundle).hexdigest(),
    }


@router.get("/rulepacks/{rulepack_id}/export/download")
def download_rulepack_bundle(rulepack_id: str, user: DevUser = Depends(get_current_user)):
    from pathlib import Path

    from fastapi import Response

    path = Path(__file__).resolve().parents[3] / "knowledge" / "rulepacks" / f"{rulepack_id}.yaml"
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"no such rulepack: {rulepack_id}")
    bundle = rulepack_bundle.export_bundle(path)
    return Response(content=bundle, media_type="application/zip")


@router.get("/controls")
def list_controls(user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    return {"items": knowledge_service.list_controls()}


@router.get("/frameworks")
def list_frameworks(user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        return {"items": knowledge_service.list_frameworks(conn)}


@router.get("/frameworks/{framework_id}/coverage")
def framework_coverage(framework_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        try:
            return knowledge_service.framework_coverage(conn, framework_id)
        except knowledge_service.FrameworkNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no imported items found for framework {framework_id!r}",
            ) from exc


@router.post("/frameworks/import", status_code=201)
def import_framework(
    file: UploadFile = File(...),
    framework: str | None = None,
    benchmark: str | None = None,
    user: DevUser = Depends(get_current_user),
) -> dict[str, Any]:
    """STIG XCCDF and NIST OSCAL only (06-controls-and-frameworks.md §5:
    "begin here" — CIS/ISO import is out of this milestone's scope). Format
    is detected from content when `framework` isn't given explicitly: XML
    -> STIG XCCDF, JSON -> NIST OSCAL."""

    content = file.file.read()
    stripped = content.lstrip()
    fmt = framework or ("stig" if stripped.startswith(b"<") else "nist")

    try:
        if fmt == "stig":
            items = stig_xccdf.parse_xccdf(content, benchmark=benchmark)
        elif fmt == "nist":
            items = nist_oscal.parse_oscal_catalog(content, benchmark=benchmark)
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"unsupported framework {fmt!r} — only 'stig' and 'nist' are imported this milestone "
                       f"(CIS/ISO import is out of scope, see 06-controls-and-frameworks.md §5)",
            )
    except (stig_xccdf.StigParseError, nist_oscal.OscalParseError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    if not items:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="no framework items found in upload")

    with connect() as conn:
        result = knowledge_service.import_framework_items(conn, items, actor=user.email)
        conn.commit()
        return result


@router.get("/frameworks/{framework_id}/items")
def list_framework_items(
    framework_id: str, benchmark: str | None = None, user: DevUser = Depends(get_current_user)
) -> dict[str, Any]:
    with connect() as conn:
        return {"items": knowledge_service.list_framework_items(conn, framework=framework_id, benchmark=benchmark)}


@router.post("/frameworks/{framework_id}/preview")
def preview_framework_update(framework_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        try:
            return knowledge_service.preview_framework_update(conn, framework_id)
        except knowledge_service.FrameworkNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no imported items found for framework {framework_id!r} — nothing to preview",
            ) from exc


@router.post("/frameworks/{framework_id}/ratify")
def ratify_framework_update(framework_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        try:
            result = knowledge_service.ratify_framework_update(conn, framework_id, actor=user.email)
        except knowledge_service.FrameworkNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no imported items found for framework {framework_id!r} — nothing to ratify",
            ) from exc
        conn.commit()
        return result


@router.get("/schema")
def get_schema(user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    return {"items": knowledge_service.schema_items()}


@router.post("/schema/register", status_code=201)
def register_schema_entry(body: dict[str, Any], user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    return {**body, "status": "registered"}


@router.get("/freshness")
def knowledge_freshness(user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    return knowledge_service.freshness()
