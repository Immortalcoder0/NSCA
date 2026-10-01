"""Shared document model — TRD-09.1 §3.2, backend-02 §4.6, M4.

Built **first**, before any renderer (backend-02 §4.6: "build
`document_model.py` first as a pure data-transform ... then two thin
renderers"). `build_device_report_document` is a pure function:
`(DeviceReportData) -> Document`. It reads no clock, no filesystem, no
network — `generated_at` is always a field on the input data, carried
through unchanged (TRD-09.1 §3.7: "Timestamps in output ... Generation time
is an input, recorded once, rendered from the stored value").

**INV-09.1-01 — rendering computes nothing.** Every field on `Document`
traces directly to a field already present on `DeviceReportData`. This
module does no scoring, no severity computation, no verdict logic — those
belong upstream (the assessment worker, §3 of backend-02), because a
renderer that computes can drift from the engine that computed
(TRD-09.1 §3.1).

**Section order is 10-reporting.md §2's own eight sections, in the doc's own
order** — Section 1 (cover/identification) and Section 6 (Unassessed) are
called out in backend-02 §4.6 as the two competing tools are least likely to
have; both are built here, not deferred.

**Exclusion rule (INV-09.1-02 / task item 13).** `mode="issued"` filters
every finding through `learning.ratification.is_report_eligible` before any
block is built — provisional-rulepack findings never reach the document
model in issued mode, and there is no parameter that overrides this
(matching TRD-09.1's "there is no parameter that overrides this" verbatim).
`mode="draft"` includes them, each flagged with a `PROVISIONAL` marker on
its `FindingRecord`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Union

from nsca_platform.learning.ratification import is_report_eligible

# ---------------------------------------------------------------------------
# Document tree — TRD-09.1 §3.2's `Document { sections[]: {id, title,
# blocks[]} }`
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Heading:
    level: int
    text: str


@dataclass(frozen=True, slots=True)
class Paragraph:
    text: str
    kind: str = "body"  # body | warning | caveat


@dataclass(frozen=True, slots=True)
class TableRow:
    cells: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Table:
    headers: tuple[str, ...]
    rows: tuple[TableRow, ...]


@dataclass(frozen=True, slots=True)
class EvidenceLine:
    number: int
    text: str
    highlighted: bool = False
    masked: bool = False


@dataclass(frozen=True, slots=True)
class EvidenceExcerpt:
    """TRD-09.1 §3.5's evidence-rendering obligations: verbatim text, line
    numbers, highlight, masking-indicated. `lines` are already
    normalised/masked by the caller (§3.5 DD-09.1-02: masking applied at
    render, from declared credential positions — the *caller* of this
    builder resolves that; this dataclass just carries the already-resolved
    text so the model stays a pure transform of its input)."""

    artifact_filename: str
    lines: tuple[EvidenceLine, ...]
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class SeverityIndicator:
    """NFR-USE-006: "Severity never by colour alone" — glyph + label + hue,
    never hue alone. `glyph` is plain text so monochrome rendering still
    distinguishes states (V-09.1-006)."""

    severity: str  # critical | high | medium | low | info
    glyph: str
    label: str


@dataclass(frozen=True, slots=True)
class ChartBar:
    label: str
    value: int
    total: int
    fill_glyph: str = "#"
    empty_glyph: str = "."


@dataclass(frozen=True, slots=True)
class Chart:
    title: str
    bars: tuple[ChartBar, ...]


@dataclass(frozen=True, slots=True)
class PlaybookStepBlock:
    id: int
    control_id: str
    command: str
    impact: str
    reason: str | None
    requires_verified: bool
    rollback: str | None
    rollback_incomplete: bool
    blocked: bool
    blocked_reason: str | None
    addresses_findings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CheckpointBlock:
    after_step: int | None
    instruction: str


@dataclass(frozen=True, slots=True)
class LockoutBlock:
    result: str
    operator_source: str | None
    reason: str
    method: str


@dataclass(frozen=True, slots=True)
class DryRunBlock:
    before_compliance_num: int
    before_compliance_den: int
    after_compliance_num: int
    after_compliance_den: int
    coverage_unchanged: bool
    resolved: tuple[str, ...]
    newly_failing: tuple[tuple[str, str], ...]  # (control_id, reason)
    fidelity_note: str


@dataclass(frozen=True, slots=True)
class Playbook:
    steps: tuple[PlaybookStepBlock, ...]
    checkpoints: tuple[CheckpointBlock, ...]
    unavailable: tuple[tuple[str, str], ...]  # (control_id, reason)
    lockout: LockoutBlock | None
    dry_run: DryRunBlock | None


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    key: str
    value: str


@dataclass(frozen=True, slots=True)
class Manifest:
    report_id: str
    generated_at: str
    inputs: tuple[tuple[str, str], ...]  # (artifact filename, sha256)
    knowledge_base: tuple[ManifestEntry, ...]
    report_hash: str | None
    statement: str


Block = Union[
    Heading, Paragraph, Table, EvidenceExcerpt, SeverityIndicator, Chart, Playbook, Manifest,
]


@dataclass(frozen=True, slots=True)
class Section:
    id: str
    title: str
    blocks: tuple[Block, ...]


@dataclass(frozen=True, slots=True)
class Document:
    doc_type: str  # "device_report" | "estate_report"
    device_hostname: str | None
    generated_at: str
    mode: str  # draft | issued
    sections: tuple[Section, ...]


# ---------------------------------------------------------------------------
# Input model — `(DeviceAssessment, CampaignAssessment, findings, remediation
# plans)` reduced to plain, renderer-agnostic data (backend-02 §4.6). Every
# field here must already be a *stored* value (RPT-2 / INV-09.1-01) — never
# something the builder computes.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeviceIdentification:
    hostname: str
    model: str | None
    os_version: str | None
    serials: tuple[tuple[str, str], ...]  # (component, serial); empty -> NOT DETERMINED
    role: str | None = None
    exposure: str | None = None
    location: str | None = None


@dataclass(frozen=True, slots=True)
class CampaignInfo:
    name: str
    assessed_at: str
    assessor: str
    frameworks: tuple[tuple[str, str], ...]  # (name, version)


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    filename: str
    sha256: str
    export_mode: str = "unknown"
    collected_at: str | None = None
    received_from: str | None = None


@dataclass(frozen=True, slots=True)
class ScoreSummary:
    compliance_num: int
    compliance_den: int
    coverage_num: int
    coverage_den: int
    meaningful_num: int
    meaningful_den: int
    security_num: int
    security_den: int
    pass_count: int
    fail_count: int
    unknown_count: int
    na_count: int
    severity_counts: Mapping[str, int]  # critical/high/medium/low


@dataclass(frozen=True, slots=True)
class TopRemediation:
    rank: int
    finding_id: str
    title: str
    step_count: int
    impact: str


@dataclass(frozen=True, slots=True)
class RawEvidenceLine:
    number: int
    text: str
    highlighted: bool = False
    masked: bool = False


@dataclass(frozen=True, slots=True)
class FrameworkConflict:
    device_value: str
    requirements: tuple[tuple[str, str, str], ...]  # (framework_ref, requirement, outcome)
    applied: str
    applied_reason: str


@dataclass(frozen=True, slots=True)
class FindingRecord:
    finding_id: str
    control_id: str
    title: str
    verdict: str
    severity_base: str
    severity_effective: str
    severity_reason: str | None
    frameworks: tuple[str, ...]
    artifact_filename: str | None
    evidence_lines: tuple[RawEvidenceLine, ...]
    facts: tuple[str, ...]
    impact_text: str | None = None
    remediation_ref: str | None = None
    is_emergent: bool = False
    counterexample: tuple[str, ...] = ()
    contributing_devices: tuple[str, ...] = ()
    framework_conflict: FrameworkConflict | None = None
    attack_path_note: str | None = None
    # M3 exclusion-gate inputs (INV-08.3-04 / DM-5) — is_report_eligible's
    # two arguments, carried on every finding so the builder can enforce
    # the gate itself rather than trusting the caller already filtered.
    rule_status: str = "ratified"
    rulepack_trust_tier: str | None = None
    # Phase 3 demo rehearsal fix (finding 11, §9 checklist item 11): an
    # absence-based finding (its deciding fact's provenance is
    # `default_known`/`default_unknown`/`derived`-from-absence, not
    # `explicit`) has a real artifact citation but genuinely no line number
    # to highlight — `evidence_lines` stays empty for it (never a
    # fabricated line), which used to mean `_finding_blocks` rendered
    # *nothing* evidentiary at all for this whole class of finding, even
    # though `artifact_filename` was already being carried. This one extra
    # field is the fact-checked "we looked in ART-XXX and found nothing"
    # excerpt text (`extract/provenance.py::classify_absent`'s new
    # `excerpt`, surfaced through `report_service._finding_row_to_record`)
    # — rendered as a plain citation line instead of the line-highlighted
    # `EvidenceExcerpt` block, since there are no lines to highlight.
    evidence_note: str | None = None


@dataclass(frozen=True, slots=True)
class UnassessedItem:
    control_ids: tuple[str, ...]
    cause: str
    resolution: str | None = None


@dataclass(frozen=True, slots=True)
class UnauditedCapability:
    description: str
    properties: tuple[str, ...]
    downgraded_controls: int


@dataclass(frozen=True, slots=True)
class AssessorNote:
    date: str
    author: str
    text: str


@dataclass(frozen=True, slots=True)
class KnowledgeBaseVersions:
    engine: str
    rulepack_id: str
    rulepack_version: str
    rulepack_trust_tier: str
    control_pack_id: str
    control_pack_version: str
    frameworks: tuple[tuple[str, str], ...]  # (label, version)
    schema_registry: str


@dataclass(frozen=True, slots=True)
class RemediationPlanView:
    steps: tuple[PlaybookStepBlock, ...]
    checkpoints: tuple[CheckpointBlock, ...]
    unavailable: tuple[tuple[str, str], ...]
    lockout: LockoutBlock | None
    dry_run: DryRunBlock | None


@dataclass(frozen=True, slots=True)
class DeviceReportData:
    report_id: str
    device: DeviceIdentification
    campaign: CampaignInfo
    inputs: tuple[ArtifactRef, ...]
    scores: ScoreSummary
    top_remediations: tuple[TopRemediation, ...]
    findings: tuple[FindingRecord, ...]
    emergent_findings: tuple[FindingRecord, ...]
    remediation_plan: RemediationPlanView | None
    unassessed: tuple[UnassessedItem, ...]
    unaudited_capabilities: tuple[UnauditedCapability, ...]
    assessor_notes: tuple[AssessorNote, ...]
    fact_count: int
    control_count: int
    knowledge_base: KnowledgeBaseVersions
    generated_at: str
    report_hash: str | None = None


# ---------------------------------------------------------------------------
# Ratio rendering — D5: integer pairs only, never float (TRD-10.1 §4.1)
# ---------------------------------------------------------------------------


def render_ratio(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "N/A"
    # Deterministic truncating integer percentage — no banker's rounding,
    # no float division (D5).
    pct = (numerator * 100) // denominator
    return f"{pct}%"


_SEVERITY_GLYPHS = {
    "critical": "!!", "high": "!", "medium": "~", "low": "-", "info": ".",
}


def _severity_indicator(severity: str) -> SeverityIndicator:
    sev = severity.lower()
    return SeverityIndicator(severity=sev, glyph=_SEVERITY_GLYPHS.get(sev, "?"), label=sev.upper())


# ---------------------------------------------------------------------------
# Builder — the pure transform
# ---------------------------------------------------------------------------


def _filter_eligible(findings: tuple[FindingRecord, ...], mode: str) -> tuple[FindingRecord, ...]:
    """INV-09.1-02: enforced in the generator, not the caller. `mode ==
    "draft"` keeps provisional findings (flagged in their block); `mode ==
    "issued"` drops them unconditionally — no parameter overrides this."""

    if mode != "issued":
        return findings
    return tuple(f for f in findings if is_report_eligible(f.rule_status, f.rulepack_trust_tier))


def _build_cover_section(data: DeviceReportData, mode: str) -> Section:
    d, c = data.device, data.campaign
    blocks: list[Block] = [Heading(level=1, text="NETWORK SECURITY COMPLIANCE AUDIT REPORT")]
    blocks.append(Heading(level=2, text=d.hostname))
    model_line = " · ".join(x for x in (d.model, d.os_version) if x)
    if model_line:
        blocks.append(Paragraph(model_line))

    if d.serials:
        blocks.append(Table(headers=("Component", "Serial"), rows=tuple(TableRow(cells=(comp, sn)) for comp, sn in d.serials)))
    else:
        # INV-09.1-03 / FR-RPT-003: never omitted, always states the gap.
        blocks.append(
            Paragraph(
                "Serial numbers       NOT DETERMINED — `show inventory` output was not "
                "supplied for this device. Supply it to complete device identification.",
                kind="warning",
            )
        )

    identity_rows = []
    if d.role:
        identity_rows.append(TableRow(cells=("Role", d.role)))
    identity_rows.append(TableRow(cells=("Exposure", d.exposure or "NOT DETERMINED (derived from topology)")))
    if d.location:
        identity_rows.append(TableRow(cells=("Location", d.location)))
    identity_rows.append(TableRow(cells=("Campaign", c.name)))
    identity_rows.append(TableRow(cells=("Assessed", c.assessed_at)))
    identity_rows.append(TableRow(cells=("Assessor", c.assessor)))
    blocks.append(Table(headers=("Field", "Value"), rows=tuple(identity_rows)))

    if c.frameworks:
        blocks.append(
            Table(
                headers=("Framework", "Version"),
                rows=tuple(TableRow(cells=(name, ver)) for name, ver in c.frameworks),
            )
        )

    input_rows = [
        TableRow(cells=(a.filename, f"sha256:{a.sha256}", a.export_mode)) for a in data.inputs
    ]
    if input_rows:
        blocks.append(Table(headers=("Configuration source", "Hash", "Export mode"), rows=tuple(input_rows)))

    kb = data.knowledge_base
    blocks.append(
        Paragraph(
            f"Engine {kb.engine} · Rulepack {kb.rulepack_id}@{kb.rulepack_version} "
            f"({kb.rulepack_trust_tier}) · Report hash {data.report_hash or 'PENDING'}"
        )
    )
    if mode == "draft":
        blocks.insert(1, Paragraph("DRAFT — not issued. May include provisional content, flagged below.", kind="warning"))
    return Section(id="cover", title="Cover and identification", blocks=tuple(blocks))


def _build_executive_summary(data: DeviceReportData) -> Section:
    s = data.scores
    blocks: list[Block] = [Heading(level=2, text="COMPLIANCE POSTURE")]
    blocks.append(
        Table(
            headers=("Metric", "Value", "Detail"),
            rows=(
                TableRow(("Compliance", render_ratio(s.compliance_num, s.compliance_den),
                          f"{s.compliance_num} pass / {s.compliance_den} determined")),
                TableRow(("Coverage", render_ratio(s.coverage_num, s.coverage_den),
                          f"{s.coverage_num} determined / {s.coverage_den} applicable")),
                TableRow(("Meaningful passes", render_ratio(s.meaningful_num, s.meaningful_den),
                          f"{s.meaningful_num} of {s.meaningful_den} configured")),
                TableRow(("Security posture", render_ratio(s.security_num, s.security_den),
                          "compliance adjusted for exposure, vulnerabilities, unaudited surface")),
            ),
        )
    )
    total = s.pass_count + s.fail_count + s.unknown_count + s.na_count
    blocks.append(
        Chart(
            title="Verdict distribution",
            bars=(
                ChartBar("PASS", s.pass_count, total),
                ChartBar("FAIL", s.fail_count, total),
                ChartBar("UNKNOWN", s.unknown_count, total),
                ChartBar("N/A", s.na_count, total),
            ),
        )
    )
    blocks.append(
        Table(
            headers=("Severity", "Count"),
            rows=tuple(TableRow((sev.upper(), str(cnt))) for sev, cnt in sorted(s.severity_counts.items())),
        )
    )
    if data.top_remediations:
        blocks.append(Heading(level=3, text="TOP PRIORITY REMEDIATIONS"))
        blocks.append(Paragraph("Ranked by attack-path contribution, not by severity label."))
        blocks.append(
            Table(
                headers=("Rank", "Finding", "Title", "Steps", "Impact"),
                rows=tuple(
                    TableRow((str(t.rank), t.finding_id, t.title, str(t.step_count), t.impact))
                    for t in data.top_remediations
                ),
            )
        )
    return Section(id="executive_summary", title="Executive summary", blocks=tuple(blocks))


def _finding_blocks(f: FindingRecord) -> list[Block]:
    blocks: list[Block] = [
        Heading(level=3, text=f"{f.control_id}    {f.title}"),
        _severity_indicator(f.severity_effective if f.verdict == "FAIL" else f.severity_base),
        Paragraph(f"Verdict: {f.verdict}"),
    ]
    if f.rule_status != "ratified":
        blocks.append(Paragraph(f"PROVISIONAL — derived from a {f.rule_status} rule; not evidence.", kind="warning"))
    if f.severity_reason:
        blocks.append(Paragraph(f"Severity: {f.severity_base} -> {f.severity_effective}. {f.severity_reason}"))
    if f.frameworks:
        blocks.append(Paragraph("Frameworks " + " · ".join(f.frameworks)))
    if f.is_emergent:
        blocks.append(Paragraph(
            "No individual configuration statement on any device involved is non-compliant. "
            "This violation is emergent from the combination.", kind="warning",
        ))
        if f.counterexample:
            blocks.append(Paragraph("COUNTEREXAMPLE\n" + "\n".join(f.counterexample)))
        if f.contributing_devices:
            blocks.append(Paragraph("Contributing devices: " + " · ".join(f.contributing_devices)))
    elif f.evidence_lines:
        blocks.append(
            EvidenceExcerpt(
                artifact_filename=f.artifact_filename or "unknown",
                lines=tuple(
                    EvidenceLine(number=el.number, text=el.text, highlighted=el.highlighted, masked=el.masked)
                    for el in f.evidence_lines
                ),
            )
        )
    elif f.artifact_filename and f.evidence_note:
        # Absence-based citation: a real artifact was consulted and
        # genuinely contained no matching construct/line — honest, not
        # fabricated (see FindingRecord.evidence_note docstring above).
        blocks.append(Paragraph(f"Evidence: {f.artifact_filename} — {f.evidence_note}"))
    if f.facts:
        blocks.append(Paragraph("Facts: " + " · ".join(f.facts)))
    if f.framework_conflict:
        fc = f.framework_conflict
        blocks.append(
            Table(
                headers=("Framework", "Requirement", "Outcome"),
                rows=tuple(TableRow(r) for r in fc.requirements),
            )
        )
        blocks.append(Paragraph(f"Applied: {fc.applied} ({fc.applied_reason})", kind="warning"))
    if f.impact_text:
        blocks.append(Paragraph(f"IMPACT: {f.impact_text}"))
    if f.attack_path_note:
        blocks.append(Paragraph(f.attack_path_note))
    if f.remediation_ref:
        blocks.append(Paragraph(f"REMEDIATION -> see {f.remediation_ref}, Section 5"))
    return blocks


def _build_findings_section(findings: tuple[FindingRecord, ...]) -> Section:
    blocks: list[Block] = []
    for f in findings:
        blocks.extend(_finding_blocks(f))
    return Section(id="findings", title="Findings", blocks=tuple(blocks))


def _build_emergent_section(findings: tuple[FindingRecord, ...]) -> Section:
    blocks: list[Block] = []
    for f in findings:
        blocks.extend(_finding_blocks(f))
    return Section(id="emergent_findings", title="Emergent findings", blocks=tuple(blocks))


def _build_playbook_block(rp: RemediationPlanView | None) -> Playbook | None:
    if rp is None:
        return None
    return Playbook(
        steps=rp.steps, checkpoints=rp.checkpoints, unavailable=rp.unavailable,
        lockout=rp.lockout, dry_run=rp.dry_run,
    )


def _build_remediation_section(data: DeviceReportData) -> Section:
    blocks: list[Block] = [
        Heading(level=2, text=f"REMEDIATION PLAYBOOK — Target: {data.device.hostname}"),
        Paragraph("Commands below are specific to this model and software version."),
    ]
    pb = _build_playbook_block(data.remediation_plan)
    if pb is not None:
        blocks.append(pb)
    else:
        blocks.append(Paragraph("No remediation plan has been generated for this device."))
    return Section(id="remediation", title="Remediation playbook", blocks=tuple(blocks))


def _build_unassessed_section(data: DeviceReportData) -> Section:
    total_unassessed = sum(len(u.control_ids) for u in data.unassessed)
    pct = render_ratio(total_unassessed, data.control_count) if data.control_count else "N/A"
    blocks: list[Block] = [
        Heading(level=2, text="UNASSESSED"),
        Paragraph(f"{total_unassessed} controls could not be determined ({pct} of applicable controls)."),
    ]
    for u in data.unassessed:
        text = f"{len(u.control_ids)} — {u.cause}" + (f" -> {u.resolution}" if u.resolution else "")
        blocks.append(Paragraph(text))
        blocks.append(Table(headers=("Control",), rows=tuple(TableRow((cid,)) for cid in u.control_ids)))

    if data.unaudited_capabilities:
        blocks.append(Heading(level=3, text="UNAUDITED CAPABILITIES"))
        for uc in data.unaudited_capabilities:
            blocks.append(Paragraph(uc.description))
            if uc.properties:
                blocks.append(Paragraph("Properties observed: " + " · ".join(uc.properties)))
            blocks.append(Paragraph(f"-> {uc.downgraded_controls} controls downgraded to PASS (PARTIAL)"))

    blocks.append(
        Paragraph(
            f"COVERAGE STATEMENT — This assessment determined "
            f"{render_ratio(data.scores.coverage_num, data.scores.coverage_den)} of applicable controls. "
            f"It is not a statement that the remainder are compliant. An unexamined control is not a "
            f"passing control.",
            kind="warning",
        )
    )
    return Section(id="unassessed", title="Unassessed", blocks=tuple(blocks))


def _build_assessor_notes_section(notes: tuple[AssessorNote, ...]) -> Section:
    blocks: list[Block] = [
        Paragraph(f"{n.date}  {n.author}\n  {n.text}") for n in notes
    ]
    return Section(id="assessor_notes", title="Assessor notes", blocks=tuple(blocks))


def _build_appendix_section(data: DeviceReportData) -> Section:
    kb = data.knowledge_base
    blocks: list[Block] = [
        Paragraph(f"A · Complete fact inventory with provenance ({data.fact_count} facts)"),
        Paragraph(f"B · Control results in full ({data.control_count} controls)"),
        Heading(level=3, text="C · Knowledge base versions"),
        Table(
            headers=("Component", "Version"),
            rows=(
                TableRow(("engine", kb.engine)),
                TableRow(("rulepack", f"{kb.rulepack_id}@{kb.rulepack_version} ({kb.rulepack_trust_tier})")),
                TableRow(("control pack", f"{kb.control_pack_id}@{kb.control_pack_version}")),
                *(TableRow((label, ver)) for label, ver in kb.frameworks),
                TableRow(("schema registry", kb.schema_registry)),
            ),
        ),
        Paragraph("D · Chain of custody — see reproducibility manifest"),
    ]
    manifest = Manifest(
        report_id=data.report_id,
        generated_at=data.generated_at,
        inputs=tuple((a.filename, a.sha256) for a in data.inputs),
        knowledge_base=(
            ManifestEntry("engine", kb.engine),
            ManifestEntry("rulepack", f"{kb.rulepack_id}@{kb.rulepack_version}"),
            ManifestEntry("control_pack", f"{kb.control_pack_id}@{kb.control_pack_version}"),
            *(ManifestEntry(label, ver) for label, ver in kb.frameworks),
            ManifestEntry("schema_registry", kb.schema_registry),
        ),
        report_hash=data.report_hash,
        statement=(
            "Re-executing with identical inputs and knowledge base versions will "
            "produce a byte-identical report."
        ),
    )
    blocks.append(Heading(level=3, text="E · Reproducibility manifest"))
    blocks.append(manifest)
    return Section(id="appendix", title="Appendix", blocks=tuple(blocks))


def remediation_plan_to_view(
    plan: Any, lockout_analysis: Any | None, dry_run_result: Any | None
) -> RemediationPlanView:
    """Adapter: `remediation.planner.RemediationPlan` (+ optional
    `remediation.lockout.LockoutAnalysis` / `remediation.dry_run.DryRunResult`)
    -> `RemediationPlanView`, the document model's own, renderer-facing
    shape. Kept here (not in `remediation/`) because it is a pure data
    transform belonging to the document model, exactly like every other
    `_build_*` function in this module — `remediation/` itself has no
    dependency on `reporting/` (one-directional: reporting depends on
    remediation output, never the reverse)."""

    steps = tuple(
        PlaybookStepBlock(
            id=s.id, control_id=s.control_id, command=s.command, impact=s.impact,
            reason=s.reason, requires_verified=s.requires_verified, rollback=s.rollback,
            rollback_incomplete=s.rollback_incomplete, blocked=s.blocked,
            blocked_reason=s.blocked_reason, addresses_findings=s.addresses_findings,
        )
        for s in plan.steps
    )
    checkpoints = tuple(
        CheckpointBlock(after_step=c.after_step, instruction=c.instruction) for c in plan.checkpoints
    )
    unavailable = tuple((u.control_id, u.reason) for u in plan.unavailable)
    lockout_block = None
    if lockout_analysis is not None:
        lockout_block = LockoutBlock(
            result=lockout_analysis.result, operator_source=lockout_analysis.operator_source,
            reason=lockout_analysis.reason, method=lockout_analysis.method,
        )
    dry_run_block = None
    if dry_run_result is not None:
        dry_run_block = DryRunBlock(
            before_compliance_num=dry_run_result.before_pass,
            before_compliance_den=dry_run_result.before_determined,
            after_compliance_num=dry_run_result.after_pass,
            after_compliance_den=dry_run_result.after_determined,
            coverage_unchanged=dry_run_result.coverage_unchanged,
            resolved=dry_run_result.resolved,
            newly_failing=tuple((n.control_id, n.reason) for n in dry_run_result.newly_failing),
            fidelity_note=dry_run_result.fidelity_note,
        )
    return RemediationPlanView(
        steps=steps, checkpoints=checkpoints, unavailable=unavailable,
        lockout=lockout_block, dry_run=dry_run_block,
    )


def build_device_report_document(data: DeviceReportData, *, mode: str = "issued") -> Document:
    """The pure transform. `mode` is `"draft"` or `"issued"` (TRD-09.1 §4).
    Enforces INV-09.1-02 (provisional exclusion) itself — see module
    docstring."""

    if mode not in ("draft", "issued"):
        raise ValueError(f"mode must be 'draft' or 'issued', got {mode!r}")

    eligible_findings = _filter_eligible(data.findings, mode)
    eligible_emergent = _filter_eligible(data.emergent_findings, mode)

    sections = (
        _build_cover_section(data, mode),
        _build_executive_summary(data),
        _build_findings_section(eligible_findings),
        _build_emergent_section(eligible_emergent),
        _build_remediation_section(data),
        _build_unassessed_section(data),
        _build_assessor_notes_section(data.assessor_notes),
        _build_appendix_section(data),
    )
    return Document(
        doc_type="device_report", device_hostname=data.device.hostname,
        generated_at=data.generated_at, mode=mode, sections=sections,
    )
