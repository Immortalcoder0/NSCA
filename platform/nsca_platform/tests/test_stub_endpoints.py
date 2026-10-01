"""M0 acceptance tests: every stubbed endpoint responds with the documented
status code and the spec's example payload (where the spec gives one,
verbatim; field-for-field for the fields the spec lists)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from nsca_platform.main import app
from nsca_platform.tests.conftest import requires_db

client = TestClient(app)

LEAD = {"X-Dev-Role": "lead_assessor"}
PLATFORM_ADMIN = {"X-Dev-Role": "platform_administrator"}
NET_ADMIN = {"X-Dev-Role": "network_administrator"}


def test_openapi_schema_live() -> None:
    resp = client.get("/api/v1/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["openapi"]
    # Spot check a handful of documented paths exist in the schema
    for path in [
        "/api/v1/campaigns",
        "/api/v1/campaigns/{campaign_id}/artifacts",
        "/api/v1/assessments/{assessment_id}",
        "/api/v1/findings/{finding_id}",
        "/api/v1/training/queue",
        "/api/v1/knowledge/rulepacks",
        "/api/v1/reports/{report_id}",
        "/api/v1/admin/health",
    ]:
        assert path in schema["paths"], path


# ---- Campaigns (M1: real DB-backed via services/campaign.py) ------------
#
# These now require a real Postgres (backend-02 §4.1 forbids a SQLite
# dual-backend) — see `nsca_platform/tests/conftest.py`. Each test creates
# its own campaign rather than assuming a fixed `CMP-2026Q3-001` id exists,
# since campaign ids are now real, DB-generated public ids.


def _create_test_campaign(**overrides) -> dict:
    body = {
        "name": "Q3-2026 Core Infrastructure Audit",
        "scope": {"type": "filter", "expression": "exposure == 'internet_facing'"},
        "frameworks": [{"framework": "cis", "benchmark": "cisco_ios_15", "version": "4.1.0"}],
        "owner": "p.sharma",
        "window": {"start": "2026-09-01", "end": "2026-09-30"},
    }
    body.update(overrides)
    resp = client.post("/api/v1/campaigns", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


@requires_db
def test_create_campaign(db_conn) -> None:
    body = _create_test_campaign()
    assert body["name"] == "Q3-2026 Core Infrastructure Audit"
    assert body["owner"] == "p.sharma"
    assert body["status"] == "Draft"
    assert body["id"].startswith("CMP-")


@requires_db
def test_create_campaign_rejects_unknown_framework(db_conn) -> None:
    # M5 (Phase 3 demo-rehearsal Bug 4): a genuinely made-up framework name
    # is refused with a clean 422, not accepted unconditionally. cis/nist/
    # stig/iso remain accepted — they're recognised families even before
    # any content is imported for them (CIS/ISO import itself is out of
    # this milestone's scope).
    rejected = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Bad framework campaign",
            "scope": {"type": "filter", "expression": "exposure == 'internet_facing'"},
            "frameworks": [{"framework": "totally_fake_framework_xyz", "version": "1.0"}],
            "owner": "p.sharma",
        },
    )
    assert rejected.status_code == 422

    ok = _create_test_campaign(frameworks=[{"framework": "iso", "benchmark": "27001", "version": "2022"}])
    assert ok["frameworks"][0]["framework"] == "iso"


@requires_db
def test_list_campaigns(db_conn) -> None:
    _create_test_campaign()
    resp = client.get("/api/v1/campaigns")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1


@requires_db
def test_get_campaign(db_conn) -> None:
    created = _create_test_campaign()
    resp = client.get(f"/api/v1/campaigns/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]
    assert "knowledge_pin" in resp.json()


@requires_db
def test_get_campaign_not_found(db_conn) -> None:
    resp = client.get("/api/v1/campaigns/CMP-NOPE-999")
    assert resp.status_code == 404


@requires_db
def test_patch_campaign(db_conn) -> None:
    created = _create_test_campaign()
    resp = client.patch(f"/api/v1/campaigns/{created['id']}", json={"owner": "new-owner"})
    assert resp.status_code == 200
    assert resp.json()["owner"] == "new-owner"


@requires_db
def test_patch_campaign_rejected_once_not_draft(db_conn) -> None:
    created = _create_test_campaign()
    issue = client.post(f"/api/v1/campaigns/{created['id']}/issue", headers=LEAD)
    assert issue.status_code == 200
    resp = client.patch(f"/api/v1/campaigns/{created['id']}", json={"owner": "someone-else"})
    assert resp.status_code == 409


@requires_db
def test_resolve_scope_explicit(db_conn) -> None:
    created = _create_test_campaign(scope={"type": "explicit", "devices": ["CORE-SW-01"]})
    resp = client.post(f"/api/v1/campaigns/{created['id']}/scope/resolve")
    assert resp.status_code == 200
    assert "device_count" in resp.json()
    # No device named CORE-SW-01 correlated yet in this fresh DB -> 0.
    assert resp.json()["device_count"] == 0


@requires_db
def test_issue_campaign_requires_lead_assessor(db_conn) -> None:
    created = _create_test_campaign()
    forbidden = client.post(
        f"/api/v1/campaigns/{created['id']}/issue", headers={"X-Dev-Role": "read_only"}
    )
    assert forbidden.status_code == 403

    ok = client.post(f"/api/v1/campaigns/{created['id']}/issue", headers=LEAD)
    assert ok.status_code == 200
    assert ok.json()["status"] == "Issued"


@requires_db
def test_close_campaign(db_conn) -> None:
    created = _create_test_campaign()
    client.post(f"/api/v1/campaigns/{created['id']}/issue", headers=LEAD)
    resp = client.post(f"/api/v1/campaigns/{created['id']}/close")
    assert resp.status_code == 200
    assert resp.json()["status"] == "Closed"


@requires_db
def test_close_campaign_requires_issued_first(db_conn) -> None:
    created = _create_test_campaign()
    resp = client.post(f"/api/v1/campaigns/{created['id']}/close")
    assert resp.status_code == 409


@requires_db
def test_campaign_completeness(db_conn) -> None:
    created = _create_test_campaign()
    resp = client.get(f"/api/v1/campaigns/{created['id']}/completeness")
    assert resp.status_code == 200
    assert "outcomes" in resp.json()


def test_compare_campaigns() -> None:
    # Still an M0-style stub — comparison needs finding lifecycle +
    # knowledge-base diffing, both out of M1 scope.
    resp = client.get("/api/v1/campaigns/CMP-2026Q3-001/compare/CMP-2026Q2-001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["compliance"] == {"from": 0.78, "to": 0.81}
    assert body["decomposition"][0]["cause"] == "verified_remediation"


# ---- Ingestion (M1: real DB-backed via services/ingestion.py) -----------
#
# `test_upload_artifacts_four_outcome_states` is the M1 acceptance fixture:
# bulk-uploading a real multi-platform directory must produce the four
# outcome states from 15-api-specification.md §3's example.

_CISCO_IOSXE_VERBOSE = b"""! Cisco IOS XE Software
hostname CORE-SW-01
version 16.12.04
!
ip classless
no ip source-route
ip cef
no service pad
!
interface GigabitEthernet0/1
 ip address 10.0.0.1 255.255.255.0
