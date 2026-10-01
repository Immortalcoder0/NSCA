"""M3 determinism (G1, D6, INV-04.1-02): assessing the same estate twice
produces a byte-identical merged `Graph` — same node/edge ordering, same
node identities, regardless of the order devices are handed to
`merge_estate` (V-04.1-006 shuffled-ordering intent, scaled down from
"10 runs / 1000 devices" to what a unit test can assert)."""

from __future__ import annotations

from pathlib import Path

from nsca_engine.api import assess_device
from nsca_engine.graph import build as graph_build
from nsca_engine.tests.helpers import ASSESSED_AT, build_knowledge_base, make_artifact

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "graph_estate"
_DEVICE_IDS = {
    "gate_p.cfg": "GATE-P", "core_p.cfg": "CORE-P", "srv_p.cfg": "SRV-P",
}


def _assess_all(kb):
    out = []
    for filename, device_id in _DEVICE_IDS.items():
        content = (FIXTURES / filename).read_text(encoding="utf-8")
        out.append(assess_device((make_artifact(content, artifact_id=device_id),), kb, ASSESSED_AT))
    return out


def test_merged_graph_is_byte_identical_across_independent_runs():
    kb1 = build_knowledge_base()
    kb2 = build_knowledge_base()  # independently re-loaded from disk

    devices1 = _assess_all(kb1)
    devices2 = _assess_all(kb2)

    graph1 = graph_build.merge_estate(devices1)
    graph2 = graph_build.merge_estate(devices2)

    assert repr(graph1.nodes) == repr(graph2.nodes)
    assert repr(graph1.edges) == repr(graph2.edges)
    assert graph1 == graph2


def test_merged_graph_is_order_independent():
    kb = build_knowledge_base()
    devices = _assess_all(kb)

    forward = graph_build.merge_estate(devices)
    shuffled = graph_build.merge_estate(tuple(reversed(devices)))

    assert repr(forward.nodes) == repr(shuffled.nodes)
    assert repr(forward.edges) == repr(shuffled.edges)


def test_node_and_edge_ordering_is_sorted():
    kb = build_knowledge_base()
    devices = _assess_all(kb)
    graph = graph_build.merge_estate(devices)

    node_ids = [n.node_id for n in graph.nodes]
    assert node_ids == sorted(node_ids)

    edge_keys = [(e.source_id, e.target_id, e.kind) for e in graph.edges]
    assert edge_keys == sorted(edge_keys)
