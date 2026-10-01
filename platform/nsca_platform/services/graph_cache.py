"""In-process campaign `Graph` cache — M5 pragmatic choice, documented.

**Judgment call (flagged, not silently resolved):** `services/dispute.py`'s
`_try_engine_reachability` and `remediation/lockout.py`'s equivalent both
need a real `nsca_engine.api.Graph` (merged estate nodes/edges) to call
`nsca_engine.api.query_reachability` for real. The full answer is a
persisted `graph_node`/`graph_edge` schema (Alembic migration + SQLAlchemy
models + mappers) so a `Graph` survives process restarts and can be
rebuilt for any historical campaign. Given M5's time budget, this module
is the pragmatic fallback instead: an in-process, per-`campaign_public_id`
cache of the `Graph` `assess_campaign` most recently produced for that
campaign, populated by `services/assessment.py.run_assessment` right after
it calls `assess_campaign`.

**What this buys:** dispute reachability verification and remediation
lockout checking can call the real engine for real, for any campaign that
has been assessed at least once since this process started — which is
exactly the scenario the M5 task's new tests exercise (assess, then
dispute/lockout-check in the same process).

**What this does NOT buy:** the graph is lost on process restart, is not
shared across worker processes (no multi-worker deployment exists yet —
`run_assessment` itself runs synchronously in the request-handling process,
per that module's own docstring), and is never invalidated except by a
fresh `assess_campaign` call for the same campaign. A real
`graph_node`/`graph_edge` schema remains the correct next step and is
flagged here explicitly so it isn't mistaken for "done."

**Extension (Phase 3 rehearsal fix, items 7/8's related systemic gap):**
`assess_campaign` also computes `attack_paths`/`systemic_findings` — real
per-campaign risk output that used to be discarded entirely, leaving
`GET /campaigns/{id}/attack-paths` and `/systemic` as fixed M0 stubs
regardless of campaign state. Rather than inventing a second storage
mechanism, `set_risk_findings`/`get_risk_findings` below extend this same
in-process, per-`campaign_public_id`, non-persisted cache pattern — same
tradeoffs as the `Graph` cache above (lost on restart, single-process
only), populated by the same `run_assessment` call site right after its
`assess_campaign` call. `set_graph`/`get_graph`'s existing signature and
cache dict are left untouched so `services/dispute.py`, `remediation/
lockout.py`, and existing tests that call `set_graph` directly keep
working exactly as before.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from nsca_engine.api import Graph

if TYPE_CHECKING:
    from nsca_engine.api import AttackPath, SystemicFindingCandidate

_cache: dict[str, Graph] = {}
_risk_cache: dict[str, tuple[tuple["AttackPath", ...], tuple["SystemicFindingCandidate", ...]]] = {}
_lock = threading.Lock()


def set_graph(campaign_public_id: str, graph: Graph) -> None:
    with _lock:
        _cache[campaign_public_id] = graph


def get_graph(campaign_public_id: str) -> Graph | None:
    with _lock:
        return _cache.get(campaign_public_id)


def set_risk_findings(
    campaign_public_id: str,
    attack_paths: "tuple[AttackPath, ...]",
    systemic_findings: "tuple[SystemicFindingCandidate, ...]",
) -> None:
    with _lock:
        _risk_cache[campaign_public_id] = (attack_paths, systemic_findings)


def get_risk_findings(
    campaign_public_id: str,
) -> "tuple[tuple[AttackPath, ...], tuple[SystemicFindingCandidate, ...]] | None":
    with _lock:
        return _risk_cache.get(campaign_public_id)


def clear() -> None:
    """Test-only: drop every cached graph and risk-findings entry."""

    with _lock:
        _cache.clear()
        _risk_cache.clear()
