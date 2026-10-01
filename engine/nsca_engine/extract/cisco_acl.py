"""Cisco IOS graph-relevant fact extraction (TRD-04.1 input side).

M1's declarative extractor DSL (``extract/runtime.py``) supports only
``scope: any`` / ``scope: vty`` (its own docstring flags full ``context``
scope selection as an M2+ extension). Object-group membership and ACL
rule-to-interface binding are inherently *parent/child* relationships in the
parse tree (a ``network-object``/``group-object`` line's meaning depends on
which ``object-group network NAME`` container encloses it; an
``ip access-group`` line's meaning depends on which ``interface`` container
encloses it) that the flat regex-capture DSL has no way to express without a
non-trivial DSL extension.

Rather than bolt a parent-context feature onto the generic runtime under M3
time pressure (touching machinery every other platform's rulepack also
depends on), this module walks the Cisco IOS parse tree directly and emits
the same ``Fact`` shape extractors produce, with the same provenance
discipline (explicit, lines, excerpt, extractor id). This keeps facts as the
interface between extraction and the graph builder (TRD-04.1 §3.2: graph
construction is "a pure function of the campaign's fact sets") while being
honest that this is a Cisco-specific, code-based extractor rather than a
YAML-declared one — flagged as a judgment call in the M3 report.

Fact paths introduced here (none collide with the M1/M2 rulepacks' paths):

  filter.objects[i].name                          address-object group name
  filter.object_members[i].group                  owning group name
  filter.object_members[i].member                 literal CIDR/host, or
                                                    another group's name
  filter.acl_rules[i].acl_id
  filter.acl_rules[i].seq                          source order within device
  filter.acl_rules[i].action                       "permit" | "deny"
  filter.acl_rules[i].protocol
  filter.acl_rules[i].source                       object name or literal CIDR
  filter.acl_rules[i].source_is_object             bool
  filter.acl_rules[i].destination
  filter.acl_rules[i].destination_is_object        bool
  filter.acl_rules[i].dest_port                    str | None
  interface.entries[i].name
  interface.entries[i].ip_address                  CIDR string | None
  interface.acl_bindings[i].interface
  interface.acl_bindings[i].acl_id
  interface.acl_bindings[i].direction              "in" | "out"
  route.static[i].destination                      CIDR string
  route.static[i].next_hop
"""

from __future__ import annotations

import ipaddress
import re

from nsca_engine.parse.grammar import Node, ParseTree
from nsca_engine.types import Fact, Provenance, ProvenanceSource

_EXTRACTOR = "cisco_ios.graph.acl_topology@v1"

_ACL_HEADER = re.compile(r"^ip access-list extended (?P<name>\S+)$")
_RULE = re.compile(r"^(?P<action>permit|deny) (?P<proto>\S+) (?P<rest>.+)$")
_OBJ_GROUP_HEADER = re.compile(r"^object-group network (?P<name>\S+)$")
_NET_OBJECT_HOST = re.compile(r"^network-object host (?P<ip>\S+)$")
_NET_OBJECT_ANY = re.compile(r"^network-object any$")
_NET_OBJECT_PAIR = re.compile(r"^network-object (?P<ip>\S+) (?P<wc>\S+)$")
_NET_OBJECT_GROUP = re.compile(r"^network-object object-group (?P<name>\S+)$")
_GROUP_OBJECT = re.compile(r"^group-object (?P<name>\S+)$")
_INTERFACE_HEADER = re.compile(r"^interface (?P<name>\S+)$")
_IP_ADDRESS = re.compile(r"^ip address (?P<ip>\S+) (?P<mask>\S+)$")
_ACCESS_GROUP = re.compile(
    r"^ip access-group (?P<acl>\S+) (?P<dir>in|out)$"
)
_STATIC_ROUTE = re.compile(
    r"^ip route (?P<dest>\S+) (?P<mask>\S+) (?P<next_hop>\S+)$"
)


