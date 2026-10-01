"""P7 · Native structured input (TRD-02.1 §3.3, cloud policy JSON).

"Already a tree. Line ranges from a position-preserving JSON parse." The
standard library's ``json`` module does not preserve token positions, so this
module is a small hand-written, line-tracking JSON tokenizer/parser — the
same reasoning that drives ``xml.py`` to use ``lxml`` over ``xmltodict``:
without real position tracking G3 (evidence binding) is unsatisfiable, and a
line number silently reconstructed after the fact ("assume the object started
near this key") is not defensible evidence.

**Judgment call (flagged, M2):** "cloud JSON" is not one shape — AWS security
groups, Azure NSGs and GCP firewall rules all differ. TRD-02.1 §3.3 P7 and
its own verification table (V-02.1-006) ask only that *some* structured cloud
policy JSON parses through the shared contract, not that all three shapes be
supported. This module implements one representative, vendor-neutral shape —
a JSON object describing a cloud-hosted virtual-firewall/router device (top
level: ``hostname``, ``rules: [...]``, ``management: {...}``) — modelled
after the general shape common to AWS/Azure/GCP exports (a device object with
a management block and an ordered rule list), rather than any one vendor's
exact export format. Extractors are written against this shape; adapting a
literal AWS/Azure/GCP export is future work once a real corpus sample is
available (the open corpus-sourcing risk already flagged in backend-01 §8).

Mapping onto the shared ``Node`` contract: a JSON object -> ``container``;
each of its non-composite key/value pairs -> one ``statement`` child (so an
extractor's ``match`` regex, written the same way as every other paradigm's,
can match against that statement's raw source text); an array -> a
``container`` per element, indexed in ``path`` (``rules[0]``, ``rules[1]``,
...) matching how the engine already represents collections elsewhere
(``extract/runtime.py``'s ``auth.local_users[0].name`` shape) — see the edge
case table's "JSON policy with unordered keys ... ordered deterministically
by key" (D6): object keys are walked in *source* order for tree construction
(preserving the export's own ordering, which is what a line-numbered parse
naturally gives), not re-sorted — re-sorting would make ``path`` disagree
with ``raw()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from nsca_engine.parse.grammar import Node, ParseResult, ParseTree, split_lines


@dataclass(frozen=True, slots=True)
class CloudJsonGrammarSpec:
    """No configurable knobs needed yet — kept as a real dataclass so the
    rulepack loader's per-paradigm dispatch is uniform (see xml.py)."""


class _JsonSyntaxError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Minimal position-tracking JSON tokenizer + recursive-descent parser.
# ---------------------------------------------------------------------------


class _Tokenizer:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.line = 1
        self.n = len(text)

    def _skip_ws(self) -> None:
        while self.pos < self.n and self.text[self.pos] in " \t\r\n":
            if self.text[self.pos] == "\n":
                self.line += 1
            self.pos += 1

    def peek_nonws(self) -> str:
        save_pos, save_line = self.pos, self.line
        self._skip_ws()
        ch = self.text[self.pos] if self.pos < self.n else ""
        self.pos, self.line = save_pos, save_line
        return ch

    def next_token(self) -> tuple[str, Any, int]:
        """Returns (kind, value, line). kind in punctuation chars,
        'string', 'number', 'true', 'false', 'null'."""

        self._skip_ws()
        if self.pos >= self.n:
            raise _JsonSyntaxError("unexpected end of input")
        line = self.line
        ch = self.text[self.pos]
        if ch in "{}[]:,":
            self.pos += 1
            return ch, ch, line
        if ch == '"':
            return self._read_string()
        if ch == "-" or ch.isdigit():
            return self._read_number()
        for lit, val in (("true", True), ("false", False), ("null", None)):
            if self.text.startswith(lit, self.pos):
                self.pos += len(lit)
                return "literal", val, line
        raise _JsonSyntaxError(f"unexpected character {ch!r} at line {line}")

    def _read_string(self) -> tuple[str, str, int]:
        line = self.line
        assert self.text[self.pos] == '"'
        self.pos += 1
        out = []
        while True:
            if self.pos >= self.n:
                raise _JsonSyntaxError("unterminated string")
            ch = self.text[self.pos]
            if ch == "\\":
                out.append(self.text[self.pos : self.pos + 2])
                self.pos += 2
                continue
            if ch == '"':
                self.pos += 1
                break
            if ch == "\n":
                self.line += 1
            out.append(ch)
            self.pos += 1
        raw = "".join(out)
        try:
            value = bytes(raw, "utf-8").decode("unicode_escape")
        except Exception:
            value = raw
        return "string", value, line

    def _read_number(self) -> tuple[str, Any, int]:
        line = self.line
        start = self.pos
        if self.text[self.pos] == "-":
            self.pos += 1
        while self.pos < self.n and (self.text[self.pos].isdigit() or self.text[self.pos] in ".eE+-"):
            self.pos += 1
        raw = self.text[start : self.pos]
        value: Any = float(raw) if any(c in raw for c in ".eE") else int(raw)
        return "number", value, line


