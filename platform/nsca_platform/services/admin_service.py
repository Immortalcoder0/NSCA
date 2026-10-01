"""Administration — real DB-backed users/credentials/status, M5.

Closes the Phase 3 demo-rehearsal Bug 6 gap: `api/admin.py`'s
`list_users`/`create_user`/`list_credentials`/`create_credential`/
`get_audit_log` were M0 stubs returning hardcoded fake data regardless of
what was actually in the database. This module wires them to the real
`admin_user`/`admin_credential`/`audit_log_entry` tables
(`db/models/admin.py`).

**Credential material (NFR-SEC-003).** `create_credential` never writes
whatever secret the caller submitted (`body.get("secret")`/`body.get(
"value")`, if present) anywhere — not to this table, not to the audit log
`details` blob, not to a log line. Only a label, a type, and an opaque
`reference` (caller-supplied if given, otherwise a generated placeholder
handle such as a vault path) are persisted. `list_credentials` therefore
cannot leak a secret by construction: one was never stored.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from nsca_platform.audit import log as audit_log
from nsca_platform.db.engine import database_available
from nsca_platform.db.models.admin import admin_credential as admin_credential_table
from nsca_platform.db.models.admin import admin_user as admin_user_table
from nsca_platform.db.models.admin import audit_log_entry as audit_log_entry_table

# Fields that must never be persisted or echoed back, under any key
# spelling a client might use — belt-and-braces on top of the schema-level
# guarantee (admin_credential has no column that *could* hold one).
_SECRET_BODY_KEYS = ("secret", "value", "password", "private_key", "key", "token")


def _user_row_to_dict(row: Any) -> dict[str, Any]:
    return {"id": str(row.id), "name": row.name, "email": row.email, "role": row.role}


def list_users(conn: Connection) -> dict[str, Any]:
    rows = conn.execute(select(admin_user_table).order_by(admin_user_table.c.created_at)).fetchall()
    return {"items": [_user_row_to_dict(r) for r in rows]}


def create_user(conn: Connection, body: dict[str, Any], *, actor: str) -> dict[str, Any]:
    user_id = uuid.uuid4()
    name = body.get("name", "Unnamed User")
    email = body.get("email") or f"{user_id.hex[:8]}@example.invalid"
    role = body.get("role", "assessor")
    conn.execute(admin_user_table.insert().values(id=user_id, name=name, email=email, role=role))
    audit_log.record(
        conn, actor=actor, action="admin.user.create", entity_type="admin_user",
        entity_id=str(user_id), details={"name": name, "role": role},
    )
    row = conn.execute(select(admin_user_table).where(admin_user_table.c.id == user_id)).first()
    return {**_user_row_to_dict(row), "status": "created"}


def _credential_row_to_dict(row: Any) -> dict[str, Any]:
    # Deliberately excludes `reference` from the public shape too — even
    # though it is never a secret, it can be a vault path/identifier that
    # is itself sensitive infrastructure detail, and nothing in
    # 15-api-specification.md §9's documented shape (`id`, `label`, `type`)
    # requires exposing it.
    return {"id": str(row.id), "label": row.label, "type": row.type}


def list_credentials(conn: Connection) -> dict[str, Any]:
    rows = conn.execute(select(admin_credential_table).order_by(admin_credential_table.c.created_at)).fetchall()
    return {"items": [_credential_row_to_dict(r) for r in rows]}


def create_credential(conn: Connection, body: dict[str, Any], *, actor: str) -> dict[str, Any]:
    cred_id = uuid.uuid4()
    label = body.get("label", "unnamed")
    cred_type = body.get("type", "ssh_keypair")
    # A caller-supplied `reference` (e.g. "vault:kv/nsca/ios-audit") is
    # stored as-is; a caller-supplied secret is never stored under any
    # key — only a generated opaque placeholder handle stands in for it.
    reference = body.get("reference") or f"unmanaged-ref-{cred_id.hex[:12]}"
    conn.execute(
        admin_credential_table.insert().values(
            id=cred_id, label=label, type=cred_type, reference=reference, created_by=actor,
        )
    )
    audit_log.record(
        conn, actor=actor, action="admin.credential.create", entity_type="admin_credential",
        entity_id=str(cred_id),
        # `details` carries only label/type — never `reference`/secret —
        # since the audit log is itself readable via GET /admin/audit-log.
        details={"label": label, "type": cred_type, "secret_fields_supplied": sorted(
            k for k in body if k in _SECRET_BODY_KEYS
        )},
    )
    return {"id": str(cred_id), "label": label, "type": cred_type}


def list_audit_log(conn: Connection, limit: int = 50) -> dict[str, Any]:
    rows = conn.execute(
        select(audit_log_entry_table).order_by(audit_log_entry_table.c.at.desc()).limit(limit)
    ).fetchall()
    items = [
        {
            "id": str(r.id),
            "actor": r.actor,
            "action": r.action,
            "target": r.entity_id,
            "at": r.at.isoformat(),
            "hash": r.entry_hash,
        }
        for r in rows
    ]
    return {"items": items, "next_cursor": None}


def system_status(conn: Connection | None) -> dict[str, Any]:
    db_ok = database_available()
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "unreachable",
        # No persistent job queue/worker exists in this build (ingestion,
        # assessment and report generation all run synchronously within
        # the request — see api/reports.py's module docstring for the
        # report-generation case) — reported honestly rather than as a
        # plausible-looking fabricated queue depth.
        "job_queue": {"pending": 0, "running": 0, "note": "no persistent job queue exists in this build; work runs synchronously"},
        "inference_container": "not_configured",
        "version": "0.1.0",
    }
