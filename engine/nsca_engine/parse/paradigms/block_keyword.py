"""P4 · Block keyword structurer (TRD-02.1 §3.3, FortiOS).

Two nesting mechanisms operate simultaneously: ``config``/``end`` and
``edit``/``next``. Per §3.6/DD-02.1-04, an unbalanced ``end`` (or ``next``)
changes the meaning of everything that follows — a *contaminating* error —
so it is a hard failure (``status = "refused"``), not a locally-recovered
one, exactly as the TRD's own failure-mode table requires.

``set``/``unset``/``append``/``select`` statement lines become ``statement``
nodes; ``config``/``edit`` open ``container`` nodes (``config_block``/
``edit_block`` recorded in ``context`` for downstream scope-selection,
mirroring how ``indentation.py`` records ``vty_range``).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from nsca_engine.parse.grammar import Node, ParseResult, ParseTree, split_lines

_STATEMENT_VERBS = frozenset({"set", "unset", "append", "select", "unselect"})


@dataclass(frozen=True, slots=True)
class BlockKeywordGrammarSpec:
    comment_char: str = "#"


def parse(artifact_id: str, text: str, grammar: BlockKeywordGrammarSpec) -> ParseResult:
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

    # stack entries: (node_id, path, block_kind) block_kind in {"config","edit"}
    stack: list[tuple[int, tuple[str, ...], str]] = [(root_id, (), "root")]
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
        tokens = stripped.split()
        head_token = tokens[0].lower()
        parent_id, parent_path, _ = stack[-1]

        if head_token == "config":
            name = " ".join(tokens[1:])
            node_path = parent_path + (stripped,)
            nid = new_id()
            nodes[nid] = Node(
                id=nid, parent=parent_id, children=(), path=node_path, verb=None,
                head="config", attributes={}, operands=tuple(tokens[1:]),
                line_start=lineno, line_end=lineno, kind="container",
                context="config_block", context_params={"name": name},
            )
            children_acc[nid] = []
            children_acc[parent_id].append(nid)
            stack.append((nid, node_path, "config"))
            matched_count += 1
            continue

        if head_token == "edit":
            name = " ".join(tokens[1:]).strip('"')
            node_path = parent_path + (stripped,)
            nid = new_id()
            nodes[nid] = Node(
                id=nid, parent=parent_id, children=(), path=node_path, verb=None,
                head="edit", attributes={}, operands=tuple(tokens[1:]),
                line_start=lineno, line_end=lineno, kind="container",
                context="edit_block", context_params={"name": name},
            )
            children_acc[nid] = []
            children_acc[parent_id].append(nid)
            stack.append((nid, node_path, "edit"))
            matched_count += 1
            continue

        if head_token == "next":
            if len(stack) <= 1 or stack[-1][2] != "edit":
                unbalanced = True
                errors.append(f"line {lineno}: unmatched 'next' (no open edit block)")
                continue
            closing_id, _, _ = stack.pop()
            closed = nodes[closing_id]
            nodes[closing_id] = Node(
                id=closed.id, parent=closed.parent, children=closed.children,
                path=closed.path, verb=closed.verb, head=closed.head,
                attributes=closed.attributes, operands=closed.operands,
                line_start=closed.line_start, line_end=lineno, kind=closed.kind,
                context=closed.context, context_params=closed.context_params,
            )
            matched_count += 1
            continue

        if head_token == "end":
            if len(stack) <= 1 or stack[-1][2] != "config":
                unbalanced = True
                errors.append(f"line {lineno}: unmatched 'end' (no open config block)")
                continue
            closing_id, _, _ = stack.pop()
            closed = nodes[closing_id]
            nodes[closing_id] = Node(
                id=closed.id, parent=closed.parent, children=closed.children,
                path=closed.path, verb=closed.verb, head=closed.head,
                attributes=closed.attributes, operands=closed.operands,
                line_start=closed.line_start, line_end=lineno, kind=closed.kind,
                context=closed.context, context_params=closed.context_params,
            )
            matched_count += 1
            continue

        if head_token in _STATEMENT_VERBS and len(tokens) >= 2:
            key = tokens[1]
            value = " ".join(tokens[2:])
            node_path = parent_path + (stripped,)
            nid = new_id()
            nodes[nid] = Node(
                id=nid, parent=parent_id, children=(), path=node_path, verb=head_token,
                head=key, attributes={key: value} if value else {}, operands=tuple(tokens[2:]),
                line_start=lineno, line_end=lineno, kind="statement",
            )
            children_acc[parent_id].append(nid)
            matched_count += 1
            continue

        nid = new_id()
        nodes[nid] = Node(
            id=nid, parent=parent_id, children=(), path=parent_path + (stripped,),
            verb=None, head=tokens[0], attributes={}, operands=tuple(tokens[1:]),
            line_start=lineno, line_end=lineno, kind="unmatched",
        )
        children_acc[parent_id].append(nid)

    if len(stack) > 1:
        unbalanced = True
        errors.append("unbalanced config/edit blocks: unclosed block(s) at end of input")

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
        status=status, paradigm_used="block_keyword",
        node_count=len(finalized) - 1, max_depth=max_depth,
    )