def _parse_value(tok: _Tokenizer) -> tuple[Any, int]:
    kind, value, line = tok.next_token()
    if kind == "{":
        return _parse_object(tok, line), line
    if kind == "[":
        return _parse_array(tok, line), line
    if kind == "string":
        return value, line
    if kind == "number":
        return value, line
    if kind == "literal":
        return value, line
    raise _JsonSyntaxError(f"unexpected token {kind!r} at line {line}")


def _parse_object(tok: _Tokenizer, _open_line: int) -> _JsonObject:
    entries: list[tuple[str, Any, int]] = []
    if tok.peek_nonws() == "}":
        tok.next_token()
        return _JsonObject(entries)
    while True:
        kkind, kvalue, kline = tok.next_token()
        if kkind != "string":
            raise _JsonSyntaxError(f"expected string key at line {kline}")
        ckind, _, _ = tok.next_token()
        if ckind != ":":
            raise _JsonSyntaxError(f"expected ':' after key at line {kline}")
        value, vline = _parse_value(tok)
        entries.append((kvalue, value, kline))
        nkind, _, _ = tok.next_token()
        if nkind == ",":
            continue
        if nkind == "}":
            break
        raise _JsonSyntaxError(f"expected ',' or '}}' at line {kline}")
    return _JsonObject(entries)


def _parse_array(tok: _Tokenizer, _open_line: int) -> _JsonArray:
    items: list[tuple[Any, int]] = []
    if tok.peek_nonws() == "]":
        tok.next_token()
        return _JsonArray(items)
    while True:
        value, vline = _parse_value(tok)
        items.append((value, vline))
        nkind, _, _ = tok.next_token()
        if nkind == ",":
            continue
        if nkind == "]":
            break
        raise _JsonSyntaxError("expected ',' or ']'")
    return _JsonArray(items)


class _JsonObject:
    def __init__(self, entries: list[tuple[str, Any, int]]) -> None:
        self.entries = entries  # (key, value, line) in source order


class _JsonArray:
    def __init__(self, items: list[tuple[Any, int]]) -> None:
        self.items = items  # (value, line) in source order


def _is_composite(v: Any) -> bool:
    return isinstance(v, (_JsonObject, _JsonArray))


