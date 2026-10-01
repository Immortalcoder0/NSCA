"""FINDING and FINDING_TRANSITION — 14-data-model.md §2/§3.

`state` uses the lifecycle names exactly as 09-findings-lifecycle.md §4's
table spells them (`New`, `Confirmed`, `Disputed`, `Withdrawn`,
`Risk Accepted`, `Assigned`, `Remediated`, `Verified`, `Closed`) — including
the space in "Risk Accepted" — rather than inventing a camel-case variant,
since the state machine in `services/finding_lifecycle.py` is meant to be a
direct reproduction of that table, not a re-interpretation of it.

`identity_key` is `f"{device_id}:{control_id}"` (14-data-model.md §2: "what
makes recurrence, regression and ageing computable across campaigns") — a
plain string column so a future cross-campaign query is a simple equality
filter, not a join through campaign history.

Evidence, framework refs and attack-path ids are stored as JSONB rather than
normalised child tables: `evidence[]`/`framework_refs[]` are always read and
written as a whole with their parent finding (never queried independently
across findings in this milestone's scope), so a JSONB column reproduces the
doc's array-of-object shape with far less mapping code, at the cost of not
being independently indexable — flagged as a judgment call, same reasoning
`campaign.scope_devices` used in M1.
"""

from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, ForeignKey, String, Table, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from nsca_platform.db.models.base import metadata, uuid_pk

finding = Table(
    "finding",
    metadata,
    uuid_pk(),
    Column("public_id", String, nullable=False, unique=True),
    Column("campaign_id", UUID(as_uuid=True), ForeignKey("campaign.id"), nullable=False),
    Column("device_id", UUID(as_uuid=True), ForeignKey("device.id"), nullable=False),
    Column("assessment_id", UUID(as_uuid=True), ForeignKey("assessment.id"), nullable=True),
    Column("control_id", String, nullable=False),
    # PASS | FAIL | UNKNOWN | NOT_APPLICABLE | PASS_PARTIAL
    Column("verdict", String, nullable=False),
    # meaningful | vacuous — set only when verdict == PASS
    Column("pass_quality", String, nullable=True),
    # facts_missing | default_unknown | parse_gap | export_incomplete | data_not_collected
    Column("unknown_reason", String, nullable=True),
    Column("severity_base", String, nullable=True),
    Column("severity_effective", String, nullable=True),
    Column("severity_reason", String, nullable=True),
    Column("evidence", JSONB, nullable=False, server_default="[]"),
    Column("framework_refs", JSONB, nullable=False, server_default="[]"),
    Column("attack_paths", JSONB, nullable=False, server_default="[]"),
    Column("contamination_reason", String, nullable=True),
    Column("rulepack_trust_tier", String, nullable=True),
    # New | Confirmed | Disputed | Withdrawn | Risk Accepted | Assigned |
    # Remediated | Verified | Closed — 09-findings-lifecycle.md §4
    Column("state", String, nullable=False, server_default="New"),
    Column("owner", String, nullable=True),
    Column("due_date", Date, nullable=True),
    Column("identity_key", String, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

# Append-only, per 14-data-model.md §3 FINDING_TRANSITION. Unlike
# `audit_log_entry` (M1), no DB-level RULE forbidding UPDATE/DELETE is added
# here — the append-only *invariant* that matters end-to-end is the
# hash-chained audit log itself (11-audit-integrity.md §7), which every
# finding-lifecycle transition also writes to in the same transaction
# (backend-02 §2.3); `finding_transition` is the human-readable per-finding
# view of a subset of that same history, not a second source of truth.
finding_transition = Table(
    "finding_transition",
    metadata,
    uuid_pk(),
    Column("finding_id", UUID(as_uuid=True), ForeignKey("finding.id"), nullable=False),
    Column("from_state", String, nullable=True),
    Column("to_state", String, nullable=False),
    Column("actor", String, nullable=False),
    Column("at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("reason", String, nullable=True),
)