def normalize_network(ip: str, mask_or_wildcard: str, *, is_wildcard: bool) -> str:
    """Best-effort normalisation to CIDR notation. Falls back to the raw
    ``ip mask`` pair (space-joined) when the mask/wildcard is not a clean
    contiguous prefix — never silently drops information."""

    try:
        if is_wildcard:
            inverted = ".".join(str(255 - int(o)) for o in mask_or_wildcard.split("."))
            net = ipaddress.IPv4Network(f"{ip}/{inverted}", strict=False)
        else:
            net = ipaddress.IPv4Network(f"{ip}/{mask_or_wildcard}", strict=False)
        return str(net)
    except (ValueError, OSError):
        return f"{ip} {mask_or_wildcard}"


def normalize_interface_address(ip: str, mask: str) -> str:
    """Like `normalize_network` but preserves the host bits (an interface's
    own address, not the network it sits on) — ``203.0.113.1 255.255.255.0``
    becomes ``203.0.113.1/24``, not ``203.0.113.0/24``. Subnet-membership
    computations downstream (`graph/build.py`, `graph/reachability.py`) call
    ``ipaddress.ip_network(..., strict=False)`` on this value, which derives
    the network correctly regardless of the host bits present."""

    try:
        iface = ipaddress.IPv4Interface(f"{ip}/{mask}")
        return str(iface)
    except (ValueError, OSError):
        return f"{ip} {mask}"


def _parse_selector(tokens: tuple[str, ...], idx: int) -> tuple[str, bool, int]:
    """Returns (value, is_object, next_idx). ``value`` is a bare object
    name when ``is_object``; otherwise a normalised literal (CIDR or
    ``any``/``0.0.0.0/0``/``host`` form)."""

    tok = tokens[idx]
    if tok == "any":
        return "0.0.0.0/0", False, idx + 1
    if tok == "host":
        return f"{tokens[idx + 1]}/32", False, idx + 2
    if tok == "object-group":
        return tokens[idx + 1], True, idx + 2
    # bare "ip wildcard" pair
    return normalize_network(tok, tokens[idx + 1], is_wildcard=True), False, idx + 2


