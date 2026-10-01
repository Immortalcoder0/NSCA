"""Graph construction (TRD-04.1): per-device graph contribution and
multi-device estate merge.

Construction is a pure function of the campaign's fact sets
(DD-04.1-01) — no device is queried, nothing is discovered actively.
``device_graph_contribution`` reads a single device's already-extracted
``Fact`` tuple (never raw text — TRD-04.1 §3.2's pipeline starts from
"resolved fact sets", and 04-system-architecture.md's own principle is that
facts are the interface between extraction and everything downstream) and
returns the ``GraphFragment`` shape ``api.py`` already commits to.
``merge_estate`` combines many fragments into the campaign-wide ``Graph``.

Node/edge identity is deterministic (INV-04.1-02): every id is built from
stable content (device id + kind + a stable identifier drawn from the
facts), never from insertion order or a counter that would depend on
dict/set iteration order.

``GraphNode``/``GraphEdge`` (types.py, M0-fixed contract shapes) have no
dedicated ``source_facts`` field. INV-04.1-01 ("every node and edge traces to
source facts") is honoured here by recording the contributing fact path(s)
under ``attrs["source_facts"]`` instead of a new dataclass field — a
deliberate choice to satisfy the invariant without touching a contract
shape M0 fixed as final (flagged in the M3 report).
"""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, cast

from nsca_engine.types import Fact, GraphEdge, GraphFragment, GraphNode

# Rebuilt lazily inside functions that need it, to avoid a hard import-time
# dependency of graph/ on api.py (api.py imports graph/, not the other way
# around, for M3's assess_device wiring). The TYPE_CHECKING-only imports
# below are erased at runtime (see `from __future__ import annotations`
# above — every annotation is a lazily-evaluated string) so they cannot
# introduce the cycle; they exist purely so mypy --strict sees real types
# here instead of `object`.
if TYPE_CHECKING:
    from nsca_engine.api import DeviceAssessment, Graph


# ---------------------------------------------------------------------------
# Fact-table helpers — turn a flat Fact tuple into row dicts, deterministic
# order (source order == extraction order == the config's own line order).
# ---------------------------------------------------------------------------


def _rows(facts: tuple[Fact, ...], base: str) -> list[dict[str, object]]:
    """Group ``base[i].field`` facts into a list of row dicts, ordered by
    index. Missing indices are skipped (never happens for facts this module
    itself produced, but defensive against partial fact sets in tests)."""

    by_index: dict[int, dict[str, object]] = {}
    prefix = base + "["
    for f in facts:
        if not f.path.startswith(prefix):
            continue
        rest = f.path[len(prefix):]
        idx_str, _, field = rest.partition("].")
        try:
            idx = int(idx_str)
        except ValueError:
            continue
        by_index.setdefault(idx, {})[field] = f.value
    return [by_index[i] for i in sorted(by_index)]


def _fact_by_path(facts: tuple[Fact, ...], path: str) -> Fact | None:
    for f in facts:
        if f.path == path:
            return f
    return None


def _str(row: Mapping[str, object], key: str) -> str | None:
    """Narrow a row value (``object`` — rows are heterogeneous, built from
    ``Fact.value: Any``, TRD-03.2) to ``str`` for the call sites that need a
    string identifier (node ids, dict keys). Anything not actually a string
    is treated the same as "field absent" — never fabricated."""

    value = row.get(key)
    return value if isinstance(value, str) else None


# ---------------------------------------------------------------------------
# Transitive object-group expansion (TRD-03.2 §4.6's algorithm, applied at
# graph-build time since M1's rulepacks don't yet compute
# ``filter.objects[].expanded`` as a generic derived fact).
# ---------------------------------------------------------------------------


def expand_object(
    name: str, members_by_group: Mapping[str, tuple[str, ...]]
) -> dict[str, tuple[str, ...]] | None:
    """Returns ``{literal: chain}`` where ``chain`` is the full
    ``(name, ..., literal)`` path used to reach that literal — matching
    04-system-architecture.md §4.5's ``Trusted-Admins -> Partners ->
    0.0.0.0/0`` chain format exactly, joinable with `` -> ``.

    Returns ``None`` (default_unknown, never an understated result — TRD-03.2
    §4.6) on a cycle or an unresolvable member reference.
    """

    result: dict[str, tuple[str, ...]] = {}

    def _walk(node: str, seen: tuple[str, ...]) -> bool:
        if node in seen:
            return False  # cycle — caller treats whole expansion as unknown
        seen = seen + (node,)
        members = members_by_group.get(node)
        if members is None:
            return False  # referenced group has no definition — unresolved
        for m in members:
            if m in members_by_group:
                if not _walk(m, seen):
                    return False
            else:
                # A literal member. Anything that parses as a network/host is
                # accepted as a literal; anything else is an unresolved
                # reference to an undefined group (default_unknown).
                try:
                    ipaddress.ip_network(m, strict=False)
                except ValueError:
                    return False
                result[m] = seen + (m,)
        return True

    if not _walk(name, ()):
        return None
    return result


