# PHASE 3 — CORRECTIONS POST-AUDIT

> **Instructions pour Claude Code.** Lis CLAUDE.md ET ce fichier.
> Ce document corrige 54 failures identifiées par l'audit post-Phase 3.
> Exécute dans l'ordre strict. Chaque bloc se termine par une vérification.
>
> **État actuel** : 435 collected, 368 passed, 53 failed, 9 skipped, 5 errors
> **État cible** : 435 collected, ~425 passed, ≤5 failed, 9 skipped, 0 errors

---

## PRINCIPE — NE CASSER AUCUN DES 368 TESTS QUI PASSENT

Après chaque bloc de corrections, exécuter :

```bash
pytest tests/ -v --tb=short 2>&1 | tail -30
```

Si un test qui passait avant échoue maintenant → **annuler et comprendre pourquoi.**

---

## BLOC A — pytest-asyncio (résout ~32 failures + 4 errors)

### Diagnostic

Les fichiers `test_providers.py` (17 failures), `test_rotator.py` (15 failures) et
`test_graph_delta.py` (4 errors) échouent parce que :

1. `@pytest.mark.asyncio` n'est pas reconnu (pytest-asyncio n'est pas chargé)
2. Les tests async ne sont jamais exécutés — ils échouent immédiatement
3. `test_graph_delta.py` utilise `@pytest.yield_fixture` (déprécié)

### Étape A.1 — Installer pytest-asyncio

⚡ **VÉRIFIE D'ABORD** : `pip show pytest-asyncio 2>/dev/null`

Si absent :

```bash
pip install pytest-asyncio
```

### Étape A.2 — Configurer pytest pour asyncio

⚡ **VÉRIFIE D'ABORD** : `cat pytest.ini 2>/dev/null || cat pyproject.toml 2>/dev/null | grep asyncio`

Créer ou modifier `pytest.ini` (ou la section `[tool.pytest.ini_options]` de `pyproject.toml`) :

```ini
[pytest]
asyncio_mode = auto
```

Le mode `auto` fait que tout test `async def` est automatiquement traité comme asyncio,
sans besoin de `@pytest.mark.asyncio`. Ceci résout les 32 failures dans test_providers et
test_rotator sans modifier aucun fichier de test.

### Étape A.3 — Corriger test_graph_delta.py

⚡ **VÉRIFIE D'ABORD** : `grep -n "yield_fixture\|pytest.yield_fixture" tests/test_graph_delta.py`

Remplacer chaque occurrence de `@pytest.yield_fixture` par `@pytest.fixture`.
C'est un rename 1:1, le comportement est identique.

### Vérification bloc A

```bash
pytest tests/test_providers.py tests/test_rotator.py tests/test_graph_delta.py -v --tb=short 2>&1 | tail -30
```

**Cible** : les 17 + 15 + 4 + 4 failures/errors deviennent des PASSED.
Certains tests OllamaProvider pourraient encore échouer si les mocks async sont mal configurés
(les mocks ont été écrits pour un runtime sync). Si c'est le cas, ne force pas — on les
traite au bloc D.

---

## BLOC B — Anciens tiers low/medium/high (résout 10 failures)

### Diagnostic

Les fichiers `test_phase03_attestation.py`, `test_phase03_revalidation.py` et
`test_phase03_integration.py` contiennent des assertions de l'ancienne nomenclature
(Phase 0.3) qui n'a pas été mise à jour quand Phase 2 a changé les tiers.

Les assertions échouent ainsi :

```
AssertionError: assert "sandbox" == "low"
AssertionError: assert "proposition" == "medium"
AssertionError: assert "validated" == "high"
```

### Étape B.1 — test_phase03_attestation.py

⚡ **VÉRIFIE D'ABORD** : `grep -n '"low"\|"medium"\|"high"' tests/test_phase03_attestation.py`

Remplacer les assertions de tier dans `TestDeriveConfidenceTier` :

| Ancien | Nouveau |
|--------|---------|
| `== "low"` | `== "sandbox"` |
| `== "medium"` | `== "proposition"` |
| `== "high"` | `== "validated"` |
| `== "verified"` | `== "verified"` (inchangé) |

