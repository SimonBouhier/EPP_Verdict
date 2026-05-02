#!/usr/bin/env python
"""
Insère un header `sys.path.insert(...)` au début de chaque tests/test_*.py
qui n'en a pas, pour permettre l'exécution directe `python tests/test_X.py`.

Pourquoi ce header est nécessaire :
- Quand on lance `python tests/test_X.py`, Python ajoute `tests/` à sys.path
  mais pas le repo root.
- Les imports `from services.X import Y` en haut du fichier échouent alors
  avec ModuleNotFoundError.
- Le footer ajouté par `add_runner_footer.py` ne suffit pas — il s'exécute
  APRÈS les imports du fichier, donc trop tard.
- pytest et le runner v1 (`tools/epp_test_runner.py`) gèrent ce cas via
  rootdir/conftest, mais l'exécution `python file.py` directe ne passe par
  aucun de ces mécanismes.

Le header est inséré juste après la docstring du module (si présente) pour
préserver `__doc__`. Détection idempotente via la signature `_epp_sys`.

Usage :
    python scripts/add_sys_path_header.py            # dry-run
    python scripts/add_sys_path_header.py --apply    # applique
    python scripts/add_sys_path_header.py --apply --verbose

Le script est conçu pour cohabiter avec `scripts/add_runner_footer.py` —
les deux ensemble rendent chaque tests/test_*.py exécutable directement.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import NamedTuple

# Force UTF-8 sur stdout/stderr (cp1252 Windows ne supporte pas les emojis).
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, ValueError, OSError):
    pass


# Signature unique de notre header — permet la détection d'idempotence.
HEADER_SIGNATURE = "_epp_sys.path.insert"

# Préfixe `_epp_` sur sys/pathlib pour éviter les conflits avec d'éventuels
# `import sys` ou `from pathlib import Path` plus loin dans le fichier — les
# imports Python ne sont pas idempotents au niveau de leur effet sur le
# binding local, mais nommer différemment évite toute confusion. Le `del`
# final nettoie pour ne pas polluer le namespace du module.
HEADER_BLOCK = (
    "# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).\n"
    "import sys as _epp_sys\n"
    "import pathlib as _epp_pathlib\n"
    "_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))\n"
    "del _epp_sys, _epp_pathlib\n"
    "\n"
)


# Patterns existants reconnus comme équivalents fonctionnels (le fichier a
# déjà un sys.path setup manuel) — on les détecte pour ne pas dupliquer.
_EXISTING_SYS_PATH_RE = re.compile(
    r"sys\.path\.insert\s*\(\s*0\s*,\s*str\s*\(\s*Path\s*\(\s*__file__\s*\)"
    r"(?:\s*\.\s*resolve\s*\(\s*\)\s*)?\.\s*parent\s*\.\s*parent",
)


class FileVerdict(NamedTuple):
    path: Path
    action: str  # "add" | "already_done"
    reason: str = ""


def classify(test_file: Path) -> FileVerdict:
    """Décide si le fichier a besoin d'un header sys.path."""
    try:
        content = test_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = test_file.read_text(encoding="latin-1")

    if HEADER_SIGNATURE in content:
        return FileVerdict(test_file, "already_done", "header _epp_sys déjà présent")

    if _EXISTING_SYS_PATH_RE.search(content):
        return FileVerdict(
            test_file,
            "already_done",
            "sys.path.insert manuel existant détecté (équivalent fonctionnel)",
        )

    return FileVerdict(test_file, "add", "")


