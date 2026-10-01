"""Unit tests for parse/paradigms/xml.py (TRD-02.1 §3.3 P5, PAN-OS) —
lxml-backed, sourceline-preserving XML structuring (TECH-STACK.md §6,
backend-01 §5.1). Verifies element->node/attribute->attribute mapping, line
binding via `sourceline` (G3), and the malformed-document hard-error case."""

from __future__ import annotations

from nsca_engine.parse.paradigms import xml as xml_paradigm

_GRAMMAR = xml_paradigm.XmlGrammarSpec()

_CONFIG = (
    "<config>\n"
    "  <mgt-config>\n"
    "    <ssh>\n"
    "      <session-limit>10</session-limit>\n"
    "    </ssh>\n"
    "    <telnet enabled=\"no\"/>\n"
    "  </mgt-config>\n"
    "</config>\n"
)


def test_line_ranges_resolve_to_exact_source_text_span():
    result = xml_paradigm.parse("ART-1", _CONFIG, _GRAMMAR)
    for node in result.tree.nodes.values():
        if node.id == result.tree.root_id:
            continue
        raw = result.tree.raw(node)
        # every element's own opening line must appear inside its raw span
        assert result.tree.lines[node.line_start - 1] in raw.split("\n")


def test_element_becomes_node_with_correct_path():
    result = xml_paradigm.parse("ART-1", _CONFIG, _GRAMMAR)
    session_limit = next(n for n in result.tree.nodes.values() if n.head == "session-limit")
    assert session_limit.path == ("config", "mgt-config", "ssh", "session-limit")
    assert session_limit.operands == ("10",)
    assert session_limit.line_start == session_limit.line_end == 4


def test_attribute_maps_to_node_attributes():
    result = xml_paradigm.parse("ART-1", _CONFIG, _GRAMMAR)
    telnet = next(n for n in result.tree.nodes.values() if n.head == "telnet")
    assert telnet.attributes == {"enabled": "no"}
    assert telnet.kind == "statement"


def test_container_vs_leaf_kind():
    result = xml_paradigm.parse("ART-1", _CONFIG, _GRAMMAR)
    ssh = next(n for n in result.tree.nodes.values() if n.head == "ssh")
    assert ssh.kind == "container"
    session_limit = next(n for n in result.tree.nodes.values() if n.head == "session-limit")
    assert session_limit.kind == "statement"


def test_malformed_xml_is_refused():
    bad = "<config><mgt-config></config>"
    result = xml_paradigm.parse("ART-1", bad, _GRAMMAR)
    assert result.status == "refused"
    assert result.errors


def test_coverage_is_full_for_well_formed_document():
    result = xml_paradigm.parse("ART-1", _CONFIG, _GRAMMAR)
    assert result.coverage == 1
    assert result.status == "parsed"
