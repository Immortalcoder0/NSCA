"""M3 unit tests for `graph/exposure.py` (TRD-04.1 §3.6)."""

from __future__ import annotations

from pathlib import Path

from nsca_engine.api import assess_device
from nsca_engine.graph import build as graph_build
from nsca_engine.graph import exposure
from nsca_engine.tests.helpers import ASSESSED_AT, build_knowledge_base, make_artifact

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "graph_estate"
_KB = build_knowledge_base()


_DEVICE_IDS = {
    "edge_fw_01.cfg": "EDGE-FW-01",
    "gate_p.cfg": "GATE-P", "core_p.cfg": "CORE-P", "srv_p.cfg": "SRV-P",
    "gate_b.cfg": "GATE-B", "core_b.cfg": "CORE-B", "srv_b.cfg": "SRV-B",
}


def _assess(filename: str):
    content = (FIXTURES / filename).read_text(encoding="utf-8")
    device_id = _DEVICE_IDS[filename]
    return assess_device((make_artifact(content, artifact_id=device_id),), _KB, ASSESSED_AT)


def test_edge_device_with_external_interface_is_internet_facing():
    assessment = _assess("edge_fw_01.cfg")
    graph = graph_build.merge_estate((assessment,))
    result = exposure.classify_device(graph, "EDGE-FW-01")
    assert result.classification == "internet_facing"
    assert result.confidence == "high"
    assert result.basis


def test_internal_only_device_is_internal():
    devices = [_assess(f) for f in ("gate_p.cfg", "core_p.cfg", "srv_p.cfg")]
    graph = graph_build.merge_estate(devices)
    result = exposure.classify_device(graph, "SRV-P")
    assert result.classification == "internal"


def test_gate_device_with_external_interface_is_internet_facing():
    devices = [_assess(f) for f in ("gate_p.cfg", "core_p.cfg", "srv_p.cfg")]
    graph = graph_build.merge_estate(devices)
    result = exposure.classify_device(graph, "GATE-P")
    assert result.classification == "internet_facing"


def test_device_with_no_graph_presence_is_internal_low_confidence():
    devices = [_assess("srv_p.cfg")]
    graph = graph_build.merge_estate(devices)
    result = exposure.classify_device(graph, "NONEXISTENT-DEVICE")
    assert result.classification == "internal"
    assert result.confidence == "low"


def test_classify_estate_covers_every_device_sorted():
    devices = [_assess(f) for f in ("srv_p.cfg", "gate_p.cfg", "core_p.cfg")]
    graph = graph_build.merge_estate(devices)
    results = exposure.classify_estate(graph)
    assert sorted(results) == ["CORE-P", "GATE-P", "SRV-P"]
    assert results["GATE-P"].classification == "internet_facing"
    assert results["SRV-P"].classification == "internal"


def test_ambiguous_exposure_never_defaults_to_isolated():
    # Hand-built graph: a device with routes but no zone information at all
    # (TRD-04.1 §3.6 / V-04.1-008 — ambiguity must never resolve to the
    # *safest-looking* classification).
    from nsca_engine.api import Graph
    from nsca_engine.types import GraphNode

    graph = Graph(
        nodes=(
            GraphNode(node_id="X:device:X", device_id="X", kind="device", attrs={}),
            GraphNode(
                node_id="X:route:0.0.0.0/0:1.2.3.4", device_id="X", kind="route",
                attrs={"destination": "0.0.0.0/0", "next_hop": "1.2.3.4"},
            ),
        ),
        edges=(),
    )
    result = exposure.classify_device(graph, "X")
    assert result.classification != "isolated"
    assert result.classification == "internet_facing"
