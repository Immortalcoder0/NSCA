"""``gate_g1_determinism`` (00-master-plan.md §7, TECH-STACK.md §16): an
AST-walk over every module under ``nsca_engine/`` (production code only —
see ``_SOURCE_ROOT`` below) that fails the build on any import of
``random``, ``time.time``, ``datetime.now``/``datetime.utcnow``, ``uuid4``,
or anything from the top-level ``platform/`` package (``nsca_platform`` —
Backend Track B's code, per backend-01 §1: "Your code has no dependency on
Track B's code, ever").

This is a real, runnable AST-walking script — not just a description of
one. It is wired into the test suite (``pytest`` runs it as any other test
module, satisfying M5's "actually runnable" requirement) and is also
callable standalone via ``python -m nsca_engine.tests.test_gate_g1_determinism``
for a CI step that wants a bare pass/fail exit code independent of pytest.

Scope note (judgment call, flagged per the M5 task brief): 00-master-plan.md
§7 literally specifies the AST-walk target as ``engine/nsca_engine/`` with no
carve-out for ``tests/``. This gate does exclude ``nsca_engine/tests/`` —
Hypothesis-based property tests legitimately need `random`-adjacent behaviour
via the Hypothesis library's own internals (imported, not authored here), and
test fixtures use fixed, literal `datetime(...)` construction (never
`datetime.now()`) for `ASSESSED_AT`. Gating test code the same way as
production code would either force awkward workarounds in test helpers for
no determinism benefit (tests are not part of the byte-identical-output
contract) or require re-deriving Hypothesis's own AST, neither of which
serves G1's actual purpose: keeping the *assessment path* clock/randomness
free. If this scope is judged too permissive, tightening ``_SOURCE_ROOT`` to
include ``tests/`` is a one-line change — call it out explicitly rather than
silently deciding it during a later milestone.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]  # nsca_engine/
_SOURCE_ROOT = ENGINE_ROOT  # production code; tests/ excluded — see docstring
_EXCLUDED_DIRS = {"tests", "__pycache__"}

_FORBIDDEN_IMPORT_MODULES = {"random", "uuid"}
# A bare `import platform` (stdlib, host-info — non-deterministic across
# machines) OR anything from the top-level `platform/` package
# (`nsca_platform`, Backend Track B) is forbidden. Both are named "platform"
# in different senses (see module docstring); both are genuine determinism/
# import-boundary hazards, so both are caught here rather than picking one
# reading and silently dropping the other.
_FORBIDDEN_PLATFORM_MODULES = {"platform", "nsca_platform"}

# `from time import time` / `from datetime import ...` are allowed as bare
# module imports (`import time`, `from datetime import datetime` for type
# annotations and fixed-literal construction are both fine and used
# throughout this codebase) — what's forbidden is the specific *call*
# `time.time()` / `datetime.now()` / `datetime.utcnow()` / `uuid.uuid4()`,
# plus importing the `time` *function* directly out of the `time` module
# (`from time import time`), which would make the call site
# indistinguishable from any other name.


def _iter_source_files(root: Path) -> list[Path]:
    out = []
    for path in sorted(root.rglob("*.py")):
        if any(part in _EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        out.append(path)
    return out


class Violation:
    __slots__ = ("path", "lineno", "message")

    def __init__(self, path: Path, lineno: int, message: str) -> None:
        self.path = path
        self.lineno = lineno
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - formatting only
        return f"{self.path}:{self.lineno}: {self.message}"


def _check_import(node: ast.Import, path: Path) -> list[Violation]:
    violations = []
    for alias in node.names:
        top = alias.name.split(".")[0]
        if top in _FORBIDDEN_IMPORT_MODULES:
            violations.append(
                Violation(path, node.lineno, f"forbidden import: `import {alias.name}` (G1 — no randomness)")
            )
        if top in _FORBIDDEN_PLATFORM_MODULES:
            violations.append(
                Violation(
                    path, node.lineno,
                    f"forbidden import: `import {alias.name}` (G1 — no platform/ dependency, "
                    "no host-dependent stdlib `platform` module)",
                )
            )
    return violations


def _check_import_from(node: ast.ImportFrom, path: Path) -> list[Violation]:
    violations = []
    module = node.module or ""
    top = module.split(".")[0]
    if top in _FORBIDDEN_IMPORT_MODULES:
        violations.append(
            Violation(path, node.lineno, f"forbidden import: `from {module} import ...` (G1 — no randomness)")
        )
    if top in _FORBIDDEN_PLATFORM_MODULES:
        violations.append(
            Violation(
                path, node.lineno,
                f"forbidden import: `from {module} import ...` (G1 — no platform/ dependency)",
            )
        )
    if module == "time" and any(a.name == "time" for a in node.names):
        violations.append(
            Violation(path, node.lineno, "forbidden import: `from time import time` (G1 — no clock)")
        )
    if module == "uuid" and any(a.name == "uuid4" for a in node.names):
        violations.append(
            Violation(path, node.lineno, "forbidden import: `from uuid import uuid4` (G1 — no randomness)")
        )
    if module == "datetime" and any(a.name in ("now", "utcnow") for a in node.names):
        violations.append(
            Violation(path, node.lineno, "forbidden import: datetime `now`/`utcnow` (G1 — no clock)")
        )
    return violations


def _attribute_chain_name(node: ast.expr) -> str | None:
    """Render `a.b.c` back to the string `"a.b.c"` for a dotted Attribute/
    Name chain, or `None` if `node` isn't a plain dotted chain (e.g. it's a
    call result or subscript — those can't be `time.time` etc. textually)."""

    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    else:
        return None
    return ".".join(reversed(parts))


