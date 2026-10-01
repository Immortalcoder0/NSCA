"""Unit tests for parse/paradigms/flat_path.py (TRD-02.1 §3.3 P2, Juniper
set-format): line binding, common-prefix container merging, verb retention
(DD-02.1-02), coverage."""

from __future__ import annotations

from nsca_engine.parse.paradigms import flat_path

_GRAMMAR = flat_path.FlatPathGrammarSpec()


def test_line_ranges_resolve_to_exact_source_text():
    config = (
        "set system services ssh protocol-version v2\n"
        "set system services ssh root-login deny\n"
    )
    result = flat_path.parse("ART-1", config, _GRAMMAR)
    for node in result.tree.nodes.values():
        if node.id == result.tree.root_id:
            continue
        assert result.tree.raw(node) == "\n".join(
            result.tree.lines[node.line_start - 1 : node.line_end]
        )


def test_common_prefix_is_merged_into_one_shared_container():
    config = (
        "set system services ssh protocol-version v2\n"
        "set system services ssh root-login deny\n"
    )
    result = flat_path.parse("ART-1", config, _GRAMMAR)
    ssh_containers = [
        n for n in result.tree.nodes.values()
        if n.kind == "container" and n.path == ("system", "services", "ssh")
    ]
    assert len(ssh_containers) == 1
    assert len(result.tree.children_of(ssh_containers[0].id)) == 2


def test_leaf_statement_has_verb_and_attribute_pair():
    config = "set system services ssh protocol-version v2\n"
    result = flat_path.parse("ART-1", config, _GRAMMAR)
    leaf = next(n for n in result.tree.nodes.values() if n.kind == "statement")
    assert leaf.verb == "set"
    assert leaf.attributes == {"protocol-version": "v2"}
    assert leaf.path == ("system", "services", "ssh", "protocol-version", "v2")
    assert leaf.line_start == 1 and leaf.line_end == 1


def test_delete_verb_is_retained_not_applied():
    config = "set system services ssh root-login deny\ndelete system services ssh root-login\n"
    result = flat_path.parse("ART-1", config, _GRAMMAR)
    verbs = sorted(n.verb for n in result.tree.nodes.values() if n.verb)
    assert verbs == ["delete", "set"]


def test_grammar_coverage_is_full_for_a_clean_config():
    config = "set system host-name fw-01\nset system services ssh protocol-version v2\n"
    result = flat_path.parse("ART-1", config, _GRAMMAR)
    assert result.coverage == 1
    assert result.status == "parsed"


def test_comment_and_blank_lines_do_not_corrupt_structure():
    config = "# top of file\nset system host-name fw-01\n\nset system services ssh root-login deny\n"
    result = flat_path.parse("ART-1", config, _GRAMMAR)
    comment_nodes = [n for n in result.tree.nodes.values() if n.kind == "comment"]
    blank_nodes = [n for n in result.tree.nodes.values() if n.kind == "blank"]
    assert len(comment_nodes) == 1
    assert len(blank_nodes) == 1
