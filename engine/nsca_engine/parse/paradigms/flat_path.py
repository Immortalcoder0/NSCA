"""P2 · Flat path statements structurer (TRD-02.1 §3.3, Juniper set-format).

Each non-comment, non-blank line is a complete path (``set system services ssh
protocol-version v2``). The tree is reconstructed by common-prefix merging
across sibling statements (TRD-02.1 §3.3 P2): a shared path segment becomes
one container node reused by every statement that shares it, exactly as the
worked example in the TRD shows (``system -> services -> ssh -> {...}``).

Design decision (flagged, M2): the *last* path token is treated as the leaf
statement's own path segment; if at least two tokens remain after the verb,
the second-to-last/last pair is additionally recorded as a single
``attributes`` entry (key=value), matching the TRD's picture of an "ssh"
container holding ``protocol-version: v2`` as an attribute. Everything before
that pair becomes the container chain. This is a reasonable, documented
heuristic for a schema-less flat-path grammar (Junos "set" format has no
self-describing grammar the engine can consult) — good enough to build real
hierarchy and pass extraction/metamorphic tests, not a claim of full Junos
schema fidelity.

Per DD-02.1-02, ``delete``/``deactivate``/``activate`` lines are retained as
nodes with the matching ``verb`` — never applied as deletions during
structuring; that is TRD-02.3's job.

Per §3.6, flat-path has no unrecoverable condition: an unrecognised line
(missing a leading verb) becomes an ``unmatched`` node at the root.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from nsca_engine.parse.grammar import Node, ParseResult, ParseTree, split_lines

_VERBS = frozenset({"set", "delete", "deactivate", "activate", "protect", "insert", "rename", "copy"})


@dataclass(frozen=True, slots=True)
class FlatPathGrammarSpec:
    comment_char: str = "#"
    verbs: frozenset[str] = _VERBS


def parse(artifact_id: str, text: str, grammar: FlatPathGrammarSpec) -> ParseResult:
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

    # trie keyed by the container path tuple -> node id (prefix merging)
    container_by_path: dict[tuple[str, ...], int] = {(): root_id}

    def get_container(prefix: tuple[str, ...], lineno: int) -> int:
        if prefix in container_by_path:
            return container_by_path[prefix]
        parent_id = get_container(prefix[:-1], lineno)
        nid = new_id()
        nodes[nid] = Node(
            id=nid, parent=parent_id, children=(), path=prefix, verb=None,
            head=prefix[-1], attributes={}, operands=(), line_start=lineno,
            line_end=lineno, kind="container",
        )
        children_acc[nid] = []
        children_acc[parent_id].append(nid)
        container_by_path[prefix] = nid
        return nid

    errors: list[str] = []
    matched_count = 0
    total_nonblank = 0

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

        total_nonblank += 1

        if stripped.startswith(grammar.comment_char):
            nid = new_id()
            nodes[nid] = Node(
                id=nid, parent=root_id, children=(), path=(), verb=None,
                head=grammar.comment_char, attributes={}, operands=(),
                line_start=lineno, line_end=lineno, kind="comment",
            )
            children_acc[root_id].append(nid)
            matched_count += 1
            continue

        tokens = stripped.split()
        head_verb = tokens[0].lower()
        if head_verb not in grammar.verbs or len(tokens) < 2:
            nid = new_id()
            nodes[nid] = Node(
                id=nid, parent=root_id, children=(), path=tuple(tokens), verb=None,
                head=tokens[0], attributes={}, operands=tuple(tokens[1:]),
                line_start=lineno, line_end=lineno, kind="unmatched",
            )
            children_acc[root_id].append(nid)
            continue

        rest = tokens[1:]
        container_prefix = tuple(rest[:-1])
        parent_id = get_container(container_prefix, lineno)
        attributes = {rest[-2]: rest[-1]} if len(rest) >= 2 else {}

        nid = new_id()
        nodes[nid] = Node(
            id=nid, parent=parent_id, children=(), path=tuple(rest), verb=head_verb,
            head=rest[-1], attributes=attributes, operands=(rest[-1],),
            line_start=lineno, line_end=lineno, kind="statement",
        )
        children_acc[nid] = []
        children_acc[parent_id].append(nid)
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
        status=status, paradigm_used="flat_path",
        node_count=len(finalized) - 1, max_depth=max_depth,
    )