⚠️ **ATTENTION** : La logique de `derive_confidence_tier` a changé en Phase 2.
Elle prend maintenant `models_consulted`, `architecture_families`, etc.
Les tests Phase 0.3 appellent probablement `derive_confidence_tier(0.3)` sans ces params.

Vérifie les appels existants. Si un test fait :

```python
assert derive_confidence_tier(0.5) == "medium"
```

Il faut le changer en :

```python
assert derive_confidence_tier(0.5, models_consulted=2) == "proposition"
```

Car avec la nouvelle logique, `derive_confidence_tier(0.5)` retourne `"sandbox"` (1 seul modèle
par défaut = toujours sandbox). Chaque tier a des conditions additionnelles maintenant.

Voici la correspondance pour les 4 tests de `TestDeriveConfidenceTier` :

```python
def test_low(self):
    # Ancien : derive_confidence_tier(0.2) == "low"
    # Nouveau : score < 0.40, peu importe les modèles = sandbox
    assert derive_confidence_tier(0.2) == "sandbox"

def test_medium(self):
    # Ancien : derive_confidence_tier(0.5) == "medium"
    # Nouveau : score >= 0.40 + >= 2 modèles = proposition
    assert derive_confidence_tier(0.5, models_consulted=2) == "proposition"

def test_high(self):
    # Ancien : derive_confidence_tier(0.8) == "high"
    # Nouveau : score >= 0.70 + >= 3 modèles + >= 2 familles = validated
    assert derive_confidence_tier(0.8, models_consulted=3, architecture_families=2) == "validated"

def test_verified(self):
    # Ancien : derive_confidence_tier(0.95) == "verified"
    # Nouveau : score >= 0.85 + conditions validated + source_anchor OU validation >= 3
    assert derive_confidence_tier(
        0.95, models_consulted=3, architecture_families=2, source_anchor="test"
    ) == "verified"
```

### Étape B.2 — test_phase03_integration.py::test_all_confidence_tiers

⚡ **VÉRIFIE D'ABORD** : `grep -n '"low"\|"medium"\|"high"' tests/test_phase03_integration.py`

Même logique. Ce test crée probablement des attestations avec `crystallize()` et vérifie
les tiers. Adapter :
- Les assertions de tier ("low" → "sandbox", etc.)
- Les arguments de `crystallize()` pour qu'ils produisent les tiers attendus
  (ajouter `architecture_families=2` pour obtenir "validated", etc.)

### Étape B.3 — test_phase03_revalidation.py

⚡ **VÉRIFIE D'ABORD** : `grep -n '"low"\|"medium"\|"high"' tests/test_phase03_revalidation.py`

4 tests échouent. Les corrections suivent le même pattern :

- `test_divergence_detection` — vérifie que deux attestations de tiers différents sont
  considérées divergentes. Remplacer les anciens noms de tiers.
- `test_stable_claim_detection` — compara deux runs avec même tier. Mettre "sandbox"
  ou "proposition" au lieu de "low" ou "medium".
- `test_improved_claim_detection` — tier monte. Ex: "sandbox" → "proposition".
- `test_degraded_claim_detection` — tier descend. Ex: "proposition" → "sandbox".

### Étape B.4 — test_phase03_storage.py::test_store_and_retrieve

⚡ **VÉRIFIE D'ABORD** : `grep -n '"low"\|"medium"\|"high"' tests/test_phase03_storage.py`

1 failure. Probablement une attestation créée avec `confidence_tier="medium"` puis le
validator Pydantic la transforme en "proposition" via LEGACY_TIER_MAP, mais l'assertion
vérifie "medium". Remplacer par le nouveau tier correspondant.

### Étape B.5 — test_phase03_attestation.py::test_crystallize_produces_attestation

Ce test appelle `crystallize()` et vérifie le tier résultant. Adapter les assertions
ET les arguments (ajouter `models_consulted`, `architecture_families` si nécessaire
pour obtenir le tier attendu).

### Vérification bloc B

```bash
pytest tests/test_phase03_attestation.py tests/test_phase03_revalidation.py tests/test_phase03_integration.py tests/test_phase03_storage.py -v --tb=short 2>&1 | tail -20
```

