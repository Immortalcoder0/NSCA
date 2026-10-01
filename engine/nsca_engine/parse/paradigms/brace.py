"""P3 · Brace nesting structurer (TRD-02.1 §3.3, Juniper curly-format).

Conventional block nesting; statements terminated by ``;``. Comments (``#``
full-line, ``/* ... */`` inline) are stripped before structural
interpretation. Per §3.6, unbalanced braces at end of input is a
*contaminating* error (an unclosed brace changes the meaning of everything
that follows) and is therefore a hard failure: ``status = "refused"``,
mirroring how ``indentation.py`` refuses below the 0.50 coverage threshold
and how the M1 pipeline already treats ``status == "refused"`` uniformly
(``api.py`` raises rather than emitting facts nobody could trust, G2).

Simplification (flagged, M2): quoted-string awareness is limited to double
quotes on a single line (``"...="``) — sufficient to keep a brace character
inside a quoted description from corrupting nesting in the hand-written
fixtures this milestone targets; a brace spanning a multi-line quoted string
is not modelled.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from nsca_engine.parse.grammar import Node, ParseResult, ParseTree, split_lines

_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/")


@dataclass(frozen=True, slots=True)
class BraceGrammarSpec:
    line_comment_char: str = "#"


def _strip_quoted_braces(s: str) -> str:
    """Blank out brace/semicolon characters inside double-quoted spans so
    they are not mistaken for structural tokens (best-effort, single-line)."""

    out = []
    in_quotes = False
    for ch in s:
        if ch == '"':
            in_quotes = not in_quotes
            out.append(ch)
        elif in_quotes and ch in "{};":
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def parse(artifact_id: str, text: str, grammar: BraceGrammarSpec) -> ParseResult:
    # Strip block comments first (they may span multiple lines); replace with
    # matching blank lines so line numbers are preserved.
    def _blank_out(m: re.Match[str]) -> str:
        return "\n" * m.group(0).count("\n")

    text = _BLOCK_COMMENT_RE.sub(_blank_out, text)
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

    stack: list[tuple[int, tuple[str, ...]]] = [(root_id, ())]
    errors: list[str] = []
    matched_count = 0
    total_nonblank = 0
    unbalanced = False

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

        if stripped.startswith(grammar.line_comment_char):
            nid = new_id()
            nodes[nid] = Node(
                id=nid, parent=root_id, children=(), path=(), verb=None,
                head=grammar.line_comment_char, attributes={}, operands=(),
                line_start=lineno, line_end=lineno, kind="comment",
            )
            children_acc[root_id].append(nid)
            continue

        total_nonblank += 1
        clean = _strip_quoted_braces(stripped)
        parent_id, parent_path = stack[-1]

        if clean == "}" or (clean.endswith("}") and clean.count("}") == 1 and clean.count("{") == 0 and len(stack) > 1):
            if len(stack) <= 1:
                unbalanced = True
                errors.append(f"line {lineno}: unmatched closing brace")
                continue
            closing_id, _ = stack.pop()
            closed = nodes[closing_id]
            nodes[closing_id] = Node(
                id=closed.id, parent=closed.parent, children=closed.children,
                path=closed.path, verb=closed.verb, head=closed.head,
                attributes=closed.attributes, operands=closed.operands,
                line_start=closed.line_start, line_end=lineno, kind=closed.kind,
            )
            matched_count += 1
            continue

        if clean.endswith("{"):
            header = clean[:-1].strip()
            tokens = header.split()
            head = tokens[0] if tokens else ""
            node_path = parent_path + (header,)
            nid = new_id()
            nodes[nid] = Node(
                id=nid, parent=parent_id, children=(), path=node_path, verb=None,
                head=head, attributes={}, operands=tuple(tokens[1:]),
                line_start=lineno, line_end=lineno, kind="container",
            )
            children_acc[nid] = []
            children_acc[parent_id].append(nid)
            stack.append((nid, node_path))
            matched_count += 1
            continue

        if clean.endswith(";"):
            body = clean[:-1].strip()
            tokens = body.split()
            head = tokens[0] if tokens else ""
            attributes = {tokens[0]: " ".join(tokens[1:])} if len(tokens) >= 2 else {}
            node_path = parent_path + (body,)
            nid = new_id()
            nodes[nid] = Node(
                id=nid, parent=parent_id, children=(), path=node_path, verb=None,
                head=head, attributes=attributes, operands=tuple(tokens[1:]),
                line_start=lineno, line_end=lineno, kind="statement",
            )
            children_acc[parent_id].append(nid)
            matched_count += 1
            continue

        # unrecognised line inside a block — retained, never dropped (§3.6)
        nid = new_id()
        nodes[nid] = Node(
            id=nid, parent=parent_id, children=(), path=parent_path + (stripped,),
            verb=None, head=stripped.split()[0] if stripped.split() else "",
            attributes={}, operands=(), line_start=lineno, line_end=lineno, kind="unmatched",
        )
        children_acc[parent_id].append(nid)

    if len(stack) > 1:
        unbalanced = True
        errors.append("unbalanced braces: unclosed block(s) at end of input")

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

    if unbalanced:
        status = "refused"
    elif total_nonblank and coverage < Fraction(1, 2):
        status = "refused"
    elif coverage < 1:
        status = "parsed_with_gaps"
    else:
        status = "parsed"

    return ParseResult(
        tree=tree, coverage=coverage, unmatched=(), errors=tuple(errors),
        status=status, paradigm_used="brace",
        node_count=len(finalized) - 1, max_depth=max_depth,
    )
