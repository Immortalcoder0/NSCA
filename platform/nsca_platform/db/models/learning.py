"""Learning subsystem tables — 14-data-model.md (extended), backend-02 M3.

Six tables, one per stage of the pipeline that needs persistent state
(08-learning-system.md §2):

- ``unmatched_construct``   the raw queue an unrecognised platform's parse
                            produces (TRD-03.1's ``UnmatchedConstruct``,
                            persisted so template mining has something to
                            read across requests instead of recomputing from
                            artifacts on every call).
- ``training_question``    one mined-and-ordered question (TRD-08.1 output),
                            holding the grouped templates/candidate mappings
                            a `GET /training/queue/{platform}/next` reads.
- ``training_answer``      one administrator response (TRD-08.2 §6.4),
                            frozen at write time — this is also the raw
                            material `transfer_metrics.py` aggregates from.
- ``candidate_rule``        a synthesised extractor (TRD-08.3 §3), provisional
                            until ratified. ``two_person_rule`` CHECK
                            constraint enforces FR-LRN-015/ADM-004 at the DB
                            layer, not just in service code (backend-02 §4.1).
- ``transfer_metric_session``   one per-platform teaching session (TRD-08.4
                            §5.1) — the row the learning curve is built from.
- ``transfer_metric_confirmation``  one row per confirmation inside a
                            session, timestamped, so the curve is derivable
                            from records alone (V-08.4-010) rather than
                            reconstructed from `training_answer` after the
                            fact.

All content the *rule itself* needs to run (match pattern, emit expressions,
tests) is NOT duplicated here as relational columns — it lives in the
synthesised rulepack YAML under `knowledge/rulepacks/` (07-vendor-rulepacks.md
§2), because that YAML is what Track A's loader reads and the two must never
drift. `candidate_rule.extractor_doc` stores the same YAML fragment as JSONB
purely so the platform can render/list/ratify a rule without re-parsing the
file on every request; the file on disk remains the single source of truth
once ratified and exported (rule_synthesis.py writes both in the same call).
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from nsca_platform.db.models.base import metadata, uuid_pk

unmatched_construct = Table(
    "unmatched_construct",
    metadata,
    uuid_pk(),
    Column("platform", String, nullable=False),
    Column("artifact_id", String, nullable=False),
    Column("lines", JSONB, nullable=False),  # list[int] — UnmatchedConstruct.lines
    Column("excerpt", String, nullable=False),
    Column("parse_path", JSONB, nullable=False),  # list[str] — UnmatchedConstruct.parse_path
    Column("suppressed", Boolean, nullable=False, server_default="false"),
    Column("suppressed_reason", String, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

training_question = Table(
    "training_question",
    metadata,
    uuid_pk(),
    Column("platform", String, nullable=False),
    Column("public_id", String, nullable=False, unique=True),  # "Q-<platform>-NNN"
    Column("rank", Integer, nullable=False),
    Column("section", String, nullable=False),
    Column("skeleton", String, nullable=False),
    Column("templates", JSONB, nullable=False),  # list of {skeleton, slots, source_lines[], candidate_facts[]}
    Column("proposal", JSONB, nullable=False),  # Proposal shape, TRD-08.2 §7
    Column("gain", Integer, nullable=False),
    Column("controls_unlocked", JSONB, nullable=False),  # list[str]
    Column("facts_resolved", Integer, nullable=False),
    Column("status", String, nullable=False, server_default="pending"),  # pending|answered|skipped
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

training_answer = Table(
    "training_answer",
    metadata,
    uuid_pk(),
    Column("question_id", UUID(as_uuid=True), ForeignKey("training_question.id"), nullable=False),
    Column("session_id", UUID(as_uuid=True), ForeignKey("transfer_metric_session.id"), nullable=True),
    # confirm | polarity_inverted | edit | not_relevant | skip
    Column("response", String, nullable=False),
    Column("polarity_confirmed", Boolean, nullable=True),
    Column("edits", JSONB, nullable=True),
    Column("proposal_source", String, nullable=False),  # model | heuristic
    Column("answered_by", String, nullable=False),
    Column("answered_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

candidate_rule = Table(
    "candidate_rule",
    metadata,
    uuid_pk(),
    Column("public_id", String, nullable=False, unique=True),  # "RULE-<platform>-NNNN"
    Column("extractor_id", String, nullable=False),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("platform", String, nullable=False),
    Column("rulepack", String, nullable=False),
    # The synthesised extractor fragment (07-vendor-rulepacks.md §5 shape) —
    # mirrors what rule_synthesis.py writes into the rulepack YAML.
    Column("extractor_doc", JSONB, nullable=False),
    Column("validation_report", JSONB, nullable=True),
    # provisional | ratified | rejected | deprecated
    Column("status", String, nullable=False, server_default="provisional"),
    Column("taught_by", String, nullable=False),
    Column("taught_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("ratified_by", String, nullable=True),
    Column("ratified_at", DateTime(timezone=True), nullable=True),
    Column("source_artifact", String, nullable=True),
    Column("confirmed_examples", Integer, nullable=False, server_default="0"),
    Column("proposal_source", String, nullable=True),  # model | heuristic
    Column("polarity_confirmed", Boolean, nullable=True),
    Column("rejected_reason", String, nullable=True),
    CheckConstraint(
        "ratified_by IS NULL OR ratified_by <> taught_by", name="candidate_rule_two_person_rule"
    ),
)

transfer_metric_session = Table(
    "transfer_metric_session",
    metadata,
    uuid_pk(),
    Column("platform", String, nullable=False),
    Column("teaching_order", Integer, nullable=False),
    Column("administrator", String, nullable=False),
    Column("corpus_size", Integer, nullable=False, server_default="0"),
    Column("construct_count", Integer, nullable=False, server_default="0"),
    Column("started_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("complete", Boolean, nullable=False, server_default="false"),
    Column("confirmations_to_70pct", Integer, nullable=True),
    Column("wall_clock_minutes", Float, nullable=True),
    Column("proposal_acceptance_rate", Float, nullable=True),
    Column("edit_rate", Float, nullable=True),
    Column("polarity_correction_rate", Float, nullable=True),
    Column("not_relevant_rate", Float, nullable=True),
    Column("questions_to_first_finding", Integer, nullable=True),
    Column("same_family_as", String, nullable=True),
    UniqueConstraint("platform", "teaching_order", name="transfer_metric_session_platform_order_uq"),
)

transfer_metric_confirmation = Table(
    "transfer_metric_confirmation",
    metadata,
    uuid_pk(),
    Column("session_id", UUID(as_uuid=True), ForeignKey("transfer_metric_session.id"), nullable=False),
    Column("question_rank", Integer, nullable=False),
    Column("proposal_source", String, nullable=False),  # model | heuristic
    # confirm | polarity_inverted | edit | not_relevant | skip
    Column("outcome", String, nullable=False),
    Column("coverage_after", Float, nullable=True),
    Column("at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
