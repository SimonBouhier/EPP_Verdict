# PHASE 0.2 — Migration Embedding Sans Perte

> **Instructions pour Claude Code.** Lis CLAUDE.md ET ce fichier avant chaque étape.
> Ce document est ta feuille de route pour la Phase 0.2. Tu exécutes dans l'ordre, étape par étape.
> **Tu ne passes PAS à l'étape suivante tant que les tests de l'étape courante ne passent pas tous.**

---

## CONTEXTE

Le graphe de connaissances stocke des embeddings (vecteurs) pour chaque concept.
Aujourd'hui, ces embeddings sont couplés à un modèle spécifique (nomic-embed-text ou mxbai-embed-large)
sans vrai versioning. Si on change de modèle d'embedding, on perd les anciens vecteurs.

**Objectif** : Pouvoir changer de modèle d'embedding sans perdre le graphe existant.
Les anciens vecteurs sont conservés, les nouveaux coexistent, le rollback est toujours possible.

**Critère de validation final** : Lancer une migration de modèle A vers modèle B, vérifier que les deux
versions coexistent dans la base, que la recherche de similarité fonctionne, et que le graphe est intact.

---

## AXIOMES À RESPECTER (rappel — violations = refus du code)

1. **Obsolescence permanente des modèles** — AUCUNE dimension (768, 1024) ni nom de modèle
   ("nomic-embed-text", "mxbai-embed-large") codé en dur dans le pipeline.
   Tout passe par `EmbeddingProvider.get_dimension()` et `EmbeddingProvider.get_model_id()`.
   Les seuls endroits autorisés pour des valeurs concrètes : `config.yaml`, les tests, et les scripts CLI.

2. **Le graphe survit à tout** — Les anciens vecteurs ne sont JAMAIS écrasés tant que les nouveaux
   ne sont pas validés. La colonne `concepts.embedding` n'est mise à jour qu'en dernière étape,
   après confirmation que 100% des concepts ont été re-embedded avec succès.

3. **Transparence des coupures** — Chaque migration est journalisée : modèle source, modèle cible,
   nombre de succès/échecs, timestamps. Traçabilité complète.

4. **Calcul local** — Tout est off-chain. Pas d'impact Solana.

---

## ÉTAPE 0.2.1 — Schéma et versioning

### Ce que tu fais

**A. Créer la table `concept_embeddings` dans `schema.sql`**

```sql
CREATE TABLE IF NOT EXISTS concept_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    concept_id TEXT NOT NULL,
    model_id TEXT NOT NULL,           -- ex: "nomic-embed-text", "mxbai-embed-large"
    dimension INTEGER NOT NULL,       -- ex: 768, 1024
    embedding BLOB NOT NULL,          -- vecteur float32 sérialisé
    created_at REAL NOT NULL DEFAULT (unixepoch('now')),

    UNIQUE(concept_id, model_id),
    FOREIGN KEY (concept_id) REFERENCES concepts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_concept_embeddings_model ON concept_embeddings(model_id);
CREATE INDEX IF NOT EXISTS idx_concept_embeddings_concept ON concept_embeddings(concept_id);
```

**B. Créer la table `embedding_migrations` dans `schema.sql`**

```sql
CREATE TABLE IF NOT EXISTS embedding_migrations (
    migration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_model TEXT NOT NULL,
    to_model TEXT NOT NULL,
    dimension_from INTEGER NOT NULL,
    dimension_to INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'running' | 'completed' | 'failed' | 'rolled_back'
    concepts_total INTEGER DEFAULT 0,
    concepts_migrated INTEGER DEFAULT 0,
    concepts_failed INTEGER DEFAULT 0,
    started_at REAL,
    completed_at REAL,
    triggered_by TEXT DEFAULT 'manual',      -- 'manual' | 'config_change' | 'cli'
    error_log TEXT                            -- JSON array of {concept_id, error}
);
```

**C. Ajouter une migration SQL dans `engine.py` → `initialize()`**

Dans le bloc `migrations` existant de `engine.py`, ajouter une migration qui copie les embeddings
existants de `concepts.embedding` vers `concept_embeddings` :

