"""Ratification — TRD-08.3 §6, Stage 8 of 08-learning-system.md §2.

Two-person rule (FR-LRN-015): a rulepack is a control surface, and a wrong
rule produces wrong findings that look identical to right ones. The
`ratified_by <> taught_by` constraint is enforced **at the DB layer**
(`candidate_rule_two_person_rule` CHECK constraint,
`db/migrations/versions/0004_learning.py`) — not merely in this
service-layer code — per backend-02 §4.1's own `two_person_rule` example
and TECH-STACK.md §5. `ratify()` below still checks it in Python too,
purely to raise a clean domain exception (`SelfRatificationError`) instead
of surfacing a raw `IntegrityError` to the API layer; the DB constraint is
what actually makes self-ratification impossible even if this function is
bypassed (V-08.3-006's "including with Platform Administrator privileges...
No override path exists").

`is_report_eligible` is the enforcement point for INV-08.3-04 /
DM-5 ("Provisional rules' findings must be excluded from issued reports")
that M4's report generator is *required* to call — it does not exist yet
(M4 scope), so this function is the documented contract M4 must honour,
per the task brief's explicit instruction not to build the report
generator itself in M3.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from nsca_platform.audit import log as audit_log
from nsca_platform.db.models.learning import candidate_rule as candidate_rule_table

# 07-vendor-rulepacks.md §8 / 08-learning-system.md §8 — the trust-tier
# table. Only `ratified` (which becomes `local` tier once ratified) and
# higher tiers may appear in an issued report.
REPORT_ELIGIBLE_STATUSES = frozenset({"ratified"})
REPORT_ELIGIBLE_TIERS = frozenset({"certified", "verified_community", "local"})


class RatificationError(Exception):
    pass


class SelfRatificationError(RatificationError):
    """FR-LRN-015 / V-08.3-006 — raised before ever reaching the database,
    so the API returns a clean domain error; the DB CHECK constraint is
    the actual, un-bypassable enforcement point."""


class RuleNotFound(RatificationError):
    pass


class GatesNotPassed(RatificationError):
    pass


def _next_public_id(conn: Connection, platform: str) -> str:
    count = conn.execute(select(candidate_rule_table.c.id)).fetchall()
    return f"RULE-{platform}-{len(count) + 1:04d}"


def save_provisional(
    conn: Connection,
    *,
    extractor_id: str,
    version: int,
    platform: str,
    rulepack: str,
    extractor_doc: dict[str, Any],
    validation_report: dict[str, Any],
    taught_by: str,
    source_artifact: str,
    confirmed_examples: int,
    proposal_source: str,
    polarity_confirmed: bool | None,
    gates_passed: bool,
) -> dict[str, Any]:
    """TRD-08.3 §8's `save(extractor) -> provisional entry`. All six (plus
    coverage-delta) validation gates must have passed *before this is
    called* — `gates_passed` is asserted here as a structural invariant
    (backend-02 §4.3 point 7: "all six must run before a provisional rule
    is even saved"), not re-derived from the report, so a caller cannot
    accidentally save a rule whose gates it forgot to run."""

    if not gates_passed:
        raise GatesNotPassed(f"cannot save {extractor_id}: validation gates did not all pass")

    public_id = _next_public_id(conn, platform)
    row_id = uuid.uuid4()
    conn.execute(
        candidate_rule_table.insert().values(
            id=row_id,
            public_id=public_id,
            extractor_id=extractor_id,
            version=version,
            platform=platform,
            rulepack=rulepack,
            extractor_doc=extractor_doc,
            validation_report=validation_report,
            status="provisional",
            taught_by=taught_by,
            source_artifact=source_artifact,
            confirmed_examples=confirmed_examples,
            proposal_source=proposal_source,
            polarity_confirmed=polarity_confirmed,
        )
    )
    audit_log.record(
        conn, actor=taught_by, action="learning.rule.save_provisional",
        entity_type="candidate_rule", entity_id=public_id,
        details={"extractor_id": extractor_id, "platform": platform, "polarity_confirmed": polarity_confirmed},
    )
    return get_rule(conn, public_id)


def _row_to_response(row: Any) -> dict[str, Any]:
    return {
        "id": row.public_id,
        "extractor_id": row.extractor_id,
        "version": row.version,
        "platform": row.platform,
        "rulepack": row.rulepack,
        "status": row.status,
        "taught_by": row.taught_by,
        "taught_at": row.taught_at.isoformat() if row.taught_at else None,
        "ratified_by": row.ratified_by,
        "ratified_at": row.ratified_at.isoformat() if row.ratified_at else None,
        "source_artifact": row.source_artifact,
        "confirmed_examples": row.confirmed_examples,
        "polarity_confirmed": row.polarity_confirmed,
    }


def get_rule(conn: Connection, public_id: str) -> dict[str, Any]:
    row = conn.execute(select(candidate_rule_table).where(candidate_rule_table.c.public_id == public_id)).first()
    if row is None:
        raise RuleNotFound(public_id)
    return _row_to_response(row)


def list_rules(conn: Connection, status: str | None = None) -> list[dict[str, Any]]:
    query = select(candidate_rule_table)
    if status:
        query = query.where(candidate_rule_table.c.status == status)
    rows = conn.execute(query.order_by(candidate_rule_table.c.public_id)).fetchall()
    return [_row_to_response(r) for r in rows]


def ratify(conn: Connection, public_id: str, ratifier: str) -> dict[str, Any]:
    """TRD-08.3 §6.2's `ratify(rule, user)`:

        require user != rule.taught_by     # hard constraint
        require all validation gates passed
        record ratifier, timestamp
        status -> ratified

    The Python-level check below is a fast, clean-error path;
    `candidate_rule_two_person_rule` (the DB CHECK constraint) is what
    makes this un-bypassable even by a different, buggy call site."""

    row = conn.execute(select(candidate_rule_table).where(candidate_rule_table.c.public_id == public_id)).first()
    if row is None:
        raise RuleNotFound(public_id)
    if ratifier == row.taught_by:
        raise SelfRatificationError(
            f"{ratifier!r} authored {public_id!r} — a different authorised user must ratify it"
        )

    try:
        conn.execute(
            candidate_rule_table.update()
            .where(candidate_rule_table.c.id == row.id)
            .values(status="ratified", ratified_by=ratifier, ratified_at=datetime.now(UTC))
        )
    except IntegrityError as exc:
        # Belt-and-braces: the DB constraint firing means the Python check
        # above was somehow bypassed (e.g. a future code path). Surface it
        # as the same domain error rather than a raw IntegrityError.
        raise SelfRatificationError(str(exc)) from exc

    audit_log.record(
        conn, actor=ratifier, action="learning.rule.ratify", entity_type="candidate_rule",
        entity_id=public_id, details={"taught_by": row.taught_by},
    )
    return get_rule(conn, public_id)


def reject(conn: Connection, public_id: str, rejector: str, reason: str | None = None) -> dict[str, Any]:
    row = conn.execute(select(candidate_rule_table).where(candidate_rule_table.c.public_id == public_id)).first()
    if row is None:
        raise RuleNotFound(public_id)
    conn.execute(
        candidate_rule_table.update()
        .where(candidate_rule_table.c.id == row.id)
        .values(status="rejected", rejected_reason=reason)
    )
    audit_log.record(
        conn, actor=rejector, action="learning.rule.reject", entity_type="candidate_rule",
        entity_id=public_id, details={"reason": reason},
    )
    return get_rule(conn, public_id)


# ---------------------------------------------------------------------------
# Report eligibility — INV-08.3-04 / DM-5. M4's report generator MUST call
# this (or an equivalent check against a finding's originating rulepack
# trust tier) before including a finding in an issued report.
# ---------------------------------------------------------------------------


def is_report_eligible(rule_status: str, rulepack_trust_tier: str | None) -> bool:
    """TRD-08.3 §6.1's table:

        | Status      | Issued reports |
        |-------------|----------------|
        | provisional | No             |
        | ratified    | Yes            |
        | deprecated  | No             |

    and 07-vendor-rulepacks.md §8's trust-tier table (provisional tier is
    also excluded there, independent of the individual rule's own status —
    both checks apply, since a rulepack's *tier* and an individual rule's
    *status* are tracked separately: a `local` rulepack containing one
    still-provisional rule should exclude findings from *that* rule
    without excluding the whole rulepack's other, already-ratified rules).

    Called with `(finding.rule_status, finding.rulepack_trust_tier)` — see
    module docstring for why this lives here rather than in M4's
    (nonexistent) report generator.
    """

    if rule_status not in REPORT_ELIGIBLE_STATUSES:
        return False
    if rulepack_trust_tier is not None and rulepack_trust_tier not in REPORT_ELIGIBLE_TIERS:
        return False
    return True


def filter_report_eligible_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convenience wrapper `finding_lifecycle`/M4 report generation can
    call directly: filters a list of finding dicts (each carrying
    `rule_status` and `rulepack_trust_tier` keys) down to report-eligible
    ones. `A finding derived from provisional parsing is not evidence.`"""

    return [
        f for f in findings
        if is_report_eligible(f.get("rule_status", "provisional"), f.get("rulepack_trust_tier"))
    ]
