"""Administration — 15-api-specification.md §9.

Credential material is never returned by any endpoint under any role
(§9) — enforced by construction (see `db/models/admin.py`'s
`admin_credential` table docstring and `services/admin_service.py`'s
module docstring), not merely by a response-shape convention.

M5: `list_users`/`create_user`/`list_credentials`/`create_credential`/
`get_audit_log` (list) are wired to real DB-backed CRUD
(`services/admin_service.py`) — closing the Phase 3 demo-rehearsal Bug 6
gap. `GET /admin/audit-log/verify` was already real (M5, hash-chain
verification, unchanged below).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status

from nsca_platform.audit import log as audit_log
from nsca_platform.auth.dev_auth import (
    ROLE_DISPLAY_NAMES,
    DevUser,
    Role,
    get_current_user,
    require_role,
)
from nsca_platform.db.engine import connect
from nsca_platform.services import admin_service, demo_seed

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(user: DevUser = Depends(require_role(Role.PLATFORM_ADMINISTRATOR))) -> dict[str, Any]:
    with connect() as conn:
        return admin_service.list_users(conn)


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    body: dict[str, Any],
    user: DevUser = Depends(require_role(Role.PLATFORM_ADMINISTRATOR)),
) -> dict[str, Any]:
    with connect() as conn:
        result = admin_service.create_user(conn, body, actor=user.email)
        conn.commit()
        return result


@router.get("/roles")
def list_roles(user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    return {"items": [{"key": r.value, "name": ROLE_DISPLAY_NAMES[r]} for r in Role]}


@router.get("/credentials")
def list_credentials(user: DevUser = Depends(require_role(Role.NETWORK_ADMINISTRATOR))) -> dict[str, Any]:
    with connect() as conn:
        return admin_service.list_credentials(conn)


@router.post("/credentials", status_code=status.HTTP_201_CREATED)
def create_credential(
    body: dict[str, Any],
    user: DevUser = Depends(require_role(Role.NETWORK_ADMINISTRATOR)),
) -> dict[str, Any]:
    with connect() as conn:
        result = admin_service.create_credential(conn, body, actor=user.email)
        conn.commit()
        return result


@router.get("/audit-log")
def get_audit_log(user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    with connect() as conn:
        return admin_service.list_audit_log(conn)


@router.get("/audit-log/verify")
def verify_audit_log(user: DevUser = Depends(require_role(Role.PLATFORM_ADMINISTRATOR))) -> dict[str, Any]:
    """Real hash-chain verification (M5) — `audit.log.verify_chain` walks
    every `audit_log_entry` row via its `previous_entry_hash -> entry_hash`
    pointers and recomputes each entry's hash. 15-api-specification.md §9's
    documented response shape:
    `{"entries_checked": int, "chain_intact": bool, "first_break": str | None}`.
    """

    with connect() as conn:
        return audit_log.verify_chain(conn)


@router.post("/seed-demo-data")
def seed_demo_data(user: DevUser = Depends(require_role(Role.PLATFORM_ADMINISTRATOR))) -> dict[str, Any]:
    """One-click demo population — real dataflow, not fabricated rows or
    response shapes (see `services/demo_seed.py`'s module docstring for the
    full rationale). Creates one campaign, uploads 8 real multi-platform
    artifacts, resolves scope, runs a real assessment, issues the campaign,
    generates a real per-device report, and seeds a real training-queue
    entry — the same sequence a human clicking through the app would
    trigger. Safe to call repeatedly (each call creates a fresh campaign;
    training-queue seeding is idempotent and skips if already seeded)."""

    with connect() as conn:
        result = demo_seed.run(conn, user.id)
        conn.commit()
        return result


@router.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok"}


@router.get("/status")
def system_status(user: DevUser = Depends(get_current_user)) -> dict[str, Any]:
    return admin_service.system_status(None)
