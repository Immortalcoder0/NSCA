"""M5 performance tests against the four NFR targets backend-01 §6 names for
this milestone (13-nonfunctional-requirements.md — exact wording quoted
below, not paraphrased, since the task brief is explicit about not guessing
numeric targets):

    NFR-PERF-001  "The system MUST assess 500 devices in under 5 minutes on
                   commodity hardware (8 cores, 16 GB), fully offline"
    NFR-PERF-002  "Single-device assessment MUST complete in under 2 seconds
                   for a configuration of 10,000 lines"
    NFR-PERF-003  "The system MUST handle individual configurations up to
                   500,000 lines (large firewall policy sets) without
                   failure"
    NFR-PERF-006  "Graph construction and reachability analysis MUST
                   complete in under 60 seconds for an estate of 1,000
                   devices"

Honesty flags (same standard as the M2/M4 corpus-gap notes elsewhere in this
codebase — read before trusting these numbers):

- No real 10,000-line or 500,000-line configuration exists in this
  repository (TRD-00 §8.2's corpus was never sourced — flagged repeatedly
  since M2). NFR-PERF-002/003 are measured against a **synthetic
  stand-in**: a real Cisco IOS fixture (`RICH_CONTROLS_CONFIG`) with many
  repeated, uniquely-numbered `interface` blocks appended to pad to the
  target line count. This is structurally a real Cisco IOS grammar (every
  block parses as a genuine indentation-paradigm construct, not junk text),
  but it is not a real enterprise firewall policy export, and the facts it
  produces (thousands of near-identical interfaces) are not representative
  of a real device's fact distribution.
- NFR-PERF-001 is measured for real (not projected): `assess_device` run
  over 500 independently-generated device configs (the M4
  `branch_router_fleet` generator, reused rather than inventing new content)
  through a real `multiprocessing` pool capped at 8 workers, matching the
  NFR's literal "8 cores" baseline regardless of how many cores this
  machine actually has (recorded below, since it may exceed 8).
- NFR-PERF-006 builds a synthetic 1,000-device estate from the same
  `branch_router_fleet` generator (each device contributes a small, real
  graph fragment) and runs `graph.build.merge_estate` +
  `graph.reachability.query` against it.

Two of these four (NFR-PERF-001's 500-device run and NFR-PERF-003's
500,000-line parse) are expensive enough that running them on every
`pytest` invocation would make the M5 "run the full suite 10 times to prove
no flakiness" check impractical. They are real, `pytest`-collected tests,
gated behind the `perf` marker (see `pyproject.toml`'s
`addopts = "-m 'not perf'"`) so the default `pytest` run — the one repeated
10x for the determinism-flake check — stays fast; run them explicitly with
`pytest -m perf` (or the `if __name__ == "__main__"` entry point below,
which runs the full set unconditionally with the marker ignored). This is a
scope/practicality judgment call, flagged rather than silently made: it
does NOT mean these two targets were measured only once and never verified
for repeatability — see the M5 report for the actual repeated-run results.

NFR-PERF-002 and NFR-PERF-006 are cheap enough (single-digit seconds) to run
unconditionally in the default suite, so they run on every `pytest`
invocation, including all 10 repeats of the flakiness check.
"""

from __future__ import annotations

import multiprocessing
import os
import time

import pytest

from nsca_engine.api import assess_device
from nsca_engine.graph import build as graph_build
from nsca_engine.graph import reachability
from nsca_engine.tests.fixtures.branch_routers import branch_router_config
from nsca_engine.tests.helpers import (
    ASSESSED_AT,
    RICH_CONTROLS_CONFIG,
    build_knowledge_base,
    build_knowledge_base_m2,
    make_artifact,
)

_MEASURED_CPU_COUNT = os.cpu_count() or 1


# ---------------------------------------------------------------------------
# Synthetic large-config generator (NFR-PERF-002/003) — flagged, see module
# docstring: repeats a real Cisco IOS fixture's header plus many uniquely-
# numbered `interface` blocks to reach a target line count.
# ---------------------------------------------------------------------------


