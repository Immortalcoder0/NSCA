"""End-to-end learning pipeline — backend-02 M3's full milestone flow in
one test: mine -> propose -> confirm (via the real `POST /training/answer`
service call) -> synthesize -> validate -> save provisional -> ratify ->
report-eligibility -> transfer metrics.

This is the closest thing in this milestone to TRD-08.3 §11's V-08.3-011
("teach a held-out platform... mine, propose, confirm, synthesise,
validate, ratify, re-assess") without a real assessment worker to
re-assess with (that's `services/assessment.py`, M2 territory) — every
step up to "findings carry correct evidence" is exercised against the
MikroTik acceptance fixture.
"""

from __future__ import annotations

import uuid

from nsca_platform.db.engine import connect
from nsca_platform.learning import ratification, transfer_metrics
from nsca_platform.learning.template_mining import RequiredControlLike
from nsca_platform.services import training as training_service
from nsca_platform.tests.conftest import requires_db
from nsca_platform.tests.fixtures.mikrotik import build_required_controls, build_unmatched_constructs


def _controls_and_facts():
    controls_fixture = build_required_controls()
    controls = [RequiredControlLike(c.control_id, c.requires_facts) for c in controls_fixture]
    fact_candidates = [(f, "boolean") for c in controls_fixture for f in c.requires_facts]
    return controls, fact_candidates


@requires_db
def test_full_mikrotik_teaching_session_end_to_end(db_conn, tmp_path, monkeypatch):
    # Bug found and fixed alongside the rule-synthesis regex bug: this
    # test's `submit_answer` call below triggers real rule synthesis
    # (`services/training.py::_write_and_activate`, wired to disk earlier
    # this session) — without isolating `NSCA_KNOWLEDGE_DIR`, every run of
    # this test permanently wrote a new `mikrotik_e2e_<random>.yaml` file
    # into the real, shipped `nsca/knowledge/rulepacks/` directory (dozens
    # accumulated over one session). Point writes at a scratch directory
    # instead — this test only needs the write to happen, not to land in
    # production content.
    monkeypatch.setenv("NSCA_KNOWLEDGE_DIR", str(tmp_path))
    platform = f"mikrotik_e2e_{uuid.uuid4().hex[:6]}"
    unmatched = build_unmatched_constructs()
    controls, fact_candidates = _controls_and_facts()

    # Stage 1-3: mine + order into 9 questions (grammar inference is
    # exercised separately in test_grammar_inference.py against the same
    # corpus text).
    created = training_service.seed_questions_for_platform(
        db_conn, platform=platform, unmatched=unmatched, controls=controls, fact_candidates=fact_candidates,
    )
    assert len(created) == 9

    session = transfer_metrics.start_session(
        db_conn, platform=platform, administrator="r.kulkarni", corpus_size=125, construct_count=48,
    )
    session_id = uuid.UUID(session["id"])

    # Stage 4-5: answer Q1 (/ip service — the negation-bearing template)
    # with an explicit polarity confirmation.
    q1 = training_service.next_question(db_conn, platform)
    assert q1["section"] == "/ip service"
    assert q1["proposal"]["polarity"]["requires_explicit_confirmation"] is True

    answer_result = training_service.submit_answer(
        db_conn,
        question_id=q1["question_id"], response="confirm", polarity_confirmed=True, edits=None,
        actor="r.kulkarni", taught_by="r.kulkarni", source_artifact="RTR-Pune-02.rsc",
        session_id=session_id, question_rank_for_metrics=1,
    )
    assert answer_result["accepted"] is True

    # Stage 6-7: synthesis + validation gates ran inline inside
    # submit_answer (via services.training._synthesize_from_answer) and
    # produced at least one provisional rule.
    assert "rule" in answer_result
    assert answer_result["rule"]["status"] == "provisional_rules_saved"
    saved_rule = answer_result["rule"]["rules"][0]
    assert saved_rule["status"] == "provisional"
    assert saved_rule["taught_by"] == "r.kulkarni"

    # Provisional rules are usable for exploration but not report-eligible.
    assert ratification.is_report_eligible(saved_rule["status"], "provisional") is False

    # Stage 8: ratification by a DIFFERENT user (two-person rule).
    ratified = ratification.ratify(db_conn, saved_rule["id"], "v.singh")
    assert ratified["status"] == "ratified"
    assert ratified["ratified_by"] == "v.singh"
    assert ratification.is_report_eligible(ratified["status"], "local") is True

    # Answer the remaining 8 questions (mix of confirm/not_relevant) to
    # complete the session, driving coverage_after up so the session
    # crosses 70% and gets recorded as complete.
    remaining = training_service.queue_for_platform(db_conn, platform)[1:]
    n = len(remaining)
    for i, q in enumerate(remaining, start=2):
        coverage_after = i / (n + 1)  # monotonically increasing synthetic coverage
        response = "confirm" if q["proposal"]["polarity"].get("indicator") is None else "not_relevant"
        training_service.submit_answer(
            db_conn, question_id=q["question_id"], response=response,
            polarity_confirmed=True if q["proposal"]["polarity"]["requires_explicit_confirmation"] else None,
            edits=None, actor="r.kulkarni", session_id=session_id, question_rank_for_metrics=i,
        )
        transfer_metrics.record_confirmation(
            db_conn, session_id=session_id, question_rank=i, proposal_source="heuristic",
            outcome="confirm", coverage_after=coverage_after,
        )

    completed = transfer_metrics.complete_session(db_conn, session_id, wall_clock_minutes=8.2)
    assert completed["complete"] is True
    assert completed["confirmations_to_70pct"] is not None

    curve = transfer_metrics.curve(db_conn)
    assert any(p["platform"] == platform for p in curve)


