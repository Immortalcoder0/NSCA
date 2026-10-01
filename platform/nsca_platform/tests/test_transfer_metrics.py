"""Transfer metrics — TRD-08.4, backend-02 M3.

The transfer-metrics recording test (task brief) proves confirmations are
recorded live, per-confirmation, and that the curve is derivable from those
records alone in teaching order (INV-08.4-02, V-08.4-010).
"""

from __future__ import annotations

from nsca_platform.learning import transfer_metrics
from nsca_platform.tests.conftest import requires_db


def _run_session(conn, platform, *, order_hint_administrator="r.kulkarni", coverage_curve, outcomes, minutes):
    session = transfer_metrics.start_session(
        conn, platform=platform, administrator=order_hint_administrator, corpus_size=125, construct_count=48,
    )
    session_id = session["id"]
    import uuid as _uuid

    for i, (outcome, cov) in enumerate(zip(outcomes, coverage_curve), start=1):
        transfer_metrics.record_confirmation(
            conn, session_id=_uuid.UUID(session_id), question_rank=i,
            proposal_source="heuristic", outcome=outcome, coverage_after=cov,
        )
    return transfer_metrics.complete_session(conn, _uuid.UUID(session_id), wall_clock_minutes=minutes)


@requires_db
def test_session_and_confirmations_are_recorded_live(db_conn):
    result = _run_session(
        db_conn, "mikrotik_routeros",
        coverage_curve=[0.30, 0.55, 0.71, 0.71, 0.71],
        outcomes=["confirm", "confirm", "confirm", "edit", "not_relevant"],
        minutes=8.2,
    )
    assert result["complete"] is True
    assert result["confirmations_to_70pct"] == 3  # first index where coverage >= 0.70
    assert result["wall_clock_minutes"] == 8.2


@requires_db
def test_first_platform_ever_taught_gets_teaching_order_one(db_conn):
    result = _run_session(
        db_conn, "first_platform_ever",
        coverage_curve=[0.75], outcomes=["confirm"], minutes=5.0,
    )
    assert result["order"] == 1


@requires_db
def test_teaching_order_increments_across_sessions(db_conn):
    r1 = _run_session(db_conn, "platform_a", coverage_curve=[0.75], outcomes=["confirm"], minutes=5.0)
    r2 = _run_session(db_conn, "platform_b", coverage_curve=[0.75], outcomes=["confirm"], minutes=5.0)
    assert r2["order"] == r1["order"] + 1


@requires_db
def test_curve_is_ordered_by_teaching_order_not_platform_name_or_confirmations(db_conn):
    """INV-08.4-02 — the x-axis is teaching order, never re-sorted."""

    _run_session(db_conn, "zzz_platform_taught_first", coverage_curve=[0.75, 0.90], outcomes=["confirm", "confirm"], minutes=40.0)
    _run_session(db_conn, "aaa_platform_taught_second", coverage_curve=[0.75], outcomes=["confirm"], minutes=5.0)

    curve = transfer_metrics.curve(db_conn)
    platforms_in_curve = [p["platform"] for p in curve if p["platform"] in ("zzz_platform_taught_first", "aaa_platform_taught_second")]
    # zzz was taught first (lower order) despite sorting alphabetically after aaa.
    assert platforms_in_curve.index("zzz_platform_taught_first") < platforms_in_curve.index("aaa_platform_taught_second")


@requires_db
def test_incomplete_session_excluded_from_curve(db_conn):
    """V-08.4-011 — a session that never reaches 70% coverage is recorded
    as incomplete and excluded from the curve, counted separately."""

    result = _run_session(
        db_conn, "abandoned_platform",
        coverage_curve=[0.20, 0.35, 0.40], outcomes=["confirm", "confirm", "skip"], minutes=6.0,
    )
    assert result["complete"] is False
    assert result["confirmations_to_70pct"] is None

    curve = transfer_metrics.curve(db_conn)
    assert "abandoned_platform" not in {p["platform"] for p in curve}

    incomplete = transfer_metrics.incomplete_sessions(db_conn)
    assert "abandoned_platform" in {p["platform"] for p in incomplete}


@requires_db
def test_polarity_correction_rate_computed_and_thresholded(db_conn):
    """INV-08.4-03 — polarity correction rate is tracked as a safety
    signal, above 15% raises a release-blocking signal."""

    # 3 of 4 polarity-relevant answers were corrections -> 75% rate.
    result = _run_session(
        db_conn, "polarity_stress_test",
        coverage_curve=[0.75, 0.80, 0.85, 0.90],
        outcomes=["polarity_inverted", "polarity_inverted", "polarity_inverted", "confirm"],
        minutes=10.0,
    )
    assert result["polarity_correction_rate"] == 0.75

    m = transfer_metrics.metrics(db_conn, platform="polarity_stress_test")
    assert m["polarity_safety_signal"] == "release_blocking"


@requires_db
def test_proposal_acceptance_and_edit_rates_computed(db_conn):
    result = _run_session(
        db_conn, "rate_test_platform",
        coverage_curve=[0.3, 0.5, 0.7, 0.7],
        outcomes=["confirm", "confirm", "edit", "not_relevant"],
        minutes=4.0,
    )
    assert result["proposal_acceptance_rate"] == 0.5
    assert result["edit_rate"] == 0.25
    assert result["not_relevant_rate"] == 0.25


@requires_db
def test_metrics_endpoint_shape_matches_api_spec(db_conn):
    """15-api-specification.md §6's `GET /training/metrics` shape."""

    _run_session(db_conn, "cisco_ios_like", coverage_curve=[0.71], outcomes=["confirm"], minutes=41.0)
    result = transfer_metrics.metrics(db_conn)
    assert "platforms" in result
    assert "trend" in result
    if result["platforms"]:
        p = result["platforms"][0]
        assert {"order", "platform", "confirmations_to_70pct", "wall_clock_minutes", "proposal_acceptance_rate"} <= set(p)
