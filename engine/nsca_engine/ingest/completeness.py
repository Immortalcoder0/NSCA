"""Export-mode (verbose/terse) detection (TRD-01.1 §3.6) and collection
completeness accounting (§3.8).

M1 scope: export-mode detection implements the three-signal decision
procedure. Density-based calibration against a corpus distribution (the
third signal) needs a real corpus (M2+); M1 implements the first two signals
(explicit marker, default-line presence) and treats density as unavailable,
which per DD-01.1-03 ("unknown export mode is treated as terse") is the safe
direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from fractions import Fraction


class ExportMode(Enum):
    VERBOSE = auto()
    TERSE = auto()
    UNKNOWN = auto()


@dataclass(frozen=True, slots=True)
class ExportModeResult:
    mode: ExportMode
    confidence: Fraction


def detect_export_mode(
    text: str, known_default_lines: tuple[str, ...], threshold_verbose: int = 3
) -> ExportModeResult:
    present = sum(1 for line in known_default_lines if line in text)
    if present >= threshold_verbose:
        return ExportModeResult(mode=ExportMode.VERBOSE, confidence=Fraction(9, 10))
    if present == 0:
        # DD-01.1-03: without a density signal (M2+), do not claim TERSE with
        # confidence — fall through to UNKNOWN, which coverage treats as
        # terse anyway (safe direction, G2).
        return ExportModeResult(mode=ExportMode.UNKNOWN, confidence=Fraction(0))
    return ExportModeResult(mode=ExportMode.UNKNOWN, confidence=Fraction(0))


@dataclass(frozen=True, slots=True)
class CompletenessReport:
    expected: frozenset[str]
    received: frozenset[str]
    missing: frozenset[str]


def completeness(expected: frozenset[str], received: frozenset[str]) -> CompletenessReport:
    missing = expected - received
    return CompletenessReport(expected=expected, received=received, missing=missing)
