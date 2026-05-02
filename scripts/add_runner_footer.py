#!/usr/bin/env python
"""
Injecte un footer `if __name__ == "__main__":` dans chaque tests/test_*.py
qui n'en a pas, pour permettre l'exécution directe `python tests/test_X.py`.

Le footer délègue à `tests/_runner.py::run_self` qui :
  - Lance pytest sur le fichier en sous-processus avec verbose.
  - Affiche la sortie en temps réel (tee console).
  - Sauvegarde un fichier horodaté dans `test_results/individual/`.

Idempotence : le script détecte un footer existant via la signature unique
`from tests._runner import run_self` et skip le fichier dans ce cas.

Skip custom : si un fichier a déjà un `if __name__ == "__main__":` non-runner,
on le préserve et log un warning. L'utilisateur décidera s'il veut le
remplacer manuellement.

Usage :
    python scripts/add_runner_footer.py            # dry-run par défaut
    python scripts/add_runner_footer.py --apply    # applique les changements
    python scripts/add_runner_footer.py --apply --verbose

Sortie typique :
    [add_runner_footer] scanned: 85
      added       : 82
      already_done: 1   (footer runner déjà présent)
      custom_main : 2   (warning : __main__ custom non-runner détecté)
      written: 82 (--apply mode)

Le script ne modifie pas les fichiers en dry-run (par défaut).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

# Regex pour `if __name__ == "__main__":` en **début de ligne** (pas dans une
# docstring, pas indenté, pas commenté). On accepte simple ou double quote.
# Évite le faux positif sur les fichiers qui mentionnent le pattern dans une
# docstring — par ex. tests/test_asyncio_run_migration_s9_001.py l'évoque
# textuellement comme contre-exemple à un linter.
_MAIN_GUARD_RE = re.compile(
    r'^if\s+__name__\s*==\s*[\'"]__main__[\'"]\s*:\s*$',
    re.MULTILINE,
)

# Force UTF-8 sur stdout/stderr (cp1252 Windows ne supporte pas les emojis).
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, ValueError, OSError):
    pass


# Marqueur unique de notre footer — utilisé pour la détection d'idempotence.
FOOTER_SIGNATURE = "from tests._runner import run_self"

FOOTER_BLOCK = """

# ─────────────────────────────────────────────────────────────────────────
# Single-file runner — `python tests/<this_file>.py`
# Génère un rapport horodaté dans `test_results/individual/`.
# Cf. `tests/_runner.py::run_self` pour le détail.
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from tests._runner import run_self
    raise SystemExit(run_self(__file__))
"""


class FileVerdict(NamedTuple):
    path: Path
    action: str  # "add" | "already_done" | "custom_main"
    reason: str = ""


def classify(test_file: Path) -> FileVerdict:
    """Décide quoi faire pour un fichier de test donné."""
    try:
        content = test_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Fallback : try latin-1 then mark as add (rare)
        content = test_file.read_text(encoding="latin-1")

    if FOOTER_SIGNATURE in content:
        return FileVerdict(test_file, "already_done", "footer runner déjà injecté")

    if _MAIN_GUARD_RE.search(content):
        return FileVerdict(
            test_file,
            "custom_main",
            "__main__ custom déjà présent (non-runner) — remplacement manuel requis",
        )

    return FileVerdict(test_file, "add", "")


def append_footer(test_file: Path) -> None:
    """Ajoute le footer à la fin du fichier en mode append UTF-8."""
    # Lit pour s'assurer qu'on termine bien par une newline avant d'ajouter.
    content = test_file.read_text(encoding="utf-8")
    needs_nl_before = not content.endswith("\n")
    with test_file.open("a", encoding="utf-8", newline="\n") as fh:
        if needs_nl_before:
            fh.write("\n")
        fh.write(FOOTER_BLOCK)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Applique les modifications (par défaut : dry-run, ne touche aucun fichier).",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Affiche le détail par fichier."
    )
    parser.add_argument(
        "--tests-dir",
        default="tests",
        help="Répertoire des tests (default: tests).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    tests_dir = (repo_root / args.tests_dir).resolve()
    if not tests_dir.is_dir():
        print(f"[add_runner_footer] ERROR: tests dir not found: {tests_dir}")
        return 2

    test_files = sorted(tests_dir.glob("test_*.py"))
    verdicts: list[FileVerdict] = [classify(p) for p in test_files]

    by_action: dict[str, list[FileVerdict]] = {"add": [], "already_done": [], "custom_main": []}
    for v in verdicts:
        by_action[v.action].append(v)

    print(f"[add_runner_footer] scanned: {len(verdicts)} test_*.py in {tests_dir}")
    print(f"  add         : {len(by_action['add'])}")
    print(f"  already_done: {len(by_action['already_done'])}")
    print(f"  custom_main : {len(by_action['custom_main'])}")

    if args.verbose or by_action["custom_main"]:
        if by_action["custom_main"]:
            print("\n[add_runner_footer] ⚠️  custom_main (skip — manual review needed):")
            for v in by_action["custom_main"]:
                print(f"   - {v.path.relative_to(repo_root)}")

    if args.verbose:
        if by_action["already_done"]:
            print("\n[add_runner_footer] already_done (idempotent skip):")
            for v in by_action["already_done"]:
                print(f"   - {v.path.relative_to(repo_root)}")
        if by_action["add"]:
            print("\n[add_runner_footer] add (would inject footer):")
            for v in by_action["add"]:
                print(f"   + {v.path.relative_to(repo_root)}")

    if not args.apply:
        print(
            "\n[add_runner_footer] DRY RUN — no file modified. "
            "Re-run with --apply to inject."
        )
        return 0

    written = 0
    for v in by_action["add"]:
        try:
            append_footer(v.path)
            written += 1
        except Exception as e:
            print(f"[add_runner_footer] FAILED on {v.path}: {e}")
    print(f"\n[add_runner_footer] written: {written} (--apply mode)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
