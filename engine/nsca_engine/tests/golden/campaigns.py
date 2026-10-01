"""The 20 golden campaigns for ``gate_determinism_golden_set``
(00-master-plan.md §7: "Runs 20 golden campaigns through the full pipeline
twice -> compare report hashes"; backend-01 §3's module layout names
``tests/golden/`` as exactly where this belongs).

Corpus-gap flag (same honesty as the M2/M4 reports): TRD-00 §8.2's real
corpus (200+ sanitised configurations across >=5 platforms) does not exist
in this repository. These 20 campaigns are deliberately-varied synthetic
constructions built from fixtures **already created** in M1-M4's own test
suite (``tests/fixtures/*``, ``tests/fixtures/graph_estate/*``,
``tests/fixtures/ap003/*``, ``tests/fixtures/branch_routers.py``) rather than
20 new configs invented from scratch for this milestone alone — reusing them
both keeps this file honest about what's real versus synthetic, and doubles
as extra coverage of those fixtures under a battery of campaign shapes they
were not originally exercised under.

Variety deliberately spans (per the M5 task brief): single-device and
multi-device campaigns, small (1) through large (40) fleets, all 7 taught
platforms (cisco_ios + the 6 M2 platforms — flat_path/brace/block_keyword/
xml/path_header paradigms plus cloud JSON), and same-platform vs.
cross-platform campaigns.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nsca_engine.tests.fixtures.branch_routers import branch_router_fleet
from nsca_engine.tests.helpers import (
    M2_FIXTURES,
    RICH_CONTROLS_CONFIG,
    WORKED_EXAMPLE_CONFIG,
)

_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
_AP003_DIR = _FIXTURES_DIR / "ap003"
_GRAPH_ESTATE_DIR = _FIXTURES_DIR / "graph_estate"


@dataclass(frozen=True, slots=True)
class GoldenCampaign:
    """One golden campaign: an id plus ``((device_id, config_text), ...)``,
    already sorted by ``device_id`` (D6 — deterministic input order is the
    caller's job, not something the pipeline should have to normalise)."""

    id: str
    devices: tuple[tuple[str, str], ...]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _m2(platform: str) -> str:
    return _read(M2_FIXTURES[platform])


def _campaign(campaign_id: str, devices: dict[str, str]) -> GoldenCampaign:
    return GoldenCampaign(
        id=campaign_id,
        devices=tuple(sorted(devices.items(), key=lambda kv: kv[0])),
    )


def _graph_estate_devices() -> dict[str, str]:
    return {
        f"GE-{path.stem.upper()}": _read(path)
        for path in sorted(_GRAPH_ESTATE_DIR.glob("*.cfg"))
    }


def _ap003_devices() -> dict[str, str]:
    return {
        "EDGE-FW-01": _read(_AP003_DIR / "edge_fw_01.cfg"),
        "CORE-SW-01": _read(_AP003_DIR / "core_sw_01.cfg"),
    }


def _branch_fleet_devices(total: int, defective: int) -> dict[str, str]:
    return dict(branch_router_fleet(total=total, defective=defective))


def _all_seven_platforms_devices() -> dict[str, str]:
    devices = {"MIX-CISCO-01": RICH_CONTROLS_CONFIG}
    for platform in sorted(M2_FIXTURES):
        devices[f"MIX-{platform.upper()}-01"] = _m2(platform)
    return devices


def _build_golden_campaigns() -> tuple[GoldenCampaign, ...]:
    campaigns = [
        # 1-2: single Cisco IOS device, two different fixture bodies.
        _campaign("cisco_single_worked_example", {"CORE-SW-01": WORKED_EXAMPLE_CONFIG}),
        _campaign("cisco_single_rich_controls", {"CORE-SW-01": RICH_CONTROLS_CONFIG}),
        # 3: the AP-003 two-device attack-path reproduction (M4's own
        # acceptance fixture, reused here under the golden-set gate too).
        _campaign("ap003_edge_and_core_pair", _ap003_devices()),
        # 4: the full 7-device M3 graph-estate reference topology.
        _campaign("graph_estate_full_seven_devices", _graph_estate_devices()),
        # 5-8: the M4 branch-router fleet generator at four fleet sizes,
        # each keeping ~75% defective (matching the M4 systemic-clustering
        # ratio) so every size stays above the TRD-06.3 §4.2 threshold.
        _campaign("branch_fleet_5_devices", _branch_fleet_devices(5, 4)),
        _campaign("branch_fleet_10_devices", _branch_fleet_devices(10, 8)),
        _campaign("branch_fleet_20_devices", _branch_fleet_devices(20, 15)),
        _campaign("branch_fleet_40_devices_full", _branch_fleet_devices(40, 31)),
        # 9-14: one single-device campaign per M2 platform/paradigm.
        _campaign("juniper_set_single_device", {"JNPR-SET-01": _m2("juniper_junos_set")}),
        _campaign("juniper_brace_single_device", {"JNPR-BRACE-01": _m2("juniper_junos_curly")}),
        _campaign("fortios_single_device", {"FTNT-01": _m2("fortios")}),
        _campaign("panos_single_device", {"PANOS-01": _m2("panos")}),
        _campaign("routeros_single_device", {"ROS-01": _m2("routeros")}),
        _campaign("cloud_fw_single_device", {"CLOUD-FW-01": _m2("cloud_generic_fw")}),
        # 15: one device per taught platform, all 7, in a single campaign —
        # the cross-platform estate shape assess_campaign must merge cleanly.
        _campaign("all_seven_platforms_mixed", _all_seven_platforms_devices()),
        # 16-18: cross-platform pairs (two devices, two different platforms).
        _campaign(
            "cisco_and_juniper_set_pair",
            {"CORE-SW-01": RICH_CONTROLS_CONFIG, "JNPR-SET-01": _m2("juniper_junos_set")},
        ),
        _campaign(
            "cisco_and_fortios_pair",
            {"CORE-SW-01": WORKED_EXAMPLE_CONFIG, "FTNT-01": _m2("fortios")},
        ),
        _campaign(
            "panos_and_routeros_pair",
            {"PANOS-01": _m2("panos"), "ROS-01": _m2("routeros")},
        ),
        # 19: AP-003 pair plus the full graph-estate topology in one
        # campaign (9 devices total) — exercises assess_campaign's estate
        # merge/reachability across two independently-built device groups
        # sharing one campaign, with disjoint device-id namespaces.
        _campaign("ap003_plus_graph_estate_combined", {**_ap003_devices(), **_graph_estate_devices()}),
        # 20: a differently-shaped branch fleet (mostly-compliant instead of
        # mostly-defective) — the systemic-clustering *non*-trigger case,
        # complementing #5-8's defective-heavy shape.
        _campaign("branch_fleet_30_mostly_compliant", _branch_fleet_devices(30, 6)),
    ]
    campaigns.sort(key=lambda c: c.id)
    return tuple(campaigns)


GOLDEN_CAMPAIGNS: tuple[GoldenCampaign, ...] = _build_golden_campaigns()
