"""Report service — real DB-backed gather/generate/download/verify,
backend-02 §4.6, M4. Complements `test_report_determinism.py` (which uses
a hand-built `DeviceReportData` fixture with no DB dependency): this file
exercises `services/report_service.py`'s DB-gathering path specifically.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from nsca_platform.db.models.campaign import campaign as campaign_table
from nsca_platform.db.models.device import device as device_table
from nsca_platform.db.models.finding import finding as finding_table
from nsca_platform.services import report_service
from nsca_platform.tests.conftest import requires_db


def _seed_campaign_and_device(db_conn, *, state: str = "Review") -> tuple[str, str]:
    campaign_id = uuid.uuid4()
    db_conn.execute(
        campaign_table.insert().values(
            id=campaign_id, public_id="CMP-TEST-RPT-001", name="Report service test campaign",
            scope_definition={}, owner="tester", state=state,
            frameworks=[{"framework": "cis", "version": "4.1.0"}],
            knowledge_base_pin={
                "engine": "v2.4.0",
                "rulepacks": [{"id": "cisco_iosxe", "version": "7.2.1", "tier": "certified"}],
                "control_packs": [{"id": "nsca-core", "version": "3.1.0"}],
            },
        )
    )
    device_id = uuid.uuid4()
    db_conn.execute(
        device_table.insert().values(
            id=device_id, hostname="RPT-TEST-SW-01", platform="cisco_iosxe", os_version="16.12.04",
            model="Catalyst 9300", serials=[{"component": "Chassis", "serial": "TEST123"}],
        )
    )
    db_conn.execute(
        finding_table.insert().values(
            id=uuid.uuid4(), public_id="F-TEST-000001", campaign_id=campaign_id, device_id=device_id,
            control_id="NSCA-MGMT-002", verdict="FAIL", severity_base="high", severity_effective="high",
            evidence=[{"artifact": "running-config.txt", "lines": [1, 2], "highlight": [1],
                       "excerpt": "line vty 0 4\n transport input telnet ssh", "facts": []}],
            framework_refs=[{"framework": "cis", "id": "CIS-IOS-1.2.4"}],
            identity_key="RPT-TEST-SW-01:NSCA-MGMT-002", rulepack_trust_tier="certified",
        )
    )
    db_conn.execute(
        finding_table.insert().values(
            id=uuid.uuid4(), public_id="F-TEST-000002", campaign_id=campaign_id, device_id=device_id,
            control_id="NSCA-MGMT-001", verdict="PASS", severity_base="high", severity_effective="high",
            evidence=[], framework_refs=[], identity_key="RPT-TEST-SW-01:NSCA-MGMT-001",
            rulepack_trust_tier="certified",
        )
    )
    db_conn.commit()
    return "CMP-TEST-RPT-001", "RPT-TEST-SW-01"


@requires_db
def test_gather_device_report_data_from_stored_rows(db_conn) -> None:
    from datetime import datetime, timezone

    campaign_public_id, hostname = _seed_campaign_and_device(db_conn)
    data = report_service.gather_device_report_data(
        db_conn, campaign_public_id, hostname, report_id="RPT-TEST-001",
        generated_at=datetime(2026, 9, 12, tzinfo=timezone.utc),
    )
    assert data.device.hostname == hostname
    assert len(data.findings) == 2
    fail_finding = next(f for f in data.findings if f.verdict == "FAIL")
    assert fail_finding.control_id == "NSCA-MGMT-002"
    assert fail_finding.artifact_filename == "running-config.txt"
    assert data.scores.pass_count == 1
    assert data.scores.fail_count == 1


@requires_db
def test_generate_download_verify_round_trip(db_conn) -> None:
    campaign_public_id, hostname = _seed_campaign_and_device(db_conn, state="Review")

    result = report_service.generate_report(db_conn, campaign_public_id, hostname, mode="issued", actor="tester")
    db_conn.commit()
    assert result["status"] == "generated"
    assert "json" in result["formats_available"]
    assert "csv" in result["formats_available"]
    assert "oscal" in result["formats_available"]

    report_id = result["id"]
    meta = report_service.get_report_meta(db_conn, report_id)
    assert meta["device"] == hostname

    json_bytes = report_service.download_report_bytes(db_conn, report_id, "json")
    import json as jsonmod

    payload = jsonmod.loads(json_bytes)
    assert payload["report_id"] == report_id
    assert payload["device"]["hostname"] == hostname

    manifest = report_service.get_manifest(db_conn, report_id)
    assert manifest["report_id"] == report_id
    assert manifest["report_hash"] == result["hash"]

    verify_result = report_service.verify_report(db_conn, report_id, actor="tester")
    db_conn.commit()
    assert verify_result["result"] == "MATCH"
    assert verify_result["original_hash"] == verify_result["recomputed_hash"]


@requires_db
def test_issued_generation_refused_for_draft_campaign(db_conn) -> None:
    campaign_public_id, hostname = _seed_campaign_and_device(db_conn, state="Draft")
    with pytest.raises(report_service.CampaignNotIssuable):
        report_service.generate_report(db_conn, campaign_public_id, hostname, mode="issued", actor="tester")


@requires_db
def test_draft_generation_allowed_for_draft_campaign(db_conn) -> None:
    campaign_public_id, hostname = _seed_campaign_and_device(db_conn, state="Draft")
    result = report_service.generate_report(db_conn, campaign_public_id, hostname, mode="draft", actor="tester")
    db_conn.commit()
    assert result["status"] == "generated"


@requires_db
def test_provisional_finding_excluded_from_issued_report(db_conn) -> None:
    campaign_public_id, hostname = _seed_campaign_and_device(db_conn, state="Review")
    campaign_row = db_conn.execute(
        select(campaign_table).where(campaign_table.c.public_id == campaign_public_id)
    ).first()
    device_row = db_conn.execute(select(device_table).where(device_table.c.hostname == hostname)).first()
    db_conn.execute(
        finding_table.insert().values(
            id=uuid.uuid4(), public_id="F-TEST-000003", campaign_id=campaign_row.id, device_id=device_row.id,
            control_id="NSCA-CRYPTO-001", verdict="FAIL", severity_base="critical", severity_effective="critical",
            evidence=[], framework_refs=[], identity_key=f"{hostname}:NSCA-CRYPTO-001",
            rulepack_trust_tier="provisional",  # excluded from issued reports (INV-08.3-04 / DM-5)
        )
    )
    db_conn.commit()

    issued = report_service.generate_report(db_conn, campaign_public_id, hostname, mode="issued", actor="tester")
    db_conn.commit()
    issued_json = report_service.download_report_bytes(db_conn, issued["id"], "json")
    import json as jsonmod

    issued_control_ids = {f["control_id"] for f in jsonmod.loads(issued_json)["findings"]}
    assert "NSCA-CRYPTO-001" not in issued_control_ids

    draft = report_service.generate_report(db_conn, campaign_public_id, hostname, mode="draft", actor="tester")
    db_conn.commit()
    draft_json = report_service.download_report_bytes(db_conn, draft["id"], "json")
    draft_control_ids = {f["control_id"] for f in jsonmod.loads(draft_json)["findings"]}
    assert "NSCA-CRYPTO-001" in draft_control_ids
