"""DISPUTE, RISK_ACCEPTANCE and REMEDIATION_PLAN — 14-data-model.md §3.

`remediation_plan` is added in M4, now that `remediation/planner.py`'s
output has a real shape to persist (backend-02 §4.4) — storing the
generated plan (steps, lockout analysis, dry-run result) is what lets the
report generator render Section 5 without recomputing anything at render
time (RPT-2 / INV-09.1-01: "No verdict, score, severity or finding is
computed during rendering").

`verification` (the *re-collect -> re-assess -> compare* workflow,
09-findings-lifecycle.md §8, `services/verification.py`) is out of this
milestone's scope per the task brief and is still not created here.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from nsca_platform.db.models.base import metadata, uuid_pk

dispute = Table(
    "dispute",
    metadata,
    uuid_pk(),
    Column("public_id", String, nullable=False, unique=True),
    Column("finding_id", UUID(as_uuid=True), ForeignKey("finding.id"), nullable=False),
    Column("raised_by", String, nullable=False),
    Column("raised_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    # false_positive | compensating_control | not_applicable | accepted_risk | already_remediated
    Column("type", String, nullable=False),
    Column("claim", String, nullable=False),
    # {result, counterexample, assumptions, confidence, devices_considered, devices_missing}
    Column("verification", JSONB, nullable=True),
    Column("adjudicated_by", String, nullable=True),
    Column("adjudicated_at", DateTime(timezone=True), nullable=True),
    # upheld | rejected | converted_to_risk_acceptance
    Column("decision", String, nullable=True),
    Column("rationale", String, nullable=True),
)

risk_acceptance = Table(
    "risk_acceptance",
    metadata,
    uuid_pk(),
    Column("public_id", String, nullable=False, unique=True),
    Column("finding_id", UUID(as_uuid=True), ForeignKey("finding.id"), nullable=False),
    # Must be a Lead Assessor — enforced in services/risk_acceptance.py at
    # the point of acceptance (auth/dev_auth.require_role), not just here.
    Column("accepted_by", String, nullable=False),
    Column("accepted_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    # MANDATORY — 09-findings-lifecycle.md §7: "no indefinite acceptance".
    # Enforced twice: as a required Pydantic field on the request schema
    # (api/findings.py `RiskAcceptanceRequest.expires_at`, TECH-STACK.md §4)
    # and as NOT NULL here, so a row can never exist without one even if a
    # future code path constructs it outside the validated API request.
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("justification", String, nullable=False),
    Column("compensating_control", JSONB, nullable=True),
    Column("auto_reopened_at", DateTime(timezone=True), nullable=True),
)

remediation_plan = Table(
    "remediation_plan",
    metadata,
    uuid_pk(),
    Column("public_id", String, nullable=False, unique=True),
    Column("campaign_id", UUID(as_uuid=True), ForeignKey("campaign.id"), nullable=False),
    Column("device_id", UUID(as_uuid=True), ForeignKey("device.id"), nullable=False),
    Column("platform", String, nullable=False),
    Column("os_version", String, nullable=True),
    Column("operator_source", String, nullable=True),
    # Each of these is the JSON-serialised form of the matching
    # `remediation.planner`/`lockout`/`dry_run` dataclass tuple — see
    # `services/remediation_service.py`'s (de)serialisers, the one place
    # this shape is defined, so the DB row and the in-memory dataclasses
    # never drift apart from two independent hand-written mappings.
    Column("steps", JSONB, nullable=False),
    Column("unavailable", JSONB, nullable=False, server_default="[]"),
    Column("checkpoints", JSONB, nullable=False, server_default="[]"),
    Column("conflicts", JSONB, nullable=False, server_default="[]"),
    Column("lockout", JSONB, nullable=True),
    Column("dry_run", JSONB, nullable=True),
    Column("generated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("generated_by", String, nullable=False),
)