```python
# Migration: copier embeddings existants vers concept_embeddings (Phase 0.2)
# Ne s'exécute qu'une fois grâce à la contrainte UNIQUE(concept_id, model_id)
"""
INSERT OR IGNORE INTO concept_embeddings (concept_id, model_id, dimension, embedding, created_at)
SELECT id, COALESCE(embedding_model, 'mxbai-embed-large'), 
       CASE COALESCE(embedding_model, 'mxbai-embed-large')
           WHEN 'mxbai-embed-large' THEN 1024
           WHEN 'nomic-embed-text' THEN 768
           ELSE 0
       END,
       embedding, 
       COALESCE(embedding_updated_at, unixepoch('now'))
FROM concepts 
WHERE embedding IS NOT NULL
"""
```

**ATTENTION** : La dimension doit être déduite du modèle connu OU de la taille réelle du blob.
Si la taille du blob ne correspond pas, log un warning mais copie quand même (on corrigera ensuite).

### Ce que tu ne fais PAS

- Tu ne supprimes PAS la colonne `concepts.embedding` (elle reste comme cache)
- Tu ne modifies PAS la structure de la table `concepts`
- Tu ne touches PAS aux fichiers Python autres que `engine.py` (pour la migration)

### Tests étape 0.2.1

```python
# test_phase02_schema.py

import pytest
import aiosqlite
import struct

@pytest.fixture
async def db_with_embeddings(tmp_path):
    """Crée une DB avec quelques concepts et embeddings."""
    # Utiliser ISpaceDB.initialize() puis insérer des concepts de test
    # avec des embeddings de dimensions connues (768 et 1024)
    ...

async def test_concept_embeddings_table_exists(db_with_embeddings):
    """La table concept_embeddings existe après initialize()."""
    ...

async def test_embedding_migrations_table_exists(db_with_embeddings):
    """La table embedding_migrations existe après initialize()."""
    ...

async def test_existing_embeddings_copied(db_with_embeddings):
    """Les embeddings existants dans concepts.embedding sont copiés 
    dans concept_embeddings avec le bon model_id et la bonne dimension."""
    ...

async def test_copy_is_idempotent(db_with_embeddings):
    """Appeler initialize() deux fois ne duplique pas les embeddings."""
    ...

async def test_unique_constraint(db_with_embeddings):
    """On ne peut pas avoir deux embeddings du même modèle pour le même concept."""
    ...
```

**Critère de passage** : `pytest tests/test_phase02_schema.py -v` → tous verts.

---

## ÉTAPE 0.2.2 — Découplage des dimensions hardcodées

### Ce que tu fais

**A. `memory.py` — Supprimer le check `!= 1024`**

Remplacer :
```python
if not content or not embeddings or len(embeddings) != 1024:
    return None
```

Par :
```python
if not content or not embeddings or len(embeddings) < 1:
    return None
```

Le check de dimension sera fait par l'appelant via `EmbeddingProvider.get_dimension()`.
La mémoire sémantique accepte n'importe quelle dimension valide (> 0).

Note : `_cosine_similarity` vérifie déjà `len(vec1) != len(vec2)`, donc les vecteurs de
dimensions différentes ne seront jamais comparés.

**B. `embeddings.py` (legacy) — Déprécier**

Ajouter un avertissement en haut du fichier :
```python
"""
DEPRECATED — Use services.providers.ollama_embeddings.OllamaEmbeddingProvider instead.
This module is kept for backward compatibility only.
All new code MUST use the EmbeddingProvider interface.
"""
import warnings
warnings.warn(
    "embeddings.py is deprecated. Use OllamaEmbeddingProvider via EmbeddingProvider interface.",
    DeprecationWarning,
    stacklevel=2
)
```

Ne PAS supprimer le fichier — d'autres scripts peuvent encore l'importer.
Identifier les imports de `embeddings.py` dans le projet et les lister dans un commentaire TODO.

**C. `hydrate_embeddings.py` — Marquer comme outil legacy isolé**

