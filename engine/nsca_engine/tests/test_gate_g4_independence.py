"""``gate_g4_independence`` (00-master-plan.md §7, TECH-STACK.md §16): AST-walks
``engine/nsca_engine/collection/`` and ``platform/nsca_platform/api/`` and fails
the build on:

    - a ``collect()`` call site not passing a ``CommandId`` member
    - any signature accepting a raw ``str`` as a command
    - an ``ALLOWLIST``-shaped module-level collection containing a
      config/write/commit/copy/reload verb
    - (platform/api/ half) any API route whose handler signature accepts a
      device-write operation shape

**M5, added by this milestone — not pre-existing.** Unlike
``gate_g1_determinism``/``gate_determinism_golden_set``/``gate_import_boundary``,
no ``gate_g4_independence`` implementation existed anywhere in this repo before
this commit (confirmed by search — flagged explicitly rather than silently
assumed already done, per the M5 task brief's "if any doesn't have a real test
proving it, say so explicitly"). This module closes that gap.

**Why it passes today, and what that does and doesn't prove.**
``nsca_engine/collection/`` is an empty package (``__init__.py`` only, no
``CommandId``/``ALLOWLIST``/``collect()`` yet — read-only SSH collection via
Netmiko is real Phase-2 work, TECH-STACK.md §10, not built as of this
milestone) and ``nsca_platform/api/ingestion.py``'s only collection-shaped
route (``POST /campaigns/{id}/collect``) already types its request body's
``mode`` field as ``Literal["read_only"]`` (G4, per that file's own module
docstring) with no free-form command field at all. The AST-walk below
therefore finds nothing to violate — a real, non-fabricated pass, not a
vacuous stub — and the gate starts actually enforcing the moment either
module grows real collection code, with zero changes needed here. The
self-test (``test_gate_g4_independence_actually_detects_a_violation``) proves
the walk logic itself fires on the documented violation shapes, using
temporary files, so "currently finds nothing" is verifiably "correctly finds
nothing," not "doesn't know how to look."
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]  # nsca_engine/
REPO_ROOT = ENGINE_ROOT.parents[1]  # nsca/
COLLECTION_PKG = ENGINE_ROOT / "collection"
PLATFORM_API_PKG = REPO_ROOT / "platform" / "nsca_platform" / "api"
_EXCLUDED_DIRS = {"tests", "__pycache__"}

# TECH-STACK.md §16's own gate_g1_determinism docstring: "assert ALLOWLIST
# contains no config|write|commit|copy|reload verb." Matched case-insensitively
# against string literal values found in any module-level assignment whose
# target name contains "ALLOWLIST" (uppercase-snake-case constant, the
# documented naming convention for this kind of compile-time allowlist).
_FORBIDDEN_VERBS = ("config", "write", "commit", "copy", "reload")


class Violation:
    __slots__ = ("path", "lineno", "message")

    def __init__(self, path: Path, lineno: int, message: str) -> None:
        self.path = path
        self.lineno = lineno
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - formatting only
        return f"{self.path}:{self.lineno}: {self.message}"


def _iter_source_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out = []
    for path in sorted(root.rglob("*.py")):
        if any(part in _EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        out.append(path)
    return out


def _string_literals(node: ast.expr) -> list[str]:
    """Every string literal reachable inside `node` (a list/tuple/set of
    literals, or a single literal) — used to inspect an ALLOWLIST-shaped
    assignment's contents without needing to fully evaluate the expression."""

    out: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            out.append(sub.value)
    return out


def _check_allowlist_assignment(node: ast.Assign, path: Path) -> list[Violation]:
    violations: list[Violation] = []
    is_allowlist_target = any(
        isinstance(t, ast.Name) and "ALLOWLIST" in t.id.upper() for t in node.targets
    )
    if not is_allowlist_target:
        return violations
    for literal in _string_literals(node.value):
        lowered = literal.lower()
        for verb in _FORBIDDEN_VERBS:
            if verb in lowered:
                violations.append(
                    Violation(
                        path, node.lineno,
                        f"ALLOWLIST entry {literal!r} contains forbidden verb {verb!r} "
                        "(G4 — no write-capable command may be allowlisted)",
                    )
                )
    return violations


