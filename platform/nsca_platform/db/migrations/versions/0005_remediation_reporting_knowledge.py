"""M4 — remediation_plan, report, framework_item

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-31

Real physical schema for backend-02 M4 (remediation planner, reporting,
knowledge import): `remediation_plan` (`db/models/lifecycle.py`), `report`
(`db/models/admin.py`), `framework_item` (`db/models/knowledge.py`).

`framework_item_dm9_text_redistributable` is DM-9 (14-data-model.md §7)
enforced as a DB CHECK constraint, not just an import-code convention —
same pattern as `candidate_rule_two_person_rule` (0004) and
`risk_acceptance.expires_at NOT NULL` (0003): the constraint is created in
the same migration that creates the table, not a follow-up hardening pass.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "remediation_plan",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("public_id", sa.String(), nullable=False, unique=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaign.id"), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("device.id"), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("os_version", sa.String(), nullable=True),
        sa.Column("operator_source", sa.String(), nullable=True),
        sa.Column("steps", postgresql.JSONB(), nullable=False),
        sa.Column("unavailable", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("checkpoints", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("conflicts", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("lockout", postgresql.JSONB(), nullable=True),
        sa.Column("dry_run", postgresql.JSONB(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("generated_by", sa.String(), nullable=False),
    )

    op.create_table(
        "report",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("public_id", sa.String(), nullable=False, unique=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaign.id"), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("device.id"), nullable=True),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False, server_default="draft"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("manifest", postgresql.JSONB(), nullable=True),
        sa.Column("formats_available", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("artifact_refs", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("supersedes_report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("report.id"), nullable=True),
        sa.Column("amendment_reason", sa.String(), nullable=True),
        sa.Column("amendment_effect", sa.String(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "framework_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("framework", sa.String(), nullable=False),
        sa.Column("benchmark", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("item_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column("stated_audit_procedure", sa.String(), nullable=True),
        sa.Column("satisfied_by", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("equivalence_rationale", sa.String(), nullable=True),
        sa.Column("automation_status", sa.String(), nullable=False, server_default="not_implemented"),
        sa.Column("text_redistributable", sa.Boolean(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("imported_by", sa.String(), nullable=True),
        sa.UniqueConstraint("framework", "benchmark", "version", "item_id", name="uq_framework_item"),
        sa.CheckConstraint(
            "text_redistributable = true OR "
            "(title IS NULL AND stated_audit_procedure IS NULL AND equivalence_rationale IS NULL)",
            name="framework_item_dm9_text_redistributable",
        ),
    )


def downgrade() -> None:
    op.drop_table("framework_item")
    op.drop_table("report")
    op.drop_table("remediation_plan")