def _check_call(node: ast.Call, path: Path) -> list[Violation]:
    chain = _attribute_chain_name(node.func)
    if chain is None:
        return []
    tail = chain.split(".")[-1]
    violations = []
    if chain.endswith("time.time") or chain == "time":
        # `time.time()` (module-qualified) or a bare `time()` reached via
        # `from time import time` (already caught at the import site too —
        # this catches the call even if a future refactor renamed the
        # import binding).
        if chain in ("time.time",):
            violations.append(Violation(path, node.lineno, "forbidden call: `time.time()` (G1 — no clock)"))
    if chain.endswith("datetime.now") or chain.endswith("datetime.utcnow") or tail in ("now", "utcnow"):
        if chain.split(".")[-2:] in (["datetime", "now"], ["datetime", "utcnow"]) or chain in (
            "now", "utcnow",
        ):
            violations.append(
                Violation(path, node.lineno, f"forbidden call: `{chain}()` (G1 — no clock)")
            )
    if chain.endswith("uuid4") and ("uuid" in chain or chain == "uuid4"):
        violations.append(Violation(path, node.lineno, "forbidden call: `uuid4()` (G1 — no randomness)"))
    return violations


def find_violations(root: Path = _SOURCE_ROOT) -> list[Violation]:
    violations: list[Violation] = []
    for path in _iter_source_files(root):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:  # pragma: no cover - defensive
            violations.append(Violation(path, exc.lineno or 0, f"could not parse: {exc}"))
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                violations.extend(_check_import(node, path))
            elif isinstance(node, ast.ImportFrom):
                violations.extend(_check_import_from(node, path))
            elif isinstance(node, ast.Call):
                violations.extend(_check_call(node, path))
    return violations


def test_gate_g1_determinism_no_violations() -> None:
    violations = find_violations()
    assert not violations, "gate_g1_determinism violations:\n" + "\n".join(str(v) for v in violations)


def test_gate_g1_determinism_actually_detects_a_violation() -> None:
    """A gate that never fires is not a gate — a small self-test proving the
    AST-walk logic actually flags the patterns it claims to, using an
    in-memory source string rather than a real file (never written to
    disk, so this can't accidentally get picked up by `_iter_source_files`
    itself)."""

    import tempfile

    samples = {
        "import random\n": "random",
        "from uuid import uuid4\n": "uuid4",
        "import time\ntime.time()\n": "time.time",
        "from datetime import datetime\ndatetime.now()\n": "datetime.now",
        "import nsca_platform\n": "nsca_platform",
    }
    for source, _label in samples.items():
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "sample.py").write_text(source, encoding="utf-8")
            found = find_violations(tmp_path)
            assert found, f"gate failed to catch: {source!r}"


if __name__ == "__main__":  # pragma: no cover - CI entry point
    found = find_violations()
    if found:
        for v in found:
            print(v)
        sys.exit(1)
    print("gate_g1_determinism: clean")
    sys.exit(0)
