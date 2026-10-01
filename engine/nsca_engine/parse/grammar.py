"""The generic grammar engine's shared parse-tree contract (TRD-02.1 §3.1).

Every structural paradigm (only the indentation paradigm — Cisco/Arista — is
built in M1; see ``parse/paradigms/indentation.py``) produces trees built from
the ``Node``/``ParseTree``/``ParseResult`` shapes defined here. Downstream
subsystems (effective-config resolution, extraction) are written against this
contract and must never special-case a paradigm.

Per TECH-STACK.md §3, a node's verbatim text is **not** copied into the node —
it is materialised on demand from an offset/length pair (here: 1-indexed
``line_start``/``line_end`` into ``ParseTree.lines``, which is itself the
normalised-text line table for the artifact). For the artifact sizes M1
targets this keeps the shape faithful to the "offset, not copied text"
invariant without needing a byte-offset index; a byte-offset variant would be
a drop-in replacement for the NFR-PERF-003 500k-line case (M2+).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

# ---------------------------------------------------------------------------
# The parse tree contract (TRD-02.1 §3.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Node:
    """One node in a parse tree.

    ``kind`` is one of ``statement | container | comment | blank |
    verbatim | unmatched`` (TRD-02.1 §3.1). ``context``/``context_params``
    hold the structural context a container node opens (e.g. ``vty_range``
    with ``{"lo": "0", "hi": "4"}``) when the grammar's ``context_blocks``
    matched this line (TECH-STACK.md §4).
    """

    id: int
    parent: int | None
    children: tuple[int, ...]
    path: tuple[str, ...]
    verb: str | None
    head: str
    attributes: Mapping[str, str]
    operands: tuple[str, ...]
    line_start: int
    line_end: int
    kind: str
    context: str | None = None
    context_params: Mapping[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.context_params is None:
            object.__setattr__(self, "context_params", {})


@dataclass(frozen=True, slots=True)
class ParseTree:
    """The output tree plus the normalised line table it was built from
    (INV-02.1-01 — every node's line range resolves to real text)."""

    artifact_id: str
    lines: tuple[str, ...]  # lines[i - 1] is 1-indexed line i, post-normalisation
    nodes: Mapping[int, Node]
    root_id: int

    def raw(self, node: Node) -> str:
        """Materialise a node's verbatim source text on demand
        (TECH-STACK.md §3 — never stored per node)."""

        return "\n".join(self.lines[node.line_start - 1 : node.line_end])

    def children_of(self, node_id: int) -> tuple[Node, ...]:
        return tuple(self.nodes[c] for c in self.nodes[node_id].children)

    def walk(self) -> tuple[Node, ...]:
        """All nodes in deterministic document (pre-)order, root excluded."""

        out: list[Node] = []

        def _walk(node_id: int) -> None:
            for cid in self.nodes[node_id].children:
                out.append(self.nodes[cid])
                _walk(cid)

        _walk(self.root_id)
        return tuple(out)


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Output of a paradigm structurer (TRD-02.1 §4)."""

    tree: ParseTree
    coverage: Fraction
    unmatched: tuple[Node, ...]
    errors: tuple[str, ...]
    status: str  # parsed | parsed_with_gaps | refused
    paradigm_used: str
    node_count: int
    max_depth: int


# ---------------------------------------------------------------------------
# Paradigm-independent lexing helper (DD-02.1-01)
# ---------------------------------------------------------------------------


def split_lines(text: str) -> tuple[str, ...]:
    """Split already-normalised (LF-only, TRD-01.1 §3.2) text into a
    1-indexed line table. A trailing newline does not produce a phantom
    final empty line, matching how line numbers are perceived by a human
    reading the artifact."""

    if text == "":
        return ()
    if text.endswith("\n"):
        text = text[:-1]
    return tuple(text.split("\n"))