!
line vty 0 4
 login local
 transport input telnet ssh
!
end
"""

_CISCO_IOS_TERSE = b"""! cisco config
hostname BR-RTR-014
version 15.2
!
interface FastEthernet0/0
 ip address 10.1.1.1 255.255.255.0
!
line vty 0 4
 transport input ssh
!
end
"""

_MIKROTIK_NOT_TAUGHT = b"""# RouterOS 7.11.2
/system identity
set name=RTR-Pune-02
/ip service
set telnet disabled=no port=23
set ssh disabled=no port=22
"""

_UNIDENTIFIED = b"""%%%GARBLED-EXPORT-FORMAT%%%
some proprietary blob that matches no known grammar
0xDEADBEEF 0xCAFEBABE
"""


@requires_db
def test_upload_artifacts_four_outcome_states(db_conn) -> None:
    created = _create_test_campaign()
    resp = client.post(
        f"/api/v1/campaigns/{created['id']}/artifacts",
        files=[
            ("files", ("CORE-SW-01/running-config.txt", _CISCO_IOSXE_VERBOSE, "text/plain")),
            ("files", ("BR-RTR-014.cfg", _CISCO_IOS_TERSE, "text/plain")),
            ("files", ("RTR-Pune-02.rsc", _MIKROTIK_NOT_TAUGHT, "text/plain")),
            ("files", ("unknown-04.cfg", _UNIDENTIFIED, "text/plain")),
        ],
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["accepted"] == 4
    results_by_status = {r["status"]: r for r in body["results"]}
    assert set(results_by_status) == {"parsed", "parsed_with_caveat", "platform_not_taught", "unidentified"}

    parsed = results_by_status["parsed"]
    assert parsed["device"] == "CORE-SW-01"
    assert parsed["platform"] == "cisco_iosxe"
    assert parsed["export_mode"] == "verbose"

    caveat = results_by_status["parsed_with_caveat"]
    assert caveat["platform"] == "cisco_ios"
    assert caveat["export_mode"] == "terse"
    assert caveat["caveat"]["code"] == "TERSE_EXPORT"

    not_taught = results_by_status["platform_not_taught"]
    assert not_taught["platform"] == "mikrotik_routeros"
    assert "training" in not_taught and not_taught["training"]["url"].endswith("mikrotik_routeros")

    unidentified = results_by_status["unidentified"]
    assert "grammar_coverage" in unidentified
    assert "message" in unidentified

    # And completeness reflects the same tallies (FR-ING-015/016).
    completeness = client.get(f"/api/v1/campaigns/{created['id']}/completeness").json()
    assert completeness["outcomes"]["parsed"] == 1
    assert completeness["outcomes"]["parsed_with_caveat"] == 1
    assert completeness["outcomes"]["platform_not_taught"] == 1
    assert completeness["outcomes"]["unidentified"] == 1


@requires_db
def test_upload_artifacts_correlates_same_device_across_uploads(db_conn) -> None:
    created = _create_test_campaign()
    first = client.post(
        f"/api/v1/campaigns/{created['id']}/artifacts",
        files=[("files", ("a.cfg", _CISCO_IOSXE_VERBOSE, "text/plain"))],
    ).json()
    second = client.post(
        f"/api/v1/campaigns/{created['id']}/artifacts",
        files=[("files", ("b.cfg", _CISCO_IOSXE_VERBOSE, "text/plain"))],
    ).json()
    assert first["results"][0]["device"] == second["results"][0]["device"] == "CORE-SW-01"


def test_start_collection_mode_read_only() -> None:
    body = {
        "targets": [{"host": "10.0.0.5", "credential_ref": "cred-audit-ios"}],
        "artifacts": ["running_config", "show_version", "show_inventory"],
        "mode": "read_only",
    }
    resp = client.post("/api/v1/campaigns/CMP-2026Q3-001/collect", json=body)
    assert resp.status_code == 202


def test_start_collection_rejects_write_mode() -> None:
    body = {
        "targets": [{"host": "10.0.0.5", "credential_ref": "cred-audit-ios"}],
        "artifacts": ["running_config"],
        "mode": "read_write",
    }
    resp = client.post("/api/v1/campaigns/CMP-2026Q3-001/collect", json=body)
    assert resp.status_code == 422


def test_get_job() -> None:
    resp = client.get("/api/v1/jobs/job-2026-004821")
    assert resp.status_code == 200


@requires_db
def test_get_artifact_and_content_real(db_conn) -> None:
    created = _create_test_campaign()
    upload = client.post(
        f"/api/v1/campaigns/{created['id']}/artifacts",
        files=[("files", ("CORE-SW-01/running-config.txt", _CISCO_IOSXE_VERBOSE, "text/plain"))],
    ).json()
    artifact_id = upload["results"][0]["artifact_id"]

    resp = client.get(f"/api/v1/artifacts/{artifact_id}")
    assert resp.status_code == 200
    assert resp.json()["device"] == "CORE-SW-01"
    assert resp.json()["custody"]["content_addressed_path"]

    resp2 = client.get(f"/api/v1/artifacts/{artifact_id}/content")
    assert resp2.status_code == 200
    assert "hostname CORE-SW-01" in resp2.json()["content"]


def test_get_artifact_and_content_unknown_id_falls_back() -> None:
    resp = client.get("/api/v1/artifacts/ART-004121")
    assert resp.status_code == 200
    resp2 = client.get("/api/v1/artifacts/ART-004121/content")
    assert resp2.status_code == 200


# ---- Assessment (M2: real DB-backed via services/assessment.py, worker
# pipeline run against fixtures — backend-02 §3) ---------------------------


@requires_db
def test_run_assessment(db_conn) -> None:
    created = _create_test_campaign(scope={"type": "explicit", "devices": ["CORE-SW-01"]})
    resp = client.post(f"/api/v1/campaigns/{created['id']}/assess")
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["assessments"]


@requires_db
def test_run_assessment_unknown_campaign_404(db_conn) -> None:
    resp = client.post("/api/v1/campaigns/CMP-NOPE-999/assess")
    assert resp.status_code == 404


@requires_db
def test_get_assessment(db_conn) -> None:
    created = _create_test_campaign(scope={"type": "explicit", "devices": ["CORE-SW-01"]})
    run = client.post(f"/api/v1/campaigns/{created['id']}/assess").json()
    assessment_id = run["assessments"][0]

    resp = client.get(f"/api/v1/assessments/{assessment_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["device"] == "CORE-SW-01"
    assert body["scores"]["compliance"] == 0.78


def test_get_assessment_facts() -> None:
    resp = client.get("/api/v1/assessments/ASM-2026Q3-004121/facts")
    assert resp.status_code == 200
    assert resp.json()["facts"]


def test_get_assessment_fact_by_path() -> None:
    resp = client.get("/api/v1/assessments/ASM-2026Q3-004121/facts/mgmt.protocols.telnet.enabled")
    assert resp.status_code == 200
    body = resp.json()
    assert body["path"] == "mgmt.protocols.telnet.enabled"
    assert body["value"] is True
    assert body["provenance"]["artifact"] == "ART-004121"


def test_get_assessment_unmatched() -> None:
    resp = client.get("/api/v1/assessments/ASM-2026Q3-004121/unmatched")
    assert resp.status_code == 200


# ---- Findings (M2: real DB-backed via services/finding_lifecycle.py,
# services/dispute.py, services/risk_acceptance.py — see
# tests/test_finding_lifecycle.py for the full state-machine and
# MGMT-SW-04 dispute acceptance coverage; these tests just check the HTTP
# surface returns the documented shapes) --------------------------------


def _create_finding_via_assessment(**campaign_overrides) -> tuple[str, str]:
    """Creates a campaign, runs the fixture assessment worker against
    CORE-SW-01, and returns `(campaign_id, finding_id)` for the resulting
    NSCA-MGMT-002 finding."""

    overrides = {"scope": {"type": "explicit", "devices": ["CORE-SW-01"]}}
    overrides.update(campaign_overrides)
    created = _create_test_campaign(**overrides)
    client.post(f"/api/v1/campaigns/{created['id']}/assess")
    findings = client.get(f"/api/v1/campaigns/{created['id']}/findings").json()
    return created["id"], findings["items"][0]["id"]


@requires_db
def test_list_and_get_finding(db_conn) -> None:
    campaign_id, finding_id = _create_finding_via_assessment()
    resp = client.get(f"/api/v1/campaigns/{campaign_id}/findings")
    assert resp.status_code == 200
    assert resp.json()["items"]

    resp2 = client.get(f"/api/v1/findings/{finding_id}")
    assert resp2.status_code == 200
    body = resp2.json()
    assert body["control"] == "NSCA-MGMT-002"
    assert body["state"] == "New"


@requires_db
def test_finding_confirm_assign(db_conn) -> None:
    _, finding_id = _create_finding_via_assessment()
    assert client.post(f"/api/v1/findings/{finding_id}/confirm").status_code == 200
    resp = client.post(f"/api/v1/findings/{finding_id}/assign", json={"assignee": "r.iyer"})
    assert resp.status_code == 200
    assert resp.json()["owner"] == "r.iyer"


@requires_db
def test_finding_dispute(db_conn) -> None:
    _, finding_id = _create_finding_via_assessment(
        name="MGMT-SW-04 dispute", scope={"type": "explicit", "devices": ["MGMT-SW-04"]}
    )
    body = {
        "type": "compensating_control",
        "claim": "Device is on an isolated OOB management network 10.250.0.0/24",
    }
    resp = client.post(f"/api/v1/findings/{finding_id}/dispute", json=body)
    assert resp.status_code == 201
    assert resp.json()["verification"]["result"] == "REFUTED"


@requires_db
def test_finding_adjudicate_requires_lead_assessor(db_conn) -> None:
    _, finding_id = _create_finding_via_assessment()
    client.post(f"/api/v1/findings/{finding_id}/dispute", json={"type": "false_positive", "claim": "misread"})
    forbidden = client.post(
        f"/api/v1/findings/{finding_id}/adjudicate",
        json={"decision": "upheld"},
        headers={"X-Dev-Role": "read_only"},
    )
    assert forbidden.status_code == 403
    ok = client.post(f"/api/v1/findings/{finding_id}/adjudicate", json={"decision": "upheld"}, headers=LEAD)
    assert ok.status_code == 200
    assert ok.json()["state"] == "Withdrawn"


@requires_db
def test_accept_risk_requires_expires_at(db_conn) -> None:
    _, finding_id = _create_finding_via_assessment()
    missing_expiry = client.post(
        f"/api/v1/findings/{finding_id}/accept-risk",
        json={"justification": "Isolated OOB network; legacy NMS requires Telnet."},
        headers=LEAD,
    )
    assert missing_expiry.status_code == 422

    ok = client.post(
        f"/api/v1/findings/{finding_id}/accept-risk",
        json={
            "expires_at": "2027-03-31",
            "justification": "Isolated OOB network; legacy NMS requires Telnet. Replacement under NET-2291.",
            "compensating_control": {"claim": "Network isolation of 10.250.0.0/24"},
        },
        headers=LEAD,
    )
    assert ok.status_code == 200
    assert ok.json()["state"] == "Risk Accepted"


@requires_db
def test_mark_remediated_and_verify(db_conn) -> None:
    _, finding_id = _create_finding_via_assessment()
    client.post(f"/api/v1/findings/{finding_id}/confirm")
    client.post(f"/api/v1/findings/{finding_id}/assign", json={"assignee": "r.iyer"})
    assert client.post(f"/api/v1/findings/{finding_id}/mark-remediated").status_code == 200
    assert client.post(f"/api/v1/findings/{finding_id}/verify").status_code == 202


@requires_db
def test_finding_history_and_remediation(db_conn) -> None:
    _, finding_id = _create_finding_via_assessment()
    hist = client.get(f"/api/v1/findings/{finding_id}/history")
    assert hist.status_code == 200
    assert hist.json()["transitions"][0]["state"] == "New"
    assert client.get(f"/api/v1/findings/{finding_id}/remediation").status_code == 200


@requires_db
def test_bulk_findings(db_conn) -> None:
    _, finding_id = _create_finding_via_assessment()
    resp = client.post(
        "/api/v1/findings/bulk",
        json={"finding_ids": [finding_id, "F-NOPE-000999"], "action": "confirm"},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 1


def test_attack_paths_and_systemic() -> None:
    assert client.get("/api/v1/campaigns/CMP-2026Q3-001/attack-paths").status_code == 200
    assert client.get("/api/v1/campaigns/CMP-2026Q3-001/systemic").status_code == 200


# ---- Training (M3: real, DB-backed via services/training.py and
# learning/*.py — see test_training_pipeline.py for the full mine ->
# propose -> confirm -> synthesize -> ratify pipeline tests; these are
# just the HTTP-boundary smoke tests, same pattern M1/M2 used above) ------
#
# Real training_question rows must exist for queue/next/answer to have
# anything to return, so each test seeds the MikroTik fixture through
# services/training.py first, exactly as a real mined corpus would.


def _seed_mikrotik_questions(platform: str = "mikrotik_stub_test") -> None:
    from nsca_platform.db.engine import connect
    from nsca_platform.learning.template_mining import RequiredControlLike
    from nsca_platform.services import training as training_service
    from nsca_platform.tests.fixtures.mikrotik import build_required_controls, build_unmatched_constructs

    unmatched = build_unmatched_constructs()
    controls_fixture = build_required_controls()
    controls = [RequiredControlLike(c.control_id, c.requires_facts) for c in controls_fixture]
    fact_candidates = [(f, "boolean") for c in controls_fixture for f in c.requires_facts]

    with connect() as conn:
        training_service.seed_questions_for_platform(
            conn, platform=platform, unmatched=unmatched, controls=controls, fact_candidates=fact_candidates,
        )
        conn.commit()


@requires_db
def test_training_queue() -> None:
    _seed_mikrotik_questions("mikrotik_stub_test_queue")
    assert client.get("/api/v1/training/queue").status_code == 200
    resp = client.get("/api/v1/training/queue/mikrotik_stub_test_queue")
    assert resp.status_code == 200
    assert len(resp.json()["questions"]) == 9


@requires_db
def test_training_next_question() -> None:
    _seed_mikrotik_questions("mikrotik_stub_test_next")
    resp = client.get("/api/v1/training/queue/mikrotik_stub_test_next/next")
    assert resp.status_code == 200
    body = resp.json()
    assert body["position"] == 1
    assert body["section"] == "/ip service"


@requires_db
def test_training_answer_polarity_gate() -> None:
    """V-08.3-002 / V-08.2-002 at the real HTTP boundary."""

    _seed_mikrotik_questions("mikrotik_stub_test_answer")
    next_q = client.get("/api/v1/training/queue/mikrotik_stub_test_answer/next").json()
    qid = next_q["question_id"]
    assert next_q["proposal"]["polarity"]["requires_explicit_confirmation"] is True

    missing_polarity = client.post(
        "/api/v1/training/answer",
        json={"question_id": qid, "response": "confirm"},
    )
    assert missing_polarity.status_code == 422

    ok = client.post(
        "/api/v1/training/answer",
        json={"question_id": qid, "response": "confirm", "polarity_confirmed": True},
    )
    assert ok.status_code == 200


@requires_db
def test_training_rules_and_metrics() -> None:
    assert client.get("/api/v1/training/rules", params={"status": "provisional"}).status_code == 200
    assert client.post("/api/v1/training/rules/RULE-does-not-exist/ratify").status_code == 404
    assert client.post("/api/v1/training/rules/RULE-does-not-exist/reject").status_code == 404
    resp = client.get("/api/v1/training/metrics")
    assert resp.status_code == 200
    assert "trend" in resp.json()


# ---- Knowledge --------------------------------------------------------

def test_knowledge_rulepacks() -> None:
    # M4: /rulepacks/import is wired to real signature-verified bundle
    # import (knowledge_import.rulepack_bundle) — a bare stub byte string
    # is correctly rejected (400, not a valid bundle archive); a real
    # exported bundle round-trips through the API.
    from nsca_platform.knowledge_import import rulepack_bundle

    # M5 (Phase 3 demo-rehearsal Bug 1): real rulepacks actually loaded
    # from nsca/knowledge/rulepacks/, not one hardcoded `cisco_iosxe` entry
    # regardless of what's on disk — `cisco_ios` is a real, always-present
    # rulepack file; `cisco_iosxe` is not a real rulepack id in this build.
    listed = client.get("/api/v1/knowledge/rulepacks")
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()["items"]}
    assert "cisco_ios" in ids
    assert "cisco_iosxe" not in ids
    assert len(ids) >= 7  # cisco_ios, cloud_generic_fw, fortios, panos, 2x juniper, routeros, ...

    # M5 (Phase 3 demo-rehearsal Bug 2): real coverage for a real rulepack
    # id, and 404 (not a fabricated payload) for one that doesn't exist.
    coverage = client.get("/api/v1/knowledge/rulepacks/cisco_ios/coverage")
    assert coverage.status_code == 200
    body = coverage.json()
    assert body["rulepack_id"] == "cisco_ios"
    assert body["controls_total"] > 0
    assert 0.0 <= body["coverage_rate"] <= 1.0
    assert client.get("/api/v1/knowledge/rulepacks/totally_fake_platform_xyz/coverage").status_code == 404

    rejected = client.post(
        "/api/v1/knowledge/rulepacks/import",
        files={"file": ("bundle.tar.gz", b"stub", "application/gzip")},
    )
    assert rejected.status_code == 400

    bundle = rulepack_bundle.export_bundle(rulepack_bundle.DEFAULT_STAGING_DIR.parent / "cisco_ios.yaml")
    resp = client.post("/api/v1/knowledge/rulepacks/import", files={"file": ("cisco_ios.rpk", bundle, "application/zip")})
    assert resp.status_code == 201
    assert resp.json()["signature_verified"] is True
    assert client.get("/api/v1/knowledge/rulepacks/cisco_ios/export").status_code == 200
    assert client.get("/api/v1/knowledge/rulepacks/cisco_ios/export/download").status_code == 200


@requires_db
def test_knowledge_controls_and_frameworks(db_conn) -> None:
    controls = client.get("/api/v1/knowledge/controls")
    assert controls.status_code == 200
    assert len(controls.json()["items"]) > 0  # M5: real controls, not one hardcoded entry

    assert client.get("/api/v1/knowledge/frameworks").status_code == 200
    # M5 (Phase 3 demo-rehearsal Bug 3): coverage for a framework with zero
    # imported items is a real 404, not the old hardcoded 0.82 payload for
    # any id (CIS import itself is out of this milestone's scope).
    assert client.get("/api/v1/knowledge/frameworks/cis/coverage").status_code == 404


@requires_db
def test_knowledge_framework_import_preview_ratify(db_conn) -> None:
    # M4: /frameworks/import is wired to real STIG XCCDF / NIST OSCAL
    # parsing (knowledge_import.stig_xccdf/nist_oscal) — `<x/>` is not a
    # valid XCCDF Benchmark and is correctly refused (422); real content
    # imports for real.
    rejected = client.post(
        "/api/v1/knowledge/frameworks/import",
        files={"file": ("stig.xml", b"<x/>", "application/xml")},
    )
    assert rejected.status_code == 422

    xccdf = b"""<?xml version="1.0"?>