@requires_db
def test_teaching_produces_a_rulepack_track_a_can_load(db_conn, tmp_path, monkeypatch):
    """Ties the pipeline test to the milestone's other headline
    requirement: the provisional rule this session produces is real
    extractor content that (once written to a rulepack file, as
    rule_synthesis.py does in production) Track A's real loader accepts —
    see test_rule_synthesis.py for the dedicated version of this check;
    here we just confirm the DB-persisted `extractor_doc` round-trips into
    the same shape."""

    from nsca_engine.controls.rulepack_loader import load_rulepack

    # Same isolation fix as the test above — `submit_answer` below also
    # triggers a real disk write via `_write_and_activate`, independent of
    # this test's own explicit `write_extractors_to_rulepack` call further
    # down (which already correctly used `tmp_path`).
    monkeypatch.setenv("NSCA_KNOWLEDGE_DIR", str(tmp_path))
    platform = f"mikrotik_e2e_loader_{uuid.uuid4().hex[:6]}"
    unmatched = build_unmatched_constructs()
    controls, fact_candidates = _controls_and_facts()
    training_service.seed_questions_for_platform(
        db_conn, platform=platform, unmatched=unmatched, controls=controls, fact_candidates=fact_candidates,
    )
    q1 = training_service.next_question(db_conn, platform)
    answer_result = training_service.submit_answer(
        db_conn, question_id=q1["question_id"], response="confirm", polarity_confirmed=True, edits=None,
        actor="r.kulkarni", taught_by="r.kulkarni", source_artifact="RTR-Pune-02.rsc",
    )
    saved_rule = answer_result["rule"]["rules"][0]
    row = ratification.get_rule(db_conn, saved_rule["id"])
    assert row["extractor_id"]

    from nsca_platform.learning.rule_synthesis import write_extractors_to_rulepack
    from sqlalchemy import select
    from nsca_platform.db.models.learning import candidate_rule as candidate_rule_table

    doc_row = db_conn.execute(
        select(candidate_rule_table).where(candidate_rule_table.c.public_id == saved_rule["id"])
    ).first()
    rulepack_path = tmp_path / f"{platform}.yaml"
    write_extractors_to_rulepack(
        rulepack_path, platform=platform, vendor="mikrotik",
        grammar={"paradigm": "path_header", "comment_char": "#"},
        new_extractors=[doc_row.extractor_doc],
    )
    loaded = load_rulepack(rulepack_path)
    assert loaded.platform == platform
    assert len(loaded.extractors) == 1
