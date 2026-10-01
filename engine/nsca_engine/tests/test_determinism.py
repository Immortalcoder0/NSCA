"""G1 (determinism): identical inputs produce byte-identical output, across
independently-constructed KnowledgeBase objects and independent calls
(TRD-00 §6 G1, D6/D7)."""

from __future__ import annotations

from nsca_engine.api import assess_device
from nsca_engine.tests.helpers import (
    ASSESSED_AT,
    RICH_CONTROLS_CONFIG,
    build_knowledge_base,
    make_artifact,
)


def test_assess_device_is_deterministic_across_independent_runs():
    kb1 = build_knowledge_base()
    kb2 = build_knowledge_base()  # independently re-loaded from disk

    r1 = assess_device((make_artifact(RICH_CONTROLS_CONFIG),), kb1, ASSESSED_AT)
    r2 = assess_device((make_artifact(RICH_CONTROLS_CONFIG),), kb2, ASSESSED_AT)

    assert repr(r1.facts) == repr(r2.facts)
    assert repr(r1.findings) == repr(r2.findings)
    assert r1.scores == r2.scores
    assert r1.grammar_coverage == r2.grammar_coverage


def test_fact_iteration_order_is_sorted_by_path():
    kb = build_knowledge_base()
    result = assess_device((make_artifact(RICH_CONTROLS_CONFIG),), kb, ASSESSED_AT)
    paths = [f.path for f in result.facts]
    assert paths == sorted(paths)
