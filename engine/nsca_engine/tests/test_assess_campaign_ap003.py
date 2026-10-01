"""M4 acceptance test: the AP-003 example from
09-findings-lifecycle.md §11.2, reproduced end-to-end from raw artifacts
through `assess_device` (x2) -> `assess_campaign`, not from a hand-built
Graph.

    ATTACK PATH  AP-003
      External untrusted zone -> core management plane

      Link 1  F-000412  Telnet enabled on EDGE-FW-01          critical
      Link 2  F-000518  Over-broad group in outside-in ACL    high
      Link 3  F-000603  Reversible credential on CORE-SW-01    high

      Breaking any single link breaks the chain.
      Lowest-cost link: F-000518 - one command, impact: safe

See `risk/attack_paths.py`'s module docstring for the documented control-id
mapping this reproduction uses (NSCA-MGMT-002 = telnet, NSCA-MGMT-005 =
source-restriction/over-broad-group, NSCA-AUTH-001 = reversible credential)
and why link *order* here is derived from TRD-06.2 §3.4's enabling-category
ordering rather than the doc's own presentational order.
"""

from __future__ import annotations

from pathlib import Path

from nsca_engine.api import FindingKey, Severity, Verdict, assess_campaign, assess_device
from nsca_engine.tests.helpers import ASSESSED_AT, build_knowledge_base, make_artifact

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ap003"


def _assessments():
    kb = build_knowledge_base()
    edge = assess_device(
        (make_artifact((FIXTURES / "edge_fw_01.cfg").read_text(encoding="utf-8"), artifact_id="EDGE-FW-01"),),
        kb, ASSESSED_AT,
    )
    core = assess_device(
        (make_artifact((FIXTURES / "core_sw_01.cfg").read_text(encoding="utf-8"), artifact_id="CORE-SW-01"),),
        kb, ASSESSED_AT,
    )
    return kb, edge, core


def test_ap003_findings_present_on_the_two_devices():
    _, edge, core = _assessments()

    edge_by_control = {f.control_id: f for f in edge.findings}
    assert edge_by_control["NSCA-MGMT-002"].verdict == Verdict.FAIL  # telnet enabled
    assert edge_by_control["NSCA-MGMT-005"].verdict == Verdict.FAIL  # no source restriction

    core_by_control = {f.control_id: f for f in core.findings}
    assert core_by_control["NSCA-AUTH-001"].verdict == Verdict.FAIL  # reversible credential


def test_ap003_chain_reproduced_end_to_end():
    kb, edge, core = _assessments()
    campaign = assess_campaign((edge, core), kb)

    assert len(campaign.attack_paths) == 1
    path = campaign.attack_paths[0]

    links_in_path = {(step.device_id, step.rule_id) for step in path.steps}
    # The three AP-003 links must all be present. `NSCA-MGMT-005` (source
    # restriction) also legitimately fires on CORE-SW-01 — its
    # `mgmt.source_restriction.configured` default is unconditionally
    # `false` in the M1 Cisco IOS rulepack (no extractor sets it `true` from
    # an `access-class` line yet — a real control-library gap, flagged, not
    # this milestone's to fix) — so it is not excluded here, only asserted
    # as a superset.
    assert {
        ("EDGE-FW-01", "NSCA-MGMT-002"),
        ("EDGE-FW-01", "NSCA-MGMT-005"),
        ("CORE-SW-01", "NSCA-AUTH-001"),
    } <= links_in_path

    # DD-06.2-02: breaking link chosen by cost, not severity — NSCA-AUTH-001
    # is base-severity CRITICAL, but the single-command / safe-impact
    # NSCA-MGMT-005 finding(s) are the cheapest to remediate and should win.
    assert "NSCA-MGMT-005" in path.weakest_link_reason


def test_ap003_effective_severities_elevate_on_internet_facing_edge():
    kb, edge, core = _assessments()
    campaign = assess_campaign((edge, core), kb)

    # EDGE-FW-01 is internet-facing (external + internal zones) -> its FAIL
    # findings escalate per TRD-06.1 §3.2's own worked modifier table.
    mgmt002_key = FindingKey(device_id="EDGE-FW-01", control_id="NSCA-MGMT-002")
    assert campaign.effective_severities[mgmt002_key] == Severity.CRITICAL

    # CORE-SW-01 is purely internal -> no modifier fires, effective==base.
    auth001_key = FindingKey(device_id="CORE-SW-01", control_id="NSCA-AUTH-001")
    assert campaign.effective_severities[auth001_key] == Severity.CRITICAL


def test_ap003_reachability_counterexample_underpins_the_path():
    """INV-06.2-01/02: the path is only ever assembled on top of a concrete
    TRD-04.2 reachability result — verify that result independently."""

    from nsca_engine.graph import build as graph_build
    from nsca_engine.graph import reachability

    _, edge, core = _assessments()
    graph = graph_build.merge_estate((edge, core))
    result = reachability.query(graph, src_addr="203.0.113.5", dst_addr="10.0.20.1", protocol="tcp", dport=22)
    assert result.outcome == "reachable"
    assert result.counterexample is not None
    assert result.counterexample.chain[0].device_id == "EDGE-FW-01"
    assert result.counterexample.chain[0].detail == "Trusted-Admins -> Partners -> 0.0.0.0/0"
