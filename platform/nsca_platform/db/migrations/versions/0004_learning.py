"""M3 learning subsystem — unmatched_construct, training_question,
training_answer, candidate_rule, transfer_metric_session,
transfer_metric_confirmation.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-29

`candidate_rule.ratified_by <> taught_by` is a DB CHECK constraint
(`candidate_rule_two_person_rule`), not just a service-layer check — per
TECH-STACK.md §5 and backend-02 §4.1's `two_person_rule` example, exactly the
same pattern `risk_acceptance.expires_at NOT NULL` used in migration 0003.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "unmatched_construct",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("artifact_id", sa.String(), nullable=False),
        sa.Column("lines", postgresql.JSONB(), nullable=False),
        sa.Column("excerpt", sa.String(), nullable=False),
        sa.Column("parse_path", postgresql.JSONB(), nullable=False),
        sa.Column("suppressed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("suppressed_reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "transfer_metric_session",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("teaching_order", sa.Integer(), nullable=False),
        sa.Column("administrator", sa.String(), nullable=False),
        sa.Column("corpus_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("construct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("complete", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("confirmations_to_70pct", sa.Integer(), nullable=True),
        sa.Column("wall_clock_minutes", sa.Float(), nullable=True),
        sa.Column("proposal_acceptance_rate", sa.Float(), nullable=True),
        sa.Column("edit_rate", sa.Float(), nullable=True),
        sa.Column("polarity_correction_rate", sa.Float(), nullable=True),
        sa.Column("not_relevant_rate", sa.Float(), nullable=True),
        sa.Column("questions_to_first_finding", sa.Integer(), nullable=True),
        sa.Column("same_family_as", sa.String(), nullable=True),
        sa.UniqueConstraint("platform", "teaching_order", name="transfer_metric_session_platform_order_uq"),
    )

    op.create_table(
        "transfer_metric_confirmation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("transfer_metric_session.id"), nullable=False
        ),
        sa.Column("question_rank", sa.Integer(), nullable=False),
        sa.Column("proposal_source", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("coverage_after", sa.Float(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "training_question",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("public_id", sa.String(), nullable=False, unique=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(), nullable=False),
        sa.Column("skeleton", sa.String(), nullable=False),
        sa.Column("templates", postgresql.JSONB(), nullable=False),
        sa.Column("proposal", postgresql.JSONB(), nullable=False),
        sa.Column("gain", sa.Integer(), nullable=False),
        sa.Column("controls_unlocked", postgresql.JSONB(), nullable=False),
        sa.Column("facts_resolved", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "training_answer",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_question.id"), nullable=False),
        sa.Column(
            "session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("transfer_metric_session.id"), nullable=True
        ),
        sa.Column("response", sa.String(), nullable=False),
        sa.Column("polarity_confirmed", sa.Boolean(), nullable=True),
        sa.Column("edits", postgresql.JSONB(), nullable=True),
        sa.Column("proposal_source", sa.String(), nullable=False),
        sa.Column("answered_by", sa.String(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "candidate_rule",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("public_id", sa.String(), nullable=False, unique=True),
        sa.Column("extractor_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("rulepack", sa.String(), nullable=False),
        sa.Column("extractor_doc", postgresql.JSONB(), nullable=False),
        sa.Column("validation_report", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="provisional"),
        sa.Column("taught_by", sa.String(), nullable=False),
        sa.Column("taught_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ratified_by", sa.String(), nullable=True),
        sa.Column("ratified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_artifact", sa.String(), nullable=True),
        sa.Column("confirmed_examples", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("proposal_source", sa.String(), nullable=True),
        sa.Column("polarity_confirmed", sa.Boolean(), nullable=True),
        sa.Column("rejected_reason", sa.String(), nullable=True),
        sa.CheckConstraint("ratified_by IS NULL OR ratified_by <> taught_by", name="candidate_rule_two_person_rule"),
    )


def downgrade() -> None:
    op.drop_table("candidate_rule")
    op.drop_table("training_answer")
    op.drop_table("training_question")
    op.drop_table("transfer_metric_confirmation")
    op.drop_table("transfer_metric_session")
    op.drop_table("unmatched_construct")
