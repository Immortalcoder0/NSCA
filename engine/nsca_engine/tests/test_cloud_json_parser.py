"""Unit tests for parse/paradigms/cloud_json.py (TRD-02.1 §3.3 P7, cloud
policy JSON): position-tracking JSON parse (not stdlib `json`, which
discards positions — same G3 reasoning as xml.py/lxml), object->container,
array element indexing, scalar->statement mapping, and the malformed-JSON
hard-error case."""

from __future__ import annotations

from nsca_engine.parse.paradigms import cloud_json

_GRAMMAR = cloud_json.CloudJsonGrammarSpec()

_CONFIG = (
    "{\n"
    '  "hostname": "cloud-fw-01",\n'
    '  "management": {\n'
    '    "ssh_enabled": true,\n'
    '    "https_enabled": false\n'
    "  },\n"
    '  "rules": [\n'
    "    {\n"
    '      "name": "allow-ssh",\n'
    '      "action": "allow",\n'
    '      "port": 22\n'
    "    },\n"
    "    {\n"
    '      "name": "deny-all",\n'
    '      "action": "deny",\n'
    '      "port": 0\n'
    "    }\n"
    "  ]\n"
    "}\n"
)


def test_line_ranges_resolve_to_exact_source_text_span():
    result = cloud_json.parse("ART-1", _CONFIG, _GRAMMAR)
    for node in result.tree.nodes.values():
        if node.id == result.tree.root_id:
            continue
        raw = result.tree.raw(node)
        assert result.tree.lines[node.line_start - 1] in raw.split("\n")


def test_scalar_leaf_has_correct_line_and_value():
    result = cloud_json.parse("ART-1", _CONFIG, _GRAMMAR)
    hostname = next(n for n in result.tree.nodes.values() if n.path == ("hostname",))
    assert hostname.kind == "statement"
    assert hostname.attributes == {"hostname": "cloud-fw-01"}
    assert hostname.line_start == hostname.line_end == 2


def test_nested_object_becomes_container():
    result = cloud_json.parse("ART-1", _CONFIG, _GRAMMAR)
    mgmt = next(n for n in result.tree.nodes.values() if n.path == ("management",))
    assert mgmt.kind == "container"
    children = result.tree.children_of(mgmt.id)
    assert {c.head for c in children} == {"ssh_enabled", "https_enabled"}


def test_array_elements_are_indexed_in_path():
    result = cloud_json.parse("ART-1", _CONFIG, _GRAMMAR)
    rule_elements = [
        n for n in result.tree.nodes.values()
        if n.path and n.path[0] in ("rules[0]", "rules[1]")
    ]
    paths = {n.path[0] for n in rule_elements}
    assert paths == {"rules[0]", "rules[1]"}


def test_array_element_scalar_field_matches_source_line():
    result = cloud_json.parse("ART-1", _CONFIG, _GRAMMAR)
    deny_action = next(
        n for n in result.tree.nodes.values()
        if n.attributes.get("action") == "deny"
    )
    assert deny_action.line_start == 15


def test_malformed_json_is_refused():
    bad = '{"hostname": "x", "rules": [}'
    result = cloud_json.parse("ART-1", bad, _GRAMMAR)
    assert result.status == "refused"
    assert result.errors


def test_status_parsed_for_well_formed_document():
    result = cloud_json.parse("ART-1", _CONFIG, _GRAMMAR)
    assert result.status == "parsed"
