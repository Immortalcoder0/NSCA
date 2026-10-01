"""Append an audit-log entry inside the caller's transaction.

Per backend-02 §2.3: "Design the audit log write as part of the same
service-layer function that performs the state change (same transaction),
from the first endpoint you build, so it is structurally impossible to add
a ninth endpoint that forgets it." `record()` therefore takes an open
`Connection` — never opens its own — so every call site is guaranteed to
be inside the same transaction as the state change it documents; the
caller commits both together.

Hash chaining (DM-8, 14-data-model.md §6 AUDIT_LOG_ENTRY): each entry's
`entry_hash` covers `(previous_entry_hash, at, actor, action, entity_type,
entity_id, details)`. `previous_entry_hash` is looked up with
`SELECT ... ORDER BY at DESC LIMIT 1 FOR UPDATE` so concurrent writers
serialize on the tail of the chain rather than racing to read the same
"previous" row — otherwise two concurrent audit writes could both compute
their hash from the same previous entry and silently fork the chain.

`verify_chain` (M5, 15-api-specification.md §9's `GET /admin/audit-log
/verify`) walks the chain **by its own linked-list pointers**
(`previous_entry_hash -> entry_hash`), not by `at` ordering — `at` values
can collide at whatever timestamp resolution the database stores, but the
pointer chain is the actual, unambiguous write order the tail-`FOR UPDATE`
serialization above constructed. A single row with `previous_entry_hash IS
NULL` is the expected chain head; more than one, or any row unreachable by
following pointers from that head, or any row whose own `entry_hash`
doesn't match a fresh recomputation, is a broken chain.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from nsca_platform.db.models.admin import audit_log_entry


def _entry_hash(
    previous_hash: str | None,
    at: datetime,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, Any] | None,
) -> str:
    payload = {
        "previous_entry_hash": previous_hash,
        "at": at.isoformat(),
        "actor": actor,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record(
    conn: Connection,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, Any] | None = None,
) -> uuid.UUID:
    """Writes one audit_log_entry row, chained to the current tail, using
    the caller's connection/transaction. Does not commit — the caller's
    transaction boundary is the audit entry's transaction boundary, by
    design (backend-02 §2.3).
    """

    tail = conn.execute(
        select(audit_log_entry.c.entry_hash)
        .order_by(audit_log_entry.c.at.desc())
        .limit(1)
        .with_for_update()
    ).first()
    previous_hash = tail[0] if tail else None

    at = datetime.now(UTC)
    entry_id = uuid.uuid4()
    entry_hash = _entry_hash(previous_hash, at, actor, action, entity_type, entity_id, details)

    conn.execute(
        audit_log_entry.insert().values(
            id=entry_id,
            at=at,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            previous_entry_hash=previous_hash,
            entry_hash=entry_hash,
        )
    )
    return entry_id


def verify_chain(conn: Connection) -> dict[str, Any]:
    """Real hash-chain verification (M5, `GET /admin/audit-log/verify`,
    15-api-specification.md §9). Returns
    `{"entries_checked": int, "chain_intact": bool, "first_break": str | None}`
    — `first_break` is the `id` (as a string) of the first entry, in chain
    order, whose own hash doesn't recompute correctly or that breaks the
    linked-list structure (a fork or an orphan); `None` when the whole
    chain (all rows in the table) verifies clean.

    An empty table is a trivially intact chain (`entries_checked=0`,
    `chain_intact=True`) — there is nothing to have broken.
    """

    rows = conn.execute(select(audit_log_entry)).fetchall()
    if not rows:
        return {"entries_checked": 0, "chain_intact": True, "first_break": None}

    children_by_prev: dict[str | None, list[Any]] = {}
    for row in rows:
        children_by_prev.setdefault(row.previous_entry_hash, []).append(row)

    heads = children_by_prev.get(None, [])
    if len(heads) != 1:
        # Zero heads (every row claims a previous_entry_hash, i.e. no valid
        # start of a chain) or multiple heads (more than one chain claims to
        # be "the" chain) are both structurally broken — report the
        # earliest-inserted row among the offending set as the break point.
        offending = heads if heads else rows
        first = min(offending, key=lambda r: (r.at, str(r.id)))
        return {"entries_checked": len(rows), "chain_intact": False, "first_break": str(first.id)}

    previous_hash: str | None = None
    current = heads[0]
    visited_ids: set[Any] = set()
    entries_checked = 0
    first_break: str | None = None

    while True:
        entries_checked += 1
        expected_hash = _entry_hash(
            previous_hash, current.at, current.actor, current.action,
            current.entity_type, current.entity_id, current.details,
        )
        if current.entry_hash != expected_hash:
            first_break = str(current.id)
            break

        visited_ids.add(current.id)
        previous_hash = current.entry_hash

        next_candidates = children_by_prev.get(current.entry_hash, [])
        if not next_candidates:
            break
        if len(next_candidates) > 1:
            # A fork: two entries both claim this one as their predecessor.
            first_break = str(min(next_candidates, key=lambda r: (r.at, str(r.id))).id)
            break
        current = next_candidates[0]

    if first_break is None and entries_checked != len(rows):
        # Rows exist that the pointer walk never reached — orphaned entries,
        # also a broken chain, even though every visited entry hashed clean.
        orphan = min((r for r in rows if r.id not in visited_ids), key=lambda r: (r.at, str(r.id)))
        first_break = str(orphan.id)
        entries_checked = len(rows)

    return {
        "entries_checked": entries_checked,
        "chain_intact": first_break is None,
        "first_break": first_break,
    }
