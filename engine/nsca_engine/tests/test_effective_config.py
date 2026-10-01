"""Effective configuration resolution — the Cisco overlapping `line vty`
case (TRD-02.3 §3.5), reproduced exactly per the TRD's own worked example:

    line vty 0 4
     transport input telnet ssh
     exec-timeout 0 0
    line vty 0 15
     transport input ssh

    -> vty[0..4]   transport = {ssh}   (later stanza wins)
                   exec_timeout = 0    (retained — the later stanza never
                                         mentioned it)
    -> vty[5..15]  transport = {ssh}
                   exec_timeout = <unset>  (no declaration covers it)

backend-01 §5.2 calls this subsystem out as the highest-risk one to
under-build; this is the dedicated unit test for it.
"""

from __future__ import annotations

from nsca_engine.controls.rulepack_loader import load_rulepack
from nsca_engine.extract import runtime as extract_runtime
from nsca_engine.parse import effective_config
from nsca_engine.parse.paradigms import indentation
from nsca_engine.tests.helpers import RULEPACK_PATH

_LOADED_RP = load_rulepack(RULEPACK_PATH)

_CONFIG = (
    "line vty 0 4\n"
    " transport input telnet ssh\n"
    " exec-timeout 0 0\n"
    "line vty 0 15\n"
    " transport input ssh\n"
)


def test_overlapping_vty_ranges_partition_and_resolve_per_attribute():
    result = indentation.parse("ART-VTY", _CONFIG, _LOADED_RP.grammar)
    effective = effective_config.resolve(result.tree)

    assert [(i.lo, i.hi) for i in effective.vty_instances] == [(0, 4), (5, 15)]

    inst_0_4 = effective.vty_instances[0]
    inst_5_15 = effective.vty_instances[1]

    # vty[0..4]: transport comes from the LATER stanza (line vty 0 15),
    # exec_timeout is RETAINED from the earlier stanza (never overridden).
    assert result.tree.raw(inst_0_4.attrs["transport_input"]).strip() == "transport input ssh"
    assert result.tree.raw(inst_0_4.attrs["exec_timeout"]).strip() == "exec-timeout 0 0"

    # vty[5..15]: only ever touched by the second stanza; no exec_timeout.
    assert result.tree.raw(inst_5_15.attrs["transport_input"]).strip() == "transport input ssh"
    assert "exec_timeout" not in inst_5_15.attrs


def test_facts_emitted_per_range_no_collapse():
    """DD-02.3-03: a control asserting "no VTY line permits Telnet" must see
    every range — facts are emitted per scope instance, never collapsed to
    a single value."""

    result = indentation.parse("ART-VTY", _CONFIG, _LOADED_RP.grammar)
    effective = effective_config.resolve(result.tree)
    extraction = extract_runtime.extract(
        result.tree, effective, _LOADED_RP.extractors, "ART-VTY", _LOADED_RP.lookup_tables
    )
    telnet_facts = [f for f in extraction.facts if f.path.endswith("mgmt.protocols.telnet.enabled")]
    assert len(telnet_facts) == 2
    paths = {f.path for f in telnet_facts}
    assert paths == {
        "vty[0..4].mgmt.protocols.telnet.enabled",
        "vty[5..15].mgmt.protocols.telnet.enabled",
    }
    values = {f.path: f.value for f in telnet_facts}
    assert values["vty[0..4].mgmt.protocols.telnet.enabled"] is False  # transport input ssh only
    assert values["vty[5..15].mgmt.protocols.telnet.enabled"] is False


def test_no_vty_ranges_yields_empty_instances():
    result = indentation.parse("ART-NOVTY", "hostname X\n", _LOADED_RP.grammar)
    effective = effective_config.resolve(result.tree)
    assert effective.vty_instances == ()
