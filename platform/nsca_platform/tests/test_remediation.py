"""Remediation planner + lockout + dry-run — TRD-07.1, backend-02 M4.

No DB dependency: `planner.plan`/`lockout.check_lockout`/`dry_run.dry_run`
are pure functions over in-memory facts/findings, so these tests run
without Postgres (unlike the report-generation acceptance test, they don't
need the graceful-skip pattern).
"""

from __future__ import annotations

import random

import pytest

from nsca_platform.remediation import dry_run as dryrun_mod
from nsca_platform.remediation import lockout, planner

LIB = planner.load_remediation_library()


def test_track_a_real_loader_still_parses_the_control_pack_with_remediation_content():
    """backend-02 §2.2: "Treat 'can Track A's loader parse what I just
    wrote' as a literal integration test, not an assumption." Sanctioned
    use of `nsca_engine.controls.rulepack_loader` per backend-02 §2.2 (this
    round-trip verification only)."""

    from nsca_engine.controls.rulepack_loader import load_control_pack

    loaded = load_control_pack(planner.DEFAULT_CONTROL_PACK_PATHS[0])
    control_ids = {c.control_id for c in loaded.controls}
    assert {"NSCA-MGMT-002", "NSCA-MGMT-005", "NSCA-AUTH-001", "NSCA-AUTH-002", "NSCA-AUTH-003"} <= control_ids
    # The real loader must still compile every control's actual `assert`
    # expression correctly — remediation content must be invisible to it.
    auth003 = next(c for c in loaded.controls if c.control_id == "NSCA-AUTH-003")
    assert auth003.requires_facts == ("auth.local_users",)

BASE_FACTS = {
    "mgmt.protocols.telnet.enabled": True,
    "mgmt.protocols.http.enabled": True,
    "mgmt.protocols.ssh.enabled": True,
    "auth.local_users": [{"username": "admin", "privilege_level": 15, "reversible": True}],
    "auth.central.configured": False,
    "mgmt.source_restriction.configured": False,
}

ALL_FINDINGS = [
    {"id": "F-000412", "control": "NSCA-MGMT-002", "verdict": "FAIL"},
    {"id": "F-000603", "control": "NSCA-AUTH-001", "verdict": "FAIL"},
    {"id": "F-000604", "control": "NSCA-AUTH-002", "verdict": "FAIL"},
    {"id": "F-000518", "control": "NSCA-MGMT-005", "verdict": "FAIL"},
    {"id": "F-000700", "control": "NSCA-AUTH-003", "verdict": "PASS"},
]


# ---------------------------------------------------------------------------
# V-07.1-001 — version-specific selection, refusal for unauthored content
# ---------------------------------------------------------------------------


def test_version_specific_selection_differs_by_platform():
    findings = [{"id": "F1", "control": "NSCA-MGMT-002", "verdict": "FAIL"}]
    legacy = planner.plan(findings, device_id="D1", platform="cisco_ios", os_version="12.4", facts={}, library=LIB)
    modern = planner.plan(findings, device_id="D2", platform="cisco_iosxe", os_version="16.12.04", facts={}, library=LIB)

    assert [s.command for s in legacy.steps] != [s.command for s in modern.steps]
    # IOS-XE band adds `ip http secure-server` (TRD-07.1 §3.2's own example).
    assert "ip http secure-server" in [s.command for s in modern.steps]
    assert "ip http secure-server" not in [s.command for s in legacy.steps]
    assert not legacy.unavailable and not modern.unavailable


def test_refusal_for_platform_with_no_authored_content():
    findings = [{"id": "F1", "control": "NSCA-MGMT-002", "verdict": "FAIL"}]
    p = planner.plan(findings, device_id="D3", platform="cisco_nxos", os_version="9.3", facts={}, library=LIB)

    assert p.steps == ()
    assert len(p.unavailable) == 1
    assert p.unavailable[0].control_id == "NSCA-MGMT-002"
    assert "manually" in p.unavailable[0].reason


def test_refusal_for_version_outside_every_range():
    findings = [{"id": "F1", "control": "NSCA-MGMT-002", "verdict": "FAIL"}]
    # cisco_ios band is ">=12.0,<15.0" — 9.1 (pre-12) falls outside it too.
    p = planner.plan(findings, device_id="D4", platform="cisco_ios", os_version="9.1", facts={}, library=LIB)
    assert p.steps == ()
    assert len(p.unavailable) == 1


