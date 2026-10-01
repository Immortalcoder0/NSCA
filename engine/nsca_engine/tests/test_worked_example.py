"""M1 acceptance test (backend-01 §6): 05-security-baseline-model.md §9's
worked example, reproduced end to end through `assess_device` — fingerprint
-> indentation-paradigm parse -> extract -> evaluate.

Interpretation note (flagged, not silently resolved): the doc's §9 fact list
illustrates 11 facts for a 5-line excerpt; a real engine evaluating a >=20
control pack legitimately resolves additional `default_unknown`/
`default_known` facts for other controls' `requires_facts` that the doc's
tiny excerpt does not mention at all. This test therefore asserts the
doc's 11 facts are each present with the documented value/provenance
(a subset match), not that the full fact set equals exactly those 11 — the
latter would be false for any engine that evaluates more than the doc's one
illustrative control.
"""

from __future__ import annotations

from nsca_engine.api import assess_device
from nsca_engine.tests.helpers import (
    ASSESSED_AT,
    WORKED_EXAMPLE_CONFIG,
    build_knowledge_base,
    make_artifact,
)
from nsca_engine.types import ProvenanceSource


def _facts_by_path(assessment):
    return {f.path: f for f in assessment.facts}


def test_worked_example_reproduces_exact_fact_list():
    kb = build_knowledge_base()
    artifact = make_artifact(WORKED_EXAMPLE_CONFIG)
    assessment = assess_device((artifact,), kb, ASSESSED_AT)
    facts = _facts_by_path(assessment)

    # auth.local_users[0].*
    f = facts["auth.local_users[0].name"]
    assert f.value == "admin"
    assert f.provenance.source == ProvenanceSource.EXPLICIT
    assert f.provenance.lines == (6,)
    assert f.provenance.extractor == "cisco_ios.username@v4"

    f = facts["auth.local_users[0].privilege_level"]
    assert f.value == 15
    assert f.provenance.source == ProvenanceSource.EXPLICIT
    assert f.provenance.lines == (6,)

    f = facts["auth.local_users[0].storage_type"]
    assert f.value == "reversible"
    assert f.provenance.source == ProvenanceSource.EXPLICIT
    assert f.provenance.lines == (6,)

    f = facts["auth.local_users[0].reversible"]
    assert f.value is True
    assert f.provenance.source == ProvenanceSource.DERIVED
    assert f.provenance.depends_on == ("auth.local_users[0].storage_type",)

    # mgmt.protocols.{telnet,ssh}.enabled — single VTY range, so unqualified
    # per this engine's design choice (see runtime.py docstring): a lone
    # `line vty` declaration has no aggregation ambiguity to disambiguate,
    # matching the doc's own unqualified path.
    f = facts["mgmt.protocols.telnet.enabled"]
    assert f.value is True
    assert f.provenance.source == ProvenanceSource.EXPLICIT
    assert f.provenance.lines == (21,)
    assert f.provenance.extractor == "cisco_ios.vty.transport_input@v7"

    f = facts["mgmt.protocols.ssh.enabled"]
    assert f.value is True
    assert f.provenance.source == ProvenanceSource.EXPLICIT
    assert f.provenance.lines == (21,)

    f = facts["mgmt.session.idle_timeout_sec"]
    assert f.value == 0
    assert f.provenance.source == ProvenanceSource.EXPLICIT
    assert f.provenance.lines == (22,)
    assert f.provenance.extractor == "cisco_ios.vty.exec_timeout@v3"

    f = facts["snmp.communities[0].name"]
    assert f.value == "public"
    assert f.provenance.source == ProvenanceSource.EXPLICIT
    assert f.provenance.lines == (24,)
    assert f.provenance.extractor == "cisco_ios.snmp.community@v2"

    f = facts["snmp.communities[0].is_default"]
    assert f.value is True
    assert f.provenance.source == ProvenanceSource.DERIVED

    # mgmt.source_restriction.configured — default_known, cited, per doc.
    f = facts["mgmt.source_restriction.configured"]
    assert f.value is False
    assert f.provenance.source == ProvenanceSource.DEFAULT_KNOWN
    assert f.provenance.default_source is not None

    # crypto.ssh.ciphers — default_unknown: THE flagship case. No entry in
    # the rulepack's defaults table -> forces UNKNOWN downstream, never a
    # silent pass (SBM §9's whole point).
    f = facts["crypto.ssh.ciphers"]
    assert f.value is None
    assert f.provenance.source == ProvenanceSource.DEFAULT_UNKNOWN


def test_crypto_ssh_ciphers_default_unknown_forces_unknown_verdict():
    """The exact consequence the worked example calls out: every
    cipher-suite control returns UNKNOWN rather than silently passing."""

    kb = build_knowledge_base()
    artifact = make_artifact(WORKED_EXAMPLE_CONFIG)
    assessment = assess_device((artifact,), kb, ASSESSED_AT)
    finding = next(f for f in assessment.findings if f.control_id == "NSCA-CRYPTO-001")
    from nsca_engine.types import Verdict

    assert finding.verdict == Verdict.UNKNOWN
    assert finding.unknown_reason is not None
