"""
RED test for S9-001 — no test function should call asyncio.run().

Current state (RED):
    tests/test_phase02_decoupling.py, test_phase02_migration.py,
    test_phase03_integration.py, test_phase03_revalidation.py each wrap an
    inner `async def run_test()` and call `asyncio.run(run_test())` inside
    a sync test function. This conflicts with pytest.ini's
    `asyncio_mode = auto` contract: any change to that config silently
    breaks those tests, and the nested event-loop pattern is fragile
    (cf. AUDIT[A7-001] 🔴 CRITICAL).

Expected state after GREEN:
    Test bodies are migrated to `@pytest.mark.asyncio` + `async def test_...`.
    No `asyncio.run(...)` is called from inside a test function.
    Standalone scripts (`if __name__ == "__main__":`) are legitimate and not
    affected by this rule.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


TESTS_DIR = Path(__file__).resolve().parent


def _find_asyncio_run_in_test_funcs(file_path: Path) -> list[tuple[str, int]]:
    """Return (function_name, lineno) for every test function that calls
    asyncio.run(). Classes are descended; bodies of `if __name__ == "__main__"`
    blocks are ignored (those are standalone scripts)."""
    try:
        source = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []

    offenders: list[tuple[str, int]] = []

    def _walk_callable(node: ast.AST, parent_name: str | None) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fqname = node.name if parent_name is None else f"{parent_name}.{node.name}"
            # Only inspect test_* functions (pytest convention).
            if node.name.startswith("test_"):
                for sub in ast.walk(node):
                    if (
                        isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == "run"
                        and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == "asyncio"
                    ):
                        offenders.append((fqname, sub.lineno))
            # Recurse into nested callables to catch helper funcs inside tests.
            for child in ast.iter_child_nodes(node):
                _walk_callable(child, fqname)
        elif isinstance(node, ast.ClassDef):
            for child in ast.iter_child_nodes(node):
                _walk_callable(child, node.name)

    for top in ast.iter_child_nodes(tree):
        _walk_callable(top, None)

    return offenders


TARGET_FILES = [
    "test_phase02_decoupling.py",
    "test_phase02_migration.py",
    "test_phase03_integration.py",
    "test_phase03_revalidation.py",
]


@pytest.mark.parametrize("filename", TARGET_FILES)
def test_no_asyncio_run_in_test_functions(filename: str) -> None:
    """RED: each target file currently hosts asyncio.run() inside tests."""
    path = TESTS_DIR / filename
    assert path.exists(), f"expected {filename} under tests/"
    offenders = _find_asyncio_run_in_test_funcs(path)
    assert not offenders, (
        f"{filename}: {len(offenders)} test function(s) still use asyncio.run() — "
        f"migrate to @pytest.mark.asyncio + async def test_...\n"
        f"Offenders: {offenders!r}"
    )
