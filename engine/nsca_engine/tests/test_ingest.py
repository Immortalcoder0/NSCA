"""Unit tests for ingest/correlate.py, ingest/custody.py,
ingest/completeness.py (TRD-01.1)."""

from __future__ import annotations

from nsca_engine.ingest import completeness, correlate, custody


def test_hash_computed_before_transform_is_stable_and_sha256():
    content = b"hello\r\nworld\r\n"
    h1 = custody.hash_content(content)
    h2 = custody.hash_content(content)
    assert h1 == h2
    assert h1.startswith("sha256:")
    assert len(h1) == len("sha256:") + 64


def test_record_custody_captures_size_and_filename():
    record = custody.record_custody(
        artifact_id="ART-1", content=b"abc", filename="running-config.txt",
        received_from="upload",
    )
    assert record.size_bytes == 3
    assert record.filename == "running-config.txt"
    assert record.content_hash == custody.hash_content(b"abc")


def test_correlate_prefers_serial_over_hostname():
    """V-01.1-003 (DD-01.1-02): two artifact sets sharing hostname with
    distinct chassis serials must not merge."""

    candidates = (
        correlate.IdentityCandidate(artifact_id="A1", hostname="CORE-SW-01", chassis_serial="SN111"),
        correlate.IdentityCandidate(artifact_id="A2", hostname="CORE-SW-01", chassis_serial="SN222"),
    )
    results = correlate.correlate(candidates)
    assert any(r.outcome == correlate.CorrelationOutcome.ESCALATED for r in results)


def test_correlate_same_serial_different_hostname_merges_with_flag():
    candidates = (
        correlate.IdentityCandidate(artifact_id="A1", hostname="OLD-NAME", chassis_serial="SN999"),
        correlate.IdentityCandidate(artifact_id="A2", hostname="NEW-NAME", chassis_serial="SN999"),
    )
    results = correlate.correlate(candidates)
    assert len(results) == 1
    assert results[0].outcome == correlate.CorrelationOutcome.ASSIGNED
    assert results[0].reason == "hostname_changed"


def test_correlate_no_identity_signal_is_held():
    candidates = (correlate.IdentityCandidate(artifact_id="A1", hostname=None, chassis_serial=None),)
    results = correlate.correlate(candidates)
    assert results[0].outcome == correlate.CorrelationOutcome.HELD


def test_completeness_accounts_for_every_expected_device():
    expected = frozenset({f"DEV-{i}" for i in range(50)})
    received = frozenset({f"DEV-{i}" for i in range(43)})
    report = completeness.completeness(expected, received)
    assert len(report.missing) == 7
    assert report.missing == expected - received


def test_export_mode_verbose_detected_by_default_line_density():
    known_defaults = ("ip http server", "logging console", "no service password-encryption")
    text = "\n".join(known_defaults)
    result = completeness.detect_export_mode(text, known_defaults, threshold_verbose=3)
    assert result.mode == completeness.ExportMode.VERBOSE


def test_export_mode_unknown_when_no_defaults_present():
    result = completeness.detect_export_mode("hostname X\n", ("ip http server",))
    assert result.mode == completeness.ExportMode.UNKNOWN
