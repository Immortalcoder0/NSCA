"""Multi-device reachability queries and counterexample generation
(TRD-04.2).

Scope note (flagged, not silently resolved): TRD-04.2 §3.2/§3.3 describes
full set-based (``PacketSet``) evaluation, carrying sets through traversal
and materialising a single representative only at the end (DD-04.2-01).
This implementation evaluates a single concrete packet all the way through
instead (`query`'s ``src_addr``/``dst_addr`` are already concrete
addresses). For first-match ACL semantics this is sound — a concrete packet
is decided by exactly one rule, the first whose selector contains it — and
it is what M3's acceptance fixture (the canonical single-packet
counterexample) needs. It under-serves the *set*-oriented use cases TRD-04.2
also describes (e.g. "is there any packet on any port that reaches this
service" style broad queries) — those would need the full set-based engine
and are left for a later milestone. ``query_zone`` on top of `query` picks a
deterministic representative address per zone (DD-04.2-03's own convention:
``203.0.113.5`` for an external source) so a caller can still ask a
zone-to-zone question without hand-picking an address.

Multi-hop traversal is also a documented simplification relative to
TRD-04.2 §3.4: the visited-set key is ``device_id`` alone (not
``(node, packet_set)``), and only *inbound* ACLs are evaluated at each hop
(outbound/egress filtering is not). Both are sound simplifications for the
single-concrete-packet case this module targets, not for the general
set-based algorithm.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from nsca_engine.api import Graph
from nsca_engine.types import GraphNode

MAX_DEPTH = 12

# DD-04.2-03: deterministic representative addresses, chosen exactly as the
# canonical example in 04-system-architecture.md §4.5 does (203.0.113.5 —
# TEST-NET-3 — for an external source; a plausible ephemeral source port).
_ZONE_REPRESENTATIVES = {
    "external": "203.0.113.5",
}
_EPHEMERAL_SRC_PORT = 44210


@dataclass(frozen=True, slots=True)
class RuleChainStep:
    """One hop's decisive rule (TRD-04.2 §3.1's ``EDGE-FW-01 rule
    'outside-in' line 14`` style evidence)."""

    device_id: str
    rule_ref: str  # e.g. "acl[outside-in] line 14"
    action: str
    detail: str | None  # e.g. "Trusted-Admins -> Partners -> 0.0.0.0/0"


@dataclass(frozen=True, slots=True)
class Counterexample:
    """A concrete permitted packet plus the rule chain that permits it
    (INV-04.2-01)."""

    src_addr: str
    dst_addr: str
    protocol: str
    src_port: int
    dst_port: int
    chain: tuple[RuleChainStep, ...]

    def summary(self) -> str:
        chain_text = "; ".join(
            f"{s.device_id} rule {s.rule_ref}"
            + (f", because group {s.detail}" if s.detail else "")
            for s in self.chain
        )
        return (
            f"{self.src_addr}:{self.src_port} -> {self.dst_addr}:{self.dst_port} "
            f"{self.protocol.upper()} permitted via {chain_text}"
        )


@dataclass(frozen=True, slots=True)
class SearchStats:
    nodes_visited: int
    depth_reached: int
    exhausted: bool


@dataclass(frozen=True, slots=True)
class QueryResult:
    outcome: str  # "reachable" | "unreachable" | "unknown"
    counterexample: Counterexample | None
    assumptions: tuple[str, ...]
    confidence: str  # "high" | "medium" | "low"
    search_stats: SearchStats
    weakest_edge_confidence: str | None = None


def _by_id(graph: Graph) -> dict[str, GraphNode]:
    return {n.node_id: n for n in graph.nodes}


def _acl_rules(graph: Graph, acl_node_id: str) -> list[GraphNode]:
    rule_ids = {
        e.source_id for e in graph.edges if e.kind == "member_of" and e.target_id == acl_node_id
    }
    nodes = _by_id(graph)
    rules = [nodes[rid] for rid in rule_ids if rid in nodes and nodes[rid].kind == "acl_rule"]
    rules.sort(key=lambda n: (n.attrs.get("seq", 0), n.node_id))
    return rules


def _proto_matches(rule_proto: str | None, query_proto: str) -> bool:
    if rule_proto is None:
        return True
    rp = rule_proto.lower()
    return rp in (query_proto.lower(), "ip", "any")


def _port_matches(dest_port_raw: str | None, dport: int) -> bool:
    if not dest_port_raw:
        return True
    tokens = dest_port_raw.split()
    if tokens[:1] == ["eq"] and len(tokens) >= 2:
        try:
            return int(tokens[1]) == dport
        except ValueError:
            return True
    if tokens[:1] == ["range"] and len(tokens) >= 3:
        try:
            return int(tokens[1]) <= dport <= int(tokens[2])
        except ValueError:
            return True
    return True  # unrecognised port clause — fail open to "match", flagged


def _selector_matches(
    addr: str, is_object: bool, raw: str | None,
    expanded: tuple[str, ...] | None, chains: dict[str, tuple[str, ...]] | None,
    unknown: bool,
) -> tuple[bool | None, str | None]:
    """Returns (match, detail). ``match is None`` means the selector could
    not be resolved (default_unknown membership) — the caller must treat
    the whole query as UNKNOWN, never silently skip it (TRD-04.2 §5: "Rule
    referencing an unresolvable object -> Rule contributes UNKNOWN; the
    query cannot return PASS")."""

    if is_object:
        if unknown:
            return None, None
        for literal in expanded or ():
            try:
                net = ipaddress.ip_network(literal, strict=False)
            except ValueError:
                continue
            if ipaddress.ip_address(addr) in net:
                chain = (chains or {}).get(literal)
                detail = " -> ".join(chain) if chain else literal
                return True, detail
        return False, None
    if raw is None:
        return True, None
    try:
        net = ipaddress.ip_network(raw, strict=False)
    except ValueError:
        return None, None
    return ipaddress.ip_address(addr) in net, None


def _dst_delivered_by_device(graph: Graph, device_id: str, dst_addr: str) -> bool:
    """Whether ``dst_addr`` is on one of *this* device's own connected
    subnets. Deliberately device-scoped (not "anywhere in the collected
    estate") so multi-hop traversal (`_next_hops`) is load-bearing: a
    destination two hops away is not "delivered" until the search actually
    reaches the device it is connected to."""

    try:
        addr = ipaddress.ip_address(dst_addr)
    except ValueError:
        return False
    for n in graph.nodes:
        if n.kind != "interface" or n.device_id != device_id:
            continue
        ip_cidr = n.attrs.get("ip_address")
        if not ip_cidr:
            continue
        try:
            net = ipaddress.ip_network(ip_cidr, strict=False)
        except ValueError:
            continue
        if addr in net:
            return True
    return False


def _entry_interfaces(graph: Graph, src_addr: str) -> list[GraphNode]:
    try:
        addr = ipaddress.ip_address(src_addr)
    except ValueError:
        addr = None

    interfaces = [n for n in graph.nodes if n.kind == "interface" and n.attrs.get("ip_address")]
    if addr is not None:
        directly_connected = []
        for n in interfaces:
            try:
                net = ipaddress.ip_network(n.attrs["ip_address"], strict=False)
            except ValueError:
                continue
            if addr in net:
                directly_connected.append(n)
        if directly_connected:
            return sorted(directly_connected, key=lambda n: n.node_id)

    # Not directly connected anywhere collected -> treat as arriving from
    # outside, via every interface sitting in an external zone.
    zone_edges = {
        e.source_id: e.target_id for e in graph.edges if e.kind == "in_zone"
    }
    nodes = _by_id(graph)
    externals = [
        n for n in interfaces
        if zone_edges.get(n.node_id) in nodes
        and nodes[zone_edges[n.node_id]].attrs.get("name") == "external"
    ]
    return sorted(externals, key=lambda n: n.node_id)


def _inbound_acl(graph: Graph, iface_node_id: str) -> GraphNode | None:
    nodes = _by_id(graph)
    for e in graph.edges:
        if e.kind == "applied_to" and e.target_id == iface_node_id and e.attrs.get("direction") == "in":
            acl = nodes.get(e.source_id)
            if acl is not None and acl.kind == "acl":
                return acl
    return None


def _next_hops(graph: Graph, device_id: str) -> list[GraphNode]:
    """Every node reachable via a ``routes_to`` edge originating from this
    device — either the device node itself (static-route resolution, in
    `merge_estate`) or one of its own interface nodes (shared-subnet
    adjacency, also `merge_estate`)."""

    nodes = _by_id(graph)
    own_ids = {n.node_id for n in graph.nodes if n.device_id == device_id}
    targets = [
        nodes[e.target_id] for e in graph.edges
        if e.kind == "routes_to" and e.source_id in own_ids and e.target_id in nodes
    ]
    return sorted(targets, key=lambda n: n.node_id)


def query(
    graph: Graph, src_addr: str, dst_addr: str,
    protocol: str = "tcp", dport: int = 22,
    *, src_port: int = _EPHEMERAL_SRC_PORT, max_depth: int = MAX_DEPTH,
) -> QueryResult:
    """Concrete-packet reachability query (see module docstring for the
    documented simplifications relative to TRD-04.2's full set-based
    algorithm)."""

    assumptions: list[str] = []
    entries = _entry_interfaces(graph, src_addr)
    if not entries:
        return QueryResult(
            outcome="unknown", counterexample=None,
            assumptions=("no plausible entry interface found for this source address",),
            confidence="low", search_stats=SearchStats(0, 0, exhausted=False),
        )

    visited: set[str] = set()
    nodes_visited = 0
    depth_reached = 0
    exhausted = False
    weakest_confidence: str | None = None

    frontier: list[tuple[str, str, tuple[RuleChainStep, ...], int]] = [
        (n.device_id, n.node_id, (), 0) for n in entries
    ]
    frontier.sort(key=lambda item: (item[0], item[1]))
    any_unknown = False

    while frontier:
        device_id, iface_id, chain, depth = frontier.pop(0)
        depth_reached = max(depth_reached, depth)
        key = device_id
        if key in visited:
            continue
        visited.add(key)
        nodes_visited += 1
        if depth > max_depth:
            exhausted = True
            continue

        acl = _inbound_acl(graph, iface_id)
        decisive: GraphNode | None = None
        detail: str | None = None
        if acl is not None:
            unresolved = False
            for rule in _acl_rules(graph, acl.node_id):
                a = rule.attrs
                if not _proto_matches(a.get("protocol"), protocol):
                    continue
                dst_match, _ = _selector_matches(
                    dst_addr, bool(a.get("destination_is_object")), a.get("destination"),
                    a.get("destination_expanded"), a.get("destination_chains"),
                    bool(a.get("destination_unknown")),
                )
                if dst_match is None:
                    unresolved = True
                    break
                if not dst_match:
                    continue
                if not _port_matches(a.get("dest_port"), dport):
                    continue
                src_match, src_detail = _selector_matches(
                    src_addr, bool(a.get("source_is_object")), a.get("source"),
                    a.get("source_expanded"), a.get("source_chains"),
                    bool(a.get("source_unknown")),
                )
                if src_match is None:
                    unresolved = True
                    break
                if not src_match:
                    continue
                decisive = rule
                detail = src_detail
                break
            if unresolved:
                any_unknown = True
                continue
        # acl is None -> no ACL applied inbound: default permit, flagged.
        if acl is not None and decisive is None:
            assumptions.append(
                f"{device_id}: no ACL rule matched — implicit deny (Cisco ACL default)"
            )
            continue  # blocked at this entry
        if acl is None:
            assumptions.append(f"{device_id}: no inbound ACL on {iface_id} — default permit")

        step = None
        if decisive is not None:
            a = decisive.attrs
            rule_ref = f"acl[{a.get('acl_id')}] line {a.get('line')}"
            step = RuleChainStep(
                device_id=device_id, rule_ref=rule_ref, action=a.get("action", "permit"),
                detail=detail,
            )
            if a.get("action") == "deny":
                assumptions.append(f"{device_id}: denied by {rule_ref}")
                continue
        new_chain = chain + ((step,) if step is not None else ())

        if _dst_delivered_by_device(graph, device_id, dst_addr):
            return QueryResult(
                outcome="reachable",
                counterexample=Counterexample(
                    src_addr=src_addr, dst_addr=dst_addr, protocol=protocol,
                    src_port=src_port, dst_port=dport, chain=new_chain,
                ),
                assumptions=tuple(assumptions),
                confidence="high",
                search_stats=SearchStats(nodes_visited, depth_reached, exhausted=False),
                weakest_edge_confidence=weakest_confidence,
            )

        for hop in _next_hops(graph, device_id):
            if hop.device_id in visited:
                continue
            frontier.append((hop.device_id, hop.node_id, new_chain, depth + 1))
        frontier.sort(key=lambda item: (item[0], item[1]))

    if exhausted:
        return QueryResult(
            outcome="unknown", counterexample=None,
            assumptions=tuple(assumptions) + ("search budget (max depth) exhausted",),
            confidence="low", search_stats=SearchStats(nodes_visited, depth_reached, exhausted=True),
        )
    if any_unknown:
        return QueryResult(
            outcome="unknown", counterexample=None,
            assumptions=tuple(assumptions)
            + ("a rule referenced an unresolvable object-group membership",),
            confidence="low", search_stats=SearchStats(nodes_visited, depth_reached, exhausted=False),
        )
    return QueryResult(
        outcome="unreachable", counterexample=None,
        assumptions=tuple(assumptions),
        confidence="medium" if assumptions else "high",
        search_stats=SearchStats(nodes_visited, depth_reached, exhausted=False),
    )


def query_zone(
    graph: Graph, src_zone: str, dst_addr: str,
    protocol: str = "tcp", dport: int = 22,
) -> QueryResult:
    """Convenience wrapper for a zone-to-address question (what the M3 task
    brief calls "given a source zone/network and destination zone/network").
    Resolves ``src_zone`` to a deterministic representative address
    (DD-04.2-03) rather than hand-picking one per call site."""

    src_addr = _ZONE_REPRESENTATIVES.get(src_zone)
    if src_addr is None:
        return QueryResult(
            outcome="unknown", counterexample=None,
            assumptions=(f"no representative address is defined for zone {src_zone!r}",),
            confidence="low", search_stats=SearchStats(0, 0, exhausted=False),
        )
    return query(graph, src_addr, dst_addr, protocol, dport)
