"""Shared `MetaData` for every table in `db/models/` (M1).

Per backend-02 §4.1: SQLAlchemy Core, not the ORM. All model modules
import this single `metadata` object so Alembic has one target to diff
against (see `db/migrations/env.py`).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Column, MetaData
from sqlalchemy.dialects.postgresql import UUID

metadata = MetaData()


def uuid_pk() -> Column:
    """Standard UUID primary key column, generated client-side.

    Client-side default (rather than a DB `gen_random_uuid()` default) so
    application code can know an object's id before the INSERT commits —
    needed for the audit-log-in-the-same-transaction pattern (backend-02
    §2.3): the service layer builds the audit entry referencing the new
    row's id in the same statement batch.
    """

    return Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
