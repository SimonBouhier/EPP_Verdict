# CLAUDE.md — EPP_Verdict

> **Ce fichier est FIGÉ. Tu ne le modifies JAMAIS. Tu le relis à chaque début de session.**

---

## 1. IDENTITÉ

**Nom** : EPP_Verdict (Epistemic Proof Program)
**En une phrase** : Des LLMs débattent en local, un consensus signé est ancré on-chain sur Solana.
**Base héritée** : Fork de Lyra ACE. Lyra est la base générique — EPP_Verdict est le produit spécifique.

Ce n'est PAS : un agent de trading, un chatbot, un oracle de prix, un prediction market.

---

## 2. ARCHITECTURE — VUE STATIQUE

```
COUCHE 1 — Interface
    │  epp_cli.py           → CLI : epp ask, submit, query, frame, graph stats
    │  main.py              → Point d'entrée FastAPI
    │  models.py            → Modèles Pydantic (requêtes/réponses)
    │
COUCHE 2 — Pipeline E2E + Moteur ESMM (off-chain, Python)
    │  pipeline.py          → Point d'entrée unique CLI→DB (run_pipeline)
    │  orchestrator.py      → Pilote les runs ESMM
    │  cycle_manager.py     → Exécute les cycles (DIVERGENT, DEBATE, META)
    │  cycle_prompts.py     → Prompts par type de cycle
    │  triplet_extractor.py → Pipeline extraction multi-modèles
    │  triplet_validator.py → Validation Pydantic des triplets
    │  consensus_engine.py  → Vote multi-modèles, scores SHA-256
    │  cochain_builder.py   → Signature 5D (0-cochaine épistémique)
    │  gap_detector.py      → Détection de lacunes dans le graphe
    │  coverage_analyzer.py → Métriques Shannon entropy
    │  attestation.py       → EpistemicAttestation + crystallize()
    │  triplet_adapter.py   → ConsensusTriplet → dict pipeline
    │  question_seeder.py   → Seed du graphe depuis la question
    │  post_crystallization.py → Hook post-attestation (Brier, tiers)
    │
COUCHE 3 — Providers (consommables, interchangeables)
    │  base.py              → ABC ModelProvider + EmbeddingProvider
    │  registry.py          → ProviderRegistry (get/register/clear)
    │  multi_provider_rotator.py → Rotation provider-agnostique
    │  ollama.py            → Adaptateur Ollama
    │  openai_compat.py     → Adaptateur OpenAI-compatible
    │  anthropic.py         → Adaptateur Anthropic
    │  ollama_embeddings.py → Embeddings Ollama
    │  mock_provider.py     → Mock réaliste pour tests sans LLM
    │
COUCHE 4 — Graphe de connaissances (RAG attesté)
    │  engine.py            → ISpaceDB (~100 méthodes, 3100+ lignes)
    │  pool.py              → Pool connexions + cache + concurrency limiter
    │  graph.py             → Endpoints FastAPI mutations graphe
    │  graph_delta.py       → Mutations auditables + KappaCalculator
    │  schema.sql           → Schéma SQL (25 tables)
    │  entity_resolver.py   → Résolution d'entités par embeddings
    │  relation_normalizer.py → Canonicalisation relations
    │  relation_generator.py  → Génération de relations par similarité
    │  config_loader.py     → Singleton config.yaml
    │
COUCHE 5 — Conscience & Adaptation (héritage Lyra)
    │  metrics.py           → Monitoring passif
    │  adaptation.py        → Auto-ajustement actif
    │  memory.py            → Mémoire sémantique
    │
COUCHE 6 — Solana (MVP devnet)
    │  programs/epp/        → Programme Anchor/Rust (submit, challenge, ping)
    │  bridge.py            → Sérialisation Python → Solana (float↔u16, UTF-8)
    │  client.py            → EppSolanaClient (submit attestation)
    │  metrological_frame.py → Cadres de mesure Pydantic
    │  config.py            → SolanaConfig + SolanaCluster (devnet only)
    │
SUPPORT
    config.yaml             → Configuration centralisée
    injector.py             → Injection contexte sémantique
    session_storage.py      → Gestion sessions
    prompts.py              → Prompts d'extraction
    seed_injector.py        → Injection de graines sémantiques
    populate_graph.py       → Population initiale du graphe
    hydrate_embeddings.py   → Hydratation des vecteurs
    run_logger.py           → Journalisation des runs ESMM
```

