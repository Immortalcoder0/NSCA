"""Minimal, safe evaluator for campaign scope filter expressions.

15-api-specification.md §2's create example:

    "exposure == 'internet_facing' or (role == 'access' and sample(0.10))"

There is no formal grammar specified anywhere in the read docs for this
expression language — flagged as a judgment call. This module supports the
subset actually used in the spec's own examples: `==`, `!=`, boolean
`and`/`or`/`not`, parenthesisation, string/number literals, bare
identifiers resolved against a device's attribute dict, and a `sample(p)`
pseudo-function that does deterministic stratified sampling by hashing the
device's identifier (never `random`, to keep scope resolution
reproducible across runs against the same device set — determinism matters
here for the same reason it matters in the engine, per backend-02 §2.5).

Built on `ast.parse` with a restricted node whitelist rather than `eval`
directly — `eval` on an untrusted campaign-authored expression string would
be a code execution hole.
"""

from __future__ import annotations

import ast
import hashlib
from collections.abc import Mapping
from typing import Any

_ALLOWED_NODES = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Call,
)


class ScopeExpressionError(ValueError):
    pass


def _validate(node: ast.AST) -> None:
    if not isinstance(node, _ALLOWED_NODES):
        raise ScopeExpressionError(f"Disallowed expression element: {type(node).__name__}")
    for child in ast.iter_child_nodes(node):
        _validate(child)


def _sample_fraction(device_id: str, probability: float) -> bool:
    """Deterministic stratified sampling: hash the device id into [0, 1)
    and compare against the requested probability. Same device, same
    probability -> same inclusion decision every time (no `random`)."""

    digest = hashlib.sha256(device_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    return bucket < probability


def evaluate(expression: str, device: Mapping[str, Any], device_id: str) -> bool:
    """Evaluates `expression` against one device's attributes.

    Raises `ScopeExpressionError` on anything outside the supported
    subset, rather than silently returning False — a scope expression
    that fails to parse must be surfaced to the campaign author, not
    quietly resolve to an empty scope.
    """

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ScopeExpressionError(f"Invalid scope expression: {exc}") from exc
    _validate(tree)
    return bool(_eval_node(tree.body, device, device_id))


def _eval_node(node: ast.AST, device: Mapping[str, Any], device_id: str) -> Any:
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, device, device_id) for v in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_node(node.operand, device, device_id)
    if isinstance(node, ast.Compare):
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise ScopeExpressionError("Only single comparisons are supported")
        left = _eval_node(node.left, device, device_id)
        right = _eval_node(node.comparators[0], device, device_id)
        op = node.ops[0]
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        raise ScopeExpressionError(f"Unsupported comparison operator: {type(op).__name__}")
    if isinstance(node, ast.Name):
        return device.get(node.id)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id != "sample":
            raise ScopeExpressionError("Only sample(probability) calls are supported")
        if len(node.args) != 1:
            raise ScopeExpressionError("sample() takes exactly one argument")
        probability = _eval_node(node.args[0], device, device_id)
        return _sample_fraction(device_id, float(probability))
    raise ScopeExpressionError(f"Unsupported expression element: {type(node).__name__}")
