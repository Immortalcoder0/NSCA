"""Backward-compatible re-export shim.

M0 defined every table directly in this module. M1 moved the real physical
schema into `db/models/` (one module per data-model entity group, per
backend-02 §4's module layout) so Alembic, `db/mappers.py` and the service
layer all agree on a single source of truth. This module is kept only so
any pre-M1 import of `nsca_platform.db.tables` doesn't break; new code
should import from `nsca_platform.db.models` directly.
"""

from __future__ import annotations

from nsca_platform.db.models import (
    admin_user,
    artifact,
    assessment,
    campaign,
    device,
    dispute,
    fact,
    finding,
    finding_transition,
    metadata,
    risk_acceptance,
)

__all__ = [
    "metadata",
    "campaign",
    "device",
    "artifact",
    "assessment",
    "fact",
    "admin_user",
    "finding",
    "finding_transition",
    "dispute",
    "risk_acceptance",
]
