# PLAN TACTIQUE — Robustesse Consensus (Phase 2.1/2.2 du MVP)

> **Correspondance** : EPP_PLAN_MVP.md §2.1 + §2.2
> **Prérequis** : Phase 4.7 complète. Baseline 487 passed, 0 failed, 11 skipped.
> **Objectif** : Transformer le consensus égalitaire en consensus pondéré,
>   mesurable et résistant au Sybil.
> **Protocole** : RED-GREEN-FIX obligatoire. ADR consultés avant chaque sous-phase.
> **Corrections** : Diagnostic Opus 15/02 intégré (D1-D6, 10 corrections).

---

## ARCHITECTURE DU PLAN

```
R-2.1.1  Pondération dynamique (Brier → votes)
R-2.1.2  Dashboard performance modèles
R-2.2.1  Diversité architecturale dans le consensus
R-2.2.2  Clustering embeddings (détection réponses quasi-identiques)
R-2.2.3  Commit-reveal complet avec stockage DB
```

Ordre d'exécution strict. Chaque sous-phase dépend de la précédente.
R-2.2.3 (commit-reveal) est le premier à sauter si le temps manque.

---

## R-2.1.1 — PONDÉRATION DYNAMIQUE DES VOTES (Brier → Consensus)

> **But** : Les votes des modèles avec un bon track record pèsent plus lourd.
> **ADR à lire** : ADR-005 (tiers multi-critères), ADR-003 (pipeline unique).
> **Infrastructure existante** :
> - `ModelVote.weight` (default 1.0) — le champ d'injection existe déjà
> - `get_model_brier_score()` — retourne `total_resolved` et `avg_brier_score`
> - `post_crystallization_hook()` — enregistre les votes dans model_track_record
> - `ConsensusEngine.compute_consensus()` — traite tous les modèles à poids égal

### Principe de pondération

```
weight(model) = 1.0                      si 0 prédictions résolues (cold start)
weight(model) = 1.0 - avg_brier_score    si prédictions résolues > 0
```

Un Brier de 0.0 (parfait) → poids 1.0. Un Brier de 0.5 (hasard) → poids 0.5.
Un Brier de 1.0 (toujours faux) → poids 0.0.
Un modèle sans historique → poids neutre 1.0 (décision humain 15/02).

### Chaîne d'appel réelle (diagnostic D2 — corrigé)

Le pipeline ne touche pas directement le consensus. La chaîne passe par
l'orchestrateur et le cycle_manager :

```
pipeline.run_pipeline()                              [pipeline.py:73]
  → _extract_triplets_from_question()                [pipeline.py:235]
    → ESMMOrchestrator(db, config, providers)         [pipeline.py:267]
      → orchestrator.execute_cycles()                [orchestrator.py:315]
        → cycle_manager.execute_cycle()              [cycle_manager.py:174]
          → _extract_triplets_from_responses()       [cycle_manager.py:683]
            → triplet_extractor.extract_from_text()  [triplet_extractor.py:253]
              → consensus_engine.compute_consensus() [consensus_engine.py:94]
```

**Option retenue : propagation par paramètre (Option A).**
Le ConsensusEngine est un singleton partagé via `get_triplet_extractor()` —
un setter mutable (Option B) causerait des race conditions entre runs concurrents.
Option A modifie 7 signatures mais garantit l'isolation par run.

### Modifications — 7 signatures (C1 obligatoire sur chacune)

**A. `consensus_engine.py:94` — Ajouter paramètre `model_weights`**

`compute_consensus()` accepte un nouveau paramètre optionnel
`model_weights: dict[str, float] | None = None`.

Si fourni, le poids de chaque modèle remplace le comptage unitaire :
- Actuellement : `agreement_ratio = count / total_models`
- Pondéré : `weighted_agreement = sum(weights[m] for m in contributing_models) / sum(all_weights)`

La `avg_confidence` est pondérée de la même manière.

Si `model_weights` est None → comportement actuel inchangé (backward compat).

**B. `triplet_extractor.py:253` — Relayer `model_weights`**

