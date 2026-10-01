"""Metamorphic testing (TRD-11.2), first-instance harness per backend-01
§5.5: semantics-preserving input mutations must not change the extracted
facts. M1 builds one mutation type end to end (whitespace alteration) and
one more (block reordering) as the pattern proof — the full mutation
catalogue (object renaming, abbreviation, comment insertion, line-ending
changes, equivalent-syntax substitution) is TRD-11.2's own scope, not M1's.
"""

from __future__ import annotations

from nsca_engine.api import assess_device
from nsca_engine.tests.helpers import (
    ASSESSED_AT,
    RICH_CONTROLS_CONFIG,
    build_knowledge_base,
    make_artifact,
)


def _fact_signature(assessment):
    """A comparable, order-independent signature of a device assessment's
    fact set: (path, value, provenance.source) — deliberately excluding
    line numbers, which a mutation is *expected* to shift."""

    return sorted(
        (f.path, repr(f.value), f.provenance.source.value) for f in assessment.facts
    )


def _verdict_signature(assessment):
    return sorted((f.control_id, f.verdict.value) for f in assessment.findings)


def test_whitespace_alteration_preserves_facts_and_verdicts():
    """Trailing whitespace and blank-line-count changes must not alter a
    single extracted fact or verdict."""

    kb = build_knowledge_base()
    mutated = RICH_CONTROLS_CONFIG.replace("\n", "   \n")  # trailing spaces on every line
    mutated = mutated.replace("!\n", "!\n\n")  # extra blank lines after separators

    original = assess_device((make_artifact(RICH_CONTROLS_CONFIG),), kb, ASSESSED_AT)
    mutant = assess_device((make_artifact(mutated, artifact_id="ART-MUT"),), kb, ASSESSED_AT)

    assert _fact_signature(original) == _fact_signature(mutant)
    assert _verdict_signature(original) == _verdict_signature(mutant)


def test_block_reordering_preserves_facts_and_verdicts():
    """Reordering independent top-level blocks (which do not participate in
    the VTY overlap-resolution mechanism) must not change the fact set."""

    kb = build_knowledge_base()

    block_a = "logging host 10.0.0.200\n"
    block_b = "ntp server 10.0.0.201\n"
    block_c = "snmp-server community public RO\n"

    base = (
        "!\n"
        "version 15.2\n"
        "hostname CORE-SW-01\n"
        "!\n"
        "username admin privilege 15 password 7 0822455D0A16\n"
        "!\n"
        "line vty 0 4\n"
        " transport input ssh\n"
        " exec-timeout 5 0\n"
        "!\n"
    )

    config_1 = base + block_a + block_b + block_c
    config_2 = base + block_c + block_a + block_b

    r1 = assess_device((make_artifact(config_1, artifact_id="ART-A"),), kb, ASSESSED_AT)
    r2 = assess_device((make_artifact(config_2, artifact_id="ART-B"),), kb, ASSESSED_AT)

    assert _fact_signature(r1) == _fact_signature(r2)
    assert _verdict_signature(r1) == _verdict_signature(r2)