<Benchmark xmlns="http://checklists.nist.gov/xccdf/1.1" id="xccdf_test">
  <version>1</version>
  <Group id="V-000001">
    <Rule id="SV-000001r_rule" severity="high">
      <title>Test rule</title>
      <check><check-content>Verify test condition.</check-content></check>
    </Rule>
  </Group>
</Benchmark>"""
    resp = client.post(
        "/api/v1/knowledge/frameworks/import",
        files={"file": ("stig.xml", xccdf, "application/xml")},
        params={"benchmark": "test_benchmark"},
    )
    assert resp.status_code == 201
    assert resp.json()["items_imported"] == 1

    items = client.get("/api/v1/knowledge/frameworks/stig/items")
    assert items.status_code == 200
    assert any(i["item_id"] == "V-000001" for i in items.json()["items"])

    # M5 (Phase 3 demo-rehearsal Bug 3): the imported content now actually
    # shows up in GET /knowledge/frameworks, and real coverage is
    # computable for it (not the old always-0.82 stub).
    listed_frameworks = client.get("/api/v1/knowledge/frameworks").json()["items"]
    assert any(f["framework"] == "stig" and f["benchmark"] == "test_benchmark" for f in listed_frameworks)
    coverage = client.get("/api/v1/knowledge/frameworks/stig/coverage")
    assert coverage.status_code == 200
    assert coverage.json()["total_recommendations"] == 1

    # /preview is honestly reduced (no versioned-snapshot history exists to
    # diff against), not the old fabricated `added: 6` example payload.
    preview = client.post("/api/v1/knowledge/frameworks/stig/preview")
    assert preview.status_code == 200
    assert preview.json()["current_item_count"] == 1
    assert preview.json()["content_changes"] is None
    assert client.post("/api/v1/knowledge/frameworks/nonexistent_framework_xyz/preview").status_code == 404

    ratify = client.post("/api/v1/knowledge/frameworks/stig/ratify")
    assert ratify.status_code == 200
    assert ratify.json()["status"] == "ratified"


def test_knowledge_schema_and_freshness() -> None:
    assert client.get("/api/v1/knowledge/schema").status_code == 200
    resp = client.post("/api/v1/knowledge/schema/register", json={"path": "x.y.z", "type": "boolean"})
    assert resp.status_code == 201
    assert client.get("/api/v1/knowledge/freshness").status_code == 200


# ---- Reports (M4: services/report_service.py, real gather+render+persist) -

import uuid as _uuid

from nsca_platform.db.models.campaign import campaign as _campaign_table
from nsca_platform.db.models.device import device as _device_table
from nsca_platform.db.models.finding import finding as _finding_table


def _seed_report_fixture(db_conn) -> tuple[str, str]:
    campaign_id = _uuid.uuid4()
    db_conn.execute(
        _campaign_table.insert().values(
            id=campaign_id, public_id="CMP-TEST-REPORTS-001", name="Report endpoint test",
            scope_definition={}, owner="tester", state="Review",
        )
    )
    device_id = _uuid.uuid4()
    db_conn.execute(
        _device_table.insert().values(id=device_id, hostname="RPT-ENDPOINT-SW-01", platform="cisco_iosxe")
    )
    db_conn.execute(
        _finding_table.insert().values(
            id=_uuid.uuid4(), public_id="F-TEST-ENDPOINT-001", campaign_id=campaign_id, device_id=device_id,
            control_id="NSCA-MGMT-001", verdict="PASS", severity_base="high", severity_effective="high",
            evidence=[], framework_refs=[], identity_key="RPT-ENDPOINT-SW-01:NSCA-MGMT-001",
        )
    )
    db_conn.commit()
    return "CMP-TEST-REPORTS-001", "RPT-ENDPOINT-SW-01"


@requires_db
def test_generate_and_get_report(db_conn) -> None:
    campaign_public_id, hostname = _seed_report_fixture(db_conn)
    gen = client.post(
        f"/api/v1/campaigns/{campaign_public_id}/reports/generate",
        params={"device": hostname, "mode": "issued"},
    )
    assert gen.status_code == 202
    report_id = gen.json()["report_id"]
    assert client.get(f"/api/v1/reports/{report_id}").status_code == 200


@requires_db
def test_list_reports(db_conn) -> None:
    # M5 (Phase 3 demo-rehearsal Bug 7): GET /reports previously didn't
    # exist at all — real query against the `report` table, optionally
    # filtered by campaign_id.
    campaign_public_id, hostname = _seed_report_fixture(db_conn)
    gen = client.post(
        f"/api/v1/campaigns/{campaign_public_id}/reports/generate",
        params={"device": hostname, "mode": "issued"},
    )
    report_id = gen.json()["report_id"]

    all_reports = client.get("/api/v1/reports")
    assert all_reports.status_code == 200
    assert any(r["id"] == report_id for r in all_reports.json()["items"])

    scoped = client.get("/api/v1/reports", params={"campaign_id": campaign_public_id})
    assert scoped.status_code == 200
    assert [r["id"] for r in scoped.json()["items"]] == [report_id]
    assert scoped.json()["items"][0]["device"] == hostname

    empty = client.get("/api/v1/reports", params={"campaign_id": "CMP-NOPE-999"})
    assert empty.status_code == 404


@requires_db
def test_download_report_all_formats(db_conn) -> None:
    campaign_public_id, hostname = _seed_report_fixture(db_conn)
    gen = client.post(
        f"/api/v1/campaigns/{campaign_public_id}/reports/generate",
        params={"device": hostname, "mode": "issued"},
    )
    report_id = gen.json()["report_id"]
    meta = client.get(f"/api/v1/reports/{report_id}").json()
    for fmt in meta["formats_available"]:
        resp = client.get(f"/api/v1/reports/{report_id}/download", params={"format": fmt})
        assert resp.status_code == 200, fmt
    # json/csv/oscal never depend on WeasyPrint's native libraries and must
    # always be present; pdf/docx are present whenever their renderer's
    # dependency is importable on this host.
    assert {"json", "csv", "oscal"} <= set(meta["formats_available"])


@requires_db
def test_report_manifest_verify_amend(db_conn) -> None:
    campaign_public_id, hostname = _seed_report_fixture(db_conn)
    gen = client.post(
        f"/api/v1/campaigns/{campaign_public_id}/reports/generate",
        params={"device": hostname, "mode": "issued"},
    )
    report_id = gen.json()["report_id"]
    assert client.get(f"/api/v1/reports/{report_id}/manifest").status_code == 200
    verify = client.post(f"/api/v1/reports/{report_id}/verify")
    assert verify.status_code == 200
    assert verify.json()["result"] == "MATCH"
    # Amendment (issued-report immutability + linked correction) remains
    # out of this milestone's scope — the M0 stub endpoint is still live.
    assert client.post(f"/api/v1/reports/{report_id}/amend", json={"note": "x"}).status_code == 200


def test_estate_report_and_export() -> None:
    assert client.get("/api/v1/campaigns/CMP-2026Q3-001/reports/estate").status_code == 200
    assert client.get("/api/v1/campaigns/CMP-2026Q3-001/export").status_code == 200


# ---- Admin --------------------------------------------------------------

@requires_db
def test_admin_users_requires_platform_administrator(db_conn) -> None:
    forbidden = client.get("/api/v1/admin/users", headers=LEAD)
    assert forbidden.status_code == 403
    ok = client.get("/api/v1/admin/users", headers=PLATFORM_ADMIN)
    assert ok.status_code == 200
    assert ok.json()["items"] == []  # M5: real DB-backed, empty until a user is created

    created = client.post(
        "/api/v1/admin/users",
        json={"name": "New User", "email": "new-user@example.invalid", "role": "assessor"},
        headers=PLATFORM_ADMIN,
    )
    assert created.status_code == 201
    assert created.json()["name"] == "New User"

    # Real persistence, not a fabricated response — the created user is
    # actually there on the next list call.
    listed = client.get("/api/v1/admin/users", headers=PLATFORM_ADMIN)
    assert any(u["email"] == "new-user@example.invalid" for u in listed.json()["items"])


def test_admin_roles() -> None:
    resp = client.get("/api/v1/admin/roles")
    assert resp.status_code == 200
    keys = {r["key"] for r in resp.json()["items"]}
    assert keys == {"assessor", "lead_assessor", "network_administrator", "platform_administrator", "read_only"}


@requires_db
def test_admin_credentials_requires_network_administrator_and_never_returns_secret(db_conn) -> None:
    forbidden = client.get("/api/v1/admin/credentials", headers=LEAD)
    assert forbidden.status_code == 403
    ok = client.get("/api/v1/admin/credentials", headers=NET_ADMIN)
    assert ok.status_code == 200
    for item in ok.json()["items"]:
        assert "secret" not in item and "password" not in item

    # A caller-submitted secret must never be persisted or echoed back —
    # NFR-SEC-003, enforced by construction (admin_credential has no
    # column that could hold one; see services/admin_service.py).
    created = client.post(
        "/api/v1/admin/credentials",
        json={"label": "test-cred", "type": "ssh_keypair", "secret": "hunter2-should-never-be-stored"},
        headers=NET_ADMIN,
    )
    assert created.status_code == 201
    body = created.json()
    assert "secret" not in body and "password" not in body and "reference" not in body

    listed = client.get("/api/v1/admin/credentials", headers=NET_ADMIN).json()["items"]
    assert any(c["label"] == "test-cred" for c in listed)
    for item in listed:
        assert "secret" not in item and "password" not in item and "reference" not in item

    from nsca_platform.db.models.admin import admin_credential as _admin_credential_table

    rows = db_conn.execute(_admin_credential_table.select()).fetchall()
    for r in rows:
        assert "hunter2-should-never-be-stored" not in (r.reference or "")


@requires_db
def test_admin_audit_log(db_conn) -> None:
    resp = client.get("/api/v1/admin/audit-log")
    assert resp.status_code == 200
    assert "items" in resp.json()


@requires_db
def test_admin_audit_log_verify_real(db_conn) -> None:
    # M5: `/admin/audit-log/verify` is real hash-chain verification
    # (`audit.log.verify_chain`, see nsca_platform/tests/test_audit_log_verify.py
    # for the dedicated tamper-detection coverage) — no longer the M0
    # static-literal stub, so this just checks the documented response
    # shape rather than a hardcoded `entries_checked` value.
    resp = client.get("/api/v1/admin/audit-log/verify", headers=PLATFORM_ADMIN)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"entries_checked", "chain_intact", "first_break"}
    assert isinstance(body["chain_intact"], bool)


def test_admin_health_and_status() -> None:
    assert client.get("/api/v1/admin/health").status_code == 200
    assert client.get("/api/v1/admin/status").status_code == 200


def test_unknown_dev_role_header_rejected() -> None:
    resp = client.get("/api/v1/campaigns", headers={"X-Dev-Role": "superuser"})
    assert resp.status_code == 400