`extract_from_text()` accepte un paramètre optionnel `model_weights`
et le passe à `consensus_engine.compute_consensus()`.

**C. `cycle_manager.py:683` — Relayer dans `_extract_triplets_from_responses()`**

Accepte `model_weights` optionnel, le passe à `extract_from_text()`.

**D. `cycle_manager.py:174` — Relayer dans `execute_cycle()`**

Accepte `model_weights` optionnel, le passe à `_extract_triplets_from_responses()`.

**E. `orchestrator.py:315` — Calculer et passer dans `execute_cycles()`**

L'orchestrateur a accès à `self.db`. Il calcule les poids Brier
au début du run (une fois) et les passe à chaque cycle :

```python
model_weights = {}
for model_id in configured_models:
    brier = await self.db.get_model_brier_score(model_id)
    if brier and brier["total_resolved"] > 0:
        model_weights[model_id] = max(0.0, 1.0 - brier["avg_brier_score"])
    else:
        model_weights[model_id] = 1.0  # Cold start: poids neutre
```

**F. `pipeline.py:235` — Relayer dans `_extract_triplets_from_question()`**

Accepte `model_weights` optionnel, le passe à l'orchestrateur.

**G. `pipeline.py:73` — Relayer dans `run_pipeline()`**

Accepte `model_weights` optionnel. Si non fourni, les poids sont
calculés par l'orchestrateur (point E).

**H. `ModelVote.weight` — Remplir dans le pipeline post-consensus**

Le champ `ModelVote.weight` (déjà existant, default 1.0) est rempli avec
le poids Brier effectif pour traçabilité dans l'attestation.

### Vérification C1 — grep des 7 signatures

```bash
grep -rn "compute_consensus" --include="*.py" database/ services/ cli/ app/ tests/
grep -rn "extract_from_text" --include="*.py" database/ services/ cli/ app/ tests/
grep -rn "_extract_triplets_from_responses" --include="*.py" database/ services/ cli/ app/ tests/
grep -rn "execute_cycle" --include="*.py" database/ services/ cli/ app/ tests/
grep -rn "execute_cycles" --include="*.py" database/ services/ cli/ app/ tests/
grep -rn "_extract_triplets_from_question" --include="*.py" database/ services/ cli/ app/ tests/
grep -rn "run_pipeline" --include="*.py" database/ services/ cli/ app/ tests/
```

Chaque appelant doit être mis à jour pour accepter (ou ignorer) le nouveau paramètre.

### Tests RED-GREEN-FIX

**RED 1** — Consensus pondéré change le score :
```python
async def test_weighted_consensus_changes_score():
    """Un modèle avec poids 0.1 influence moins qu'un modèle avec poids 1.0."""
    engine = ConsensusEngine(min_agreement=0.3)
    # 3 modèles, même triplet, mais poids différents
    results_equal = await engine.compute_consensus(model_results)
    results_weighted = await engine.compute_consensus(model_results, model_weights={"a": 1.0, "b": 0.1, "c": 1.0})
    assert results_equal[0].consensus_score != results_weighted[0].consensus_score
```

**RED 2** — Cold start = poids neutre :
```python
async def test_cold_start_model_gets_neutral_weight():
    """Modèle sans historique Brier → poids 1.0."""
    # get_model_brier_score retourne None pour un modèle inconnu
    brier = await db.get_model_brier_score("nouveau_modele")
    weight = 1.0 if not brier or brier["total_resolved"] == 0 else max(0.0, 1.0 - brier["avg_brier_score"])
    assert weight == 1.0
```

**RED 3** — model_weights=None → backward compat :
```python
async def test_consensus_without_weights_unchanged():
    """Sans model_weights, le comportement est identique à l'actuel."""
    engine = ConsensusEngine()
    result_old = await engine.compute_consensus(model_results)
    result_new = await engine.compute_consensus(model_results, model_weights=None)
    assert result_old == result_new
```

### Validation

```bash
pytest tests/ --tb=short
# Attendu : 487+ passed, 0 failed
```

---

## R-2.1.2 — DASHBOARD PERFORMANCE MODÈLES