def parse(artifact_id: str, text: str, grammar: CloudJsonGrammarSpec) -> ParseResult:
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
    total_scalar = 0

    try:
        tok = _Tokenizer(text)
        root_value, root_line = _parse_value(tok)
    except _JsonSyntaxError as exc:
        errors.append(str(exc))
        tree = ParseTree(artifact_id=artifact_id, lines=lines, nodes=nodes, root_id=root_id)
        return ParseResult(
            tree=tree, coverage=Fraction(0), unmatched=(), errors=tuple(errors),
            status="refused", paradigm_used="cloud_json", node_count=0, max_depth=0,
        )

    def last_line_of(value: Any, fallback: int) -> int:
        if isinstance(value, _JsonObject):
            return max((last_line_of(v, ln) for _, v, ln in value.entries), default=fallback)
        if isinstance(value, _JsonArray):
            return max((last_line_of(v, ln) for v, ln in value.items), default=fallback)
        return fallback

    def build(value: Any, line: int, parent_id: int, path: tuple[str, ...]) -> None:
        nonlocal total_scalar
        if isinstance(value, _JsonObject):
            nid = new_id()
            end_line = last_line_of(value, line)
            nodes[nid] = Node(
                id=nid, parent=parent_id, children=(), path=path, verb=None,
                head=path[-1] if path else "", attributes={}, operands=(),
                line_start=line, line_end=end_line, kind="container",
            )
            children_acc[nid] = []
            children_acc[parent_id].append(nid)
            for key, val, kline in value.entries:
                build(val, kline, nid, path + (key,))
            return
        if isinstance(value, _JsonArray):
            nid = new_id()
            end_line = last_line_of(value, line)
            nodes[nid] = Node(
                id=nid, parent=parent_id, children=(), path=path, verb=None,
                head=path[-1] if path else "", attributes={}, operands=(),
                line_start=line, line_end=end_line, kind="container",
            )
            children_acc[nid] = []
            children_acc[parent_id].append(nid)
            for idx, (item, iline) in enumerate(value.items):
                item_end = last_line_of(item, iline)
                elem_id = new_id()
                nodes[elem_id] = Node(
                    id=elem_id, parent=nid, children=(), path=path[:-1] + (f"{path[-1]}[{idx}]",),
                    verb=None, head=f"{path[-1]}[{idx}]", attributes={}, operands=(),
                    line_start=iline, line_end=item_end, kind="container",
                )
                children_acc[elem_id] = []
                children_acc[nid].append(elem_id)
                if _is_composite(item):
                    # merge the composite's own children directly under this
                    # indexed element node (avoid a redundant extra hop).
                    if isinstance(item, _JsonObject):
                        for key, val, kline in item.entries:
                            build(val, kline, elem_id, (f"{path[-1]}[{idx}]", key))
                    else:
                        for _j, (subitem, subline) in enumerate(item.items):
                            build(subitem, subline, elem_id, (f"{path[-1]}[{idx}]",))
                else:
                    scalar_id = new_id()
                    nodes[scalar_id] = Node(
                        id=scalar_id, parent=elem_id, children=(), path=path[:-1] + (f"{path[-1]}[{idx}]", "value"),
                        verb=None, head="value", attributes={"value": str(item)},
                        operands=(str(item),), line_start=iline, line_end=iline, kind="statement",
                    )
                    children_acc[elem_id].append(scalar_id)
                    total_scalar += 1
            return
        # scalar leaf: statement node, one physical line's worth of raw text
        nonlocal_key = path[-1] if path else ""
        nid = new_id()
        nodes[nid] = Node(
            id=nid, parent=parent_id, children=(), path=path, verb=None,
            head=nonlocal_key, attributes={nonlocal_key: value} if path else {},
            operands=(str(value),), line_start=line, line_end=line, kind="statement",
        )
        children_acc[parent_id].append(nid)
        total_scalar += 1

    build(root_value, root_line, root_id, ())

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
    # A JSON document is a single syntactic unit ("Already a tree", TRD-02.1
    # §3.3 P7): a document that parses at all parses completely — there is
    # no partial-match/coverage-gap concept the way there is for a
    # line-oriented paradigm. `total_scalar` is retained (not just `_`) as
    # a readable signal that at least one leaf fact was actually produced.
    coverage = Fraction(1, 1)
    max_depth = max((len(n.path) for n in finalized.values()), default=0)

    return ParseResult(
        tree=tree, coverage=coverage, unmatched=(), errors=tuple(errors),
        status="parsed", paradigm_used="cloud_json",
        node_count=len(finalized) - 1, max_depth=max_depth,
    )
