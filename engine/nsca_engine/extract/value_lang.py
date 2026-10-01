"""The extractor value expression language (TRD-03.1 §3.3).

Deliberately minimal, total and side-effect free — the same "declarative
content, no code execution" property that governs the (separate, richer)
control assertion language in ``controls/expression.py`` (INV-03.1-01,
NFR-SEC-007): rulepacks are importable content, so an extractor capable of
arbitrary execution would make importing a community rulepack a remote code
execution vector.

Implementation approach: parse with ``ast.parse(expr, mode="eval")`` and walk
the resulting tree with a strict allow-list of node types and function names.
Anything outside the allow-list (imports, attribute access beyond
``x.field``, comprehensions, lambdas, calls to unknown names, etc.) is
rejected at *compile* time, before the extractor ever runs against a device.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping
from typing import Any


class ValueLangError(ValueError):
    """Raised when an extractor value expression is malformed or attempts
    something outside the allowed subset (INV-03.1-01)."""


_ALLOWED_NODE_TYPES = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.In,
    ast.NotIn,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.BinOp,
    ast.Add,
)

_ALLOWED_FUNCS: Mapping[str, Callable[..., Any]] = {}


def _split(s: Any, sep: str | None = None) -> list[str]:
    if s is None:
        return []
    return str(s).split(sep) if sep else str(s).split()


def _lower(s: Any) -> str:
    return str(s).lower() if s is not None else ""


def _trim(s: Any) -> str:
    return str(s).strip() if s is not None else ""


def _startswith(s: Any, prefix: str) -> bool:
    return str(s).startswith(prefix) if s is not None else False


def _contains(s: Any, sub: str) -> bool:
    return sub in str(s) if s is not None else False


def _int(v: Any) -> int | None:
    if v is None:
        return None
    result: int = int(v)
    return result


def _to_seconds(v: Any, unit: str) -> int | None:
    if v is None:
        return None
    seconds: int = int(v)
    if unit == "seconds":
        return seconds
    if unit == "minutes":
        return seconds * 60
    if unit == "hours":
        return seconds * 3600
    raise ValueLangError(f"unknown time unit: {unit}")


_ALLOWED_FUNCS = {
    "split": _split,
    "lower": _lower,
    "trim": _trim,
    "startswith": _startswith,
    "contains": _contains,
    "int": _int,
    "to_seconds": _to_seconds,
}


def compile_expr(source: str) -> ast.Expression:
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        raise ValueLangError(f"invalid value expression {source!r}: {exc}") from exc
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODE_TYPES):
            raise ValueLangError(
                f"value expression {source!r} uses a disallowed construct: "
                f"{type(node).__name__}"
            )
        if isinstance(node, ast.Call):
            allowed_names = set(_ALLOWED_FUNCS) | {"map_lookup"}
            if not isinstance(node.func, ast.Name) or node.func.id not in allowed_names:
                raise ValueLangError(
                    f"value expression {source!r} calls an unknown function"
                )
    return tree


def evaluate_expr(
    compiled: ast.Expression, captures: Mapping[str, Any], lookup: Mapping[str, Any] | None = None
) -> Any:
    """Evaluate a compiled value expression against regex capture groups
    plus optional ``map_lookup`` tables (declared by the rulepack)."""

    lookup = lookup or {}

    def ev(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id == "true":
                return True
            if node.id == "false":
                return False
            if node.id in captures:
                return captures[node.id]
            raise ValueLangError(f"unknown identifier: {node.id}")
        if isinstance(node, ast.List) or isinstance(node, ast.Tuple):
            return [ev(e) for e in node.elts]
        if isinstance(node, ast.BoolOp):
            values = [ev(v) for v in node.values]
            if isinstance(node.op, ast.And):
                result = True
                for v in values:
                    result = result and bool(v)
                return result
            result = False
            for v in values:
                result = result or bool(v)
            return result
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not bool(ev(node.operand))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = ev(node.left), ev(node.right)
            if left is None or right is None:
                return None
            return left + right
        if isinstance(node, ast.Compare):
            left = ev(node.left)
            for op, comparator in zip(node.ops, node.comparators, strict=True):
                right = ev(comparator)
                if isinstance(op, ast.Eq):
                    ok = left == right
                elif isinstance(op, ast.NotEq):
                    ok = left != right
                elif isinstance(op, ast.In):
                    ok = left in right
                elif isinstance(op, ast.NotIn):
                    ok = left not in right
                else:
                    raise ValueLangError("unsupported comparison operator")
                if not ok:
                    return False
                left = right
            return True
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                # Unreachable through `compile_expr` — the allow-list walk
                # (`_validate`, below) only accepts `ast.Name` as a call
                # target. Kept as a real check (not a bare `type: ignore`)
                # so a future change to the allow-list fails loudly here
                # instead of hitting an AttributeError deeper in `ev`.
                raise ValueLangError("unsupported call target")
            func_name = node.func.id
            args = [ev(a) for a in node.args]
            if func_name == "map_lookup":
                table_name, key = args
                table = lookup.get(table_name, {})
                return table.get(key)
            return _ALLOWED_FUNCS[func_name](*args)
        raise ValueLangError(f"unsupported node: {type(node).__name__}")

    return ev(compiled)
