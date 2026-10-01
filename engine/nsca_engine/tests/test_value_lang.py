"""Unit tests for extract/value_lang.py (TRD-03.1 §3.3) — the extractor
value expression language: allowed operations succeed, disallowed
constructs (arbitrary code execution surface) are rejected at compile time
(INV-03.1-01)."""

from __future__ import annotations

import pytest

from nsca_engine.extract.value_lang import ValueLangError, compile_expr, evaluate_expr


def test_membership_over_split():
    compiled = compile_expr("'ssh' in split(protos) or 'all' in split(protos)")
    assert evaluate_expr(compiled, {"protos": "telnet ssh"}) is True
    assert evaluate_expr(compiled, {"protos": "ssh"}) is True
    assert evaluate_expr(compiled, {"protos": "telnet"}) is False


def test_to_seconds_addition():
    compiled = compile_expr("to_seconds(m, 'minutes') + to_seconds(s, 'seconds')")
    assert evaluate_expr(compiled, {"m": "5", "s": "30"}) == 330


def test_map_lookup():
    compiled = compile_expr("map_lookup('cisco_pw_types', ptype)")
    assert evaluate_expr(compiled, {"ptype": "7"}, {"cisco_pw_types": {"7": "reversible"}}) == "reversible"


def test_int_cast():
    compiled = compile_expr("int(priv)")
    assert evaluate_expr(compiled, {"priv": "15"}) == 15


@pytest.mark.parametrize(
    "malicious",
    [
        "__import__('os').system('echo pwned')",
        "open('/etc/passwd').read()",
        "[x for x in range(10)]",
        "(lambda: 1)()",
        "eval('1')",
        "exec('1')",
    ],
)
def test_disallowed_constructs_rejected_at_compile_time(malicious):
    with pytest.raises(ValueLangError):
        compile_expr(malicious)
