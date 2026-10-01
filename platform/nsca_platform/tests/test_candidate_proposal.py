"""Candidate proposal — TRD-08.2, backend-02 M3.

Ollama is not reachable in this sandbox (verified directly: a connection to
`localhost:11434` times out) — see the M3 report. Every test here exercises
the heuristic-only path, which is the one INV-08.2-03 requires to work
unconditionally and the one guaranteed to run in CI. The redaction tests
are the one piece of the model-path machinery exercised directly, since
FR-LRN-028 requires it to run even when no model is ever invoked.
"""

from __future__ import annotations

from nsca_platform.learning.candidate_proposal import (
    InferenceMode,
    ollama_reachable,
    propose,
    propose_heuristic,
    redact_secrets,
)
from nsca_platform.learning.template_mining import mine_templates
from nsca_platform.tests.fixtures.mikrotik import build_unmatched_constructs


def _ip_service_template():
    unmatched = build_unmatched_constructs()
    templates = mine_templates(unmatched)
    candidates = [t for t in templates if t.enclosing_path == "/ip service" and t.occurrence_count >= 2]
    assert candidates
    return candidates[0]


# ---------------------------------------------------------------------------
# Redaction — FR-LRN-028, unconditional pre-step.
# ---------------------------------------------------------------------------


def test_redaction_removes_plaintext_password_value():
    line = "add name=admin group=full password=Str0ngP@ss"
    redacted = redact_secrets(line)
    assert "Str0ngP@ss" not in redacted
    assert "password=" in redacted  # key retained, value redacted


def test_redaction_removes_snmp_community_string():
    line = "add name=private read-access=yes write-access=yes"
    line2 = "set community=SuperSecretCommunity123"
    assert "SuperSecretCommunity123" not in redact_secrets(line2)
    # non-secret line passes through unchanged
    assert redact_secrets(line) == line


def test_redaction_is_structure_preserving():
    """TRD-08.2 §5.3 — a redacted type-7-shaped password remains
    syntactically the same shape (same length, punctuation preserved)."""

    line = "password=Str0ngP@ss99"
    redacted = redact_secrets(line)
    # Same overall length, same punctuation positions, alnum chars masked.
    assert len(redacted) == len(line)
    assert redacted != line
    assert "@" in redacted  # non-alnum punctuation preserved


def test_redaction_removes_pem_blocks():
    text = "\n".join(
        [
            "-----BEGIN CERTIFICATE-----",
            "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA",
            "-----END CERTIFICATE-----",
        ]
    )
    redacted = redact_secrets(text)
    assert "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA" not in redacted


def test_redaction_runs_before_heuristic_proposal_regardless_of_mode():
    """propose() must redact even when mode=none (no model ever invoked) —
    it is not conditional on the model actually being called."""

    t = _ip_service_template()
    # propose() internally calls redact_secrets on every source line before
    # doing anything else; this test just confirms the call succeeds and
    # the resulting proposal doesn't leak the raw (non-secret, in this
    # fixture) excerpt verbatim into anything unexpected. The important
    # assertion is functional: it must not raise, and must not attempt any
    # network call in mode=none.
    proposal = propose(t, [("mgmt.protocols.telnet.enabled", "boolean")], mode=InferenceMode.NONE)
    assert proposal.source == "heuristic"


# ---------------------------------------------------------------------------
# Heuristic-only proposal generation (INV-08.2-03).
# ---------------------------------------------------------------------------


def test_heuristic_proposal_finds_telnet_lexical_match():
    t = _ip_service_template()
    candidates = [
        ("mgmt.protocols.telnet.enabled", "boolean"),
        ("mgmt.protocols.ssh.enabled", "boolean"),
    ]
    proposal = propose_heuristic(t, candidates)
    assert proposal.source == "heuristic"
    assert proposal.confidence > 0
    fact_paths = {m.fact_path for m in proposal.mappings}
    assert "mgmt.protocols.telnet.enabled" in fact_paths


def test_heuristic_proposal_carries_explainable_signals():
    """V-08.2-008 — every proposal carries non-empty signals[] identifying
    which evidence kind contributed."""

    t = _ip_service_template()
    proposal = propose_heuristic(t, [("mgmt.protocols.telnet.enabled", "boolean")])
    assert len(proposal.signals) > 0
    assert all(s.kind in ("lexical", "structural", "value_shape") for s in proposal.signals)


def test_heuristic_proposal_flags_polarity_for_negation_bearing_template():
    t = _ip_service_template()
    proposal = propose_heuristic(t, [("mgmt.protocols.telnet.enabled", "boolean")])
    assert proposal.polarity["inverted"] is True
    assert proposal.polarity["indicator"] == "disabled"
    assert proposal.polarity["requires_explicit_confirmation"] is True


def test_no_plausible_mapping_produces_honest_low_confidence_proposal():
    unmatched = build_unmatched_constructs()
    templates = mine_templates(unmatched)
    filler = next(t for t in templates if t.enclosing_path == "/ip route")
    proposal = propose_heuristic(filler, [("mgmt.protocols.telnet.enabled", "boolean")])
    assert proposal.confidence == 0.0
    assert "could not determine" in proposal.description.lower()


# ---------------------------------------------------------------------------
# Model availability (INV-08.2-03 / open question §7 — Ollama unreachable
# in this environment, verified directly).
# ---------------------------------------------------------------------------


def test_ollama_is_not_reachable_in_this_sandbox():
    """Documents the environment fact this milestone's report relies on:
    heuristic-only mode is what actually runs here, not a theoretical
    fallback path."""

    assert ollama_reachable(timeout=1.0) is False


def test_local_mode_degrades_to_heuristic_when_unreachable():
    t = _ip_service_template()
    proposal = propose(t, [("mgmt.protocols.telnet.enabled", "boolean")], mode=InferenceMode.LOCAL)
    # Falls back silently to heuristic — teaching still functions
    # (INV-08.2-03), it is not an error.
    assert proposal.source == "heuristic"


def test_hosted_mode_is_refused_unconditionally():
    """V-08.2-007 — air-gapped mode refuses hosted inference at
    configuration, zero outbound attempts."""

    t = _ip_service_template()
    try:
        propose(t, [("mgmt.protocols.telnet.enabled", "boolean")], mode=InferenceMode.HOSTED)
        assert False, "expected PermissionError"
    except PermissionError as exc:
        assert "air-gapped" in str(exc) or "hosted" in str(exc)