def find_insertion_line(content: str) -> int:
    """Retourne l'index (0-based) de la ligne où insérer le header.

    Insère :
    - Après la docstring du module si présente.
    - **Et** après les éventuels `from __future__ import ...` qui doivent
      rester en tête de fichier (sinon SyntaxError).
    - En tout début sinon.

    Renvoie un index dans la liste produite par splitlines(keepends=True).
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return 0

    line = 0
    idx = 0

    # Skip docstring si présente.
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        line = tree.body[0].end_lineno or 0
        idx = 1

    # Skip les `from __future__ import ...` qui suivent la docstring.
    # Python exige qu'ils soient en tête de fichier — insérer notre header
    # avant l'un d'eux casse la compilation (SyntaxError).
    while idx < len(tree.body):
        node = tree.body[idx]
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            line = node.end_lineno or line
            idx += 1
        else:
            break

    return line


def prepend_header(test_file: Path) -> None:
    """Insère HEADER_BLOCK au bon endroit (après docstring + __future__)."""
    content = test_file.read_text(encoding="utf-8")
    insert_line = find_insertion_line(content)

    lines = content.splitlines(keepends=True)
    prefix_nl = ""
    if insert_line > 0 and not lines[insert_line - 1].endswith("\n"):
        prefix_nl = "\n"

    new_content = (
        "".join(lines[:insert_line])
        + prefix_nl
        + HEADER_BLOCK
        + "".join(lines[insert_line:])
    )
    test_file.write_text(new_content, encoding="utf-8", newline="\n")


# Pattern reconnaissant exactement le bloc HEADER_BLOCK injecté précédemment.
# Capture optionnellement le commentaire `# AUTO ...`, les 3 lignes de code,
# le `del`, et la ligne vide qui suit.
_HEADER_BLOCK_RE = re.compile(
    r"^# AUTO — permet `python tests/test_X\.py` direct \(cf\. tests/_runner\.py\)\.\n"
    r"import sys as _epp_sys\n"
    r"import pathlib as _epp_pathlib\n"
    r"_epp_sys\.path\.insert\(0, str\(_epp_pathlib\.Path\(__file__\)\.resolve\(\)\.parent\.parent\)\)\n"
    r"del _epp_sys, _epp_pathlib\n"
    r"\n?",  # ligne vide optionnelle qui suit
    re.MULTILINE,
)


def remove_existing_header(content: str) -> tuple[str, bool]:
    """Retire le bloc header s'il est présent. Retourne (nouveau, was_removed)."""
    if HEADER_SIGNATURE not in content:
        return content, False
    new_content, n_subs = _HEADER_BLOCK_RE.subn("", content, count=1)
    return new_content, n_subs > 0


