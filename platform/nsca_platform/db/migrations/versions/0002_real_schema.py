"""M1 real schema — campaign, device, artifact, assessment, fact, audit_log_entry

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-28

Replaces the M0 placeholder tables with the physical schema derived from
14-data-model.md (campaign, device, artifact, assessment, fact) plus the
append-only, hash-chained audit_log_entry table (DM-8, TECH-STACK.md §5).
`finding` is dropped here and deferred to M2 (finding lifecycle) — no code
in this milestone reads or writes it yet, and standing up a table whose
real shape (verdict, state machine, dispute/risk-acceptance refs) isn't
built yet would just mean re-migrating it again next milestone.

Per backend-02 §4.1, constraints are created in the same migration as the
tables they govern, not as follow-up hardening:
  - `audit_no_update` / `audit_no_delete` RULEs make audit_log_entry
    append-only at the storage layer (DM-8).
  - `fact.value` stays a nullable JSONB column with no CHECK forcing it
    non-null — the NULL-ness *is* the ⊥ representation (TECH-STACK.md §5).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- drop M0 placeholders --------------------------------------------
    op.drop_table("finding")
    op.drop_table("assessment")
    op.drop_table("artifact")
    op.drop_table("device")
    op.drop_table("campaign")
    # admin_user's M0 shape is unchanged by M1 — keep it as-is.

    # --- campaign ----------------------------------------------------------
    op.create_table(
        "campaign",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("public_id", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("scope_definition", postgresql.JSONB(), nullable=False),
        sa.Column("scope_devices", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("sampling_method", postgresql.JSONB(), nullable=True),
        sa.Column("frameworks", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("owner", sa.String(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(), nullable=False, server_default="Draft"),
        sa.Column("knowledge_base_pin", postgresql.JSONB(), nullable=True),
        sa.Column(
            "previous_campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- device --------------------------------------------------------------
    op.create_table(
        "device",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("hostname", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=True),
        sa.Column("os_version", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("serials", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_assessed", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("hostname", name="uq_device_hostname"),
    )

    # --- artifact ------------------------------------------------------------
    op.create_table(
        "artifact",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("public_id", sa.String(), nullable=False, unique=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("device.id"), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaign.id"), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("export_mode", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("received_from", sa.String(), nullable=False),
        sa.Column("supplied_by", sa.String(), nullable=True),
        sa.Column("collector", sa.String(), nullable=True),
        sa.Column("source_address", sa.String(), nullable=True),
        sa.Column("collection_method", sa.String(), nullable=True),
        sa.Column(
            "parent_artifact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("artifact.id"), nullable=True
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="uploaded"),
        sa.Column("platform", sa.String(), nullable=True),
        sa.Column("os_version", sa.String(), nullable=True),
        sa.Column("fingerprint_confidence", sa.Numeric(), nullable=True),
        sa.Column("grammar_coverage", sa.Numeric(), nullable=True),
        sa.Column("caveat", postgresql.JSONB(), nullable=True),
        sa.Column("training", postgresql.JSONB(), nullable=True),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("storage_path", sa.String(), nullable=False),
    )

    # --- assessment / fact -----------------------------------------------
    op.create_table(
        "assessment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("public_id", sa.String(), nullable=False, unique=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaign.id"), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("device.id"), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fingerprint_confidence", sa.Numeric(), nullable=True),
        sa.Column("grammar_coverage", sa.Numeric(), nullable=True),
        sa.Column("compliance_score", sa.Numeric(), nullable=True),
        sa.Column("coverage_score", sa.Numeric(), nullable=True),
        sa.Column("meaningful_ratio", sa.Numeric(), nullable=True),
        sa.Column("security_score", sa.Numeric(), nullable=True),
        sa.Column("counts", postgresql.JSONB(), nullable=True),
        sa.Column("rulepacks_used", postgresql.JSONB(), nullable=True),
        sa.Column("unmatched_constructs", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "fact",
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessment.id"), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=True),
        sa.Column("value_type", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("artifact.id"), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("excerpt", sa.String(), nullable=True),
        sa.Column("extractor", sa.String(), nullable=True),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.Column("layer", sa.String(), nullable=True),
        sa.Column("depends_on", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("assessment_id", "path"),
    )

    # --- audit_log_entry (append-only, hash-chained — DM-8) -----------------
    op.create_table(
        "audit_log_entry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("previous_entry_hash", sa.String(), nullable=True),
        sa.Column("entry_hash", sa.String(), nullable=False),
    )
    op.execute("CREATE RULE audit_no_update AS ON UPDATE TO audit_log_entry DO INSTEAD NOTHING")
    op.execute("CREATE RULE audit_no_delete AS ON DELETE TO audit_log_entry DO INSTEAD NOTHING")


def downgrade() -> None:
    op.execute("DROP RULE IF EXISTS audit_no_delete ON audit_log_entry")
    op.execute("DROP RULE IF EXISTS audit_no_update ON audit_log_entry")
    op.drop_table("audit_log_entry")
    op.drop_table("fact")
    op.drop_table("assessment")
    op.drop_table("artifact")
    op.drop_table("device")
    op.drop_table("campaign")

    # restore M0 placeholder shapes
    op.create_table(
        "campaign",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="Draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "device",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hostname", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "artifact",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="uploaded"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "assessment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "finding",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("control", sa.String(), nullable=False),
        sa.Column("verdict", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False, server_default="Open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
