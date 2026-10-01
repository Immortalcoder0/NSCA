"""ARTIFACT — 14-data-model.md §2.

Evidence, immutable from receipt (DM-1). Bytes never live in this table —
`storage_path` points into the content-addressed filesystem
(`db/artifact_store.py`, `artifacts/<sha256[:2]>/<sha256[2:4]>/<sha256>`,
per TECH-STACK.md §5). `content_hash` is the sha256 computed at receipt,
before any processing, matching FR-ING-012.

Fields beyond the doc's literal list — `status`, `grammar_coverage`,
`caveat`, `training` — are Track B's own additions to persist the outcome
of the four-state ingestion classification
(15-api-specification.md §3) so `GET /artifacts/{id}` can report it without
recomputing. `status` values: `uploaded` (received, not yet classified),
`parsed`, `parsed_with_caveat`, `platform_not_taught`, `unidentified`.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Table, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from nsca_platform.db.models.base import metadata, uuid_pk

artifact = Table(
    "artifact",
    metadata,
    uuid_pk(),
    Column("public_id", String, nullable=False, unique=True),
    Column("device_id", UUID(as_uuid=True), ForeignKey("device.id"), nullable=True),
    Column("campaign_id", UUID(as_uuid=True), ForeignKey("campaign.id"), nullable=False),
    Column("filename", String, nullable=False),
    Column("content_hash", String, nullable=False),
    Column("size_bytes", Integer, nullable=False),
    # running_config | show_version | show_inventory | cloud_policy |
    # tech_support_bundle | unknown
    Column("artifact_type", String, nullable=False, server_default="unknown"),
    # verbose | terse | unknown
    Column("export_mode", String, nullable=False, server_default="unknown"),
    Column("received_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    # upload | live_collection | bundle_extraction
    Column("received_from", String, nullable=False),
    Column("supplied_by", String, nullable=True),
    Column("collector", String, nullable=True),
    Column("source_address", String, nullable=True),
    Column("collection_method", String, nullable=True),
    Column("parent_artifact_id", UUID(as_uuid=True), ForeignKey("artifact.id"), nullable=True),
    Column("status", String, nullable=False, server_default="uploaded"),
    Column("platform", String, nullable=True),
    Column("os_version", String, nullable=True),
    Column("fingerprint_confidence", Numeric, nullable=True),
    Column("grammar_coverage", Numeric, nullable=True),
    Column("caveat", JSONB, nullable=True),
    Column("training", JSONB, nullable=True),
    Column("message", String, nullable=True),
    Column("storage_path", String, nullable=False),
)
