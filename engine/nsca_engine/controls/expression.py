"""The control assertion expression language (TRD-05.1) — three-valued
(Kleene) logic over the fact set.

Per backend-01 §5.3: Lark generates the parser from the EBNF grammar below;
the Kleene evaluator itself is hand-written (TRD-05.1 §3.2 truth tables
cannot come from an off-the-shelf library — TECH-STACK.md §7). The grammar
covers exactly the subset the M1 native control library
(``knowledge/control_packs/nsca_native.yaml``) uses: boolean/comparison/
membership expressions, ``and``/``or``/``not``, and single-level collection
quantifiers (``all``/``any``/``none``/``count``) with a lambda-style
predicate (TRD-05.1 §3.5). Nested quantifiers beyond depth 1 and lookup-table
sharing across packs are out of scope for M1 (TRD-05.1 §3.8/§8 already flags
depth-2 nesting as a complexity bound; M1's control set does not need it).

``⊥`` (unknown) is represented internally as Python ``None`` threaded through
every operator per the exact truth tables in TRD-05.1 §3.2/§3.3 — comparisons
and quantifiers over an unknown operand yield ``⊥``, never silently
``False`` (the single most common three-valued implementation error, per the
TRD).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from lark import Lark, Token, Tree

# `⊥` is represented as None. Kleene = True | False | None.
Kleene = bool | None

# `_eval` legitimately returns a bare `int` for a `count(...)` quantifier
# node (see `_quant_count`/the "quantifier" branch below) — the grammar
# allows `count(...)` to appear anywhere an `or_expr` operand can, including
# directly under `and`/`or` with no surrounding comparison. `evaluate()`
# already guards against that specific misuse with an explicit
# `ExpressionError` at the top level (TRD-05.1 §4's compile/evaluate split —
# this is an evaluation-time check, not a compile-time grammar restriction).
# `k_and`/`k_or` themselves are correctly typed against `Kleene` only, so the
# two call sites that feed a raw `_eval` result into them are annotated
# `type: ignore[arg-type]` rather than duplicating `evaluate()`'s guard at
# every recursion point.
EvalResult = Kleene | int

_GRAMMAR = r"""
    ?start: or_expr

    ?or_expr: and_expr ("or" and_expr)*   -> or_op
    ?and_expr: not_expr ("and" not_expr)* -> and_op
    ?not_expr: "not" not_expr             -> not_op
             | atom

    ?atom: value "|" QUANT "(" NAME "=>" or_expr ")" -> quantifier
         | value COMPOP value                        -> compare
         | value "in" value                          -> membership
         | value
         | "(" or_expr ")"

    COMPOP: "==" | "!=" | "<=" | ">=" | "<" | ">"
    QUANT: "all" | "any" | "none" | "count"

    ?value: "true"                    -> true_lit
          | "false"                   -> false_lit
          | INT                       -> int_lit
          | STRING                    -> string_lit
          | list_lit
          | PATH                      -> path_lit

    list_lit: "[" [value ("," value)*] "]"

    PATH: NAME ("." NAME)*
    NAME: /[a-zA-Z_][a-zA-Z0-9_]*/
    INT: /-?[0-9]+/
    STRING: /"[^"]*"/

    %import common.WS
    %ignore WS
