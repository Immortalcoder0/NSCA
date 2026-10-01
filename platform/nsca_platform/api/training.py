"""Training — 15-api-specification.md §6, backend-02 M3.

Real (non-stub) routes, wired to `services/training.py` and
`learning/ratification.py` / `learning/transfer_metrics.py`. Response
shapes match the spec's field names exactly (§2.4 / backend-02 §4.2); the
*data* is now real DB-backed content instead of the M0 stub's hardcoded
example payload, per the task brief's "only the data source changes."

`TrainingAnswer`'s polarity gate (V-08.3-002 / V-08.2-002) is enforced
inside `services.training.submit_answer` via
`learning.polarity.TrainingAnswer`, the real Pydantic model — this router
no longer carries its own stub copy of that validator.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.engine import Connection

from nsca_platform.auth.dev_auth import DevUser, get_current_user
from nsca_platform.db.engine import connect
from nsca_platform.learning import ratification, transfer_metrics
from nsca_platform.learning.polarity import TrainingAnswer as _PolarityTrainingAnswer
from nsca_platform.services import training as training_service

router = APIRouter(prefix="/training", tags=["training"])


def _conn() -> Connection:
    return connect()


class TrainingAnswerRequest(BaseModel):
    question_id: str
    response: Literal["confirm", "polarity_inverted", "edit", "not_relevant", "skip"]
    polarity_confirmed: bool | None = None
    edits: dict[str, Any] | None = None
    # Optional teaching-session context — when supplied, a confirm/
    # polarity_inverted answer triggers rule synthesis inline (the API
    # surface has no separate "synthesize" endpoint per the spec, so this
    # is the one write path that produces a provisional rule).
    taught_by: str | None = None
    source_artifact: str | None = None
    session_id: str | None = None


class StartSessionRequest(BaseModel):
    platform: str
    corpus_size: int = 0
    construct_count: int = 0
    same_family_as: str | None = None


class CompleteSessionRequest(BaseModel):
    wall_clock_minutes: float


@router.post("/sessions")
def start_training_session(body: StartSessionRequest, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    """TRD-08.4 §5.1's session lifecycle had a service-layer implementation
    (`transfer_metrics.start_session`/`complete_session`) with no route
    ever exposing it — the live UI had no way to obtain a `session_id` to
    pass to `POST /training/answer`, so every real confirmation was
    recorded session-less and `GET /training/metrics` stayed permanently
    empty even after a full teach-and-ratify pass. This and the sibling
    `/sessions/{id}/complete` route close that gap."""

    with _conn() as conn:
        result = transfer_metrics.start_session(
            conn,
            platform=body.platform,
            administrator=user.id,
            corpus_size=body.corpus_size,
            construct_count=body.construct_count,
            same_family_as=body.same_family_as,
        )
        conn.commit()
        return result


@router.post("/sessions/{session_id}/complete")
def complete_training_session(
    session_id: str, body: CompleteSessionRequest, user: DevUser = Depends(get_current_user)
) -> dict[str, Any]:
    with _conn() as conn:
        try:
            result = transfer_metrics.complete_session(
                conn, uuid.UUID(session_id), wall_clock_minutes=body.wall_clock_minutes,
            )
        except transfer_metrics.SessionNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        conn.commit()
        return result


@router.get("/queue")
def training_queue(user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with _conn() as conn:
        return {"platforms": training_service.platforms_with_pending_questions(conn)}


@router.get("/queue/{platform}")
def training_queue_platform(platform: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with _conn() as conn:
        return {"platform": platform, "questions": training_service.queue_for_platform(conn, platform)}


@router.get("/queue/{platform}/next")
def training_next_question(platform: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with _conn() as conn:
        q = training_service.next_question(conn, platform)
    if q is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no pending questions for this platform")
    return q


@router.post("/answer")
def submit_answer(body: TrainingAnswerRequest, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    session_uuid = uuid.UUID(body.session_id) if body.session_id else None
    with _conn() as conn:
        try:
            result = training_service.submit_answer(
                conn,
                question_id=body.question_id,
                response=body.response,
                polarity_confirmed=body.polarity_confirmed,
                edits=body.edits,
                actor=user.id,
                taught_by=body.taught_by,
                source_artifact=body.source_artifact,
                session_id=session_uuid,
            )
        except training_service.QuestionNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ratification.GatesNotPassed as exc:
            # Bug found during the Phase 3 demo rehearsal: a synthesized
            # extractor that fails one of the six TRD-08.3 validation gates
            # (e.g. corpus-scope) previously bubbled up as an unhandled 500.
            # A gate failure is an expected, recoverable outcome — this
            # specific construct isn't safely automatable yet, not a server
            # defect — so it belongs in the same 422 family as the polarity
            # gate below, not a crash. Note this still rolls back the whole
            # request (no `conn.commit()` is reached), same as the 500 did:
            # the question is not marked answered and must be retried. A
            # real fix would let already-gate-passed extractors from the
            # same answer commit independently of a sibling's failure —
            # that's a genuine, separate improvement, not attempted here.
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 — surface Pydantic's polarity-gate ValueError as 422
            if "polarity confirmation required" in str(exc):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
            raise
        conn.commit()
        return result


@router.get("/rules")
def list_training_rules(
    status_filter: str | None = Query(default=None, alias="status"),
    user: DevUser = Depends(get_current_user),
) -> dict[str, Any]:
    with _conn() as conn:
        return {"items": ratification.list_rules(conn, status=status_filter)}


@router.post("/rules/{rule_id}/ratify")
def ratify_rule(rule_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with _conn() as conn:
        try:
            result = ratification.ratify(conn, rule_id, user.id)
        except ratification.SelfRatificationError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except ratification.RuleNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        conn.commit()
        return result


@router.post("/rules/{rule_id}/reject")
def reject_rule(rule_id: str, user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with _conn() as conn:
        try:
            result = ratification.reject(conn, rule_id, user.id)
        except ratification.RuleNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        conn.commit()
        return result


@router.get("/metrics")
def training_metrics(user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with _conn() as conn:
        return transfer_metrics.metrics(conn)
