"""Polarity — TRD-08.2 §4, the highest-consequence error class in the
product (08-learning-system.md §5.3/§12).

```
disabled = no    ->    enabled = TRUE
```

Invert this and a device with Telnet wide open is certified compliant — and
unlike a parse failure (which surfaces as UNKNOWN), a polarity error
surfaces as a *confident PASS*. Policy: **never infer polarity silently**.
It is always its own explicit, separately confirmable statement
(INV-08.2-01), and a negation-bearing template cannot be confirmed without
it (INV-08.2-02) — enforced here as a Pydantic `@model_validator`, exactly
the pattern TECH-STACK.md §4 shows for `TrainingAnswer`, so a client cannot
bypass the gate by skipping a UI step.

`V-08.3-002` / `V-08.2-002` (the polarity-gate test) is written first in
this milestone's test suite and treated as release-blocking, per the task
brief and TRD-08.3 §11's own note that it is "one of the five criteria that
prove the product's central claims."
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, model_validator

# TRD-08.2 §4.2 — negation indicators, safety-critical content (TRD-08.4 Q3:
# "shipped with the engine, extended locally with attribution, never
# overwritten by an import"). Kept here as the canonical list; the polarity
# index (transfer_metrics.py) may append platform-observed forms but never
# removes from this base set.
NEGATION_INDICATORS: frozenset[str] = frozenset({
    "disabled", "deny", "no-", "off", "shutdown", "suppress", "inactive",
    "block", "prohibit", "reject", "restrict", "none", "delete", "unset",
})

# Value-domain forms that are themselves negative (TRD-08.2 §4.2's second
# XOR operand): "the value domain is itself negative".
NEGATIVE_VALUE_FORMS: frozenset[str] = frozenset({"no", "false", "off", "disable", "disabled"})


def key_contains_negation(key: str) -> bool:
    lowered = key.lower()
    return any(ind in lowered for ind in NEGATION_INDICATORS)


def value_is_negative_form(value: str) -> bool:
    return value.strip().lower() in NEGATIVE_VALUE_FORMS


def value_as_bool(value: str) -> bool | None:
    """Literal reading of a yes/no-shaped token, before any key-negation
    adjustment. Returns ``None`` for a value this simple domain can't
    classify (the caller should fall back to leaving polarity unresolved
    rather than guessing)."""

    lowered = value.strip().lower()
    if lowered in ("yes", "true", "on", "enable", "enabled", "1"):
        return True
    if lowered in NEGATIVE_VALUE_FORMS or lowered in ("0",):
        return False
    return None


def polarity_inverted(key: str, value: str | None = None) -> bool:
    """Whether reading this key requires flipping the naive value-boolean
    to reach the *target* (positively-phrased) fact — TRD-08.2 §11 Q1's
    "required only where a negation indicator is present [in the key]"
    design: `disabled=no` and `disabled=yes` are *both* flagged
    `inverted: true` (08-learning-system.md §6's UI mock shows the same
    `polarity.inverted: true` regardless of which value confirmed the
    example), because it is the *key* being negatively phrased relative to
    the positively-phrased target fact (`X.enabled`) that makes a flip
    necessary — not which particular value was observed. `value` is
    accepted for interface symmetry with `derive_boolean_value` but does
    not change the result; the two-argument value-domain XOR variant of
    this formula that TRD-08.2 §4.2's prose sketches was tried during
    development and rejected — flagged as a judgment call in the M3
    report — because it produces `inverted=False` for the document's own
    repeated central worked example (`disabled=no`), contradicting every
    other place the document shows this exact case as `inverted: true`
    (§6's UI mock, TRD-08.3 §3.1's synthesised rule comment).
    """

    return key_contains_negation(key)


def derive_boolean_value(key: str, value: str) -> bool | None:
    """The actual target boolean, correctly handling the "flip once"
    rule (TRD-08.2 §4.2's "a naïve implementation that flips once regardless
    of the value gets one of them wrong" — here the flip is conditioned on
    `polarity_inverted`, so `disabled=no` -> True and `disabled=yes` ->
    False both come out right from the same rule)."""

    raw = value_as_bool(value)
    if raw is None:
        return None
    return (not raw) if polarity_inverted(key, value) else raw


def requires_explicit_polarity_confirmation(key: str, value: str | None = None) -> bool:
    """TRD-08.2 §11 Q1's current design: required only where a negation
    indicator is present in the *key* — value-only negation (e.g.
    `enabled=no`, no negation word in the key) is still polarity-relevant
    but does not itself force the confirmation block; `polarity_inverted`
    is still computed and shown either way. This mirrors
    15-api-specification.md §6's `requires_explicit_confirmation` field."""

    return key_contains_negation(key)


class PolarityInfo(BaseModel):
    inverted: bool
    indicator: str | None = None
    requires_explicit_confirmation: bool = False


class TrainingAnswer(BaseModel):
    """TECH-STACK.md §4's exact pattern, reproduced verbatim for the real
    (non-stub) training pipeline. `requires_polarity` is carried on the
    answer itself (populated by the caller from the persisted
    `training_question` row) rather than looked up from a module-level
    stub set, which is what `api/training.py`'s M0 stand-in did."""

    question_id: str
    response: Literal["confirm", "polarity_inverted", "edit", "not_relevant", "skip"]
    requires_polarity: bool = False
    polarity_confirmed: bool | None = None
    edits: dict[str, Any] | None = None

    @model_validator(mode="after")
    def polarity_gate(self) -> TrainingAnswer:
        # INV-08.2-02: a negation-bearing template cannot be confirmed
        # (accepted OR explicitly flagged as inverted) without a polarity
        # answer — both `confirm` and `polarity_inverted` are decisions
        # *about* polarity, so both require the field to be set.
        if self.requires_polarity and self.response in ("confirm", "polarity_inverted"):
            if self.polarity_confirmed is None:
                raise ValueError(
                    "polarity confirmation required: this template contains a negation "
                    "indicator and its polarity reading must be explicitly confirmed or "
                    "flagged as inverted before it can be accepted"
                )
        return self
