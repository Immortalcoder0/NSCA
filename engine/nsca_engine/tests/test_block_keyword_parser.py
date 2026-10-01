"""Unit tests for parse/paradigms/block_keyword.py (TRD-02.1 §3.3 P4,
FortiOS): the two simultaneous nesting mechanisms (config/end, edit/next),
line binding, and the unbalanced-end hard-error case (§3.6, DD-02.1-04,
V-02.1-007)."""

from __future__ import annotations

from nsca_engine.parse.paradigms import block_keyword

_GRAMMAR = block_keyword.BlockKeywordGrammarSpec()

_CONFIG = (
    "config system global\n"
    "    set admin-telnet disable\n"
    "end\n"
    "config firewall policy\n"
    "    edit 1\n"
    "        set srcintf \"wan1\"\n"
    "        set action accept\n"
    "    next\n"
    "end\n"
)


def test_line_ranges_resolve_to_exact_source_text():
    result = block_keyword.parse("ART-1", _CONFIG, _GRAMMAR)
    for node in result.tree.nodes.values():
        if node.id == result.tree.root_id:
            continue
        assert result.tree.raw(node) == "\n".join(
            result.tree.lines[node.line_start - 1 : node.line_end]
        )


def test_config_block_spans_config_to_end():
    result = block_keyword.parse("ART-1", _CONFIG, _GRAMMAR)
    global_block = next(
        n for n in result.tree.nodes.values()
        if n.context == "config_block" and n.context_params.get("name") == "system global"
    )
    assert global_block.line_start == 1
    assert global_block.line_end == 3


def test_edit_sub_container_nested_inside_config():
    result = block_keyword.parse("ART-1", _CONFIG, _GRAMMAR)
    edit_block = next(n for n in result.tree.nodes.values() if n.context == "edit_block")
    parent = result.tree.nodes[edit_block.parent]
    assert parent.context == "config_block"
    assert parent.context_params.get("name") == "firewall policy"
    assert edit_block.line_start == 5
    assert edit_block.line_end == 8


def test_set_statement_has_verb_and_attributes():
    result = block_keyword.parse("ART-1", _CONFIG, _GRAMMAR)
    stmt = next(n for n in result.tree.nodes.values() if n.head == "action")
    assert stmt.verb == "set"
    assert stmt.attributes == {"action": "accept"}


def test_unbalanced_end_is_refused():
    bad = "config system global\n    set admin-telnet disable\nend\nend\n"
    result = block_keyword.parse("ART-1", bad, _GRAMMAR)
    assert result.status == "refused"
    assert result.errors


def test_unclosed_config_at_eof_is_refused():
    bad = "config system global\n    set admin-telnet disable\n"
    result = block_keyword.parse("ART-1", bad, _GRAMMAR)
    assert result.status == "refused"


def test_grammar_coverage_is_full_for_a_clean_config():
    result = block_keyword.parse("ART-1", _CONFIG, _GRAMMAR)
    assert result.coverage == 1
    assert result.status == "parsed"
