"""M2 end-to-end smoke tests (backend-01 §6 M2 "done" criterion): for every
new platform, `assess_device` runs fingerprint -> parse -> extract ->
evaluate without raising, against a real fixture in the corresponding
structural paradigm — proving the pipe does not break for a non-Cisco
platform, per the M2 task brief ("doesn't need to be rich, just prove the
pipe doesn't break").

This does **not** claim corpus coverage (TRD-00 §8.2's 200-real-configuration
minimum is explicitly out of reach for this milestone — flagged in the M2
report, not silently skipped); it is a fixture-driven correctness+wiring
proof, one per platform/paradigm.
"""

from __future__ import annotations

import pytest

from nsca_engine.api import assess_device
from nsca_engine.tests.helpers import (
    ASSESSED_AT,
    M2_FIXTURES,
    build_knowledge_base_m2,
    make_artifact,
)
from nsca_engine.types import ProvenanceSource, Verdict

_KB = build_knowledge_base_m2()


@pytest.mark.parametrize("platform", sorted(M2_FIXTURES))
def test_assess_device_runs_end_to_end_for_every_m2_platform(platform):
    content = M2_FIXTURES[platform].read_text(encoding="utf-8")
    assessment = assess_device((make_artifact(content),), _KB, ASSESSED_AT)

    assert assessment.fingerprint.platform == platform
    assert assessment.fingerprint.confidence > 0
    assert len(assessment.facts) > 0
    # every emitted fact must carry a real, resolvable provenance — G3.
    for fact in assessment.facts:
        assert fact.provenance.source in ProvenanceSource
    # at least one control was evaluated to a real verdict, not silently
    # skipped (parse -> extract -> evaluate all actually ran).
    verdicts = {f.verdict for f in assessment.findings}
    assert verdicts
    assert verdicts <= set(Verdict)


def test_juniper_set_facts_match_the_fixture():
    content = M2_FIXTURES["juniper_junos_set"].read_text(encoding="utf-8")
    assessment = assess_device((make_artifact(content),), _KB, ASSESSED_AT)
    by_path = {f.path: f for f in assessment.facts}
    assert by_path["mgmt.protocols.ssh.enabled"].value is True
    assert by_path["auth.root_login_denied"].value is True
    assert by_path["crypto.ssh.protocol_version"].value == "v2"


def test_juniper_brace_facts_match_the_fixture():
    content = M2_FIXTURES["juniper_junos_curly"].read_text(encoding="utf-8")
    assessment = assess_device((make_artifact(content),), _KB, ASSESSED_AT)
    by_path = {f.path: f for f in assessment.facts}
    assert by_path["device.hostname"].value == "fw-brace-01"
    assert by_path["auth.root_login_denied"].value is True
    assert by_path["crypto.ssh.protocol_version"].value == "v2"


def test_fortios_facts_match_the_fixture():
    content = M2_FIXTURES["fortios"].read_text(encoding="utf-8")
    assessment = assess_device((make_artifact(content),), _KB, ASSESSED_AT)
    by_path = {f.path: f for f in assessment.facts}
    assert by_path["mgmt.protocols.telnet.enabled"].value is False
    assert by_path["logging.remote_enabled"].value is True
    assert by_path["filter.default_policy"].value == "accept"
    ftnt_001 = next(f for f in assessment.findings if f.control_id == "NSCA-FTNT-001")
    assert ftnt_001.verdict == Verdict.PASS


def test_panos_facts_match_the_fixture():
    content = M2_FIXTURES["panos"].read_text(encoding="utf-8")
    assessment = assess_device((make_artifact(content),), _KB, ASSESSED_AT)
    by_path = {f.path: f for f in assessment.facts}
    assert by_path["device.hostname"].value == "panos-fw-01"
    assert by_path["mgmt.protocols.telnet.enabled"].value is False
    assert by_path["mgmt.protocols.https.enabled"].value is True
    assert by_path["mgmt.ssh.session_limit"].value == 10
    panos_002 = next(f for f in assessment.findings if f.control_id == "NSCA-PANOS-002")
    assert panos_002.verdict == Verdict.PASS


def test_routeros_facts_match_the_fixture():
    content = M2_FIXTURES["routeros"].read_text(encoding="utf-8")
    assessment = assess_device((make_artifact(content),), _KB, ASSESSED_AT)
    by_path = {f.path: f for f in assessment.facts}
    assert by_path["mgmt.protocols.telnet.enabled"].value is False
    assert by_path["mgmt.protocols.ssh.enabled"].value is True
    assert by_path["time.ntp.enabled"].value is True
    ros_001 = next(f for f in assessment.findings if f.control_id == "NSCA-ROS-001")
    assert ros_001.verdict == Verdict.PASS


def test_cloud_json_facts_match_the_fixture():
    content = M2_FIXTURES["cloud_generic_fw"].read_text(encoding="utf-8")
    assessment = assess_device((make_artifact(content),), _KB, ASSESSED_AT)
    by_path = {f.path: f for f in assessment.facts}
    assert by_path["device.hostname"].value == "cloud-fw-01"
    assert by_path["mgmt.protocols.https.enabled"].value is True
    rule_names = sorted(
        f.value for p, f in by_path.items()
        if p.startswith("filter.rules[") and p.endswith("].name")
    )
    assert rule_names == ["allow-ssh", "deny-all"]
    cloud_001 = next(f for f in assessment.findings if f.control_id == "NSCA-CLOUD-001")
    assert cloud_001.verdict == Verdict.PASS
