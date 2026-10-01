"""M4 determinism test: `assess_campaign` run twice over the same
`DeviceAssessment`s (and once more with the input order shuffled) produces
byte-for-byte identical `CampaignAssessment` output (backend-01 §2.1, D1/D6;
same obligation the M3 report already exercised for the graph layer)."""

from __future__ import annotations

from pathlib import Path

from nsca_engine.api import assess_campaign, assess_device
from nsca_engine.tests.fixtures.branch_routers import branch_router_fleet
from nsca_engine.tests.helpers import ASSESSED_AT, build_knowledge_base, make_artifact

AP003_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ap003"


def _ap003_assessments(kb):
    edge = assess_device(
        (make_artifact((AP003_FIXTURES / "edge_fw_01.cfg").read_text(encoding="utf-8"), artifact_id="EDGE-FW-01"),),
        kb, ASSESSED_AT,
    )
    core = assess_device(
        (make_artifact((AP003_FIXTURES / "core_sw_01.cfg").read_text(encoding="utf-8"), artifact_id="CORE-SW-01"),),
        kb, ASSESSED_AT,
    )
    return edge, core


def test_assess_campaign_is_byte_identical_across_runs():
    kb = build_knowledge_base()
    edge, core = _ap003_assessments(kb)

    first = assess_campaign((edge, core), kb)
    second = assess_campaign((edge, core), kb)
    third = assess_campaign((core, edge), kb)  # shuffled device order

    assert first == second == third
    assert repr(first) == repr(second) == repr(third)


def test_assess_campaign_is_byte_identical_on_larger_fleet():
    kb = build_knowledge_base()
    fleet = branch_router_fleet(total=40, defective=31)
    assessments = tuple(
        assess_device((make_artifact(cfg, artifact_id=device_id),), kb, ASSESSED_AT)
        for device_id, cfg in fleet
    )

    first = assess_campaign(assessments, kb)
    second = assess_campaign(tuple(reversed(assessments)), kb)

    assert first == second
    assert repr(first) == repr(second)
