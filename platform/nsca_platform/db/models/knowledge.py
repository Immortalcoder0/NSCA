"""FRAMEWORK_ITEM — 14-data-model.md §4, backend-02 §4 module layout
("knowledge.py ... framework_item — metadata only; content stays in
knowledge/"), M4.

**DM-9, enforced at the DB layer, not just the import code**
(14-data-model.md §7: "Framework items with `text_redistributable = false`
store identifiers only — Import layer"). The CHECK constraint below is the
actual, un-bypassable enforcement: a row with `text_redistributable = false`
cannot carry `title`/`stated_audit_procedure`/`equivalence_rationale` text,
even if a future import code path (STIG, or a not-yet-built CIS/ISO one)
forgets to strip it. This is the same "constraint, not just a service-layer
check" pattern `candidate_rule_two_person_rule` (M3) and
`risk_acceptance.expires_at NOT NULL` (M2) already established.

Only `RULEPACK`/`EXTRACTOR`/`CONTROL`/`DEFAULT`/`FACT_DEFINITION` content
stays out of the DB per the module-layout comment ("metadata only; content
stays in knowledge/") — `FRAMEWORK_ITEM` itself is the one knowledge-base
entity this milestone persists as real rows, because framework import
(STIG/NIST) needs to be queryable/listable (`GET /knowledge/frameworks`,
coverage manifests) independent of re-parsing the source file every time.
"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, String, Table, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB

from nsca_platform.db.models.base import metadata, uuid_pk

framework_item = Table(
    "framework_item",
    metadata,
    uuid_pk(),
    Column("framework", String, nullable=False),  # cis | nist | stig | iso
    Column("benchmark", String, nullable=False),
    Column("version", String, nullable=False),
    Column("item_id", String, nullable=False),  # e.g. V-216644, AC-17
    Column("title", String, nullable=True),
    Column("severity", String, nullable=True),
    Column("stated_audit_procedure", String, nullable=True),
    Column("satisfied_by", JSONB, nullable=False, server_default="[]"),  # ref(Control)[]
    Column("equivalence_rationale", String, nullable=True),
    # automated | manual_only | data_unavailable | not_implemented
    Column("automation_status", String, nullable=False, server_default="not_implemented"),
    Column("text_redistributable", Boolean, nullable=False),
    Column("imported_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("imported_by", String, nullable=True),
    UniqueConstraint("framework", "benchmark", "version", "item_id", name="uq_framework_item"),
    CheckConstraint(
        "text_redistributable = true OR "
        "(title IS NULL AND stated_audit_procedure IS NULL AND equivalence_rationale IS NULL)",
        name="framework_item_dm9_text_redistributable",
    ),
)
