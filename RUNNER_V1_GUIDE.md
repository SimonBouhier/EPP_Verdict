# EPP_Verdict Test Runner v1 — Guide d'utilisation

## Installation

Le runner est implémenté en `tools/epp_test_runner.py` — aucune dépendance externe supplémentaire (utilise pytest standard).

## Commandes CMD

### 1. Lancer tous les tests (baseline)
```bash
python tools/epp_test_runner.py -- tests/ -v
```
**Résultat attendu :**
- 698 passed, 14 skipped
- Artefacts dans `test_results/2026-04-07_14-30-45/`

### 2. Lancer un fichier ADR spécifique
```bash
python tools/epp_test_runner.py -- tests/test_adr010_consensus_meta.py -v
```

### 3. Lancer avec label (pour organisation)
```bash
python tools/epp_test_runner.py --label "audit-p0-fixes" -- tests/ -v
```
**Résultat :**
- Artefacts dans `test_results/2026-04-07_14-30-45_audit-p0-fixes/`

### 4. Lancer seulement les tests par phase
```bash
python tools/epp_test_runner.py -- tests/ -k "phase1" -v
```

### 5. Lancer seulement les tests non-skippés (excluant localnet + Solana mock)
```bash
python tools/epp_test_runner.py -- tests/ --ignore=tests/test_phase4_solana.py -v
```

### 6. Lancer une suite minimaliste (test RED-GREEN-FIX)
```bash
python tools/epp_test_runner.py --label "red-green-fix-created-at" -- tests/ -k "created_at" -v
```

---

## Arborescence de sortie

```
test_results/
│
└── 2026-04-07_14-30-45_audit-p0-fixes/     [run_dir]
    ├── console.txt                         [logs complets stdout/stderr]
    ├── summary.json                        [métriques JSON]
    ├── results.jsonl                       [1 JSON par test]
    ├── command.txt                         [commande exécutée]
    └── report.md                           [rapport lisible]
```

## Artefacts détaillés

### `summary.json`
Métriques globales du run :
- `run_id` : identifiant unique
- `collected_total` : nombre de tests collectés
- `selected_total` : nombre de tests exécutés
- `deselected_total` : nombre de tests exclus
- `test_outcomes` : compteurs {passed, failed, skipped, xfailed}
- `proof_usable` : boolean — run probant ou non
- `proof_notes` : array de warnings si non-probant

**Exemple :**
```json
{
  "run_id": "2026-04-07_14-30-45_audit-p0-fixes",
  "collected_total": 712,
  "selected_total": 698,
  "deselected_total": 14,
  "test_outcomes": {
    "passed": 698,
    "failed": 0,
    "skipped": 14
  },
  "proof_usable": true,
  "proof_notes": []
}
```

**Cas non-probant (0 selected) :**
```json
{
  "selected_total": 0,
  "proof_usable": false,
  "proof_notes": ["0 tests selected: run non-probant"]
}
```

### `results.jsonl`
1 ligne JSON par test, avec détails :
- `nodeid` : identifiant du test (ex: `tests/test_adr010_consensus_meta.py::TestClass::test_name`)
- `final_outcome` : `passed` | `failed` | `skipped` | `xfailed`
- `duration_total` : durée en secondes (float)
- `phase` : `phase1`, `phase2`, `phase3`, `phase4`, ou null (auto-détecté)
- `adr` : `adr010`, `adr011`, ..., ou null (auto-détecté)
- `phases` : dict avec setup/call/teardown phases
- `longrepr` : traceback complet si failed, null sinon

**Exemple ligne :**
```json
{"nodeid": "tests/test_adr010_consensus_meta.py::TestConsensusMetaSchema::test_schema_has_consensus_meta_column", "final_outcome": "passed", "duration_total": 0.045, "phase": null, "adr": "adr010"}
```

