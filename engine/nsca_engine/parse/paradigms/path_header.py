"""P6 · Path headers with key-value structurer (TRD-02.1 §3.3, MikroTik
RouterOS).

A ``/path`` line opens a container that persists until the next ``/path``
line (RouterOS export syntax has no closing delimiter — the next path header
implicitly closes the previous section). Statement lines
(``add``/``set``/``remove``/``enable``/``disable``/...) are parsed as
``verb key=value key=value ...``; a bracketed selector (``[ find
default=yes ]``) is parsed as a single selector operand, not as attributes,
per the TRD's explicit instruction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from nsca_engine.parse.grammar import Node, ParseResult, ParseTree, split_lines

_SELECTOR_RE = re.compile(r"\[[^\]]*\]")
_KV_RE = re.compile(r'(\S+?)=("(?:[^"\\]|\\.)*"|\S+)')


@dataclass(frozen=True, slots=True)
class PathHeaderGrammarSpec:
    comment_char: str = "#"


def _parse_kv(s: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in _KV_RE.finditer(s):
        key, value = m.group(1), m.group(2)
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        out[key] = value
    return out


def parse(artifact_id: str, text: str, grammar: PathHeaderGrammarSpec) -> ParseResult:
    lines = split_lines(text)
    nodes: dict[int, Node] = {}
    children_acc: dict[int, list[int]] = {}
    next_id = 0

    def new_id() -> int:
        nonlocal next_id
        next_id += 1
        return next_id

    root_id = 0
    nodes[root_id] = Node(
        id=root_id, parent=None, children=(), path=(), verb=None, head="",
        attributes={}, operands=(), line_start=0, line_end=0, kind="container",
    )
    children_acc[root_id] = []

    errors: list[str] = []
    matched_count = 0
    total_nonblank = 0

    current_container_id = root_id
    current_path: tuple[str, ...] = ()
    stmt_counter: dict[tuple[str, ...], int] = {}

    for i, raw_line in enumerate(lines):
        lineno = i + 1
        stripped = raw_line.strip()
        if stripped == "":
            nid = new_id()
            nodes[nid] = Node(
                id=nid, parent=root_id, children=(), path=(), verb=None, head="",
                attributes={}, operands=(), line_start=lineno, line_end=lineno, kind="blank",
            )
            children_acc[root_id].append(nid)
            continue

        if stripped.startswith(grammar.comment_char):
            nid = new_id()
            nodes[nid] = Node(
                id=nid, parent=root_id, children=(), path=(), verb=None,
                head=grammar.comment_char, attributes={}, operands=(),
                line_start=lineno, line_end=lineno, kind="comment",
            )
            children_acc[root_id].append(nid)
            continue

        total_nonblank += 1

        if stripped.startswith("/"):
            # `/ip service` -> path components are whitespace-separated
            # words after the leading `/`, not further `/`-separated
            # segments (RouterOS export syntax has exactly one `/` per
            # header line).
            segments = tuple(stripped[1:].split())
            nid = new_id()
            nodes[nid] = Node(
                id=nid, parent=root_id, children=(), path=segments, verb=None,
                head=segments[-1] if segments else "", attributes={}, operands=(),
                line_start=lineno, line_end=lineno, kind="container",
            )
            children_acc[nid] = []
            children_acc[root_id].append(nid)
            current_container_id = nid
            current_path = segments
            matched_count += 1
            continue

        # statement line: VERB [selector] key=value ...
        selector_match = _SELECTOR_RE.search(stripped)
        selector = selector_match.group(0) if selector_match else None
        rest = _SELECTOR_RE.sub("", stripped).strip()
        tokens = rest.split(None, 1)
        verb = tokens[0] if tokens else stripped
        kv_part = tokens[1] if len(tokens) > 1 else ""
        attributes = _parse_kv(kv_part)
        operands = (selector,) if selector else ()

        idx = stmt_counter.get(current_path, 0)
        stmt_counter[current_path] = idx + 1
        node_path = current_path + (f"{verb}[{idx}]",)

        nid = new_id()
        nodes[nid] = Node(
            id=nid, parent=current_container_id, children=(), path=node_path,
            verb=verb, head=verb, attributes=attributes, operands=operands,
            line_start=lineno, line_end=lineno, kind="statement",
        )
        children_acc[current_container_id].append(nid)
        matched_count += 1

    finalized: dict[int, Node] = {}
    for nid, node in nodes.items():
        kids = tuple(children_acc.get(nid, []))
        finalized[nid] = Node(
            id=node.id, parent=node.parent, children=kids, path=node.path,
            verb=node.verb, head=node.head, attributes=node.attributes,
            operands=node.operands, line_start=node.line_start,
            line_end=node.line_end, kind=node.kind, context=node.context,
            context_params=node.context_params,
        )

    tree = ParseTree(artifact_id=artifact_id, lines=lines, nodes=finalized, root_id=root_id)
    coverage = Fraction(matched_count, total_nonblank) if total_nonblank else Fraction(1, 1)
    max_depth = max((len(n.path) for n in finalized.values()), default=0)

    status = "parsed"
    if total_nonblank and coverage < Fraction(1, 2):
        status = "refused"
    elif coverage < 1:
        status = "parsed_with_gaps"

    return ParseResult(
        tree=tree, coverage=coverage, unmatched=(), errors=tuple(errors),
        status=status, paradigm_used="path_header",
        node_count=len(finalized) - 1, max_depth=max_depth,
    )
