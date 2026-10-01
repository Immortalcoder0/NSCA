"""Evidence for absence-based findings (Phase 3 demo rehearsal finding 11,
§9 checklist item 11): a FAIL finding whose deciding fact is
`default_known` (a documented platform default, e.g. "no login banner is
configured by default") or `derived`-from-absence (e.g.
`logging.remote_configured` when no `logging host`/`logging trap` construct
exists anywhere) must still cite the artifact that was actually searched —
never empty `evidence`, and never a fabricated line number.
"""

from __future__ import annotations

from nsca_engine.api import assess_device
from nsca_engine.tests.helpers import (
    ASSESSED_AT,
    RICH_CONTROLS_CONFIG,
    WORKED_EXAMPLE_CONFIG,
    build_knowledge_base,
    make_artifact,
)
from nsca_engine.types import ProvenanceSource, Verdict


def _findings_by_id(config):
    kb = build_knowledge_base()
    assessment = assess_device((make_artifact(config),), kb, ASSESSED_AT)
    return {f.control_id: f for f in assessment.findings}


# ---------------------------------------------------------------------------
# default_known absence (NSCA-MGMT-005 / NSCA-MGMT-006 — the exact two
# controls the rehearsal named)
# ---------------------------------------------------------------------------


def test_default_known_absence_fail_has_real_evidence_citation():
    by_id = _findings_by_id(RICH_CONTROLS_CONFIG)

    mgmt_005 = by_id["NSCA-MGMT-005"]
    assert mgmt_005.verdict == Verdict.FAIL
    assert mgmt_005.evidence, "absence-based FAIL must not have empty evidence"
    ev = mgmt_005.evidence[0]
    assert ev.artifact_id == "ART-001"  # the real artifact id make_artifact used
    assert ev.lines == ()  # honest: no fabricated line number for something absent
    assert "mgmt.source_restriction.configured" in ev.excerpt
    assert "platform default" in ev.excerpt

    mgmt_006 = by_id["NSCA-MGMT-006"]
    assert mgmt_006.verdict == Verdict.FAIL
    assert mgmt_006.evidence
    ev6 = mgmt_006.evidence[0]
    assert ev6.artifact_id == "ART-001"
    assert ev6.lines == ()
    assert "mgmt.banner.login_present" in ev6.excerpt


def test_default_known_evidence_artifact_id_is_never_empty_string_or_none():
    """The exact literal defect from the rehearsal report: `artifact: null`
    or `artifact: ""` in the live report's JSON for these findings."""

    by_id = _findings_by_id(RICH_CONTROLS_CONFIG)
    for control_id in ("NSCA-MGMT-005", "NSCA-MGMT-006"):
        for ev in by_id[control_id].evidence:
            assert ev.artifact_id, f"{control_id}: evidence has falsy artifact_id"


# ---------------------------------------------------------------------------
# derived-from-absence (NSCA-LOG-001 — "no central logging configured")
# ---------------------------------------------------------------------------


def test_derived_absence_fail_has_real_evidence_citation():
    """WORKED_EXAMPLE_CONFIG has no `logging host`/`logging trap` line at
    all, so `logging.remote_configured` resolves False via the derived-fact
    absence branch, and NSCA-LOG-001 genuinely FAILs."""

    by_id = _findings_by_id(WORKED_EXAMPLE_CONFIG)
    log_001 = by_id["NSCA-LOG-001"]
    assert log_001.verdict == Verdict.FAIL
    assert log_001.evidence, "absence-derived FAIL must not have empty evidence"
    ev = log_001.evidence[0]
    assert ev.artifact_id == "ART-001"
    assert ev.lines == ()
    assert "logging" in ev.excerpt.lower()


def test_derived_presence_pass_also_gets_real_evidence():
    """Bonus correctness fix alongside the absence case: when
    `logging.remote_configured` is derived from REAL explicit facts (a
    `logging host` line genuinely present), the derived fact's own
    provenance should carry that real citation too, not just the absence
    case — a PASS finding should not regress to empty evidence either."""

    by_id = _findings_by_id(RICH_CONTROLS_CONFIG)
    log_001 = by_id["NSCA-LOG-001"]
    assert log_001.verdict == Verdict.PASS
    assert log_001.evidence
    ev = log_001.evidence[0]
    assert ev.artifact_id == "ART-001"
    assert ev.lines  # a real line number from the `logging host` line this time


# ---------------------------------------------------------------------------
# Collection-typed requires_facts (NSCA-AUTH-001 / `auth.local_users` — the
# rehearsal's own named example): `_resolve_base_or_scoped` never resolves a
# bare collection base path, so evidence construction used to come up empty
# regardless of provenance for any control whose `requires_facts` names a
# collection rather than a scalar/scope-qualified fact.
# ---------------------------------------------------------------------------


def test_collection_typed_control_gets_real_evidence():
    """NSCA-AUTH-001 (`requires_facts: [auth.local_users]`) genuinely FAILs
    against RICH_CONTROLS_CONFIG's admin/priv15/reversible-password user —
    real, explicit per-user facts exist, but the control's requires_facts
    entry is the bare collection path `auth.local_users`, which the
    scalar/scope-qualified resolver alone can never surface as evidence."""

    by_id = _findings_by_id(RICH_CONTROLS_CONFIG)
    auth_001 = by_id["NSCA-AUTH-001"]
    assert auth_001.verdict == Verdict.FAIL
    assert auth_001.evidence, "collection-typed FAIL must not have empty evidence"
    ev = auth_001.evidence[0]
    assert ev.artifact_id == "ART-001"
    assert ev.lines  # the real `username admin ...` line
    assert ev.fact_paths[0].startswith("auth.local_users[0].")


# ---------------------------------------------------------------------------
# General property: every finding whose evidence is non-empty must carry a
# real (non-falsy) artifact_id — the traceability-matrix §9 checklist
# item 11 requirement, checked across the whole rich control pack, not just
# the two named controls.
# ---------------------------------------------------------------------------


def test_no_finding_has_evidence_with_falsy_artifact_id():
    kb = build_knowledge_base()
    assessment = assess_device((make_artifact(RICH_CONTROLS_CONFIG),), kb, ASSESSED_AT)
    offenders = [
        (f.control_id, ev)
        for f in assessment.findings
        for ev in f.evidence
        if not ev.artifact_id
    ]
    assert not offenders, f"findings with evidence but no artifact_id: {offenders}"


def test_fail_findings_backed_by_default_unknown_also_cite_the_artifact():
    """DEFAULT_UNKNOWN facts (no defaults-table entry at all — genuinely
    "we don't know") are now evidence-eligible too (controls/evaluate.py's
    fix), so any finding whose deciding fact lands here still gets an
    honest "no matching construct found" citation rather than being
    silently excluded from evidence construction."""

    kb = build_knowledge_base()
    assessment = assess_device((make_artifact(RICH_CONTROLS_CONFIG),), kb, ASSESSED_AT)
    by_path = {f.path: f for f in assessment.facts}
    default_unknown_paths = {
        p for p, f in by_path.items() if f.provenance.source == ProvenanceSource.DEFAULT_UNKNOWN
    }
    assert default_unknown_paths, "fixture should exercise at least one default_unknown fact"
    for p in default_unknown_paths:
        f = by_path[p]
        assert f.provenance.artifact_id == "ART-001"
        assert f.provenance.excerpt and "no matching construct found" in f.provenance.excerpt
