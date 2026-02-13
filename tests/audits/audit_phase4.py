"""
Audit Phase 4 — Script portable (Windows/Linux, Python uniquement)
Exécuter depuis la racine du projet EPP_Verdict :
    python audit_phase4.py
Génère audit_phase4_results.txt
"""
import os
import re
import subprocess
import sys
from pathlib import Path

OUTPUT_FILE = "audit_phase4_results.txt"
SCAN_DIRS = ["database", "services", "app", "cli"]
TEST_DIR = "tests"

def find_py_files(*dirs, exclude_test=True, exclude_pycache=True):
    """Trouve tous les .py dans les dossiers donnés."""
    files = []
    for d in dirs:
        p = Path(d)
        if not p.exists():
            continue
        for f in p.rglob("*.py"):
            s = str(f)
            if exclude_pycache and "__pycache__" in s:
                continue
            if exclude_test and ("test_" in f.name or s.startswith("tests")):
                continue
            files.append(f)
    return files

def search_in_files(files, pattern, context_after=0):
    """Cherche un pattern regex dans une liste de fichiers."""
    results = []
    rx = re.compile(pattern)
    for f in files:
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines):
            if rx.search(line):
                hit = f"{f}:{i+1}: {line.rstrip()}"
                ctx = []
                for j in range(1, context_after + 1):
                    if i + j < len(lines):
                        ctx.append(f"  +{j}: {lines[i+j].rstrip()}")
                results.append((hit, ctx))
    return results

def main():
    out_lines = []
    def emit(text=""):
        out_lines.append(text)
        print(text)

    emit("=" * 60)
    emit("AUDIT PHASE 4 — Résultats")
    emit("=" * 60)

    # --- BLOC 2 : SINGLETONS (C2) ---
    emit("\n=== 2. SINGLETONS (C2) — global _ dans code production ===")
    prod_files = find_py_files(*SCAN_DIRS, exclude_test=True)
    hits = search_in_files(prod_files, r"^\s*global\s+_")
    if hits:
        for h, _ in hits:
            emit(h)
    else:
        emit("(aucun trouvé)")
    emit(f"Total : {len(hits)}")

    # --- BLOC 3 : EXCEPT SILENCIEUX (C3) ---
    emit("\n=== 3. EXCEPT SILENCIEUX (C3) — except ... pass sans log/raise/AUDIT ===")
    silent_count = 0
    for f in prod_files:
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not re.match(r"except\b", stripped):
                continue
            # Regarde les 3 lignes suivantes pour trouver un "pass" nu
            block = []
            for j in range(1, 4):
                if i + j < len(lines):
                    block.append(lines[i + j].strip())
            for b_line in block:
                if b_line == "pass":
                    # Vérifier s'il y a logger/raise/AUDIT/# OK dans le bloc
                    context = " ".join(block) + " " + stripped
                    if any(kw in context for kw in ["logger.", "logging.", "raise", "AUDIT", "# OK"]):
                        break
                    emit(f"{f}:{i+1}: {stripped}")
                    for j2, b in enumerate(block):
                        emit(f"  +{j2+1}: {b}")
                    silent_count += 1
                    break
    if silent_count == 0:
        emit("(aucun trouvé)")
    emit(f"Total : {silent_count}")

    # --- BLOC 4 : ASSERTIONS FAIBLES (C6) ---
    emit("\n=== 4. ASSERTIONS FAIBLES (C6) — assert is not None / assert True ===")
    test_files = find_py_files(TEST_DIR, exclude_test=False, exclude_pycache=True)
    weak_patterns = [
        r"assert\s+\w+\s+is\s+not\s+None\s*$",
        r"assert\s+True\s*$",
        r"assert\s+\w+\s+is\s+True\s*$",
    ]
    weak_count = 0
    for pat in weak_patterns:
        hits = search_in_files(test_files, pat)
        for h, _ in hits:
            emit(h)
            weak_count += 1
    if weak_count == 0:
        emit("(aucune trouvée)")
    emit(f"Total : {weak_count}")

    # --- BLOC 5 : GIT STATUS ---
    emit("\n=== 5. GIT STATUS ===")
    try:
        r = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=10)
        output = r.stdout.strip()
        emit(output if output else "(working tree clean)")
    except Exception as e:
        emit(f"(erreur git : {e})")

    # --- BLOC 6 : GIT DIFF STAT ---
    emit("\n=== 6. GIT DIFF STAT ===")
    try:
        r = subprocess.run(["git", "diff", "--stat"], capture_output=True, text=True, timeout=10)
        output = r.stdout.strip()
        emit(output if output else "(aucun diff non stagé)")
    except Exception as e:
        emit(f"(erreur git : {e})")

    # --- GIT DIFF STAGED ---
    emit("\n=== 6b. GIT DIFF STAGED STAT ===")
    try:
        r = subprocess.run(["git", "diff", "--cached", "--stat"], capture_output=True, text=True, timeout=10)
        output = r.stdout.strip()
        emit(output if output else "(aucun diff stagé)")
    except Exception as e:
        emit(f"(erreur git : {e})")

    emit("\n" + "=" * 60)
    emit("FIN AUDIT")
    emit("=" * 60)

    # Écrire le fichier
    Path(OUTPUT_FILE).write_text("\n".join(out_lines), encoding="utf-8")
    print(f"\n>>> Résultats sauvegardés dans {OUTPUT_FILE}")

if __name__ == "__main__":
    main()