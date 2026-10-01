"""CAMPAIGN — 14-data-model.md §2.

Physical schema for the audit-engagement entity. Field list is reproduced
from the doc's table; `public_id` (e.g. `CMP-2026Q3-001`) is Track B's own
addition — the doc's `id` is "an identifier" without a format, and
15-api-specification.md's examples use a human-legible campaign code as the
externally visible id, so we store both: `id` (UUID, internal PK) and
`public_id` (the spec-shaped code, unique, used in URLs/responses).

`scope_devices` is stored as JSONB — the doc lists it as `ref[]`, but the
resolved device list is a snapshot produced by `scope/resolve`, not a
relational membership that needs its own join-table semantics (no
per-membership attributes beyond what's already in `device`). Flagged as a
judgment call: a `campaign_device` association table would also be a
reasonable reading of "ref[]" if a later milestone needs per-membership
metadata (e.g. why a device was sampled in).
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from nsca_platform.db.models.base import metadata, uuid_pk

campaign = Table(
    "campaign",
    metadata,
    uuid_pk(),
    Column("public_id", String, nullable=False, unique=True),
    Column("name", String, nullable=False),
    Column("scope_definition", JSONB, nullable=False),
    Column("scope_devices", JSONB, nullable=False, server_default="[]"),
    Column("sampling_method", JSONB, nullable=True),
    Column("frameworks", JSONB, nullable=False, server_default="[]"),
    Column("owner", String, nullable=False),
    Column("window_start", DateTime(timezone=True), nullable=True),
    Column("window_end", DateTime(timezone=True), nullable=True),
    # Draft, Collecting, Assessing, Review, Issued, Closed — FR-CMP-005
    Column("state", String, nullable=False, server_default="Draft"),
    Column("knowledge_base_pin", JSONB, nullable=True),
    Column("previous_campaign_id", UUID(as_uuid=True), ForeignKey("campaign.id"), nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
