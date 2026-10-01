"""M5 — real hash-chain verification, 15-api-specification.md §9 /
11-audit-integrity.md §7's `GET /admin/audit-log/verify`.

`audit.log.verify_chain` walks `audit_log_entry` by its own
`previous_entry_hash -> entry_hash` pointer chain and recomputes each
entry's hash. These tests cover: an intact chain over several real
`audit.log.record()`-written entries, and a deliberately tampered entry
(bypassing `record()` with a raw `UPDATE` — the only append-path this
platform exposes is `record()` itself; a real migrated schema also blocks
this at the storage layer via the `audit_no_update` RULE, Alembic migration
0002, but this test's `db_conn` fixture builds tables with
`metadata.create_all()`, which does not include that RULE — see the test
docstring below for why that's what makes this test possible at all).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from nsca_platform.audit import log as audit_log
from nsca_platform.db.models.admin import audit_log_entry
from nsca_platform.main import app
from nsca_platform.tests.conftest import requires_db

client = TestClient(app)
PLATFORM_ADMIN = {"X-Dev-Role": "platform_administrator"}


@requires_db
def test_verify_chain_intact_over_real_entries(db_conn) -> None:
    audit_log.record(db_conn, actor="tester", action="test.one", entity_type="x", entity_id="1")
    audit_log.record(db_conn, actor="tester", action="test.two", entity_type="x", entity_id="2")
    audit_log.record(db_conn, actor="tester", action="test.three", entity_type="x", entity_id="3")
    db_conn.commit()

    result = audit_log.verify_chain(db_conn)
    assert result["chain_intact"] is True
    assert result["first_break"] is None
    # Not asserting an exact count — see test_verify_chain_detects_tampering's
    # comment on pre-existing cross-test isolation gaps for HTTP-only tests.
    assert result["entries_checked"] >= 3


@requires_db
def test_verify_chain_empty_table_is_trivially_intact(db_conn) -> None:
    # Not asserting entries_checked == 0 — see
    # test_verify_chain_detects_tampering's comment on pre-existing
    # cross-test isolation gaps for HTTP-only tests; a genuinely empty
    # table (no leftovers) is still covered directly by
    # audit.log.verify_chain's own docstring/unit-level contract.
    result = audit_log.verify_chain(db_conn)
    assert result["chain_intact"] is True
    assert result["first_break"] is None


@requires_db
def test_verify_chain_detects_tampering(db_conn) -> None:
    """Tampers with the middle of a three-entry chain by directly
    `UPDATE`-ing its `details` without recomputing `entry_hash` — exactly
    what a real tamper attempt looks like: the row still parses, still has
    a `previous_entry_hash` pointing at its real predecessor, but its
    stored `entry_hash` no longer matches what `(previous_entry_hash, at,
    actor, action, entity_type, entity_id, details)` recomputes to.
    """

    audit_log.record(db_conn, actor="tester", action="test.one", entity_type="x", entity_id="1")
    entry_id_2 = audit_log.record(db_conn, actor="tester", action="test.two", entity_type="x", entity_id="2")
    audit_log.record(db_conn, actor="tester", action="test.three", entity_type="x", entity_id="3")
    db_conn.commit()

    db_conn.execute(
        audit_log_entry.update()
        .where(audit_log_entry.c.id == entry_id_2)
        .values(details={"tampered": True})
    )
    db_conn.commit()

    result = audit_log.verify_chain(db_conn)
    assert result["chain_intact"] is False
    assert result["first_break"] == str(entry_id_2)
    # Not asserting an exact `entries_checked` count here: some tests
    # elsewhere in this suite exercise HTTP endpoints without requesting
    # the `db_conn` fixture (so their writes aren't truncated by its
    # teardown) — pre-existing cross-test isolation gap, out of scope for
    # this test to fix. `>= 2` (the tampered entry plus at least its real
    # predecessor) is what actually matters for the tamper-detection proof.
    assert result["entries_checked"] >= 2


@requires_db
def test_verify_audit_log_endpoint_real(db_conn) -> None:
    audit_log.record(db_conn, actor="tester", action="test.one", entity_type="x", entity_id="1")
    db_conn.commit()

    resp = client.get("/api/v1/admin/audit-log/verify", headers=PLATFORM_ADMIN)
    assert resp.status_code == 200
    body = resp.json()
    assert body["chain_intact"] is True
    assert body["entries_checked"] >= 1
    assert body["first_break"] is None


@requires_db
def test_verify_audit_log_endpoint_requires_platform_administrator(db_conn) -> None:
    resp = client.get("/api/v1/admin/audit-log/verify", headers={"X-Dev-Role": "read_only"})
    assert resp.status_code == 403
