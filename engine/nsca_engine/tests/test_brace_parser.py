"""Unit tests for parse/paradigms/brace.py (TRD-02.1 §3.3 P3, Juniper
curly-format): nesting, statement terminators, line binding, and the
unbalanced-brace hard-error case (§3.6, DD-02.1-04, V-02.1-007)."""

from __future__ import annotations

from nsca_engine.parse.paradigms import brace

_GRAMMAR = brace.BraceGrammarSpec()

_CONFIG = (
    "system {\n"
    "    services {\n"
    "        ssh {\n"
    "            protocol-version v2;\n"
    "            root-login deny;\n"
    "        }\n"
    "    }\n"
    "}\n"
)


def test_line_ranges_resolve_to_exact_source_text():
    result = brace.parse("ART-1", _CONFIG, _GRAMMAR)
    for node in result.tree.nodes.values():
        if node.id == result.tree.root_id:
            continue
        assert result.tree.raw(node) == "\n".join(
            result.tree.lines[node.line_start - 1 : node.line_end]
        )


def test_nested_containers_have_correct_parent_chain():
    result = brace.parse("ART-1", _CONFIG, _GRAMMAR)
    ssh = next(n for n in result.tree.nodes.values() if n.head == "ssh")
    services = result.tree.nodes[ssh.parent]
    system = result.tree.nodes[services.parent]
    assert services.head == "services"
    assert system.head == "system"
    assert system.parent == result.tree.root_id


def test_container_line_range_spans_open_to_close():
    result = brace.parse("ART-1", _CONFIG, _GRAMMAR)
    system = next(n for n in result.tree.nodes.values() if n.head == "system")
    assert system.line_start == 1
    assert system.line_end == 8


def test_statement_terminated_by_semicolon_has_attributes():
    result = brace.parse("ART-1", _CONFIG, _GRAMMAR)
    stmt = next(n for n in result.tree.nodes.values() if n.head == "protocol-version")
    assert stmt.kind == "statement"
    assert stmt.attributes == {"protocol-version": "v2"}
    assert stmt.line_start == stmt.line_end == 4


def test_unbalanced_closing_brace_is_refused():
    bad = "system {\n    services {\n    }\n}\n}\n"  # one extra closing brace
    result = brace.parse("ART-1", bad, _GRAMMAR)
    assert result.status == "refused"
    assert result.errors


def test_unclosed_block_at_eof_is_refused():
    bad = "system {\n    services {\n"
    result = brace.parse("ART-1", bad, _GRAMMAR)
    assert result.status == "refused"
    assert result.errors


def test_comment_lines_do_not_open_blocks():
    config = "# leading comment\nsystem {\n    host-name fw-01;\n}\n"
    result = brace.parse("ART-1", config, _GRAMMAR)
    assert result.status == "parsed"
    comment_nodes = [n for n in result.tree.nodes.values() if n.kind == "comment"]
    assert len(comment_nodes) == 1
