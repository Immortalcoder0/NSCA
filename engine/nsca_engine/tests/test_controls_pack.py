"""M1 acceptance test (backend-01 §6): >=20 controls from the native control
pack evaluate correctly across all four verdicts (PASS/FAIL/UNKNOWN/
NOT_APPLICABLE) against a Cisco IOS device's facts.
"""

from __future__ import annotations

from nsca_engine.api import assess_device
from nsca_engine.tests.helpers import (
    ASSESSED_AT,
    RICH_CONTROLS_CONFIG,
    build_knowledge_base,
    make_artifact,
)
from nsca_engine.types import Verdict


def _assess():
    kb = build_knowledge_base()
    artifact = make_artifact(RICH_CONTROLS_CONFIG)
    return assess_device((artifact,), kb, ASSESSED_AT), kb


def test_control_pack_has_at_least_twenty_controls():
    _, kb = _assess()
    loaded = kb.control_packs[0].loaded
    assert len(loaded.controls) >= 20


def test_all_four_verdicts_are_reachable():
    assessment, _ = _assess()
    verdicts = {f.verdict for f in assessment.findings}
    assert verdicts == {Verdict.PASS, Verdict.FAIL, Verdict.UNKNOWN, Verdict.NOT_APPLICABLE}


def test_verdicts_match_expected_per_control():
    """Pinned expected verdict per control_id against RICH_CONTROLS_CONFIG —
    documents *why* each control lands where it does (see helpers.py /
    the M1 report for the full reasoning)."""

    assessment, _ = _assess()
    by_id = {f.control_id: f.verdict for f in assessment.findings}

    expected = {
        "NSCA-MGMT-001": Verdict.PASS,       # ssh enabled, explicit
        "NSCA-MGMT-002": Verdict.FAIL,       # telnet permitted
        # NSCA-MGMT-003 requires both http.enabled (explicit false) and
        # https.enabled (default_unknown). Kleene alone would resolve this
        # PASS ("false or unknown" only needs the false side settled — TRD-
        # 05.1 DD-05.1-01), but backend-01 §5.4's structural requires_facts
        # pre-check fires unconditionally on ANY unknown required fact,
        # before the expression evaluator runs at all — so this resolves
        # UNKNOWN instead. This is the exact TRD-05.1/05.2-vs-backend-01
        # tension documented in controls/evaluate.py's module docstring.
        "NSCA-MGMT-003": Verdict.UNKNOWN,
        "NSCA-MGMT-004": Verdict.FAIL,       # idle timeout 0 (never expires)
        "NSCA-MGMT-005": Verdict.FAIL,       # no source restriction (default_known false)
        "NSCA-MGMT-006": Verdict.FAIL,       # no login banner (default_known false)
        "NSCA-MGMT-007": Verdict.PASS,       # ssh version 2 explicit
        "NSCA-MGMT-008": Verdict.UNKNOWN,    # max_auth_tries never extracted
        "NSCA-MGMT-009": Verdict.UNKNOWN,    # local_fallback never extracted
        "NSCA-MGMT-010": Verdict.NOT_APPLICABLE,  # panos-only control
        "NSCA-AUTH-001": Verdict.FAIL,       # admin priv15 + reversible type-7 password
        "NSCA-AUTH-002": Verdict.PASS,       # aaa central auth configured
        "NSCA-SNMP-001": Verdict.FAIL,       # community "public" is default
        "NSCA-SNMP-002": Verdict.UNKNOWN,    # snmp.versions never extracted
        "NSCA-SNMP-003": Verdict.UNKNOWN,    # write_access_present never extracted
        "NSCA-LOG-001": Verdict.PASS,        # logging host configured
        "NSCA-LOG-002": Verdict.PASS,        # timestamps enabled
        "NSCA-LOG-003": Verdict.UNKNOWN,     # admin_commands_logged never extracted
        "NSCA-TIME-001": Verdict.PASS,       # ntp server configured
        "NSCA-TIME-002": Verdict.UNKNOWN,    # ntp authentication never extracted
        "NSCA-CRYPTO-001": Verdict.UNKNOWN,  # crypto.ssh.ciphers default_unknown
        "NSCA-CRYPTO-002": Verdict.UNKNOWN,  # fips_mode never extracted
    }
    assert len(expected) >= 20

    mismatches = {
        cid: (by_id.get(cid), want) for cid, want in expected.items() if by_id.get(cid) != want
    }
    assert not mismatches, f"verdict mismatches: {mismatches}"


def test_pass_quality_and_unknown_reason_are_populated():
    assessment, _ = _assess()
    for finding in assessment.findings:
        if finding.verdict == Verdict.PASS:
            assert finding.pass_quality is not None
        if finding.verdict == Verdict.UNKNOWN:
            assert finding.unknown_reason is not None
