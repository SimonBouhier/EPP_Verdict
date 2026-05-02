"""
Single-file test runner — helper unique pour `python tests/test_X.py`.

Pattern d'usage (footer ajouté à chaque test_*.py) :

    if __name__ == "__main__":
        import sys, pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
        from tests._runner import run_self
        raise SystemExit(run_self(__file__))

Comportement :

- Exécute `pytest <fichier> -v --tb=short --color=yes` en sous-processus.
- Affiche la sortie en temps réel sur stdout (tee).
- Sauvegarde la même sortie dans `test_results/individual/<basename>_<timestamp>.txt`.
- Préfixe et suffixe le fichier d'un en-tête/pied identifiant (run id, exit code, durée).
- Retourne le code de sortie pytest pour propagation `SystemExit`.

Pas de dépendance externe au-delà de la stdlib + pytest. Compatible Windows
(force UTF-8 sur stdout/stderr pour ne pas crasher sur les emojis pytest).

Pour le runner global multi-fichiers, voir `tools/epp_test_runner.py` qui
produit un dossier horodaté complet avec summary.json + report.md.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Force UTF-8 sur stdout/stderr pour que les emojis pytest (✅ ❌ ⏭️ etc.)
# ne crashent pas sous Windows cp1252. Best-effort.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, ValueError, OSError):
    pass


def run_self(test_file: str, *, extra_args: list[str] | None = None) -> int:
    """
    Lance pytest sur `test_file` avec verbose + tee console/fichier.

    Args:
        test_file: chemin absolu du fichier de test (passé via `__file__`).
        extra_args: arguments pytest additionnels optionnels (ex: ['-x', '-s']).

    Returns:
        exit code pytest (0 = green, non-zero = failures/errors).

    Side effects:
        - Crée `test_results/individual/` si absent.
        - Écrit `test_results/individual/<basename>_<timestamp>.txt`.
        - Affiche tout en console (stdout temps réel).
    """
    test_path = Path(test_file).resolve()
    repo_root = test_path.parent.parent  # tests/test_X.py → repo root
    individual_dir = repo_root / "test_results" / "individual"
    individual_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    basename = test_path.stem  # "test_lean_conformance" sans extension
    output_path = individual_dir / f"{basename}_{timestamp}.txt"

    started_at = datetime.now()
    started_iso = started_at.replace(microsecond=0).isoformat()
    cmd: list[str] = [
        sys.executable, "-m", "pytest",
        str(test_path), "-v", "--tb=short", "--color=yes",
    ]
    if extra_args:
        cmd.extend(extra_args)

    header = (
        f"{'=' * 72}\n"
        f"EPP_Verdict — Single-file test runner\n"
        f"  file       : {test_path}\n"
        f"  started_at : {started_iso}\n"
        f"  command    : {' '.join(cmd)}\n"
        f"  output     : {output_path}\n"
        f"{'=' * 72}\n"
    )
    sys.stdout.write(header)
    sys.stdout.flush()

    # --color=yes laisse passer les codes ANSI ; on les écrit tels quels dans
    # le fichier (lisible par `cat`/`type` dans tout terminal moderne).
    # Si l'utilisateur préfère un fichier sans codes ANSI, retirer --color=yes.
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")

    exit_code = 0
    with output_path.open("w", encoding="utf-8") as fh:
        fh.write(header)
        fh.flush()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(repo_root),
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            bufsize=1,
        )
        assert process.stdout is not None  # for type checkers
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            fh.write(line)
            fh.flush()
        process.wait()
        exit_code = process.returncode

    finished_at = datetime.now()
    duration_s = (finished_at - started_at).total_seconds()
    finished_iso = finished_at.replace(microsecond=0).isoformat()

    # pytest exit codes (cf. https://docs.pytest.org/en/stable/reference/exit-codes.html)
    # 0 = all passed
    # 1 = some tests failed
    # 2 = test execution interrupted by user
    # 3 = internal error
    # 4 = pytest cli usage error
    # 5 = no tests collected
    exit_meaning = {
        0: "all tests passed",
        1: "some tests failed",
        2: "interrupted by user",
        3: "pytest internal error",
        4: "pytest CLI usage error",
        5: "no tests collected",
    }.get(exit_code, f"unknown exit code {exit_code}")

    footer = (
        f"\n{'=' * 72}\n"
        f"  finished_at: {finished_iso}\n"
        f"  duration_s : {duration_s:.2f}\n"
        f"  exit_code  : {exit_code}  ({exit_meaning})\n"
        f"  saved_to   : {output_path}\n"
        f"{'=' * 72}\n"
    )
    sys.stdout.write(footer)
    sys.stdout.flush()
    with output_path.open("a", encoding="utf-8") as fh:
        fh.write(footer)

    return exit_code


__all__ = ["run_self"]
