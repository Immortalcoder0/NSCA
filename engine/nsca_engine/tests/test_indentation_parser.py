"""Unit tests for parse/grammar.py + parse/paradigms/indentation.py
(TRD-02.1) — line binding (INV-02.1-01/V-02.1-002), banner verbatim handling,
and total line coverage on the indentation paradigm."""

from __future__ import annotations

from nsca_engine.controls.rulepack_loader import load_rulepack
from nsca_engine.parse.paradigms import indentation
from nsca_engine.tests.helpers import RULEPACK_PATH

_LOADED_RP = load_rulepack(RULEPACK_PATH)


def test_line_ranges_resolve_to_exact_source_text():
    config = "line vty 0 4\n transport input ssh\n exec-timeout 5 0\n"
    result = indentation.parse("ART-1", config, _LOADED_RP.grammar)
    for node in result.tree.nodes.values():
        if node.id == result.tree.root_id:
            continue
        assert result.tree.raw(node) == "\n".join(
            result.tree.lines[node.line_start - 1 : node.line_end]
        )


def test_vty_container_has_context_and_params():
    config = "line vty 0 4\n transport input ssh\n"
    result = indentation.parse("ART-1", config, _LOADED_RP.grammar)
    vty_nodes = [n for n in result.tree.nodes.values() if n.context == "vty_range"]
    assert len(vty_nodes) == 1
    assert vty_nodes[0].context_params == {"lo": "0", "hi": "4"}


def test_child_statement_is_parented_to_container():
    config = "line vty 0 4\n transport input ssh\n"
    result = indentation.parse("ART-1", config, _LOADED_RP.grammar)
    container = next(n for n in result.tree.nodes.values() if n.context == "vty_range")
    child = result.tree.nodes[container.children[0]]
    assert child.head == "transport"
    assert child.parent == container.id


def test_comment_line_resets_indentation_stack():
    config = "line vty 0 4\n transport input ssh\n!\nhostname X\n"
    result = indentation.parse("ART-1", config, _LOADED_RP.grammar)
    hostname_node = next(n for n in result.tree.nodes.values() if n.head == "hostname")
    assert hostname_node.parent == result.tree.root_id


def test_banner_is_a_single_verbatim_node_and_does_not_corrupt_structure():
    config = (
        "banner motd #\n"
        "! this looks like a comment but is inside the banner\n"
        " indented text also inside the banner\n"
        "#\n"
        "hostname AFTER-BANNER\n"
    )
    result = indentation.parse("ART-1", config, _LOADED_RP.grammar)
    verbatim_nodes = [n for n in result.tree.nodes.values() if n.kind == "verbatim"]
    assert len(verbatim_nodes) == 1
    assert verbatim_nodes[0].line_start == 1
    assert verbatim_nodes[0].line_end == 4
    hostname_node = next(n for n in result.tree.nodes.values() if n.head == "hostname")
    assert hostname_node.parent == result.tree.root_id
    assert hostname_node.line_start == 5


def test_grammar_coverage_is_full_for_a_clean_config():
    config = "hostname X\n!\nline vty 0 4\n transport input ssh\n"
    result = indentation.parse("ART-1", config, _LOADED_RP.grammar)
    assert result.coverage == 1
    assert result.status == "parsed"