# ---------------------------------------------------------------------------
# Zone derivation (TRD-04.1 §3.5) — Cisco has no explicit zone concept, so
# zones are derived from interface address privacy.
# ---------------------------------------------------------------------------


_RFC1918_NETS = (
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
)


def _derive_zone(ip_cidr: str | None) -> str | None:
    """TRD-04.1 §3.5's Cisco/Arista derivation rule: "RFC1918 only ->
    internal", else external. Deliberately narrower than Python's
    ``IPv4Network.is_private`` — that property also marks RFC5737
    documentation ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24,
    used by this milestone's own fixtures, matching
    04-system-architecture.md §4.5's own example address) as "private",
    which would misclassify a real internet-facing edge as internal."""

    if ip_cidr is None:
        return None
    try:
        net = ipaddress.ip_network(ip_cidr, strict=False)
    except ValueError:
        return None
    if not isinstance(net, ipaddress.IPv4Network):
        # No M1/M2 rulepack emits IPv6 interface addresses today; treat as
        # external rather than risk an IPv4/IPv6 `subnet_of` TypeError.
        return "external"
    is_rfc1918 = any(net.subnet_of(rfc1918) for rfc1918 in _RFC1918_NETS)
    return "internal" if is_rfc1918 else "external"


# ---------------------------------------------------------------------------
# Per-device contribution
# ---------------------------------------------------------------------------

_RICH_PLATFORMS = frozenset({"cisco_ios"})


def device_graph_contribution(
    device_id: str, platform: str, facts: tuple[Fact, ...]
) -> GraphFragment:
    """Build this device's `GraphFragment` from its already-extracted facts.

    Cisco IOS (``extract/cisco_acl.py``, wired into ``assess_device``) is the
    only platform with rich enough facts (ACLs, nested object-groups,
    interfaces, static routes) for a meaningful graph contribution today.
    Every other M1/M2 platform gets a minimal-but-correct contribution: a
    device node always (backed by the always-present
    ``device.config_export_mode`` fact, satisfying INV-04.1-01), plus
    whatever the platform's rulepack happens to expose (`filter.rules[]`
    names for cloud_generic_fw, `topology.interfaces[]` for routeros) — never
    fabricated topology beyond what the facts state. Flagged in the M3
    report as the rich-vs-minimal split.
    """

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    export_mode_fact = _fact_by_path(facts, "device.config_export_mode")
    device_source_facts: tuple[str, ...] = (
        ("device.config_export_mode",) if export_mode_fact is not None else ()
    )
    device_node_id = f"{device_id}:device:{device_id}"
    nodes.append(
        GraphNode(
            node_id=device_node_id, device_id=device_id, kind="device",
            attrs={"platform": platform, "source_facts": device_source_facts},
        )
    )

    if platform in _RICH_PLATFORMS:
        _build_cisco_ios(device_id, device_node_id, facts, nodes, edges)
    else:
        _build_minimal(device_id, device_node_id, facts, nodes, edges)

    nodes.sort(key=lambda n: n.node_id)
    edges.sort(key=lambda e: (e.source_id, e.target_id, e.kind))
    return GraphFragment(device_id=device_id, nodes=tuple(nodes), edges=tuple(edges))


def _build_minimal(
    device_id: str, device_node_id: str,
    facts: tuple[Fact, ...], nodes: list[GraphNode], edges: list[GraphEdge],
) -> None:
    for i, row in enumerate(_rows(facts, "filter.rules")):
        name = row.get("name")
        if name is None:
            continue
        node_id = f"{device_id}:acl_rule:{name}"
        nodes.append(
            GraphNode(
                node_id=node_id, device_id=device_id, kind="acl_rule",
                attrs={"name": name, "source_facts": (f"filter.rules[{i}].name",)},
            )
        )
        edges.append(
            GraphEdge(
                source_id=device_node_id, target_id=node_id, kind="references", attrs={},
            )
        )

    for i, row in enumerate(_rows(facts, "topology.interfaces")):
        name = row.get("name")
        if name is None:
            continue
        node_id = f"{device_id}:interface:{name}"
        nodes.append(
            GraphNode(
                node_id=node_id, device_id=device_id, kind="interface",
                attrs={"name": name, "source_facts": (f"topology.interfaces[{i}].name",)},
            )
        )
        edges.append(
            GraphEdge(source_id=node_id, target_id=device_node_id, kind="member_of", attrs={}),
        )


