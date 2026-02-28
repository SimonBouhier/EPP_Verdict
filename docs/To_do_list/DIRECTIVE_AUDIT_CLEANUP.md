# DIRECTIVE — Réorganisation Audit & Documentation

## CONTEXTE

L'audit unifié `epp_audit.py` remplace 3 anciens scripts.
Les tests Solana localnet sont validés (26/26).
Total projet : 723 tests, 21 mutations KILLED, 0 SURVIVED.

---

## PHASE 1 — Fichiers à supprimer (racine)

```bash
# Anciens scripts remplacés par epp_audit.py
rm audit_runner.py
rm audit.sh
rm find_orphans.sh

# Ancien rapport remplacé par EPP_AUDIT_REPORT.md
rm MUTATION_REPORT.md
```

**Vérification AVANT suppression :**
```bash
# Confirmer que epp_audit.py contient les 21 mutations
grep -c "Mutation(" epp_audit.py
# Attendu : 21

# Confirmer que les anciens scripts ne sont importés nulle part
grep -rl "audit_runner\|audit\.sh\|find_orphans" --include="*.py" --include="*.md" .
# Seuls résultats acceptables : CHANGELOG.md, ce fichier directive
```

---

## PHASE 2 — Déplacer les outputs vers tests/audits/

```bash
# Déplacer les fichiers auxiliaires
mv audit_checksums.txt tests/audits/audit_checksums.txt

# Le rapport généré doit aller dans tests/audits/
mv EPP_AUDIT_REPORT.md tests/audits/EPP_AUDIT_REPORT.md
```

**Modifier `epp_audit.py` — 2 chemins à mettre à jour :**

```python
# AVANT
REPORT_PATH = ROOT / "EPP_AUDIT_REPORT.md"
CHECKSUMS_PATH = ROOT / "audit_checksums.txt"

# APRÈS
REPORT_PATH = ROOT / "tests" / "audits" / "EPP_AUDIT_REPORT.md"
CHECKSUMS_PATH = ROOT / "tests" / "audits" / "audit_checksums.txt"
```

---

## PHASE 3 — Structure cible

```
EPP_Verdict/
├── epp_audit.py                    ← Script unifié (RESTE en racine)
├── pytest.ini
├── conftest.py
├── tests/
│   ├── audits/
│   │   ├── EPP_AUDIT_REPORT.md     ← Rapport généré (DÉPLACÉ)
│   │   ├── audit_checksums.txt     ← Checksums baseline (DÉPLACÉ)
│   │   └── ...                     ← Autres rapports historiques
│   ├── test_phase1_client.py
│   ├── test_phase1_integration.py
│   ├── test_claim_verify.py
│   └── ...
```

---

## PHASE 4 — Mettre à jour la documentation

### 4.1 — ARCHITECTURE.md

Ajouter dans la section appropriée :

```markdown
### Audit Tooling

- `epp_audit.py` — Unified audit script (4 phases)
  - Phase 1: Static analysis (C2-C8 controls)
  - Phase 2: Orphan detection
  - Phase 3: Full regression (pytest)
  - Phase 4: Mutation testing (21 mutations, 7 groups)
- Reports output to `tests/audits/`

Usage:
  python epp_audit.py                  # Full audit (~10 min)
  python epp_audit.py --no-mutations   # Phases 1-3 (~30 sec)
  python epp_audit.py --static         # Phase 1 only
  python epp_audit.py --mutations      # Phase 4 only
```

### 4.2 — CONTROLS.md

Vérifier que les contrôles C1-C9 sont documentés et à jour.
Ajouter si absent :

```markdown
### C8 — VERIFY Mode Test Coverage
- 7 test files covering VERIFY mode (claim_type, decidability, VERDICT_PENALTIES)
- 10 test files covering consensus_engine

### Solana Integration Tests
- 26 tests (11 unit, 6 mock, 9 localnet E2E)
- Requires: solana-test-validator running on localhost:8899
- Env vars: EPP_TEST_LOCALNET=1, EPP_TEST_INTEGRATION=1
```

### 4.3 — CHANGELOG.md

Ajouter entrée :

```markdown
## [Unreleased] — 2026-02-28

### Added
- `epp_audit.py` — Unified audit script replacing audit_runner.py, audit.sh, find_orphans.sh
  - 21 mutation targets (M1.1-M7.3) including 3 new calibration mutations
  - Static analysis: C2 singletons, C3 silent except, C4 schema drift,
    C5 config drift, C6 weak assertions, C8 VERIFY coverage
  - Orphan detection (pure Python, cross-platform)
  - Full regression with collection error resilience
- Solana localnet E2E tests validated (26/26 passed)

### Removed
- `audit_runner.py` — Replaced by epp_audit.py Phase 4
- `audit.sh` — Replaced by epp_audit.py Phase 1
- `find_orphans.sh` — Replaced by epp_audit.py Phase 2
- `MUTATION_REPORT.md` — Replaced by EPP_AUDIT_REPORT.md

### Fixed
- Orphan detector false positives on Windows/WSL (path separator bug)
- C4 schema drift false positives (French comments, SQL VIEWs)
- C5 config drift false positives (YAML section parents vs terminal keys)
- C8 VERIFY coverage grep failures on Windows paths
- pytest Phase 3 collection abort on missing hypothesis dependency
```

---

## PHASE 5 — Vérification finale

```bash
# 1. Le script tourne depuis la racine avec les nouveaux chemins
python epp_audit.py --static --orphans

# 2. Le rapport est généré dans tests/audits/
ls tests/audits/EPP_AUDIT_REPORT.md

# 3. Les anciens scripts n'existent plus
ls audit_runner.py audit.sh find_orphans.sh 2>&1 | grep "No such file"

# 4. Aucune référence cassée
grep -rn "audit_runner\|MUTATION_REPORT" --include="*.py" --include="*.md" . \
  | grep -v CHANGELOG | grep -v DIRECTIVE | grep -v __pycache__
# Attendu : 0 résultat

# 5. Full regression inchangée
python -m pytest tests/ --tb=short -q
# Attendu : 697+ passed
```

---

## NOTES POUR CLAUDE CODE

- NE PAS modifier epp_audit.py sauf les 2 chemins REPORT_PATH et CHECKSUMS_PATH
- NE PAS toucher aux 21 mutations (M1.1-M7.3) — elles sont validées
- NE PAS renommer epp_audit.py — le nom est déjà référencé dans les rapports
- Suivre RED-GREEN-FIX : si un test casse après déplacement, montrer le ROUGE
- Fournir `git diff` après modification de chaque fichier doc