Ajouter un header :
```python
"""
LEGACY TOOL — Not part of the main pipeline.
Uses direct HTTP calls to Ollama (not EmbeddingProvider).
For production embedding migration, use tools/migrate_embeddings.py instead.
"""
```

Ne PAS réécrire ce fichier — il n'est pas dans le pipeline critique.

**D. `engine.py` — Mettre à jour `add_concept()`**

La méthode `add_concept()` doit accepter et stocker `embedding_model` :

```python
async def add_concept(
    self,
    concept_id: str,
    rho_static: float = 0.0,
    embedding: bytes = None,
    embedding_model: str = None,  # NOUVEAU — obligatoire si embedding fourni
    source: str = "manual",
    first_seen_model: str = None
) -> None:
```

Si `embedding` est fourni mais pas `embedding_model`, lever un `ValueError`.
Écrire aussi dans `concept_embeddings` en même temps que dans `concepts`.

### Ce que tu ne fais PAS

- Tu ne réécris PAS `hydrate_embeddings.py` ni `embeddings.py` entièrement
- Tu ne changes PAS la signature publique de `memory.py` (SemanticMemory)
- Tu ne supprimes PAS de fichier

### Tests étape 0.2.2

```python
# test_phase02_decoupling.py

async def test_memory_accepts_768d():
    """SemanticMemory.store_memory() accepte des vecteurs 768D."""
    ...

async def test_memory_accepts_1024d():
    """SemanticMemory.store_memory() accepte des vecteurs 1024D."""
    ...

async def test_memory_rejects_empty():
    """SemanticMemory.store_memory() rejette les vecteurs vides."""
    ...

async def test_cosine_rejects_mixed_dimensions():
    """_cosine_similarity retourne 0.0 pour des vecteurs de dimensions différentes."""
    ...

async def test_add_concept_requires_model_with_embedding(db):
    """add_concept() avec embedding mais sans embedding_model lève ValueError."""
    ...

async def test_add_concept_writes_to_both_tables(db):
    """add_concept() avec embedding écrit dans concepts ET concept_embeddings."""
    ...

def test_legacy_embeddings_deprecation_warning():
    """Importer embeddings.py émet un DeprecationWarning."""
    ...
```

**Critère de passage** : `pytest tests/test_phase02_decoupling.py -v` → tous verts.

---

## ÉTAPE 0.2.3 — Pipeline de migration progressive

### Ce que tu fais

**A. Réécrire `tools/migrate_embeddings.py`**

Le nouveau script DOIT :

