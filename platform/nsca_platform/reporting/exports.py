"""Machine-readable exports — JSON, CSV, OSCAL. TRD-09.1 §3.9, backend-02
§4.6, M4.

All three render from `DeviceReportData` (the same input `document_model.py`
composes from) rather than from the pre-rendered `Document` tree, since
these formats need full structured fidelity (fact paths, provenance-style
detail) that the presentation-oriented block tree intentionally flattens
away for PDF/DOCX layout. This does **not** create a second source of
truth: both this module and `document_model.py` read the same
`DeviceReportData`, so a finding present in one is present in the other
(DD-09.1-01's guarantee extended to the machine-readable formats).

**INV-09.1-07** — non-redistributable framework text never appears in any
export. This module only ever emits `FindingRecord.frameworks` (bare
`"framework:id"` reference strings, e.g. `"cis:CIS-IOS-1.2.4"`), never CIS
or ISO body text — there is no field on `DeviceReportData` that carries
framework prose in the first place (TRD-05.3 INV-05.3-02's data-layer
enforcement means this module has nothing to leak even if it tried).

**V-09.1-009** — the OSCAL export contains compliance results only; the
security-posture score (`ScoreSummary.security_num`/`security_den`,
exposure/vulnerability-adjusted per TRD-06.1 DD-06.1-04) is never written
into `to_oscal`'s output — only `to_json`/`to_csv` include it, since those
are NSCA-native formats, not OSCAL's standardised conformance structure.

Determinism (backend-02 §2.5): every export uses `sort_keys=True` (JSON),
a fixed row order (CSV, from `data.findings`'s already-stored order), and
UUID5-derived (not UUID4/random) identifiers in OSCAL, so two calls with an
unchanged `DeviceReportData` produce byte-identical output.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Any

from nsca_platform.learning.ratification import is_report_eligible
from nsca_platform.reporting.document_model import DeviceReportData, FindingRecord

_OSCAL_NAMESPACE = uuid.UUID("6ec1c6b0-7f0a-4c1e-9c7a-8f6d4b6a1e00")  # fixed, not random


def _eligible(findings: tuple[FindingRecord, ...], mode: str) -> tuple[FindingRecord, ...]:
    if mode != "issued":
        return findings
    return tuple(f for f in findings if is_report_eligible(f.rule_status, f.rulepack_trust_tier))


def _finding_to_dict(f: FindingRecord) -> dict[str, Any]:
    return {
        "finding_id": f.finding_id,
        "control_id": f.control_id,
        "title": f.title,
        "verdict": f.verdict,
        "severity": {"base": f.severity_base, "effective": f.severity_effective, "reason": f.severity_reason},
        "frameworks": list(f.frameworks),
        "evidence": {
            "artifact": f.artifact_filename,
            "lines": [
                {"number": el.number, "text": el.text, "highlighted": el.highlighted, "masked": el.masked}
                for el in f.evidence_lines
            ],
        },
        "facts": list(f.facts),
        "is_emergent": f.is_emergent,
        "counterexample": list(f.counterexample),
        "contributing_devices": list(f.contributing_devices),
        "remediation_ref": f.remediation_ref,
        "rule_status": f.rule_status,
        "rulepack_trust_tier": f.rulepack_trust_tier,
    }


def to_json(data: DeviceReportData, *, mode: str = "issued") -> bytes:
    """TRD-09.1 §3.9: "Full findings with evidence, provenance, framework
    mappings." Ratios are rendered as `{numerator, denominator}` objects,
    never a bare float (D5)."""

    findings = _eligible(data.findings, mode)
    emergent = _eligible(data.emergent_findings, mode)
    s = data.scores

    obj = {
        "report_id": data.report_id,
        "mode": mode,
        "generated_at": data.generated_at,
        "device": {
            "hostname": data.device.hostname,
            "model": data.device.model,
            "os_version": data.device.os_version,
            "serials": [{"component": c, "serial": sn} for c, sn in data.device.serials],
            "role": data.device.role,
            "exposure": data.device.exposure,
            "location": data.device.location,
        },
        "campaign": {
            "name": data.campaign.name,
            "assessed_at": data.campaign.assessed_at,
            "assessor": data.campaign.assessor,
            "frameworks": [{"name": n, "version": v} for n, v in data.campaign.frameworks],
        },
        "inputs": [
            {"filename": a.filename, "sha256": a.sha256, "export_mode": a.export_mode}
            for a in data.inputs
        ],
        "scores": {
            "compliance": {"numerator": s.compliance_num, "denominator": s.compliance_den},
            "coverage": {"numerator": s.coverage_num, "denominator": s.coverage_den},
            "meaningful": {"numerator": s.meaningful_num, "denominator": s.meaningful_den},
            "security_posture": {"numerator": s.security_num, "denominator": s.security_den},
            "pass_count": s.pass_count, "fail_count": s.fail_count,
            "unknown_count": s.unknown_count, "not_applicable_count": s.na_count,
            "severity_counts": dict(s.severity_counts),
        },
        "findings": [_finding_to_dict(f) for f in findings],
        "emergent_findings": [_finding_to_dict(f) for f in emergent],
        "unassessed": [
            {"control_ids": list(u.control_ids), "cause": u.cause, "resolution": u.resolution}
            for u in data.unassessed
        ],
        "knowledge_base": {
            "engine": data.knowledge_base.engine,
            "rulepack": {
                "id": data.knowledge_base.rulepack_id, "version": data.knowledge_base.rulepack_version,
                "trust_tier": data.knowledge_base.rulepack_trust_tier,
            },
            "control_pack": {
                "id": data.knowledge_base.control_pack_id, "version": data.knowledge_base.control_pack_version,
            },
            "frameworks": [{"label": lbl, "version": v} for lbl, v in data.knowledge_base.frameworks],
            "schema_registry": data.knowledge_base.schema_registry,
        },
        "report_hash": data.report_hash,
    }
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False, default=str).encode("utf-8")


def to_csv(data: DeviceReportData, *, mode: str = "issued") -> bytes:
    """TRD-09.1 §3.9: "Flattened for ticketing; evidence referenced, not
    embedded" — the evidence column carries `artifact:line-line`, not the
    excerpt text itself."""

    findings = _eligible(data.findings, mode)
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow([
        "finding_id", "control_id", "title", "verdict", "severity_base", "severity_effective",
        "frameworks", "evidence_reference", "remediation_ref",
    ])
    for f in findings:
        line_ref = ""
        if f.artifact_filename and f.evidence_lines:
            nums = [el.number for el in f.evidence_lines]
            line_ref = f"{f.artifact_filename}:{min(nums)}-{max(nums)}"
        writer.writerow([
            f.finding_id, f.control_id, f.title, f.verdict, f.severity_base, f.severity_effective,
            "|".join(f.frameworks), line_ref, f.remediation_ref or "",
        ])
    return buf.getvalue().encode("utf-8")


_OSCAL_STATE = {"PASS": "satisfied", "PASS_PARTIAL": "satisfied", "FAIL": "not-satisfied"}


def to_oscal(data: DeviceReportData, *, mode: str = "issued") -> bytes:
    """NIST OSCAL assessment-results, compliance-derived results only
    (TRD-06.1 DD-06.1-04, V-09.1-009). UNKNOWN/NOT_APPLICABLE findings are
    not compliance-determined results and are omitted from `findings[]`
    (documented, not silently dropped — see module docstring); the
    security-posture score is never written here at all."""

    findings = _eligible(data.findings, mode)
    result_uuid = str(uuid.uuid5(_OSCAL_NAMESPACE, f"result:{data.report_id}"))
    ar_uuid = str(uuid.uuid5(_OSCAL_NAMESPACE, f"assessment-results:{data.report_id}"))

    oscal_findings = []
    for f in findings:
        state = _OSCAL_STATE.get(f.verdict)
        if state is None:
            continue
        finding_uuid = str(uuid.uuid5(_OSCAL_NAMESPACE, f"finding:{data.report_id}:{f.finding_id}"))
        oscal_findings.append({
            "uuid": finding_uuid,
            "title": f.title,
            "description": f.title,
            "target": {
                "target-id": f.control_id,
                "type": "objective-id",
                "status": {"state": state},
            },
            "related-observations": [],
        })

    obj = {
        "assessment-results": {
            "uuid": ar_uuid,
            "metadata": {
                "title": f"NSCA Compliance Assessment Results — {data.device.hostname}",
                "last-modified": data.generated_at,
                "version": "1.0",
                "oscal-version": "1.1.2",
            },
            "results": [
                {
                    "uuid": result_uuid,
                    "title": f"{data.campaign.name} — {data.device.hostname}",
                    "description": "Compliance-derived results only; security posture is excluded.",
                    "start": data.campaign.assessed_at,
                    "reviewed-controls": {
                        "control-selections": [{"include-all": {}}],
                    },
                    "findings": oscal_findings,
                }
            ],
        }
    }
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False, default=str).encode("utf-8")