> **But** : Visualiser les Brier scores et poids effectifs de chaque modèle.
> **Dépend de** : R-2.1.1 (les poids doivent être calculés pour être affichés).

### Modifications

**A. `engine.py` — Nouvelle méthode `get_all_model_brier_scores()`**

Retourne la liste complète des modèles avec leurs stats Brier
(utilise la vue `v_model_brier_scores` existante).

**B. `epp_cli.py` — Commande `epp models stats`**

Affiche un tableau :
```
Model               | Predictions | Resolved | Avg Brier | Weight
ollama::mistral:7b  | 42          | 12       | 0.2341    | 0.77
ollama::llama3:8b   | 38          | 8        | 0.3102    | 0.69
ollama::qwen2:7b    | 15          | 0        | -         | 1.00 (cold)
```

### Tests

**RED** — La commande CLI retourne des stats formatées :
```python
async def test_models_stats_returns_formatted_output():
    """epp models stats retourne un tableau lisible avec poids calculés."""
```

### Validation

```bash
pytest tests/ --tb=short
```

---

## R-2.2.1 — DIVERSITÉ ARCHITECTURALE DANS LE CONSENSUS

> **But** : Les familles d'architecture sous-représentées ne sont pas pénalisées.
> **ADR à lire** : ADR-005 (condition "≥ 2 familles" pour tier validated),
>   ADR-007 (attestations append-only).
> **Infrastructure existante** :
> - `infer_architecture_family()` — classifie les modèles par famille
> - `ConsensusTriplet.contributing_models` — liste des modèles contributeurs

### Principe (corrigé — diagnostic D3)

Deux mécanismes complémentaires :

**A. Diversité comme métrique (déjà dans la signature 5D `relation_diversity`).**
Pas de changement — elle reste une dimension descriptive.

**B. Bonus de diversité APRÈS crystallize() (Option C — décision humain 15/02).**

Le bonus ne doit PAS modifier le `consensus_score` brut ni le `confidence_tier`
(violation ADR-005 si un score de 0.64 passe à 0.704 → tier change de
`proposition` à `validated`).

Le bonus est appliqué dans `post_crystallization_hook()` et stocké dans
deux nouvelles colonnes de la table `attestations` :
- `adjusted_consensus_score REAL` — `consensus_score × diversity_bonus_factor`, cap à 1.0
- `diversity_bonus_factor REAL DEFAULT 1.0` — 1.0 (mono-famille) ou 1.1 (≥ 2 familles)

Le `consensus_score` et le `confidence_tier` de l'attestation restent immuables
(ADR-007).

### Modifications

**A. `schema.sql` — Ajouter 2 colonnes à `attestations`**

```sql
-- Ajout à la table attestations :
adjusted_consensus_score REAL,         -- score × diversity_bonus_factor (cap 1.0)
diversity_bonus_factor REAL DEFAULT 1.0 -- 1.0=mono-famille, 1.1=multi-famille
```

**B. `post_crystallization_hook()` — Calculer et stocker le bonus**

Après crystallize() et store_attestation(), le hook :
1. Récupère les familles des modèles contributeurs via `infer_architecture_family()`
2. Si ≥ 2 familles distinctes → `diversity_bonus_factor = 1.1`
3. `adjusted_consensus_score = min(consensus_score * factor, 1.0)`
4. UPDATE attestation avec les deux champs

**C. `engine.py` — Méthode `update_attestation_diversity_bonus()`**

Met à jour `adjusted_consensus_score` et `diversity_bonus_factor`
pour une attestation existante. Ce n'est PAS un UPDATE du contenu
épistémique immuable (ADR-007) — c'est un enrichissement post-hoc
comparable aux champs Solana.

### Tests RED-GREEN-FIX

**RED 1** — Diversité multi-famille produit un bonus :
```python
async def test_diversity_bonus_with_multiple_families():
    """Triplet confirmé par 2 familles → adjusted_score > consensus_score."""
    # families: {"mistral": "transformer_dense", "llama": "transformer_dense"} → 1 famille → factor 1.0
    # families: {"mistral": "transformer_dense", "mixtral": "transformer_moe"} → 2 familles → factor 1.1
```