1. **Utiliser `EmbeddingProvider`** (pas d'appel HTTP direct à Ollama)
2. **Lire le modèle cible depuis `config.yaml`** ou un argument CLI
3. **Écrire dans `concept_embeddings`** (jamais écraser `concepts.embedding` directement)
4. **Journaliser dans `embedding_migrations`** (début, progression, fin)
5. **Supporter `--dry-run`** : affiche ce qui serait fait sans écrire
6. **Supporter `--batch-size N`** : nombre de concepts par batch (défaut: 50)
7. **Être idempotent** : si un concept a déjà un embedding pour le modèle cible, le skip
8. **Reporter les erreurs** : concept_id + erreur dans `embedding_migrations.error_log`

**Structure du script :**

```python
"""
EPP Embedding Migration Tool
============================
Migrates concept embeddings from one model to another.
Uses EmbeddingProvider interface — no hardcoded model or dimension.

Usage:
    python tools/migrate_embeddings.py --to nomic-embed-text --batch-size 50
    python tools/migrate_embeddings.py --to mxbai-embed-large --dry-run
    python tools/migrate_embeddings.py --finalize  # Updates concepts.embedding cache
    python tools/migrate_embeddings.py --rollback <migration_id>
"""
```

**Phases de migration :**

```
Phase 1: PREPARE
  - Vérifier que le provider cible est accessible (health_check)
  - Compter les concepts à migrer
  - Créer l'entrée dans embedding_migrations (status='running')

Phase 2: MIGRATE
  - Pour chaque batch de concepts :
    - Récupérer le concept_id (le texte à embedder)
    - Appeler EmbeddingProvider.embed(concept_id)
    - Sérialiser en blob float32
    - INSERT OR IGNORE INTO concept_embeddings
    - Mettre à jour embedding_migrations.concepts_migrated
  - Si erreur : logger dans error_log, continuer le batch

Phase 3: FINALIZE (commande séparée --finalize)
  - Seulement si concepts_failed == 0
  - Copier les nouveaux vecteurs de concept_embeddings vers concepts.embedding
  - Mettre à jour concepts.embedding_model et concepts.embedding_updated_at
  - Mettre à jour embedding_migrations.status = 'completed'

Phase ROLLBACK (commande --rollback <migration_id>)
  - Supprimer les entrées concept_embeddings pour le modèle cible
  - Restaurer concepts.embedding depuis concept_embeddings du modèle source
  - Mettre à jour embedding_migrations.status = 'rolled_back'
```

**B. Ajouter des méthodes dans `engine.py`**

```python
async def store_concept_embedding(
    self, concept_id: str, model_id: str, dimension: int, embedding: bytes
) -> None:
    """Stocke un embedding versionné dans concept_embeddings."""
    ...

async def get_concept_embedding(
    self, concept_id: str, model_id: str
) -> Optional[bytes]:
    """Récupère un embedding pour un concept et un modèle donné."""
    ...

async def get_concepts_needing_migration(
    self, target_model: str, limit: int = 100
) -> List[str]:
    """Retourne les concept_ids qui ont un embedding mais pas pour target_model."""
    ...

async def create_embedding_migration(
    self, from_model: str, to_model: str, dim_from: int, dim_to: int
) -> int:
    """Crée une entrée de migration et retourne migration_id."""
    ...

async def update_embedding_migration(
    self, migration_id: int, **kwargs
) -> None:
    """Met à jour les champs d'une migration (concepts_migrated, status, etc.)."""
    ...

async def finalize_embedding_migration(
    self, migration_id: int, target_model: str
) -> int:
    """Copie concept_embeddings → concepts.embedding pour le modèle cible. 
    Retourne le nombre de concepts mis à jour."""
    ...
```

### Ce que tu ne fais PAS

- Tu ne supprimes PAS l'ancien `migrate_embeddings.py` — tu le remplaces
- Tu n'appelles PAS directement httpx/requests — tout passe par EmbeddingProvider
- Tu ne touches PAS à `concepts.embedding` dans la phase MIGRATE (seulement dans FINALIZE)

### Tests étape 0.2.3

```python
# test_phase02_migration.py

async def test_store_concept_embedding(db):
    """store_concept_embedding écrit dans concept_embeddings."""
    ...

async def test_get_concept_embedding(db):
    """get_concept_embedding lit depuis concept_embeddings."""
    ...

async def test_concepts_needing_migration(db):
    """get_concepts_needing_migration retourne les concepts sans embedding pour le modèle cible."""
    ...

async def test_migration_is_idempotent(db):
    """Relancer la migration ne duplique pas les embeddings (UNIQUE constraint)."""
    ...

async def test_finalize_copies_to_concepts(db):
    """finalize_embedding_migration copie vers concepts.embedding."""
    ...

async def test_finalize_refuses_if_failures(db):
    """finalize refuse si concepts_failed > 0 dans la migration."""
    ...

async def test_migration_logging(db):
    """Chaque migration est tracée dans embedding_migrations."""
    ...

# Test d'intégration (peut nécessiter Ollama mock)
async def test_full_migration_dry_run():
    """--dry-run ne modifie rien en base."""
    ...
```

**Critère de passage** : `pytest tests/test_phase02_migration.py -v` → tous verts.

---

## ÉTAPE 0.2.4 — Recherche cross-version et configuration

### Ce que tu fais

**A. Ajouter `active_embedding_model` dans `config.yaml`**

```yaml
embeddings:
  active_model: "nomic-embed-text"    # Modèle courant pour les nouvelles opérations
  fallback_reembed: true              # Re-embed à la volée si pas de vecteur pour le modèle actif
  similarity_min_score: 0.1           # Seuil minimum pour les résultats de similarité
```

**B. Modifier la recherche de similarité dans `engine.py`**

Ajouter une méthode :

```python
async def get_concepts_with_embeddings_for_model(
    self, model_id: str, limit: int = 1000
) -> List[Dict]:
    """Récupère les concepts avec embeddings pour un modèle spécifique.
    Cherche d'abord dans concept_embeddings, fallback sur concepts.embedding 
    si le model_id correspond à concepts.embedding_model."""
    ...
```

Modifier `get_concepts_with_embeddings()` existant pour qu'il utilise le `active_model`
de la config au lieu de retourner aveuglément tous les embeddings.

**C. Fallback re-embed à la volée**

Si `fallback_reembed: true` dans la config ET qu'un concept n'a pas de vecteur pour le modèle actif :
- Re-embed via `EmbeddingProvider.embed(concept_id)`
- Stocker dans `concept_embeddings`
- Retourner le nouveau vecteur

Ce fallback est appelé dans `get_concept_embedding()` si le résultat est None et le fallback activé.
**Attention** : le fallback nécessite un `EmbeddingProvider` — `engine.py` ne doit PAS importer
un provider directement. Passer le provider en paramètre optionnel ou utiliser un callback.

**D. S'assurer que `injector.py` et `memory.py` utilisent le bon modèle**

`injector.py` utilise `get_multi_neighbors()` qui ne touche pas aux embeddings directement.
Pas de changement nécessaire pour le moment.

`memory.py` stocke les embeddings en mémoire (pas en DB). Vérifier qu'il n'y a pas de
mismatch de dimensions entre les vecteurs stockés et les nouveaux. Le check dimensionnel
dans `_cosine_similarity` protège déjà contre ça.

### Ce que tu ne fais PAS

- Tu ne crées PAS de dépendance directe engine.py → OllamaEmbeddingProvider
- Tu ne casses PAS la signature de `get_concepts_with_embeddings()` (ajouter le paramètre en optionnel)

### Tests étape 0.2.4

```python
# test_phase02_search.py

async def test_get_embeddings_for_specific_model(db):
    """get_concepts_with_embeddings_for_model retourne uniquement les vecteurs du modèle demandé."""
    ...

async def test_get_embeddings_default_uses_active_model(db):
    """get_concepts_with_embeddings() utilise le modèle actif de la config."""
    ...

async def test_no_cross_dimension_comparison(db):
    """Les vecteurs 768D et 1024D ne sont jamais mélangés dans un même résultat."""
    ...

async def test_fallback_reembed(db, mock_provider):
    """Si fallback activé et pas de vecteur, re-embed à la volée et cache."""
    ...

async def test_fallback_disabled(db):
    """Si fallback désactivé, retourne None pour un modèle manquant."""
    ...
```

**Critère de passage** : `pytest tests/test_phase02_search.py -v` → tous verts.

---

## ÉTAPE 0.2.5 — Validation finale et nettoyage

### Ce que tu fais

**A. Test d'intégration complet**

Créer `tests/test_phase02_integration.py` qui simule le scénario complet :

1. Créer un graphe avec 20 concepts et des embeddings modèle A (mock 768D)
2. Vérifier que la recherche de similarité fonctionne avec modèle A
3. Lancer une migration vers modèle B (mock 1024D)
4. Vérifier que les deux versions coexistent dans `concept_embeddings`
5. Vérifier que la recherche de similarité fonctionne avec modèle B
6. Vérifier que `concepts.embedding` n'a PAS changé (pas encore finalisé)
7. Finaliser la migration
8. Vérifier que `concepts.embedding` est maintenant en modèle B
9. Vérifier que les relations, cochaines, et autres données sont intactes

**B. Mise à jour de `ARCHITECTURE.md`**

Ajouter dans la section appropriée :

```markdown
### Embedding Versioning (Phase 0.2)

| Table | Rôle | État |
|-------|------|------|
| `concept_embeddings` | Stockage multi-versions des embeddings | ✅ Fonctionnel |
| `embedding_migrations` | Journal des migrations de modèle | ✅ Fonctionnel |

| Fichier | Rôle | État |
|---------|------|------|
| `tools/migrate_embeddings.py` | Migration progressive via EmbeddingProvider | ✅ Fonctionnel |
| `embeddings.py` | Legacy — déprécié, utiliser EmbeddingProvider | ⚠️ Déprécié |
```

**C. Mise à jour de `CHANGELOG.md`**

```markdown
## [YYYY-MM-DD] Phase 0.2 — Migration embedding sans perte

- Créé table `concept_embeddings` (stockage multi-versions, UNIQUE par concept+modèle)
- Créé table `embedding_migrations` (journal des migrations)
- Réécrit `tools/migrate_embeddings.py` : utilise EmbeddingProvider, migration non-destructive, --dry-run, --finalize, --rollback
- Découplé dimensions hardcodées : memory.py accepte toute dimension, embeddings.py marqué déprécié
- Ajouté config `embeddings.active_model` dans config.yaml
- Ajouté méthodes engine.py : store/get_concept_embedding, get_concepts_needing_migration, finalize_embedding_migration
- XX tests unitaires + intégration
```

### Tests étape 0.2.5

Le test d'intégration ci-dessus EST le test de cette étape.

**Critère de passage final** : 
- `pytest tests/test_phase02_*.py -v` → TOUS verts
- Le graphe existant est intact (stats identiques avant/après migration)
- Deux versions d'embeddings coexistent dans `concept_embeddings`
- Le rollback fonctionne (retour au modèle précédent)

---

## RÉSUMÉ — ORDRE D'EXÉCUTION

| Étape | Action | Tests | Bloquant |
|-------|--------|-------|----------|
| 0.2.1 | Schéma SQL + migration données | test_phase02_schema.py | Oui |
| 0.2.2 | Découplage dimensions hardcodées | test_phase02_decoupling.py | Oui |
| 0.2.3 | Pipeline migration progressive | test_phase02_migration.py | Oui |
| 0.2.4 | Recherche cross-version + config | test_phase02_search.py | Oui |
| 0.2.5 | Intégration finale + docs | test_phase02_integration.py | Oui |

**Chaque étape est bloquante. Ne passe pas à la suivante tant que les tests ne sont pas verts.**

---

## FICHIERS MODIFIÉS (inventaire prévu)

| Fichier | Modification | Étape |
|---------|-------------|-------|
| `database/schema.sql` | +2 tables (concept_embeddings, embedding_migrations) | 0.2.1 |
| `database/engine.py` | +migration SQL, +6 méthodes embedding | 0.2.1, 0.2.3, 0.2.4 |
| `services/consciousness/memory.py` | Supprimer check `!= 1024` | 0.2.2 |
| `embeddings.py` | Ajouter DeprecationWarning | 0.2.2 |
| `hydrate_embeddings.py` | Ajouter header legacy | 0.2.2 |
| `tools/migrate_embeddings.py` | Réécriture complète | 0.2.3 |
| `config.yaml` | +section embeddings | 0.2.4 |
| `ARCHITECTURE.md` | +section embedding versioning | 0.2.5 |
| `CHANGELOG.md` | +entrée Phase 0.2 | 0.2.5 |

## FICHIERS CRÉÉS

| Fichier | Contenu | Étape |
|---------|---------|-------|
| `tests/test_phase02_schema.py` | Tests schéma et migration données | 0.2.1 |
| `tests/test_phase02_decoupling.py` | Tests découplage dimensions | 0.2.2 |
| `tests/test_phase02_migration.py` | Tests pipeline migration | 0.2.3 |
| `tests/test_phase02_search.py` | Tests recherche cross-version | 0.2.4 |
| `tests/test_phase02_integration.py` | Test intégration complet | 0.2.5 |

## FICHIERS NON TOUCHÉS (vérification)

- `CLAUDE.md` — JAMAIS
- `EPP_PLAN_MVP.md` — JAMAIS
- `orchestrator.py` — pas de lien avec embeddings
- `cycle_manager.py` — pas de lien
- `consensus_engine.py` — pas de lien
- `cochain_builder.py` — pas de lien
- Tout le dossier `services/providers/` sauf utilisation de l'interface EmbeddingProvider
