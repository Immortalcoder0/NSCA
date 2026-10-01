"""Ratification — TRD-08.3 §6, backend-02 M3.

The two-person ratification DB-constraint test is one of this milestone's
explicitly required tests (task brief). It is written to hit the real
`candidate_rule_two_person_rule` CHECK constraint directly via SQL,
bypassing `ratification.ratify()`'s own Python-level guard, so it actually
proves the DB enforces this — not just that the service function does.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from nsca_platform.db.models.learning import candidate_rule as candidate_rule_table
from nsca_platform.learning import ratification
from nsca_platform.tests.conftest import requires_db


def _insert_provisional_rule(conn, *, taught_by: str = "r.kulkarni") -> str:
    public_id = f"RULE-test-{uuid.uuid4().hex[:8]}"
    conn.execute(
        candidate_rule_table.insert().values(
            id=uuid.uuid4(),
            public_id=public_id,
            extractor_id="mikrotik_routeros.ip_service.telnet_enabled",
            version=1,
            platform="mikrotik_routeros",
            rulepack="mikrotik_routeros",
            extractor_doc={"extractor_id": "x", "match": "y", "emit": []},
            status="provisional",
            taught_by=taught_by,
            source_artifact="RTR-Pune-02.rsc",
            confirmed_examples=5,
            proposal_source="heuristic",
            polarity_confirmed=True,
        )
    )
    return public_id


@requires_db
def test_ratify_by_a_different_user_succeeds(db_conn):
    public_id = _insert_provisional_rule(db_conn, taught_by="r.kulkarni")
    result = ratification.ratify(db_conn, public_id, "v.singh")
    assert result["status"] == "ratified"
    assert result["ratified_by"] == "v.singh"


@requires_db
def test_service_layer_refuses_self_ratification(db_conn):
    """V-08.3-006 — refused via the service layer's own check."""

    public_id = _insert_provisional_rule(db_conn, taught_by="r.kulkarni")
    with pytest.raises(ratification.SelfRatificationError):
        ratification.ratify(db_conn, public_id, "r.kulkarni")


@requires_db
def test_db_constraint_refuses_self_ratification_even_bypassing_the_service_layer(db_conn):
    """THE two-person ratification DB-constraint test: hits the raw table
    directly with an UPDATE that sets `ratified_by = taught_by`, bypassing
    `ratification.ratify()` entirely (as if a future or buggy code path
    tried to do this). The `candidate_rule_two_person_rule` CHECK
    constraint must still refuse it — this is what "enforced at the DB
    layer" (backend-02 §4.1) actually means: no Python code path, however
    written, can create a self-ratified row."""

    public_id = _insert_provisional_rule(db_conn, taught_by="r.kulkarni")

    with pytest.raises(IntegrityError, match="candidate_rule_two_person_rule"):
        db_conn.execute(
            candidate_rule_table.update()
            .where(candidate_rule_table.c.public_id == public_id)
            .values(status="ratified", ratified_by="r.kulkarni")
        )
        db_conn.commit()
    db_conn.rollback()


@requires_db
def test_db_constraint_allows_null_ratified_by(db_conn):
    """The constraint is `ratified_by IS NULL OR ratified_by <> taught_by`
    — a still-provisional row (ratified_by NULL) must remain insertable."""

    public_id = _insert_provisional_rule(db_conn, taught_by="r.kulkarni")
    row = ratification.get_rule(db_conn, public_id)
    assert row["status"] == "provisional"
    assert row["ratified_by"] is None


@requires_db
def test_ratification_is_recorded_in_the_audit_log(db_conn):
    from sqlalchemy import select

    from nsca_platform.db.models.admin import audit_log_entry

    public_id = _insert_provisional_rule(db_conn, taught_by="r.kulkarni")
    ratification.ratify(db_conn, public_id, "v.singh")

    rows = db_conn.execute(
        select(audit_log_entry).where(audit_log_entry.c.entity_id == public_id)
    ).fetchall()
    actions = {r.action for r in rows}
    assert "learning.rule.save_provisional" in actions or "learning.rule.ratify" in actions
    assert "learning.rule.ratify" in actions


# ---------------------------------------------------------------------------
# Provisional-exclusion-from-reports filter — INV-08.3-04 / DM-5.
# ---------------------------------------------------------------------------


def test_is_report_eligible_excludes_provisional():
    assert ratification.is_report_eligible("provisional", "local") is False


def test_is_report_eligible_excludes_deprecated():
    assert ratification.is_report_eligible("deprecated", "local") is False


def test_is_report_eligible_includes_ratified_local_tier():
    assert ratification.is_report_eligible("ratified", "local") is True


def test_is_report_eligible_includes_certified_and_verified_community():
    assert ratification.is_report_eligible("ratified", "certified") is True
    assert ratification.is_report_eligible("ratified", "verified_community") is True


def test_is_report_eligible_excludes_provisional_trust_tier_even_if_status_ratified():
    """Belt-and-braces: a rulepack-level `provisional` trust tier (imported
    bundle not yet ratified as a whole) excludes even an individually
    `ratified`-status rule within it."""

    assert ratification.is_report_eligible("ratified", "provisional") is False


def test_filter_report_eligible_findings_excludes_provisional_rule_findings():
    findings = [
        {"id": "F-1", "rule_status": "ratified", "rulepack_trust_tier": "local"},
        {"id": "F-2", "rule_status": "provisional", "rulepack_trust_tier": "local"},
        {"id": "F-3", "rule_status": "ratified", "rulepack_trust_tier": "certified"},
    ]
    eligible = ratification.filter_report_eligible_findings(findings)
    eligible_ids = {f["id"] for f in eligible}
    assert eligible_ids == {"F-1", "F-3"}
