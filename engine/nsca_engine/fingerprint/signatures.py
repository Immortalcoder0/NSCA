"""Weighted signature matching (TRD-01.2 §3.2) — M1 scope: Cisco IOS only.

Other platforms are M2 (task brief: "Just Cisco IOS needs to work correctly
for M1"). The decision procedure (§3.3, including the margin requirement of
DD-01.2-02) is implemented in full even though only one platform is loaded,
because a single-platform corpus can still legitimately produce
``LOW_CONFIDENCE``/``UNKNOWN`` outcomes worth testing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True, slots=True)
class Signature:
    kind: str  # line_regex | line_exact | comment_char | block_regex | negative
    pattern: str
    weight: Fraction

    def compiled(self) -> re.Pattern[str]:
        if self.kind == "line_exact":
            return re.compile(re.escape(self.pattern), re.MULTILINE)
        return re.compile(self.pattern, re.MULTILINE)


@dataclass(frozen=True, slots=True)
class PlatformSignatureSet:
    platform: str
    vendor: str
    signatures: tuple[Signature, ...]


def score_platform(text: str, sigset: PlatformSignatureSet) -> Fraction:
    """TRD-01.2 §3.2: ``score = Σ w_i · match_i``, normalised by the sum of
    positive weights. Negative signatures still subtract, uncapped, so a
    strong negative match can drive the score below zero (clamped at 0)."""

    lines = text.split("\n")
    total_positive = sum((s.weight for s in sigset.signatures if s.weight > 0), Fraction(0))
    if total_positive == 0:
        return Fraction(0)

    raw = Fraction(0)
    for sig in sigset.signatures:
        pattern = sig.compiled()
        if sig.kind == "comment_char":
            matched = any(line.strip() == sig.pattern for line in lines)
        else:
            matched = pattern.search(text) is not None
        if matched:
            raw += sig.weight

    normalised = raw / total_positive
    if normalised < 0:
        return Fraction(0)
    if normalised > 1:
        return Fraction(1)
    return normalised


def matched_signals(text: str, sigset: PlatformSignatureSet) -> tuple[str, ...]:
    """Which signatures fired — for explainability (TRD-01.2 §4
    ``signals_matched[]``)."""

    lines = text.split("\n")
    out = []
    for sig in sigset.signatures:
        pattern = sig.compiled()
        if sig.kind == "comment_char":
            matched = any(line.strip() == sig.pattern for line in lines)
        else:
            matched = pattern.search(text) is not None
        if matched:
            out.append(f"{sig.kind}:{sig.pattern}")
    return tuple(out)