---

## 3. FLUX DE DONNÉES PRINCIPAL

```
Question → pipeline.run_pipeline()
    → question_seeder (seed graphe)
    → Orchestrator → Cycles (DIVERGENT → DEBATE → META)
        → Triplet Extraction → Consensus Engine
    → triplet_adapter (ConsensusTriplet → dict)
    → crystallize() → EpistemicAttestation (claim + score + sig_5d)
    → store_attestation() → DB
    → inject_to_graph() → GraphDelta
    → post_crystallization_hook() → Brier + tier transitions
    → [Phase 4] Ancrage on-chain Solana (PDA)
```

---

## 4. RÈGLES DE CODE

- **Python 3.11+**, async/await, type hints obligatoires
- **Imports** : relatifs dans le package (`from .module import X`), absolus pour dépendances externes
- **Patterns obligatoires** :
  - Toute interaction LLM passe par l'interface `ModelProvider` (ABC dans `base.py`)
  - Tout triplet passe par `TripletValidator` avant injection
  - Tout consensus passe par `ConsensusEngine`
  - Toute mutation du graphe passe par `GraphDelta`
- **Nommage** : snake_case partout, classes en PascalCase, constantes en UPPER_SNAKE
- **Pas de code mort** : si tu supprimes une feature, supprime le code. Pas de commentaires `# TODO: remove`
- **Tests** : tout nouveau composant a au moins un test unitaire
- **Résultat final** : toute session se termine par `pytest tests/ --tb=short` complet

---

## 5. RÈGLES ANTI-DETTE IA

Ces règles viennent de bugs réels trouvés sur EPP_Verdict. Elles sont non-négociables.

### 5.1 — Pas d'INSERT brut

Tout `INSERT INTO` dans une table avec UNIQUE ou PRIMARY KEY utilise
`INSERT OR IGNORE` ou `INSERT OR REPLACE`. Jamais `INSERT INTO` seul.

**Pourquoi** : Un doublon crash silencieusement ou bruyamment selon le contexte.
On l'a trouvé dans `record_model_prediction()` et dans le rollback de `DELETE_EDGE`.

### 5.2 — Pas d'except:pass sans justification

Tout bloc `except` qui avale l'erreur DOIT avoir un commentaire expliquant POURQUOI.
Format : `except Exception:  # OK: <raison>` ou `# AUDIT[AX-NNN]`.

Un `except: pass` nu est une dette technique immédiate. L'erreur avalée sera
invisible au debugging et se manifestera loin de la cause.

### 5.3 — Propagation obligatoire des signatures

Quand tu modifies la signature d'une méthode publique (ajout/suppression/renommage
de paramètre), tu DOIS :

1. Lister tous les appelants : `grep -rn "method_name" --include="*.py" database/ services/ cli/ app/ tests/`
2. Mettre à jour CHAQUE appelant
3. Vérifier avec `pytest tests/ --tb=short`

**Pourquoi** : `add_concept()` a été modifié en Phase 0.2 (ajout `embedding_model`),
mais 3 appelants n'ont été corrigés qu'en Phase 3.2 — 4 phases plus tard.

### 5.4 — Cohérence schéma ↔ code

Quand tu ajoutes une méthode qui INSERT/SELECT/UPDATE dans une table ou colonne,
tu DOIS vérifier que la table ET la colonne existent dans `schema.sql`.

```bash
# Vérification : tables dans le code vs schéma
grep -oP "(?:FROM|INTO|UPDATE|JOIN)\s+(\w+)" database/engine.py | awk '{print $2}' | sort -u
grep -oP "CREATE TABLE IF NOT EXISTS (\w+)" database/schema.sql | awk '{print $NF}' | sort
```

