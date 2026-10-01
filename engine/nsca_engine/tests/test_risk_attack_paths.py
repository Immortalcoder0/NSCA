"""Unit tests for `risk/attack_paths.py` beyond the AP-003 acceptance test
(`test_assess_campaign_ap003.py`)."""

from __future__ import annotations

from pathlib import Path

from nsca_engine.api import assess_device
from nsca_engine.graph import build as graph_build
from nsca_engine.graph import exposure as graph_exposure
from nsca_engine.risk import attack_paths as risk_attack_paths
from nsca_engine.tests.helpers import ASSESSED_AT, build_knowledge_base, make_artifact

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "graph_estate"


def test_no_reachable_path_yields_no_attack_paths():
    """§5 edge case: no reachable paths -> empty result (INV-06.2-01: never
    inferred from findings alone)."""

    kb = build_knowledge_base()
    content = (FIXTURES / "core_b.cfg").read_text(encoding="utf-8")
    assessment = assess_device((make_artifact(content, artifact_id="CORE-B"),), kb, ASSESSED_AT)
    graph = graph_build.merge_estate((assessment,))
    exposures = graph_exposure.classify_estate(graph)

    paths = risk_attack_paths.compute_attack_paths((assessment,), graph, exposures)
    assert paths == ()


def test_attack_path_ids_are_deterministic_across_runs():
    kb = build_knowledge_base()
    edge = assess_device(
        (make_artifact((Path(__file__).resolve().parent / "fixtures" / "ap003" / "edge_fw_01.cfg")
                        .read_text(encoding="utf-8"), artifact_id="EDGE-FW-01"),),
        kb, ASSESSED_AT,
    )
    core = assess_device(
        (make_artifact((Path(__file__).resolve().parent / "fixtures" / "ap003" / "core_sw_01.cfg")
                        .read_text(encoding="utf-8"), artifact_id="CORE-SW-01"),),
        kb, ASSESSED_AT,
    )
    graph = graph_build.merge_estate((edge, core))
    exposures = graph_exposure.classify_estate(graph)

    first = risk_attack_paths.compute_attack_paths((edge, core), graph, exposures)
    second = risk_attack_paths.compute_attack_paths((core, edge), graph, exposures)  # shuffled order
    assert first == second
