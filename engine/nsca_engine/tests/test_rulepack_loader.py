"""Unit tests for controls/rulepack_loader.py — loads the real
`knowledge/rulepacks/cisco_ios.yaml` and `knowledge/control_packs/
nsca_native.yaml` and checks the resulting shapes."""

from __future__ import annotations

from nsca_engine.controls.rulepack_loader import load_control_pack, load_rulepack
from nsca_engine.tests.helpers import CONTROL_PACK_PATH, RULEPACK_PATH


def test_load_rulepack_extractors_sorted_and_nonempty():
    loaded = load_rulepack(RULEPACK_PATH)
    assert loaded.platform == "cisco_ios"
    assert len(loaded.extractors) > 0
    ids = [e.extractor_id for e in loaded.extractors]
    assert ids == sorted(ids)


def test_load_rulepack_defaults_cite_a_source():
    loaded = load_rulepack(RULEPACK_PATH)
    for path, entries in loaded.defaults.items():
        for entry in entries:
            assert entry.source, f"defaults entry for {path} has no source citation"


def test_crypto_ssh_ciphers_has_no_defaults_entry():
    """The exact mechanism behind the worked example's flagship
    default_unknown case: no defaults table row for crypto.ssh.ciphers."""

    loaded = load_rulepack(RULEPACK_PATH)
    assert "crypto.ssh.ciphers" not in loaded.defaults


def test_load_control_pack_controls_sorted_and_at_least_twenty():
    loaded = load_control_pack(CONTROL_PACK_PATH)
    assert len(loaded.controls) >= 20
    ids = [c.control_id for c in loaded.controls]
    assert ids == sorted(ids)


def test_every_control_has_a_compiled_assertion():
    loaded = load_control_pack(CONTROL_PACK_PATH)
    for c in loaded.controls:
        assert c.assertion.tree is not None
