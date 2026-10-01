"""M3 acceptance tests: the canonical counterexample from
04-system-architecture.md §4.5 (Trusted-Admins -> Partners -> 0.0.0.0/0),
plus fully-blocked and fully-permitted multi-device reachability scenarios.
"""

from __future__ import annotations

from pathlib import Path

from nsca_engine.api import assess_device
from nsca_engine.graph import build as graph_build
from nsca_engine.graph import reachability
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


def test_canonical_counterexample_reproduced_exactly():
    """04-system-architecture.md §4.5:

    > 203.0.113.5:44210 -> 10.0.0.1:22 TCP permitted via rule `outside-in`
    > line 14, because group `Trusted-Admins` -> group `Partners` ->
    > `0.0.0.0/0`
    """

    assessment = _assess("edge_fw_01.cfg")
    graph = graph_build.merge_estate((assessment,))

    result = reachability.query(
        graph, src_addr="203.0.113.5", dst_addr="10.0.0.1", protocol="tcp", dport=22,
    )

    assert result.outcome == "reachable"
    ce = result.counterexample
    assert ce is not None
    assert ce.src_addr == "203.0.113.5"
    assert ce.src_port == 44210
    assert ce.dst_addr == "10.0.0.1"
    assert ce.dst_port == 22
    assert ce.protocol == "tcp"

    assert len(ce.chain) == 1
    step = ce.chain[0]
    assert step.device_id == "EDGE-FW-01"
    assert step.rule_ref == "acl[outside-in] line 14"
    assert step.action == "permit"
    assert step.detail == "Trusted-Admins -> Partners -> 0.0.0.0/0"

    assert ce.summary() == (
        "203.0.113.5:44210 -> 10.0.0.1:22 TCP permitted via "
        "EDGE-FW-01 rule acl[outside-in] line 14, "
        "because group Trusted-Admins -> Partners -> 0.0.0.0/0"
    )


def test_canonical_counterexample_via_zone_query():
    assessment = _assess("edge_fw_01.cfg")
    graph = graph_build.merge_estate((assessment,))
    result = reachability.query_zone(graph, "external", "10.0.0.1", "tcp", 22)
    assert result.outcome == "reachable"
    assert result.counterexample.src_addr == "203.0.113.5"


def test_fully_permitted_three_device_chain():
    devices = [_assess(f) for f in ("gate_p.cfg", "core_p.cfg", "srv_p.cfg")]
    graph = graph_build.merge_estate(devices)
    result = reachability.query(
        graph, src_addr="203.0.113.9", dst_addr="10.10.1.5", protocol="tcp", dport=443,
    )
    assert result.outcome == "reachable"
    assert result.counterexample is not None
    assert result.counterexample.chain == ()  # no ACLs anywhere on the path
    assert result.search_stats.nodes_visited == 3


def test_fully_blocked_three_device_chain():
    devices = [_assess(f) for f in ("gate_b.cfg", "core_b.cfg", "srv_b.cfg")]
    graph = graph_build.merge_estate(devices)
    result = reachability.query(
        graph, src_addr="203.0.113.9", dst_addr="10.20.1.5", protocol="tcp", dport=443,
    )
    assert result.outcome == "unreachable"
    assert result.counterexample is None
    assert any("CORE-B" in a for a in result.assumptions)


def test_denied_traffic_carries_no_counterexample():
    assessment = _assess("edge_fw_01.cfg")
    graph = graph_build.merge_estate((assessment,))
    # Same rule chain, but a destination port the ACL does not permit.
    result = reachability.query(
        graph, src_addr="203.0.113.5", dst_addr="10.0.0.1", protocol="tcp", dport=23,
    )
    assert result.outcome == "unreachable"
    assert result.counterexample is None
