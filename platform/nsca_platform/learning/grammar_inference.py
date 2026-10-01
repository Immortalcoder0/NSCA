"""Grammar inference — TRD-02.2, purely statistical, no model (DD-02.2-01).

Recovers an unknown configuration format's *structure* — comment character,
hierarchy paradigm, statement shape, verbs, selectors — with zero semantic
understanding and zero human input, then reports how much of the artifact
that structure accounts for (`coverage`). This is Stage 1 of the pipeline
(08-learning-system.md §2): syntax is inferable statistically; semantics is
not, and inference stops precisely at that boundary (TRD-02.2 §3.1).

Six paradigms are scored (TRD-02.2 §3.5); the highest wins only if it clears
an absolute threshold *and* a margin over the runner-up (DD-02.2-02) —
otherwise inference escalates rather than guessing, because a wrong paradigm
produces a plausible-looking but wrong parse tree, which is worse than
admitting the format is unhandled (same principle as G2/INV-02.2-01).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field, replace

PARADIGMS = ("indentation", "flat_path", "brace", "block_keyword", "xml", "path_header")

_COMMENT_CANDIDATES = ("#", "!", ";", "//", "/*", "--", '"')

_ACCEPT_THRESHOLD = 0.70
_ACCEPT_MARGIN = 0.15

# TRD-02.2 §3.8 coverage bands.
_COVERAGE_ACCEPT = 0.95
_COVERAGE_ACCEPT_WITH_GAPS = 0.80
_COVERAGE_WARNING = 0.50


@dataclass(frozen=True, slots=True)
class GrammarHypothesis:
    comment_char: str | None
    paradigm: str | None
    paradigm_confidence: float
    statement_shape: str
    quoting: str
    verbs: tuple[str, ...]
    selectors: tuple[str, ...]
    path_prefix: str | None
    verbatim_regions: tuple[tuple[int, int], ...]
    coverage: float
    status: str  # accepted | accepted_with_gaps | warning | rejected
    paradigm_scores: dict[str, float] = field(default_factory=dict)
    corroborating_artifacts: int = 0
    total_lines: int = 0
    matched_lines: int = 0
    unmatched_line_numbers: tuple[int, ...] = ()
    refusal_message: str | None = None


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _mean_token_entropy(lines: list[str]) -> float:
    if not lines:
        return 0.0
    return sum(_shannon_entropy(l) for l in lines) / len(lines)


def detect_comment_char(lines: list[str]) -> str | None:
    """TRD-02.2 §3.3. The `log(1 + |L_c|)` term suppresses a single stray
    line beginning with an unusual character from outscoring the real
    comment character in a configuration with few comments."""

    best_char: str | None = None
    best_score = 0.0
    for cand in _COMMENT_CANDIDATES:
        l_c = [l for l in lines if l.lstrip().startswith(cand)]
        if len(l_c) < 2:
            continue
        assign_hits = sum(
            1
            for l in l_c
            if "=" in l or (":" in l and not l.strip().startswith("http"))
        )
        assign_rate = assign_hits / len(l_c)
        entropy = _mean_token_entropy([l.lstrip()[len(cand):] for l in l_c])
        score = entropy * (1 - assign_rate) * math.log(1 + len(l_c))
        if score > best_score:
            best_score = score
            best_char = cand
    return best_char if best_score > 0.3 else None


_PEM_BEGIN = re.compile(r"^-----BEGIN [^-]+-----$")
_PEM_END = re.compile(r"^-----END [^-]+-----$")
_BASE64_LINE = re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$")


def detect_verbatim_regions(lines: list[str]) -> list[tuple[int, int]]:
    """TRD-02.2 §3.4 — PEM blocks and long base64 runs, excluded from
    structural statistics before paradigm scoring (they severely distort it
    otherwise)."""

    regions: list[tuple[int, int]] = []
    i = 0
    n = len(lines)
    while i < n:
        stripped = lines[i].strip()
        if _PEM_BEGIN.match(stripped):
            start = i
            j = i + 1
            while j < n and not _PEM_END.match(lines[j].strip()):
                j += 1
            end = min(j, n - 1)
            regions.append((start, end))
            i = end + 1
            continue
        if _BASE64_LINE.match(stripped):
            start = i
            j = i
            while j < n and _BASE64_LINE.match(lines[j].strip()):
                j += 1
            if j - start >= 3:
                regions.append((start, j - 1))
                i = j
                continue
        i += 1
    return regions


def _is_comment(line: str, comment_char: str | None) -> bool:
    return comment_char is not None and line.lstrip().startswith(comment_char)


def _indentation_score(lines: list[str]) -> float:
    if not lines:
        return 0.0
    indents = [len(l) - len(l.lstrip(" \t")) for l in lines if l.strip()]
    if not indents:
        return 0.0
    depths = sorted(set(indents))
    fraction_indented = sum(1 for i in indents if i > 0) / len(indents)
    depth_score = min(1.0, (len(depths) - 1) / 3) if len(depths) >= 2 else 0.0
    if len(depths) < 2 or fraction_indented < 0.20:
        return 0.05 + 0.1 * fraction_indented
    return 0.5 * depth_score + 0.5 * fraction_indented


def _common_prefix_len(a: list[str], b: list[str]) -> int:
    n = 0
    for x, y in zip(a, b, strict=False):  # common prefix of possibly different-length lists
        if x != y:
            break
        n += 1
    return n


def _flat_path_score(lines: list[str]) -> float:
    stmt = [l.strip() for l in lines if l.strip()]
    if not stmt:
        return 0.0
    firsts = [l.split()[0] for l in stmt if l.split()]
    if not firsts:
        return 0.0
    dominant = Counter(firsts).most_common(1)[0][1] / len(firsts)
    toks = [l.split() for l in stmt]
    prefixes = [
        _common_prefix_len(toks[i], toks[i + 1]) for i in range(len(toks) - 1)
    ]
    mean_prefix = sum(prefixes) / len(prefixes) if prefixes else 0.0
    if dominant < 0.70:
        return 0.05 + 0.2 * dominant
    return 0.5 * dominant + 0.5 * min(1.0, mean_prefix / 2)


def _brace_score(lines: list[str]) -> float:
    text = "\n".join(lines)
    opens = text.count("{")
    closes = text.count("}")
    if opens == 0:
        return 0.0
    balance_ok = opens == closes
    depth = 0
    max_depth = 0
    for ch in text:
        if ch == "{":
            depth += 1
            max_depth = max(max_depth, depth)
        elif ch == "}":
            depth = max(0, depth - 1)
    if not balance_ok:
        return 0.05
    return 0.5 * (1.0 if balance_ok else 0.0) + 0.5 * min(1.0, max_depth / 3)


_BLOCK_OPENERS = {"config", "edit", "route", "interface", "begin"}
_BLOCK_CLOSERS = {"end", "next"}


def _block_keyword_score(lines: list[str]) -> float:
    stmt = [l.strip() for l in lines if l.strip()]
    if not stmt:
        return 0.0
    opens = 0
    closes = 0
    pair_types: set[str] = set()
    depth = 0
    max_depth = 0
    for l in stmt:
        head = l.split()[0].lower() if l.split() else ""
        if head in _BLOCK_OPENERS:
            opens += 1
            depth += 1
            max_depth = max(max_depth, depth)
            pair_types.add(head)
        elif head in _BLOCK_CLOSERS:
            closes += 1
            depth = max(0, depth - 1)
            pair_types.add(head)
    if opens == 0:
        return 0.0
    balance_score = 1.0 - min(1.0, abs(opens - closes) / max(opens, 1))
    type_bonus = 0.2 if len(pair_types) >= 2 else 0.0
    return min(1.0, 0.5 * balance_score + 0.3 * min(1.0, max_depth / 2) + type_bonus)


def _xml_score(text: str) -> float:
    stripped = text.strip()
    if not stripped.startswith("<"):
        return 0.0
    try:
        import xml.etree.ElementTree as ET

        ET.fromstring(stripped)
        return 1.0
    except Exception:
        return 0.0


def _path_header_score(lines: list[str]) -> float:
    stmt = [l for l in lines if l.strip()]
    if not stmt:
        return 0.0
    headers = [l for l in stmt if l.strip().startswith("/") and "=" not in l and not l.startswith((" ", "\t"))]
    bodies = [l for l in stmt if "=" in l]
    if not headers:
        return 0.0
    header_fraction = len(headers) / len(stmt)
    body_fraction = len(bodies) / len(stmt) if bodies else 0.0
    # Alternation: how often a header line is followed (anywhere later, since
    # bodies apply until the next header) by at least one body line before
    # the next header — a weak but cheap corroborating signal.
    return min(1.0, 0.5 * min(1.0, header_fraction * 4) + 0.5 * min(1.0, body_fraction * 1.3))


def score_paradigms(lines: list[str]) -> dict[str, float]:
    text = "\n".join(lines)
    return {
        "indentation": _indentation_score(lines),
        "flat_path": _flat_path_score(lines),
        "brace": _brace_score(lines),
        "block_keyword": _block_keyword_score(lines),
        "xml": _xml_score(text),
        "path_header": _path_header_score(lines),
    }


def _detect_statement_shape(lines: list[str]) -> tuple[str, str]:
    stmt = [l for l in lines if l.strip()]
    if not stmt:
        return "positional", "none"
    eq = sum(l.count("=") for l in stmt)
    colon = sum(l.count(":") for l in stmt)
    eq_density = eq / len(stmt)
    colon_density = colon / len(stmt)
    if eq_density >= 0.8:
        shape = "key_value"
    elif colon_density >= 0.8:
        shape = "colon_key_value"
    else:
        shape = "positional"

    quote_pairs = sum(l.count('"') for l in stmt) // 2
    quoting = "double_quote" if quote_pairs > 0 else "none"
    return shape, quoting


def _detect_verbs(lines: list[str]) -> tuple[str, ...]:
    stmt = [l.strip() for l in lines if l.strip()]
    if not stmt:
        return ()
    firsts = [l.split()[0] for l in stmt if l.split() and not l.startswith("/")]
    if not firsts:
        return ()
    counts = Counter(firsts)
    total = len(firsts)
    candidates = [tok for tok, c in counts.items() if c / total >= 0.10]
    if len(set(candidates)) > 8:
        candidates = [tok for tok, _ in counts.most_common(8)]
    return tuple(sorted(set(candidates)))


_SELECTOR_RE = re.compile(r"\[\s*[^\[\]]+?\s*\]")


def _detect_selectors(lines: list[str]) -> tuple[str, ...]:
    found: set[str] = set()
    for l in lines:
        for m in _SELECTOR_RE.finditer(l):
            found.add(m.group(0))
    return tuple(sorted(found))[:20]


_KV_TOKEN = re.compile(r"^\S+=\S*$")


def _line_matches_grammar(
    line: str,
    *,
    comment_char: str | None,
    paradigm: str,
    verbs: tuple[str, ...],
) -> bool:
    stripped = line.strip()
    if not stripped:
        return True  # blank lines are structurally accounted for
    if _is_comment(line, comment_char):
        return True
    if paradigm == "path_header":
        if stripped.startswith("/") and "=" not in stripped:
            return True
        # "<verb> [selector] [positional-target] <key>=<value> ..." — RouterOS
        # (and this paradigm generally) allows a bare positional token before
        # the key=value run, e.g. `set telnet disabled=no port=23` (`telnet`
        # names the target, it is not itself a key=value pair). Once the
        # first key=value token appears, every remaining token must also be
        # key=value shaped; leading non-kv tokens are tolerated as the
        # positional target/selector.
        first = stripped.split()[0] if stripped.split() else ""
        if verbs and first in verbs:
            rest = _SELECTOR_RE.sub("", stripped)
            tokens = rest.split()[1:]
            if not tokens:
                return True
            seen_kv = False
            for t in tokens:
                is_kv = bool(_KV_TOKEN.match(t)) or t in ("[", "]")
                if is_kv:
                    seen_kv = True
                elif seen_kv:
                    return False  # a non-kv token after kv tokens began — not this shape
            return True
        return False
    if paradigm == "block_keyword":
        first = stripped.split()[0].lower() if stripped.split() else ""
        if first in _BLOCK_OPENERS or first in _BLOCK_CLOSERS:
            return True
        if "=" in stripped or (verbs and first in verbs):
            return True
        return False
    if paradigm == "indentation":
        return True  # indentation lines are structurally valid by construction
    if paradigm == "flat_path":
        first = stripped.split()[0] if stripped.split() else ""
        return bool(verbs) and first in verbs
    if paradigm == "brace":
        return True
    if paradigm == "xml":
        return True
    return False


def infer_grammar(text: str, *, corroborating_artifacts: int = 0) -> GrammarHypothesis:
    """TRD-02.2's full pipeline: comment char -> verbatim regions -> paradigm
    scoring -> statement shape -> verbs/selectors -> assembly + coverage
    validation (§3.2)."""

    raw_lines = text.splitlines()
    if not raw_lines:
        return GrammarHypothesis(
            comment_char=None, paradigm=None, paradigm_confidence=0.0, statement_shape="none",
            quoting="none", verbs=(), selectors=(), path_prefix=None, verbatim_regions=(),
            coverage=0.0, status="rejected", paradigm_scores={}, corroborating_artifacts=corroborating_artifacts,
            total_lines=0, matched_lines=0, unmatched_line_numbers=(),
            refusal_message="Empty artifact.",
        )

    verbatim_regions = detect_verbatim_regions(raw_lines)
    verbatim_idx: set[int] = set()
    for start, end in verbatim_regions:
        verbatim_idx.update(range(start, end + 1))

    comment_char = detect_comment_char(raw_lines)
    stat_lines = [l for i, l in enumerate(raw_lines) if i not in verbatim_idx and not _is_comment(l, comment_char)]

    scores = score_paradigms(stat_lines)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_paradigm, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = best_score - second_score

    ambiguous = not (best_score >= _ACCEPT_THRESHOLD and margin >= _ACCEPT_MARGIN)

    if ambiguous:
        return GrammarHypothesis(
            comment_char=comment_char, paradigm=None, paradigm_confidence=best_score,
            statement_shape="unknown", quoting="unknown", verbs=(), selectors=(),
            path_prefix=None, verbatim_regions=tuple(verbatim_regions), coverage=0.0,
            status="rejected", paradigm_scores=scores, corroborating_artifacts=corroborating_artifacts,
            total_lines=len(raw_lines), matched_lines=0, unmatched_line_numbers=(),
            refusal_message=(
                f"Paradigm ambiguous: best={best_paradigm!r} ({best_score:.2f}), "
                f"margin={margin:.2f} < {_ACCEPT_MARGIN}. Assisted grammar authoring required."
            ),
        )

    statement_shape, quoting = _detect_statement_shape(stat_lines)
    verbs = _detect_verbs(stat_lines)
    selectors = _detect_selectors(stat_lines)
    path_prefix = "/" if best_paradigm == "path_header" else None

    unmatched: list[int] = []
    matched = 0
    total = 0
    for i, line in enumerate(raw_lines):
        if i in verbatim_idx:
            matched += 1
            total += 1
            continue
        if not line.strip():
            continue  # blanks excluded from the denominator entirely
        total += 1
        if _line_matches_grammar(line, comment_char=comment_char, paradigm=best_paradigm, verbs=verbs):
            matched += 1
        else:
            unmatched.append(i + 1)

    coverage = matched / total if total else 0.0

    if coverage >= _COVERAGE_ACCEPT:
        status = "accepted"
    elif coverage >= _COVERAGE_ACCEPT_WITH_GAPS:
        status = "accepted_with_gaps"
    elif coverage >= _COVERAGE_WARNING:
        status = "warning"
    else:
        status = "rejected"

    refusal = None
    if status == "rejected":
        refusal = (
            f"⚠ Grammar inference achieved {coverage * 100:.0f}% line coverage.\n"
            "  Structure could not be reliably determined.\n"
            "  → Assisted grammar authoring required, or supply an alternative export format."
        )

    return GrammarHypothesis(
        comment_char=comment_char, paradigm=best_paradigm, paradigm_confidence=best_score,
        statement_shape=statement_shape, quoting=quoting, verbs=verbs, selectors=selectors,
        path_prefix=path_prefix, verbatim_regions=tuple(verbatim_regions), coverage=coverage,
        status=status, paradigm_scores=scores, corroborating_artifacts=corroborating_artifacts,
        total_lines=total, matched_lines=matched, unmatched_line_numbers=tuple(unmatched),
        refusal_message=refusal,
    )


def infer_platform(artifacts: list[str]) -> list[GrammarHypothesis]:
    """TRD-02.2 §3.9 — corroboration across sibling artifacts. Runs
    inference on each and reports whether paradigms agree; agreement raises
    confidence (recorded via `corroborating_artifacts`), disagreement is
    left visible to the caller rather than silently voted on."""

    hyps = [infer_grammar(a) for a in artifacts]
    paradigms = {h.paradigm for h in hyps if h.paradigm is not None}
    if len(paradigms) == 1 and len(hyps) > 1:
        n = len(hyps)
        hyps = [replace(h, corroborating_artifacts=n) for h in hyps]
    return hyps
