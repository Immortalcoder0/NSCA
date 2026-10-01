"""Exposure-weighted effective severity (TRD-06.1).

Scope note (flagged, not silently narrowed): TRD-06.1 §3.2 describes
``risk_modifiers`` as declared *on the control* (a YAML list of
``{if, severity}`` clauses evaluated as expressions). Nothing in the
knowledge base built so far (``controls/rulepack_loader.py``,
``knowledge/control_packs/*.yaml``, ``controls/evaluate.py``'s
``NativeControl``) carries such a field yet — extending the control-pack
schema and the expression evaluator to support ``risk_modifiers`` is a
knowledge-authoring change bigger than this milestone (M4's job is
campaign-wide risk computation on top of the M0-M3 contract, not extending
the control-pack YAML schema). This module instead applies a single,
documented, built-in modifier table keyed on ``device.exposure`` alone
(the exposure classification, TRD-04.1 §3.6 / ``graph/exposure.py``),
matching TRD-06.1 §3.2's own worked example (``internet_facing -> critical``,
``isolated -> medium``) plus a reasonable ``dmz -> high`` extension. This is
the "propose a default and record it" pattern used elsewhere in this engine
(backend-01 §8) — flagged in the M4 report, not silently resolved.

Determinism (TRD-06.1 §3.7): pure function of
``(finding, device_context, control)``. No clock, no randomness.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from nsca_engine.graph.exposure import ExposureResult
from nsca_engine.types import DeviceFinding, FindingKey, Severity, Verdict

if TYPE_CHECKING:
    from nsca_engine.api import DeviceAssessment

# Ordinal order, low -> high (matches types.Severity's documented band set).
_SEVERITY_RANK: Mapping[Severity, int] = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# DD-06.1-01: modifiers set an absolute level, not a delta. TRD-06.1 §3.2's
# own example plus a documented `dmz` extension (a DMZ-sited device is more
# exposed than `internal` but less than `internet_facing` — `high` sits
# between the two, matching how `dmz` already sits in the ordinal exposure
# scale in `graph/exposure.py`).
_EXPOSURE_MODIFIERS: Mapping[str, Severity] = {
    "internet_facing": Severity.CRITICAL,
    "dmz": Severity.HIGH,
    "isolated": Severity.MEDIUM,
    # "internal" deliberately absent: no modifier fires, effective == base
    # (TRD-06.1 §5 "Control with no risk_modifiers -> effective equals base").
}


@dataclass(frozen=True, slots=True)
class WeightedFinding:
    """TRD-06.1 §4's ``WeightedFinding`` interface shape."""

    device_id: str
    control_id: str
    severity_base: Severity
    severity_effective: Severity
    modifiers_fired: tuple[str, ...]
    severity_reason: str | None
    severity_context_incomplete: bool


def _clamp(severity: Severity) -> Severity:
    rank = max(0, min(4, _SEVERITY_RANK[severity]))
    for sev, r in _SEVERITY_RANK.items():
        if r == rank:
            return sev
    return severity  # pragma: no cover - defensive, unreachable


def weight(
    finding: DeviceFinding, device_id: str, exposure: ExposureResult | None
) -> WeightedFinding:
    """TRD-06.1 §4's ``weight(finding, device_context, control) ->
    WeightedFinding``. ``control`` is not threaded through separately here —
    everything this module needs from the control (``severity_base``) is
    already carried on ``finding`` (``DeviceFinding.severity`` is base
    severity, per that dataclass's own docstring).

    Only ``verdict == FAIL`` findings are risk-weighted (TRD-06.1's whole
    premise is "this FAIL is more/less dangerous depending on where the
    device sits" — a PASS or UNKNOWN doesn't carry a live risk to weight).
    Every other verdict returns ``effective == base`` with no modifier.
    """

    base = finding.severity

    if finding.verdict != Verdict.FAIL:
        return WeightedFinding(
            device_id=device_id, control_id=finding.control_id,
            severity_base=base, severity_effective=base,
            modifiers_fired=(), severity_reason=None,
            severity_context_incomplete=False,
        )

    if exposure is None:
        # TRD-06.1 §5: "Device exposure unknown -> No exposure modifier
        # fires; base severity; severity_context_incomplete set".
        return WeightedFinding(
            device_id=device_id, control_id=finding.control_id,
            severity_base=base, severity_effective=base,
            modifiers_fired=(), severity_reason=None,
            severity_context_incomplete=True,
        )

    modifier_severity = _EXPOSURE_MODIFIERS.get(exposure.classification)
    if modifier_severity is None:
        # "internal", or an unrecognised classification (defensive) -> no
        # modifier fires. DD-06.1-02's low-confidence handling: a low
        # confidence classification is still a real (if weaker) signal, not
        # an unknown one, so it fires normally but is not reported as
        # context-incomplete. A genuinely absent classification (exposure is
        # None, handled above) is what triggers severity_context_incomplete.
        return WeightedFinding(
            device_id=device_id, control_id=finding.control_id,
            severity_base=base, severity_effective=base,
            modifiers_fired=(), severity_reason=None,
            severity_context_incomplete=False,
        )

    effective = _clamp(modifier_severity)
    fired = (f"device.exposure == {exposure.classification}",)
    if effective == base:
        # INV-06.1-01 only requires a reason when severity *differs* from
        # base; recording the fired modifier even when it happens to equal
        # base would read as a spurious escalation.
        reason = None
    else:
        reason = (
            f"{base.value.upper()} -> {effective.value.upper()}: "
            f"elevated because device.exposure == {exposure.classification}"
            if _SEVERITY_RANK[effective] > _SEVERITY_RANK[base]
            else (
                f"{base.value.upper()} -> {effective.value.upper()}: "
                f"reduced because device.exposure == {exposure.classification}"
            )
        )

    return WeightedFinding(
        device_id=device_id, control_id=finding.control_id,
        severity_base=base, severity_effective=effective,
        modifiers_fired=fired, severity_reason=reason,
        severity_context_incomplete=False,
    )


def compute_effective_severities(
    device_assessments: tuple[DeviceAssessment, ...],
    exposures: Mapping[str, ExposureResult],
) -> dict[FindingKey, Severity]:
    """Campaign-wide pass: every ``(device, control)`` finding, weighted.

    Returns a ``dict[FindingKey, Severity]`` — the exact shape
    ``CampaignAssessment.effective_severities`` commits to. Kept as a plain
    function (not a method) so `api.assess_campaign` can call it directly;
    also independently unit-testable without going through the full
    campaign pipeline.
    """

    out: dict[FindingKey, Severity] = {}
    for da in sorted(device_assessments, key=lambda d: d.graph_contribution.device_id):
        device_id = da.graph_contribution.device_id
        exposure = exposures.get(device_id)
        for finding in sorted(da.findings, key=lambda f: f.control_id):
            wf = weight(finding, device_id, exposure)
            out[FindingKey(device_id=device_id, control_id=finding.control_id)] = (
                wf.severity_effective
            )
    return out
