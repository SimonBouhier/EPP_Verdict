# PHASE 3.2 — CORRECTIONS POST-AUDIT + ANNOTATIONS

> **Instructions pour Claude Code.** Lis CLAUDE.md, ARCHITECTURE.md, ET ce fichier.
>
> **RÈGLE ABSOLUE** : `pytest tests/ --tb=short` avant et après chaque bloc.
> Si un test qui passait avant échoue → **stop, annule, reporte.**
>
> **État actuel** : 425 passed, 0 failed, 10 skipped
> **État cible** : 425+ passed, 0 failed, ≤10 skipped (les tables ajoutées ne
> cassent rien car elles n'existaient pas avant — les tests mockent ces chemins)

---

## PRIORITÉ DES BLOCS

| Bloc | Sujet | Criticité | Risque de régression |
|------|-------|-----------|---------------------|
| **B0** | Schéma SQL incomplet (6 tables manquantes) | 🔴🔴🔴 | Nul (tables absentes = ajout pur) |
| **B1** | Crashs runtime (imports cassés, signatures) | 🔴🔴 | Faible (correctifs ciblés) |
| **B2** | Annotations audit dans le code | ⚪ | Nul (commentaires seulement) |

---

## BLOC 0 — SCHÉMA SQL INCOMPLET

### Diagnostic

`engine.py` référence 23 tables. `schema.sql` n'en définit que 18.
**6 tables sont complètement absentes du schéma** :

| Table | Utilisée par | Crash si appelée |
|-------|-------------|-----------------|
| `attestations` | `store_attestation()`, `get_attestation_by_hash()`, `get_latest_attestation()`, `get_attestation_count()`, `get_attestations_by_subject()`, `update_attestation_solana_tx()`, `update_attestation_submission_status()` | OUI — `epp ask` crashera |
| `concept_embeddings` | `store_concept_embedding()`, `add_concept()` Phase 0.2, `find_similar_concepts()` | OUI — embedding versioning cassé |
| `embedding_migrations` | `record_embedding_migration()`, `update_migration_progress()`, `get_migration()`, `finalize_embedding_migration()`, `rollback_embedding_migration()` | OUI — outil migration cassé |
| `metrological_frames` | `initialize()` seed, `store_metrological_frame()`, `get_metrological_frame()`, `list_metrological_frames()` | OUI — `epp frame list` crashera |
| `model_track_record` | `record_model_prediction()`, `resolve_prediction()` | OUI — post-crystallization crashera |
| `tier_transitions` | `log_tier_transition()` | OUI — post-crystallization crashera |

Les tests passent (425) parce qu'ils mockent les méthodes DB ou ne traversent pas ces
chemins. **Toute exécution réelle du pipeline crashera.**

### Étape B0 — Ajouter les 6 tables à schema.sql

⚡ **VÉRIFIE D'ABORD** :

```bash
# Confirmer les tables manquantes
grep -oP "(?:FROM|INTO|UPDATE|JOIN)\s+(\w+)" database/engine.py | awk '{print $2}' | sort -u | grep -v SET > /tmp/engine_tables.txt
grep -oP "CREATE TABLE IF NOT EXISTS (\w+)" database/schema.sql | awk '{print $NF}' | sort > /tmp/schema_tables.txt
comm -23 /tmp/engine_tables.txt /tmp/schema_tables.txt
```

Résultat attendu : `attestations`, `concept_embeddings`, `embedding_migrations`,
`metrological_frames`, `model_track_record`, `tier_transitions`.

⚡ **RECONSTITUE LE DDL** depuis les colonnes utilisées dans `engine.py`.
Pour chaque table, chercher TOUS les INSERT, SELECT, UPDATE qui la référencent
et en déduire les colonnes, types, et contraintes.

Voici le DDL reconstruit — **vérifie chaque colonne contre engine.py avant d'insérer** :

#### Table `attestations`

```sql
-- ============================================================================
-- TABLE: ATTESTATIONS (Phase 0.3 — Cristallisation épistémique)
-- ============================================================================
-- Stockage append-only des attestations cristallisées.
-- Chaque attestation est un triplet (S,P,O) + consensus + signature 5D.

CREATE TABLE IF NOT EXISTS attestations (
    attestation_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identité du claim
    claim_hash TEXT NOT NULL,                   -- SHA-256 du triplet + frame
    subject TEXT NOT NULL,                      -- Sujet canonique
    predicate TEXT NOT NULL,                    -- Prédicat canonique
    object TEXT NOT NULL,                       -- Objet canonique

    -- Consensus
    consensus_score REAL NOT NULL,              -- Score de consensus [0, 1]
    models_consulted INTEGER NOT NULL,          -- Nombre de modèles consultés
    models_agreeing INTEGER NOT NULL,           -- Nombre de modèles en accord
    model_votes TEXT,                           -- JSON: liste des votes par modèle

    -- Signature 5D
    sig_agreement REAL DEFAULT 0.0,
    sig_semantic_consistency REAL DEFAULT 0.0,
    sig_centrality REAL DEFAULT 0.0,
    sig_stability REAL DEFAULT 0.0,
    sig_relation_diversity REAL DEFAULT 0.0,

    -- Classification
    epistemic_type TEXT NOT NULL,               -- 'factual' | 'analytical' | 'predictive'
    confidence_tier TEXT NOT NULL,              -- 'sandbox' | 'proposition' | 'validated' | 'verified'

    -- Contexte
    metrological_frame TEXT,                    -- Frame ID utilisé
    source_anchor TEXT,                         -- Référence externe optionnelle
    run_id INTEGER,                             -- ESMM run associé
    question TEXT,                              -- Question originale

    -- Métadonnées
    timestamp REAL NOT NULL,                    -- Unix timestamp de création
    protocol_version TEXT DEFAULT '0.3',
    validation_count INTEGER DEFAULT 1,
    previous_hash TEXT,                         -- Hash de l'attestation précédente (chaînage)
    portable_json TEXT,                         -- JSON sérialisé complet

    -- Solana
    solana_tx_signature TEXT,                   -- Signature de transaction on-chain
    submission_status TEXT DEFAULT 'pending',   -- 'pending' | 'submitted' | 'confirmed' | 'failed'

    -- Tracking
    created_at REAL NOT NULL DEFAULT (unixepoch('now'))
);

CREATE INDEX IF NOT EXISTS idx_attestations_hash ON attestations(claim_hash);
CREATE INDEX IF NOT EXISTS idx_attestations_subject ON attestations(subject);
CREATE INDEX IF NOT EXISTS idx_attestations_created ON attestations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_attestations_tier ON attestations(confidence_tier);
CREATE INDEX IF NOT EXISTS idx_attestations_run ON attestations(run_id);
```

#### Table `concept_embeddings`

```sql
-- ============================================================================
-- TABLE: CONCEPT_EMBEDDINGS (Phase 0.2 — Versionnage multi-modèle)
-- ============================================================================
-- Stocke les embeddings par concept ET par modèle.
-- Permet la migration progressive entre modèles d'embedding.

CREATE TABLE IF NOT EXISTS concept_embeddings (
    concept_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    embedding BLOB NOT NULL,
    created_at REAL NOT NULL DEFAULT (unixepoch('now')),

    PRIMARY KEY (concept_id, model_id),
    FOREIGN KEY (concept_id) REFERENCES concepts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_concept_embeddings_model ON concept_embeddings(model_id);
```

#### Table `embedding_migrations`

```sql
-- ============================================================================
-- TABLE: EMBEDDING_MIGRATIONS (Phase 0.2 — Traçabilité des migrations)
-- ============================================================================

CREATE TABLE IF NOT EXISTS embedding_migrations (
    migration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_model TEXT NOT NULL,
    target_model TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',    -- 'pending' | 'running' | 'completed' | 'rolled_back'
    total_concepts INTEGER DEFAULT 0,
    migrated_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    started_at REAL,
    completed_at REAL,
    rolled_back_at REAL,
    created_at REAL NOT NULL DEFAULT (unixepoch('now'))
);
```

#### Table `metrological_frames`

```sql
-- ============================================================================
-- TABLE: METROLOGICAL_FRAMES (Phase 0.3 — Référentiels de mesure)
-- ============================================================================
-- Définit les cadres de mesure pour la validation épistémique.

CREATE TABLE IF NOT EXISTS metrological_frames (
    frame_id TEXT NOT NULL,
    version TEXT NOT NULL,
    domain TEXT NOT NULL,
    metric TEXT NOT NULL,
    description TEXT,
    parameters TEXT,                            -- JSON: paramètres du cadre
    required_sources INTEGER DEFAULT 1,
    governance TEXT,                            -- JSON: règles de gouvernance
    frame_hash TEXT,                            -- Hash du cadre pour intégrité
    created_by TEXT DEFAULT 'system',
    created_at REAL NOT NULL DEFAULT (unixepoch('now')),

    PRIMARY KEY (frame_id, version)
);
```

#### Table `model_track_record`

```sql
-- ============================================================================
-- TABLE: MODEL_TRACK_RECORD (Phase 0.3 — Brier scoring)
-- ============================================================================
-- Track record des prédictions modèles pour calcul du Brier score.

CREATE TABLE IF NOT EXISTS model_track_record (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    claim_hash TEXT NOT NULL,
    predicted_confidence REAL NOT NULL,
    predicted_agreed INTEGER NOT NULL,         -- 0 ou 1
    actual_outcome INTEGER,                    -- NULL tant que non résolu
    brier_score REAL,                          -- Calculé à la résolution
    resolved_at REAL,
    resolution_source TEXT,                    -- 'manual' | 'revalidation' | ...
    created_at REAL NOT NULL DEFAULT (unixepoch('now'))
);

CREATE INDEX IF NOT EXISTS idx_track_model ON model_track_record(model_id);
CREATE INDEX IF NOT EXISTS idx_track_claim ON model_track_record(claim_hash);
CREATE INDEX IF NOT EXISTS idx_track_unresolved ON model_track_record(actual_outcome) WHERE actual_outcome IS NULL;
```

#### Table `tier_transitions`

```sql
-- ============================================================================
-- TABLE: TIER_TRANSITIONS (Phase 0.3 — Historique des changements de tier)
-- ============================================================================

CREATE TABLE IF NOT EXISTS tier_transitions (
    transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_hash TEXT NOT NULL,
    old_tier TEXT NOT NULL,
    new_tier TEXT NOT NULL,
    reason TEXT,
    attestation_id INTEGER,
    run_id INTEGER,
    created_at REAL NOT NULL DEFAULT (unixepoch('now'))
);

CREATE INDEX IF NOT EXISTS idx_tier_claim ON tier_transitions(claim_hash);
```

### Placement dans schema.sql

Ajouter ces 6 CREATE TABLE **après** la table `knowledge_gaps` (ligne ~570)
et **avant** la table `canonical_relations` (ligne ~573).

### Vérification B0

```bash
# 1. Vérifier que le schéma est valide
python -c "
import sqlite3
conn = sqlite3.connect(':memory:')
with open('database/schema.sql') as f:
    conn.executescript(f.read())
print('Schema OK')
conn.close()
"

# 2. Vérifier que toutes les tables sont maintenant couvertes
grep -oP '(?:FROM|INTO|UPDATE|JOIN)\s+(\w+)' database/engine.py | awk '{print \$2}' | sort -u | grep -v SET > /tmp/engine_tables.txt
grep -oP 'CREATE TABLE IF NOT EXISTS (\w+)' database/schema.sql | awk '{print \$NF}' | sort > /tmp/schema_tables.txt
MISSING=$(comm -23 /tmp/engine_tables.txt /tmp/schema_tables.txt)
[ -z "$MISSING" ] && echo "All tables covered" || echo "STILL MISSING: $MISSING"

# 3. Tests
pytest tests/ --tb=short 2>&1 | tail -5
```

---

## BLOC 1 — CRASHS RUNTIME

### B1.1 — Import cassé entity_resolver.py [A6-002]

⚡ **VÉRIFIE D'ABORD** :

```bash
grep -n "get_embedding" services/esmm/entity_resolver.py
```

Résultat attendu : `from app.embeddings import get_embedding` (singulier, 2 occurrences)
Le module `app/embeddings.py` exporte `get_embeddings` (pluriel).

**Correction** : Remplacer `get_embedding` par `get_embeddings` aux deux endroits
(lignes ~145 et ~178).

⚠️ MAIS : le rapport audit [A6-001] indique que `app/embeddings.py` est DEPRECATED.
On corrige l'import cassé maintenant, la migration vers le provider layer sera faite
plus tard. Ne pas migrer dans cette phase — trop risqué.

```python
# Ligne ~145
from app.embeddings import get_embeddings
target_embedding = await get_embeddings(concept)

# Ligne ~178
from app.embeddings import get_embeddings
embedding = await get_embeddings(concept)
```

### B1.2 — add_concept() sans embedding_model [A3-001, A3-002]

⚡ **VÉRIFIE D'ABORD** :

```bash
grep -n "add_concept" services/esmm/seed_injector.py
grep -n "add_concept" services/esmm/populate_graph.py
```

Deux fichiers appellent `add_concept()` avec `embedding=embedding_bytes` mais
sans `embedding_model`. Depuis Phase 0.2, `add_concept()` lève `ValueError`
si `embedding` est fourni sans `embedding_model`.

**seed_injector.py** — 2 appels (lignes ~249 et ~412) :

```python
# Appel 1 (~ligne 249) — ajouter embedding_model
await self.db.add_concept(
    concept_id=concept,
    rho_static=0.5,
    embedding=embedding_bytes,
    embedding_model="mxbai-embed-large" if embedding_bytes else None,
    source="seed",
    first_seen_model=None
)

# Appel 2 (~ligne 412) — ajouter embedding_model
await self.db.add_concept(
    concept_id=concept_id,
    rho_static=0.5,
    embedding=embedding_bytes,
    embedding_model="mxbai-embed-large" if embedding_bytes else None,
    source="seed"
)
```

**populate_graph.py** — 1 appel (~ligne 249) :

```python
await self.db.add_concept(
    concept_id=concept,
    rho_static=0.0,
    embedding=embedding_bytes,
    embedding_model="mxbai-embed-large" if embedding_bytes else None,
    source="topics_file",
    first_seen_model=None
)
```

⚠️ **Le modèle d'embedding est hardcodé ici**. C'est acceptable car ces fichiers
utilisent `from app.embeddings import get_embeddings` qui utilise `mxbai-embed-large`
par défaut. Quand la migration vers le provider layer sera faite [A6-001], ce
hardcoding sera remplacé par `provider.get_model_id()`.

⚠️ **Note** : `question_seeder.py` [A3-003 dans le rapport] n'est PAS affecté —
il n'envoie pas d'embedding, donc le `ValueError` ne se déclenche pas.

### B1.3 — record_model_prediction() INSERT sans OR IGNORE [A4-010]

⚡ **VÉRIFIE D'ABORD** :

```bash
grep -n "INSERT INTO model_track_record" database/engine.py
```

Remplacer `INSERT INTO` par `INSERT OR IGNORE INTO` pour éviter un crash sur doublon
(même modèle + même claim_hash en cas de retry).

### Vérification B1

```bash
# Vérifier l'import fixé
python -c "from services.esmm.entity_resolver import EntityResolver; print('OK')"

# Tests complets
pytest tests/ --tb=short 2>&1 | tail -5
```

---

## BLOC 2 — ANNOTATIONS AUDIT DANS LE CODE

### Convention d'annotation

Les annotations suivent un format standardisé qui permet le grep et le suivi :

```python
# AUDIT[A2-005] 🟡 FRAGILE: except:pass masque les erreurs de migration SQL.
# Intentionnel pour ALTER TABLE déjà appliqué. Voir AUDIT_REPORT.md.
```

Format : `# AUDIT[<id>] <emoji> <NIVEAU>: <description courte>`

| Emoji + niveau | Signification |
|---|---|
| `🔴 CRITICAL` | Bug latent, crash en production |
| `🟡 FRAGILE` | Fonctionne mais cassera au prochain changement |
| `🟢 ACCEPTED` | Pattern intentionnel, documenté |

### Règles d'annotation

1. **UNE seule ligne** par annotation. Pas de paragraphe.
2. L'annotation est placée **sur la ligne précédant le code concerné**.
3. Si plusieurs trouvailles touchent le même bloc, une seule annotation avec les IDs groupés.
4. **Ne JAMAIS modifier le code** lors de l'annotation. Commentaires seulement.
5. Les trouvailles 🟢 ACCEPTED sont annotées aussi (elles documentent un choix).
6. Les trouvailles ⚪ INFO ne sont PAS annotées dans le code.

### Fichiers à annoter

Annoter **uniquement les fichiers P0 et P1** du rapport. Pas les tests, pas les P2.

#### engine.py (22 trouvailles)

```bash
grep -n "global _db_instance" database/engine.py
# → Annoter [A1-001]

grep -n "except.*:" database/engine.py | grep -A1 "pass$"
# → Annoter [A2-005] à [A2-009] sur chaque bloc except:pass

grep -n "INSERT INTO model_track_record" database/engine.py
# → Annoter [A4-010] (corrigé en B1.3 mais annoter quand même pour tracking)

grep -n "f\".*SELECT\|f\".*WHERE" database/engine.py
# → Annoter [A4-007] sur les f-strings SQL
```

Exemples concrets d'annotations dans engine.py :

```python
# AUDIT[A1-001] 🔴 CRITICAL: get_db() ignore db_path si instance existe déjà.
# Un 2ème appel avec un path différent retourne silencieusement l'ancienne DB.
async def get_db(db_path: Optional[str] = None) -> ISpaceDB:
```

```python
# AUDIT[A2-005] 🟢 ACCEPTED: ALTER TABLE échoue si colonne existe déjà.
# Intentionnel — migrations idempotentes. Voir engine.py::initialize().
for migration in migrations:
    try:
        await db.execute(migration)
    except Exception:
        pass
```

```python
# AUDIT[A2-006] 🟡 FRAGILE: retourne {} sur exception — indistinguable de "pas de données".
async def get_stats(self) -> Dict[str, Any]:
```

```python
# AUDIT[A4-007] 🟡 FRAGILE: f-string SQL. Valeurs internes (pas d'input user), mais pattern risqué.
cursor = await conn.execute(
    f"SELECT ... WHERE {where_sql} ...",
```

#### pipeline.py (11 trouvailles)

```python
# AUDIT[A2-010,A9-001] 🟡 FRAGILE: erreurs accumulées sans arrêt du pipeline.
# Des triplets partiels pourraient être injectés si l'erreur survient après validation.
errors.append(f"Pipeline error: {e}")
```

```python
# AUDIT[A3-005] 🟡 FRAGILE: store_attestation() attend un dict, pas un objet Pydantic.
# Conversion implicite via model_dump(). Cassera si les clés changent.
await db.store_attestation(attestation.model_dump())
```

#### pool.py (8 trouvailles)

```python
# AUDIT[A2-001] 🔴 CRITICAL: except:pass masque les erreurs de fermeture de connexion.
# Une connexion corrompue ou verrouillée persistera silencieusement.
```

```python
# AUDIT[A1-007] 🟡 FRAGILE: cache sans TTL ni invalidation après mutations DB.
_concept_cache: Dict[str, Any] = {}
```

#### orchestrator.py (7 trouvailles)

```python
# AUDIT[A2-012] 🟡 FRAGILE: timeout de cycle logué mais cycle sauté, run continue.
# Un cycle critique manqué peut fausser le consensus final.
```

#### bridge.py + client.py (12 trouvailles)

```python
# AUDIT[A10-006] 🟡 FRAGILE: string_to_fixed_bytes() tronque silencieusement.
# Un caractère UTF-8 multi-byte peut être coupé → bytes invalides on-chain.
```

```python
# AUDIT[A10-003] 🔴 CRITICAL: Transaction building non implémenté (NotImplementedError).
# Intentionnel pour MVP. Implémentation requise avant Phase 4 devnet.
```

```python
# AUDIT[A10-008] 🟡 FRAGILE: Devnet guard contournable via URL RPC directe.
```

#### seed_injector.py, populate_graph.py, entity_resolver.py

```python
# AUDIT[A3-001] 🔴 CRITICAL: add_concept() sans embedding_model — ValueError garanti.
# CORRIGÉ en Phase 3.2 (B1.2). Annotation conservée pour traçabilité.
```

```python
# AUDIT[A6-002] 🔴 CRITICAL: import get_embedding (singulier) cassé.
# CORRIGÉ en Phase 3.2 (B1.1). Module deprecated, migration provider layer en attente.
```

#### triplet_extractor.py

```python
# AUDIT[A2-014] 🟡 FRAGILE: JSON invalide du LLM → retourne liste vide.
# Perte silencieuse de triplets si le modèle génère du JSON malformé.
```

#### cycle_manager.py

```python
# AUDIT[A2-013] 🟡 FRAGILE: échecs d'extraction individuels accumulés sans arrêt.
```

### Procédure d'annotation

```bash
# 1. Lister les points à annoter par fichier
grep -c "AUDIT\[" database/engine.py        # Cible : ~15 annotations
grep -c "AUDIT\[" services/esmm/pipeline.py  # Cible : ~8 annotations
grep -c "AUDIT\[" database/pool.py           # Cible : ~6 annotations
# etc.

# 2. Après annotation, vérifier que le code n'est pas cassé
python -c "import database.engine; print('OK')"
python -c "import services.esmm.pipeline; print('OK')"

# 3. Tests
pytest tests/ --tb=short 2>&1 | tail -5
```

### Compteur final attendu

```bash
# Total des annotations dans le code
grep -rn "AUDIT\[" --include="*.py" database/ services/ app/ cli/ | wc -l
# Cible : 60-80 annotations (pas besoin de couvrir les 189 trouvailles —
# seulement les 🔴 CRITICAL et 🟡 FRAGILE dans les fichiers P0/P1)
```

---

## VALIDATION FINALE

```bash
# 1. Schema complet
python -c "
import sqlite3
conn = sqlite3.connect(':memory:')
with open('database/schema.sql') as f:
    conn.executescript(f.read())
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print(f'{len(tables)} tables created')
expected = {'attestations', 'concept_embeddings', 'embedding_migrations',
            'metrological_frames', 'model_track_record', 'tier_transitions'}
missing = expected - set(tables)
assert not missing, f'STILL MISSING: {missing}'
print('All 6 new tables present')
conn.close()
"

# 2. Import entity_resolver
python -c "from services.esmm.entity_resolver import EntityResolver; print('Import OK')"

# 3. Tests
pytest tests/ -v --tb=short 2>&1 | tail -10

# 4. Annotations count
echo "Annotations:"
grep -rn "AUDIT\[" --include="*.py" database/ services/ app/ cli/ | wc -l
```

### État cible

| Métrique | Avant | Après |
|----------|-------|-------|
| **PASSED** | 425 | 425+ |
| **FAILED** | 0 | 0 |
| **Tables schema.sql** | 18 | 24 |
| **Crashs runtime connus** | 6+ | 0 |
| **Annotations AUDIT[]** | 0 | 60-80 |

### CHANGELOG.md

```markdown
## [2026-02-11] Phase 3.2 — Consolidation post-audit

- Ajouté 6 tables manquantes dans schema.sql : attestations, concept_embeddings,
  embedding_migrations, metrological_frames, model_track_record, tier_transitions
- Corrigé import cassé entity_resolver.py (get_embedding → get_embeddings)
- Ajouté embedding_model aux appels add_concept() dans seed_injector.py et populate_graph.py
- Sécurisé record_model_prediction() avec INSERT OR IGNORE
- Annoté ~70 points d'audit dans le code (AUDIT[AX-NNN] markers)
- Tests: 425 passed, 0 failed, 10 skipped
```

---

*Phase 3.2 — Corrections post-audit + annotations*
*Basé sur AUDIT_REPORT.md du 11 février 2026*
*Priorité : B0 (schéma) > B1 (crashs) > B2 (annotations)*
