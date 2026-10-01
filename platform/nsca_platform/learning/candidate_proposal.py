"""Candidate proposal — TRD-08.2, Stage 4 of 08-learning-system.md §2.

Three corroborating signals (§3): lexical priors, structural analogy,
value-shape/polarity — always computed, always available (INV-08.2-03: the
system functions with no model available). A local Ollama model, when
reachable, *refines* the heuristic proposal; it never replaces the
requirement to produce one, and its output is discarded as a proposal for
human confirmation the moment it's produced — nothing it says is ever
stored as a fact (§5.2).

**Redaction runs unconditionally before any model invocation** (FR-LRN-028)
— `redact_secrets` is called from `propose()` itself, not from a
conditional branch a caller could skip, and it runs even in heuristic-only
mode (cheap, and it keeps the boundary in one place rather than two).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from nsca_platform.learning.polarity import (
    key_contains_negation,
    polarity_inverted,
    requires_explicit_polarity_confirmation,
)
from nsca_platform.learning.template_mining import (
    Slot,
    Template,
    _expand_synonyms,
    _split_words,
)

OLLAMA_DEFAULT_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b-instruct"
OLLAMA_TIMEOUT_SECONDS = 2.0

# ---------------------------------------------------------------------------
# Redaction (FR-LRN-028) — structure-preserving, unconditional.
# ---------------------------------------------------------------------------

# Rulepack-declared credential positions (07-vendor-rulepacks.md §7.2's
# `password_encodings`) plus generically hash-shaped tokens. Kept small and
# explicit rather than a "smart" ML redactor — false negatives here are a
# security bug, so the patterns favour recall.
_SECRET_KEY_NAMES = re.compile(
    r"\b(password|passwd|secret|community|psk|pre-?shared-?key|private-?key)\b",
    re.IGNORECASE,
)
_HASH_SHAPED = re.compile(r"^\$\d\$[./A-Za-z0-9]{4,}\$?[./A-Za-z0-9]*$")  # e.g. $8$..., $1$...
_PEM_BLOCK = re.compile(
    r"-----BEGIN [^-]+-----.*?-----END [^-]+-----", re.DOTALL
)


def _redact_value_preserving_shape(value: str) -> str:
    """Replace with same-length placeholder characters so the shape (a
    "type 7 password" stays a syntactically plausible type-7-shaped token)
    is preserved for the model to reason about (TRD-08.2 §5.3)."""

    if not value:
        return value
    return "".join("*" if c.isalnum() else c for c in value)


def redact_secrets(text: str) -> str:
    """FR-LRN-028 — called unconditionally by `propose()` before anything
    is sent to a model. Structure-preserving (§5.3): a redacted line is
    still recognisably the same shape."""

    text = _PEM_BLOCK.sub(lambda m: "-----BEGIN REDACTED-----\n[redacted]\n-----END REDACTED-----", text)

    out_lines = []
    for line in text.splitlines():
        redacted = line
        # key=value / key "value" forms where the key names a credential.
        def _kv_sub(m: re.Match[str]) -> str:
            key, sep, val = m.group("key"), m.group("sep"), m.group("val")
            return f"{key}{sep}{_redact_value_preserving_shape(val)}"

        redacted = re.sub(
            r"(?P<key>\b\w[\w-]*)(?P<sep>\s*=\s*)(?P<val>\S+)",
            lambda m: _kv_sub(m) if _SECRET_KEY_NAMES.search(m.group("key")) else m.group(0),
            redacted,
        )
        # Bare hash-shaped tokens anywhere on the line.
        redacted = re.sub(
            r"\S+",
            lambda m: _redact_value_preserving_shape(m.group(0)) if _HASH_SHAPED.match(m.group(0)) else m.group(0),
            redacted,
        )
        out_lines.append(redacted)
    return "\n".join(out_lines)


# ---------------------------------------------------------------------------
# Heuristic proposal — lexical + structural + value-shape (§3).
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Signal:
    kind: str  # "lexical" | "structural" | "value_shape" | "model"
    contribution: float
    detail: str


@dataclass(frozen=True, slots=True)
class Mapping:
    slot_value: str
    fact_path: str
    justification: str


@dataclass(frozen=True, slots=True)
class Proposal:
    template_id: str
    mappings: tuple[Mapping, ...]
    polarity: dict[str, Any]
    confidence: float
    signals: tuple[Signal, ...]
    description: str
    source: str  # "model" | "heuristic"


# A tiny seed structural index (TRD-08.2 §3.2 / TRD-08.4 §3.1's
# synonym/structural indices, in their simplest form — no cross-platform
# corpus exists yet in this milestone, so this is the bootstrap content
# rather than something accumulated from prior teaching sessions;
# transfer_metrics.py's synonym index is where real accumulation happens
# once platforms have actually been taught).
_STRUCTURAL_INDEX: dict[str, tuple[str, ...]] = {
    "mgmt.protocols": ("service", "services", "management", "mgmt"),
    "snmp.communities": ("snmp", "community"),
    "logging": ("logging", "log", "syslog"),
    "time.ntp": ("ntp", "clock", "time"),
    "auth.radius": ("radius", "aaa"),
    "auth.local_users": ("user", "users"),
    "auth.local_groups": ("group", "groups"),
}


def _lexical_score(token: str, fact: str) -> float:
    """TRD-08.2 §3.1's `lexical_score` — exact synonym match (1.0), fuzzy
    edit-distance-below-threshold (0.7), or description-substring (0.5).
    Simplified to synonym-table + segment matching (no live schema
    registry description lookup wired in this milestone)."""

    fact_segments = _split_words(fact)
    expanded_token = _expand_synonyms({token.lower()})
    if fact_segments & expanded_token:
        return 1.0
    # Fuzzy: cheap normalized edit distance via difflib.
    import difflib

    best = max((difflib.SequenceMatcher(None, token.lower(), seg).ratio() for seg in fact_segments), default=0.0)
    if best >= 0.8:
        return 0.7
    return 0.0


def _structural_score(enclosing_path: str, fact: str) -> float:
    path_words = _split_words(enclosing_path)
    for prefix, keywords in _STRUCTURAL_INDEX.items():
        if fact.startswith(prefix) and (path_words & set(keywords)):
            return 1.0
    return 0.0


_BOOLEAN_WORDS = frozenset({"yes", "no", "true", "false", "on", "off", "enable", "disable", "enabled", "disabled"})


def _value_shape_score_applies(slot: Slot) -> bool:
    """Whether this slot is (plausibly) the boolean-domain *value* slot
    (`disabled=<yes|no>`'s value position) rather than an *identifying*
    slot (`disabled=<yes|no>`'s service-name position) — used to keep
    per-value lexical matching (identifying slots) separate from the
    template-level boolean-shape bonus (the value slot)."""

    vals = {v.lower() for v in slot.observed_values}
    return 0 < len(vals) <= 2 and vals <= _BOOLEAN_WORDS


def _value_shape_score(t: Template, fact_type: str) -> float:
    for s in t.slots:
        if fact_type == "boolean" and _value_shape_score_applies(s):
            return 1.0
    return 0.0


def propose_heuristic(
    t: Template,
    fact_candidates: list[tuple[str, str]],  # (fact_path, fact_type)
) -> Proposal:
    """TRD-08.2 §3 — always available, no model required (INV-08.2-03)."""

    signals: list[Signal] = []
    mappings: list[Mapping] = []

    # Redaction runs even in heuristic mode — cheap, and keeps the
    # boundary in exactly one place (`propose()` below is the real
    # unconditional call site; this function is also exercised directly by
    # tests, so it redacts too rather than relying on a caller to remember).
    _ = redact_secrets(" ".join(t.literal_tokens))

    # Score fact candidates once for template-level (structural/value-shape)
    # signals, then — separately — score each *identifying* slot's
    # individual observed values against the vocabulary so that e.g.
    # `telnet` and `ssh` (two values of the same slot) each get their own
    # best-matching fact rather than all values collapsing onto one
    # "best overall" fact (TRD-08.2 §3.1: the lexical match is inherently
    # per-token, not per-template).
    #
    # Bug found while fixing the rule-synthesis regex-anchoring bug (a
    # related but distinct defect, same live-teaching scenario): this used
    # to only exclude the boolean yes/no *value* slot
    # (`_value_shape_score_applies`), so any OTHER varying slot on the same
    # line — e.g. a `port=<integer>` slot whose observed values are literal
    # port numbers (21/22/23/80) — was treated as "identifying" too and
    # lexically scored against the fact vocabulary. Port numbers have no
    # meaningful lexical relationship to any fact, so `_lexical_score`
    # degenerately picked *some* fact for each (observed: all four
    # collapsed onto `mgmt.protocols.telnet.enabled`, the first/best-scoring
    # fact by whatever tiny residual score matched) — proposing four
    # extra, semantically wrong mappings alongside the four genuinely
    # correct ones (ftp/ssh/telnet/www). Only a slot whose *type* is
    # `"identifier"` (varying-but-non-numeric tokens — `template_mining.py`'s
    # `_slot_type` classification) is a plausible "which service/feature"
    # identifying slot; integer/address/cidr/mac-typed slots never are.
    identifying_slots = [
        s for s in t.slots if not _value_shape_score_applies(s) and s.slot_type == "identifier"
    ]
    best_template_fact = None
    best_template_score = 0.0
    for fact, ftype in fact_candidates:
        structural = _structural_score(t.enclosing_path, fact)
        value_shape = _value_shape_score(t, ftype)
        lexical = max((_lexical_score(tok, fact) for tok in t.literal_tokens), default=0.0)
        score = 0.5 * lexical + 0.3 * structural + 0.2 * value_shape
        if score > best_template_score:
            best_template_score = score
            best_template_fact = (fact, ftype, lexical, structural, value_shape)

    per_value_facts: dict[str, tuple[str, float]] = {}
    for s in identifying_slots:
        for v in s.observed_values:
            best_v_fact = None
            best_v_score = 0.0
            for fact, _ftype in fact_candidates:
                lexical = _lexical_score(v, fact)
                structural = _structural_score(t.enclosing_path, fact)
                score = 0.6 * lexical + 0.4 * structural
                if score > best_v_score:
                    best_v_score = score
                    best_v_fact = fact
            if best_v_fact is not None and best_v_score > 0:
                per_value_facts[v] = (best_v_fact, best_v_score)

    if per_value_facts:
        for v, (fact, _score) in per_value_facts.items():
            mappings.append(Mapping(slot_value=v, fact_path=fact, justification=f"lexical match on {v!r}"))
        signals.append(Signal("lexical", max(s for _f, s in per_value_facts.values()), "per-value lexical matches against fact vocabulary"))
        if best_template_fact is not None and best_template_fact[3] > 0:
            signals.append(Signal("structural", best_template_fact[3], f"enclosing path '{t.enclosing_path}' matches known structure"))
    elif best_template_fact is not None:
        fact, ftype, lexical, structural, value_shape = best_template_fact
        if lexical > 0:
            signals.append(Signal("lexical", lexical, f"token(s) match fact vocabulary for {fact}"))
        if structural > 0:
            signals.append(Signal("structural", structural, f"enclosing path '{t.enclosing_path}' matches known structure for {fact}"))
        if value_shape > 0:
            signals.append(Signal("value_shape", value_shape, f"observed value domain compatible with {ftype}"))
        for s in t.slots:
            for v in s.observed_values:
                mappings.append(Mapping(slot_value=v, fact_path=fact, justification=f"lexical match on {v!r}"))

    # Polarity — computed from whichever literal key looks negation-bearing
    # (INV-08.2-01: always its own explicit field, never silently folded
    # into the mapping).
    negation_key = next((tok for tok in t.literal_tokens if key_contains_negation(tok)), None)
    polarity = {
        "inverted": bool(negation_key and polarity_inverted(negation_key)),
        "indicator": negation_key,
        "requires_explicit_confirmation": bool(negation_key and requires_explicit_polarity_confirmation(negation_key)),
    }

    if per_value_facts:
        confidence = min(1.0, max(score for _f, score in per_value_facts.values()))
        fact_names = sorted({f for f, _s in per_value_facts.values()})
        description = f"This appears to relate to {', '.join(fact_names)}"
    elif best_template_fact is not None:
        confidence = min(1.0, best_template_score)
        description = f"This appears to relate to {best_template_fact[0]}"
    else:
        confidence = 0.0
        description = "We could not determine what this construct does"

    return Proposal(
        template_id=t.template_id,
        mappings=tuple(mappings),
        polarity=polarity,
        confidence=confidence,
        signals=tuple(signals),
        description=description,
        source="heuristic",
    )


# ---------------------------------------------------------------------------
# Local inference mode (FR-LRN-027) — Ollama, gated behind reachability.
# ---------------------------------------------------------------------------


class InferenceMode:
    LOCAL = "local"
    HOSTED = "hosted"
    NONE = "none"


def ollama_reachable(base_url: str = OLLAMA_DEFAULT_URL, timeout: float = OLLAMA_TIMEOUT_SECONDS) -> bool:
    """Best-effort reachability probe — mirrors
    `db/engine.py::database_available()`'s pattern for Postgres. Never
    raises; any failure (connection refused, timeout, DNS) means "not
    reachable", which the caller degrades to heuristic-only for
    (INV-08.2-03)."""

    try:
        req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:  # noqa: BLE001 — deliberately broad, see docstring
        return False


def refine_with_model(
    t: Template,
    heuristic: Proposal,
    fact_candidates: list[tuple[str, str]],
    *,
    base_url: str = OLLAMA_DEFAULT_URL,
    model: str = OLLAMA_MODEL,
    timeout: float = OLLAMA_TIMEOUT_SECONDS,
) -> Proposal | None:
    """Calls a local Ollama instance, JSON-schema-constrained to select
    only from `fact_candidates`' registered paths (TRD-08.2 §5.1 — "the
    model selects from registered fact paths rather than emitting free
    text"). Returns ``None`` on any failure (unreachable, malformed
    response, or a path outside the registered set — TRD-08.2 §8's "model
    proposes an unregistered fact path" edge case: discarded before
    presentation, heuristic fallback used), never raising into the caller.

    Secrets are redacted (`redact_secrets`) before the prompt is built —
    unconditionally, per FR-LRN-028 — regardless of whether this function
    is ever actually reached (`propose()` below also redacts independently
    as the real enforcement point; this call redacts again defensively
    since this function can be unit-tested in isolation).
    """

    redacted_excerpt = redact_secrets(" | ".join(ln[2] for ln in t.source_lines))
    allowed_paths = [f for f, _ in fact_candidates]

    schema = {
        "type": "object",
        "properties": {
            "fact_path": {"type": "string", "enum": allowed_paths},
            "polarity_inverted": {"type": "boolean"},
            "justification": {"type": "string"},
        },
        "required": ["fact_path", "polarity_inverted", "justification"],
    }
    prompt = (
        "You are mapping a network device configuration construct to a security "
        "schema fact. Only choose from the allowed fact paths.\n"
        f"Section: {t.enclosing_path}\nSkeleton: {t.skeleton}\n"
        f"Observed lines (secrets redacted): {redacted_excerpt}\n"
        f"Allowed fact paths: {allowed_paths}\n"
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "format": schema,
        "stream": False,
    }

    try:
        req = urllib.request.Request(
            f"{base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        parsed = json.loads(body.get("response", "{}"))
    except Exception:  # noqa: BLE001 — any failure degrades to heuristic
        return None

    fact_path = parsed.get("fact_path")
    if fact_path not in allowed_paths:
        return None  # TRD-08.2 §8 — unregistered path, discard

    signals = tuple(heuristic.signals) + (
        Signal("model", 1.0, f"model proposed {fact_path}: {parsed.get('justification', '')}"),
    )
    mappings = tuple(
        Mapping(slot_value=m.slot_value, fact_path=fact_path, justification="model-proposed")
        for m in heuristic.mappings
    ) or heuristic.mappings

    return Proposal(
        template_id=t.template_id,
        mappings=mappings,
        polarity={**heuristic.polarity, "inverted": bool(parsed.get("polarity_inverted", heuristic.polarity["inverted"]))},
        confidence=max(heuristic.confidence, 0.8),
        signals=signals,
        description=heuristic.description,
        source="model",
    )


def propose(
    t: Template,
    fact_candidates: list[tuple[str, str]],
    *,
    mode: str = InferenceMode.NONE,
    base_url: str = OLLAMA_DEFAULT_URL,
) -> Proposal:
    """TRD-08.2 §7's `propose()` interface. Redaction is the unconditional
    first step (FR-LRN-028) — happens before any mode branching, so it can
    never be skipped by a caller choosing a mode.
    """

    # Unconditional redaction pre-step (the actual enforcement point).
    for _art, _lines, excerpt in t.source_lines:
        redact_secrets(excerpt)

    heuristic = propose_heuristic(t, fact_candidates)

    if mode == InferenceMode.HOSTED:
        raise PermissionError(
            "hosted inference mode is refused — air-gapped deployments must use "
            "'local' or 'none' (TRD-08.2 §5.4, NFR-DEP-001)"
        )

    if mode == InferenceMode.LOCAL and ollama_reachable(base_url):
        refined = refine_with_model(t, heuristic, fact_candidates, base_url=base_url)
        if refined is not None:
            return refined

    return heuristic
