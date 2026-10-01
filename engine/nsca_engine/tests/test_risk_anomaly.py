"""Unit + acceptance tests for `risk/anomaly.py` (TRD-06.3).

The acceptance test (`test_systemic_cluster_detected_on_31_of_40_fleet`) is
the M4 milestone's second "done when" criterion: a systemic-finding cluster
correctly detected on a corpus subset with >=30 near-identical branch-router
configs, using the deliberately constructed fixture set in
`fixtures/branch_routers.py` (the real corpus doesn't have anything like this
yet, same reasoning as the M2/M3 corpus-gap notes elsewhere).
"""

from __future__ import annotations

from nsca_engine.api import Verdict, assess_campaign, assess_device
from nsca_engine.risk import anomaly as risk_anomaly
from nsca_engine.tests.fixtures.branch_routers import (
    DEFECTIVE_COUNT,
    branch_router_fleet,
)
from nsca_engine.tests.helpers import ASSESSED_AT, build_knowledge_base, make_artifact

_KB = build_knowledge_base()


def _assess_fleet():
    fleet = branch_router_fleet()
    assessments = [
        assess_device((make_artifact(cfg, artifact_id=device_id),), _KB, ASSESSED_AT)
        for device_id, cfg in fleet
    ]
    return assessments


def test_systemic_cluster_detected_on_31_of_40_fleet():
    assessments = _assess_fleet()
    campaign = assess_campaign(tuple(assessments), _KB)

    telnet_clusters = [
        c for c in campaign.systemic_findings if c.control_id == "NSCA-MGMT-002"
    ]
    assert len(telnet_clusters) == 1
    cluster = telnet_clusters[0]
    assert len(cluster.device_ids) == DEFECTIVE_COUNT
    assert set(cluster.device_ids) == {f"BR-RTR-{i:03d}" for i in range(1, DEFECTIVE_COUNT + 1)}
    # V-06.3-005: the unaffected peers are enumerated for verification.
    assert "BR-RTR-032" in cluster.description
    assert "verified" in cluster.description or "verify" in cluster.description


def test_systemic_threshold_matches_trd_06_3_max_5_or_20pct():
    """TRD-06.3 §4.2: |cluster| >= max(5, 0.20 * platform_device_count).
    40 devices -> 20% = 8, so a defect on exactly 8 devices should also
    register as systemic; on 7 it should not."""

    fleet = branch_router_fleet(total=40, defective=8)
    assessments = [
        assess_device((make_artifact(cfg, artifact_id=device_id),), _KB, ASSESSED_AT)
        for device_id, cfg in fleet
    ]
    clusters = risk_anomaly.detect_systemic(tuple(assessments))
    telnet = [c for c in clusters if c.control_id == "NSCA-MGMT-002"]
    assert len(telnet) == 1 and len(telnet[0].device_ids) == 8

    fleet_below = branch_router_fleet(total=40, defective=7)
    assessments_below = [
        assess_device((make_artifact(cfg, artifact_id=device_id),), _KB, ASSESSED_AT)
        for device_id, cfg in fleet_below
    ]
    clusters_below = risk_anomaly.detect_systemic(tuple(assessments_below))
    assert not any(c.control_id == "NSCA-MGMT-002" for c in clusters_below)


def test_platform_default_when_all_devices_fail():
    fleet = branch_router_fleet(total=10, defective=10)
    assessments = [
        assess_device((make_artifact(cfg, artifact_id=device_id),), _KB, ASSESSED_AT)
        for device_id, cfg in fleet
    ]
    clusters = risk_anomaly.detect_systemic(tuple(assessments))
    telnet = next(c for c in clusters if c.control_id == "NSCA-MGMT-002")
    assert len(telnet.device_ids) == 10
    assert "platform-default" in telnet.description or "platform default" in telnet.description


def test_systemic_findings_supplement_not_replace_individual_findings_inv_06_3_02():
    assessments = _assess_fleet()
    campaign = assess_campaign(tuple(assessments), _KB)
    assert any(c.control_id == "NSCA-MGMT-002" for c in campaign.systemic_findings)

    # Every one of the 31 affected devices still carries its own FAIL finding.
    for da in assessments[:DEFECTIVE_COUNT]:
        by_control = {f.control_id: f for f in da.findings}
        assert by_control["NSCA-MGMT-002"].verdict == Verdict.FAIL


def test_small_peer_group_is_not_analysed_dd_06_3_01():
    fleet = branch_router_fleet(total=3, defective=1)
    assessments = tuple(
        assess_device((make_artifact(cfg, artifact_id=device_id),), _KB, ASSESSED_AT)
        for device_id, cfg in fleet
    )
    groups = risk_anomaly.peer_groups(assessments, {})
    assert all(not g.analysed for g in groups)
    anomalies = risk_anomaly.detect_peer_anomalies(assessments, {})
    assert anomalies == ()


def test_uniform_group_has_no_anomalies():
    fleet = branch_router_fleet(total=6, defective=6)  # all identical (module-level defect)
    assessments = tuple(
        assess_device((make_artifact(cfg, artifact_id=device_id),), _KB, ASSESSED_AT)
        for device_id, cfg in fleet
    )
    anomalies = risk_anomaly.detect_peer_anomalies(assessments, {})
    assert anomalies == ()


def test_deviating_minority_detected_as_peer_anomaly():
    """37 clean devices, 3 telnet-enabled outliers -> the 3 should be
    flagged as peer anomalies (structurally distinguishable via the
    transport-input fact's normalised path presence)."""

    fleet = branch_router_fleet(total=40, defective=3)
    assessments = tuple(
        assess_device((make_artifact(cfg, artifact_id=device_id),), _KB, ASSESSED_AT)
        for device_id, cfg in fleet
    )
    anomalies = risk_anomaly.detect_peer_anomalies(assessments, {})
    anomalous_devices = {a.device_id for a in anomalies}
    assert {"BR-RTR-001", "BR-RTR-002", "BR-RTR-003"} <= anomalous_devices


def test_determinism_shuffled_order():
    assessments = _assess_fleet()
    forward = risk_anomaly.detect_systemic(tuple(assessments))
    backward = risk_anomaly.detect_systemic(tuple(reversed(assessments)))
    assert forward == backward
