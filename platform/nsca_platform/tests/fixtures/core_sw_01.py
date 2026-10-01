"""CORE-SW-01 — 10-reporting.md §2's worked example, reproduced as a
`DeviceReportData` fixture. This is M4's primary acceptance fixture
(backend-02 §5 M4: "the CORE-SW-01 report example in 10-reporting.md §2 is
reproduced byte-for-byte across two separate generation runs").

Every number below is taken directly from the doc's own ASCII-art example
(serials, compliance/coverage/meaningful/security percentages, severity
counts, the five top remediations, the NSCA-MGMT-002 finding with its
evidence excerpt, the NSCA-MGMT-004 framework-conflict example, the
NSCA-GRAPH-004 emergent finding, the unassessed/unaudited breakdown, the two
assessor notes, and the reproducibility manifest's report_id/hash/
timestamps) — not invented. The remediation playbook (section 5) is instead
*generated* by this milestone's real `remediation.planner`/`lockout`/
`dry_run` modules against a fact set consistent with the doc's own
NSCA-MGMT-002/NSCA-AUTH-001/NSCA-AUTH-002/NSCA-MGMT-005 findings, rather
than hand-typed, so the acceptance fixture exercises the real subsystem
end to end.
"""

from __future__ import annotations

from datetime import datetime, timezone

from nsca_platform.remediation import dry_run as dryrun_mod
from nsca_platform.remediation import lockout as lockout_mod
from nsca_platform.remediation import planner as planner_mod
from nsca_platform.reporting.document_model import (
    ArtifactRef,
    AssessorNote,
    CampaignInfo,
    DeviceIdentification,
    DeviceReportData,
    FindingRecord,
    FrameworkConflict,
    KnowledgeBaseVersions,
    RawEvidenceLine,
    ScoreSummary,
    TopRemediation,
    UnassessedItem,
    UnauditedCapability,
    remediation_plan_to_view,
)

GENERATED_AT_DT = datetime(2026, 9, 12, 14, 22, 31, tzinfo=timezone.utc)
GENERATED_AT = "2026-09-12T14:22:31Z"
REPORT_ID = "RPT-2026Q3-CORE-SW-01-001"
REPORT_HASH = "9a41c7f2e" + "0" * 55  # placeholder-shaped 64-hex-char stand-in, deterministic either way

_FACTS = {
    "mgmt.protocols.telnet.enabled": True,
    "mgmt.protocols.http.enabled": True,
    "mgmt.protocols.ssh.enabled": True,
    "auth.local_users": [{"username": "admin", "privilege_level": 15, "reversible": True}],
    "auth.central.configured": False,
    "mgmt.source_restriction.configured": False,
}

_PLAYBOOK_FINDINGS = [
    {"id": "F-000412", "control": "NSCA-MGMT-002", "verdict": "FAIL"},
    {"id": "F-000603", "control": "NSCA-AUTH-001", "verdict": "FAIL"},
    {"id": "F-000604", "control": "NSCA-AUTH-002", "verdict": "FAIL"},
    {"id": "F-000518", "control": "NSCA-MGMT-005", "verdict": "FAIL"},
    {"id": "F-000700", "control": "NSCA-AUTH-003", "verdict": "PASS"},
]


def _build_remediation_view():
    library = planner_mod.load_remediation_library()
    plan = planner_mod.plan(
        _PLAYBOOK_FINDINGS, device_id="CORE-SW-01", platform="cisco_iosxe", os_version="16.12.04",
        facts=_FACTS, library=library, operator_source="10.20.5.44",
    )
    modelled = dryrun_mod.apply_remediation_to_facts(_FACTS, plan)
    lock = lockout_mod.check_lockout(plan, modelled, operator_source="10.20.5.44")
    plan = lockout_mod.apply_lockout_blocking(plan, lock)
    dr = dryrun_mod.dry_run(_PLAYBOOK_FINDINGS, _FACTS, plan, library=library)
    return remediation_plan_to_view(plan, lock, dr)