def _build_cisco_ios(
    device_id: str, device_node_id: str,
    facts: tuple[Fact, ...], nodes: list[GraphNode], edges: list[GraphEdge],
) -> None:
    # -- object groups + membership --------------------------------------
    obj_rows = _rows(facts, "filter.objects")
    group_names = {row["name"] for row in obj_rows if "name" in row}

    member_rows = _rows(facts, "filter.object_members")
    members_by_group: dict[str, list[str]] = {}
    for row in member_rows:
        g, m = _str(row, "group"), _str(row, "member")
        if g is None or m is None:
            continue
        members_by_group.setdefault(g, []).append(m)
    members_by_group_t = {k: tuple(v) for k, v in members_by_group.items()}

    for i, row in enumerate(obj_rows):
        name = row.get("name")
        if name is None:
            continue
        node_id = f"{device_id}:address_object:{name}"
        nodes.append(
            GraphNode(
                node_id=node_id, device_id=device_id, kind="address_object",
                attrs={"name": name, "source_facts": (f"filter.objects[{i}].name",)},
            )
        )

    literal_ids: set[str] = set()
    for i, row in enumerate(member_rows):
        g, m = _str(row, "group"), _str(row, "member")
        if g is None or m is None:
            continue
        src_id = f"{device_id}:address_object:{g}"
        if m in group_names:
            tgt_id = f"{device_id}:address_object:{m}"
        else:
            tgt_id = f"{device_id}:literal:{m}"
            if tgt_id not in literal_ids:
                literal_ids.add(tgt_id)
                nodes.append(
                    GraphNode(
                        node_id=tgt_id, device_id=device_id, kind="literal",
                        attrs={
                            "cidr": m,
                            "source_facts": (f"filter.object_members[{i}].member",),
                        },
                    )
                )
        edges.append(
            GraphEdge(
                source_id=src_id, target_id=tgt_id, kind="member_of",
                attrs={"source_facts": (
                    f"filter.object_members[{i}].group",
                    f"filter.object_members[{i}].member",
                )},
            )
        )

    # -- ACLs + rules -------------------------------------------------------
    rule_rows = _rows(facts, "filter.acl_rules")
    acl_ids: dict[str, str] = {}
    for i, row in enumerate(rule_rows):
        acl_id = _str(row, "acl_id")
        if acl_id is None:
            continue
        acl_node_id = acl_ids.get(acl_id)
        if acl_node_id is None:
            acl_node_id = f"{device_id}:acl:{acl_id}"
            acl_ids[acl_id] = acl_node_id
            nodes.append(
                GraphNode(
                    node_id=acl_node_id, device_id=device_id, kind="acl",
                    attrs={"acl_id": acl_id, "source_facts": (f"filter.acl_rules[{i}].acl_id",)},
                )
            )

        seq = row.get("seq", i)
        source = row.get("source")
        source_is_object = bool(row.get("source_is_object"))
        destination = row.get("destination")
        destination_is_object = bool(row.get("destination_is_object"))
        rule_attrs: dict[str, object] = {
            "acl_id": acl_id, "seq": seq, "action": row.get("action"),
            "protocol": row.get("protocol"), "source": source,
            "source_is_object": source_is_object, "destination": destination,
            "destination_is_object": destination_is_object,
            "dest_port": row.get("dest_port"), "line": row.get("line"),
            "source_facts": tuple(
                f"filter.acl_rules[{i}].{field}"
                for field in (
                    "acl_id", "seq", "action", "protocol", "source",
                    "source_is_object", "destination", "destination_is_object",
                    "dest_port", "line",
                )
            ),
        }
        if source_is_object and isinstance(source, str):
            expanded = expand_object(source, members_by_group_t)
            if expanded is None:
                rule_attrs["source_unknown"] = True
            else:
                rule_attrs["source_expanded"] = tuple(sorted(expanded))
                rule_attrs["source_chains"] = dict(sorted(expanded.items()))
        if destination_is_object and isinstance(destination, str):
            expanded_d = expand_object(destination, members_by_group_t)
            if expanded_d is None:
                rule_attrs["destination_unknown"] = True
            else:
                rule_attrs["destination_expanded"] = tuple(sorted(expanded_d))
                rule_attrs["destination_chains"] = dict(sorted(expanded_d.items()))

        rule_node_id = f"{device_id}:acl_rule:{acl_id}:{seq}"
        nodes.append(
            GraphNode(node_id=rule_node_id, device_id=device_id, kind="acl_rule", attrs=rule_attrs)
        )
        edges.append(
            GraphEdge(source_id=rule_node_id, target_id=acl_node_id, kind="member_of", attrs={})
        )
        if source_is_object and isinstance(source, str) and source in group_names:
            edges.append(
                GraphEdge(
                    source_id=rule_node_id, target_id=f"{device_id}:address_object:{source}",
                    kind="references", attrs={},
                )
            )

    # -- interfaces + zones --------------------------------------------------
    iface_rows = _rows(facts, "interface.entries")
    for i, row in enumerate(iface_rows):
        name = row.get("name")
        if name is None:
            continue
        ip_cidr = _str(row, "ip_address")
        iface_node_id = f"{device_id}:interface:{name}"
        nodes.append(
            GraphNode(
                node_id=iface_node_id, device_id=device_id, kind="interface",
                attrs={
                    "name": name, "ip_address": ip_cidr,
                    "source_facts": (
                        f"interface.entries[{i}].name", f"interface.entries[{i}].ip_address",
                    ),
                },
            )
        )
        edges.append(
            GraphEdge(source_id=iface_node_id, target_id=device_node_id, kind="member_of", attrs={})
        )
        zone = _derive_zone(ip_cidr)
        if zone is not None:
            zone_node_id = f"{device_id}:zone:{zone}"
            if not any(n.node_id == zone_node_id for n in nodes):
                nodes.append(
                    GraphNode(
                        node_id=zone_node_id, device_id=device_id, kind="zone",
                        attrs={
                            "name": zone, "derived": True,
                            "source_facts": (f"interface.entries[{i}].ip_address",),
                        },
                    )
                )
            edges.append(
                GraphEdge(source_id=iface_node_id, target_id=zone_node_id, kind="in_zone", attrs={})
            )

    # -- ACL <-> interface bindings ------------------------------------------
    for i, row in enumerate(_rows(facts, "interface.acl_bindings")):
        iface_name = _str(row, "interface")
        acl_id = _str(row, "acl_id")
        direction = row.get("direction")
        if iface_name is None or acl_id is None:
            continue
        iface_node_id = f"{device_id}:interface:{iface_name}"
        if acl_id not in acl_ids:
            continue  # dangling reference to an undeclared ACL — dropped (TRD-04.1 §3.7)
        acl_node_id = acl_ids[acl_id]
        edges.append(
            GraphEdge(
                source_id=acl_node_id, target_id=iface_node_id, kind="applied_to",
                attrs={
                    "direction": direction,
                    "source_facts": (
                        f"interface.acl_bindings[{i}].interface",
                        f"interface.acl_bindings[{i}].acl_id",
                        f"interface.acl_bindings[{i}].direction",
                    ),
                },
            )
        )

    # -- static routes --------------------------------------------------------
    for i, row in enumerate(_rows(facts, "route.static")):
        dest, next_hop = row.get("destination"), row.get("next_hop")
        if dest is None or next_hop is None:
            continue
        route_node_id = f"{device_id}:route:{dest}:{next_hop}"
        nodes.append(
            GraphNode(
                node_id=route_node_id, device_id=device_id, kind="route",
                attrs={
                    "destination": dest, "next_hop": next_hop,
                    "source_facts": (
                        f"route.static[{i}].destination", f"route.static[{i}].next_hop",
                    ),
                },
            )
        )
        edges.append(
            GraphEdge(source_id=device_node_id, target_id=route_node_id, kind="references", attrs={})
        )


