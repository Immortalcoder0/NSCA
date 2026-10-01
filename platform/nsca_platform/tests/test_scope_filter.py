"""Unit tests for the scope filter expression evaluator (no DB needed)."""

from __future__ import annotations

import pytest

from nsca_platform.services.scope_filter import ScopeExpressionError, evaluate


def test_simple_equality() -> None:
    device = {"exposure": "internet_facing", "role": "access"}
    assert evaluate("exposure == 'internet_facing'", device, "dev-1") is True
    assert evaluate("exposure == 'internal'", device, "dev-1") is False


def test_and_or_parens() -> None:
    device = {"exposure": "internal", "role": "access"}
    expr = "exposure == 'internet_facing' or (role == 'access' and exposure == 'internal')"
    assert evaluate(expr, device, "dev-1") is True


def test_sample_is_deterministic() -> None:
    device = {"role": "access"}
    first = evaluate("sample(0.5)", device, "dev-42")
    second = evaluate("sample(0.5)", device, "dev-42")
    assert first == second


def test_sample_bounds() -> None:
    device: dict = {}
    assert evaluate("sample(0.0)", device, "dev-1") is False
    assert evaluate("sample(1.0)", device, "dev-1") is True


def test_rejects_arbitrary_code() -> None:
    with pytest.raises(ScopeExpressionError):
        evaluate("__import__('os').system('echo pwned')", {}, "dev-1")


def test_rejects_unknown_syntax() -> None:
    with pytest.raises(ScopeExpressionError):
        evaluate("exposure ===", {}, "dev-1")