**RED 2** — Mono-famille = pas de bonus :
```python
async def test_no_bonus_single_family():
    """Tous les modèles de la même famille → diversity_bonus_factor == 1.0."""
```

**RED 3** — Le consensus_score brut ne change pas :
```python
async def test_consensus_score_unchanged_by_diversity():
    """Le consensus_score original dans l'attestation est inchangé (ADR-005/007)."""
```

### Validation

```bash
pytest tests/ --tb=short
# Vérifier le schéma :
python -c "
import sqlite3
conn = sqlite3.connect(':memory:')
with open('database/schema.sql') as f: conn.executescript(f.read())
cursor = conn.execute('PRAGMA table_info(attestations)')
columns = [row[1] for row in cursor.fetchall()]
assert 'adjusted_consensus_score' in columns
assert 'diversity_bonus_factor' in columns
print('Schema OK — diversity columns exist')
"
```

---

## R-2.2.2 — CLUSTERING EMBEDDINGS (Détection Sybil)

> **But** : Détecter les réponses quasi-identiques qui contournent le comptage.
> **Infrastructure existante** :
> - `EmbeddingProvider.embed()` — génère des vecteurs pour tout texte
> - `entity_resolver.py` — utilise déjà la similarité cosinus pour résolution
> - `MockEmbeddingProvider` dans `tests/conftest.py:142-182` — retourne vecteurs
>   uniformes (inutile pour clustering, voir diagnostic D4)

### Principe

Avant le consensus, les réponses brutes des modèles sont embeddées.
Si deux réponses ont une similarité cosinus > seuil (ex: 0.95),
elles sont marquées comme "quasi-identiques" et le deuxième modèle
voit son poids effectif divisé par 2 dans le consensus.

Ce n'est PAS une exclusion — c'est une pondération. Un modèle Sybil
vote toujours, mais son influence est réduite proportionnellement
à sa similarité avec un autre votant.

### Modifications

**A. Nouveau module `services/esmm/response_deduplicator.py`**

```python
async def detect_similar_responses(
    responses: dict[str, str],       # model_id → raw response text
    embedding_provider: EmbeddingProvider,
    similarity_threshold: float = 0.95,
) -> dict[str, float]:
    """Retourne un dict model_id → penalty_factor (1.0 = pas de pénalité, 0.5 = quasi-doublon)."""
```

**B. Intégrer la détection dans la chaîne de propagation (Option A)**

Le penalty_factor est multiplié au poids Brier du modèle dans l'orchestrateur
(point E de R-2.1.1), avant passage aux cycles.
Un modèle avec Brier 0.77 et penalty 0.5 → poids effectif 0.385.

**C. `ModelVote` — Enrichir la traçabilité**

Champ optionnel `similarity_penalty: float = 1.0` pour audit.

**D. `tests/conftest.py` — Nouveau `MockDeterministicEmbeddingProvider`**

Le `MockEmbeddingProvider` existant retourne `[0.1] * 768` pour tout texte
(cosinus toujours = 1.0, inutilisable pour tester le clustering).

Créer un `MockDeterministicEmbeddingProvider` qui retourne des vecteurs
basés sur un hash du texte :
- Textes identiques → même vecteur → cosinus = 1.0
- Textes différents → vecteurs différents → cosinus < 1.0

```python
class MockDeterministicEmbeddingProvider(EmbeddingProvider):
    async def embed(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).digest()
        return [b / 255.0 for b in h[:self.dimension_value]]
```

### Tests RED-GREEN-FIX

**RED 1** — Réponses identiques détectées :
```python
async def test_identical_responses_detected():
    """Deux réponses identiques → penalty_factor < 1.0 pour la seconde."""
```

**RED 2** — Réponses différentes non pénalisées :
```python
async def test_different_responses_no_penalty():
    """Réponses divergentes → tous les penalty_factors == 1.0."""
```

**RED 3** — Seuil configurable :
```python
async def test_similarity_threshold_respected():
    """Réponses similaires mais sous le seuil → pas de pénalité."""
```

