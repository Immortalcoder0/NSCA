"""Report generation service — TRD-09.1, backend-02 §4.6, M4.

Wires `reporting/document_model.py` + `pdf.py`/`docx.py`/`exports.py` to
real, stored campaign/device/finding data (RPT-2 / INV-09.1-01: "No
verdict, score, severity or finding is computed during rendering" — this
module *gathers* stored rows into `DeviceReportData`; it does not compute
any new verdict/score itself, only tallies already-stored per-finding
verdicts into the summary counts `document_model.ScoreSummary` needs).

**Simplification, flagged rather than silently assumed:** a finding row
does not currently carry a per-extractor `rule_status` (that lives on
`candidate_rule`, keyed by extractor id, with no direct join wired to
`finding` this milestone) — `rule_status` is derived here as `"ratified"`
unless the finding's own `rulepack_trust_tier == "provisional"`, in which
case `"provisional"`. This is coarser than the real per-rule status table
but is a conservative subset of `learning.ratification.is_report_eligible`'s
check (which also independently gates on `rulepack_trust_tier` — the
finer-grained rule-status signal, when wired up, only *removes* more
findings from issued reports, never adds any that shouldn't be there).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from nsca_platform.audit import log as audit_log
from nsca_platform.db import artifact_store
from nsca_platform.db.models.admin import report as report_table
from nsca_platform.db.models.campaign import campaign as campaign_table
from nsca_platform.db.models.device import device as device_table
from nsca_platform.db.models.finding import finding as finding_table
from nsca_platform.db.models.lifecycle import remediation_plan as remediation_plan_table
from nsca_platform.knowledge_base_loader import KnowledgeBaseUnavailable, get_knowledge_base
from nsca_platform.reporting import document_model as dm
from nsca_platform.reporting import exports as exports_mod
from nsca_platform.reporting import pdf as pdf_mod
from nsca_platform.reporting.document_model import (
    CampaignInfo,
    DeviceIdentification,
    DeviceReportData,
    FindingRecord,
    KnowledgeBaseVersions,
    RawEvidenceLine,
    RemediationPlanView,
    ScoreSummary,
    UnassessedItem,
)

try:
    from nsca_platform.reporting import docx as docx_mod
except Exception:  # pragma: no cover - python-docx not installed
    docx_mod = None  # type: ignore[assignment]


class CampaignNotFound(Exception):
    pass


class DeviceNotFound(Exception):
    pass


class ReportNotFound(Exception):
    pass


class CampaignNotIssuable(Exception):
    """TRD-09.1 §5: "Report requested for an in-progress campaign -> Draft
    only; issuance refused until the campaign reaches Review.\""""


def _rule_status(rulepack_trust_tier: str | None) -> str:
    return "provisional" if rulepack_trust_tier == "provisional" else "ratified"


def _finding_row_to_record(row: Any) -> FindingRecord:
    evidence = row.evidence or []
    first = evidence[0] if evidence else None
    artifact_filename = first.get("artifact") if first else None
    evidence_lines = tuple(
        RawEvidenceLine(
            number=ln,
            text=(first.get("excerpt") or "").splitlines()[i] if first and first.get("excerpt") else "",
            highlighted=ln in (first.get("highlight") or []) if first else False,
        )
        for i, ln in enumerate((first.get("lines") or []) if first else [])
    )
    frameworks = tuple(
        f"{fr.get('framework')}:{fr.get('id')}" if isinstance(fr, dict) else str(fr)
        for fr in (row.framework_refs or [])
    )
    return FindingRecord(
        finding_id=row.public_id, control_id=row.control_id, title=row.control_id,
        verdict=row.verdict, severity_base=row.severity_base or "info",
        severity_effective=row.severity_effective or row.severity_base or "info",
        severity_reason=row.severity_reason,
        frameworks=frameworks, artifact_filename=artifact_filename,
        evidence_lines=evidence_lines,
        facts=tuple(first.get("facts") or []) if first else (),
        rule_status=_rule_status(row.rulepack_trust_tier),
        rulepack_trust_tier=row.rulepack_trust_tier,
        # Phase 3 demo rehearsal fix (finding 11): only meaningful when
        # there are no evidence_lines to render instead (an absence-based
        # citation — see FindingRecord.evidence_note's docstring); harmless
        # to always carry it through, `_finding_blocks` only reads it in
        # that case.
        evidence_note=(first.get("excerpt") if first and not evidence_lines else None),
    )


def _score_summary_from_findings(finding_rows: list[Any]) -> ScoreSummary:
    pass_count = sum(1 for f in finding_rows if f.verdict in ("PASS", "PASS_PARTIAL"))
    fail_count = sum(1 for f in finding_rows if f.verdict == "FAIL")
    unknown_count = sum(1 for f in finding_rows if f.verdict == "UNKNOWN")
    na_count = sum(1 for f in finding_rows if f.verdict == "NOT_APPLICABLE")
    determined = pass_count + fail_count
    applicable = determined + unknown_count
    return ScoreSummary(
        compliance_num=pass_count, compliance_den=determined,
        coverage_num=determined, coverage_den=applicable,
        meaningful_num=pass_count, meaningful_den=pass_count,  # pass_quality not modelled at gather time yet
        security_num=pass_count, security_den=applicable or 1,
        pass_count=pass_count, fail_count=fail_count, unknown_count=unknown_count, na_count=na_count,
        severity_counts={
            sev: sum(1 for f in finding_rows if f.verdict == "FAIL" and (f.severity_effective or f.severity_base) == sev)
            for sev in ("critical", "high", "medium", "low")
        },
    )


def _remediation_plan_view(row: Any | None) -> RemediationPlanView | None:
    if row is None:
        return None
    steps = tuple(dm.PlaybookStepBlock(**s) for s in row.steps)
    checkpoints = tuple(dm.CheckpointBlock(**c) for c in (row.checkpoints or []))
    unavailable = tuple((u["control_id"], u["reason"]) for u in (row.unavailable or []))
    lockout = dm.LockoutBlock(**row.lockout) if row.lockout else None
    dry_run = None
    if row.dry_run:
        dr = dict(row.dry_run)
        dr["newly_failing"] = tuple(tuple(x) for x in dr.get("newly_failing", []))
        dr["resolved"] = tuple(dr.get("resolved", []))
        dry_run = dm.DryRunBlock(**dr)
    return RemediationPlanView(
        steps=steps, checkpoints=checkpoints, unavailable=unavailable, lockout=lockout, dry_run=dry_run,
    )


def gather_device_report_data(
    conn: Connection, campaign_public_id: str, device_hostname: str, *, report_id: str, generated_at: datetime,
) -> DeviceReportData:
    campaign_row = conn.execute(
        select(campaign_table).where(campaign_table.c.public_id == campaign_public_id)
    ).first()
    if campaign_row is None:
        raise CampaignNotFound(campaign_public_id)
    device_row = conn.execute(select(device_table).where(device_table.c.hostname == device_hostname)).first()
    if device_row is None:
        raise DeviceNotFound(device_hostname)

    finding_rows = conn.execute(
        select(finding_table).where(
            finding_table.c.campaign_id == campaign_row.id, finding_table.c.device_id == device_row.id,
        )
    ).fetchall()

    findings = tuple(_finding_row_to_record(r) for r in finding_rows if r.verdict != "UNKNOWN")
    unassessed_ids = tuple(sorted(r.control_id for r in finding_rows if r.verdict == "UNKNOWN"))
    unassessed = (
        (UnassessedItem(control_ids=unassessed_ids, cause="see finding-level unknown_reason for each control"),)
        if unassessed_ids else ()
    )

    plan_row = conn.execute(
        select(remediation_plan_table)
        .where(
            remediation_plan_table.c.campaign_id == campaign_row.id,
            remediation_plan_table.c.device_id == device_row.id,
        )
        .order_by(remediation_plan_table.c.generated_at.desc())
    ).first()

    kb_pin = campaign_row.knowledge_base_pin or {}
    rulepacks = kb_pin.get("rulepacks") or [{}]
    control_packs = kb_pin.get("control_packs") or [{}]

    return DeviceReportData(
        report_id=report_id,
        device=DeviceIdentification(
            hostname=device_row.hostname, model=device_row.model, os_version=device_row.os_version,
            serials=tuple((s.get("component"), s.get("serial")) for s in (device_row.serials or [])),
            role=device_row.role, location=device_row.location,
        ),
        campaign=CampaignInfo(
            name=campaign_row.name, assessed_at=(device_row.last_assessed or generated_at).isoformat(),
            assessor=campaign_row.owner,
            frameworks=tuple((f.get("framework", ""), f.get("version", "")) for f in (campaign_row.frameworks or [])),
        ),
        inputs=(),
        scores=_score_summary_from_findings(list(finding_rows)),
        top_remediations=(),
        findings=findings, emergent_findings=(),
        remediation_plan=_remediation_plan_view(plan_row),
        unassessed=unassessed, unaudited_capabilities=(), assessor_notes=(),
        fact_count=0, control_count=len(finding_rows),
        knowledge_base=KnowledgeBaseVersions(
            engine=kb_pin.get("engine", "unknown"),
            rulepack_id=rulepacks[0].get("id", "unknown"), rulepack_version=rulepacks[0].get("version", "0"),
            rulepack_trust_tier=rulepacks[0].get("tier", "local"),
            control_pack_id=control_packs[0].get("id", "unknown"),
            control_pack_version=control_packs[0].get("version", "0"),
            frameworks=tuple((f.get("id", ""), f.get("version", f.get("release", ""))) for f in kb_pin.get("frameworks", [])),
            schema_registry=kb_pin.get("schema_registry", "unknown"),
        ),
        generated_at=generated_at.isoformat(),
    )


_RENDERERS = {"json": exports_mod.to_json, "csv": exports_mod.to_csv, "oscal": exports_mod.to_oscal}


def render_all_formats(document: dm.Document, data: DeviceReportData, *, generated_at: datetime) -> dict[str, bytes]:
    """Renders every format this milestone supports. PDF is attempted but
    tolerated as absent if WeasyPrint's native libraries aren't available
    on this host (`pdf.weasyprint_available()`), so report generation still
    succeeds for the formats that never depend on it."""

    out: dict[str, bytes] = {
        "json": exports_mod.to_json(data, mode=document.mode),
        "csv": exports_mod.to_csv(data, mode=document.mode),
        "oscal": exports_mod.to_oscal(data, mode=document.mode),
    }
    if docx_mod is not None:
        out["docx"] = docx_mod.render_docx(document, generated_at=generated_at)
    if pdf_mod.weasyprint_available():
        out["pdf"] = pdf_mod.render_pdf(document, generated_at=generated_at)
    return out


def generate_report(
    conn: Connection, campaign_public_id: str, device_hostname: str, *, mode: str, actor: str,
) -> dict[str, Any]:
    campaign_row = conn.execute(
        select(campaign_table).where(campaign_table.c.public_id == campaign_public_id)
    ).first()
    if campaign_row is None:
        raise CampaignNotFound(campaign_public_id)
    if mode == "issued" and campaign_row.state not in ("Review", "Issued", "Closed"):
        raise CampaignNotIssuable(
            f"campaign {campaign_public_id!r} is in state {campaign_row.state!r} — "
            f"issuance refused until the campaign reaches Review (TRD-09.1 §5)"
        )

    generated_at = datetime.now(UTC)
    report_uuid = uuid.uuid4()
    public_id = f"RPT-{campaign_public_id.replace('CMP-', '')}-{device_hostname}-{str(report_uuid)[:8]}"

    data = gather_device_report_data(
        conn, campaign_public_id, device_hostname, report_id=public_id, generated_at=generated_at,
    )
    document = dm.build_device_report_document(data, mode=mode)
    rendered = render_all_formats(document, data, generated_at=generated_at)

    content_hash = exports_mod.to_json(data, mode=mode)
    import hashlib

    report_hash = hashlib.sha256(content_hash).hexdigest()

    artifact_refs: dict[str, str] = {}
    for fmt, blob in rendered.items():
        stored = artifact_store.store(blob)
        artifact_refs[fmt] = stored.sha256

    device_row = conn.execute(select(device_table).where(device_table.c.hostname == device_hostname)).first()
    manifest = {
        "report_id": public_id, "generated": generated_at.isoformat(),
        "inputs": [{"artifact": a.filename, "sha256": a.sha256} for a in data.inputs],
        "knowledge_base": {
            "engine": data.knowledge_base.engine,
            "rulepacks": [{"id": data.knowledge_base.rulepack_id, "version": data.knowledge_base.rulepack_version}],
            "control_packs": [{"id": data.knowledge_base.control_pack_id, "version": data.knowledge_base.control_pack_version}],
        },
        "report_hash": report_hash,
        "statement": "Re-executing with identical inputs and knowledge base versions will produce a byte-identical report.",
    }

    conn.execute(
        report_table.insert().values(
            id=report_uuid, public_id=public_id, campaign_id=campaign_row.id, device_id=device_row.id if device_row else None,
            mode=mode, state=mode, generated_at=generated_at, content_hash=report_hash, manifest=manifest,
            formats_available=sorted(rendered.keys()), artifact_refs=artifact_refs,
            issued_at=generated_at if mode == "issued" else None, issued_by=actor if mode == "issued" else None,
        )
    )
    audit_log.record(
        conn, actor=actor, action="report.generate", entity_type="report", entity_id=public_id,
        details={"campaign": campaign_public_id, "device": device_hostname, "mode": mode, "hash": report_hash},
    )
    return {"id": public_id, "status": "generated", "formats_available": sorted(rendered.keys()), "hash": report_hash}


def _get_report_row(conn: Connection, report_public_id: str) -> Any:
    row = conn.execute(select(report_table).where(report_table.c.public_id == report_public_id)).first()
    if row is None:
        raise ReportNotFound(report_public_id)
    return row


def list_reports(conn: Connection, campaign_id: str | None = None) -> dict[str, Any]:
    """`GET /reports` — Phase 3 demo-rehearsal Bug 7: there was previously
    no way to enumerate previously-generated reports at all, only fetch
    one by id. Real query against the `report` table (15-api-
    specification.md §8), optionally filtered to one campaign by its
    public id. Ordered newest-first, matching how a "recent reports" list
    is actually used."""

    query = select(report_table, campaign_table.c.public_id.label("campaign_public_id")).join(
        campaign_table, report_table.c.campaign_id == campaign_table.c.id
    )
    if campaign_id is not None:
        campaign_row = conn.execute(
            select(campaign_table).where(campaign_table.c.public_id == campaign_id)
        ).first()
        if campaign_row is None:
            raise CampaignNotFound(campaign_id)
        query = query.where(report_table.c.campaign_id == campaign_row.id)

    rows = conn.execute(query.order_by(report_table.c.generated_at.desc())).fetchall()

    device_ids = {r.device_id for r in rows if r.device_id is not None}
    devices_by_id: dict[Any, str] = {}
    if device_ids:
        for d in conn.execute(select(device_table).where(device_table.c.id.in_(device_ids))).fetchall():
            devices_by_id[d.id] = d.hostname

    items = [
        {
            "id": r.public_id,
            "campaign_id": r.campaign_public_id,
            "device": devices_by_id.get(r.device_id) if r.device_id else None,
            "mode": r.mode,
            "state": r.state,
            "generated_at": r.generated_at.isoformat(),
            "formats_available": r.formats_available or [],
            "hash": r.content_hash,
        }
        for r in rows
    ]
    return {"items": items, "next_cursor": None}


def get_report_meta(conn: Connection, report_public_id: str) -> dict[str, Any]:
    row = _get_report_row(conn, report_public_id)
    campaign_row = conn.execute(select(campaign_table).where(campaign_table.c.id == row.campaign_id)).first()
    device_row = conn.execute(select(device_table).where(device_table.c.id == row.device_id)).first() if row.device_id else None
    return {
        "id": row.public_id,
        "campaign_id": campaign_row.public_id if campaign_row else None,
        "device": device_row.hostname if device_row else None,
        "generated_at": row.generated_at.isoformat(),
        "formats_available": row.formats_available or [],
        "hash": row.content_hash,
    }


def download_report_bytes(conn: Connection, report_public_id: str, fmt: str) -> bytes:
    row = _get_report_row(conn, report_public_id)
    refs = row.artifact_refs or {}
    sha = refs.get(fmt)
    if sha is None:
        raise ReportNotFound(f"{report_public_id} has no stored {fmt!r} rendering")
    return artifact_store.read(sha)


def get_manifest(conn: Connection, report_public_id: str) -> dict[str, Any]:
    row = _get_report_row(conn, report_public_id)
    return row.manifest or {}


def verify_report(conn: Connection, report_public_id: str, *, actor: str) -> dict[str, Any]:
    """TRD-09.1 §4 `verify(report_id) -> (MATCH|MISMATCH, original_hash,
    recomputed_hash)`. Re-gathers the same stored rows and re-renders the
    JSON export (the format every host can render without a native-library
    dependency) — matches this milestone's own RPT-2 rule: nothing is
    recomputed, only re-rendered from the same stored data."""

    row = _get_report_row(conn, report_public_id)
    campaign_row = conn.execute(select(campaign_table).where(campaign_table.c.id == row.campaign_id)).first()
    device_row = conn.execute(select(device_table).where(device_table.c.id == row.device_id)).first() if row.device_id else None
    if campaign_row is None or device_row is None:
        return {
            "report_id": report_public_id, "result": "UNVERIFIABLE",
            "original_hash": row.content_hash, "recomputed_hash": None, "knowledge_base_identical": None,
        }

    data = gather_device_report_data(
        conn, campaign_row.public_id, device_row.hostname, report_id=row.public_id, generated_at=row.generated_at,
    )
    import hashlib

    recomputed_hash = hashlib.sha256(exports_mod.to_json(data, mode=row.mode)).hexdigest()
    result = "MATCH" if recomputed_hash == row.content_hash else "MISMATCH"
    knowledge_base_identical = _knowledge_base_identical_to_manifest(row.manifest)
    audit_log.record(
        conn, actor=actor, action="report.verify", entity_type="report", entity_id=report_public_id,
        details={
            "result": result, "original_hash": row.content_hash, "recomputed_hash": recomputed_hash,
            "knowledge_base_identical": knowledge_base_identical,
        },
    )
    return {
        "report_id": report_public_id, "result": result,
        "original_hash": row.content_hash, "recomputed_hash": recomputed_hash,
        "knowledge_base_identical": knowledge_base_identical,
    }


def _knowledge_base_identical_to_manifest(manifest: dict[str, Any] | None) -> bool | None:
    """Bug found during the Phase 3 demo rehearsal: this was hardcoded
    `True` unconditionally, so a real MISMATCH (report content drifted)
    always rendered as "same knowledge base, content regenerated
    differently" — the more alarming, correctly-styled defect case per the
    UX spec — rather than distinguishing it from an *expected* drift after
    a knowledge-base change. Real fix: compare the manifest's frozen
    `knowledge_base.rulepacks`/`control_packs` id@version set (recorded at
    generation time) against the currently-live `KnowledgeBase`'s pin.

    Known, honest limitation: rulepack YAML files don't bump their own
    `version` field when the learning subsystem writes new extractors into
    them (`rule_synthesis.write_extractors_to_rulepack` — teaching more
    rules for an *already-loaded* platform doesn't change its version
    string). This check reliably detects a platform/control-pack being
    added, removed, or version-bumped; it does not detect same-version
    content drift within one rulepack file. That's a real gap in the
    underlying versioning scheme, not something to paper over here with a
    fabricated content hash the rest of the system doesn't use.
    """

    if not manifest:
        return None
    try:
        current_kb = get_knowledge_base()
    except KnowledgeBaseUnavailable:
        return None

    current_versions = frozenset(current_kb.pin.rulepack_versions) | frozenset(current_kb.pin.control_pack_versions)

    original_kb = manifest.get("knowledge_base") or {}
    original_versions = frozenset(
        f"{rp.get('id')}@{rp.get('version')}" for rp in original_kb.get("rulepacks", [])
    ) | frozenset(
        f"{cp.get('id')}@{cp.get('version')}" for cp in original_kb.get("control_packs", [])
    )
    return current_versions == original_versions
