"""Real SQLAlchemy Core table definitions — M1.

One module per data-model entity group, per backend-02 §4's module layout.
All modules share the single `metadata` object defined in `base.py` so
Alembic (`db/migrations/env.py`) has one source of truth to diff against.

Importing this package (or any submodule) registers every table on
`metadata` as a side effect — this is the SQLAlchemy Core idiom the M0
`db/tables.py` scaffold already used.
"""

from __future__ import annotations

from nsca_platform.db.models.admin import admin_credential, admin_user, audit_log_entry, report
from nsca_platform.db.models.artifact import artifact
from nsca_platform.db.models.assessment import assessment, fact
from nsca_platform.db.models.base import metadata
from nsca_platform.db.models.campaign import campaign
from nsca_platform.db.models.device import device
from nsca_platform.db.models.finding import finding, finding_transition
from nsca_platform.db.models.knowledge import framework_item
from nsca_platform.db.models.lifecycle import dispute, remediation_plan, risk_acceptance
from nsca_platform.db.models.learning import (
    candidate_rule,
    training_answer,
    training_question,
    transfer_metric_confirmation,
    transfer_metric_session,
    unmatched_construct,
)

__all__ = [
    "metadata",
    "campaign",
    "device",
    "artifact",
    "assessment",
    "fact",
    "admin_user",
    "admin_credential",
    "audit_log_entry",
    "finding",
    "finding_transition",
    "dispute",
    "risk_acceptance",
    "unmatched_construct",
    "training_question",
    "training_answer",
    "candidate_rule",
    "transfer_metric_session",
    "transfer_metric_confirmation",
    "framework_item",
    "remediation_plan",
    "report",
]
