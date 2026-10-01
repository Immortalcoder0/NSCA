"""P5 · XML structurer (TRD-02.1 §3.3, PAN-OS).

Direct mapping: element -> node, attribute -> attribute, text -> operand.
Line ranges come from the parser's position tracking.

Per TECH-STACK.md §6 / backend-01 §5.1: uses ``lxml``, **not** ``xmltodict`` —
the latter discards ``sourceline``, which makes evidence binding (G3)
impossible on XML platforms. This is called out as "the single most
commonly-missed dependency decision in this problem space"; this module is
where that decision is honoured for real.

Per §3.6, a malformed document is a hard failure (``status = "refused"``) —
the whole document is one syntactic unit, so a malformed document has no
local recovery.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from lxml import etree

from nsca_engine.parse.grammar import Node, ParseResult, ParseTree, split_lines


@dataclass(frozen=True, slots=True)
class XmlGrammarSpec:
    """No configurable knobs are needed yet for the minimal PAN-OS grammar —
    kept as a real dataclass (not a bare ``None``) so the rulepack loader's
    per-paradigm dispatch is uniform across every paradigm module."""


def _qualified_tag(el: etree._Element) -> str:
    """Namespaces are preserved in ``path`` (TRD-02.1 §5 edge case:
    "XML with namespaces ... namespaces preserved in path") by rendering a
    ``{uri}tag`` Clark-notation tag back to its declared prefix (``pfx:tag``)
    where one exists, rather than being silently dropped."""

    tag = el.tag
    if not isinstance(tag, str):
        # lxml's `.tag` is `str` for a regular element but can be a special
        # (comment/PI) marker for other node kinds — callers of this
        # function only ever pass regular elements, so this is defensive,
        # not a real code path.
        raise ValueError(f"non-string element tag: {tag!r}")
    if tag.startswith("{"):
        uri, local = tag[1:].split("}", 1)
        for pfx, ns_uri in (el.nsmap or {}).items():
            if ns_uri == uri and pfx:
                return f"{pfx}:{local}"
        return local  # default (unprefixed) namespace — no visible prefix
    return tag


def _max_descendant_line(el: etree._Element) -> int:
    best = el.sourceline or 1
    for child in el:
        best = max(best, _max_descendant_line(child))
    return best


def parse(artifact_id: str, text: str, grammar: XmlGrammarSpec) -> ParseResult:
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
    total_elements = 0

    try:
        parser = etree.XMLParser(remove_blank_text=False, recover=False)
        xml_root = etree.fromstring(text.encode("utf-8"), parser=parser)
    except etree.XMLSyntaxError as exc:
        errors.append(f"malformed XML document: {exc}")
        tree = ParseTree(artifact_id=artifact_id, lines=lines, nodes=nodes, root_id=root_id)
        return ParseResult(
            tree=tree, coverage=Fraction(0), unmatched=(), errors=tuple(errors),
            status="refused", paradigm_used="xml", node_count=0, max_depth=0,
        )

    def walk(el: etree._Element, parent_id: int, parent_path: tuple[str, ...]) -> None:
        nonlocal matched_count, total_elements
        total_elements += 1
        tag = _qualified_tag(el)
        node_path = parent_path + (tag,)
        line_start = el.sourceline or 1
        line_end = _max_descendant_line(el)
        child_elements = list(el)
        text_content = (el.text or "").strip()
        operands = (text_content,) if (text_content and not child_elements) else ()
        kind = "container" if child_elements else "statement"

        nid = new_id()
        nodes[nid] = Node(
            id=nid, parent=parent_id, children=(), path=node_path, verb=None,
            head=tag, attributes=dict(el.attrib), operands=operands,
            line_start=line_start, line_end=line_end, kind=kind,
        )
        children_acc[nid] = []
        children_acc[parent_id].append(nid)
        matched_count += 1

        for child in child_elements:
            walk(child, nid, node_path)

    walk(xml_root, root_id, ())

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
    coverage = Fraction(matched_count, total_elements) if total_elements else Fraction(1, 1)
    max_depth = max((len(n.path) for n in finalized.values()), default=0)

    return ParseResult(
        tree=tree, coverage=coverage, unmatched=(), errors=tuple(errors),
        status="parsed", paradigm_used="xml",
        node_count=len(finalized) - 1, max_depth=max_depth,
    )
