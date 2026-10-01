"""Real `KnowledgeBase` construction and caching — M5 (backend-02 §5).

Closes the gap flagged throughout M1-M4 (`services/ingestion.py`,
`services/assessment.py`, `services/dispute.py`, `remediation/lockout.py`
docstrings): those call sites needed a real `nsca_engine.api.KnowledgeBase`
— schema registry + every loaded rulepack/control pack — and nothing in
`nsca_platform` built one from `nsca/knowledge/`. `load_knowledge_base`
itself is real (M5, `nsca_engine/api.py`); this module is the one place
`nsca_platform` calls it, with process-lifetime caching so the real disk
I/O + rulepack/control-pack parsing it performs happens once, not on every
request (`load_knowledge_base`'s own docstring: "the one allowed disk read
this contract permits ... performed once").

Cache key is the resolved knowledge directory path, not a single global —
so tests that point `NSCA_KNOWLEDGE_DIR` at a scratch directory (e.g. a
deliberately-broken rulepack fixture) don't collide with the real
`nsca/knowledge/` a concurrently-running app instance already cached.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from nsca_engine.api import KnowledgeBase, load_knowledge_base

# `nsca/knowledge/` relative to this file: knowledge_base_loader.py sits at
# nsca/platform/nsca_platform/knowledge_base_loader.py, so parents[2] is
# nsca/ itself.
_DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"

_cache: dict[str, KnowledgeBase] = {}
_lock = threading.Lock()


class KnowledgeBaseUnavailable(Exception):
    """Raised when no usable `KnowledgeBase` could be constructed (missing
    directory, zero loadable rulepacks/control packs, etc.) — callers at
    the service-layer boundary should catch this and fall back to their own
    documented fixture/degraded path (never invent a fake KnowledgeBase)."""


def knowledge_dir_from_env() -> Path:
    """`NSCA_KNOWLEDGE_DIR` overrides the default `nsca/knowledge/` — used
    by tests that need a scratch knowledge directory, and by deployments
    that keep knowledge content outside the repo checkout."""

    raw = os.environ.get("NSCA_KNOWLEDGE_DIR")
    return Path(raw) if raw else _DEFAULT_KNOWLEDGE_DIR


def get_knowledge_base(knowledge_dir: Path | str | None = None) -> KnowledgeBase:
    """Returns the cached `KnowledgeBase` for `knowledge_dir` (default:
    `knowledge_dir_from_env()`), building and caching it on first call.

    Raises `KnowledgeBaseUnavailable` (never a bare exception from
    `nsca_engine.api.load_knowledge_base`, so every caller can catch one
    exception type) if construction fails.
    """

    path = Path(knowledge_dir) if knowledge_dir is not None else knowledge_dir_from_env()
    key = str(path.resolve()) if path.exists() else str(path)

    with _lock:
        cached = _cache.get(key)
    if cached is not None:
        return cached

    try:
        kb = load_knowledge_base(path)
    except Exception as exc:  # noqa: BLE001 — normalised to one exception type
        raise KnowledgeBaseUnavailable(f"could not load KnowledgeBase from {path}: {exc}") from exc

    with _lock:
        _cache[key] = kb
    return kb


def clear_cache() -> None:
    """Test-only: drop every cached `KnowledgeBase` so a subsequent
    `get_knowledge_base()` call re-reads from disk. Production code never
    needs this — the knowledge directory is immutable for the lifetime of
    a running process (a new rulepack/control pack ratified by the learning
    subsystem takes effect on the next process start/restart, matching
    `load_knowledge_base`'s own "one allowed disk read" contract)."""

    with _lock:
        _cache.clear()
