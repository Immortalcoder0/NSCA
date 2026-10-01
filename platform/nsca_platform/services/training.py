"""Training service — orchestrates the learning pipeline
(08-learning-system.md §2) behind `api/training.py`'s real (non-stub)
routes, backend-02 M3.

```
seed_questions_for_platform   mine() -> persisted training_question rows
next_question / queue         reads training_question
submit_answer                 polarity gate -> training_answer -> (on
                               confirm/polarity_inverted) rule_synthesis
                               -> validation_gates -> ratification.save_provisional
```

`submit_answer` is where confirmation becomes a provisional rule — the API
surface only exposes one write endpoint (`POST /training/answer`,
15-api-specification.md §6), so that is where synthesis is triggered
inline, rather than inventing an undocumented second endpoint.
"""

from __future__ import annotations

import uuid
from typing import Any

from nsca_engine.api import UnmatchedConstruct
from sqlalchemy import select
from sqlalchemy.engine import Connection

from nsca_platform.db.models.learning import training_answer as answer_table
from nsca_platform.db.models.learning import training_question as question_table
from nsca_platform.knowledge_base_loader import knowledge_dir_from_env
from nsca_platform.knowledge_base_loader import clear_cache as clear_knowledge_base_cache
from nsca_platform.learning import ratification, rule_synthesis, transfer_metrics, validation_gates
from nsca_platform.services import knowledge_service
from nsca_platform.learning.candidate_proposal import Proposal, propose_heuristic
from nsca_platform.learning.polarity import TrainingAnswer as PolarityTrainingAnswer
from nsca_platform.learning.template_mining import (
    RequiredControlLike,
    Slot,
    Template,
    mine,
)


class QuestionNotFound(Exception):
    pass


# ---------------------------------------------------------------------------
# Template <-> JSON (training_question.templates) round-trip
# ---------------------------------------------------------------------------


def _template_to_json(t: Template) -> dict[str, Any]:
    return {
        "template_id": t.template_id,
        "enclosing_path": t.enclosing_path,
        "skeleton": t.skeleton,
        "verb": t.verb,
        "shape": list(t.shape),
        "literal_tokens": list(t.literal_tokens),
        "occurrence_count": t.occurrence_count,
        "source_lines": [[art, list(lines), excerpt] for art, lines, excerpt in t.source_lines],
        "slots": [
            {"position": s.position, "slot_type": s.slot_type, "observed_values": list(s.observed_values)}
            for s in t.slots
        ],
    }


def _json_to_template(doc: dict[str, Any]) -> Template:
    return Template(
        template_id=doc["template_id"],
        enclosing_path=doc["enclosing_path"],
        skeleton=doc["skeleton"],
        verb=doc.get("verb", ""),
        shape=tuple(doc.get("shape", ())),
        literal_tokens=tuple(doc["literal_tokens"]),
        occurrence_count=doc["occurrence_count"],
        source_lines=tuple((a, tuple(lines), e) for a, lines, e in doc["source_lines"]),
        slots=tuple(Slot(position=s["position"], slot_type=s["slot_type"], observed_values=tuple(s["observed_values"])) for s in doc["slots"]),
    )


def _proposal_to_json(p: Proposal) -> dict[str, Any]:
    return {
        "description": p.description,
        "mappings": [{"token": m.slot_value, "fact": m.fact_path, "justification": m.justification} for m in p.mappings],
        "polarity": p.polarity,
        "confidence": p.confidence,
        "signals": [{"kind": s.kind, "contribution": s.contribution, "detail": s.detail} for s in p.signals],
        "source": p.source,
    }


# ---------------------------------------------------------------------------
# Seeding — mine() a corpus and persist ordered questions
# ---------------------------------------------------------------------------