**Cible** : 10 failures deviennent PASSED.

---

## BLOC C — Async sans event loop (résout ~9 failures)

### Diagnostic

`test_esmm_phase1.py` (7 failures) et `test_phase1_client.py` (2 failures) utilisent
`asyncio.run()` ou appellent des méthodes async sans event loop.

### Étape C.1 — test_esmm_phase1.py

⚡ **VÉRIFIE D'ABORD** : `grep -n "asyncio.run\|async def\|await " tests/test_esmm_phase1.py | head -20`

Deux cas possibles :

**Cas 1 — les tests sont `def test_xxx()` qui appellent `asyncio.run()`** :

Si le bloc A a installé pytest-asyncio avec `asyncio_mode = auto`, il suffit de :
- Remplacer `def test_xxx(self):` par `async def test_xxx(self):`
- Remplacer `result = asyncio.run(some_async())` par `result = await some_async()`
- Supprimer `import asyncio` si plus utilisé

**Cas 2 — les tests appellent des coroutines sans await** :

Ajouter `await` devant les appels async et rendre le test `async def`.

Pour chaque test en failure :
```
test_populate_from_file_empty_db     → probablement appelle db.initialize() sans await
test_get_population_stats            → idem
test_find_similar_concepts_no_embedding → idem
test_get_generation_stats            → idem
test_inject_seed_unknown_type        → idem
test_inject_seed_minimal             → idem
test_get_seed_status                 → idem
```

### Étape C.2 — test_phase1_client.py (2 failures)

⚡ **VÉRIFIE D'ABORD** : `grep -n "asyncio\|async def\|await" tests/test_phase1_client.py | head -20`

```
test_mock_submit_returns_signature   → probablement asyncio.run() mal configuré
test_mock_query_returns_empty        → idem
```

Même correction : `async def` + `await` au lieu de `asyncio.run()`.

### Étape C.3 — test_phase03_storage.py (1 failure restante si pas résolu en B)

⚡ **VÉRIFIE D'ABORD** : si ce test échoue encore après le bloc B, vérifier si c'est un
problème de event loop (nested `asyncio.run()`).

### Vérification bloc C

```bash
pytest tests/test_esmm_phase1.py tests/test_phase1_client.py -v --tb=short 2>&1 | tail -20
```

**Cible** : 9 failures deviennent PASSED.

---

## BLOC D — Failure Phase 3 : question_seeder (résout 1 failure)

### Diagnostic

```
FAILED tests/test_phase3_question_seeder.py::TestSeedGraphFromQuestion::test_seed_graph_on_empty
```

Le test appelle `seed_graph_from_question(db, question)` qui appelle en interne
`db.add_concept(concept_id=concept, source="question_seed")`.

La Phase 0.2 a ajouté un paramètre `embedding_model` obligatoire si un embedding est fourni,
et potentiellement `first_seen_model` comme paramètre. Vérifie la signature exacte.

### Étape D.1

⚡ **VÉRIFIE D'ABORD** : `grep -n "def add_concept" database/engine.py`

Lis la signature complète de `add_concept()`. Identifie les paramètres obligatoires.

### Étape D.2 — Adapter question_seeder.py

Dans `seed_graph_from_question()`, l'appel `db.add_concept()` doit passer tous les
paramètres requis. Exemple si `first_seen_model` est requis :

```python
await db.add_concept(
    concept_id=concept,
    source="question_seed",
    first_seen_model="question_seeder",
)
```

Ou si la signature est positionnelle :

```python
await db.add_concept(concept, source="question_seed")
```

Adapte au réel — ne suppose pas.

### Vérification bloc D

```bash
pytest tests/test_phase3_question_seeder.py -v --tb=short
```

**Cible** : 7/7 PASSED (le test `test_seed_graph_on_empty` passe).

---

## BLOC E — Amélioration post_crystallization.py (non-bloquant)

### Diagnostic

`post_crystallization.py` ne passe pas `run_id` à `log_tier_transition()`.
Ce n'est pas un bug (le paramètre est optionnel) mais une perte de traçabilité.

### Étape E.1