Si une table ou colonne manque → l'ajouter dans `schema.sql` DANS LE MÊME COMMIT.

### 5.5 — Singletons vérifiés

Tout singleton avec `if _instance is None` DOIT vérifier que les paramètres
n'ont pas changé entre les appels. Si les paramètres changent, recréer l'instance
ou logger un warning explicite.

**Pourquoi** : `get_pool("db_a.db")` puis `get_pool("db_b.db")` retournait
silencieusement le pool de `db_a.db`. Trouvé en Phase 3.1.

### 5.6 — Tests substantifs

Un test DOIT avoir au moins une assertion qui vérifie une VALEUR, pas juste
l'existence. `assert result is not None` seul est insuffisant.

Bon : `assert result.consensus_score >= 0.4`
Mauvais : `assert result is not None`

### 5.7 — Configuration effective

Si tu ajoutes une clé dans `config.yaml`, tu DOIS l'utiliser dans le code
via `get_value()`. Si tu hardcodes une valeur, ne l'ajoute PAS à config.yaml.
Les clés décoratives (jamais lues) sont de la dette.

---

## 6. RÈGLES DE DOCUMENTATION — CRITIQUES

1. **Tu ne crées JAMAIS un nouveau fichier .md** sauf dans `docs/adr/`. Les fichiers de documentation sont :
   - `CLAUDE.md` (celui-ci — LECTURE SEULE, tu n'y touches pas)
   - `ARCHITECTURE.md` (état vivant du code — tu le mets à jour quand tu modifies la structure)
   - `CHANGELOG.md` (journal factuel — une entrée par modification significative)
   - `EPP_PLAN_MVP.md` (plan stratégique — LECTURE SEULE, référence uniquement)
   - `CONTROLS.md` (protocole de recette — LECTURE SEULE, utilisé par le reviewer)
   - `AUDIT_REPORT.md` (rapport d'audit — LECTURE SEULE, résultat de l'audit Phase 3.2)
   - `docs/adr/ADR-NNN.md` (Architecture Decision Records — 10 lignes max par fichier)

2. **Quand tu modifies ARCHITECTURE.md** :
   - Mets à jour UNIQUEMENT les sections affectées par ton changement
   - Maximum 10 lignes de diff par mise à jour
   - Documente ce qui EXISTE, jamais ce qui est prévu

3. **Quand tu modifies CHANGELOG.md** :
   - Format : `## [YYYY-MM-DD] Titre court` puis 2-3 lignes factuelles
   - Pas de prose, pas d'explication de design, juste les faits

4. **Tu ne documentes PAS** : la roadmap, les idées futures, les alternatives considérées, les justifications de design longues. Ça n'a pas sa place dans le code.

---

## 7. MÉTHODE DE TRAVAIL

1. **Avant de coder** : relis ce fichier ET `ARCHITECTURE.md`
2. **Avant d'utiliser une librairie/framework** : consulte Context7 (`@context7`) pour la documentation à jour (Anchor, FastAPI, Pydantic, httpx, Solana SDK, etc.)
3. **Quand tu ne sais pas** : demande plutôt que d'inventer
4. **Quand tu modifies un fichier existant** : vérifie que tu ne casses pas les imports des fichiers qui en dépendent
5. **Commits** : messages courts, impératifs, en anglais. Ex: `Add ModelProvider ABC`, `Fix rollback_deltas fallback`
6. **Quand tu déclares avoir mis à jour la doc** : montre le diff ou les lignes modifiées. Ne pas juste dire "c'est à jour".
7. **Avant de modifier un encodage, un format de données, ou un schéma** : consulte les ADR dans `docs/adr/`. Si ta modification contredit un ADR actif, signale-le.

### 7.1 — Vérification post-modification (obligatoire)

Après TOUTE modification de code, avant de déclarer la tâche terminée :

```bash
# 1. Tests complets (pas juste le fichier modifié)
pytest tests/ --tb=short

# 2. Si une signature a changé : vérifier les appelants
grep -rn "nom_de_la_methode" --include="*.py" database/ services/ cli/ app/ tests/

# 3. Si une table/colonne a été ajoutée : vérifier le schéma
python -c "
import sqlite3
conn = sqlite3.connect(':memory:')
with open('database/schema.sql') as f: conn.executescript(f.read())
print('Schema OK')
"
```

### 7.2 — Annotations AUDIT dans le code

Le code contient des marqueurs `# AUDIT[AX-NNN]` issus du rapport d'audit Phase 3.2.

| Marqueur | Signification |
|----------|---------------|
| `🔴 CRITICAL` | Ne pas modifier ce code sans comprendre le risque documenté |
| `🟡 FRAGILE` | Modification possible mais vérifier les effets de bord |
| `🟢 ACCEPTED` | Pattern intentionnel, ne pas "corriger" |

Si tu corriges un point AUDIT, mets à jour l'annotation :
`# AUDIT[AX-NNN] 🔴→✅ FIXED Phase X.Y: <description courte>`

Ne supprime jamais une annotation AUDIT — la traçabilité a de la valeur.

---

## 8. GLOSSAIRE

| Terme | Définition |
|-------|------------|
| **EPP** | Epistemic Proof Program — programme Solana stockant les attestations |
| **ESMM** | Exploration Sémantique Multi-Modèles — protocole de consensus multi-LLM |
| **0-cochaine** | Signature épistémique 5D : accord, cohérence, centralité, stabilité, diversité |
| **Attestation** | Claim + consensus_score + signature_5d + models + frame, ancrable on-chain |
| **Référentiel métrologique** | Spécification versionnée de ce qu'on mesure et comment |
| **Source anchor** | Référence vérifiable externe brisant la circularité du consensus LLM |
| **PDA** | Program Derived Address — compte Solana dérivé du programme EPP |
| **ModelProvider** | Interface abstraite (ABC) que tout modèle doit implémenter |
| **GraphDelta** | Mécanisme de mutation auditable du graphe de connaissances |
| **Pipeline** | Chemin unique Question→Orchestrator→Crystallize→DB→Graph (`pipeline.py`) |
| **Cristallisation** | Transformation consensus → attestation sérialisable + hash SHA-256 |
| **Confidence Tier** | Niveau de confiance d'une attestation : sandbox → proposition → validated → verified |
| **Brier Score** | Mesure de calibration des prédictions par modèle (`model_track_record`) |
| **AUDIT[AX-NNN]** | Marqueur d'audit dans le code, référence au rapport `AUDIT_REPORT.md` |

---

## 9. ÉTAT DU PROJET (Phases complétées)

| Phase | Date | Contenu | Tests |
|-------|------|---------|-------|
| **0.1** | 04/02 | ModelProvider ABC, OllamaProvider, ProviderRegistry, MultiProviderRotator | 55 |
| **0.2** | 05/02 | Embedding versioning, concept_embeddings, migration CLI | 45 |
| **0.3** | 05/02 | EpistemicAttestation, crystallize(), RunLogger, 4 tiers de confiance | 65 |
| **1** | 06/02 | Programme Anchor (submit/challenge/ping), bridge Python↔Solana, CLI complet | 83 |
| **2** | 08/02 | Confidence tiers multi-critères, Brier scoring, pipeline.py | 61 |
| **3** | 10/02 | Pipeline E2E, post_crystallization, question_seeder, triplet_adapter | 76 |
| **3.1** | 10/02 | pytest-asyncio, tier migration, pool isolation, rollback fix | +49 récupérés |
| **3.2** | 11/02 | Audit interne (51 annotations), 3 crashs runtime corrigés, schéma complété | 425 total |

**État courant** : 425 passed, 0 failed, 10 skipped.

### Prochaines priorités (ordre strict)

1. **Scénarios de démo** — 5 scénarios fonctionnels (J7 du plan MVP)
2. **Consolidation** — Résorber les 🟡 FRAGILE identifiés par l'audit (progressif)
3. **Solana devnet réel** — Transaction building (actuellement `NotImplementedError`)
4. **Track record** — 100+ attestations avec Brier scoring fonctionnel

Ne saute pas d'étape. Chaque priorité dépend de la précédente.