def extract_graph_facts(tree: ParseTree, artifact_id: str) -> tuple[Fact, ...]:
    """Walk the Cisco IOS parse tree and emit graph-relevant facts (ACLs,
    object-groups, interfaces, static routes). Deterministic: nodes are
    walked in document order (``ParseTree.walk``, TRD-02.1 §3.1), and
    collection indices are assigned in that same order — two runs over the
    same tree produce byte-identical fact lists (D6)."""

    facts: list[Fact] = []

    obj_idx = 0
    member_idx = 0
    rule_idx = 0
    iface_idx = 0
    binding_idx = 0
    route_idx = 0

    def _prov(node: Node) -> Provenance:
        lines = (
            (node.line_start,)
            if node.line_start == node.line_end
            else tuple(range(node.line_start, node.line_end + 1))
        )
        return Provenance(
            source=ProvenanceSource.EXPLICIT,
            artifact_id=artifact_id,
            lines=lines,
            excerpt=tree.raw(node),
            extractor=_EXTRACTOR,
        )

    for node in tree.walk():
        if node.kind not in ("statement", "container"):
            continue
        text = tree.raw(node).strip()

        m = _OBJ_GROUP_HEADER.match(text)
        if m:
            group_name = m.group("name")
            facts.append(
                Fact(
                    path=f"filter.objects[{obj_idx}].name",
                    value=group_name, type="string", provenance=_prov(node),
                )
            )
            obj_idx += 1
            for child in tree.children_of(node.id):
                if child.kind not in ("statement", "container"):
                    continue
                ctext = tree.raw(child).strip()
                member: str | None = None
                cm = _NET_OBJECT_HOST.match(ctext)
                if cm:
                    member = f"{cm.group('ip')}/32"
                elif _NET_OBJECT_ANY.match(ctext):
                    member = "0.0.0.0/0"
                elif (cm := _NET_OBJECT_GROUP.match(ctext)):
                    member = cm.group("name")
                elif (cm := _GROUP_OBJECT.match(ctext)):
                    member = cm.group("name")
                elif (cm := _NET_OBJECT_PAIR.match(ctext)):
                    member = normalize_network(cm.group("ip"), cm.group("wc"), is_wildcard=True)
                if member is not None:
                    facts.append(
                        Fact(
                            path=f"filter.object_members[{member_idx}].group",
                            value=group_name, type="string", provenance=_prov(child),
                        )
                    )
                    facts.append(
                        Fact(
                            path=f"filter.object_members[{member_idx}].member",
                            value=member, type="string", provenance=_prov(child),
                        )
                    )
                    member_idx += 1
            continue

        m = _ACL_HEADER.match(text)
        if m:
            acl_id = m.group("name")
            for child in tree.children_of(node.id):
                if child.kind not in ("statement", "container"):
                    continue
                ctext = tree.raw(child).strip()
                rm = _RULE.match(ctext)
                if not rm:
                    continue
                action, proto, rest = rm.group("action"), rm.group("proto"), rm.group("rest")
                tokens = tuple(rest.split())
                src, src_is_obj, next_idx = _parse_selector(tokens, 0)
                dst, dst_is_obj, next_idx = _parse_selector(tokens, next_idx)
                dest_port = " ".join(tokens[next_idx:]) or None
                for field, value in (
                    ("acl_id", acl_id), ("seq", rule_idx), ("action", action),
                    ("protocol", proto), ("source", src), ("source_is_object", src_is_obj),
                    ("destination", dst), ("destination_is_object", dst_is_obj),
                    ("dest_port", dest_port), ("line", child.line_start),
                ):
                    facts.append(
                        Fact(
                            path=f"filter.acl_rules[{rule_idx}].{field}",
                            value=value, type="unknown", provenance=_prov(child),
                        )
                    )
                rule_idx += 1
            continue

        m = _INTERFACE_HEADER.match(text)
        if m:
            iface_name = m.group("name")
            ip_addr: str | None = None
            for child in tree.children_of(node.id):
                if child.kind not in ("statement", "container"):
                    continue
                ctext = tree.raw(child).strip()
                im = _IP_ADDRESS.match(ctext)
                if im:
                    ip_addr = normalize_interface_address(im.group("ip"), im.group("mask"))
                ag = _ACCESS_GROUP.match(ctext)
                if ag:
                    for field, value in (
                        ("interface", iface_name), ("acl_id", ag.group("acl")),
                        ("direction", ag.group("dir")),
                    ):
                        facts.append(
                            Fact(
                                path=f"interface.acl_bindings[{binding_idx}].{field}",
                                value=value, type="string", provenance=_prov(child),
                            )
                        )
                    binding_idx += 1
            facts.append(
                Fact(
                    path=f"interface.entries[{iface_idx}].name",
                    value=iface_name, type="string", provenance=_prov(node),
                )
            )
            facts.append(
                Fact(
                    path=f"interface.entries[{iface_idx}].ip_address",
                    value=ip_addr, type="string", provenance=_prov(node),
                )
            )
            iface_idx += 1
            continue

        m = _STATIC_ROUTE.match(text)
        if m:
            dest = normalize_network(m.group("dest"), m.group("mask"), is_wildcard=False)
            facts.append(
                Fact(
                    path=f"route.static[{route_idx}].destination",
                    value=dest, type="string", provenance=_prov(node),
                )
            )
            facts.append(
                Fact(
                    path=f"route.static[{route_idx}].next_hop",
                    value=m.group("next_hop"), type="string", provenance=_prov(node),
                )
            )
            route_idx += 1
            continue

    return tuple(facts)