# ---------------------------------------------------------------------------
# V-07.1-002 / V-07.1-011 — dependency ordering, determinism under shuffle
# ---------------------------------------------------------------------------


def test_dependency_ordering_is_topologically_correct_and_deterministic():
    orders = []
    for _ in range(10):
        shuffled = ALL_FINDINGS[:]
        random.shuffle(shuffled)
        p = planner.plan(
            shuffled, device_id="CORE-SW-01", platform="cisco_iosxe", os_version="16.12.04",
            facts=BASE_FACTS, library=LIB, operator_source="10.20.5.44",
        )
        orders.append(tuple((s.control_id, s.command) for s in p.steps))

    assert len(set(orders)) == 1, "plan step order must be independent of input finding order (D6/D7)"

    p = planner.plan(
        ALL_FINDINGS, device_id="CORE-SW-01", platform="cisco_iosxe", os_version="16.12.04",
        facts=BASE_FACTS, library=LIB, operator_source="10.20.5.44",
    )
    position = {s.id: i for i, s in enumerate(p.steps)}
    for s in p.steps:
        for dep in s.depends_on:
            assert position[dep] < position[s.id]

    # Cross-finding dependency: every NSCA-AUTH-002 step precedes every
    # NSCA-AUTH-001 step (after_control).
    auth002_positions = [position[s.id] for s in p.steps if s.control_id == "NSCA-AUTH-002"]
    auth001_positions = [position[s.id] for s in p.steps if s.control_id == "NSCA-AUTH-001"]
    assert max(auth002_positions) < min(auth001_positions)


def test_cycle_is_rejected():
    steps_by_node = {
        ("X", 1): planner.RawStepDoc(
            control_id="X", local_id=1, cmd="a", impact="safe", reason=None,
            depends_on=(2,), after_control=None, requires_verified=False,
            checkpoint=None, rollback=None, rollback_from_prior_fact=None, fact_effects=(),
        ),
        ("X", 2): planner.RawStepDoc(
            control_id="X", local_id=2, cmd="b", impact="safe", reason=None,
            depends_on=(1,), after_control=None, requires_verified=False,
            checkpoint=None, rollback=None, rollback_from_prior_fact=None, fact_effects=(),
        ),
    }
    edges = {("X", 1): {("X", 2)}, ("X", 2): {("X", 1)}}
    with pytest.raises(planner.RemediationContentError):
        planner._topological_order(list(steps_by_node.keys()), edges)


# ---------------------------------------------------------------------------
# V-07.1-005 — verification checkpoint precedes an irreversible step
# ---------------------------------------------------------------------------


def test_checkpoint_precedes_irreversible_step():
    p = planner.plan(
        ALL_FINDINGS, device_id="CORE-SW-01", platform="cisco_iosxe", os_version="16.12.04",
        facts=BASE_FACTS, library=LIB, operator_source="10.20.5.44",
    )
    assert len(p.checkpoints) == 1
    cp = p.checkpoints[0]
    assert "TACACS" in cp.instruction
    remove_account_step = next(
        s for s in p.steps if s.control_id == "NSCA-AUTH-001" and s.requires_verified
    )
    assert cp.after_step is not None
    assert cp.after_step < remove_account_step.id


# ---------------------------------------------------------------------------
# V-07.1-010 — no remediation for UNKNOWN verdicts
# ---------------------------------------------------------------------------


def test_no_remediation_for_unknown_verdict():
    findings = [{"id": "F1", "control": "NSCA-MGMT-002", "verdict": "UNKNOWN"}]
    p = planner.plan(findings, device_id="D5", platform="cisco_iosxe", os_version="16.12.04", facts={}, library=LIB)
    assert p.steps == ()
    assert p.unavailable == ()  # not even reported unavailable — simply not planned


# ---------------------------------------------------------------------------
# Conflict detection (TRD-07.1 §5)
# ---------------------------------------------------------------------------


