"""ASSESSMENT and FACT — 14-data-model.md §2.

Table shape only in M1 — the worker pipeline that populates these
(§3 of backend-02, calling `nsca_engine.api.assess_device`) is M2 scope.
Created now so the migration that will be load-bearing for M2 doesn't have
to invent the fact table's `value jsonb NULL = unknown` shape under time
pressure; it is reproduced verbatim from TECH-STACK.md §5 here.
"""

from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Table,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from nsca_platform.db.models.base import metadata, uuid_pk

assessment = Table(
    "assessment",
    metadata,
    uuid_pk(),
    Column("public_id", String, nullable=False, unique=True),
    Column("campaign_id", UUID(as_uuid=True), ForeignKey("campaign.id"), nullable=False),
    Column("device_id", UUID(as_uuid=True), ForeignKey("device.id"), nullable=False),
    Column("executed_at", DateTime(timezone=True), nullable=False),
    Column("fingerprint_confidence", Numeric, nullable=True),
    Column("grammar_coverage", Numeric, nullable=True),
    Column("compliance_score", Numeric, nullable=True),
    Column("coverage_score", Numeric, nullable=True),
    Column("meaningful_ratio", Numeric, nullable=True),
    Column("security_score", Numeric, nullable=True),
    Column("counts", JSONB, nullable=True),
    Column("rulepacks_used", JSONB, nullable=True),
    Column("unmatched_constructs", JSONB, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

# TECH-STACK.md §5's exact shape: `value jsonb` (nullable), meaning ⊥
# (unknown) — structurally distinct from a JSON `false`. Never add a
# NOT NULL constraint to this column; that would collapse the ⊥
# representation the whole Security Baseline Model depends on.
fact = Table(
    "fact",
    metadata,
    Column("assessment_id", UUID(as_uuid=True), ForeignKey("assessment.id"), nullable=False),
    Column("path", String, nullable=False),
    Column("value", JSONB, nullable=True),  # NULL = unknown, never confusable with false
    Column("value_type", String, nullable=True),
    Column(
        "source",
        String,
        nullable=False,
    ),  # explicit|default_known|default_inferred|inherited|default_unknown|not_applicable|derived
    Column("artifact_id", UUID(as_uuid=True), ForeignKey("artifact.id"), nullable=True),
    Column("line_start", Integer, nullable=True),
    Column("line_end", Integer, nullable=True),
    Column("excerpt", String, nullable=True),
    Column("extractor", String, nullable=True),
    Column("confidence", Numeric, nullable=True),
    Column("layer", String, nullable=True),
    Column("depends_on", JSONB, nullable=True),
    PrimaryKeyConstraint("assessment_id", "path"),
)
