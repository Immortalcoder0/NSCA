"""Chassis-serial extraction end to end through the real HTTP API (Phase 3
demo rehearsal finding 7, §9 checklist item 5): a real `show inventory`
artifact uploaded alongside a device's running-config (FR-ING-010's
directory-per-device multi-artifact ingestion) must produce real serials on
the persisted device/assessment — not the "NOT DETERMINED" the rehearsal
found live.

Uses the same real corpus Cisco IOS config `test_real_engine_wiring.py`
uses, paired with a hand-written but realistic `show inventory` artifact in
the exact format `nsca_engine/extract/cisco_inventory.py` parses.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nsca_platform.main import app
from nsca_platform.tests.conftest import requires_db
from nsca_platform.tests.test_stub_endpoints import _create_test_campaign

client = TestClient(app)

_ENGINE_FIXTURE = (
    Path(__file__).resolve().parents[3] / "engine" / "nsca_engine" / "tests" / "fixtures" / "ap003" / "core_sw_01.cfg"
)

pytestmark = pytest.mark.skipif(
    not _ENGINE_FIXTURE.exists(),
    reason=f"engine corpus fixture not found at {_ENGINE_FIXTURE} in this checkout layout",
)

SHOW_INVENTORY_TEXT = (
    'NAME: "1", DESCR: "WS-C3850-24T-E"\n'
    "PID: WS-C3850-24T-E   , VID: V04  , SN: FCW2140L0GH\n"
    "\n"
    'NAME: "StackPort1", DESCR: "StackPort1"\n'
    "PID: STACK-T1-50CM    , VID: V01  , SN: FOC2138Y0K2\n"
    "\n"
    'NAME: "Power Supply 1", DESCR: "Power Supply 1"\n'
    "PID: PWR-C1-350WAC     , VID: V01  , SN: ART2137F0PL\n"
)


def _real_ios_config(hostname: str) -> bytes:
    text = _ENGINE_FIXTURE.read_text(encoding="utf-8")
    text = text.replace("hostname CORE-SW-01", f"hostname {hostname}")
    return text.encode("utf-8")


@requires_db
def test_upload_running_config_and_show_inventory_produces_real_serials(db_conn) -> None:
    hostname = "SERIAL-IOS-01"
    created = _create_test_campaign(
        name="chassis serial wiring test",
        scope={"type": "explicit", "devices": [hostname]},
    )
    upload = client.post(
        f"/api/v1/campaigns/{created['id']}/artifacts",
        files=[
            ("files", (f"{hostname}/running-config.txt", _real_ios_config(hostname), "text/plain")),
            ("files", (f"{hostname}/show-inventory.txt", SHOW_INVENTORY_TEXT.encode("utf-8"), "text/plain")),
        ],
    )
    assert upload.status_code == 201, upload.text
    statuses = {r["status"] for r in upload.json()["results"]}
    # Both artifacts must correlate to one device — proven below by both
    # ending up on the same assessment/device row, matching the rehearsal's
    # own "multi-artifact correlation itself works" observation.
    assert statuses <= {"parsed", "parsed_with_caveat"}

    assess = client.post(f"/api/v1/campaigns/{created['id']}/assess")
    assert assess.status_code == 202, assess.text
    assessment_ids = assess.json()["assessments"]
    assert assessment_ids

    body = client.get(f"/api/v1/assessments/{assessment_ids[0]}").json()
    assert body["device"] == hostname

    # The exact bug: previously `serials` was always `[]` — chassis serial
    # was "not extracted anywhere in this package". Now it's real, from the
    # real show-inventory artifact uploaded above.
    assert body["serials"], "device.serials should be populated from the real show-inventory artifact"
    serial_values = {s["serial"] for s in body["serials"]}
    assert serial_values == {"FCW2140L0GH", "FOC2138Y0K2", "ART2137F0PL"}
