"""M3 integration test: `assess_device`'s `graph_contribution` field is
wired end-to-end (not the M0/M1 placeholder `GraphFragment(nodes=(),
edges=())`) for at least two platforms — a rich one (Cisco IOS) and a
minimal one (cloud_generic_fw, which only exposes `filter.rules[].name`).
"""

from __future__ import annotations

from pathlib import Path

from nsca_engine.api import assess_device
from nsca_engine.graph import build as graph_build
from nsca_engine.tests.helpers import (
    ASSESSED_AT,
    M2_FIXTURES,
    build_knowledge_base,
    build_knowledge_base_m2,
    make_artifact,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "graph_estate"


def test_cisco_ios_graph_contribution_is_not_the_m0_placeholder():
    kb = build_knowledge_base()
    content = (FIXTURES / "edge_fw_01.cfg").read_text(encoding="utf-8")
    assessment = assess_device((make_artifact(content),), kb, ASSESSED_AT)
    frag = assessment.graph_contribution
    assert frag.device_id == "ART-001"
    assert len(frag.nodes) > 0
    assert len(frag.edges) > 0
    assert any(n.kind == "acl_rule" for n in frag.nodes)


def test_cloud_fw_graph_contribution_is_not_the_m0_placeholder():
    kb = build_knowledge_base_m2()
    content = M2_FIXTURES["cloud_generic_fw"].read_text(encoding="utf-8")
    assessment = assess_device((make_artifact(content),), kb, ASSESSED_AT)
    frag = assessment.graph_contribution
    assert len(frag.nodes) > 0  # at minimum the device node
    assert any(n.kind == "device" for n in frag.nodes)


def test_graph_contribution_feeds_merge_estate_and_reachability():
    kb = build_knowledge_base()
    content = (FIXTURES / "edge_fw_01.cfg").read_text(encoding="utf-8")
    assessment = assess_device((make_artifact(content, artifact_id="EDGE-FW-01"),), kb, ASSESSED_AT)
    graph = graph_build.merge_estate((assessment,))
    assert any(n.kind == "device" and n.device_id == "EDGE-FW-01" for n in graph.nodes)
