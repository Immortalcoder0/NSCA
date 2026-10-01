"""DEVICE — 14-data-model.md §2.

Device identity persists across campaigns; assessments do not. This table
is therefore NOT campaign-scoped — a device row is created once (at first
correlation) and reused by every later campaign that collects from it
again. `hostname` is unique per the correlation heuristic in
`services/ingestion.py` (FR-ING-010/011: correlate by hostname and/or
serial); a real fingerprint/serial-based correlation (once Track A ships
`nsca_engine.fingerprint`) may need a looser uniqueness rule (same serial,
different hostname after a rename) — flagged as a follow-up.

`exposure` is deliberately absent here: 14-data-model.md says it is
"Derived from graph, per campaign" — i.e. it is not a device property at
all, it's a campaign-scoped computation that belongs with the graph
entities (M3+), not a column on this table.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Table, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB

from nsca_platform.db.models.base import metadata, uuid_pk

device = Table(
    "device",
    metadata,
    uuid_pk(),
    Column("hostname", String, nullable=False),
    Column("platform", String, nullable=True),
    Column("os_version", String, nullable=True),
    Column("model", String, nullable=True),
    Column("serials", JSONB, nullable=False, server_default="[]"),
    Column("role", String, nullable=True),
    Column("location", String, nullable=True),
    Column("first_seen", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("last_assessed", DateTime(timezone=True), nullable=True),
    UniqueConstraint("hostname", name="uq_device_hostname"),
)
