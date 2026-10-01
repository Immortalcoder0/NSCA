"""``gate_determinism_golden_set`` (00-master-plan.md §7, TECH-STACK.md §16):
runs the 20 golden campaigns (``tests/golden/campaigns.py``) through the full
pipeline (``assess_device`` per device, then ``assess_campaign``) **twice**,
independently, and asserts the two runs produce byte-identical hashes.

"Byte-identical" is checked two ways per campaign, per the M5 task brief:
1. ``repr()`` equality on the full ``(device_assessments, campaign_assessment)``
   tuple (the exact mechanism ``test_assess_campaign_determinism.py`` already
   uses at M4) — catches any field-level divergence with a readable diff.
2. A real ``sha256`` hash of a canonical serialisation of that same repr
   string — the literal "hash comparison" TECH-STACK.md §16 names
   (``gate_determinism_golden_set``: "20 golden campaigns x 2 runs -> compare
   report hashes").

Each run builds its own **independently-constructed** ``KnowledgeBase``
(``build_knowledge_base_m2()`` called twice, not shared) — same rationale as
``test_determinism.py``'s ``kb1``/``kb2`` split: the guarantee under test is
"identical inputs, any process, any run" (00-master-plan.md §5.1), not merely
"the same Python object re-used."

This is a real, runnable gate — ``pytest`` exercises every campaign via
`pytest.mark.parametrize`, and `python -m nsca_engine.tests.test_golden_set`
runs the same check standalone with a plain pass/fail exit code, for a CI
step that wants that instead of pytest's own exit code.
"""

from __future__ import annotations

import hashlib
import sys

import pytest

from nsca_engine.api import KnowledgeBase, assess_campaign, assess_device
from nsca_engine.tests.golden.campaigns import GOLDEN_CAMPAIGNS, GoldenCampaign
from nsca_engine.tests.helpers import ASSESSED_AT, build_knowledge_base_m2, make_artifact


def _run_campaign(kb: KnowledgeBase, campaign: GoldenCampaign) -> str:
    """Run the full pipeline over one golden campaign and return a
    canonical, hashable string representation of everything both
    `assess_device` and `assess_campaign` produced."""

    device_assessments = tuple(
        assess_device((make_artifact(content, artifact_id=device_id),), kb, ASSESSED_AT)
        for device_id, content in campaign.devices
    )
    campaign_assessment = assess_campaign(device_assessments, kb)
    return repr(device_assessments) + "\n---campaign---\n" + repr(campaign_assessment)


def _sha256(canonical: str) -> str:
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_gate() -> list[str]:
    """Run every golden campaign through the pipeline twice against two
    independently-constructed `KnowledgeBase`s and return the ids of any
    campaign whose hash differed between runs (empty list = gate passes)."""

    kb_run_a = build_knowledge_base_m2()
    kb_run_b = build_knowledge_base_m2()

    failures = []
    for campaign in GOLDEN_CAMPAIGNS:
        canonical_a = _run_campaign(kb_run_a, campaign)
        canonical_b = _run_campaign(kb_run_b, campaign)
        if canonical_a != canonical_b or _sha256(canonical_a) != _sha256(canonical_b):
            failures.append(campaign.id)
    return failures


def test_golden_set_has_exactly_20_campaigns_with_unique_ids() -> None:
    assert len(GOLDEN_CAMPAIGNS) == 20
    ids = [c.id for c in GOLDEN_CAMPAIGNS]
    assert len(ids) == len(set(ids)), "golden campaign ids must be unique"


def test_golden_set_every_campaign_has_at_least_one_device() -> None:
    for campaign in GOLDEN_CAMPAIGNS:
        assert campaign.devices, f"{campaign.id} has no devices"


@pytest.fixture(scope="module")
def _kb_pair() -> tuple[KnowledgeBase, KnowledgeBase]:
    # Two independently-constructed KnowledgeBase objects, reloaded from
    # disk separately — shared across the parametrized tests below purely
    # for wall-clock speed (rulepack/control-pack YAML loading is not what
    # this gate is testing); the determinism guarantee under test is
    # per-campaign-run, not per-KnowledgeBase-construction.
    return build_knowledge_base_m2(), build_knowledge_base_m2()


@pytest.mark.parametrize("campaign", GOLDEN_CAMPAIGNS, ids=lambda c: c.id)
def test_golden_campaign_double_run_is_byte_identical(campaign: GoldenCampaign, _kb_pair) -> None:
    kb_a, kb_b = _kb_pair
    canonical_a = _run_campaign(kb_a, campaign)
    canonical_b = _run_campaign(kb_b, campaign)

    assert canonical_a == canonical_b, (
        f"golden campaign {campaign.id!r}: repr() diverged between two "
        "independent runs — determinism violation"
    )
    assert _sha256(canonical_a) == _sha256(canonical_b), (
        f"golden campaign {campaign.id!r}: sha256 hash diverged between two "
        "independent runs — determinism violation"
    )


if __name__ == "__main__":  # pragma: no cover - CI entry point
    failed = run_gate()
    if failed:
        print("gate_determinism_golden_set: FAILED for:", ", ".join(failed))
        sys.exit(1)
    print(f"gate_determinism_golden_set: clean ({len(GOLDEN_CAMPAIGNS)} campaigns, 2 runs each)")
    sys.exit(0)