### Validation

```bash
pytest tests/ --tb=short
```

---

## R-2.2.3 — COMMIT-REVEAL COMPLET

> **But** : Prouver que les modèles n'ont pas vu les réponses des autres avant de voter.
> **Scope** : Complet avec stockage DB (décision humain 15/02).
> **ADR à lire** : ADR-007 (attestations append-only).

### Principe

Le protocole en 3 temps :

1. **COMMIT** — Chaque modèle génère sa réponse. Le hash SHA-256 de la réponse
   est stocké en DB AVANT que les réponses soient partagées pour le débat.
2. **REVEAL** — Les réponses brutes sont utilisées normalement dans le pipeline.
3. **VERIFY** — Après le consensus, on vérifie que hash(réponse) == hash committé.
   Si mismatch → le vote du modèle est invalidé.

Dans un setup mono-opérateur, ce protocole est une preuve d'intégrité du process,
pas une défense adversariale. Il prouve qu'on n'a pas manipulé les réponses
après coup. La valeur est pour le hackathon : le juge peut vérifier la chaîne.

### Point d'insertion — diagnostic D5

Les réponses brutes sont **déjà persistées** dans `exploration_cycles.responses`
(colonne `TEXT NOT NULL`, JSON `{model_name: response_text}`).
Le verify peut relire directement depuis cette table sans re-stocker les réponses.

Point d'insertion dans `execute_cycle()` (cycle_manager.py) :

```python
# cycle_manager.py — execute_cycle()

L214:  responses = await self._query_models(question, cycle_type, timeout)
       # ↑ responses = Dict[str, str] = {model_name: response_text}

       # === COMMIT (insérer ici) ===
       for model_id, response_text in responses.items():
           response_hash = hashlib.sha256(response_text.encode()).hexdigest()
           await self.db.store_commit(self.run_id, model_id, cycle_type.value, response_hash)

L256:  extraction_result = await self._extract_triplets_from_responses(...)
L261:  cycle_id = await self._log_cycle(responses=responses, ...)
```

Le verify se fait en post-crystallization via `exploration_cycles` :

```python
cycle = await db.get_exploration_cycle(cycle_id)
stored_responses = json.loads(cycle["responses"])
for model_id, text in stored_responses.items():
    computed_hash = hashlib.sha256(text.encode()).hexdigest()
    committed = await db.get_commit(run_id, model_id, phase)
    verified = (computed_hash == committed["response_hash"])
```

### Double stockage (décision humain 15/02)

**Table `commit_reveal`** — journal granulaire (hash par modèle/phase) :

```sql
CREATE TABLE IF NOT EXISTS commit_reveal (
    commit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    model_id TEXT NOT NULL,
    phase TEXT NOT NULL,              -- 'divergent' | 'debate' | 'meta'
    response_hash TEXT NOT NULL,      -- SHA-256 de la réponse brute
    committed_at REAL NOT NULL DEFAULT (unixepoch('now')),
    revealed_at REAL,                 -- NULL jusqu'au reveal
    verified INTEGER,                 -- NULL=pending, 1=match, 0=mismatch
    FOREIGN KEY (run_id) REFERENCES esmm_runs(run_id)
);
```

**Colonne dans `attestations`** — verdict sans jointure :

```sql
-- Ajout à la table attestations :
commit_reveal_verified INTEGER       -- NULL=pas de commit-reveal, 1=intègre, 0=mismatch
```

### Modifications

**A. `schema.sql` — Nouvelle table `commit_reveal` + colonne `attestations`**

Ajouter la table et la colonne ci-dessus.

**B. `engine.py` — Méthodes CRUD**

- `store_commit(run_id, model_id, phase, response_hash)`
- `get_commit(run_id, model_id, phase) → dict | None`
- `verify_and_update_commit(run_id, model_id, phase, revealed_response) → bool`
- `update_attestation_commit_verified(attestation_id, verified: bool)`

**C. `cycle_manager.py` — Intégrer commit dans le flux**

Entre L214 et L256 de `execute_cycle()` : hash et store_commit pour chaque réponse.

