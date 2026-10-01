"""Device exposure classification (TRD-04.1 §3.6, FR-GRF-006).

Exposure is a property of a device's *position* in the merged estate graph,
never read from configuration (INV-04.1-03). Classifications, exactly as
TRD-04.1 §3.6 defines them:

    internet_facing  - an interface sits in an external zone, OR the device
                        has a default route (0.0.0.0/0) to a non-private
                        next hop, OR it terminates an external circuit
                        (not modelled by M1's facts — VPN/WAN termination
                        is out of reach without richer collection; flagged)
    dmz              - an interface is in a dmz zone and none is external
    isolated         - every interface is in a management zone and no
                        route reaches a non-management zone
    internal         - otherwise

M1/M3's zone derivation (`graph/build.py._derive_zone`) only distinguishes
``internal``/``external`` (Cisco has no explicit zone concept — TRD-04.1
§3.5's derivation table). Explicit ``dmz``/``management`` zones are only
possible for platforms that declare them (PAN-OS, FortiOS, SRX) — none of
which have zone-emitting facts wired into the graph builder yet (M3 scope:
Cisco IOS is the rich platform). Consequently ``dmz``/``isolated`` are
reachable in this implementation only when a graph explicitly carries a zone
node named ``dmz``/``management`` — supported so the classifier is correct
once such facts exist, exercised in tests via hand-built graphs rather than
real fixtures. Flagged as a limitation, not silently narrowed.
"""

from __future__ import annotations

from dataclasses import dataclass

from nsca_engine.api import Graph


@dataclass(frozen=True, slots=True)
class ExposureResult:
    classification: str  # internet_facing | dmz | internal | isolated
    confidence: str  # high | medium | low
    basis: tuple[str, ...]  # human-readable reasons, for evidence (G3)


def classify_device(graph: Graph, device_id: str) -> ExposureResult:
    """INV-04.1-03: computed purely from graph position. Ambiguous cases
    default to the more severe classification (§3.6 "the asymmetry favours
    the false alarm") — never silently resolved to the safer-looking one."""

    zone_names: set[str] = set()
    basis: list[str] = []

    interface_ids = {
        n.node_id for n in graph.nodes if n.kind == "interface" and n.device_id == device_id
    }
    for e in graph.edges:
        if e.kind == "in_zone" and e.source_id in interface_ids:
            zone_node = next((n for n in graph.nodes if n.node_id == e.target_id), None)
            if zone_node is not None:
                name = zone_node.attrs.get("name", zone_node.node_id)
                zone_names.add(name)
                basis.append(f"interface {e.source_id} in_zone {name}")

    has_default_route = False
    for n in graph.nodes:
        if n.kind == "route" and n.device_id == device_id and n.attrs.get("destination") in (
            "0.0.0.0/0", "0.0.0.0",
        ):
            has_default_route = True
            basis.append(f"default route via {n.attrs.get('next_hop')}")

    if not zone_names and not has_default_route:
        return ExposureResult(
            classification="internal", confidence="low",
            basis=("no interfaces or routes found for this device in the merged graph",),
        )

    if "external" in zone_names or has_default_route:
        return ExposureResult(
            classification="internet_facing", confidence="high" if zone_names else "medium",
            basis=tuple(basis),
        )

    if "dmz" in zone_names:
        return ExposureResult(classification="dmz", confidence="high", basis=tuple(basis))

    if zone_names and zone_names <= {"management"}:
        return ExposureResult(classification="isolated", confidence="high", basis=tuple(basis))

    if not zone_names:
        # Routes exist but none is a default route, and no zone info at
        # all — ambiguous. §3.6: default to the more severe classification,
        # never to `isolated`.
        return ExposureResult(
            classification="dmz", confidence="low",
            basis=("ambiguous: routes present but no zone information", *basis),
        )

    return ExposureResult(classification="internal", confidence="medium", basis=tuple(basis))


def classify_estate(graph: Graph) -> dict[str, ExposureResult]:
    """Every device present in the graph, sorted (D6)."""

    device_ids = sorted({n.device_id for n in graph.nodes if n.kind == "device"})
    return {device_id: classify_device(graph, device_id) for device_id in device_ids}