def test_conflicting_fact_effects_are_reported_and_block_both_steps():
    steps_by_node = {
        ("A", 1): planner.RawStepDoc(
            control_id="A", local_id=1, cmd="set true", impact="safe", reason=None,
            depends_on=(), after_control=None, requires_verified=False, checkpoint=None,
            rollback=None, rollback_from_prior_fact=None,
            fact_effects=(planner.FactEffect(path="x.y", op="set", value=True),),
        ),
        ("B", 1): planner.RawStepDoc(
            control_id="B", local_id=1, cmd="set false", impact="safe", reason=None,
            depends_on=(), after_control=None, requires_verified=False, checkpoint=None,
            rollback=None, rollback_from_prior_fact=None,
            fact_effects=(planner.FactEffect(path="x.y", op="set", value=False),),
        ),
    }
    conflicts = planner._detect_conflicts(steps_by_node)
    assert len(conflicts) == 1
    assert conflicts[0].fact_path == "x.y"
    assert {conflicts[0].control_a, conflicts[0].control_b} == {"A", "B"}


# ---------------------------------------------------------------------------
# V-07.1-008 — rollback restores observed prior state / marked incomplete
# ---------------------------------------------------------------------------


def test_rollback_complete_when_prior_state_known():
    p = planner.plan(
        [{"id": "F1", "control": "NSCA-MGMT-002", "verdict": "FAIL"}],
        device_id="D6", platform="cisco_iosxe", os_version="16.12.04",
        facts={"mgmt.protocols.telnet.enabled": True}, library=LIB,
    )
    telnet_step = next(s for s in p.steps if s.command == "transport input ssh")
    assert telnet_step.rollback == "transport input telnet ssh"
    assert telnet_step.rollback_incomplete is False


def test_rollback_incomplete_when_prior_state_unknown():
    p = planner.plan(
        [{"id": "F1", "control": "NSCA-MGMT-002", "verdict": "FAIL"}],
        device_id="D7", platform="cisco_iosxe", os_version="16.12.04",
        facts={},  # mgmt.protocols.telnet.enabled not present -> unknown
        library=LIB,
    )
    telnet_step = next(s for s in p.steps if s.command == "transport input ssh")
    assert telnet_step.rollback_incomplete is True
    assert "unknown" in telnet_step.rollback.lower()


def test_rollback_incomplete_for_prior_fact_marker_when_unknown():
    p = planner.plan(
        # NSCA-AUTH-001 depends on NSCA-AUTH-002 (after_control) — include
        # it as FAIL too so the chain isn't reported unavailable instead.
        [
            {"id": "F1", "control": "NSCA-AUTH-001", "verdict": "FAIL"},
            {"id": "F2", "control": "NSCA-AUTH-002", "verdict": "FAIL"},
        ],
        device_id="D8", platform="cisco_iosxe", os_version="16.12.04",
        facts={},  # auth.local_users unknown
        library=LIB,
    )
    remove_step = next(s for s in p.steps if "no username admin" in s.command)
    assert remove_step.rollback_incomplete is True


# ---------------------------------------------------------------------------
# Lockout — V-07.1-003, V-07.1-004, and the explicit "refuse rather than
# approve" requirement (a wrong PERMITTED is worse than no check)
# ---------------------------------------------------------------------------


def test_lockout_indeterminate_when_operator_source_missing():
    p = planner.plan(
        [{"id": "F1", "control": "NSCA-MGMT-005", "verdict": "FAIL"}],
        device_id="D9", platform="cisco_iosxe", os_version="16.12.04", facts=BASE_FACTS, library=LIB,
    )
    modelled = dryrun_mod.apply_remediation_to_facts(BASE_FACTS, p)
    result = lockout.check_lockout(p, modelled, operator_source=None)
    assert result.result == lockout.RESULT_INDETERMINATE
    assert result.result != lockout.RESULT_PERMITTED


def test_lockout_detects_source_denied():
    p = planner.plan(
        [{"id": "F1", "control": "NSCA-MGMT-005", "verdict": "FAIL"}],
        device_id="D10", platform="cisco_iosxe", os_version="16.12.04", facts=BASE_FACTS, library=LIB,
    )
    modelled = dryrun_mod.apply_remediation_to_facts(BASE_FACTS, p)
    result = lockout.check_lockout(p, modelled, operator_source="192.168.44.10")
    assert result.result == lockout.RESULT_LOCKOUT
    assert result.blocked_step_ids

    blocked_plan = lockout.apply_lockout_blocking(p, result)
    assert any(s.blocked for s in blocked_plan.steps)
    for s in blocked_plan.steps:
        if s.id in result.blocked_step_ids:
            assert s.blocked is True
            assert s.blocked_reason is not None


