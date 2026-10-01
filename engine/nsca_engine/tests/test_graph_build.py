"""M3 unit tests for `graph/build.py`: per-device graph contribution
correctness (Cisco IOS rich path + minimal path for other platforms) and
estate merge.
"""

from __future__ import annotations

from pathlib import Path

from nsca_engine.api import assess_device
from nsca_engine.graph import build as graph_build
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


def test_cisco_object_group_nesting_is_captured():
    assessment = _assess("edge_fw_01.cfg")
    frag = assessment.graph_contribution
    by_id = {n.node_id: n for n in frag.nodes}

    trusted_admins = by_id["EDGE-FW-01:address_object:Trusted-Admins"]
    partners = by_id["EDGE-FW-01:address_object:Partners"]
    literal = by_id["EDGE-FW-01:literal:0.0.0.0/0"]
    assert trusted_admins.kind == "address_object"
    assert partners.kind == "address_object"
    assert literal.kind == "literal"

    member_edges = {(e.source_id, e.target_id, e.kind) for e in frag.edges}
    assert (
        "EDGE-FW-01:address_object:Trusted-Admins",
        "EDGE-FW-01:address_object:Partners",
        "member_of",
    ) in member_edges
    assert (
        "EDGE-FW-01:address_object:Partners",
        "EDGE-FW-01:literal:0.0.0.0/0",
        "member_of",
    ) in member_edges


def test_cisco_acl_rule_expands_source_chain():
    assessment = _assess("edge_fw_01.cfg")
    frag = assessment.graph_contribution
    rule = next(n for n in frag.nodes if n.kind == "acl_rule")
    assert rule.attrs["acl_id"] == "outside-in"
    assert rule.attrs["line"] == 14
    assert rule.attrs["source_expanded"] == ("0.0.0.0/0",)
    assert rule.attrs["source_chains"]["0.0.0.0/0"] == (
        "Trusted-Admins", "Partners", "0.0.0.0/0",
    )


def test_cisco_interfaces_and_zones_derived():
    assessment = _assess("edge_fw_01.cfg")
    frag = assessment.graph_contribution
    by_id = {n.node_id: n for n in frag.nodes}
    outside = by_id["EDGE-FW-01:interface:GigabitEthernet0/0"]
    inside = by_id["EDGE-FW-01:interface:GigabitEthernet0/1"]
    assert outside.attrs["ip_address"] == "203.0.113.1/24"
    assert inside.attrs["ip_address"] == "10.0.0.1/24"

    zone_edges = {
        (e.source_id, e.target_id) for e in frag.edges if e.kind == "in_zone"
    }
    assert (outside.node_id, "EDGE-FW-01:zone:external") in zone_edges
    assert (inside.node_id, "EDGE-FW-01:zone:internal") in zone_edges


def test_acl_applied_to_interface_edge():
    assessment = _assess("edge_fw_01.cfg")
    frag = assessment.graph_contribution
    applied = [e for e in frag.edges if e.kind == "applied_to"]
    assert len(applied) == 1
    e = applied[0]
    assert e.source_id == "EDGE-FW-01:acl:outside-in"
    assert e.target_id == "EDGE-FW-01:interface:GigabitEthernet0/0"
    assert e.attrs["direction"] == "in"


def test_every_node_carries_source_facts():
    # INV-04.1-01 — traceability, satisfied via attrs["source_facts"] since
    # GraphNode has no dedicated field for it (see build.py's docstring).
    assessment = _assess("edge_fw_01.cfg")
    fact_paths = {f.path for f in assessment.facts}
    for node in assessment.graph_contribution.nodes:
        source_facts = node.attrs.get("source_facts", ())
        assert source_facts, f"node {node.node_id} has no source_facts"
        for path in source_facts:
            assert path in fact_paths, f"{node.node_id} cites unknown fact {path}"


def test_minimal_contribution_for_platform_without_acl_extraction():
    from nsca_engine.tests.helpers import M2_FIXTURES, build_knowledge_base_m2

    kb = build_knowledge_base_m2()
    content = M2_FIXTURES["routeros"].read_text(encoding="utf-8")
    assessment = assess_device((make_artifact(content),), kb, ASSESSED_AT)
    frag = assessment.graph_contribution
    kinds = {n.kind for n in frag.nodes}
    assert "device" in kinds
    # No ACL/object-group data exists for RouterOS in M1/M2's rulepack, so no
    # acl/address_object nodes should be fabricated.
    assert "address_object" not in kinds
    assert "acl" not in kinds
    device_node = next(n for n in frag.nodes if n.kind == "device")
    assert device_node.attrs["source_facts"]


def test_merge_estate_combines_fragments_and_links_shared_subnets():
    frag_a = graph_build.device_graph_contribution(
        "A", "cisco_ios",
        _facts_iface("A", "Gi0/0", "10.0.0.1/24"),
    )
    frag_b = graph_build.device_graph_contribution(
        "B", "cisco_ios",
        _facts_iface("B", "Gi0/0", "10.0.0.2/24"),
    )
    graph = graph_build.merge_estate((frag_a, frag_b))

    node_ids = {n.node_id for n in graph.nodes}
    assert "A:interface:Gi0/0" in node_ids
    assert "B:interface:Gi0/0" in node_ids

    adjacency = [
        e for e in graph.edges
        if e.kind == "routes_to" and e.attrs.get("reason") == "shared_subnet"
    ]
    pairs = {(e.source_id, e.target_id) for e in adjacency}
    assert ("A:interface:Gi0/0", "B:interface:Gi0/0") in pairs
    assert ("B:interface:Gi0/0", "A:interface:Gi0/0") in pairs
    assert all(e.attrs["confidence"] == "low" for e in adjacency)


def test_merge_estate_accepts_device_assessments_directly():
    a = _assess("gate_p.cfg")
    b = _assess("core_p.cfg")
    c = _assess("srv_p.cfg")
    graph = graph_build.merge_estate((a, b, c))
    device_ids = {n.device_id for n in graph.nodes if n.kind == "device"}
    assert device_ids == {"GATE-P", "CORE-P", "SRV-P"}


def _facts_iface(device_id: str, name: str, cidr: str):
    from nsca_engine.types import Fact, Provenance, ProvenanceSource

    prov = Provenance(source=ProvenanceSource.EXPLICIT, artifact_id=device_id)
    return (
        Fact(path="interface.entries[0].name", value=name, type="string", provenance=prov),
        Fact(path="interface.entries[0].ip_address", value=cidr, type="string", provenance=prov),
        Fact(
            path="device.config_export_mode", value="full", type="enum",
            provenance=Provenance(source=ProvenanceSource.DERIVED),
        ),
    )