**D. `post_crystallization_hook()` — Intégrer verify**

Après crystallization, pour chaque attestation :
1. Récupérer les commits du run
2. Relire les réponses depuis `exploration_cycles`
3. Vérifier hash(réponse) == committed hash
4. Stocker le verdict dans `attestations.commit_reveal_verified`
5. Mettre à jour `commit_reveal.verified` et `commit_reveal.revealed_at`

**E. `epp_cli.py` — Commande `epp verify <run_id>`**

Affiche les résultats de vérification commit-reveal pour un run.

### Tests RED-GREEN-FIX

**RED 1** — Commit stocké et vérifiable :
```python
async def test_commit_stored_and_verifiable():
    """store_commit → verify_and_update_commit avec même réponse → True."""
```

**RED 2** — Réponse altérée détectée :
```python
async def test_altered_response_detected():
    """store_commit → verify_and_update_commit avec réponse différente → False."""
```

**RED 3** — Verdict dans attestation :
```python
async def test_attestation_commit_verified_column():
    """Après verify, attestation.commit_reveal_verified == 1 (intègre)."""
```

**RED 4** — Intégrité du pipeline complet :
```python
async def test_pipeline_commit_reveal_integrity():
    """Un run complet avec MockProvider → tous les commits vérifiés."""
```

### Validation

```bash
pytest tests/ --tb=short
# Vérifier aussi la cohérence schéma :
python -c "
import sqlite3
conn = sqlite3.connect(':memory:')
with open('database/schema.sql') as f: conn.executescript(f.read())
print('Schema OK — commit_reveal table exists')
cursor = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='commit_reveal'\")
assert cursor.fetchone() is not None
cursor = conn.execute('PRAGMA table_info(attestations)')
columns = [row[1] for row in cursor.fetchall()]
assert 'commit_reveal_verified' in columns
print('Schema OK — commit_reveal_verified column exists')
"
```

---

## TABLEAU RÉCAPITULATIF

| Sous-phase | Scope | Fichiers modifiés | Effort | Priorité |
|------------|-------|-------------------|--------|----------|
| R-2.1.1 | Pondération Brier → consensus | consensus_engine, triplet_extractor, cycle_manager, orchestrator, pipeline | 4-5h | P0 |
| R-2.1.2 | Dashboard modèles CLI | engine, epp_cli | 1-2h | P3 |
| R-2.2.1 | Diversité architecturale | schema, attestation, post_crystallization, engine | 2-3h | P1 |
| R-2.2.2 | Clustering embeddings | nouveau module, orchestrator, conftest | 3-4h | P2 |
| R-2.2.3 | Commit-reveal complet | schema, engine, cycle_manager, post_crystallization, epp_cli | 5-7h | P4 |

**Total** : 15-21h. Si temps limité, R-2.2.3 saute en premier, R-2.1.2 en second.

---

## RÈGLES TRANSVERSALES

1. **RED-GREEN-FIX** pour toute modification de compute_consensus() ou du pipeline.
2. **ADR** consultés avant chaque sous-phase (`cat docs/adr/*.md`).
3. **Backward compat** : tous les nouveaux paramètres sont optionnels avec defaults
   qui reproduisent le comportement actuel. Aucun test existant ne doit casser.
4. **pytest complet** à la fin de chaque sous-phase.
5. **CHANGELOG.md** mis à jour à chaque sous-phase.
6. **Signature check** (C1) : 7 signatures modifiées en R-2.1.1 →
   grep obligatoire sur chacune (voir section "Vérification C1").
7. **Schéma check** (C4) : R-2.2.1 et R-2.2.3 ajoutent des colonnes/tables →
   vérifier schema.sql à chaque sous-phase concernée.

---

*PLAN_TACTIQUE_R2.md — EPP_Verdict*
*Rédigé par Claude Opus — 15 février 2026*
*Corrigé par Claude Code — 15 février 2026 (diagnostic D1-D6, 10 corrections)*
*Décisions humaines intégrées : cold start neutre, commit-reveal complet,*
*Option A (propagation), Option C (bonus post-crystallize), double stockage.*
