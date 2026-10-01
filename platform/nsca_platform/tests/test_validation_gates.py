"""Validation gates — TRD-08.3 §4 / V-08.3-001, backend-02 M3.

Each gate is exercised failing individually (V-08.3-001's own procedure:
"Submit rules failing each gate individually... All six rejected.").
"""

from __future__ import annotations

from nsca_platform.learning.validation_gates import (
    check_no_catastrophic_backtracking,
    gate_conflict,
    gate_corpus_scope,
    gate_metamorphic,
    gate_regression,
    gate_self_match,
    gate_type_conformance,
    run_all_gates,
)

TELNET_PATTERN = r"^set\s+telnet\s+disabled=(?P<val>\S+)(?:\s+.*)?$"
TELNET_VALUE_EXPR = "val == 'no'"


def test_gate1_self_match_passes_on_confirmed_examples():
    result = gate_self_match(TELNET_PATTERN, ["set telnet disabled=no port=23"])
    assert result.outcome == "pass"


def test_gate1_self_match_fails_when_missing_a_confirmed_example():
    result = gate_self_match(TELNET_PATTERN, ["set telnet disabled=no port=23", "set telnet disabled=no port=2323extra unrelated garbage that does not match anyway"])
    # second "example" deliberately shaped so it won't match -> must fail
    bad_pattern = r"^set telnet disabled=no$"  # too narrow, no trailing content allowed
    result = gate_self_match(bad_pattern, ["set telnet disabled=no port=23"])
    assert result.outcome == "fail"


def test_gate1_self_match_fails_on_zero_confirmed_examples():
    result = gate_self_match(TELNET_PATTERN, [])
    assert result.outcome == "fail"


def test_gate2_corpus_scope_passes_when_platform_only_matches_itself():
    corpus = {"mikrotik": ["set telnet disabled=no port=23"], "cisco_ios": ["transport input ssh"]}
    result = gate_corpus_scope(TELNET_PATTERN, "mikrotik", corpus)
    assert result.outcome == "pass"


def test_gate2_corpus_scope_hard_fails_on_cross_platform_match():
    """DD-08.3-01 — cross-platform matching is a hard failure, never a warning."""

    broad_pattern = r".*telnet.*"
    corpus = {
        "mikrotik": ["set telnet disabled=no port=23"],
        "cisco_ios": ["transport input telnet ssh"],
    }
    result = gate_corpus_scope(broad_pattern, "mikrotik", corpus)
    assert result.outcome == "fail"


def test_gate2_empty_corpus_degrades_to_warning():
    result = gate_corpus_scope(TELNET_PATTERN, "mikrotik", {})
    assert result.outcome == "warn"


def test_gate3_conflict_passes_with_no_existing_producer():
    result = gate_conflict("mgmt.protocols.telnet.enabled", {"dev1": True}, {})
    assert result.outcome == "pass"


def test_gate3_conflict_fails_on_differing_values():
    existing = {"other_rule@1": {"dev1": False}}
    result = gate_conflict("mgmt.protocols.telnet.enabled", {"dev1": True}, existing)
    assert result.outcome == "fail"


def test_gate3_conflict_warns_on_probable_duplicate():
    existing = {"other_rule@1": {"dev1": True}}
    result = gate_conflict("mgmt.protocols.telnet.enabled", {"dev1": True}, existing)
    assert result.outcome == "warn"


def test_gate4_type_conformance_fails_on_unregistered_fact_path():
    result = gate_type_conformance(TELNET_VALUE_EXPR, "boolean", frozenset({"mgmt.protocols.ssh.enabled"}), "mgmt.protocols.telnet.enabled")
    assert result.outcome == "fail"


def test_gate4_type_conformance_passes_for_boolean_expression():
    result = gate_type_conformance(
        TELNET_VALUE_EXPR, "boolean", frozenset({"mgmt.protocols.telnet.enabled"}), "mgmt.protocols.telnet.enabled"
    )
    assert result.outcome == "pass"


def test_gate5_regression_fails_when_new_pattern_shadows_an_existing_test():
    frozen = [{"input": "set telnet disabled=no port=23", "expect": {"mgmt.protocols.telnet.enabled": True}}]
    result = gate_regression(TELNET_PATTERN, TELNET_VALUE_EXPR, frozen)
    assert result.outcome == "fail"


def test_gate5_regression_passes_with_no_overlap():
    frozen = [{"input": "set ssh disabled=no port=22", "expect": {"mgmt.protocols.ssh.enabled": True}}]
    result = gate_regression(TELNET_PATTERN, TELNET_VALUE_EXPR, frozen)
    assert result.outcome == "pass"


def test_gate6_metamorphic_passes_for_whitespace_robust_pattern():
    result = gate_metamorphic(TELNET_PATTERN, TELNET_VALUE_EXPR, ["set telnet disabled=no port=23"])
    assert result.outcome == "pass"


def test_gate6_metamorphic_fails_for_whitespace_brittle_pattern():
    """DD-08.3-02 — a rule matching only exact whitespace fails at
    synthesis time."""

    brittle_pattern = r"^set telnet disabled=(?P<val>\S+) port=23$"  # single space only, no double-space tolerance
    result = gate_metamorphic(brittle_pattern, TELNET_VALUE_EXPR, ["set telnet disabled=no port=23"])
    assert result.outcome == "fail"


def test_backtracking_check_flags_nested_quantifiers():
    result = check_no_catastrophic_backtracking(r"^(a+)+$")
    assert result.outcome == "fail"


def test_backtracking_check_passes_normal_pattern():
    result = check_no_catastrophic_backtracking(TELNET_PATTERN)
    assert result.outcome == "pass"


def test_run_all_gates_all_pass_for_a_correct_rule():
    report = run_all_gates(
        pattern=TELNET_PATTERN,
        value_expr=TELNET_VALUE_EXPR,
        fact_path="mgmt.protocols.telnet.enabled",
        fact_type="boolean",
        confirmed_examples=["set telnet disabled=no port=23"],
        target_platform="mikrotik",
        corpus={"mikrotik": ["set telnet disabled=no port=23"], "cisco_ios": ["transport input ssh"]},
        existing_producers={},
        new_value_for={"RTR-Pune-02": True},
        registered_fact_paths=frozenset({"mgmt.protocols.telnet.enabled"}),
        frozen_tests=[],
    )
    assert report.all_passed


def test_run_all_gates_reports_the_specific_failing_gate():
    """V-08.3-001: 'Administrator returned to correction with the failing
    gate named.'"""

    report = run_all_gates(
        pattern=TELNET_PATTERN,
        value_expr=TELNET_VALUE_EXPR,
        fact_path="mgmt.protocols.telnet.enabled",
        fact_type="boolean",
        confirmed_examples=["set telnet disabled=no port=23"],
        target_platform="mikrotik",
        corpus={"mikrotik": ["set telnet disabled=no port=23"]},
        existing_producers={"cisco.rule@1": {"RTR-Pune-02": False}},
        new_value_for={"RTR-Pune-02": True},
        registered_fact_paths=frozenset({"mgmt.protocols.telnet.enabled"}),
        frozen_tests=[],
    )
    assert not report.all_passed
    failing = [r.gate for r in report.results if r.outcome == "fail"]
    assert "conflict" in failing
