"""P1 · Indentation paradigm structurer (TRD-02.1 §3.3, Cisco family).

Depth is derived from leading-whitespace count; a comment-char line or a
blank line returns the stack to depth 0 (TRD-02.1 §3.3 P1). Banner bodies
open a verbatim region that receives no structural interpretation until the
closing delimiter is seen again (TRD-02.1 §3.3, edge case table §5) — without
this a banner containing ``!`` or indented text would corrupt the tree.

M1 scope: this is the one paradigm M1 needs (backend-01 §6). It is
deliberately simpler than the full TRD-02.1 spec in one respect, flagged in
the M1 report: scope selection for extraction (``parse/effective_config.py``,
``extract/runtime.py``) searches the whole tree rather than being routed
through a declared ``context``/``section`` scope-selection language — a
simplification, not a correctness gap, because every M1 extractor's ``match``
regex is itself scope-specific enough not to false-positive across contexts
in the Cisco IOS corpus this milestone targets.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from nsca_engine.parse.grammar import Node, ParseResult, ParseTree, split_lines


@dataclass(frozen=True, slots=True)
class ContextBlockRule:
    """One ``context_blocks`` entry from the rulepack's grammar block
    (TECH-STACK.md §4): a regex plus the context name it opens, with named
    capture groups becoming ``context_params``."""

    pattern: re.Pattern[str]
    context: str


@dataclass(frozen=True, slots=True)
class IndentationGrammarSpec:
    comment_char: str
    context_blocks: tuple[ContextBlockRule, ...] = ()
    banner_heads: tuple[str, ...] = ("banner",)


import re  # noqa: E402  (kept local to avoid a module-level re import ordering nit)


def _leading_spaces(line: str) -> int:
    n = 0
    for ch in line:
        if ch == " ":
            n += 1
        elif ch == "\t":
            n += 1  # tab expansion is not modelled in M1; recorded as 1 level
        else:
            break
    return n


def parse(artifact_id: str, text: str, grammar: IndentationGrammarSpec) -> ParseResult:
    lines = split_lines(text)
    nodes: dict[int, Node] = {}
    next_id = 0

    def new_id() -> int:
        nonlocal next_id
        next_id += 1
        return next_id

    root_id = 0
    nodes[root_id] = Node(
        id=root_id,
        parent=None,
        children=(),
        path=(),
        verb=None,
        head="",
        attributes={},
        operands=(),
        line_start=0,
        line_end=0,
        kind="container",
    )
    # mutable children accumulator, flushed into frozen Node objects at the end
    children_acc: dict[int, list[int]] = {root_id: []}

    # stack of (depth, node_id, path tuple)
    stack: list[tuple[int, int, tuple[str, ...]]] = [(-1, root_id, ())]

    errors: list[str] = []
    i = 0
    n = len(lines)
    matched_count = 0
    total_nonblank = 0

    while i < n:
        lineno = i + 1
        raw_line = lines[i]
        stripped = raw_line.strip()

        if stripped == "":
            nid = new_id()
            nodes[nid] = Node(
                id=nid, parent=root_id, children=(), path=(), verb=None, head="",
                attributes={}, operands=(), line_start=lineno, line_end=lineno,
                kind="blank",
            )
            children_acc.setdefault(root_id, []).append(nid)
            stack = [(-1, root_id, ())]
            i += 1
            continue

        total_nonblank += 1

        if stripped == grammar.comment_char or stripped.startswith(
            grammar.comment_char + " "
        ) or stripped == grammar.comment_char * len(stripped):
            nid = new_id()
            nodes[nid] = Node(
                id=nid, parent=root_id, children=(), path=(), verb=None,
                head=grammar.comment_char, attributes={}, operands=(),
                line_start=lineno, line_end=lineno, kind="comment",
            )
            children_acc.setdefault(root_id, []).append(nid)
            stack = [(-1, root_id, ())]
            matched_count += 1
            i += 1
            continue

        tokens = stripped.split()
        head_token = tokens[0]

        # Banner verbatim region.
        if head_token.lower() in grammar.banner_heads and len(tokens) >= 3:
            delim = tokens[-1][-1]
            start = lineno
            end = lineno
            j = i + 1
            while j < n:
                end = j + 1
                if delim in lines[j]:
                    break
                j += 1
            nid = new_id()
            nodes[nid] = Node(
                id=nid, parent=root_id, children=(), path=("banner",),
                verb=None, head="banner", attributes={}, operands=tuple(tokens[1:]),
                line_start=start, line_end=end, kind="verbatim",
            )
            children_acc.setdefault(root_id, []).append(nid)
            stack = [(-1, root_id, ())]
            matched_count += 1
            i = j + 1
            continue

        depth = _leading_spaces(raw_line)

        while len(stack) > 1 and stack[-1][0] >= depth:
            stack.pop()
        parent_depth, parent_id, parent_path = stack[-1]

        if tokens[0].lower() == "no" and len(tokens) > 1:
            verb = "no"
            head = tokens[1]
            operands = tuple(tokens[2:])
        else:
            verb = None
            head = tokens[0]
            operands = tuple(tokens[1:])

        context = None
        context_params: Mapping[str, str] = {}
        for rule in grammar.context_blocks:
            m = rule.pattern.match(stripped)
            if m:
                context = rule.context
                context_params = dict(m.groupdict())
                break

        node_path = parent_path + (stripped,)
        nid = new_id()
        kind = "container" if context is not None else "statement"
        nodes[nid] = Node(
            id=nid, parent=parent_id, children=(), path=node_path, verb=verb,
            head=head, attributes={}, operands=operands, line_start=lineno,
            line_end=lineno, kind=kind, context=context,
            context_params=context_params,
        )
        children_acc.setdefault(parent_id, []).append(nid)
        children_acc.setdefault(nid, [])
        stack.append((depth, nid, node_path))
        matched_count += 1
        i += 1

    # any statement that ended up with children is really a container
    finalized: dict[int, Node] = {}
    for nid, node in nodes.items():
        kids = tuple(children_acc.get(nid, []))
        kind = node.kind
        if kind == "statement" and kids:
            kind = "container"
        finalized[nid] = Node(
            id=node.id, parent=node.parent, children=kids, path=node.path,
            verb=node.verb, head=node.head, attributes=node.attributes,
            operands=node.operands, line_start=node.line_start,
            line_end=node.line_end, kind=kind, context=node.context,
            context_params=node.context_params,
        )

    tree = ParseTree(artifact_id=artifact_id, lines=lines, nodes=finalized, root_id=root_id)

    coverage = (
        Fraction(matched_count, total_nonblank) if total_nonblank else Fraction(1, 1)
    )
    max_depth = 0
    for node in finalized.values():
        max_depth = max(max_depth, len(node.path))

    status = "parsed"
    if total_nonblank and coverage < Fraction(1, 2):
        status = "refused"
    elif coverage < 1:
        status = "parsed_with_gaps"

    return ParseResult(
        tree=tree,
        coverage=coverage,
        unmatched=(),
        errors=tuple(errors),
        status=status,
        paradigm_used="indentation",
        node_count=len(finalized) - 1,
        max_depth=max_depth,
    )


def compile_context_blocks(
    specs: tuple[tuple[str, str], ...],
) -> tuple[ContextBlockRule, ...]:
    """Compile ``(pattern, context_name)`` pairs into ``ContextBlockRule``s."""

    return tuple(
        ContextBlockRule(pattern=re.compile(pattern), context=context)
        for pattern, context in specs
    )
