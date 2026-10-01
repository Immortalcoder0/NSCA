"""Transfer metrics — TRD-08.4, Stage 9 of 08-learning-system.md §2.

> The declining confirmation curve is the measurable answer to the problem
> statement's demand for "Scalability & Adaptation". It is the product's
> central claim, and it cannot be fabricated because the platform records
> every confirmation as it happens.

Recorded live, per confirmation (`transfer_metric_confirmation`), from the
*first* platform taught (TRD-08.4 §5.1, INV-08.4-02) — there is no separate
mechanism for shipped vs. taught rulepacks (07-vendor-rulepacks.md §1), so
the certified rulepacks shipped in the box go through this exact same
recording mechanism once their own teaching sessions are entered.

`curve()` returns points **in teaching order**, never re-sorted by
platform name or confirmation count (INV-08.4-02: "Plotting by platform
rather than teaching order... The claim being made becomes meaningless").
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from nsca_platform.db.models.learning import (
    transfer_metric_confirmation as confirmation_table,
)
from nsca_platform.db.models.learning import (
    transfer_metric_session as session_table,
)

COVERAGE_TARGET = 0.70  # TRD-08.4 §3's fixed 70% coverage target.

# INV-08.4-03 — polarity correction rate release-blocking thresholds.
POLARITY_RATE_HEALTHY = 0.05
POLARITY_RATE_INVESTIGATE = 0.15


class SessionNotFound(Exception):
    pass


def start_session(
    conn: Connection,
    *,
    platform: str,
    administrator: str,
    corpus_size: int,
    construct_count: int,
    same_family_as: str | None = None,
) -> dict[str, Any]:
    """Records a new teaching session. `teaching_order` is derived from
    how many sessions already exist — TRD-08.4 §5.1: "there is no separate
    mechanism for shipped vs. taught rulepacks", so the very first
    platform anyone teaches (including the product team's own onboarding
    of the platforms shipped in the box) gets `teaching_order = 1`."""

    existing = conn.execute(select(session_table.c.id)).fetchall()
    teaching_order = len(existing) + 1
    row_id = uuid.uuid4()
    conn.execute(
        session_table.insert().values(
            id=row_id,
            platform=platform,
            teaching_order=teaching_order,
            administrator=administrator,
            corpus_size=corpus_size,
            construct_count=construct_count,
            same_family_as=same_family_as,
            complete=False,
        )
    )
    return _session_row_to_dict(_get_session_row(conn, row_id))


def _get_session_row(conn: Connection, session_id: uuid.UUID) -> Any:
    row = conn.execute(select(session_table).where(session_table.c.id == session_id)).first()
    if row is None:
        raise SessionNotFound(str(session_id))
    return row


def record_confirmation(
    conn: Connection,
    *,
    session_id: uuid.UUID,
    question_rank: int,
    proposal_source: str,
    outcome: str,
    coverage_after: float | None = None,
) -> None:
    """TRD-08.4 §5.1 / V-08.4-010 — every confirmation carries its own
    timestamp, question rank, proposal source and outcome, recorded live
    (not reconstructed from `training_answer` after the session ends)."""

    conn.execute(
        confirmation_table.insert().values(
            id=uuid.uuid4(),
            session_id=session_id,
            question_rank=question_rank,
            proposal_source=proposal_source,
            outcome=outcome,
            coverage_after=coverage_after,
        )
    )


def complete_session(
    conn: Connection,
    session_id: uuid.UUID,
    *,
    wall_clock_minutes: float,
    coverage_target: float = COVERAGE_TARGET,
) -> dict[str, Any]:
    """Aggregates the session's recorded confirmations into the reported
    metrics (TRD-08.4 §5.1's table) and marks it complete. A session that
    never reaches `coverage_target` is recorded as **incomplete**
    (`complete=False`, §7 edge case / V-08.4-011) rather than silently
    included in the curve with a null `confirmations_to_70pct`."""

    _get_session_row(conn, session_id)  # raises SessionNotFound if missing
    confirmations = conn.execute(
        select(confirmation_table)
        .where(confirmation_table.c.session_id == session_id)
        .order_by(confirmation_table.c.at)
    ).fetchall()

    total = len(confirmations)
    if total == 0:
        raise ValueError("cannot complete a session with zero recorded confirmations")

    accepted_unchanged = sum(1 for c in confirmations if c.outcome == "confirm")
    edited = sum(1 for c in confirmations if c.outcome == "edit")
    not_relevant = sum(1 for c in confirmations if c.outcome == "not_relevant")
    polarity_proposals = sum(1 for c in confirmations if c.outcome in ("confirm", "polarity_inverted"))
    polarity_corrections = sum(1 for c in confirmations if c.outcome == "polarity_inverted")

    confirmations_to_70pct = None
    for i, c in enumerate(confirmations, start=1):
        if c.coverage_after is not None and c.coverage_after >= coverage_target:
            confirmations_to_70pct = i
            break
    complete = confirmations_to_70pct is not None

    questions_to_first_finding = None
    for i, c in enumerate(confirmations, start=1):
        if c.outcome in ("confirm", "polarity_inverted"):
            questions_to_first_finding = i
            break

    proposal_acceptance_rate = accepted_unchanged / total if total else None
    edit_rate = edited / total if total else None
    not_relevant_rate = not_relevant / total if total else None
    polarity_correction_rate = (polarity_corrections / polarity_proposals) if polarity_proposals else None

    conn.execute(
        session_table.update()
        .where(session_table.c.id == session_id)
        .values(
            completed_at=datetime.now(UTC),
            complete=complete,
            confirmations_to_70pct=confirmations_to_70pct,
            wall_clock_minutes=wall_clock_minutes,
            proposal_acceptance_rate=proposal_acceptance_rate,
            edit_rate=edit_rate,
            polarity_correction_rate=polarity_correction_rate,
            not_relevant_rate=not_relevant_rate,
            questions_to_first_finding=questions_to_first_finding,
        )
    )
    return _session_row_to_dict(_get_session_row(conn, session_id))


def _session_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "platform": row.platform,
        "order": row.teaching_order,
        "administrator": row.administrator,
        "corpus_size": row.corpus_size,
        "construct_count": row.construct_count,
        "complete": row.complete,
        "same_family_as": row.same_family_as,
        "confirmations_to_70pct": row.confirmations_to_70pct,
        "wall_clock_minutes": row.wall_clock_minutes,
        "proposal_acceptance_rate": row.proposal_acceptance_rate,
        "edit_rate": row.edit_rate,
        "polarity_correction_rate": row.polarity_correction_rate,
        "not_relevant_rate": row.not_relevant_rate,
        "questions_to_first_finding": row.questions_to_first_finding,
    }


def curve(conn: Connection) -> list[dict[str, Any]]:
    """TRD-08.4 §6's `curve()` interface — **teaching order**, complete
    sessions only (§7: incomplete sessions are excluded from the curve,
    counted separately). Confounds (construct count, corpus size,
    administrator, same-family relationship) are reported *alongside* each
    point, never adjusted away (DD-08.4-03)."""

    rows = conn.execute(
        select(session_table)
        .where(session_table.c.complete.is_(True))
        .order_by(session_table.c.teaching_order)
    ).fetchall()
    return [_session_row_to_dict(r) for r in rows]


def incomplete_sessions(conn: Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        select(session_table)
        .where(session_table.c.complete.is_(False))
        .order_by(session_table.c.teaching_order)
    ).fetchall()
    return [_session_row_to_dict(r) for r in rows]


def metrics(conn: Connection, platform: str | None = None) -> dict[str, Any]:
    """`api/training.py`'s `GET /training/metrics` — 15-api-specification.md
    §6's shape (`platforms[]` + `trend`)."""

    all_complete = curve(conn)
    platforms = [p for p in all_complete if platform is None or p["platform"] == platform]

    trend = "declining"
    values = [p["confirmations_to_70pct"] for p in all_complete if p["confirmations_to_70pct"] is not None]
    if len(values) >= 2:
        # DD-08.4-03 — honest, not adjusted: a simple monotonic check, not
        # a fitted trend line that could flatter the data.
        non_increasing = all(values[i] >= values[i + 1] for i in range(len(values) - 1))
        trend = "declining" if non_increasing and values[0] > values[-1] else "mixed"

    polarity_rates = [p["polarity_correction_rate"] for p in all_complete if p["polarity_correction_rate"] is not None]
    safety_signal = None
    if polarity_rates:
        latest = polarity_rates[-1]
        if latest > POLARITY_RATE_INVESTIGATE:
            safety_signal = "release_blocking"
        elif latest > POLARITY_RATE_HEALTHY:
            safety_signal = "investigate"
        else:
            safety_signal = "healthy"

    return {
        "platforms": [
            {
                "order": p["order"],
                "platform": p["platform"],
                "confirmations_to_70pct": p["confirmations_to_70pct"],
                "wall_clock_minutes": p["wall_clock_minutes"],
                "proposal_acceptance_rate": p["proposal_acceptance_rate"],
                "polarity_correction_rate": p["polarity_correction_rate"],
            }
            for p in platforms
        ],
        "trend": trend,
        "polarity_safety_signal": safety_signal,
    }
