"""Unit tests for `risk/severity.py` (TRD-06.1)."""

from __future__ import annotations

from nsca_engine.graph.exposure import ExposureResult
from nsca_engine.risk import severity as risk_severity
from nsca_engine.types import DeviceFinding, PassQuality, Severity, Verdict


def _fail_finding(severity: Severity, control_id: str = "NSCA-MGMT-002") -> DeviceFinding:
    return DeviceFinding(
        control_id=control_id, verdict=Verdict.FAIL, pass_quality=None,
        unknown_reason=None, severity=severity, severity_reason=None,
        evidence=(), framework_refs=(), contamination_reason=None, coverage_inputs={},
    )


def test_internet_facing_elevates_to_critical():
    finding = _fail_finding(Severity.HIGH)
    exposure = ExposureResult(classification="internet_facing", confidence="high", basis=())
    wf = risk_severity.weight(finding, "DEV-1", exposure)
    assert wf.severity_base == Severity.HIGH
    assert wf.severity_effective == Severity.CRITICAL
    assert wf.severity_reason is not None
    assert "internet_facing" in wf.severity_reason


def test_isolated_reduces_severity():
    finding = _fail_finding(Severity.CRITICAL)
    exposure = ExposureResult(classification="isolated", confidence="high", basis=())
    wf = risk_severity.weight(finding, "DEV-1", exposure)
    assert wf.severity_effective == Severity.MEDIUM
    assert wf.severity_reason is not None


def test_internal_exposure_leaves_severity_unchanged_with_no_reason():
    finding = _fail_finding(Severity.HIGH)
    exposure = ExposureResult(classification="internal", confidence="medium", basis=())
    wf = risk_severity.weight(finding, "DEV-1", exposure)
    assert wf.severity_effective == Severity.HIGH
    assert wf.severity_reason is None
    assert wf.modifiers_fired == ()


def test_four_exposure_classes_differ_v_06_1_001():
    """V-06.1-001: identical finding on four devices classified
    internet_facing, dmz, internal and isolated differs per the declared
    modifiers."""

    base = Severity.HIGH
    results = {
        cls: risk_severity.weight(
            _fail_finding(base), f"DEV-{cls}",
            ExposureResult(classification=cls, confidence="high", basis=()),
        ).severity_effective
        for cls in ("internet_facing", "dmz", "internal", "isolated")
    }
    assert results["internet_facing"] == Severity.CRITICAL
    assert results["dmz"] == Severity.HIGH
    assert results["internal"] == Severity.HIGH
    assert results["isolated"] == Severity.MEDIUM
    assert len(set(results.values())) > 1


def test_unknown_exposure_sets_context_incomplete_v_06_1_003():
    finding = _fail_finding(Severity.HIGH)
    wf = risk_severity.weight(finding, "DEV-1", None)
    assert wf.severity_effective == Severity.HIGH
    assert wf.severity_context_incomplete is True
    assert wf.modifiers_fired == ()


def test_pass_verdict_never_weighted():
    finding = DeviceFinding(
        control_id="NSCA-MGMT-002", verdict=Verdict.PASS, pass_quality=PassQuality.MEANINGFUL,
        unknown_reason=None, severity=Severity.HIGH, severity_reason=None,
        evidence=(), framework_refs=(), contamination_reason=None, coverage_inputs={},
    )
    exposure = ExposureResult(classification="internet_facing", confidence="high", basis=())
    wf = risk_severity.weight(finding, "DEV-1", exposure)
    assert wf.severity_effective == Severity.HIGH
    assert wf.severity_reason is None


def test_every_escalation_records_a_reason_v_06_1_002():
    for base in Severity:
        for cls in ("internet_facing", "dmz", "isolated"):
            wf = risk_severity.weight(
                _fail_finding(base), "DEV-1",
                ExposureResult(classification=cls, confidence="high", basis=()),
            )
            if wf.severity_effective != wf.severity_base:
                assert wf.severity_reason, (base, cls, wf)


def test_deterministic_repeat():
    finding = _fail_finding(Severity.HIGH)
    exposure = ExposureResult(classification="internet_facing", confidence="high", basis=())
    first = risk_severity.weight(finding, "DEV-1", exposure)
    second = risk_severity.weight(finding, "DEV-1", exposure)
    assert first == second
