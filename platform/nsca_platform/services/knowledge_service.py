"""Persistence for knowledge-base import — backend-02 §4.5, M4.

One place `api/knowledge.py` calls to turn parsed `ParsedFrameworkItem`s
(from `knowledge_import.stig_xccdf`/`nist_oscal`) into `framework_item` rows,
and to import/export rulepack bundles
(`knowledge_import.rulepack_bundle`). Every state-changing call writes the
audit log in the same transaction (backend-02 §2.3).

M5 addition (Phase 3 demo-rehearsal Bugs 1/2/3/4/5): real reads over the
`KnowledgeBase` (`knowledge_base_loader.get_knowledge_base`) for
rulepacks/controls/schema/freshness, and real reads over `framework_item`
for frameworks/coverage/preview/ratify + the known-framework-family set
`services/campaign.py`'s Bug 4 fix validates against — one source of
truth for "what frameworks does this build actually know about," shared
by both the knowledge endpoints and campaign creation.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from nsca_platform.audit import log as audit_log
from nsca_platform.db.models.knowledge import framework_item as framework_item_table
from nsca_platform.knowledge_base_loader import (
    KnowledgeBaseUnavailable,
    get_knowledge_base,
    knowledge_dir_from_env,
)
from nsca_platform.knowledge_import.stig_xccdf import ParsedFrameworkItem

# The four framework families this build's docs/data model recognise
# (06-controls-and-frameworks.md §5's import-source table: CIS, DISA STIG,
# NIST SP 800-53, ISO/IEC 27001) — known *as families*, independent of
# whether this milestone's import machinery has a parser for them yet
# (only STIG XCCDF and NIST OSCAL are wired; CIS/ISO import is explicitly
# out of scope, per `api/knowledge.py`'s module docstring). Campaign
# framework selection (Bug 4) validates against this set unioned with
# whatever has actually been imported into `framework_item` — so a real
# family name is always accepted even before any content for it exists,
# but a genuinely made-up string is not.
KNOWN_FRAMEWORK_FAMILIES: frozenset[str] = frozenset({"cis", "nist", "stig", "iso"})


class FrameworkNotFound(Exception):
    pass


class RulepackNotFound(Exception):
    pass


def import_framework_items(
    conn: Connection, items: Sequence[ParsedFrameworkItem], *, actor: str
) -> dict[str, Any]:
    """Upserts every parsed item (idempotent re-import: `ON CONFLICT`
    the unique `(framework, benchmark, version, item_id)` key updates in
    place — a STIG release imported twice must not create duplicate rows).
    """

    imported = 0
    for item in items:
        stmt = pg_insert(framework_item_table).values(
            id=uuid.uuid4(), imported_by=actor, **item.as_dict(),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_framework_item",
            set_={
                "title": stmt.excluded.title,
                "severity": stmt.excluded.severity,
                "stated_audit_procedure": stmt.excluded.stated_audit_procedure,
                "automation_status": stmt.excluded.automation_status,
                "text_redistributable": stmt.excluded.text_redistributable,
                "imported_by": stmt.excluded.imported_by,
            },
        )
        conn.execute(stmt)
        imported += 1

    audit_log.record(
        conn, actor=actor, action="knowledge.framework.import",
        entity_type="framework_item",
        entity_id=f"{items[0].framework}:{items[0].benchmark}@{items[0].version}" if items else "empty",
        details={"count": imported, "framework": items[0].framework if items else None},
    )
    return {
        "framework": items[0].framework if items else None,
        "benchmark": items[0].benchmark if items else None,
        "version": items[0].version if items else None,
        "status": "imported",
        "items_imported": imported,
    }


def list_framework_items(
    conn: Connection, framework: str | None = None, benchmark: str | None = None
) -> list[dict[str, Any]]:
    query = select(framework_item_table)
    if framework:
        query = query.where(framework_item_table.c.framework == framework)
    if benchmark:
        query = query.where(framework_item_table.c.benchmark == benchmark)
    rows = conn.execute(query.order_by(framework_item_table.c.item_id)).fetchall()

    results = []
    for r in rows:
        entry: dict[str, Any] = {
            "framework": r.framework, "benchmark": r.benchmark, "version": r.version,
            "item_id": r.item_id, "severity": r.severity,
            "automation_status": r.automation_status,
            "text_redistributable": r.text_redistributable,
        }
        # INV-09.1-07 / DM-9: text fields are only ever present when the
        # source explicitly permits redistribution — enforced again here
        # (belt-and-braces on top of the DB CHECK constraint) so a future
        # response-shape change can't accidentally surface withheld text.
        if r.text_redistributable:
            entry["title"] = r.title
            entry["stated_audit_procedure"] = r.stated_audit_procedure
        results.append(entry)
    return results


def known_framework_families(conn: Connection) -> set[str]:
    """The static, documented family set unioned with whatever has
    actually been imported (so a rulepack-bundle-style import path that
    lands under a not-yet-listed family name is still recognised without a
    code change, same generality principle as `load_knowledge_base`)."""

    imported = conn.execute(select(framework_item_table.c.framework).distinct()).fetchall()
    return set(KNOWN_FRAMEWORK_FAMILIES) | {r[0] for r in imported if r[0]}


def list_frameworks(conn: Connection) -> list[dict[str, Any]]:
    """Real distinct (framework, benchmark, version) triples actually
    present in `framework_item` — Phase 3 demo-rehearsal Bug 3's second
    half: `GET /knowledge/frameworks` previously returned three hardcoded
    literal entries regardless of what (if anything) had been imported."""

    rows = conn.execute(
        select(
            framework_item_table.c.framework,
            framework_item_table.c.benchmark,
            framework_item_table.c.version,
        )
        .distinct()
        .order_by(framework_item_table.c.framework, framework_item_table.c.benchmark, framework_item_table.c.version)
    ).fetchall()
    return [{"framework": r.framework, "benchmark": r.benchmark, "version": r.version} for r in rows]


def framework_coverage(conn: Connection, framework_id: str) -> dict[str, Any]:
    """Real automation-coverage manifest computed from imported
    `framework_item` rows. Raises `FrameworkNotFound` for a framework with
    zero imported items (e.g. `cis`/`iso`, whose import parsers are out of
    this milestone's scope) rather than returning a fabricated manifest —
    same "404, not a fake payload" principle as `rulepack_coverage`."""

    rows = conn.execute(
        select(framework_item_table).where(framework_item_table.c.framework == framework_id)
    ).fetchall()
    if not rows:
        raise FrameworkNotFound(framework_id)

    total = len(rows)
    counts = {"automated": 0, "manual_only": 0, "data_unavailable": 0, "not_implemented": 0}
    for r in rows:
        counts[r.automation_status if r.automation_status in counts else "not_implemented"] += 1

    latest = max(rows, key=lambda r: r.imported_at)
    manual_only_items = [
        {"id": r.item_id, "reason": r.equivalence_rationale or "reason not recorded by this import"}
        for r in rows
        if r.automation_status == "manual_only"
    ]

    return {
        "framework": framework_id,
        "benchmark": latest.benchmark,
        "version": latest.version,
        "total_recommendations": total,
        "automated": counts["automated"],
        "manual_only": counts["manual_only"],
        "data_unavailable": counts["data_unavailable"],
        "not_implemented": counts["not_implemented"],
        "automation_rate": round(counts["automated"] / total, 4) if total else 0.0,
        "manual_only_items": manual_only_items,
    }


def preview_framework_update(conn: Connection, framework_id: str) -> dict[str, Any]:
    """Honest, reduced version of the documented "estate impact dry run"
    (15-api-specification.md §7): this build does not persist versioned
    framework snapshots, so a real added/modified/withdrawn diff against a
    prior version cannot be computed. Rather than keep returning the
    spec's literal example numbers as if they were real, this reports the
    one real, grounded fact available — the current imported item count —
    and says plainly that the diff itself isn't available yet."""

    items = list_framework_items(conn, framework=framework_id)
    if not items:
        raise FrameworkNotFound(framework_id)
    return {
        "framework_id": framework_id,
        "current_item_count": len(items),
        "content_changes": None,
        "estate_impact": None,
        "note": (
            "This build does not persist versioned framework snapshots, so a real "
            "added/modified/withdrawn diff against a prior version cannot be computed "
            "here — current_item_count is real, content_changes/estate_impact are "
            "genuinely unavailable rather than fabricated."
        ),
    }


def ratify_framework_update(conn: Connection, framework_id: str, *, actor: str) -> dict[str, Any]:
    items = list_framework_items(conn, framework=framework_id)
    if not items:
        raise FrameworkNotFound(framework_id)
    audit_log.record(
        conn, actor=actor, action="knowledge.framework.ratify", entity_type="framework_item",
        entity_id=framework_id, details={"item_count": len(items)},
    )
    return {"framework_id": framework_id, "status": "ratified", "ratified_by": actor, "item_count": len(items)}


# ---------------------------------------------------------------------------
# Rulepacks / controls / schema / freshness — real reads over the
# `KnowledgeBase` (`knowledge_base_loader.get_knowledge_base`), M5.
# `KnowledgeBaseUnavailable` degrades to an empty result rather than a 500
# (this is a read path many demo screens hit; a missing/broken
# knowledge dir shouldn't take down every knowledge-base screen at once —
# ingestion/assessment, which actually need a KnowledgeBase to do their
# job, still surface the failure loudly at their own call sites).
# ---------------------------------------------------------------------------


def _emitted_fact_paths(loaded_rulepack: Any) -> set[str]:
    """Every fact path this rulepack's extractors can actually produce, per
    their declared `emit[].fact` targets (07-vendor-rulepacks.md §5) — the
    real signal `rulepack_coverage` cross-references against each
    applicable control's `requires_facts`, replacing the old hardcoded
    `controls_covered: 154` stub. Does not additionally account for
    `rulepack.defaults` (a fact with no extractor emitting it can still be
    *resolved* at assessment time via a platform default) — flagged as a
    conservative simplification, not silently assumed: coverage computed
    this way can only under-count, never over-claim, a control as covered
    when it in fact is not extractable, which matches the "never over-claim"
    principle other M1 engine code (`assess_device`) already follows."""

    paths: set[str] = set()
    for extractor in getattr(loaded_rulepack, "extractors", ()) or ():
        for emit in getattr(extractor, "emits", ()) or ():
            fact = getattr(emit, "fact", None)
            if fact:
                paths.add(fact)
    return paths


def _all_native_controls(kb: Any) -> list[Any]:
    controls: list[Any] = []
    for cp in kb.control_packs:
        if cp.loaded is not None:
            controls.extend(cp.loaded.controls)
    return controls


def _control_applies(control: Any, platform: str) -> bool:
    family = control.applies_to.platform_family
    return "*" in family or platform in family


def list_rulepacks() -> list[dict[str, Any]]:
    """Every rulepack the real `KnowledgeBase` actually loaded from
    `nsca/knowledge/rulepacks/` — Phase 3 demo-rehearsal Bug 1: this
    previously returned one hardcoded `cisco_iosxe` entry regardless of
    what was on disk."""

    try:
        kb = get_knowledge_base()
    except KnowledgeBaseUnavailable:
        return []
    return [
        {"id": rp.platform, "version": rp.version, "trust_tier": rp.trust_tier, "platform": rp.platform}
        for rp in sorted(kb.rulepacks, key=lambda r: r.platform)
    ]


def rulepack_coverage(rulepack_id: str) -> dict[str, Any]:
    """Real coverage: of every native control applicable to this
    rulepack's platform (`applies_to.platform_family`), how many can
    actually be evaluated because every fact path it `requires_facts`
    is one this rulepack's extractors emit. Raises `RulepackNotFound` for
    an id that isn't a real loaded rulepack — Phase 3 demo-rehearsal Bug 2:
    this previously returned an identical fabricated payload for any id,
    including nonsense ones."""

    try:
        kb = get_knowledge_base()
    except KnowledgeBaseUnavailable as exc:
        raise RulepackNotFound(rulepack_id) from exc

    rulepack = next((rp for rp in kb.rulepacks if rp.platform == rulepack_id), None)
    if rulepack is None:
        raise RulepackNotFound(rulepack_id)

    emitted = _emitted_fact_paths(rulepack.loaded) if rulepack.loaded is not None else set()
    applicable = [c for c in _all_native_controls(kb) if _control_applies(c, rulepack_id)]
    covered = [c for c in applicable if set(c.requires_facts) <= emitted]

    total = len(applicable)
    covered_n = len(covered)
    return {
        "rulepack_id": rulepack_id,
        "version": rulepack.version,
        "controls_covered": covered_n,
        "controls_total": total,
        "coverage_rate": round(covered_n / total, 4) if total else 0.0,
    }


def _enum_value(x: Any) -> Any:
    return getattr(x, "value", x)


def list_controls() -> list[dict[str, Any]]:
    try:
        kb = get_knowledge_base()
    except KnowledgeBaseUnavailable:
        return []
    items = [
        {
            "id": c.control_id,
            "title": c.title,
            "family": c.family,
            "severity_base": _enum_value(c.severity_base),
        }
        for c in _all_native_controls(kb)
    ]
    items.sort(key=lambda i: i["id"])
    return items


def schema_items() -> list[dict[str, Any]]:
    try:
        kb = get_knowledge_base()
    except KnowledgeBaseUnavailable:
        return []
    items = [
        {"path": fd.path, "type": fd.type, "category": fd.category, "domain": fd.domain, "status": fd.status}
        for domain in kb.schema_registry.domains
        for fd in kb.schema_registry.fact_definitions_for_domain(domain)
    ]
    items.sort(key=lambda i: i["path"])
    return items


def freshness() -> dict[str, Any]:
    try:
        kb = get_knowledge_base()
    except KnowledgeBaseUnavailable:
        return {"rulepacks": [], "vulnerability_index": None}

    knowledge_dir = knowledge_dir_from_env()
    rulepacks = []
    for rp in sorted(kb.rulepacks, key=lambda r: r.platform):
        path = knowledge_dir / "rulepacks" / f"{rp.platform}.yaml"
        imported_at = (
            datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat() if path.exists() else None
        )
        rulepacks.append({"id": rp.platform, "version": rp.version, "imported_at": imported_at})
    return {
        "rulepacks": rulepacks,
        # No vulnerability-index data source exists anywhere in this
        # codebase (grepped for one before writing this) — reported as
        # genuinely absent rather than a fabricated snapshot date/age.
        "vulnerability_index": None,
    }
