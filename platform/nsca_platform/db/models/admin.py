"""ADMIN_USER and AUDIT_LOG_ENTRY — 14-data-model.md §6.

`audit_log_entry` is append-only and hash-chained (DM-8, 11-audit-integrity.md
§7). The append-only property is enforced at the storage layer by RULEs
created in the migration (`audit_no_update`/`audit_no_delete`,
TECH-STACK.md §5) — not merely by service-layer discipline. `entry_hash` is
computed by `audit/log.py` over `(previous_entry_hash, at, actor, action,
entity_type, entity_id, details)`; `previous_entry_hash` is `NULL` only for
the very first entry in the chain.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from nsca_platform.db.models.base import metadata, uuid_pk

admin_user = Table(
    "admin_user",
    metadata,
    uuid_pk(),
    Column("name", String, nullable=False),
    Column("email", String, nullable=False, unique=True),
    Column("role", String, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

# ADMIN_CREDENTIAL — M5, backend-02 §4.8 / 15-api-specification.md §9,
# NFR-SEC-003 ("credential material is never returned by any endpoint under
# any role"). Enforced *by construction* here, not just by a response-shape
# convention: this table has no column capable of holding secret material
# at all — `reference` is an opaque, non-secret handle (e.g. a vault path
# or an external secret-manager key id) the operator supplies or the
# platform generates; the actual key/password bytes never reach this
# process's memory as anything but a local variable that is discarded
# immediately after being exchanged for (or replaced by) a reference. A
# `GET` against this table can therefore never leak a secret, because one
# was never stored — not because a serializer happens to omit a field.
admin_credential = Table(
    "admin_credential",
    metadata,
    uuid_pk(),
    Column("label", String, nullable=False),
    Column("type", String, nullable=False),  # ssh_keypair | api_token | ...
    Column("reference", String, nullable=False),  # opaque handle only — never the secret
    Column("created_by", String, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

audit_log_entry = Table(
    "audit_log_entry",
    metadata,
    uuid_pk(),
    Column("at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("actor", String, nullable=False),
    Column("action", String, nullable=False),
    Column("entity_type", String, nullable=False),
    Column("entity_id", String, nullable=False),
    Column("details", JSONB, nullable=True),
    Column("previous_entry_hash", String, nullable=True),
    Column("entry_hash", String, nullable=False),
)

# REPORT — 14-data-model.md, TRD-09.1 §3.8/§4, M4. `device_id` NULL means an
# estate report. `content_hash` and per-format artifact sha256 references
# (in `manifest`) let `POST /reports/{id}/verify` re-render and compare
# without recomputing anything the assessment already determined
# (INV-09.1-01). Amendments are new rows, never in-place updates
# (INV-09.1-06: "An issued report is never regenerated in place") —
# `supersedes_report_id` links an amendment back to the report it corrects.
report = Table(
    "report",
    metadata,
    uuid_pk(),
    Column("public_id", String, nullable=False, unique=True),
    Column("campaign_id", UUID(as_uuid=True), ForeignKey("campaign.id"), nullable=False),
    Column("device_id", UUID(as_uuid=True), ForeignKey("device.id"), nullable=True),
    Column("mode", String, nullable=False),  # draft | issued
    Column("state", String, nullable=False, server_default="draft"),  # draft | issued | superseded
    Column("generated_at", DateTime(timezone=True), nullable=False),
    Column("content_hash", String, nullable=True),
    Column("manifest", JSONB, nullable=True),
    Column("formats_available", JSONB, nullable=False, server_default="[]"),
    Column("artifact_refs", JSONB, nullable=False, server_default="{}"),  # {format: sha256}
    Column("supersedes_report_id", UUID(as_uuid=True), ForeignKey("report.id"), nullable=True),
    Column("amendment_reason", String, nullable=True),
    Column("amendment_effect", String, nullable=True),
    Column("issued_at", DateTime(timezone=True), nullable=True),
    Column("issued_by", String, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