def test_lockout_permitted_when_operator_included():
    p = planner.plan(
        [{"id": "F1", "control": "NSCA-MGMT-005", "verdict": "FAIL"}],
        device_id="D11", platform="cisco_iosxe", os_version="16.12.04", facts=BASE_FACTS, library=LIB,
    )
    modelled = dryrun_mod.apply_remediation_to_facts(BASE_FACTS, p)
    result = lockout.check_lockout(p, modelled, operator_source="10.20.5.44")
    assert result.result == lockout.RESULT_PERMITTED


def test_lockout_detects_all_transports_disabled():
    facts = dict(BASE_FACTS)
    plan_obj = planner.RemediationPlan(
        device_id="D12", platform="cisco_iosxe", os_version="16.12.04",
        steps=(
            planner.RemediationStep(
                id=1, control_id="X", command="no transport ssh/telnet/http/https", impact="lockout_risk",
                reason=None, depends_on=(), requires_verified=False, rollback=None,
                rollback_incomplete=True, addresses_findings=(), fact_effects=(
                    planner.FactEffect(path="mgmt.protocols.ssh.enabled", value=False),
                    planner.FactEffect(path="mgmt.protocols.telnet.enabled", value=False),
                    planner.FactEffect(path="mgmt.protocols.http.enabled", value=False),
                    planner.FactEffect(path="mgmt.protocols.https.enabled", value=False),
                ),
            ),
        ),
        unavailable=(), checkpoints=(), conflicts=(),
    )
    modelled = dryrun_mod.apply_remediation_to_facts(facts, plan_obj)
    result = lockout.check_lockout(plan_obj, modelled, operator_source="10.20.5.44")
    assert result.result == lockout.RESULT_LOCKOUT
    assert "all_transports_disabled" in result.modes_detected


def test_lockout_method_is_flagged_as_approximation_not_real_graph():
    """The explicit task requirement: the lockout check must be flagged as
    a local approximation when it cannot get a real graph answer, not
    silently presented as equivalent to a real reachability query."""

    p = planner.plan(
        [{"id": "F1", "control": "NSCA-MGMT-005", "verdict": "FAIL"}],
        device_id="D13", platform="cisco_iosxe", os_version="16.12.04", facts=BASE_FACTS, library=LIB,
    )
    modelled = dryrun_mod.apply_remediation_to_facts(BASE_FACTS, p)
    result = lockout.check_lockout(p, modelled, operator_source="10.20.5.44")
    assert result.method == lockout.METHOD_LOCAL_APPROXIMATION
    assert "approximation" in result.reason.lower()


_EDGE_FW_FIXTURE = (
    __import__("pathlib").Path(__file__).resolve().parents[3]
    / "engine" / "nsca_engine" / "tests" / "fixtures" / "graph_estate" / "edge_fw_01.cfg"
)