⚡ **VÉRIFIE D'ABORD** : `grep -n "log_tier_transition" services/esmm/post_crystallization.py`

Ajouter `run_id=attestation.run_id` :

```python
await db.log_tier_transition(
    claim_hash=attestation.claim_hash,
    old_tier=from_tier,
    new_tier=to_tier,
    reason=f"crystallization (consensus={attestation.consensus_score:.3f})",
    run_id=attestation.run_id,
)
```

### Étape E.2

⚡ **VÉRIFIE D'ABORD** que les tests existants passent encore :

```bash
pytest tests/test_phase3_post_crystallization.py -v --tb=short
```

---

## BLOC F — Vérification record_model_prediction signature

### Diagnostic

`post_crystallization.py` appelle `record_model_prediction()` avec `predicted_agreed=vote.agreed`.
Vérifie que le paramètre s'appelle bien `predicted_agreed` dans engine.py, pas `agreed`.

### Étape F.1

⚡ **VÉRIFIE D'ABORD** : `grep -n "def record_model_prediction" database/engine.py`

Lis la signature. Compare avec l'appel dans `post_crystallization.py`.

Si le paramètre s'appelle `agreed` dans engine.py mais `predicted_agreed` dans l'appel
(ou inversement), corrige l'un des deux pour cohérence.

⚠️ **Ne change la signature de engine.py que si aucun autre code ne l'appelle.**
Préfère modifier post_crystallization.py pour s'aligner sur engine.py.

### Vérification bloc F

```bash
pytest tests/test_phase3_post_crystallization.py tests/test_phase3_pipeline.py -v --tb=short
```

---

## VALIDATION FINALE

```bash
pytest tests/ -v --tb=short 2>&1 | tail -30
```

### État attendu

| Métrique | Avant corrections | Après corrections |
|----------|-------------------|-------------------|
| **PASSED** | 368 | ~425 |
| **FAILED** | 53 | ≤5 |
| **SKIPPED** | 9 | 9 |
| **ERROR** | 5 | 0 |

Les ≤5 failures résiduelles seraient des tests qui nécessitent une refonte plus profonde
(ex: mocks OllamaProvider complexes qui ne fonctionnent pas avec pytest-asyncio auto mode).
Si c'est le cas, les marquer `@pytest.mark.skip(reason="TODO: refactor async mocks")` avec
un commentaire explicatif, ne pas les supprimer.

### CHANGELOG.md

Ajouter une entrée factuelle :

```markdown
## [2026-02-XX] Phase 3.1 — Corrections post-audit

- Installé pytest-asyncio, configuré asyncio_mode=auto (résout 32 failures async)
- Corrigé test_graph_delta.py: yield_fixture → fixture (résout 4 errors)
- Migré 10 tests Phase 0.3 vers nouveaux tiers (sandbox/proposition/validated/verified)
- Corrigé test_esmm_phase1.py + test_phase1_client.py: async/await (résout 9 failures)
- Corrigé question_seeder.py: signature add_concept() (résout 1 failure Phase 3)
- Ajouté run_id dans post_crystallization hook (traçabilité)
- Tests: ~425 pass, ≤5 fail, 9 skipped, 0 errors (avant: 368 pass, 53 fail, 5 errors)
```

---

## RÉSUMÉ DES BLOCS

| Bloc | Quoi | Failures résolues | Difficulté |
|------|------|-------------------|------------|
| **A** | pytest-asyncio + yield_fixture | ~36 | Facile |
| **B** | Tiers low/medium/high → sandbox/proposition/validated | 10 | Moyenne |
| **C** | Async sans event loop | ~9 | Moyenne |
| **D** | question_seeder add_concept | 1 | Facile |
| **E** | run_id dans post_crystallization | 0 (amélioration) | Trivial |
| **F** | Vérification signature record_model_prediction | 0 (prévention) | Trivial |

**Ordre d'exécution** : A → B → C → D → E → F → Validation finale.

---

*Corrections post-audit Phase 3 — 10 février 2026*
*Base : 435 tests collectés, 368 PASSED, 53 FAILED, 5 ERRORS*
*Cible : ~425 PASSED, ≤5 FAILED, 0 ERRORS*
