"""Unit tests for parse/paradigms/path_header.py (TRD-02.1 §3.3 P6, MikroTik
RouterOS): `/path` containers persisting across statements, key=value
attribute parsing, and bracketed-selector handling as a single operand
(not attributes), per the TRD's explicit instruction."""

from __future__ import annotations

from nsca_engine.parse.paradigms import path_header

_GRAMMAR = path_header.PathHeaderGrammarSpec()

_CONFIG = (
    "/ip service\n"
    "set telnet disabled=no port=23\n"
    "set www disabled=yes\n"
    "/interface ethernet\n"
    "set [ find default-name=ether1 ] name=ether1-wan\n"
)


def test_line_ranges_resolve_to_exact_source_text():
    result = path_header.parse("ART-1", _CONFIG, _GRAMMAR)
    for node in result.tree.nodes.values():
        if node.id == result.tree.root_id:
            continue
        assert result.tree.raw(node) == "\n".join(
            result.tree.lines[node.line_start - 1 : node.line_end]
        )


def test_path_header_opens_persistent_container():
    result = path_header.parse("ART-1", _CONFIG, _GRAMMAR)
    ip_service = next(n for n in result.tree.nodes.values() if n.path == ("ip", "service"))
    children = result.tree.children_of(ip_service.id)
    assert len(children) == 2  # both `set` statements attach here
    assert all(c.parent == ip_service.id for c in children)


def test_statement_parses_key_value_attributes():
    result = path_header.parse("ART-1", _CONFIG, _GRAMMAR)
    telnet_stmt = next(
        n for n in result.tree.nodes.values()
        if n.verb == "set" and n.attributes.get("port") == "23"
    )
    assert telnet_stmt.attributes == {"disabled": "no", "port": "23"}


def test_bracketed_selector_is_a_single_operand_not_attributes():
    result = path_header.parse("ART-1", _CONFIG, _GRAMMAR)
    eth_stmt = next(
        n for n in result.tree.nodes.values()
        if n.attributes.get("name") == "ether1-wan"
    )
    assert eth_stmt.operands == ("[ find default-name=ether1 ]",)
    assert "find" not in eth_stmt.attributes
    assert eth_stmt.attributes == {"name": "ether1-wan"}


def test_second_path_header_closes_the_first_container():
    result = path_header.parse("ART-1", _CONFIG, _GRAMMAR)
    eth = next(n for n in result.tree.nodes.values() if n.path == ("interface", "ethernet"))
    children = result.tree.children_of(eth.id)
    assert len(children) == 1


def test_grammar_coverage_is_full_for_a_clean_config():
    result = path_header.parse("ART-1", _CONFIG, _GRAMMAR)
    assert result.coverage == 1
    assert result.status == "parsed"
