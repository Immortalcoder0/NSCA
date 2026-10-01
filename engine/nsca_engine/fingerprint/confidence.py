"""Fingerprint decision procedure (TRD-01.2 §3.3): outcome routing from
per-platform scores, including the margin requirement (DD-01.2-02) that
distinguishes a confident identification from an unresolved choice between
two similar platforms.

M1 loads exactly one platform (Cisco IOS), so ``AMBIGUOUS`` cannot actually
occur against the shipped rulepack set — the logic is implemented in full
regardless (M2 adds more platforms and immediately exercises it), and is
unit-tested with synthetic two-platform signature sets.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, auto
from fractions import Fraction

_KNOWN_THRESHOLD = Fraction(3, 4)
_MARGIN_THRESHOLD = Fraction(1, 5)
_LOW_THRESHOLD = Fraction(2, 5)


class FingerprintOutcome(Enum):
    KNOWN = auto()
    LOW_CONFIDENCE = auto()
    AMBIGUOUS = auto()
    IDENTIFIABLE_UNTAUGHT = auto()
    UNKNOWN = auto()


@dataclass(frozen=True, slots=True)
class FingerprintDecision:
    outcome: FingerprintOutcome
    platform: str | None
    confidence: Fraction
    runner_up: tuple[str, Fraction] | None
    signals_matched: tuple[str, ...]


def decide(
    scores: Mapping[str, Fraction],
    signals_by_platform: Mapping[str, tuple[str, ...]],
    self_identification: tuple[str, str] | None = None,
) -> FingerprintDecision:
    if not scores:
        if self_identification is not None:
            return FingerprintDecision(
                outcome=FingerprintOutcome.IDENTIFIABLE_UNTAUGHT,
                platform=self_identification[0], confidence=Fraction(0),
                runner_up=None, signals_matched=(),
            )
        return FingerprintDecision(
            outcome=FingerprintOutcome.UNKNOWN, platform=None,
            confidence=Fraction(0), runner_up=None, signals_matched=(),
        )

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    best_platform, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else Fraction(0)
    second_platform = ranked[1][0] if len(ranked) > 1 else None
    margin = best_score - second_score

    if best_score >= _KNOWN_THRESHOLD and margin >= _MARGIN_THRESHOLD:
        return FingerprintDecision(
            outcome=FingerprintOutcome.KNOWN, platform=best_platform,
            confidence=best_score, runner_up=None,
            signals_matched=signals_by_platform.get(best_platform, ()),
        )

    if best_score >= _KNOWN_THRESHOLD and margin < _MARGIN_THRESHOLD:
        return FingerprintDecision(
            outcome=FingerprintOutcome.AMBIGUOUS, platform=best_platform,
            confidence=best_score,
            runner_up=(second_platform, second_score) if second_platform else None,
            signals_matched=signals_by_platform.get(best_platform, ()),
        )

    if best_score < _LOW_THRESHOLD:
        if self_identification is not None:
            return FingerprintDecision(
                outcome=FingerprintOutcome.IDENTIFIABLE_UNTAUGHT,
                platform=self_identification[0], confidence=best_score,
                runner_up=None, signals_matched=(),
            )
        return FingerprintDecision(
            outcome=FingerprintOutcome.UNKNOWN, platform=None,
            confidence=best_score, runner_up=None, signals_matched=(),
        )

    return FingerprintDecision(
        outcome=FingerprintOutcome.LOW_CONFIDENCE, platform=best_platform,
        confidence=best_score, runner_up=None,
        signals_matched=signals_by_platform.get(best_platform, ()),
    )
