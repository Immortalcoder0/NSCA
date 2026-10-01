"""Exhaustive Kleene (three-valued logic) truth-table tests (TRD-05.1 §3.2,
V-05.1-001/002/003) — written as one of the first tests in this module, per
backend-01 §5.3, before the full grammar was built out.
"""

from __future__ import annotations

import itertools

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nsca_engine.controls.expression import (
    _quant_all,
    _quant_any,
    _quant_count,
    k_and,
    k_cmp,
    k_eq,
    k_in,
    k_ne,
    k_not,
    k_or,
)

TRUTHY = (True, False, None)

_AND_TABLE = {
    (True, True): True, (True, False): False, (True, None): None,
    (False, True): False, (False, False): False, (False, None): False,
    (None, True): None, (None, False): False, (None, None): None,
}

_OR_TABLE = {
    (True, True): True, (True, False): True, (True, None): True,
    (False, True): True, (False, False): False, (False, None): None,
    (None, True): True, (None, False): None, (None, None): None,
}


@pytest.mark.parametrize("a,b", list(itertools.product(TRUTHY, TRUTHY)))
def test_and_truth_table_exhaustive(a, b):
    assert k_and(a, b) == _AND_TABLE[(a, b)]


@pytest.mark.parametrize("a,b", list(itertools.product(TRUTHY, TRUTHY)))
def test_or_truth_table_exhaustive(a, b):
    assert k_or(a, b) == _OR_TABLE[(a, b)]


def test_not_unknown_is_unknown():
    assert k_not(None) is None
    assert k_not(True) is False
    assert k_not(False) is True


# DD-05.1-01's "whole point" cells, called out explicitly.
def test_false_and_unknown_is_false():
    assert k_and(False, None) is False
    assert k_and(None, False) is False


def test_true_and_unknown_is_unknown():
    assert k_and(True, None) is None
    assert k_and(None, True) is None


def test_true_or_unknown_is_true():
    assert k_or(True, None) is True
    assert k_or(None, True) is True


def test_false_or_unknown_is_unknown():
    assert k_or(False, None) is None
    assert k_or(None, False) is None


# V-05.1-002: comparison with unknown yields unknown, never false.
@given(st.one_of(st.booleans(), st.integers(), st.text(), st.none()))
def test_eq_with_none_operand_is_never_false(value):
    assert k_eq(None, value) is None
    assert k_eq(value, None) is None
    r = k_ne(None, value)
    assert r is None
    r2 = k_ne(value, None)
    assert r2 is None


@given(st.integers())
def test_cmp_with_none_operand_is_never_false(value):
    for op in ("<", "<=", ">", ">="):
        assert k_cmp(op, None, value) is None
        assert k_cmp(op, value, None) is None


def test_in_with_unknown_operand_is_unknown():
    assert k_in(None, [1, 2, 3]) is None
    assert k_in(1, None) is None


# V-05.1-003: quantifier semantics under unknown.
def test_quant_all_false_if_any_false():
    assert _quant_all([True, False, None]) is False


def test_quant_all_unknown_if_none_false_but_some_unknown():
    assert _quant_all([True, None, True]) is None


def test_quant_all_true_if_all_true():
    assert _quant_all([True, True]) is True


def test_quant_all_true_on_empty_collection():
    # TRD-05.1 §5 edge case: vacuously true — vacuity classification (TRD-
    # 05.2) is what prevents this being reported as a meaningful pass, not
    # the expression language itself.
    assert _quant_all([]) is True


def test_quant_any_true_if_any_true():
    assert _quant_any([False, True, None]) is True


def test_quant_any_unknown_if_none_true_but_some_unknown():
    assert _quant_any([False, None]) is None


def test_quant_any_false_if_all_false():
    assert _quant_any([False, False]) is False


def test_quant_count_unknown_if_any_unknown():
    assert _quant_count([True, None, False]) is None


def test_quant_count_is_strict_never_short_circuits():
    assert _quant_count([True, True, None]) is None
    assert _quant_count([True, True, False]) == 2
