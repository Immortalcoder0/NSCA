"""Template mining, relevance filtering and information-gain ordering —
TRD-08.1, Stages 2-3 of 08-learning-system.md §2.

Three reductions, applied in order (TRD-08.1 §4):

1. **Template collapse** (`mine_templates`) — corpus-wide positional
   variability, not per-line (DD-08.1-01, this is exactly why Drain3 was
   rejected — TECH-STACK.md §9: Drain3 clusters *within* a single log
   stream by shape-similarity heuristics; it has no notion of "this
   position varies across many occurrences of the same skeleton versus
   this position merely looks like a value", which is the actual criterion
   here). A token becomes a slot because it *varies* across occurrences
   sharing a skeleton, not because it looks like an IP/int/etc. — the
   pattern-based slot *typing* only decides the slot's declared type, never
   whether a position is a slot at all.
2. **Relevance filtering** (`score_relevance` / `filter_relevant`) — scored
   against the fact vocabulary the loaded controls require (§4.2).
3. **Information-gain ordering** (`order_questions`) — greedy, recomputed
   between rounds (DD-08.1-03), deterministic tie-breaks (INV-08.1-02).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from nsca_engine.api import UnmatchedConstruct

VARIABILITY_RATIO = 0.5
INITIAL_BUDGET = 12

# 08-learning-system.md §4.2 / TRD-08.1 §4.2 — vocabulary derived from
# loaded controls' `requires_facts` plus schema descriptions/synonyms
# (DD-08.1-01's own text), seeded here with the doc's explicit examples
# since this module has no network access to a live schema registry.
HIGH_RELEVANCE_VOCAB = frozenset({
    "telnet", "ssh", "snmp", "community", "password", "user", "group",
    "privilege", "radius", "tacacs", "log", "syslog", "logging", "ntp",
    "timeout", "cipher", "key", "certificate", "acl", "filter", "permit",
    "deny", "aaa", "api",
})

# 08-learning-system.md §4.2's own low-scoring example list, verbatim —
# extended only with the direct plurals/derivatives of the same words
# (`interface`/`interfaces`), never with unrelated words invented for this
# fixture's filler sections (that produced false suppressions during
# development — see the M3 report's judgment-call notes).
LOW_RELEVANCE_VOCAB = frozenset({
    "description", "comment", "vlan", "route", "bandwidth", "mtu", "name",
    "color",
})

# Known cross-platform synonyms (TRD-08.1 §4.2's "known synonyms", the same
# lexical gift TRD-08.4's synonym_index formalises across platforms) — a
# small seed table, not a hand-maintained substitute for the vocabulary
# itself (that remains schema/control-derived).
KNOWN_SYNONYMS: dict[str, frozenset[str]] = {
    "http": frozenset({"www", "web"}),
    "ssh": frozenset({"ssh"}),
    "telnet": frozenset({"telnet"}),
    "ftp": frozenset({"ftp"}),
    "api": frozenset({"api"}),
    "snmp": frozenset({"snmp", "community"}),
    "ntp": frozenset({"ntp"}),
    "radius": frozenset({"radius"}),
    "aaa": frozenset({"aaa"}),
}


def _expand_synonyms(words: set[str]) -> set[str]:
    """Bidirectional synonym expansion: a template observing `www` should
    also be considered to have observed `http` (the canonical/fact-side
    name), not just the reverse — `KNOWN_SYNONYMS` is keyed canonical ->
    observed-forms, so this builds the reverse index once per call."""

    expanded = set(words)
    for canonical, forms in KNOWN_SYNONYMS.items():
        if canonical in words or (words & forms):
            expanded.add(canonical)
            expanded |= forms
    return expanded

_CIDR_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}/\d{1,2}$")
_ADDR_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_INT_RE = re.compile(r"^-?\d+$")
_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
_QUOTED_RE = re.compile(r'^".*"$')


def _slot_type(values: list[str]) -> str:
    if all(_CIDR_RE.match(v) for v in values):
        return "cidr"
    if all(_ADDR_RE.match(v) for v in values):
        return "address"
    if all(_INT_RE.match(v) for v in values):
        return "integer"
    if all(_QUOTED_RE.match(v) for v in values):
        return "string"
    if all(_MAC_RE.match(v) for v in values):
        return "mac"
    if len(set(values)) / len(values) > VARIABILITY_RATIO:
        return "identifier"
    return "literal"


@dataclass(frozen=True, slots=True)
class Subtoken:
    kind: str  # "bare" | "kv_key" | "kv_val"
    value: str


def _tokenize(excerpt: str) -> tuple[Subtoken, ...]:
    out: list[Subtoken] = []
    # Selector brackets collapse to a single bare subtoken so their
    # interior is never mistaken for ordinary attributes (TRD-02.2 §3.7 —
    # "misclassifying a selector as attributes is a common inference
    # error"); this mirrors grammar_inference's own selector handling.
    stripped = re.sub(r"\[[^\[\]]*\]", "[SELECTOR]", excerpt.strip())
    for tok in stripped.split():
        if "=" in tok and not tok.startswith("="):
            key, _, val = tok.partition("=")
            out.append(Subtoken("kv_key", key))
            out.append(Subtoken("kv_val", val))
        else:
            out.append(Subtoken("bare", tok))
    return tuple(out)


@dataclass(frozen=True, slots=True)
class Slot:
    position: int
    slot_type: str
    observed_values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Template:
    template_id: str
    enclosing_path: str
    skeleton: str
    slots: tuple[Slot, ...]
    literal_tokens: tuple[str, ...]
    occurrence_count: int
    source_lines: tuple[tuple[str, tuple[int, ...], str], ...]  # (artifact_id, lines, excerpt)
    verb: str = ""
    # The shape signature (`_shape_signature`) — one label per subtoken
    # position ("bare", "key:<name>", "val"), preserved so rule_synthesis
    # can reconstruct a precise match pattern position-by-position rather
    # than re-deriving it from the human-readable `skeleton` string.
    shape: tuple[str, ...] = ()
    relevance: float = 0.0
    candidate_facts: tuple[str, ...] = ()


def _shape_signature(toks: tuple[Subtoken, ...]) -> tuple[str, ...]:
    """Key names are structurally load-bearing (DD-08.1-01's `disabled`
    example) — two lines whose key at the same position differ (`accept=`
    vs `reject-delay=`) are different constructs, not one skeleton with a
    "key slot". The shape signature therefore fixes every key name and
    every bare token's *position* (not its value) so grouping never merges
    two lines that only coincidentally share a verb and token count."""

    sig: list[str] = []
    for t in toks:
        if t.kind == "kv_key":
            sig.append(f"key:{t.value}")
        elif t.kind == "kv_val":
            sig.append("val")
        else:
            sig.append("bare")
    return tuple(sig)


def mine_templates(unmatched: list[UnmatchedConstruct]) -> list[Template]:
    """TRD-08.1 §4.1 — collapse lines into templates by *corpus-wide*
    positional variability within a shared (enclosing_path, verb, shape)
    (DD-08.1-01). INV-08.1-01: every source line is retained on its
    template (`source_lines`), so collapse is lossless."""

    groups: dict[tuple[str, str, tuple[str, ...]], list[UnmatchedConstruct]] = {}
    for uc in unmatched:
        path = ".".join(uc.parse_path) if uc.parse_path else "(root)"
        toks = _tokenize(uc.excerpt)
        if not toks:
            continue
        verb = toks[0].value
        key = (path, verb, _shape_signature(toks))
        groups.setdefault(key, []).append(uc)

    templates: list[Template] = []
    for (path, verb, shape), members in sorted(groups.items()):
        n_subtok = len(shape)
        per_position_values: list[list[str]] = [[] for _ in range(n_subtok)]
        for uc in members:
            toks = _tokenize(uc.excerpt)
            for i, t in enumerate(toks):
                per_position_values[i].append(t.value)

        slots: list[Slot] = []
        literal_tokens: list[str] = []
        skeleton_parts: list[str] = []
        for i in range(n_subtok):
            values = per_position_values[i]
            distinct = set(values)
            is_slot = len(members) >= 2 and len(distinct) > 1 and (len(distinct) / len(values)) > VARIABILITY_RATIO
            label = shape[i]
            if label.startswith("key:"):
                key_name = label[len("key:"):]
                literal_tokens.append(key_name)
                skeleton_parts.append(f"{key_name}=" if i + 1 < n_subtok and shape[i + 1] == "val" else key_name)
                continue
            if is_slot:
                stype = _slot_type(values)
                slots.append(Slot(position=i, slot_type=stype, observed_values=tuple(sorted(distinct))))
                skeleton_parts.append(f"<{stype}>")
            else:
                literal_tokens.append(values[0])
                skeleton_parts.append(values[0])

        skeleton = " ".join(skeleton_parts)
        source_lines = tuple((uc.artifact_id, uc.lines, uc.excerpt) for uc in members)
        template_id = f"{path}::{verb}::{'.'.join(shape)}"
        templates.append(
            Template(
                template_id=template_id,
                enclosing_path=path,
                skeleton=skeleton,
                slots=tuple(slots),
                literal_tokens=tuple(literal_tokens),
                occurrence_count=len(members),
                source_lines=source_lines,
                verb=verb,
                shape=shape,
            )
        )
    return templates


def _stem(word: str) -> str:
    """Trivial plural stemming (`groups` -> `group`, `communities` ->
    `communitie` -> handled below) — just enough that a fact path's plural
    collection name (`auth.local_groups`) matches a template's singular
    section name (`/user group`) without a hand-maintained synonym for
    every plural. Deliberately conservative: only strips a bare trailing
    `s` (and `ies`->`y`) on words long enough that this is unlikely to
    collide with something unrelated."""

    if word.endswith("ies") and len(word) > 5:
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss") and len(word) > 4:
        return word[:-1]
    return word


def _split_words(*chunks: str) -> set[str]:
    """Splits on `.`, `_`, `-`, `/` and whitespace — the delimiters both
    fact paths (`mgmt.protocols.telnet.enabled`) and vendor tokens
    (`strong-crypto`, `reject-delay`) use — so `strong-crypto` and a fact
    segment `strong_crypto` compare equal after splitting. Each segment is
    also stemmed (`_stem`) so `groups`/`group` and `communities`/`community`
    compare equal."""

    out: set[str] = set()
    for chunk in chunks:
        if not chunk:
            continue
        for seg in re.split(r"[./_\-\s]+", chunk.lower()):
            if seg:
                out.add(seg)
                out.add(_stem(seg))
    return out


# Generic property words that appear at the end of many unrelated fact
# paths (`*.enabled`, `*.configured`, `*.present`, ...) — matching on these
# alone produces false positives across every boolean-shaped fact in the
# vocabulary, which is not a real lexical/structural signal. Stripped from
# the *fact* side of matching (never from the template side, since a
# template genuinely containing e.g. `disabled=no` should still register
# `disabled`/`enabled` as ordinary vocabulary for relevance scoring).
_GENERIC_FACT_WORDS = frozenset({
    "enabled", "configured", "present", "set", "status", "ok", "defined",
})


def _template_word_bag(t: Template) -> set[str]:
    words: set[str] = set()
    for tok in t.literal_tokens:
        words |= _split_words(tok)
    for s in t.slots:
        for v in s.observed_values:
            words |= _split_words(v)
    words |= _split_words(t.enclosing_path)
    return words


def score_relevance(t: Template) -> float:
    """TRD-08.1 §4.2's `relevance()` — lexical proximity (w1) + structural
    proximity of the enclosing path (w2) + a light value-shape bonus (w3)
    for boolean-domain slots (the dominant shape of `mgmt.*.enabled`-style
    facts). Anomaly boost (w4, TRD-06.3 §3.7) is not implemented — this
    milestone has no peer-anomaly detector wired in, flagged rather than
    faked with a nonzero constant."""

    words = _template_word_bag(t)
    high_hits = len(words & HIGH_RELEVANCE_VOCAB)
    low_hits = len(words & LOW_RELEVANCE_VOCAB)
    lexical = high_hits - 0.5 * low_hits

    path_words = {seg.lower() for seg in re.split(r"[/\s]+", t.enclosing_path) if seg}
    structural = len(path_words & HIGH_RELEVANCE_VOCAB) * 0.5

    value_shape = 0.0
    for s in t.slots:
        if len(s.observed_values) <= 2 and s.slot_type in ("literal", "identifier"):
            value_shape += 0.25

    return lexical + structural + value_shape


def filter_relevant(templates: list[Template]) -> tuple[list[Template], list[Template]]:
    """DD-08.1-02 — filtering suppresses, it does not delete. Returns
    (relevant, suppressed); suppressed templates remain reachable via
    "show all" (the caller's responsibility to expose)."""

    relevant: list[Template] = []
    suppressed: list[Template] = []
    for t in templates:
        scored = replace(t, relevance=score_relevance(t))
        (relevant if scored.relevance > 0 else suppressed).append(scored)
    return relevant, suppressed


def candidate_fact_paths(t: Template, fact_vocab: list[str]) -> tuple[str, ...]:
    """A rough (stage-3) guess of which schema facts a template might
    resolve, used only to estimate information gain before real semantic
    proposal (TRD-08.2, stage 4) exists. Matches template words (literal
    tokens, observed slot values, enclosing-path segments) against each
    candidate fact path's dot-separated segments, expanded through
    `KNOWN_SYNONYMS`."""

    expanded = _expand_synonyms(_template_word_bag(t))

    out = []
    for fact in fact_vocab:
        segments = _split_words(fact) - _GENERIC_FACT_WORDS
        if not segments:
            segments = _split_words(fact)  # an all-generic path still needs something to match
        if segments & expanded:
            out.append(fact)
    return tuple(sorted(out))


def _assign_facts_to_sections(
    by_section: dict[str, list[Template]], fact_vocab: list[str]
) -> dict[str, set[str]]:
    """Resolves each candidate fact to the single *best*-matching section
    rather than letting every section whose vocabulary merely intersects a
    fact's claim it — real vendor sections legitimately share vocabulary
    (a `/user aaa` line mentioning `radius` and a `/radius incoming`
    section both genuinely relate to RADIUS), so a boolean any-overlap test
    lets a fact be claimed by more than one section arbitrarily, which
    starves whichever section the greedy loop visits second. Breaking the
    tie by strength-of-match (most overlapping words, ties broken by
    section name) keeps each fact single-owned and the resulting ordering
    deterministic (INV-08.1-02) without hand-tuning the vocabulary further."""

    section_words: dict[str, set[str]] = {}
    for section, tpls in by_section.items():
        words: set[str] = set()
        for t in tpls:
            words |= _template_word_bag(t)
        section_words[section] = _expand_synonyms(words)

    owner: dict[str, str] = {}
    for fact in fact_vocab:
        segments = _split_words(fact) - _GENERIC_FACT_WORDS
        if not segments:
            segments = _split_words(fact)
        best_section = None
        best_score = 0
        for section in sorted(section_words):
            score = len(section_words[section] & segments)
            if score > best_score:
                best_section, best_score = section, score
        if best_section is not None:
            owner[fact] = best_section

    result: dict[str, set[str]] = {section: set() for section in by_section}
    for fact, section in owner.items():
        result[section].add(fact)
    return result


@dataclass(frozen=True, slots=True)
class RequiredControlLike:
    control_id: str
    requires_facts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Question:
    rank: int
    section: str
    templates: tuple[Template, ...]
    gain: int
    controls_unlocked: tuple[str, ...]
    facts_resolved: int


def order_questions(
    templates: list[Template],
    controls: list[RequiredControlLike],
    *,
    budget: int = INITIAL_BUDGET,
) -> list[Question]:
    """TRD-08.1 §4.3/§4.5 — group templates sharing an enclosing path into
    one question (§4.5: "one question, multiple mappings"), then greedily
    order by information gain, recomputed after each pick (DD-08.1-03).
    Ties break on relevance, then frequency, then a stable identifier
    (INV-08.1-02): here, section name (deterministic ordering key)."""

    fact_vocab = sorted({f for c in controls for f in c.requires_facts})

    by_section: dict[str, list[Template]] = {}
    for t in templates:
        by_section.setdefault(t.enclosing_path, []).append(t)

    section_facts = _assign_facts_to_sections(by_section, fact_vocab)

    resolved_controls: set[str] = set()
    resolved_facts: set[str] = set()
    remaining_sections = set(by_section)
    ordered: list[Question] = []
    rank = 1

    while remaining_sections and len(ordered) < budget:
        best_section = None
        best_gain = -1
        best_unlocked: tuple[str, ...] = ()
        for section in sorted(remaining_sections):
            facts = section_facts[section] - resolved_facts
            unlocked = tuple(
                sorted(
                    c.control_id
                    for c in controls
                    if c.control_id not in resolved_controls
                    and set(c.requires_facts) <= (resolved_facts | facts)
                    and set(c.requires_facts) & facts
                )
            )
            gain = len(unlocked)
            section_relevance = sum(t.relevance for t in by_section[section])
            section_freq = sum(t.occurrence_count for t in by_section[section])
            if best_section is None:
                is_better = True
            else:
                cur_relevance = sum(t.relevance for t in by_section[best_section])
                cur_freq = sum(t.occurrence_count for t in by_section[best_section])
                is_better = (
                    gain > best_gain
                    or (gain == best_gain and section_relevance > cur_relevance)
                    or (gain == best_gain and section_relevance == cur_relevance and section_freq > cur_freq)
                    or (
                        gain == best_gain
                        and section_relevance == cur_relevance
                        and section_freq == cur_freq
                        and section < best_section
                    )
                )
            if is_better:
                best_section = section
                best_gain = gain
                best_unlocked = unlocked

        assert best_section is not None
        remaining_sections.discard(best_section)
        if best_gain <= 0:
            continue  # no more controls to unlock — stop presenting further questions
        facts_here = section_facts[best_section] - resolved_facts
        resolved_facts |= facts_here
        resolved_controls |= set(best_unlocked)
        ordered.append(
            Question(
                rank=rank,
                section=best_section,
                templates=tuple(by_section[best_section]),
                gain=best_gain,
                controls_unlocked=best_unlocked,
                facts_resolved=len(facts_here),
            )
        )
        rank += 1

    return ordered


@dataclass(frozen=True, slots=True)
class TrainingQueue:
    templates: tuple[Template, ...]
    questions: tuple[Question, ...]
    suppressed_count: int
    total_templates: int


def mine(
    unmatched: list[UnmatchedConstruct],
    controls: list[RequiredControlLike],
    *,
    budget: int = INITIAL_BUDGET,
) -> TrainingQueue:
    """TRD-08.1 §5's full interface: collapse -> filter -> order."""

    templates = mine_templates(unmatched)
    relevant, suppressed = filter_relevant(templates)
    questions = order_questions(relevant, controls, budget=budget)
    return TrainingQueue(
        templates=tuple(relevant),
        questions=tuple(questions),
        suppressed_count=len(suppressed),
        total_templates=len(templates),
    )
