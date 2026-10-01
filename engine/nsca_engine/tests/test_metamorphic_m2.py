"""Metamorphic tests for the five M2 paradigms + cloud JSON (TRD-11.2,
backend-01 M2 §6 "metamorphic tests pass on all of them"). Two mutation
families per paradigm, picked from TRD-11.2 §4's catalogue:

  - **Lexical: whitespace variation** (§4.1) — every paradigm. Trailing
    spaces and extra blank lines must not change a single extracted fact.
  - **Structural: reordering** (§4.2) — one per paradigm, applied only to
    an order-*insignificant* construct (DD-11.2-01: reordering an
    order-significant construct like `filter.rules[]` would legitimately
    change the facts, so the cloud-JSON case reorders top-level object keys
    instead of the rule array — the edge case TRD-02.1 §5's table calls out
    explicitly: "JSON policy with unordered keys" is not order-significant).

Mutations are applied on top of each platform's real fixture file (same
content the M2 smoke test in `test_assess_device_m2.py` already proves
reaches a KNOWN fingerprint outcome) rather than an ad hoc snippet, so the
fingerprint's confidence/margin thresholds (DD-01.2-02) are not accidentally
exercised by an under-signalled test config — the same reasoning M1's own
`RICH_CONTROLS_CONFIG`-based metamorphic tests already follow.

Relation asserted throughout is **identity** over (fact path, value,
provenance source) — the same relation `test_metamorphic.py` (M1) asserts,
deliberately excluding line numbers, which a mutation is expected to shift.
"""

from __future__ import annotations

from nsca_engine.api import assess_device
from nsca_engine.tests.helpers import (
    ASSESSED_AT,
    M2_FIXTURES,
    build_knowledge_base_m2,
    make_artifact,
)

_KB = build_knowledge_base_m2()


def _fact_signature(assessment):
    return sorted(
        (f.path, repr(f.value), f.provenance.source.value) for f in assessment.facts
    )


def _verdict_signature(assessment):
    return sorted((f.control_id, f.verdict.value) for f in assessment.findings)


def _assert_identical(original_text: str, mutated_text: str) -> None:
    original = assess_device((make_artifact(original_text, artifact_id="ART-ORIG"),), _KB, ASSESSED_AT)
    mutant = assess_device((make_artifact(mutated_text, artifact_id="ART-MUT"),), _KB, ASSESSED_AT)
    assert _fact_signature(original) == _fact_signature(mutant)
    assert _verdict_signature(original) == _verdict_signature(mutant)


def _swap_lines(text: str, a: str, b: str) -> str:
    """Swap two whole physical lines (each must appear exactly once)."""

    lines = text.split("\n")
    ia, ib = lines.index(a), lines.index(b)
    lines[ia], lines[ib] = lines[ib], lines[ia]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# flat_path (Juniper set-format)
# ---------------------------------------------------------------------------

_JSET_BASE = M2_FIXTURES["juniper_junos_set"].read_text(encoding="utf-8")


def test_flat_path_whitespace_alteration_preserves_facts():
    mutated = _JSET_BASE.replace("\n", "   \n")
    _assert_identical(_JSET_BASE, mutated)


def test_flat_path_statement_reordering_preserves_facts():
    reordered = _swap_lines(
        _JSET_BASE,
        "set system services ssh protocol-version v2",
        "set system services ssh root-login deny",
    )
    _assert_identical(_JSET_BASE, reordered)


# ---------------------------------------------------------------------------
# brace (Juniper curly-format)
# ---------------------------------------------------------------------------

_JBRACE_BASE = M2_FIXTURES["juniper_junos_curly"].read_text(encoding="utf-8")


def test_brace_whitespace_alteration_preserves_facts():
    mutated = _JBRACE_BASE.replace("\n", "   \n")
    _assert_identical(_JBRACE_BASE, mutated)


def test_brace_sibling_statement_reordering_preserves_facts():
    reordered = _swap_lines(
        _JBRACE_BASE, "            protocol-version v2;", "            root-login deny;",
    )
    _assert_identical(_JBRACE_BASE, reordered)


# ---------------------------------------------------------------------------
# block_keyword (FortiOS)
# ---------------------------------------------------------------------------

_FORTIOS_BASE = M2_FIXTURES["fortios"].read_text(encoding="utf-8")


def test_block_keyword_whitespace_alteration_preserves_facts():
    mutated = _FORTIOS_BASE.replace("\n", "   \n")
    _assert_identical(_FORTIOS_BASE, mutated)


def test_block_keyword_independent_block_reordering_preserves_facts():
    """Swap the (independent, order-insignificant) `firewall policy` and
    `log syslogd setting` top-level config blocks."""

    marker = "config log syslogd setting"
    idx = _FORTIOS_BASE.index(marker)
    head, tail = _FORTIOS_BASE[:idx], _FORTIOS_BASE[idx:]
    fw_marker = "config firewall policy"
    fw_idx = head.index(fw_marker)
    preamble, fw_block = head[:fw_idx], head[fw_idx:]
    reordered = preamble + tail + fw_block
    _assert_identical(_FORTIOS_BASE, reordered)


# ---------------------------------------------------------------------------
# xml (PAN-OS)
# ---------------------------------------------------------------------------

_PANOS_BASE = M2_FIXTURES["panos"].read_text(encoding="utf-8")


def test_xml_whitespace_alteration_preserves_facts():
    mutated = _PANOS_BASE.replace("\n", "   \n")
    _assert_identical(_PANOS_BASE, mutated)


def test_xml_sibling_element_reordering_preserves_facts():
    reordered = _swap_lines(
        _PANOS_BASE, '    <telnet enabled="no"/>', '    <https enabled="yes"/>',
    )
    _assert_identical(_PANOS_BASE, reordered)


# ---------------------------------------------------------------------------
# path_header (MikroTik RouterOS)
# ---------------------------------------------------------------------------

_ROS_BASE = M2_FIXTURES["routeros"].read_text(encoding="utf-8")


def test_path_header_whitespace_alteration_preserves_facts():
    mutated = _ROS_BASE.replace("\n", "   \n")
    _assert_identical(_ROS_BASE, mutated)


def test_path_header_statement_reordering_preserves_facts():
    reordered = _swap_lines(
        _ROS_BASE, "set telnet disabled=yes port=23", "set ssh disabled=no port=22",
    )
    _assert_identical(_ROS_BASE, reordered)


# ---------------------------------------------------------------------------
# cloud_json (structured cloud policy JSON)
# ---------------------------------------------------------------------------

_CLOUD_BASE = M2_FIXTURES["cloud_generic_fw"].read_text(encoding="utf-8")


def test_cloud_json_whitespace_alteration_preserves_facts():
    mutated = _CLOUD_BASE.replace("\n", "   \n")
    _assert_identical(_CLOUD_BASE, mutated)


def test_cloud_json_object_key_reordering_preserves_facts():
    """Move the `logging` block ahead of `hostname`/`management` — a
    top-level object-key reorder. Order-*insignificant* per TRD-02.1 §5's
    edge case table; contrast with `rules[]`, which is order-significant
    (DD-11.2-01) and deliberately not reordered anywhere in this file."""

    logging_block = '  "logging": {\n    "remote_enabled": true\n  },\n'
    assert logging_block in _CLOUD_BASE
    without = _CLOUD_BASE.replace(logging_block, "")
    reordered = without.replace("{\n", "{\n" + logging_block, 1)
    _assert_identical(_CLOUD_BASE, reordered)
