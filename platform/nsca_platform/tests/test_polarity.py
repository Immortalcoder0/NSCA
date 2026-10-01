"""Polarity — V-08.3-002 / V-08.2-001/002, backend-02 M3.

Written first and treated as release-blocking, per the task brief and
TRD-08.3 §11's note that this is "one of the five criteria that prove the
product's central claims."
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nsca_platform.learning.polarity import (
    TrainingAnswer,
    derive_boolean_value,
    key_contains_negation,
    polarity_inverted,
    value_is_negative_form,
)


# ---------------------------------------------------------------------------
# V-08.2-001 — polarity correctly detected across all five syntactic forms
# (TRD-08.2 §4.2's cross-platform table).
#
# Design decision (see polarity.py's `polarity_inverted` docstring): the
# `inverted` flag is a function of the *key* alone (does the key phrase the
# concept negatively relative to the positively-phrased target fact), not
# an XOR with the observed value — this is what makes `disabled=no` and
# `disabled=yes` both report `inverted: true`, matching every place the
# doc shows the concrete MikroTik example (08-learning-system.md §6's UI
# mock, TRD-08.3 §3.1's synthesised rule). The *target boolean* still
# correctly handles both directions via `derive_boolean_value`'s
# "flip once, conditioned on the key" rule.
# ---------------------------------------------------------------------------


def test_mikrotik_double_negative_resolves_enabled_true():
    # `set telnet disabled=no` -> telnet.enabled = TRUE
    assert derive_boolean_value("disabled", "no") is True
    assert polarity_inverted("disabled", "no") is True


def test_mikrotik_double_negative_other_direction():
    # `set api disabled=yes` -> telnet.enabled = FALSE; same key, so still
    # flagged `inverted` (it is the same negatively-phrased key), but the
    # *value* correctly resolves the other way.
    assert derive_boolean_value("disabled", "yes") is False
    assert polarity_inverted("disabled", "yes") is True


def test_fortinet_negated_value_form():
    # `set admin-telnet disable` -> telnet.enabled = FALSE. The key itself
    # ("admin-telnet") carries no negation word; the negation lives in the
    # value token ("disable"), which `value_is_negative_form` recognises.
    assert value_is_negative_form("disable") is True
    assert key_contains_negation("admin-telnet") is False


def test_cisco_positive_assertion_not_inverted():
    # `transport input ssh` -> ssh.enabled = TRUE, no negation anywhere.
    assert key_contains_negation("transport_input") is False
    assert polarity_inverted("transport_input", "ssh") is False


def test_juniper_delete_verb_is_a_negation_indicator():
    assert key_contains_negation("delete") is True


def test_flip_once_rule_handles_both_directions_from_the_same_key():
    """TRD-08.2 §4.2: 'a naïve implementation that flips once regardless of
    the value gets one of them wrong' — `derive_boolean_value` flips
    conditioned on the key's own negation, which handles both directions
    correctly from one rule."""

    assert derive_boolean_value("shutdown", "true") is False
    assert derive_boolean_value("shutdown", "false") is True


# ---------------------------------------------------------------------------
# V-08.3-002 / V-08.2-002 — a negation-bearing template cannot be confirmed
# without an explicit polarity answer. THE test.
# ---------------------------------------------------------------------------


def test_confirm_without_polarity_confirmed_is_rejected_with_422_shaped_error():
    with pytest.raises(ValidationError) as exc_info:
        TrainingAnswer(
            question_id="Q-mikrotik-001",
            response="confirm",
            requires_polarity=True,
            polarity_confirmed=None,
        )
    assert "polarity confirmation required" in str(exc_info.value)


def test_polarity_inverted_response_without_confirmation_is_also_rejected():
    """INV-08.2-02 covers both `confirm` and `polarity_inverted` — flagging
    the inversion is itself a polarity decision and still requires the
    field to be set explicitly."""

    with pytest.raises(ValidationError):
        TrainingAnswer(
            question_id="Q-mikrotik-001",
            response="polarity_inverted",
            requires_polarity=True,
            polarity_confirmed=None,
        )


def test_confirm_with_explicit_polarity_confirmed_succeeds():
    ans = TrainingAnswer(
        question_id="Q-mikrotik-001",
        response="confirm",
        requires_polarity=True,
        polarity_confirmed=True,
    )
    assert ans.polarity_confirmed is True


def test_non_negation_bearing_template_does_not_require_polarity():
    # requires_polarity=False (e.g. `mgmt.ssh.version == 2`-style template
    # with no negation indicator) — no gate.
    ans = TrainingAnswer(question_id="Q-x-001", response="confirm", requires_polarity=False)
    assert ans.polarity_confirmed is None


def test_not_relevant_and_skip_never_require_polarity_even_if_flagged():
    # A "not compliance-relevant" or "skip" answer isn't asserting anything
    # about polarity at all — the gate only applies to accept-shaped
    # responses (confirm / polarity_inverted).
    TrainingAnswer(question_id="Q-x-001", response="not_relevant", requires_polarity=True)
    TrainingAnswer(question_id="Q-x-001", response="skip", requires_polarity=True)


def test_edit_response_does_not_require_the_polarity_field():
    # `edit` lets the administrator remap slot->fact manually; polarity for
    # the edited mapping is re-derived at synthesis time from the edited
    # expression, not carried on the answer itself.
    TrainingAnswer(question_id="Q-x-001", response="edit", requires_polarity=True)
