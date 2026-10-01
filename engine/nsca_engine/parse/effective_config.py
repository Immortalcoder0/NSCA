"""Effective configuration resolution (TRD-02.3) — M1 scope: the Cisco
overlapping ``line vty`` case (TRD-02.3 §3.5, DD-02.3-03), called out in
backend-01 §5.2 as the subsystem to build first because it is the highest-risk
one to under-build.

Other mechanisms (PAN-OS layered merge, Juniper group expansion, FortiOS VDOM
scoping) are M2+ — not needed for a Cisco IOS M1 and explicitly out of scope
per the task brief ("do not build parsers for other platforms").
"""

from __future__ import annotations

from dataclasses import dataclass

from nsca_engine.parse.grammar import Node, ParseTree

# Maps a vty-range child statement's head token to the canonical attribute
# name used to key per-instance overlay resolution (DD-02.3-03).
_VTY_ATTR_HEADS: dict[str, str] = {
    "transport": "transport_input",
    "exec-timeout": "exec_timeout",
    "login": "login",
    "access-class": "access_class",
    "password": "password",
}


@dataclass(frozen=True, slots=True)
class VtyInstance:
    """One resolved, non-overlapping sub-range of VTY line numbers
    (TRD-02.3 §3.5). ``attrs`` maps canonical attribute name to the
    *declaring* statement `Node` whose evidence (lines, raw text) backs it —
    the later-declared stanza wins per attribute, not per whole stanza
    (DD-02.3-03)."""

    lo: int
    hi: int
    attrs: dict[str, Node]


@dataclass(frozen=True, slots=True)
class EffectiveConfig:
    """The effective view of one device's parse tree (TRD-02.3 §3.2,
    trimmed to what M1 needs: the tree itself, for non-ranged extraction,
    plus resolved VTY instances)."""

    tree: ParseTree
    vty_instances: tuple[VtyInstance, ...]


def _vty_attr_name(node: Node) -> str | None:
    head = node.head.lower()
    return _VTY_ATTR_HEADS.get(head)


def resolve(tree: ParseTree) -> EffectiveConfig:
    """Resolve overlapping ``line vty`` ranges into a minimal partition of
    non-overlapping instances, each carrying the winning declaration per
    attribute (TRD-02.3 §3.5 worked example, exactly).

    Declarations are walked in document order; for a given partition, the
    *last* declaration whose [lo, hi] covers it and which declares a given
    attribute wins for that attribute. A declaration that does not mention an
    attribute leaves an earlier winning declaration's value untouched for
    that partition — this is precisely the mechanism that produces
    ``vty[5..15].exec_timeout = ⊥`` in the TRD's own example.
    """

    vty_containers: list[tuple[int, int, Node]] = []
    for node in tree.walk():
        if node.context == "vty_range":
            try:
                lo = int(node.context_params.get("lo", ""))
                hi = int(node.context_params.get("hi", ""))
            except ValueError:
                continue
            vty_containers.append((lo, hi, node))

    if not vty_containers:
        return EffectiveConfig(tree=tree, vty_instances=())

    boundaries: set[int] = set()
    for lo, hi, _ in vty_containers:
        boundaries.add(lo)
        boundaries.add(hi + 1)
    sorted_bounds = sorted(boundaries)

    partitions: list[tuple[int, int]] = []
    for a, b in zip(sorted_bounds, sorted_bounds[1:], strict=False):
        partitions.append((a, b - 1))

    instances: list[VtyInstance] = []
    for part_lo, part_hi in partitions:
        attrs: dict[str, Node] = {}
        for lo, hi, container in vty_containers:  # document order == later wins
            if lo <= part_lo and part_hi <= hi:
                for child in tree.children_of(container.id):
                    attr_name = _vty_attr_name(child)
                    if attr_name is not None:
                        attrs[attr_name] = child
        if attrs:
            instances.append(VtyInstance(lo=part_lo, hi=part_hi, attrs=attrs))

    instances.sort(key=lambda v: v.lo)
    return EffectiveConfig(tree=tree, vty_instances=tuple(instances))