def seed_questions_for_platform(
    conn: Connection,
    *,
    platform: str,
    unmatched: list[UnmatchedConstruct],
    controls: list[RequiredControlLike],
    fact_candidates: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Runs the mine -> propose pipeline (Stages 2-4) and persists one
    `training_question` row per ordered question, each carrying its
    heuristic proposal (INV-08.2-03: always available)."""

    queue = mine(unmatched, controls)
    created = []
    for q in queue.questions:
        # The richest (most-occurrences) template in the group makes the
        # best representative proposal — a singleton template (e.g. the
        # one line with a different optional-tail shape) has no observed
        # slot variability to propose from.
        primary_template = max(q.templates, key=lambda t: t.occurrence_count)
        proposal = propose_heuristic(primary_template, fact_candidates)
        public_id = f"Q-{platform}-{q.rank:03d}"
        row_id = uuid.uuid4()
        conn.execute(
            question_table.insert().values(
                id=row_id,
                platform=platform,
                public_id=public_id,
                rank=q.rank,
                section=q.section,
                skeleton=primary_template.skeleton,
                templates=[_template_to_json(t) for t in q.templates],
                proposal=_proposal_to_json(proposal),
                gain=q.gain,
                controls_unlocked=list(q.controls_unlocked),
                facts_resolved=q.facts_resolved,
                status="pending",
            )
        )
        created.append({"id": public_id, "rank": q.rank, "section": q.section})
    return created


# ---------------------------------------------------------------------------
# Reading the queue
# ---------------------------------------------------------------------------


def _question_row_to_response(row: Any, *, total: int) -> dict[str, Any]:
    proposal = row.proposal or {}
    examples = [
        {"line": lines[0] if lines else None, "text": excerpt}
        for tpl in row.templates
        for (_art, lines, excerpt) in tpl.get("source_lines", [])
    ][:6]
    return {
        "question_id": row.public_id,
        "position": row.rank,
        "total": total,
        "section": row.section,
        "pattern": row.skeleton,
        "examples": examples,
        "proposal": proposal,
        "impact": {
            "facts_resolved": row.facts_resolved,
            "controls_unlocked": row.gain,
            "coverage_before": None,
            "coverage_after_estimate": None,
        },
    }


def queue_for_platform(conn: Connection, platform: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        select(question_table).where(question_table.c.platform == platform).order_by(question_table.c.rank)
    ).fetchall()
    total = len(rows)
    return [_question_row_to_response(r, total=total) for r in rows]


def next_question(conn: Connection, platform: str) -> dict[str, Any] | None:
    rows = conn.execute(
        select(question_table)
        .where(question_table.c.platform == platform, question_table.c.status == "pending")
        .order_by(question_table.c.rank)
        .limit(1)
    ).fetchall()
    if not rows:
        return None
    total = conn.execute(select(question_table).where(question_table.c.platform == platform)).fetchall()
    return _question_row_to_response(rows[0], total=len(total))


def platforms_with_pending_questions(conn: Connection) -> list[dict[str, Any]]:
    """`GET /training/queue`. `gap`/`coverage` used to be a hardcoded
    `"platform_not_taught"` / absent regardless of teaching progress — the
    Phase 3 rehearsal's `_write_and_activate` fix (`submit_answer` ->
    `rule_synthesis.write_extractors_to_rulepack` -> `clear_knowledge_base
    _cache`) means a platform can go from genuinely 0% to partially taught
    *within this same request's lifetime*, so this endpoint must reflect
    that from the real `KnowledgeBase`/control-pack cross-reference
    (`knowledge_service.rulepack_coverage`, the same real computation
    `GET /knowledge/rulepacks/{id}/coverage` already uses) rather than a
    static string — otherwise a demo can answer every question, ratify
    every rule, and this screen still claims "not taught" while the next
    `/assess` run already reflects the new facts."""

    rows = conn.execute(select(question_table)).fetchall()
    by_platform: dict[str, list[Any]] = {}
    for r in rows:
        by_platform.setdefault(r.platform, []).append(r)
    out = []
    for platform, prows in sorted(by_platform.items()):
        pending = [r for r in prows if r.status == "pending"]
        try:
            coverage = knowledge_service.rulepack_coverage(platform)["coverage_rate"]
        except knowledge_service.RulepackNotFound:
            coverage = 0.0
        out.append(
            {
                "platform": platform,
                "gap": "platform_not_taught" if coverage <= 0.0 else "platform_partially_taught",
                "questions_prepared": len(prows),
                "questions_remaining": len(pending),
                "coverage": coverage,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Answering — polarity gate, then (on confirm) rule synthesis
# ---------------------------------------------------------------------------


def submit_answer(
    conn: Connection,
    *,
    question_id: str,
    response: str,
    polarity_confirmed: bool | None,
    edits: dict[str, Any] | None,
    actor: str,
    taught_by: str | None = None,
    source_artifact: str | None = None,
    session_id: uuid.UUID | None = None,
    question_rank_for_metrics: int | None = None,
) -> dict[str, Any]:
    row = conn.execute(select(question_table).where(question_table.c.public_id == question_id)).first()
    if row is None:
        raise QuestionNotFound(question_id)

    proposal = row.proposal or {}
    requires_polarity = bool(proposal.get("polarity", {}).get("requires_explicit_confirmation"))

    # V-08.3-002 / V-08.2-002 — the actual enforcement point, at the API
    # boundary, via the same Pydantic model TECH-STACK.md §4 shows.
    validated = PolarityTrainingAnswer(
        question_id=question_id,
        response=response,  # type: ignore[arg-type]
        requires_polarity=requires_polarity,
        polarity_confirmed=polarity_confirmed,
        edits=edits,
    )

    conn.execute(
        answer_table.insert().values(
            id=uuid.uuid4(),
            question_id=row.id,
            session_id=session_id,
            response=validated.response,
            polarity_confirmed=validated.polarity_confirmed,
            edits=edits,
            proposal_source=proposal.get("source", "heuristic"),
            answered_by=actor,
        )
    )
    conn.execute(
        question_table.update().where(question_table.c.id == row.id).values(status="answered")
    )

    result: dict[str, Any] = {"question_id": question_id, "response": validated.response, "accepted": True}

    if validated.response in ("confirm", "polarity_inverted") and taught_by and source_artifact:
        # Synthesis (and, on gate-pass, `_write_and_activate`'s disk write +
        # KnowledgeBase cache clear) must happen *before* `coverage_after`
        # is measured below — otherwise the recorded point is the coverage
        # from before this confirmation took effect, and
        # `confirmations_to_70pct` could never reflect the confirmation
        # that actually crossed the threshold.
        rule_result = _synthesize_from_answer(conn, row, proposal, validated, taught_by, source_artifact)
        result["rule"] = rule_result

    if session_id is not None:
        try:
            coverage_after = knowledge_service.rulepack_coverage(row.platform)["coverage_rate"]
        except knowledge_service.RulepackNotFound:
            coverage_after = None
        transfer_metrics.record_confirmation(
            conn, session_id=session_id, question_rank=question_rank_for_metrics or row.rank,
            proposal_source=proposal.get("source", "heuristic"), outcome=validated.response,
            coverage_after=coverage_after,
        )

    return result


def _synthesize_from_answer(
    conn: Connection, row: Any, proposal: dict[str, Any], answer: PolarityTrainingAnswer,
    taught_by: str, source_artifact: str,
) -> dict[str, Any] | None:
    # Bug (found while fixing a live-teaching regression, not in the
    # original Phase 3 rehearsal list): this used to be
    # `_json_to_template(row.templates[0])` — the first template in
    # whatever order `mine()` produced `q.templates`, which is NOT
    # necessarily the same template `seed_questions_for_platform`
    # actually built the proposal from (`primary_template =
    # max(q.templates, key=occurrence_count)`, line ~118). When a
    # question groups multiple skeleton-sharing templates (e.g. one
    # /ip service question covering telnet/ssh/ftp/www all at once),
    # `templates[0]` can be a different template than `primary_template`,
    # so `mapping.slot_value` (built from the *proposal's* template) was
    # checked against the *wrong* template's `observed_values` here —
    # the containment check silently failed, and `_regex_for_mapping`
    # fell back to matching every value in that slot's domain instead of
    # anchoring the one specific value being taught. Reselecting the same
    # max-occurrence_count template used for the proposal is the fix —
    # this function must always agree with `seed_questions_for_platform`
    # on which template is "the" template for this question.
    template = max((_json_to_template(t) for t in row.templates), key=lambda t: t.occurrence_count)
    mappings = tuple(
        rule_synthesis.ConfirmedMapping(
            slot_value=m["token"], fact_path=m["fact"], polarity_confirmed=bool(answer.polarity_confirmed or not proposal.get("polarity", {}).get("requires_explicit_confirmation"))
        )
        for m in proposal.get("mappings", [])
    )
    if not mappings:
        return None

    negation_key = proposal.get("polarity", {}).get("indicator")
    confirmation = rule_synthesis.Confirmation(
        template=template, mappings=mappings, taught_by=taught_by,
        source_artifact=source_artifact, negation_key=negation_key,
    )
    try:
        extractors = rule_synthesis.synthesize(confirmation)
    except rule_synthesis.SynthesisError as exc:
        return {"status": "synthesis_failed", "reason": str(exc)}

    all_examples = [excerpt for (_a, _l, excerpt) in template.source_lines]

    saved = []
    disk_ready: list[dict[str, Any]] = []
    # `rule_synthesis.synthesize` emits exactly one extractor per mapping,
    # in the same order (see its own `for m in confirmation.mappings:`
    # loop) — zip is safe and is how each extractor's gate check knows
    # which mapping (and therefore which slot value) it belongs to.
    for mapping, ex in zip(mappings, extractors):
        # Second bug found alongside the template-selection one above:
        # once a pattern is correctly anchored to one specific slot value
        # (e.g. "ftp" only), it legitimately does NOT match every line in
        # the template's full `source_lines` (which spans every observed
        # value — ftp/ssh/telnet/www/... lines all together). Gating
        # self-match against *all* template lines regardless of which
        # mapping is being checked was previously masked by the anchoring
        # bug (a loose `\S+` pattern matched everything, so self-match
        # trivially passed) — fixing the anchoring bug exposed this one.
        # Filter confirmed_examples down to the lines that actually
        # contain this mapping's own slot value as a token, matching the
        # same criterion `_regex_for_mapping` used to decide whether to
        # anchor it in the first place.
        own_examples = [ex_line for ex_line in all_examples if mapping.slot_value in ex_line.split()]
        gate_report = validation_gates.run_all_gates(
            pattern=ex["match"],
            value_expr=ex["emit"][0]["value"],
            fact_path=ex["emit"][0]["fact"],
            fact_type="boolean",
            confirmed_examples=own_examples or all_examples,
            target_platform=row.platform,
            corpus={row.platform: all_examples},
            existing_producers={},
            new_value_for={},
            registered_fact_paths=frozenset({ex["emit"][0]["fact"]}),
            frozen_tests=[],
        )
        saved_row = ratification.save_provisional(
            conn,
            extractor_id=ex["extractor_id"], version=ex["version"], platform=row.platform,
            rulepack=row.platform, extractor_doc=ex, validation_report=gate_report.as_dict(),
            taught_by=taught_by, source_artifact=source_artifact,
            confirmed_examples=ex["provenance"]["confirmed_examples"],
            proposal_source=proposal.get("source", "heuristic"),
            polarity_confirmed=ex["provenance"]["polarity_confirmed"],
            gates_passed=gate_report.all_passed,
        )
        saved.append(saved_row)
        if gate_report.all_passed:
            disk_ready.append(ex)

    if disk_ready:
        _write_and_activate(row.platform, disk_ready)

    return {"status": "provisional_rules_saved", "rules": saved}


def _write_and_activate(platform: str, extractors: list[dict[str, Any]]) -> None:
    """The step this pipeline was missing entirely before this fix: gate-
    passed extractors were persisted as `candidate_rule` DB rows (governance
    record: who taught it, is it ratified) but never actually written to
    `knowledge/rulepacks/{platform}.yaml` — the file `nsca_engine.api.
    load_knowledge_base` reads. The real engine loader does not gate on a
    rule's `status` field at all (confirmed by reading
    `nsca_engine/controls/rulepack_loader.py` — it has no `status` handling);
    "provisional" is purely this platform's own reporting-layer concept
    (`ratification.is_report_eligible`), not something the engine consults.
    So the moment a gate-passed extractor is on disk, it is live for
    fingerprinting/extraction/assessment — matching the product's own
    "Confirming resolves 8 controls" impact language, which promises an
    immediate effect, not one gated behind a later two-person ratification.

    Writes, then drops the process-lifetime `KnowledgeBase` cache
    (`knowledge_base_loader`'s own docstring previously assumed a new
    rulepack "takes effect on the next process start/restart" — that
    assumption is what broke the live teach-then-reassess demo loop; this
    is the fix) so the *next* request rebuilds it from the now-current
    files instead of serving a stale in-memory copy.

    Known simplification, flagged rather than silently papered over: for a
    platform with an existing rulepack file (every platform this pipeline
    has actually been exercised against so far — routeros, cisco_ios, etc.
    all shipped with one from M1/M2), `vendor`/`grammar` below are ignored
    (`rule_synthesis.load_or_init_rulepack_doc` only uses them to
    initialise a *new* file). For a genuinely first-ever-taught platform
    with no prior file at all, these fall back to a guessed vendor prefix
    and the indentation paradigm — real paradigm detection
    (`learning/grammar_inference.py`, built in M3) is not wired into this
    live answer-submission path yet; that remains a separate, real gap.
    """

    knowledge_dir = knowledge_dir_from_env()
    path = rule_synthesis.default_rulepack_path(platform, knowledge_dir)
    vendor = platform.split("_")[0]
    grammar = {"paradigm": "indentation", "comment_char": "!"}
    rule_synthesis.write_extractors_to_rulepack(path, platform, vendor, grammar, extractors)
    clear_knowledge_base_cache()