### `report.md`
Rapport lisible en Markdown :
1. **Summary** : métriques globales
2. **Command Executed** : la commande pytest exacte lancée
3. **Phase Breakdown** : tableau phase1/2/3/4 avec pass rates
4. **ADR Breakdown** : tableau adr010/011/012/014/016/018
5. **Failed Tests** : détail des tests échoués (s'il y en a)
6. **Skipped / XFailed Tests** : liste des tests ignorés
7. **Environment** : Python version, platform, etc.

**Exemple début :**
```markdown
# EPP_Verdict Test Report

**Run ID:** `2026-04-07_14-30-45_audit-p0-fixes`

✅ Run probant

## Summary
- **Collected:** 712 tests
- **Selected:** 698 tests
...

## Phase Breakdown

| Phase | Total | Passed | Failed | Skipped | Pass Rate |
|-------|-------|--------|--------|---------|-----------|
| phase1 | 42 | 40 | 0 | 2 | 95.2% |
| phase2 | 180 | 178 | 0 | 2 | 98.9% |
...
```

### `console.txt`
Logs bruts complets (stdout + stderr), identiques à ce qu'on verrait en console.

### `command.txt`
Métadonnées de la commande lancée (pour traçabilité).

---

## Auto-détection phase/adr

Le runner détecte automatiquement :

### Phase detection
- Pattern : `test_phase1_`, `test_phase2_`, `test_phase3_`, `test_phase03_`, `test_phase4_`, etc.
- Extraction : normalise vers `phase1`, `phase2`, `phase3`, `phase4`
- Fallback : `null` si le pattern ne correspond pas

Exemples :
- `tests/test_phase1_bridge.py` → phase = `phase1`
- `tests/test_phase03_attestation.py` → phase = `phase3` (ou `phase03` selon le pattern)
- `tests/test_adr010_consensus_meta.py` → phase = `null`

### ADR detection
- Pattern : `test_adr010_`, `test_adr011_`, ..., `test_adr018_`, etc.
- Extraction : `adr010`, `adr011`, ..., `adr018`
- Fallback : `null` si aucun ADR

Exemples :
- `tests/test_adr010_consensus_meta.py` → adr = `adr010`
- `tests/test_adr018_flywheel.py` → adr = `adr018`
- `tests/test_phase1_bridge.py` → adr = `null`

---

## Cas spéciaux

### Run non-probant (0 tests selected)
```bash
python tools/epp_test_runner.py -- tests/ -k "nonexistent_pattern"
```

**Résultat :**
- `summary.json` : `proof_usable = false`
- `proof_notes` = `["0 tests selected: run non-probant"]`
- `report.md` : affiche ⚠️ WARNING

**Code de sortie wrapper :** 10 (au lieu de 0 ou 1)

### Collection errors / Internal errors
Si pytest rencontre une erreur lors de la collection :
- `summary.json` : `collection_errors_count > 0`
- `proof_usable = false`
- `proof_notes` += `["collection errors detected"]`

---

## Parsing programmatique

Pour CI/CD ou analyse :

### Parse summary.json
```python
import json
with open("test_results/.../summary.json") as f:
    summary = json.load(f)
    print(f"Proof usable: {summary['proof_usable']}")
    print(f"Pass rate: {summary['test_outcomes']['passed'] / summary['selected_total']:.1%}")
```

### Parse results.jsonl
```python
with open("test_results/.../results.jsonl") as f:
    for line in f:
        test = json.loads(line)
        if test["adr"] == "adr010" and test["final_outcome"] == "passed":
            print(f"✅ {test['nodeid']}")
```

### Check if run probant
```python
if not summary["proof_usable"]:
    print("⚠️ Run non-probant:")
    for note in summary["proof_notes"]:
        print(f"  - {note}")
    exit(1)
```

---

## Workflow audit (exemple)

**Étape 1 : Baseline** (avant fixes)
```bash
python tools/epp_test_runner.py --label "before-p0-fixes" -- tests/ -v
# Génère test_results/2026-04-07_14-30-45_before-p0-fixes/report.md
```

**Étape 2 : Implémenter les 4 fixes P0**
- Fix 1 : `created_at` → `timestamp`
- Fix 2 : supprimer trigger `tr_event_insert_update_session`
- Fix 3 : supprimer triggers `tr_relation_insert_update_degree`
- Fix 4 : ajouter `PRAGMA foreign_keys=ON`

**Étape 3 : Après fixes** (avec tests RED minimalistes)
```bash
python tools/epp_test_runner.py --label "after-p0-fixes" -- tests/ -v
# Génère test_results/2026-04-07_14-32-00_after-p0-fixes/report.md
```

**Étape 4 : Comparaison**
- BEFORE : `proof_usable: true` mais 4 tests RED
- AFTER : `proof_usable: true` et 4 tests GREEN

---

## Notes importantes

1. **Zéro instrumentation intrusive** : le runner ne modifie pas `conftest.py`, n'injecte pas de fixtures, n'instrumentalise rien. Il observe passivement.

2. **Proof usability** : même si 698/698 tests passent, un run avec 0 selected est marqué non-probant. C'est intentionnel : impossible de conclure quoi que ce soit d'un run qui n'a rien testé.

3. **Phase/ADR auto-détection** : basée sur des patterns simples du `nodeid`. Fiable et transparent.

4. **Markdown report** : généré automatiquement, lisible par humains, utilisable pour documentation.

5. **JSON artifacts** : machine-readable, parseable par des scripts CI/parsing.

---

## Exemples de fichiers

Les exemples d'artefacts sont disponibles dans :
- `~/.claude/examples/summary.json`
- `~/.claude/examples/results.jsonl`
- `~/.claude/examples/report.md`
