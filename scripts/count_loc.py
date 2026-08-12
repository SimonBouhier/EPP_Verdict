#!/usr/bin/env python
"""
Deterministic LOC counter for EPP_Verdict.

Walks the repo from the project root, applies an explicit exclusion list
(directories, file names, extensions), classifies the survivors by
language and role, and reports three metrics per category:

    - files     : number of files matched
    - lines     : raw line count (matches `wc -l` on Unix)
    - non_blank : lines with at least one non-whitespace character
    - code      : non_blank minus single-line comment lines

The "code" metric uses naive single-line comment detection per
language. Limitations (deliberate, in exchange for determinism):

    - Block comments (`/* */`, `<!-- -->`) over multiple lines are NOT
      stripped. Each block-comment line is counted as code.
    - Python triple-quoted strings used as docstrings are counted as
      code (they are technically expressions).
    - Inline comments after code (`x = 1  # note`) leave the line
      counted as code.

This makes the "code" count a slight overcount of substantive logic,
never an undercount. If you want a more conservative metric, read
`non_blank`.

Usage:
    python scripts/count_loc.py                 # full report
    python scripts/count_loc.py --top 15        # +list 15 largest files
    python scripts/count_loc.py --raw           # disable code detection,
                                                #   only files/lines/non_blank
    python scripts/count_loc.py --json          # JSON output for scripting
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Exclusions (path prefixes from repo root + filenames anywhere)
# ---------------------------------------------------------------------------

EXCLUDED_PATH_PREFIXES = {
    # Vendored / generated
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".git",
    ".claude",
    ".ccd_session",
    ".agents",
    "target",
    "dist",
    "build",
    "out",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".vite",
    ".next",
    ".turbo",
    ".cache",
    "coverage",
    "htmlcov",
    ".nyc_output",
    ".idea",
    ".vscode",
    ".vs",
    # Data, not code
    "demos/benchmark_runs",
    "demos/data",
    "data",
    "ui/public/data",
    "ui/dist",
    "ui/node_modules",
    # Lean build artifacts
    "Formal/.lake",
    # Anchor / Solana test-ledger artifacts (may contain unreadable named pipes)
    ".anchor",
    # Project archives / reports
    "docs/archives",
    "reports",
    "test_results",
    # Working / scratch
    "Work_in_Progress",
}

# Filenames to skip wherever they appear.
EXCLUDED_FILENAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "lake-manifest.json",
    "Cargo.lock",
    ".DS_Store",
    ".gitignore",
    ".gitattributes",
    ".npmrc",
    ".prettierrc",
    ".eslintrc",
    "tsconfig.tsbuildinfo",
}

# Extension exclusions (anything not in INCLUDED is implicitly skipped,
# but we list these here so it's explicit what we treat as non-code).
EXCLUDED_EXTENSIONS = {
    ".md",
    ".txt",
    ".pdf",
    ".rst",
    ".log",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".cfg",
    ".ini",
    ".env",
    ".lock",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".webp",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".bin",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".pyc",
    ".pyo",
    ".pyd",
    ".rlib",
    ".rmeta",
    ".o",
    ".obj",
    ".pkl",
    ".pickle",
    ".npy",
    ".npz",
    ".html",  # docs only — we make an exception below for ui/index.html
}

# Languages we DO count, mapped to a category label and a tuple of
# single-line comment prefixes.
@dataclass(frozen=True)
class LangSpec:
    label: str
    comment_prefixes: tuple[str, ...]


LANG_BY_EXT: dict[str, LangSpec] = {
    ".py": LangSpec("Python", ("#",)),
    ".ts": LangSpec("TypeScript", ("//",)),
    ".tsx": LangSpec("TypeScript (TSX)", ("//",)),
    ".js": LangSpec("JavaScript", ("//",)),
    ".jsx": LangSpec("JavaScript (JSX)", ("//",)),
    ".mjs": LangSpec("JavaScript (ESM)", ("//",)),
    ".cjs": LangSpec("JavaScript (CJS)", ("//",)),
    ".rs": LangSpec("Rust", ("//",)),
    ".lean": LangSpec("Lean", ("--",)),
    ".sql": LangSpec("SQL", ("--",)),
    ".css": LangSpec("CSS", ("//",)),
    ".scss": LangSpec("SCSS", ("//", "/*")),
    ".sh": LangSpec("Shell", ("#",)),
    ".bat": LangSpec("Batch", ("REM ", "REM\t", "::", "@REM")),
    ".ps1": LangSpec("PowerShell", ("#",)),
}


# ---------------------------------------------------------------------------
# Walk and filter
# ---------------------------------------------------------------------------


def is_excluded_path(rel: Path) -> bool:
    """Return True if `rel` (relative to REPO_ROOT) is under an excluded prefix."""
    parts = rel.parts
    if not parts:
        return False
    # Match against full prefix paths.
    for prefix in EXCLUDED_PATH_PREFIXES:
        prefix_parts = Path(prefix).parts
        if parts[: len(prefix_parts)] == prefix_parts:
            return True
    # Also match any single dir name that's a top-level exclude.
    for part in parts[:-1]:  # exclude the file itself
        if part in EXCLUDED_PATH_PREFIXES:
            return True
    return False


def iter_source_files(root: Path) -> Iterable[Path]:
    """Yield (rel_path) of every code file we want to count."""
    for path in root.rglob("*"):
        # Defensive: some Windows symlinks / named pipes (e.g. Solana test-ledger
        # validator.log) raise OSError on stat. Treat them as non-files.
        try:
            if not path.is_file():
                continue
        except OSError:
            continue
        rel = path.relative_to(root)
        if is_excluded_path(rel):
            continue
        if path.name in EXCLUDED_FILENAMES:
            continue
        ext = path.suffix.lower()
        # Special case: include ui/index.html (the SPA shell) but not arbitrary HTML.
        if ext == ".html":
            if rel == Path("ui/index.html"):
                yield rel
            continue
        if ext in EXCLUDED_EXTENSIONS:
            continue
        if ext not in LANG_BY_EXT:
            continue  # unknown extension, skip silently
        yield rel


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------


@dataclass
class FileCount:
    rel: Path
    category: str
    lines: int
    non_blank: int
    code: int


def categorize(rel: Path, lang: LangSpec) -> str:
    """Return a category label combining language and role."""
    parts = rel.parts
    ext = rel.suffix.lower()

    if ext == ".py":
        # Python role detection
        is_test = (
            "tests" in parts
            or rel.name.startswith("test_")
            or rel.name.endswith("_test.py")
        )
        if is_test:
            return "Python — tests"
        if "demos" in parts:
            return "Python — demos / scenarios"
        if "scripts" in parts:
            return "Python — scripts / tooling"
        if "Formal" in parts:
            return "Python — other"
        if any(p in {"services", "database", "app", "cli"} for p in parts):
            return "Python — production (services, database, app, cli)"
        return "Python — other"

    if ext in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
        if "ui" in parts:
            if any(p in {"tests", "__tests__"} for p in parts) or rel.name.endswith(
                (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")
            ):
                return f"{lang.label} (ui — tests)"
            if "scripts" in parts:
                return f"{lang.label} (ui — build scripts)"
            return f"{lang.label} (ui — app)"
        return lang.label

    if ext == ".rs":
        return "Rust (Anchor program)"
    if ext == ".lean":
        return "Lean (formal proofs)"
    if ext == ".sql":
        return "SQL (schema)"
    if ext in {".css", ".scss"}:
        return "CSS (ui)"
    if ext == ".html":
        return "HTML (ui shell)"
    if ext == ".sh":
        return "Shell scripts"
    if ext == ".bat":
        return "Batch scripts"
    if ext == ".ps1":
        return "PowerShell scripts"
    return lang.label


def count_file(path: Path, lang: LangSpec) -> tuple[int, int, int]:
    """Returns (lines, non_blank, code) for a single file. Best-effort encoding."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="latin-1")
        except OSError as exc:
            raise OSError(f"unable to read source file: {path}") from exc
    # Splitlines counts trailing newline correctly: "a\nb" → 2 lines, "a\nb\n" → 2 lines.
    # We use a different convention to match `wc -l` (which counts newlines):
    # raw lines = number of newlines + (1 if last char is not newline and text not empty else 0).
    if not text:
        return (0, 0, 0)
    lines_list = text.splitlines()
    raw_lines = text.count("\n")
    if not text.endswith("\n"):
        raw_lines += 1

    non_blank = 0
    code = 0
    for line in lines_list:
        stripped = line.strip()
        if not stripped:
            continue
        non_blank += 1
        if any(stripped.startswith(p) for p in lang.comment_prefixes):
            continue
        code += 1
    return (raw_lines, non_blank, code)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def aggregate(files: list[FileCount]) -> dict[str, dict[str, int]]:
    agg: dict[str, dict[str, int]] = defaultdict(
        lambda: {"files": 0, "lines": 0, "non_blank": 0, "code": 0}
    )
    for fc in files:
        bucket = agg[fc.category]
        bucket["files"] += 1
        bucket["lines"] += fc.lines
        bucket["non_blank"] += fc.non_blank
        bucket["code"] += fc.code
    return agg


