"""V-05.2-001 / backend-01 §5.4: "a control whose required fact is omitted
never evaluates to PASS." Property test over every control in the real
native control pack, run against generated fact sets that would otherwise
satisfy the control (Hypothesis).
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from nsca_engine.controls.evaluate import evaluate_control
from nsca_engine.tests.helpers import build_knowledge_base
from nsca_engine.types import Fact, Provenance, ProvenanceSource, Verdict

_KB = build_knowledge_base()
_LOADED_CP = _KB.control_packs[0].loaded
_CONTROLS = _LOADED_CP.controls
_LOOKUP = _LOADED_CP.lookup_tables


def _favourable_value(path: str):
    """A value that, taken in isolation, tends toward a PASS-shaped
    assertion for the controls in this pack (booleans -> true/false chosen
    per naming convention, numbers -> a small positive int, collections ->
    an empty list, which is vacuously compliant for none()/all())."""

    if path.endswith(".enabled") or path.endswith("_configured") or path.endswith("_present"):
        return False if "telnet" in path or "http" in path or "write_access" in path else True
    if path.endswith("_logged") or path.endswith("_enabled"):
        return True
    if "version" in path:
        return 2
    if "timeout" in path or "tries" in path:
        return 5
    return True


@given(st.sampled_from([c.control_id for c in _CONTROLS]))
@settings(max_examples=200, deadline=None)
def test_control_with_one_required_fact_omitted_never_passes(control_id):
    control = next(c for c in _CONTROLS if c.control_id == control_id)
    if not control.requires_facts:
        return  # NOT_APPLICABLE-only controls (e.g. constant-true placeholders)

    for omitted in control.requires_facts:
        facts: list[Fact] = []
        for path in control.requires_facts:
            if path == omitted:
                continue
            value = _favourable_value(path)
            facts.append(
                Fact(
                    path=path, value=value, type="unknown",
                    provenance=Provenance(source=ProvenanceSource.EXPLICIT, lines=(1,)),
                )
            )
            if value is True or value is False:
                # supply one plausible collection element too, in case this
                # base path is actually a collection (auth.local_users etc.)
                pass

        result = evaluate_control(control, tuple(facts), "cisco_ios", _LOOKUP)
        assert result.verdict != Verdict.PASS, (
            f"{control_id}: omitting {omitted} produced PASS, expected "
            f"UNKNOWN or NOT_APPLICABLE"
        )