"""

_parser = Lark(_GRAMMAR, parser="lalr", start="start")


class ExpressionError(ValueError):
    """Raised on a syntax error or a disallowed construct — surfaced at
    control-pack *load* time (TRD-05.1 §4: "compilation happens once at
    control-pack load; evaluation never parses"), never at evaluation."""


@dataclass(frozen=True, slots=True)
class CompiledExpression:
    source: str
    tree: Tree[Token]


def compile_expr(source: str) -> CompiledExpression:
    try:
        tree = _parser.parse(source)
    except Exception as exc:  # lark raises several distinct error types
        raise ExpressionError(f"failed to parse assertion {source!r}: {exc}") from exc
    return CompiledExpression(source=source, tree=tree)


# ---------------------------------------------------------------------------
# Kleene primitives (TRD-05.1 §3.2, §3.3) — hand-written, not derived from
# the grammar/parser.
# ---------------------------------------------------------------------------


def k_and(a: Kleene, b: Kleene) -> Kleene:
    if a is False or b is False:
        return False
    if a is None or b is None:
        return None
    return True


def k_or(a: Kleene, b: Kleene) -> Kleene:
    if a is True or b is True:
        return True
    if a is None or b is None:
        return None
    return False


def k_not(a: Kleene) -> Kleene:
    if a is None:
        return None
    return not a


def k_eq(a: Any, b: Any) -> Kleene:
    if a is None or b is None:
        return None
    return bool(a == b)


def k_ne(a: Any, b: Any) -> Kleene:
    r = k_eq(a, b)
    return None if r is None else (not r)


def k_cmp(op: str, a: Any, b: Any) -> Kleene:
    if a is None or b is None:
        return None
    if op == "<":
        return bool(a < b)
    if op == "<=":
        return bool(a <= b)
    if op == ">":
        return bool(a > b)
    if op == ">=":
        return bool(a >= b)
    raise ExpressionError(f"unsupported comparison operator: {op}")


def k_in(a: Any, b: Any) -> Kleene:
    if a is None or b is None:
        return None
    return bool(a in b)


# ---------------------------------------------------------------------------
# Evaluation (TRD-05.1 §3.5 quantifier semantics; §3.9 evaluation trace)
# ---------------------------------------------------------------------------

# A resolver maps a dotted fact path to a Kleene-valued Python object (bool,
# int, str, list, or None for ⊥). Collections are resolved as list[Mapping].
Resolver = Callable[[str], Any]


@dataclass
class EvalContext:
    resolve_path: Resolver
    lookup_tables: Mapping[str, Any]
    trace: list[str]
    env: dict[str, Any]


def _quant_all(values: list[Kleene]) -> Kleene:
    if any(v is False for v in values):
        return False
    if any(v is None for v in values):
        return None
    return True


def _quant_any(values: list[Kleene]) -> Kleene:
    if any(v is True for v in values):
        return True
    if any(v is None for v in values):
        return None
    return False


def _quant_count(values: list[Kleene]) -> int | None:
    if any(v is None for v in values):
        return None
    return sum(1 for v in values if v)


def _resolve_value_node(node: Tree[Token] | Token, ctx: EvalContext) -> Any:
    if isinstance(node, Tree):
        if node.data == "true_lit":
            return True
        if node.data == "false_lit":
            return False
        if node.data == "int_lit":
            return int(str(node.children[0]))
        if node.data == "string_lit":
            return str(node.children[0])[1:-1]
        if node.data == "list_lit":
            return [_resolve_value_node(c, ctx) for c in node.children]
        if node.data == "path_lit":
            return _resolve_path(str(node.children[0]), ctx)
    raise ExpressionError(f"unsupported value node: {node!r}")


def _resolve_path(path: str, ctx: EvalContext) -> Any:
    head, _, rest = path.partition(".")
    if head in ctx.env:
        obj = ctx.env[head]
        if rest == "":
            return obj
        cur = obj
        for segment in rest.split("."):
            if cur is None:
                return None
            if isinstance(cur, Mapping):
                cur = cur.get(segment)
            else:
                cur = getattr(cur, segment, None)
        return cur
    if path in ctx.lookup_tables:
        return ctx.lookup_tables[path]
    return ctx.resolve_path(path)


def _eval(node: Tree[Token] | Token, ctx: EvalContext) -> EvalResult:
    if isinstance(node, Token):
        raise ExpressionError(f"unexpected bare token: {node!r}")

    if node.data == "or_op":
        result: Kleene = False
        for child in node.children:
            result = k_or(result, _eval(child, ctx))  # type: ignore[arg-type]
        return result
    if node.data == "and_op":
        result = True
        for child in node.children:
            result = k_and(result, _eval(child, ctx))  # type: ignore[arg-type]
        return result
    if node.data == "not_op":
        return k_not(_eval(node.children[0], ctx))  # type: ignore[arg-type]
    if node.data == "compare":
        left_val = _resolve_value_node(node.children[0], ctx)
        op = str(node.children[1])
        right_val = _resolve_value_node(node.children[2], ctx)
        if op == "==":
            r = k_eq(left_val, right_val)
        elif op == "!=":
            r = k_ne(left_val, right_val)
        else:
            r = k_cmp(op, left_val, right_val)
        ctx.trace.append(f"{left_val!r} {op} {right_val!r} -> {r!r}")
        return r
    if node.data == "membership":
        left_val = _resolve_value_node(node.children[0], ctx)
        right_val = _resolve_value_node(node.children[1], ctx)
        return k_in(left_val, right_val)
    if node.data == "quantifier":
        collection_path_node = node.children[0]
        if not isinstance(collection_path_node, Tree):
            # Unreachable for a grammar-compiled expression — the `value`
            # rule always wraps a quantifier's collection operand in a
            # `path_lit` `Tree` (`PATH -> path_lit`); a bare `Token` here
            # would mean the grammar itself changed shape.
            raise ExpressionError("quantifier collection operand must be a path")
        collection_path = str(collection_path_node.children[0])
        quant = str(node.children[1])
        var_name = str(node.children[2])
        body = node.children[3]
        elements = ctx.resolve_path(collection_path)
        if elements is None:
            # INV-05.1-01: an unknown-valued collection is not an empty one.
            ctx.trace.append(f"{collection_path} is unknown (UNKNOWN) -> {quant} = UNKNOWN")
            return None
        values: list[Kleene] = []
        for element in elements:
            child_ctx = EvalContext(
                resolve_path=ctx.resolve_path,
                lookup_tables=ctx.lookup_tables,
                trace=ctx.trace,
                env={**ctx.env, var_name: element},
            )
            values.append(_eval(body, child_ctx))  # type: ignore[arg-type]
        if quant == "all":
            r = _quant_all(values)
        elif quant == "any":
            r = _quant_any(values)
        elif quant == "none":
            r = k_not(_quant_any(values))
        elif quant == "count":
            c = _quant_count(values)
            return c  # not boolean; only usable in a further comparison
        else:  # pragma: no cover - defensive
            raise ExpressionError(f"unknown quantifier: {quant}")
        ctx.trace.append(f"{collection_path} | {quant}(...) -> {r!r}")
        return r

    # A bare `value` atom (e.g. a lone `PATH` reference used as a whole
    # assertion body) resolves through `_resolve_path`/`ctx.resolve_path` to
    # whatever type that fact actually holds — not necessarily `Kleene`/
    # `int`. That is an existing, accepted looseness at this evaluator's
    # boundary (comparisons are what normally narrow a fact value to
    # Kleene; a bare reference is a control-authoring edge case, not a
    # redesign this milestone should take on).
    return _resolve_value_node(node, ctx)  # type: ignore[no-any-return]


def evaluate(
    compiled: CompiledExpression,
    resolve_path: Resolver,
    lookup_tables: Mapping[str, Any] | None = None,
) -> tuple[Kleene, tuple[str, ...]]:
    """Evaluate a compiled assertion against ``resolve_path`` (fact
    resolution). Returns ``(value, trace)`` — the trace names the deciding
    term (INV-05.1-02)."""

    ctx = EvalContext(
        resolve_path=resolve_path,
        lookup_tables=lookup_tables or {},
        trace=[],
        env={},
    )
    value = _eval(compiled.tree, ctx)
    if isinstance(value, int) and not isinstance(value, bool):
        raise ExpressionError(
            "top-level assertion must be boolean-valued (⊥/true/false), "
            f"got an integer from {compiled.source!r} — likely a bare "
            "count(...) expression missing a comparison"
        )
    return value, tuple(ctx.trace)
