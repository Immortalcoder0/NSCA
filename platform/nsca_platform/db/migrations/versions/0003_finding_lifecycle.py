"""M2 finding lifecycle — finding, finding_transition, dispute, risk_acceptance

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-29

Real physical schema for 09-findings-lifecycle.md §4 (state machine) and
§5-7 (dispute/adjudication, risk acceptance), per 14-data-model.md's FINDING,
FINDING_TRANSITION, DISPUTE and RISK_ACCEPTANCE entities. `finding` was
deliberately dropped and deferred by migration 0002 for exactly this
milestone — see that migration's docstring.

`risk_acceptance.expires_at` is NOT NULL at the DB layer as well as being a
required Pydantic field (`api/findings.py`'s `RiskAcceptanceRequest`) —
09-findings-lifecycle.md §7's "no indefinite acceptance" rule holds even if
a future code path ever constructs the row outside the validated API
request.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "finding",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("public_id", sa.String(), nullable=False, unique=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaign.id"), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("device.id"), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessment.id"), nullable=True),
        sa.Column("control_id", sa.String(), nullable=False),
        sa.Column("verdict", sa.String(), nullable=False),
        sa.Column("pass_quality", sa.String(), nullable=True),
        sa.Column("unknown_reason", sa.String(), nullable=True),
        sa.Column("severity_base", sa.String(), nullable=True),
        sa.Column("severity_effective", sa.String(), nullable=True),
        sa.Column("severity_reason", sa.String(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("framework_refs", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("attack_paths", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("contamination_reason", sa.String(), nullable=True),
        sa.Column("rulepack_trust_tier", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=False, server_default="New"),
        sa.Column("owner", sa.String(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("identity_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "finding_transition",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finding.id"), nullable=False),
        sa.Column("from_state", sa.String(), nullable=True),
        sa.Column("to_state", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
    )

    op.create_table(
        "dispute",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("public_id", sa.String(), nullable=False, unique=True),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finding.id"), nullable=False),
        sa.Column("raised_by", sa.String(), nullable=False),
        sa.Column("raised_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("claim", sa.String(), nullable=False),
        sa.Column("verification", postgresql.JSONB(), nullable=True),
        sa.Column("adjudicated_by", sa.String(), nullable=True),
        sa.Column("adjudicated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision", sa.String(), nullable=True),
        sa.Column("rationale", sa.String(), nullable=True),
    )

    op.create_table(
        "risk_acceptance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("public_id", sa.String(), nullable=False, unique=True),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finding.id"), nullable=False),
        sa.Column("accepted_by", sa.String(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("justification", sa.String(), nullable=False),
        sa.Column("compensating_control", postgresql.JSONB(), nullable=True),
        sa.Column("auto_reopened_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("risk_acceptance")
    op.drop_table("dispute")
    op.drop_table("finding_transition")
    op.drop_table("finding")
