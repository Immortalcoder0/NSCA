"""M5 — admin_credential

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-01

Real physical schema for the Phase 3 rehearsal Bug 6 fix
(`api/admin.py`'s `/admin/credentials` M0 stub -> real DB-backed storage).

NFR-SEC-003 / 15-api-specification.md §9 ("credential material is never
returned by any endpoint under any role") is enforced *by construction*
here: this table has no column that can hold secret material at all —
`reference` is an opaque, non-secret handle only (see `db/models/admin.py`
module docstring for the fuller rationale).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_credential",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("reference", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("admin_credential")