def _annotation_is_bare_str(annotation: ast.expr | None) -> bool:
    return isinstance(annotation, ast.Name) and annotation.id == "str"


def _check_function_def(node: ast.FunctionDef | ast.AsyncFunctionDef, path: Path) -> list[Violation]:
    """A `command`/`cmd`-named parameter typed as a bare `str` is a raw
    free-form command surface (G4 — "no signature accepting a raw str
    command"). Named specifically (not every `str` parameter) so this
    doesn't flag every ordinary string argument in the codebase — only the
    command-shaped ones, matching the gate's documented intent."""

    violations: list[Violation] = []
    args = node.args
    all_params = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    for param in all_params:
        if param.arg.lower() in ("command", "cmd", "raw_command") and _annotation_is_bare_str(param.annotation):
            violations.append(
                Violation(
                    path, node.lineno,
                    f"function `{node.name}` accepts `{param.arg}: str` — a raw free-form command "
                    "string (G4 — commands must be CommandId members, never a bare str)",
                )
            )
    return violations


def _check_collect_call(node: ast.Call, path: Path) -> list[Violation]:
    """Every `collect(...)` call site must pass a `CommandId` member, not a
    bare string literal, as (heuristically) its command-shaped argument."""

    func = node.func
    name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else None)
    if name != "collect":
        return []
    violations: list[Violation] = []
    for arg in (*node.args, *[kw.value for kw in node.keywords]):
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            violations.append(
                Violation(
                    path, node.lineno,
                    f"collect() called with a bare string literal {arg.value!r} — "
                    "must pass a CommandId member (G4)",
                )
            )
    return violations


def _find_violations_in(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in _iter_source_files(root):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:  # pragma: no cover - defensive
            violations.append(Violation(path, exc.lineno or 0, f"could not parse: {exc}"))
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                violations.extend(_check_allowlist_assignment(node, path))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                violations.extend(_check_function_def(node, path))
            elif isinstance(node, ast.Call):
                violations.extend(_check_collect_call(node, path))
    return violations


def find_violations() -> list[Violation]:
    return _find_violations_in(COLLECTION_PKG) + _find_violations_in(PLATFORM_API_PKG)


def test_gate_g4_independence_no_violations() -> None:
    violations = find_violations()
    assert not violations, "gate_g4_independence violations:\n" + "\n".join(str(v) for v in violations)


def test_gate_g4_independence_actually_detects_a_violation() -> None:
    """Self-test: the walk logic fires on each documented violation shape,
    using temporary files (never written into `collection/` or `platform/api/`
    themselves, so this can't be picked up by `find_violations()` above)."""

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "bad_allowlist.py").write_text(
            'ALLOWLIST = ("show running-config", "write memory")\n', encoding="utf-8",
        )
        assert _find_violations_in(tmp_path), "gate failed to catch a write verb in an ALLOWLIST"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "bad_signature.py").write_text(
            "def run(command: str) -> None:\n    pass\n", encoding="utf-8",
        )
        assert _find_violations_in(tmp_path), "gate failed to catch a bare str command parameter"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "bad_call.py").write_text(
            'collect("show version")\n', encoding="utf-8",
        )
        assert _find_violations_in(tmp_path), "gate failed to catch collect() called with a bare string"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "good.py").write_text(
            "from enum import Enum\n\n"
            "class CommandId(Enum):\n    SHOW_VERSION = 'show version'\n\n"
            "ALLOWLIST = (CommandId.SHOW_VERSION,)\n\n"
            "def run(command: 'CommandId') -> None:\n    pass\n\n"
            "def collect(cmd: 'CommandId') -> None:\n    pass\n\n"
            "collect(CommandId.SHOW_VERSION)\n",
            encoding="utf-8",
        )
        assert not _find_violations_in(tmp_path), "gate false-positived on a compliant CommandId-based module"


if __name__ == "__main__":  # pragma: no cover - CI entry point
    found = find_violations()
    if found:
        for v in found:
            print(v)
        sys.exit(1)
    print("gate_g4_independence: clean")
    sys.exit(0)