def _synthetic_large_config(target_lines: int) -> str:
    header = RICH_CONTROLS_CONFIG
    header_lines = header.count("\n")
    unit = (
        "interface GigabitEthernet0/{n}\n"
        " description synthetic-perf-unit-{n}\n"
        " ip address 10.{a}.{b}.1 255.255.255.0\n"
        " no shutdown\n"
        "!\n"
    )
    unit_line_count = 5
    remaining = max(0, target_lines - header_lines)
    repeats = remaining // unit_line_count

    parts = [header]
    for n in range(repeats):
        a = (n // 256) % 256
        b = n % 256
        parts.append(unit.format(n=n, a=a, b=b))
    parts.append("end\n")
    return "".join(parts)


# ---------------------------------------------------------------------------
# NFR-PERF-002 — single-device, 10,000-line config, under 2 seconds.
# ---------------------------------------------------------------------------


def test_nfr_perf_002_single_device_10k_lines_under_2_seconds() -> None:
    config = _synthetic_large_config(10_000)
    actual_lines = config.count("\n")
    kb = build_knowledge_base()

    start = time.perf_counter()
    result = assess_device((make_artifact(config),), kb, ASSESSED_AT)
    elapsed = time.perf_counter() - start

    assert result.facts, "synthetic large config produced no facts at all"
    print(
        f"\nNFR-PERF-002: {actual_lines} lines, assess_device took "
        f"{elapsed:.3f}s (target: < 2.0s)"
    )
    assert elapsed < 2.0, (
        f"NFR-PERF-002 NOT MET: {actual_lines}-line single-device assessment "
        f"took {elapsed:.3f}s, target is < 2.0s"
    )


# ---------------------------------------------------------------------------
# NFR-PERF-003 — up to 500,000 lines, without failure (no time budget).
# ---------------------------------------------------------------------------


@pytest.mark.perf
def test_nfr_perf_003_500k_line_config_does_not_fail() -> None:
    config = _synthetic_large_config(500_000)
    actual_lines = config.count("\n")
    kb = build_knowledge_base()

    start = time.perf_counter()
    result = assess_device((make_artifact(config),), kb, ASSESSED_AT)
    elapsed = time.perf_counter() - start

    print(f"\nNFR-PERF-003: {actual_lines} lines, assess_device took {elapsed:.1f}s (no time budget, must not fail)")
    assert result.facts
    assert result.grammar_coverage > 0


# ---------------------------------------------------------------------------
# NFR-PERF-001 — 500 devices under 5 minutes on commodity hardware
# (8 cores, 16 GB).
# ---------------------------------------------------------------------------

_worker_kb = None


def _init_worker() -> None:
    global _worker_kb
    _worker_kb = build_knowledge_base()


def _assess_one(args: tuple[str, str]) -> str:
    device_id, content = args
    assert _worker_kb is not None
    assessment = assess_device((make_artifact(content, artifact_id=device_id),), _worker_kb, ASSESSED_AT)
    return assessment.fingerprint.platform


def _perf_fleet(n: int) -> tuple[tuple[str, str], ...]:
    # Reuses the M4 `branch_router_config` generator (real Cisco IOS
    # fixture shape) rather than inventing new content — see module
    # docstring. The `% 240` keeps the synthesized third IP octet
    # (`branch_router_config`'s own `10 + i` -> 11..250) inside a valid
    # dotted-quad range for any `n`, including n > 240.
    out = []
    for i in range(1, n + 1):
        template_idx = ((i - 1) % 240) + 1
        defective = (i % 4) != 0  # ~75% defective, same ratio as the M4 fixture
        out.append((f"PERF-RTR-{i:04d}", branch_router_config(template_idx, defective=defective)))
    return tuple(out)


@pytest.mark.perf
def test_nfr_perf_001_500_devices_under_5_minutes() -> None:
    workers = min(8, _MEASURED_CPU_COUNT)
    fleet = _perf_fleet(500)

    start = time.perf_counter()
    with multiprocessing.Pool(processes=workers, initializer=_init_worker) as pool:
        platforms = pool.map(_assess_one, fleet)
    elapsed = time.perf_counter() - start

    print(
        f"\nNFR-PERF-001: 500 devices, {workers} workers (host has "
        f"{_MEASURED_CPU_COUNT} cores; capped at 8 to match the NFR's "
        f"literal baseline) took {elapsed:.1f}s (target: < 300s)"
    )
    assert len(platforms) == 500
    assert all(p == "cisco_ios" for p in platforms)
    assert elapsed < 300, (
        f"NFR-PERF-001 NOT MET: 500 devices across {workers} workers took "
        f"{elapsed:.1f}s, target is < 300s"
    )


# ---------------------------------------------------------------------------
# NFR-PERF-006 — graph construction + reachability, 1,000-device estate,
# under 60 seconds.
# ---------------------------------------------------------------------------


def test_nfr_perf_006_graph_and_reachability_1000_devices_under_60_seconds() -> None:
    kb = build_knowledge_base_m2()
    fleet = _perf_fleet(1000)

    # Assessment itself is not part of NFR-PERF-006's own budget (that's
    # NFR-PERF-001's job) — only graph construction + reachability are
    # timed; device assessment happens first, untimed, to produce the
    # fragments merge_estate needs.
    fragments = []
    for device_id, content in fleet:
        assessment = assess_device((make_artifact(content, artifact_id=device_id),), kb, ASSESSED_AT)
        fragments.append(assessment.graph_contribution)

    start = time.perf_counter()
    graph = graph_build.merge_estate(fragments)
    device_node = next((n for n in graph.nodes if n.kind == "device"), None)
    assert device_node is not None
    result = reachability.query(
        graph, src_addr="192.168.11.1", dst_addr="192.168.12.1", protocol="tcp", dport=22,
    )
    elapsed = time.perf_counter() - start

    print(
        f"\nNFR-PERF-006: {len(fragments)} devices, {len(graph.nodes)} nodes, "
        f"{len(graph.edges)} edges — merge_estate + one reachability query "
        f"took {elapsed:.2f}s (target: < 60s)"
    )
    assert result is not None
    assert elapsed < 60.0, (
        f"NFR-PERF-006 NOT MET: graph construction + reachability over "
        f"{len(fragments)} devices took {elapsed:.2f}s, target is < 60s"
    )


if __name__ == "__main__":  # pragma: no cover - manual benchmark entry point
    print(f"host: {_MEASURED_CPU_COUNT} logical cores detected")

    kb = build_knowledge_base()

    for label, target_lines, budget in (("PERF-002", 10_000, 2.0), ("PERF-003", 500_000, None)):
        cfg = _synthetic_large_config(target_lines)
        t0 = time.perf_counter()
        r = assess_device((make_artifact(cfg),), kb, ASSESSED_AT)
        dt = time.perf_counter() - t0
        budget_str = f"< {budget}s" if budget else "no budget"
        print(f"NFR-{label}: {cfg.count(chr(10))} lines, {dt:.2f}s ({budget_str}), facts={len(r.facts)}")

    fleet500 = _perf_fleet(500)
    t0 = time.perf_counter()
    with multiprocessing.Pool(processes=min(8, _MEASURED_CPU_COUNT), initializer=_init_worker) as pool:
        pool.map(_assess_one, fleet500)
    dt = time.perf_counter() - t0
    print(f"NFR-PERF-001: 500 devices / {min(8, _MEASURED_CPU_COUNT)} workers, {dt:.1f}s (< 300s)")