# ---------------------------------------------------------------------------
# Estate merge (TRD-04.1 §3.2 steps 4-6): combine every device's fragment
# into one campaign Graph, plus best-effort inter-device linkage from
# configuration alone (DD-04.1-01 — no active discovery).
# ---------------------------------------------------------------------------


def _fragment_of(item: DeviceAssessment | GraphFragment) -> GraphFragment:
    """Accepts either a `GraphFragment` directly or a `DeviceAssessment`
    (read via its `.graph_contribution` field) — duck-typed dispatch rather
    than an `isinstance` check so this module never needs a runtime import
    of `api.DeviceAssessment` (which would reintroduce the api.py <-> graph/
    cycle this module's docstring already explains). `cast` is used because
    that structural relationship is exactly what mypy cannot verify without
    a `Protocol`, which would be more machinery than this one call site
    warrants."""

    contribution = getattr(item, "graph_contribution", None)
    if contribution is not None:
        return cast(GraphFragment, contribution)
    return cast(GraphFragment, item)


def merge_estate(devices: Iterable[DeviceAssessment | GraphFragment]) -> Graph:
    """Merge many devices' `GraphFragment`s (or `DeviceAssessment`s — the
    ``.graph_contribution`` field is read automatically) into the campaign
    `Graph` (TRD-04.1 §3.2 steps 4-6).

    Deliberately a standalone function, callable directly in tests without
    going through `assess_campaign` (backend-01 M3 task: "graph-merge and
    reachability capability so assess_campaign could later call it").

    Inter-device linkage implemented (TRD-04.1 §3.3, deliberately partial —
    flagged): shared-subnet Layer-3 adjacency between interfaces on
    different devices (labelled low confidence per DD-04.1-02), and static
    route next-hop resolution to a peer's interface (medium confidence).
    VLAN-matching and discovery-protocol adjacency are not implemented (M1's
    facts carry neither).
    """


    fragments = tuple(_fragment_of(d) for d in devices)

    all_nodes: dict[str, GraphNode] = {}
    all_edges: list[GraphEdge] = []
    for frag in fragments:
        for n in frag.nodes:
            all_nodes[n.node_id] = n
        all_edges.extend(frag.edges)

    # Inter-device linkage from interface subnets.
    interfaces = [
        n for n in all_nodes.values()
        if n.kind == "interface" and n.attrs.get("ip_address")
    ]
    for i, a in enumerate(interfaces):
        try:
            net_a = ipaddress.ip_network(a.attrs["ip_address"], strict=False)
        except ValueError:
            continue
        for b in interfaces[i + 1:]:
            if b.device_id == a.device_id:
                continue
            try:
                net_b = ipaddress.ip_network(b.attrs["ip_address"], strict=False)
            except ValueError:
                continue
            if net_a.network_address == net_b.network_address and net_a.prefixlen == net_b.prefixlen:
                for src, tgt in ((a, b), (b, a)):
                    all_edges.append(
                        GraphEdge(
                            source_id=src.node_id, target_id=tgt.node_id, kind="routes_to",
                            attrs={"confidence": "low", "reason": "shared_subnet"},
                        )
                    )

    # Static-route next-hop resolution to a peer's owning interface.
    route_nodes = [n for n in all_nodes.values() if n.kind == "route"]
    for r in route_nodes:
        next_hop = r.attrs.get("next_hop")
        if not next_hop:
            continue
        try:
            hop_addr = ipaddress.ip_address(next_hop)
        except ValueError:
            continue
        for iface in interfaces:
            if iface.device_id == r.device_id:
                continue
            try:
                net = ipaddress.ip_network(iface.attrs["ip_address"], strict=False)
            except ValueError:
                continue
            if hop_addr in net:
                device_node_id = f"{r.device_id}:device:{r.device_id}"
                if device_node_id in all_nodes:
                    all_edges.append(
                        GraphEdge(
                            source_id=device_node_id, target_id=iface.node_id, kind="routes_to",
                            attrs={
                                "confidence": "medium", "reason": "static_route_next_hop",
                                "source_facts": r.attrs.get("source_facts", ()),
                            },
                        )
                    )

    # Integrity validation (TRD-04.1 §3.7): drop edges with a dangling
    # endpoint rather than let a downstream traversal crash on a missing
    # node.
    valid_edges = tuple(
        e for e in all_edges if e.source_id in all_nodes and e.target_id in all_nodes
    )

    # De-duplicate by (source, target, kind) — GraphEdge.attrs is a plain
    # Mapping (unhashable), so dedup keys off the identity-bearing fields
    # rather than routing through a set() of whole edges.
    dedup: dict[tuple[str, str, str], GraphEdge] = {}
    for e in valid_edges:
        dedup.setdefault((e.source_id, e.target_id, e.kind), e)

    sorted_nodes = tuple(sorted(all_nodes.values(), key=lambda n: n.node_id))
    sorted_edges = tuple(
        sorted(dedup.values(), key=lambda e: (e.source_id, e.target_id, e.kind))
    )

    from nsca_engine.api import Graph  # local import — api.py is the one
    # module allowed to define Graph; graph/ depends on it only here, at
    # call time, so api.py -> graph/ (assess_device wiring) does not become
    # a circular import at module load time.

    return Graph(nodes=sorted_nodes, edges=sorted_edges)