def print_table(agg: dict[str, dict[str, int]], raw_only: bool) -> None:
    cats = sorted(agg.keys(), key=lambda k: agg[k]["lines"], reverse=True)
    name_width = max(len(c) for c in cats) if cats else 30
    name_width = max(name_width, len("Category"))

    if raw_only:
        cols = ("files", "lines", "non_blank")
    else:
        cols = ("files", "lines", "non_blank", "code")

    header = f"  {'Category'.ljust(name_width)}  " + "  ".join(c.rjust(10) for c in cols)
    sep = "  " + "-" * name_width + "  " + "  ".join("-" * 10 for _ in cols)
    print()
    print(header)
    print(sep)
    totals = {c: 0 for c in cols}
    for cat in cats:
        row = agg[cat]
        cells = [str(row[c]).rjust(10) for c in cols]
        print(f"  {cat.ljust(name_width)}  " + "  ".join(cells))
        for c in cols:
            totals[c] += row[c]
    print(sep)
    print(
        f"  {'TOTAL'.ljust(name_width)}  "
        + "  ".join(str(totals[c]).rjust(10) for c in cols),
    )
    print()


def print_top_files(files: list[FileCount], top_n: int) -> None:
    sorted_files = sorted(files, key=lambda f: f.code, reverse=True)[:top_n]
    if not sorted_files:
        return
    print(f"  Top {len(sorted_files)} files by `code` line count:")
    name_width = max(len(str(f.rel)) for f in sorted_files)
    print()
    print(f"  {'File'.ljust(name_width)}  {'lines':>8}  {'code':>8}  category")
    print("  " + "-" * (name_width + 8 + 8 + 30))
    for fc in sorted_files:
        print(
            f"  {str(fc.rel).ljust(name_width)}  "
            f"{fc.lines:>8}  {fc.code:>8}  {fc.category}",
        )
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    # Force UTF-8 so em-dashes in category labels render on Windows cp1252 consoles.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Deterministic LOC counter for EPP_Verdict.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=0,
        help="Also list the N largest files by code line count.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Skip code/comment detection, only report files/lines/non_blank.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of a table.",
    )
    args = parser.parse_args()

    files: list[FileCount] = []
    for rel in iter_source_files(REPO_ROOT):
        ext = rel.suffix.lower()
        lang = LANG_BY_EXT.get(ext)
        if lang is None:
            # Special case for the included html file.
            lang = LangSpec("HTML", ("<!--",))
        lines, non_blank, code = count_file(REPO_ROOT / rel, lang)
        files.append(
            FileCount(
                rel=rel,
                category=categorize(rel, lang),
                lines=lines,
                non_blank=non_blank,
                code=code,
            ),
        )

    agg = aggregate(files)

    if args.json:
        out = {
            "totals": {
                "files": sum(b["files"] for b in agg.values()),
                "lines": sum(b["lines"] for b in agg.values()),
                "non_blank": sum(b["non_blank"] for b in agg.values()),
                "code": sum(b["code"] for b in agg.values()),
            },
            "by_category": {k: v for k, v in sorted(agg.items())},
            "files_counted": len(files),
        }
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    print(f"\n  EPP_Verdict — LOC report ({REPO_ROOT})")
    print(f"  {len(files)} files counted across {len(agg)} categories.")
    print_table(agg, raw_only=args.raw)

    if args.top > 0:
        print_top_files(files, args.top)

    print("  Method:")
    print("    - Walks REPO_ROOT, applies path/name/extension exclusions.")
    print("    - `lines`     = raw line count (newline-terminated, like `wc -l`).")
    print("    - `non_blank` = lines with non-whitespace content.")
    print("    - `code`      = non_blank minus single-line comment lines.")
    print("    - Block comments and inline comments are NOT stripped.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