def repair_header(test_file: Path) -> str:
    """Retire un éventuel header mal placé puis ré-insère au bon endroit.

    Returns:
        "no_header_inserted" : pas de header _epp_ ni de manuel → on insère.
        "already_correct" : compile OK, on laisse intact (idempotent).
        "repaired" : header _epp_ retiré + ré-inséré à la bonne position.
        "manual_existing" : pas de _epp_ mais un sys.path manuel équivalent
                            → ne rien faire (éviter la duplication).
        "epp_dedup" : _epp_ détecté ET sys.path manuel : on retire _epp_
                     pour ne garder que le manuel (cas duplication).
        "manual_review_needed" : header présent mais pattern atypique.
    """
    content = test_file.read_text(encoding="utf-8")
    has_epp = HEADER_SIGNATURE in content
    has_manual = bool(_EXISTING_SYS_PATH_RE.search(content))

    # Cas 1 : duplication détectée (notre header + manuel) → retirer le nôtre.
    if has_epp and has_manual:
        cleaned, removed = remove_existing_header(content)
        if removed:
            test_file.write_text(cleaned, encoding="utf-8", newline="\n")
            return "epp_dedup"
        return "manual_review_needed"

    # Cas 2 : pas de _epp_ mais manuel existant → ne rien faire.
    if not has_epp and has_manual:
        return "manual_existing"

    # Cas 3 : pas de header du tout → insérer.
    if not has_epp:
        prepend_header(test_file)
        return "no_header_inserted"

    # Cas 4 : _epp_ présent. Vérifier si le fichier compile RÉELLEMENT
    # (pas seulement ast.parse, qui ne détecte pas un `from __future__`
    # mal placé — c'est compile() qui applique cette règle).
    try:
        compile(content, str(test_file), "exec")
        return "already_correct"
    except SyntaxError:
        pass  # cas 5 : on va réparer

    cleaned, removed = remove_existing_header(content)
    if not removed:
        return "manual_review_needed"
    test_file.write_text(cleaned, encoding="utf-8", newline="\n")
    prepend_header(test_file)
    return "repaired"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Applique les modifications (par défaut : dry-run).",
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help=(
            "Mode réparation : pour chaque fichier où le header est présent "
            "mais provoque une SyntaxError (ex. inséré avant `from __future__"
            " import ...`), retire et ré-insère au bon endroit. Implique --apply."
        ),
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Détail par fichier."
    )
    parser.add_argument(
        "--tests-dir",
        default="tests",
        help="Répertoire des tests (default: tests).",
    )
    args = parser.parse_args()
    if args.repair:
        args.apply = True

    repo_root = Path(__file__).resolve().parent.parent
    tests_dir = (repo_root / args.tests_dir).resolve()
    if not tests_dir.is_dir():
        print(f"[add_sys_path_header] ERROR: tests dir not found: {tests_dir}")
        return 2

    test_files = sorted(tests_dir.glob("test_*.py"))
    verdicts: list[FileVerdict] = [classify(p) for p in test_files]

    by_action: dict[str, list[FileVerdict]] = {"add": [], "already_done": []}
    for v in verdicts:
        by_action[v.action].append(v)

    print(
        f"[add_sys_path_header] scanned: {len(verdicts)} test_*.py in {tests_dir}"
    )
    print(f"  add         : {len(by_action['add'])}")
    print(f"  already_done: {len(by_action['already_done'])}")

    if args.verbose:
        if by_action["already_done"]:
            print("\n[add_sys_path_header] already_done (idempotent skip):")
            for v in by_action["already_done"]:
                print(f"   - {v.path.relative_to(repo_root)}  ({v.reason})")
        if by_action["add"]:
            print("\n[add_sys_path_header] add (would inject header):")
            for v in by_action["add"]:
                print(f"   + {v.path.relative_to(repo_root)}")

    if not args.apply:
        print(
            "\n[add_sys_path_header] DRY RUN — no file modified. "
            "Re-run with --apply to inject."
        )
        return 0

    written = 0
    repaired = 0

    if args.repair:
        # Mode --repair : on parcourt TOUS les fichiers, pas seulement les
        # `add`. Pour chacun on décide : laisser, insérer, réparer, ou
        # retirer la duplication.
        outcomes: dict[str, int] = {
            "repaired": 0,
            "no_header_inserted": 0,
            "epp_dedup": 0,
            "manual_existing": 0,
            "already_correct": 0,
            "manual_review_needed": 0,
        }
        for v in verdicts:
            try:
                outcome = repair_header(v.path)
                outcomes[outcome] = outcomes.get(outcome, 0) + 1
                if outcome == "repaired":
                    print(f"   ↻ repaired : {v.path.relative_to(repo_root)}")
                elif outcome == "epp_dedup":
                    print(
                        f"   ✂  dedup    : {v.path.relative_to(repo_root)} "
                        f"(retire _epp_, garde sys.path manuel)"
                    )
                elif outcome == "no_header_inserted":
                    print(f"   + inserted : {v.path.relative_to(repo_root)}")
                elif outcome == "manual_review_needed":
                    print(
                        f"   ⚠️  manual review : {v.path.relative_to(repo_root)}"
                    )
            except Exception as e:
                print(f"[add_sys_path_header] FAILED on {v.path}: {e}")

        print("\n[add_sys_path_header] --repair summary:")
        for action, count in outcomes.items():
            print(f"  {action:25s}: {count}")
    else:
        for v in by_action["add"]:
            try:
                prepend_header(v.path)
                written += 1
            except Exception as e:
                print(f"[add_sys_path_header] FAILED on {v.path}: {e}")
        print(f"\n[add_sys_path_header] written: {written} (--apply mode)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