@pytest.mark.skipif(
    not _EDGE_FW_FIXTURE.exists(),
    reason=f"engine corpus fixture not found at {_EDGE_FW_FIXTURE} in this checkout layout",
)
def test_lockout_real_engine_reachability_permitted_and_lockout() -> None:
    """M5: `check_lockout` calls the real `nsca_engine.api.query_reachability`
    when given a real cached `Graph` (`campaign_public_id`) and a concrete
    `device_management_addr` — no production call site can supply the
    latter yet (see `remediation/lockout.py` module docstring: no
    management-address fact is modelled), so this test constructs both
    explicitly, the same way `services/dispute.py`'s real-reachability
    tests do, reusing the engine's own `edge_fw_01.cfg` graph-estate
    fixture: its ACL permits tcp/22 to 10.0.0.1 from anywhere
    (Trusted-Admins -> Partners -> 0.0.0.0/0) and denies everything else by
    default — so 10.0.0.1 is a real PERMITTED case and an address the ACL
    doesn't name (10.0.0.99) is a real LOCKOUT case.
    """

    from datetime import datetime, timezone

    from nsca_engine.api import RawArtifact
    from nsca_engine.api import assess_campaign as engine_assess_campaign
    from nsca_engine.api import assess_device as engine_assess_device
    from nsca_platform.knowledge_base_loader import get_knowledge_base
    from nsca_platform.services import graph_cache

    kb = get_knowledge_base()
    content = _EDGE_FW_FIXTURE.read_bytes()
    artifact = RawArtifact(
        id="ART-EDGE01", filename="edge_fw_01.cfg", content=content,
        artifact_type_hint=None, received_from="test",
    )
    device_assessment = engine_assess_device((artifact,), kb, datetime(2026, 9, 1, tzinfo=timezone.utc))
    campaign_assessment = engine_assess_campaign((device_assessment,), kb)
    campaign_public_id = "CMP-LOCKOUT-REAL-TEST"
    graph_cache.set_graph(campaign_public_id, campaign_assessment.graph)
    try:
        p = planner.plan(
            [{"id": "F1", "control": "NSCA-MGMT-005", "verdict": "FAIL"}],
            device_id="EDGE-FW-01", platform="cisco_ios", os_version="15.2", facts=BASE_FACTS, library=LIB,
        )
        modelled = dryrun_mod.apply_remediation_to_facts(BASE_FACTS, p)

        permitted = lockout.check_lockout(
            p, modelled, operator_source="203.0.113.5",
            campaign_public_id=campaign_public_id, device_management_addr="10.0.0.1",
        )
        assert permitted.result == lockout.RESULT_PERMITTED
        assert permitted.method == lockout.METHOD_ENGINE

        locked_out = lockout.check_lockout(
            p, modelled, operator_source="203.0.113.5",
            campaign_public_id=campaign_public_id, device_management_addr="10.0.0.99",
        )
        assert locked_out.result == lockout.RESULT_LOCKOUT
        assert locked_out.method == lockout.METHOD_ENGINE

        # Omitting either real ingredient must fall back to the local
        # approximation, never fabricate a real-looking answer.
        no_graph = lockout.check_lockout(
            p, modelled, operator_source="203.0.113.5",
            campaign_public_id="CMP-NEVER-ASSESSED", device_management_addr="10.0.0.1",
        )
        assert no_graph.method == lockout.METHOD_LOCAL_APPROXIMATION
    finally:
        graph_cache.clear()


# ---------------------------------------------------------------------------
# Dry run — V-07.1-006 (newly failing), V-07.1-007 (coverage unchanged),
# V-07.1-012 (fidelity limitation stated)
# ---------------------------------------------------------------------------


def test_dry_run_detects_newly_failing_and_resolves():
    p = planner.plan(
        ALL_FINDINGS, device_id="CORE-SW-01", platform="cisco_iosxe", os_version="16.12.04",
        facts=BASE_FACTS, library=LIB, operator_source="10.20.5.44",
    )
    result = dryrun_mod.dry_run(ALL_FINDINGS, BASE_FACTS, p, library=LIB)

    assert "NSCA-MGMT-002" in result.resolved
    assert "NSCA-AUTH-001" in result.resolved
    assert len(result.newly_failing) == 1
    assert result.newly_failing[0].control_id == "NSCA-AUTH-003"
    assert result.after_compliance > result.before_compliance
    assert result.coverage_unchanged is True
    assert "not re-run" in result.fidelity_note or "does not re-run" in result.fidelity_note


def test_dry_run_lists_unmodelled_controls_without_a_check():
    findings = ALL_FINDINGS + [{"id": "F-999", "control": "NSCA-CRYPTO-002", "verdict": "FAIL"}]
    p = planner.plan(
        ALL_FINDINGS, device_id="CORE-SW-01", platform="cisco_iosxe", os_version="16.12.04",
        facts=BASE_FACTS, library=LIB, operator_source="10.20.5.44",
    )
    result = dryrun_mod.dry_run(findings, BASE_FACTS, p, library=LIB)
    assert "NSCA-CRYPTO-002" in result.unmodelled


def test_dry_run_excludes_blocked_steps_from_the_model():
    p = planner.plan(
        [{"id": "F1", "control": "NSCA-MGMT-005", "verdict": "FAIL"}],
        device_id="D14", platform="cisco_iosxe", os_version="16.12.04", facts=BASE_FACTS, library=LIB,
    )
    modelled_unblocked = dryrun_mod.apply_remediation_to_facts(BASE_FACTS, p)
    lock = lockout.check_lockout(p, modelled_unblocked, operator_source="192.168.44.10")
    assert lock.result == lockout.RESULT_LOCKOUT
    blocked_plan = lockout.apply_lockout_blocking(p, lock)

    modelled_after_block = dryrun_mod.apply_remediation_to_facts(BASE_FACTS, blocked_plan)
    # The ACL step is blocked, so mgmt.source_restriction.configured must
    # NOT have been modelled as changed.
    assert modelled_after_block["mgmt.source_restriction.configured"] is False
