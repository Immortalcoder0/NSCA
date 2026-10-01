"""Unit tests for fingerprint/signatures.py and fingerprint/confidence.py
(TRD-01.2). M1 scope: Cisco IOS signature scoring plus the decision
procedure's outcome routing (§3.3), including the margin requirement
(DD-01.2-02) exercised with synthetic two-platform scores."""

from __future__ import annotations

from fractions import Fraction

from nsca_engine.controls.rulepack_loader import load_rulepack
from nsca_engine.fingerprint import confidence as fp_confidence
from nsca_engine.fingerprint.signatures import score_platform
from nsca_engine.tests.helpers import RICH_CONTROLS_CONFIG, RULEPACK_PATH

_LOADED_RP = load_rulepack(RULEPACK_PATH)


def test_cisco_ios_config_scores_high_confidence():
    score = score_platform(RICH_CONTROLS_CONFIG, _LOADED_RP.signature_set)
    assert score >= Fraction(3, 4)


def test_juniper_like_config_scores_low_due_to_negative_signature():
    juniper_like = "set system services ssh protocol-version v2\nset system services ssh root-login deny\n"
    score = score_platform(juniper_like, _LOADED_RP.signature_set)
    assert score == Fraction(0)


def test_decide_known_outcome():
    decision = fp_confidence.decide(
        scores={"cisco_ios": Fraction(9, 10), "juniper_set": Fraction(1, 10)},
        signals_by_platform={"cisco_ios": ("line_regex:x",), "juniper_set": ()},
    )
    assert decision.outcome == fp_confidence.FingerprintOutcome.KNOWN
    assert decision.platform == "cisco_ios"


def test_decide_ambiguous_when_margin_too_small():
    decision = fp_confidence.decide(
        scores={"cisco_ios": Fraction(80, 100), "nxos": Fraction(78, 100)},
        signals_by_platform={"cisco_ios": (), "nxos": ()},
    )
    assert decision.outcome == fp_confidence.FingerprintOutcome.AMBIGUOUS
    assert decision.runner_up is not None


def test_decide_unknown_when_score_low_and_no_self_identification():
    decision = fp_confidence.decide(scores={"cisco_ios": Fraction(1, 10)}, signals_by_platform={})
    assert decision.outcome == fp_confidence.FingerprintOutcome.UNKNOWN


def test_decide_identifiable_untaught_when_self_identification_present():
    decision = fp_confidence.decide(
        scores={"cisco_ios": Fraction(1, 10)}, signals_by_platform={},
        self_identification=("RouterOS", "7.11.2"),
    )
    assert decision.outcome == fp_confidence.FingerprintOutcome.IDENTIFIABLE_UNTAUGHT
    assert decision.platform == "RouterOS"


def test_decide_low_confidence_band():
    decision = fp_confidence.decide(scores={"cisco_ios": Fraction(1, 2)}, signals_by_platform={})
    assert decision.outcome == fp_confidence.FingerprintOutcome.LOW_CONFIDENCE
