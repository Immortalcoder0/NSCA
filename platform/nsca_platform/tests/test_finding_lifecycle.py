"""M2 acceptance tests — backend-02 §5's finding lifecycle milestone.

Covers: the mapper round-trip for `DeviceFinding`, every legal state
transition plus at least one illegal one, the MGMT-SW-04 REFUTED dispute
example (09-findings-lifecycle.md §6.1) reproduced end to end, the
risk-acceptance mandatory-expiry 422, and the auto-reopen function.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from nsca_engine.types import DeviceFinding, Evidence, PassQuality, Severity, Verdict
from nsca_platform.db import mappers
from nsca_platform.db.models.campaign import campaign as campaign_table
from nsca_platform.db.models.device import device as device_table
from nsca_platform.db.models.finding import finding as finding_table
from nsca_platform.main import app
from nsca_platform.services import dispute as dispute_service
from nsca_platform.services import finding_lifecycle
from nsca_platform.services import risk_acceptance as risk_acceptance_service
from nsca_platform.tests.conftest import requires_db
from nsca_platform.tests.test_stub_endpoints import _create_test_campaign

client = TestClient(app)
LEAD = {"X-Dev-Role": "lead_assessor"}


def _seed_campaign_and_device(conn, *, campaign_public_id: str, hostname: str) -> tuple[uuid.UUID, uuid.UUID]:
    campaign_id = uuid.uuid4()
    conn.execute(
        campaign_table.insert().values(
            id=campaign_id,
            public_id=campaign_public_id,
            name="finding lifecycle test",
            scope_definition={},
            owner="tester",
        )
    )
    device_id = uuid.uuid4()
    conn.execute(device_table.insert().values(id=device_id, hostname=hostname, serials=[]))
    return campaign_id, device_id


def _seed_finding(conn, *, campaign_public_id: str, hostname: str, control_id: str = "NSCA-MGMT-002") -> str:
    campaign_id, device_id = _seed_campaign_and_device(conn, campaign_public_id=campaign_public_id, hostname=hostname)
    evidence = Evidence(
        artifact_id="ART-TEST",
        lines=(1, 2),
        highlight_lines=(1,),
        excerpt="transport input telnet ssh",
        fact_paths=("mgmt.protocols.telnet.enabled",),
    )
    device_finding = DeviceFinding(
        control_id=control_id,
        verdict=Verdict.FAIL,
        pass_quality=None,
        unknown_reason=None,
        severity=Severity.HIGH,
        severity_reason=None,
        evidence=(evidence,),
        framework_refs=("CIS-IOS-1.2.4",),
        contamination_reason=None,
        coverage_inputs={},
    )
    result = finding_lifecycle.create_finding_from_device_finding(
        conn,
        campaign_row_id=campaign_id,
        campaign_public_id=campaign_public_id,
        device_row_id=device_id,
        device_hostname=hostname,
        assessment_row_id=None,
        device_finding=device_finding,
        rulepack_trust_tier="certified",
    )
    return result["id"]


# ---------------------------------------------------------------------------
# Mapper round-trip
# ---------------------------------------------------------------------------


@requires_db
def test_device_finding_mapper_roundtrip(db_conn) -> None:
    campaign_id, device_id = _seed_campaign_and_device(
        db_conn, campaign_public_id="CMP-MAPPER-001", hostname="MAPPER-DEV-01"
    )

    evidence = Evidence(
        artifact_id="ART-MAPPER",
        lines=(10, 12),
        highlight_lines=(11,),
        excerpt="transport input telnet",
        fact_paths=("mgmt.protocols.telnet.enabled",),
    )
    original = DeviceFinding(
        control_id="NSCA-MGMT-002",
        verdict=Verdict.FAIL,
        pass_quality=None,
        unknown_reason=None,
        severity=Severity.HIGH,
        severity_reason=None,
        evidence=(evidence,),
        framework_refs=("CIS-IOS-1.2.4", "AC-17"),
        contamination_reason=None,
        coverage_inputs={},
    )
    row_values = mappers.device_finding_to_row(
        original,
        campaign_id=campaign_id,
        device_id=device_id,
        assessment_id=None,
        public_id="F-MAPPER-000001",
        identity_key="MAPPER-DEV-01:NSCA-MGMT-002",
        framework_refs=[{"framework": "cis", "id": "CIS-IOS-1.2.4"}, {"framework": "nist", "id": "AC-17"}],
    )
    db_conn.execute(finding_table.insert().values(**row_values))

    persisted = (
        db_conn.execute(select(finding_table).where(finding_table.c.public_id == "F-MAPPER-000001")).mappings().first()
    )
    assert persisted is not None

    restored = mappers.row_to_device_finding(persisted)
    assert restored.control_id == original.control_id
    assert restored.verdict == original.verdict
    assert restored.severity == original.severity
    assert restored.evidence[0].artifact_id == original.evidence[0].artifact_id
    assert restored.evidence[0].lines == original.evidence[0].lines
    assert restored.evidence[0].excerpt == original.evidence[0].excerpt
    assert set(restored.framework_refs) == {"CIS-IOS-1.2.4", "AC-17"}


@requires_db
def test_pass_partial_verdict_on_contamination(db_conn) -> None:
    """09-findings-lifecycle.md §2.2: a PASS finding with a contamination
    reason is persisted as PASS_PARTIAL, not a bare PASS."""

    campaign_id, device_id = _seed_campaign_and_device(
        db_conn, campaign_public_id="CMP-CONTAM-001", hostname="CONTAM-DEV-01"
    )
    device_finding = DeviceFinding(
        control_id="NSCA-MGMT-002",
        verdict=Verdict.PASS,
        pass_quality=PassQuality.MEANINGFUL,
        unknown_reason=None,
        severity=Severity.LOW,
        severity_reason=None,
        evidence=(),
        framework_refs=(),
        contamination_reason="An unassessed management capability exists (winbox/8291).",
        coverage_inputs={},
    )
    result = finding_lifecycle.create_finding_from_device_finding(
        db_conn,
        campaign_row_id=campaign_id,
        campaign_public_id="CMP-CONTAM-001",
        device_row_id=device_id,
        device_hostname="CONTAM-DEV-01",
        assessment_row_id=None,
        device_finding=device_finding,
    )
    assert result["verdict"] == "PASS_PARTIAL"


# ---------------------------------------------------------------------------
# State machine — every legal transition + one illegal one
# ---------------------------------------------------------------------------


@requires_db
def test_new_to_confirmed_to_assigned_to_remediated_to_verified_to_closed(db_conn) -> None:
    finding_id = _seed_finding(db_conn, campaign_public_id="CMP-SM-001", hostname="SM-DEV-01")
    assert finding_lifecycle.get_finding(db_conn, finding_id)["state"] == "New"

    finding_lifecycle.confirm(db_conn, finding_id, "assessor@test")
    assert finding_lifecycle.get_finding(db_conn, finding_id)["state"] == "Confirmed"

    finding_lifecycle.assign(db_conn, finding_id, "r.iyer", "assessor@test")
    assert finding_lifecycle.get_finding(db_conn, finding_id)["state"] == "Assigned"

    finding_lifecycle.mark_remediated(db_conn, finding_id, "admin@test")
    assert finding_lifecycle.get_finding(db_conn, finding_id)["state"] == "Remediated"

    finding_lifecycle.apply_verification(db_conn, finding_id, "PASS", "system")
    assert finding_lifecycle.get_finding(db_conn, finding_id)["state"] == "Closed"


@requires_db
def test_remediated_still_fail_returns_to_assigned(db_conn) -> None:
    finding_id = _seed_finding(db_conn, campaign_public_id="CMP-SM-002", hostname="SM-DEV-02")
    finding_lifecycle.confirm(db_conn, finding_id, "a")
    finding_lifecycle.assign(db_conn, finding_id, "r.iyer", "a")
    finding_lifecycle.mark_remediated(db_conn, finding_id, "a")
    finding_lifecycle.apply_verification(db_conn, finding_id, "FAIL", "system")
    assert finding_lifecycle.get_finding(db_conn, finding_id)["state"] == "Assigned"


@requires_db
def test_remediated_unknown_returns_to_assigned_with_warning(db_conn) -> None:
    finding_id = _seed_finding(db_conn, campaign_public_id="CMP-SM-003", hostname="SM-DEV-03")
    finding_lifecycle.confirm(db_conn, finding_id, "a")
    finding_lifecycle.assign(db_conn, finding_id, "r.iyer", "a")
    finding_lifecycle.mark_remediated(db_conn, finding_id, "a")
    finding_lifecycle.apply_verification(db_conn, finding_id, "UNKNOWN", "system")
    result = finding_lifecycle.get_finding(db_conn, finding_id)
    assert result["state"] == "Assigned"
    hist = finding_lifecycle.history(db_conn, finding_id)
    assert "UNKNOWN" in hist["transitions"][-1]["reason"] or "coverage" in hist["transitions"][-1]["reason"]


@requires_db
def test_dispute_withdrawn_to_closed(db_conn) -> None:
    finding_id = _seed_finding(db_conn, campaign_public_id="CMP-SM-004", hostname="SM-DEV-04")
    dispute_service.raise_dispute(db_conn, finding_id, "false_positive", "the tool misread this", "admin@test")
    assert finding_lifecycle.get_finding(db_conn, finding_id)["state"] == "Disputed"

    dispute_service.adjudicate(db_conn, finding_id, "upheld", "confirmed misread", "lead@test")
    assert finding_lifecycle.get_finding(db_conn, finding_id)["state"] == "Withdrawn"

    row_id = db_conn.execute(
        select(finding_table.c.id).where(finding_table.c.public_id == finding_id)
    ).first().id
    finding_lifecycle.transition(db_conn, row_id, finding_id, "Withdrawn", "Closed", "system")
    assert finding_lifecycle.get_finding(db_conn, finding_id)["state"] == "Closed"


@requires_db
def test_dispute_overturned_returns_to_confirmed(db_conn) -> None:
    finding_id = _seed_finding(db_conn, campaign_public_id="CMP-SM-005", hostname="SM-DEV-05")
    dispute_service.raise_dispute(db_conn, finding_id, "false_positive", "claim", "admin@test")
    dispute_service.adjudicate(db_conn, finding_id, "overturned", "claim rejected", "lead@test")
    assert finding_lifecycle.get_finding(db_conn, finding_id)["state"] == "Confirmed"


@requires_db
def test_risk_accepted_expiry_reopens_to_confirmed(db_conn) -> None:
    finding_id = _seed_finding(db_conn, campaign_public_id="CMP-SM-006", hostname="SM-DEV-06")
    past = datetime.now(timezone.utc) + timedelta(days=1)  # will be expired relative to `future_now` below
    risk_acceptance_service.accept_risk(db_conn, finding_id, past, "x" * 25, None, "lead@test")
    assert finding_lifecycle.get_finding(db_conn, finding_id)["state"] == "Risk Accepted"

    future_now = datetime.now(timezone.utc) + timedelta(days=2)
    reopened = risk_acceptance_service.auto_reopen_expired(db_conn, future_now)
    assert finding_id in reopened
    assert finding_lifecycle.get_finding(db_conn, finding_id)["state"] == "Confirmed"


@requires_db
def test_illegal_transition_rejected(db_conn) -> None:
    finding_id = _seed_finding(db_conn, campaign_public_id="CMP-SM-007", hostname="SM-DEV-07")
    # New -> Assigned is not a legal transition (must go through Confirmed).
    with pytest.raises(finding_lifecycle.IllegalTransition):
        finding_lifecycle.assign(db_conn, finding_id, "r.iyer", "a")


@requires_db
def test_closed_is_terminal(db_conn) -> None:
    finding_id = _seed_finding(db_conn, campaign_public_id="CMP-SM-008", hostname="SM-DEV-08")
    finding_lifecycle.confirm(db_conn, finding_id, "a")
    finding_lifecycle.assign(db_conn, finding_id, "r.iyer", "a")
    finding_lifecycle.mark_remediated(db_conn, finding_id, "a")
    finding_lifecycle.apply_verification(db_conn, finding_id, "PASS", "system")
    assert finding_lifecycle.get_finding(db_conn, finding_id)["state"] == "Closed"
    with pytest.raises(finding_lifecycle.IllegalTransition):
        finding_lifecycle.confirm(db_conn, finding_id, "a")


# ---------------------------------------------------------------------------
# MGMT-SW-04 REFUTED dispute — 09-findings-lifecycle.md §6.1, the M2
# acceptance criterion.
# ---------------------------------------------------------------------------


@requires_db
def test_mgmt_sw_04_refuted_dispute_end_to_end(db_conn) -> None:
    finding_id = _seed_finding(
        db_conn, campaign_public_id="CMP-MGMTSW04-001", hostname="MGMT-SW-04", control_id="NSCA-MGMT-002"
    )

    result = dispute_service.raise_dispute(
        db_conn,
        finding_id,
        "compensating_control",
        "Telnet is enabled on MGMT-SW-04, but the device resides on an isolated "
        "out-of-band management network and is unreachable from any user network.",
        "r.kulkarni",
    )

    assert result["verification"]["result"] == "REFUTED"
    counterexample = result["verification"]["counterexample"]
    assert counterexample["packet"]["dst"] == "10.250.0.11"
    assert counterexample["packet"]["dport"] == 23
    assert any("Gi0/8" in step["node"] for step in counterexample["path"])
    assert any("VLAN 250" in step.get("note", "") and "VLAN 40" in step.get("note", "") for step in counterexample["path"])

    # The finding itself is now Disputed, with the verification result
    # recoverable from history/persisted dispute row.
    assert finding_lifecycle.get_finding(db_conn, finding_id)["state"] == "Disputed"


@requires_db
def test_mgmt_sw_04_dispute_via_api(db_conn) -> None:
    """Same scenario, exercised through the real HTTP endpoints (assessment
    worker persists the fixture finding, then dispute over the API)."""

    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "name": "MGMT-SW-04 dispute test",
            "scope": {"type": "explicit", "devices": ["MGMT-SW-04"]},
            "owner": "tester",
        },
    ).json()

    assess = client.post(f"/api/v1/campaigns/{campaign['id']}/assess")
    assert assess.status_code == 202, assess.text

    findings = client.get(f"/api/v1/campaigns/{campaign['id']}/findings").json()
    assert findings["items"], "assessment worker should have produced at least one finding"
    finding_id = findings["items"][0]["id"]

    dispute_resp = client.post(
        f"/api/v1/findings/{finding_id}/dispute",
        json={
            "type": "compensating_control",
            "claim": "Device resides on an isolated OOB management network 10.250.0.0/24",
        },
    )
    assert dispute_resp.status_code == 201, dispute_resp.text
    assert dispute_resp.json()["verification"]["result"] == "REFUTED"


# ---------------------------------------------------------------------------
# Real reachability-verified dispute (M5) — services/dispute.py
# ._try_engine_reachability now calls the real nsca_engine.api
# .query_reachability against a real Graph, cached per campaign
# (services/graph_cache.py) by services/assessment.py.run_assessment's real
# assess_campaign call (M5 items 3-4).
#
# MGMT-SW-04's own scenario (a VLAN-bridging interface undercutting a
# claimed OOB-isolation compensating control) has no matching real,
# parseable Cisco IOS config in this repo to assess for real — it only
# exists as `services/assessment.py`'s hand-built fixture. Rather than
# author a novel ACL config to reverse-engineer that exact scenario, this
# test reuses `edge_fw_01.cfg` — the same real config the engine's own M3
# reachability acceptance tests (`engine/nsca_engine/tests
# /test_graph_reachability.py::test_canonical_counterexample_reproduced_exactly`)
# use for the canonical 04-system-architecture.md §4.5 counterexample: an
# ACL permitting 203.0.113.x -> 10.0.0.1:22/tcp via
# Trusted-Admins -> Partners -> 0.0.0.0/0, denying everything else. That is
# the same class of proof MGMT-SW-04's REFUTED worked example makes (a
# claimed compensating control undercut by a real, discoverable route) —
# judgment call, flagged rather than silently substituted.
# ---------------------------------------------------------------------------

_EDGE_FW_FIXTURE = (
    Path(__file__).resolve().parents[3] / "engine" / "nsca_engine" / "tests" / "fixtures" / "graph_estate" / "edge_fw_01.cfg"
)


@pytest.mark.skipif(
    not _EDGE_FW_FIXTURE.exists(),
    reason=f"engine corpus fixture not found at {_EDGE_FW_FIXTURE} in this checkout layout",
)
@requires_db
def test_real_reachability_verified_dispute_refuted(db_conn) -> None:
    """A claim that tcp/22 from 203.0.113.5 to 10.0.0.1 is blocked is
    REFUTED by a real `query_reachability` call: the real Graph built from
    `edge_fw_01.cfg`'s ACL genuinely permits that traffic (the canonical
    counterexample), so the claimed compensating control does not hold."""

    created = _create_test_campaign(
        name="real reachability dispute test (refuted)",
        scope={"type": "explicit", "devices": ["EDGE-FW-01"]},
    )
    content = _EDGE_FW_FIXTURE.read_bytes()
    upload = client.post(
        f"/api/v1/campaigns/{created['id']}/artifacts",
        files=[("files", ("edge-fw-01.cfg", content, "text/plain"))],
    )
    assert upload.status_code == 201, upload.text
    # `RawArtifact.id` (the platform-assigned, engine-opaque artifact id —
    # not the device hostname) is what ends up as the graph node's
    # `device_id` in a real `assess_device`/`assess_campaign` call
    # (nsca_engine/api.py: `graph_build.device_graph_contribution(primary.id,
    # ...)`) — so the real counterexample's chain step names this artifact
    # id, not "EDGE-FW-01".
    artifact_id = upload.json()["results"][0]["artifact_id"]

    assess = client.post(f"/api/v1/campaigns/{created['id']}/assess")
    assert assess.status_code == 202, assess.text

    findings = client.get(f"/api/v1/campaigns/{created['id']}/findings").json()["items"]
    assert findings, "real assess_device should have produced at least one finding for EDGE-FW-01"
    finding_id = findings[0]["id"]

    dispute_resp = client.post(
        f"/api/v1/findings/{finding_id}/dispute",
        json={
            "type": "compensating_control",
            "claim": (
                "A compensating control blocks tcp port 22 traffic from "
                "203.0.113.5 to 10.0.0.1."
            ),
        },
    )
    assert dispute_resp.status_code == 201, dispute_resp.text
    verification = dispute_resp.json()["verification"]
    assert verification["result"] == "REFUTED"
    assert verification["counterexample"] is not None
    assert verification["counterexample"]["packet"]["dst"] == "10.0.0.1"
    assert verification["counterexample"]["packet"]["dport"] == 22
    assert any(artifact_id in step.get("node", "") for step in verification["counterexample"]["path"])


@pytest.mark.skipif(
    not _EDGE_FW_FIXTURE.exists(),
    reason=f"engine corpus fixture not found at {_EDGE_FW_FIXTURE} in this checkout layout",
)
@requires_db
def test_real_reachability_verified_dispute_confirmed(db_conn) -> None:
    """Same real Graph, but a claim about tcp/23 (a port `edge_fw_01.cfg`'s
    ACL does not permit — no rule matches, default deny) is CONFIRMED: the
    real reachability query finds no path, so the claimed compensating
    control genuinely holds."""

    created = _create_test_campaign(
        name="real reachability dispute test (confirmed)",
        scope={"type": "explicit", "devices": ["EDGE-FW-01"]},
    )
    content = _EDGE_FW_FIXTURE.read_bytes()
    upload = client.post(
        f"/api/v1/campaigns/{created['id']}/artifacts",
        files=[("files", ("edge-fw-01.cfg", content, "text/plain"))],
    )
    assert upload.status_code == 201, upload.text

    assess = client.post(f"/api/v1/campaigns/{created['id']}/assess")
    assert assess.status_code == 202, assess.text

    findings = client.get(f"/api/v1/campaigns/{created['id']}/findings").json()["items"]
    assert findings
    finding_id = findings[0]["id"]

    dispute_resp = client.post(
        f"/api/v1/findings/{finding_id}/dispute",
        json={
            "type": "compensating_control",
            "claim": (
                "A compensating control blocks tcp port 23 traffic from "
                "203.0.113.5 to 10.0.0.1."
            ),
        },
    )
    assert dispute_resp.status_code == 201, dispute_resp.text
    verification = dispute_resp.json()["verification"]
    assert verification["result"] == "CONFIRMED"
    assert verification["counterexample"] is None


# ---------------------------------------------------------------------------
# Risk acceptance mandatory expiry (422) and auto-reopen
# ---------------------------------------------------------------------------


@requires_db
def test_accept_risk_requires_future_expires_at_via_api(db_conn) -> None:
    finding_id = _seed_finding(db_conn, campaign_public_id="CMP-RA-001", hostname="RA-DEV-01")
    # The API request below runs on its own DB connection/transaction
    # (`connect()` inside the route handler) — commit here so it's visible
    # cross-connection, same as every other DB write this test relies on.
    db_conn.commit()

    missing = client.post(f"/api/v1/findings/{finding_id}/accept-risk", json={"justification": "x" * 25}, headers=LEAD)
    assert missing.status_code == 422

    backdated = client.post(
        f"/api/v1/findings/{finding_id}/accept-risk",
        json={"expires_at": "2020-01-01", "justification": "x" * 25},
        headers=LEAD,
    )
    assert backdated.status_code == 422

    ok = client.post(
        f"/api/v1/findings/{finding_id}/accept-risk",
        json={"expires_at": "2027-03-31", "justification": "Isolated OOB network; replacement scheduled."},
        headers=LEAD,
    )
    assert ok.status_code == 200
    assert ok.json()["state"] == "Risk Accepted"
    assert ok.json()["risk_acceptance"]["expires_at"] == "2027-03-31"


@requires_db
def test_auto_reopen_expired_function(db_conn) -> None:
    finding_id = _seed_finding(db_conn, campaign_public_id="CMP-RA-002", hostname="RA-DEV-02")
    already_expired = datetime.now(timezone.utc) - timedelta(days=1)
    # Bypass the API's future-expiry validator to construct an
    # already-expired acceptance directly at the service layer — the
    # validator is a *request*-time guard; the auto-reopen function must
    # still correctly reopen a row that reached this state legitimately
    # (accepted with a valid future expiry that has since passed).
    risk_acceptance_service.accept_risk(db_conn, finding_id, already_expired, "y" * 25, None, "lead@test")
    assert finding_lifecycle.get_finding(db_conn, finding_id)["state"] == "Risk Accepted"

    reopened = risk_acceptance_service.auto_reopen_expired(db_conn, datetime.now(timezone.utc))
    assert finding_id in reopened
    assert finding_lifecycle.get_finding(db_conn, finding_id)["state"] == "Confirmed"

    # Idempotent: calling again does nothing (already auto_reopened_at is set).
    reopened_again = risk_acceptance_service.auto_reopen_expired(db_conn, datetime.now(timezone.utc))
    assert finding_id not in reopened_again
