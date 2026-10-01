"""M5 — real `nsca_engine.api` calls replacing fixture/heuristic call
sites, end to end through the real HTTP API (backend-02 §5 M5 task items
1-3): `knowledge_base_loader` builds a real `KnowledgeBase` from
`nsca/knowledge/`; `services/ingestion.py._fingerprint` calls the real
`fingerprint_artifact` before falling back to its local heuristic;
`services/assessment.py.run_assessment` calls the real `assess_device`
over real uploaded artifact bytes before falling back to
`_fixture_device_assessment`.

Uses the same real, corpus-realistic Cisco IOS config the engine's own
M3 graph-integration/reachability acceptance tests use
(`engine/nsca_engine/tests/fixtures/ap003/core_sw_01.cfg`) — read from
disk with a graceful skip if this checkout's layout doesn't have it,
rather than duplicating its text here and risking silent drift from the
engine's own worked example. The uploaded hostname is deliberately
`REAL-IOS-01`, not `CORE-SW-01` — `services/assessment.py`'s
`_FIXTURES_BY_HOSTNAME` fixture dict special-cases `CORE-SW-01`, and using
a different hostname makes it unambiguous that a *real* `assess_device`
result, not a name-matched fixture, produced the assessment these tests
check.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nsca_platform.main import app
from nsca_platform.services import ingestion as ingestion_service
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


def _real_ios_config(hostname: str = "REAL-IOS-01") -> bytes:
    text = _ENGINE_FIXTURE.read_text(encoding="utf-8")
    text = text.replace("hostname CORE-SW-01", f"hostname {hostname}")
    return text.encode("utf-8")


# ---------------------------------------------------------------------------
# Item 2 — real fingerprinting in ingestion
# ---------------------------------------------------------------------------


def test_engine_fingerprint_identifies_real_cisco_ios_config() -> None:
    """Direct proof the real engine path fires (not the heuristic) for a
    real corpus config: `_try_engine_fingerprint` returns non-`None`."""

    content = _real_ios_config()
    result = ingestion_service._try_engine_fingerprint(content)
    assert result is not None
    assert result["platform"] == "cisco_ios"
    assert result["vendor"] == "cisco"


def test_fingerprint_prefers_engine_over_heuristic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patches the heuristic to explode if called — proves `_fingerprint`
    never reaches it for a real, confidently-identifiable config."""

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("heuristic fingerprint should not be called for a real, KNOWN config")

    monkeypatch.setattr(ingestion_service, "_heuristic_fingerprint", _boom)
    content = _real_ios_config()
    text = ingestion_service._decode(content)
    fp = ingestion_service._fingerprint(content, text, "real-ios-01.cfg")
    assert fp["platform"] == "cisco_ios"
    assert fp["vendor"] == "cisco"


@requires_db
def test_upload_real_cisco_ios_config_is_fingerprinted_by_real_engine(db_conn) -> None:
    """End to end through the real HTTP API: the real engine, not the
    heuristic, classifies a real corpus config."""

    created = _create_test_campaign(name="real engine fingerprint test")
    resp = client.post(
        f"/api/v1/campaigns/{created['id']}/artifacts",
        files=[("files", ("real-ios-01.cfg", _real_ios_config(), "text/plain"))],
    )
    assert resp.status_code == 201, resp.text
    result = resp.json()["results"][0]
    assert result["platform"] == "cisco_ios"
    # This corpus fixture has no verbose-export markers, so it lands in the
    # `parsed_with_caveat` branch (whose response shape doesn't echo
    # `device` — only the `parsed`/verbose branch does; see
    # services/ingestion.py._classify_and_persist). The real device
    # correlation still happened underneath either way — proven by item 3's
    # end-to-end assess_device test below, which queries the persisted
    # assessment for this exact hostname.
    assert result["status"] in ("parsed", "parsed_with_caveat")


# ---------------------------------------------------------------------------
# Item 3 — real assess_device/assess_campaign in the worker pipeline
# ---------------------------------------------------------------------------


@requires_db
def test_real_uploaded_cisco_ios_config_produces_real_assess_device_result(db_conn) -> None:
    """The headline M5 proof: upload a real config, run the assessment
    worker over the real HTTP API, and confirm the persisted assessment is
    a *real* `assess_device` result — not `_fixture_device_assessment`'s
    generic single-PASS fallback (grammar_coverage=0.5, one PASS finding,
    `rulepacks_used[0].version == "fixture"`) and not a name-matched
    fixture (this hostname isn't `CORE-SW-01`/`MGMT-SW-04`).
    """

    created = _create_test_campaign(
        name="real engine assess_device test",
        scope={"type": "explicit", "devices": ["REAL-IOS-01"]},
    )
    upload = client.post(
        f"/api/v1/campaigns/{created['id']}/artifacts",
        files=[("files", ("real-ios-01.cfg", _real_ios_config(), "text/plain"))],
    )
    assert upload.status_code == 201, upload.text

    assess = client.post(f"/api/v1/campaigns/{created['id']}/assess")
    assert assess.status_code == 202, assess.text
    assessment_ids = assess.json()["assessments"]
    assert assessment_ids

    body = client.get(f"/api/v1/assessments/{assessment_ids[0]}").json()
    assert body["device"] == "REAL-IOS-01"
    assert body["platform"] == "cisco_ios"
    # A real assess_device run over this config produces >1 findings across
    # many native controls and full grammar coverage — nothing like the
    # generic fixture's single PASS at 0.5 coverage.
    assert body["grammar_coverage"] is not None
    assert body["grammar_coverage"] > 0.9
    total_findings = sum(body["counts"].get(k, 0) for k in ("pass", "fail", "unknown", "not_applicable"))
    assert total_findings > 5
    assert body["rulepacks_used"]
    assert body["rulepacks_used"][0]["version"] != "fixture"

    findings = client.get(f"/api/v1/campaigns/{created['id']}/findings").json()["items"]
    assert findings
    assert not any(f.get("evidence") and f["evidence"][0].get("artifact_id") == "ART-GENERIC" for f in findings)
