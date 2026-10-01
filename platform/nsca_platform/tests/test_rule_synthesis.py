"""Rule synthesis — TRD-08.3, backend-02 M3.

The critical test in this module (and arguably in this whole milestone,
per the task brief) is `test_synthesized_rulepack_loads_in_real_track_a_loader`:
it writes a rulepack YAML with this module's own writer and then imports
Track A's real, unmodified `nsca_engine.controls.rulepack_loader` to load
it — the literal integration test backend-02 §2.2 asks for ("can Track A's
loader parse what I just wrote").
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nsca_platform.learning.polarity import derive_boolean_value
from nsca_platform.learning.rule_synthesis import (
    Confirmation,
    ConfirmedMapping,
    SynthesisError,
    synthesize,
    write_extractors_to_rulepack,
)
from nsca_engine.types import UnmatchedConstruct
from nsca_platform.learning.template_mining import mine_templates
from nsca_platform.tests.fixtures.mikrotik import build_unmatched_constructs


def _ip_service_multi_mapping_template():
    unmatched = build_unmatched_constructs()
    templates = mine_templates(unmatched)
    return next(t for t in templates if t.enclosing_path == "/ip service" and t.occurrence_count >= 2)


def _ip_service_template_with_value_variability():
    """A small, self-contained template (mined directly, not pulled from
    the big MikroTik fixture) whose confirmed examples include *both*
    `disabled=no` and `disabled=yes` — this is the shape TRD-08.3 §3.1's
    worked example needs (a genuine `val` capture group), which the big
    fixture's own `/ip service` group doesn't exercise on its own (all
    four of its `port=`-bearing lines happen to be `disabled=no`; `api` —
    the one `disabled=yes` line — lacks `port=` and is therefore a
    separate template, per `mine_templates`' shape-signature grouping).
    Rule synthesis is a unit-level concern; this fixture isolates it from
    that big-fixture accident."""

    unmatched = [
        UnmatchedConstruct(
            artifact_id="RTR-Pune-02.rsc", lines=(14,), excerpt="set telnet disabled=no",
            parse_path=("/ip service",),
        ),
        UnmatchedConstruct(
            artifact_id="RTR-Pune-02.rsc", lines=(17,), excerpt="set ssh disabled=no",
            parse_path=("/ip service",),
        ),
        UnmatchedConstruct(
            artifact_id="RTR-Pune-02.rsc", lines=(19,), excerpt="set api disabled=yes",
            parse_path=("/ip service",),
        ),
    ]
    templates = mine_templates(unmatched)
    assert len(templates) == 1
    return templates[0]


def _confirmation():
    from nsca_platform.learning.rule_synthesis import _is_boolean_domain

    t = _ip_service_template_with_value_variability()
    mappings = tuple(
        ConfirmedMapping(slot_value=v, fact_path=f"mgmt.protocols.{v}.enabled", polarity_confirmed=True)
        for s in t.slots
        for v in s.observed_values
        if not _is_boolean_domain(s)  # the service-name slot, not the yes/no value slot
    )
    return Confirmation(
        template=t,
        mappings=mappings,
        taught_by="r.kulkarni",
        source_artifact="RTR-Pune-02.rsc",
        negation_key="disabled",
    )


def test_synthesis_produces_one_extractor_per_confirmed_mapping():
    confirmation = _confirmation()
    extractors = synthesize(confirmation)
    assert len(extractors) == len(confirmation.mappings)
    fact_paths = {e["emit"][0]["fact"] for e in extractors}
    assert fact_paths == {m.fact_path for m in confirmation.mappings}


def test_synthesis_rejects_unconfirmed_polarity():
    """V-08.3-002 — a rule cannot be synthesised from a confirmation
    lacking polarity confirmation for a negation-bearing template."""

    t = _ip_service_multi_mapping_template()
    mappings = (ConfirmedMapping(slot_value="telnet", fact_path="mgmt.protocols.telnet.enabled", polarity_confirmed=False),)
    confirmation = Confirmation(
        template=t, mappings=mappings, taught_by="r.kulkarni",
        source_artifact="RTR-Pune-02.rsc", negation_key="disabled",
    )
    with pytest.raises(SynthesisError, match="polarity"):
        synthesize(confirmation)


def test_generated_value_expression_visibly_contains_the_inversion():
    """INV-08.3-02 — the polarity decision must be visible in the
    generated expression, not buried in an opaque lookup."""

    confirmation = _confirmation()
    extractors = synthesize(confirmation)
    telnet_ex = next(e for e in extractors if e["emit"][0]["fact"] == "mgmt.protocols.telnet.enabled")
    # disabled=no -> enabled=True, so the expression must read `val == 'no'`
    assert telnet_ex["emit"][0]["value"] == "val == 'no'"


def test_frozen_tests_reflect_confirmed_examples_correctly():
    confirmation = _confirmation()
    extractors = synthesize(confirmation)
    telnet_ex = next(e for e in extractors if e["emit"][0]["fact"] == "mgmt.protocols.telnet.enabled")
    assert len(telnet_ex["tests"]) >= 1
    for test in telnet_ex["tests"]:
        assert test["expect"]["mgmt.protocols.telnet.enabled"] is True  # disabled=no


def test_match_pattern_self_matches_its_own_source_line():
    """Gate 1 (self-match) precondition — before validation_gates even
    runs, the generated pattern must actually match the line it was
    synthesised from."""

    import re

    confirmation = _confirmation()
    extractors = synthesize(confirmation)
    telnet_ex = next(e for e in extractors if e["emit"][0]["fact"] == "mgmt.protocols.telnet.enabled")
    pattern = re.compile(telnet_ex["match"])
    assert pattern.match("set telnet disabled=no port=23")
    assert not pattern.match("set ssh disabled=no port=22")  # narrow to its own value


# ---------------------------------------------------------------------------
# THE critical integration test — real Track A loader.
# ---------------------------------------------------------------------------


def test_synthesized_rulepack_loads_in_real_track_a_loader(tmp_path: Path):
    """backend-02 §2.2: "Treat 'can Track A's loader parse what I just
    wrote' as a literal integration test, not an assumption." This test
    imports `nsca_engine.controls.rulepack_loader` — the real, unmodified
    Track A module — and confirms it loads a rulepack this module's own
    writer produced, with zero changes to either side."""

    from nsca_engine.controls.rulepack_loader import load_rulepack

    confirmation = _confirmation()
    extractors = synthesize(confirmation)

    rulepack_path = tmp_path / "mikrotik_learned_test.yaml"
    grammar = {"paradigm": "path_header", "comment_char": "#"}
    write_extractors_to_rulepack(
        rulepack_path, platform="mikrotik_learned_test", vendor="mikrotik", grammar=grammar,
        new_extractors=extractors,
    )

    loaded = load_rulepack(rulepack_path)

    assert loaded.platform == "mikrotik_learned_test"
    assert loaded.paradigm == "path_header"
    assert len(loaded.extractors) == len(extractors)
    loaded_ids = {e.extractor_id for e in loaded.extractors}
    written_ids = {e["extractor_id"] for e in extractors}
    assert loaded_ids == written_ids

    # And the loaded extractor actually *runs* — matches its own source
    # excerpt and emits the confirmed boolean value, using the real
    # engine's own match+emit path (nsca_engine.extract.runtime), proving
    # this isn't just YAML-shape-compatible but semantically correct.
    from nsca_engine.api import compile_value_expression, evaluate_value_expression

    telnet_spec = next(e for e in loaded.extractors if "telnet" in e.extractor_id)
    m = telnet_spec.match.match("set telnet disabled=no port=23")
    assert m is not None
    captures = m.groupdict()
    compiled = compile_value_expression(telnet_spec.emits[0].value_expr)
    value = evaluate_value_expression(compiled, captures, {})
    assert value is True  # disabled=no -> telnet.enabled = True


def test_rulepack_write_is_idempotent_on_re_synthesis(tmp_path: Path):
    """Re-running synthesis for the same confirmed mapping (e.g. a session
    resumed) must not duplicate extractor entries in the written file."""

    confirmation = _confirmation()
    extractors = synthesize(confirmation)
    rulepack_path = tmp_path / "mikrotik_learned_test.yaml"
    grammar = {"paradigm": "path_header", "comment_char": "#"}

    write_extractors_to_rulepack(rulepack_path, "mikrotik_learned_test", "mikrotik", grammar, extractors)
    write_extractors_to_rulepack(rulepack_path, "mikrotik_learned_test", "mikrotik", grammar, extractors)

    import yaml

    doc = yaml.safe_load(rulepack_path.read_text(encoding="utf-8"))
    ids = [e["extractor_id"] for e in doc["extractors"]]
    assert len(ids) == len(set(ids))