def build_core_sw_01() -> DeviceReportData:
    device = DeviceIdentification(
        hostname="CORE-SW-01",
        model="Cisco Catalyst 9300-48P",
        os_version="IOS-XE 16.12.04",
        serials=(
            ("Chassis", "FCW2140L0GH"),
            ("Line card 1", "FOC2138Y0K2"),
            ("Line card 2", "FOC2138Y0M9"),
            ("Power supply 1", "ART2137F0PL"),
        ),
        role="Distribution switch",
        exposure="Internal",
        location="DC-Mumbai / Rack B12",
    )
    campaign = CampaignInfo(
        name="Q3-2026 Core Infrastructure Audit",
        assessed_at="12 September 2026, 14:22 IST",
        assessor="P. Sharma, Lead Assessor",
        frameworks=(
            ("CIS Cisco IOS Benchmark", "v4.1.0"),
            ("NIST SP 800-53", "Rev 5"),
            ("DISA STIG Cisco IOS-XE Router", "2026-01 (Rel 13)"),
            ("ISO/IEC 27001", "2022"),
        ),
    )
    inputs = (
        ArtifactRef("running-config.txt", "3f9a" + "0" * 60 + "c21b", export_mode="verbose",
                     collected_at="2026-09-11", received_from="live_collection"),
        ArtifactRef("show-version.txt", "7c04" + "0" * 60 + "19af", export_mode="verbose"),
        ArtifactRef("show-inventory.txt", "e281" + "0" * 60 + "b30c", export_mode="verbose"),
    )
    scores = ScoreSummary(
        compliance_num=112, compliance_den=143,
        coverage_num=143, coverage_den=155,
        meaningful_num=72, meaningful_den=112,
        security_num=61, security_den=100,
        pass_count=112, fail_count=31, unknown_count=12, na_count=14,
        severity_counts={"critical": 3, "high": 11, "medium": 14, "low": 3},
    )
    top_remediations = (
        TopRemediation(1, "F-000518", "Remove 0.0.0.0/0 from group `Partners`", 1, "safe"),
        TopRemediation(2, "F-000412", "Disable Telnet on VTY lines", 3, "lockout_risk"),
        TopRemediation(3, "F-000603", "Replace type 7 credential", 2, "service_affecting"),
        TopRemediation(4, "F-000701", "Configure remote logging", 2, "safe"),
        TopRemediation(5, "F-000455", "Set session idle timeout", 2, "safe"),
    )

    mgmt_002 = FindingRecord(
        finding_id="F-000412", control_id="NSCA-MGMT-002",
        title="Plaintext management protocols must be disabled",
        verdict="FAIL", severity_base="high", severity_effective="critical",
        severity_reason="Elevated: this device terminates an external circuit",
        frameworks=("CIS-IOS-1.2.4", "NIST AC-17", "NIST SC-8", "STIG V-216644 (CAT I)", "ISO 27001 A.9.4.2"),
        artifact_filename="running-config.txt",
        evidence_lines=(
            RawEvidenceLine(141, "line vty 0 4"),
            RawEvidenceLine(142, " login local"),
            RawEvidenceLine(143, " transport input telnet ssh", highlighted=True),
            RawEvidenceLine(144, " exec-timeout 0 0"),
            RawEvidenceLine(145, "!"),
        ),
        facts=("mgmt.protocols.telnet.enabled = true (source: explicit, "
               "extractor: cisco_iosxe.vty.transport_input@7)",),
        impact_text=(
            "Credentials transit the network in cleartext. Any party able to observe traffic "
            "between the management station and this device obtains privilege-15 credentials."
        ),
        remediation_ref="R-000412",
        attack_path_note="This finding is an enabling link in attack path AP-003.",
    )
    mgmt_004 = FindingRecord(
        finding_id="F-000455", control_id="NSCA-MGMT-004", title="Session idle timeout",
        verdict="FAIL", severity_base="medium", severity_effective="medium", severity_reason=None,
        frameworks=("CIS-IOS-1.1.5", "STIG V-216620"),
        artifact_filename=None, evidence_lines=(), facts=("mgmt.session.idle_timeout_sec = 600",),
        framework_conflict=FrameworkConflict(
            device_value="600 s",
            requirements=(
                ("CIS-IOS-1.1.5", "<= 600 s", "PASS"),
                ("STIG V-216620", "<= 300 s", "FAIL"),
            ),
            applied="STIG (stricter)", applied_reason="applied to the stricter requirement",
        ),
    )

    graph_004 = FindingRecord(
        finding_id="F-000900", control_id="NSCA-GRAPH-004",
        title="Management plane reachable from untrusted zone",
        verdict="FAIL", severity_base="critical", severity_effective="critical", severity_reason=None,
        frameworks=(), artifact_filename=None, evidence_lines=(), facts=(),
        is_emergent=True,
        counterexample=(
            "203.0.113.5:44210 -> 10.0.0.1:22 TCP is permitted",
            "zone[external] -> EDGE-FW-01 interface Gi0/1 -> rule `outside-in` line 14 "
            "(EDGE-FW-01:1204) -> address group `Trusted-Admins` -> nested group `Partners` "
            "-> member 0.0.0.0/0 (over-broad) -> CORE-SW-01 interface Vlan1 -> management plane",
        ),
        contributing_devices=("EDGE-FW-01", "CORE-SW-01"),
    )

    unassessed = (
        UnassessedItem(
            control_ids=("NSCA-CRYPTO-003", "NSCA-CRYPTO-004"),
            cause=(
                "required facts absent, platform default unverified — this platform's cipher "
                "defaults are undocumented for IOS-XE 16.12. Explicit configuration would resolve this."
            ),
        ),
        UnassessedItem(
            control_ids=("NSCA-LOG-004", "NSCA-LOG-005", "NSCA-SNMP-004"),
            cause="configuration export incomplete — `show running-config` omits settings at default.",
            resolution="re-collect with `show running-config all`",
        ),
        UnassessedItem(
            control_ids=("NSCA-CRYPTO-005",),
            cause="parse gap — `crypto ikev2 policy` block not covered by any extractor.",
            resolution="queued for training",
        ),
    )
    unaudited = (
        UnauditedCapability(
            description="Embedded web management, TCP/8443. Outside the scope of all four selected frameworks.",
            properties=("listens", "authenticates", "mutates"),
            downgraded_controls=6,
        ),
    )
    notes = (
        AssessorNote(
            date="2026-09-19", author="p.sharma",
            text=(
                "Finding F-000418 disputed by r.kulkarni on grounds of network isolation. "
                "Compensating control REFUTED by platform verification — Gi0/8 bridges VLAN 250 "
                "and VLAN 40. Dispute rejected; finding stands."
            ),
        ),
        AssessorNote(
            date="2026-09-20", author="p.sharma",
            text=(
                "Finding F-000455 accepted as risk, expiring 2027-03-31. Legacy NMS dependency, "
                "replacement under project NET-2291."
            ),
        ),
    )
    kb = KnowledgeBaseVersions(
        engine="v2.4.0", rulepack_id="cisco_iosxe", rulepack_version="7.2.1",
        rulepack_trust_tier="Certified", control_pack_id="nsca-core", control_pack_version="3.1.0",
        frameworks=(
            ("CIS cisco_ios_15", "4.1.0"),
            ("STIG cisco_iosxe_router", "2026-01"),
            ("NIST 800-53", "Rev5"),
        ),
        schema_registry="v1.8.0",
    )

    return DeviceReportData(
        report_id=REPORT_ID, device=device, campaign=campaign, inputs=inputs, scores=scores,
        top_remediations=top_remediations,
        findings=(mgmt_002, mgmt_004),
        emergent_findings=(graph_004,),
        remediation_plan=_build_remediation_view(),
        unassessed=unassessed, unaudited_capabilities=unaudited, assessor_notes=notes,
        fact_count=84, control_count=155, knowledge_base=kb,
        generated_at=GENERATED_AT, report_hash=REPORT_HASH,
    )
