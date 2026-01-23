# Changelog

Toutes les modifications notables de Lyra-ACE sont documentees ici.

Format base sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

---

## [3.0.0] - 2026-01-22

### Resume
ESMM Phase 3 - Protocole complet avec orchestration autonome, detection de lacunes et construction de 0-cochaine.

### Ajoute

#### Orchestrateur ESMM (`services/esmm/orchestrator.py`)
- **ESMMOrchestrator** : Gestion complete des runs avec:
  - Timeouts configurables par cycle (default 5min)
  - Checkpoints automatiques toutes les 5 iterations
  - Gestion d'etat persistante (running/paused/completed/failed)
  - Adaptation dynamique des cycles

#### Gestionnaire de Cycles (`services/esmm/cycle_manager.py`)
- **ExplorationCycleManager** : Execute les 3 types de cycles:
  - DIVERGENT : Exploration large autour de concepts seeds
  - DEBATE : Validation dialectique inter-modeles
  - META : Reflexion sur les connaissances extraites
- Selection dynamique des concepts cibles
- Cache des resultats recents

#### Detection de Lacunes (`services/esmm/gap_detector.py`)
- **KnowledgeGapDetector** : Detecte 3 types de lacunes:
  - `isolated` : Concepts a faible degre (<3 connexions)
  - `unstable` : Triplets a haute variance de consensus
  - `bridge` : Liens inter-domaines manquants
- Seuils dynamiques bases sur les metriques du graphe
- Prioritisation automatique des lacunes

#### Construction 0-Cochaine (`services/esmm/cochain_builder.py`)
- **CochainBuilder** : Construit la signature epistemique 5D:
  - model_agreement : Accord inter-modeles
  - semantic_consistency : Coherence des embeddings
  - structural_centrality : Centralite PageRank-like
  - stability_score : Stabilite temporelle
  - relation_diversity : Entropie Shannon des relations
- Classification en 3 types epistemiques:
  - GENERALIST : Haut degre, relations diverses
  - SPECIALIZED : Domaine specifique, faible degre
  - HYBRID : Mix des deux

#### Analyseur de Couverture (`services/esmm/coverage_analyzer.py`)
- **CoverageAnalyzer** : Metriques de couverture:
  - coverage_score : Score composite [0,1]
  - consensus_density : Densite moyenne de consensus
  - epistemic_diversity : Entropie des types epistemiques
  - structural_stability : Coefficient de clustering moyen
- Seuils configurables pour adaptation dynamique

#### Prompts de Cycles (`services/esmm/cycle_prompts.py`)
- Templates few-shot pour chaque type de cycle
- Exemples positifs et negatifs
- Format de sortie JSON structure

#### Modeles Pydantic Phase 3 (`app/models.py`)
- `ESMMRunRequest` : Configuration de run
- `ESMMRunStatusResponse` : Statut en temps reel
- `ESMMRunResultResponse` : Resultat complet
- `CycleResultResponse` : Resultat d'un cycle
- `KnowledgeGapResponse` : Lacune detectee
- `CochainEntryResponse` : Entree de cochaine
- `CoverageMetricsResponse` : Metriques de couverture
- `ALLOWED_ESMM_MODELS` : Whitelist de modeles autorises

#### Endpoints API Phase 3 (`app/api/graph.py`)
- `POST /graph/esmm-run` : Lancer un run ESMM
- `GET /graph/esmm-run/{id}` : Statut d'un run
- `GET /graph/esmm-run/{id}/result` : Resultat complet
- `POST /graph/esmm-run/{id}/pause` : Mettre en pause
- `POST /graph/esmm-run/{id}/resume` : Reprendre
- `GET /graph/esmm-run/{id}/cycles` : Historique des cycles
- `GET /graph/esmm-run/{id}/gaps` : Lacunes d'un run
- `GET /graph/coverage/metrics` : Metriques globales
- `GET /graph/gaps/active` : Lacunes actives
- `POST /graph/gaps/{id}/address` : Marquer lacune adressee

#### Scripts Batch ESMM
- `esmm.bat` : CLI principal (wrapper Python)
- `run_esmm.bat` : Menu interactif
- `run_esmm_quick.bat` : Run rapide (1,1,1)
- `run_esmm_full.bat` : Run complet (5,3,2)
- `check_esmm_status.bat` : Verification statut
- `esmm_control.bat` : Pause/resume
- `esmm_metrics.bat` : Metriques et lacunes
- `scripts/esmm_cli.py` : CLI Python complet avec mode watch

### Modifie
- `services/esmm/__init__.py` : Version 3.0, exports Phase 3
- `app/models.py` : +200 lignes modeles Phase 3
- `app/api/graph.py` : +430 lignes endpoints Phase 3

### Notes techniques
- Background tasks FastAPI pour runs longs
- Stockage d'etat en memoire (_esmm_runs dict)
- Adaptation dynamique basee sur regles configurables
- Limite 2 modeles simultanes pour gestion VRAM

---

## [2.1.0] - 2026-01-22

### Resume
Securisation et optimisation ESMM: pool SQLite, gestion VRAM, validation stricte des triplets.

### Ajoute

#### Performance SQLite (CRITIQUE)
- **Integration pool de connexions** dans `database/engine.py`:
  - Utilisation de `SQLiteConnectionPool` de `pool.py`
  - 10 connexions poolees avec overflow de 5
  - `PRAGMA busy_timeout=30000` (30s attente sur contention)
  - Fallback pour tests/pre-initialisation

#### Gestion VRAM (ModelRotator)
- **Nouveau fichier** `services/esmm/model_rotator.py`:
  - Rotation sequentielle des modeles LLM
  - `keep_alive=0` pour decharger apres utilisation
  - `preload_model()` et `unload_model()` pour controle explicite
  - `rotate_and_process()` pour requetes multi-modeles
  - `batch_process()` pour batch sur un seul modele

#### Prompts Few-Shot
- **Nouveau fichier** `services/esmm/prompts.py`:
  - 20 relations canoniques validees (`CANONICAL_RELATIONS`)
  - `TRIPLET_EXTRACTION_PROMPT` avec exemples positifs/negatifs
  - `TRIPLET_VALIDATION_PROMPT` pour validation LLM
  - `RELATION_GENERATION_PROMPT` pour lien entre concepts
  - `normalize_relation()` - mapping vers formes canoniques

#### Validation Stricte des Triplets
- **Nouveau fichier** `services/esmm/triplet_validator.py`:
  - Modele Pydantic `ExtractedTriplet` avec validation stricte
  - Detection patterns invalides (pronoms, termes generiques)
  - Parsing JSON robuste (markdown, JSONL, malformed)
  - `TripletValidator` avec validation batch
  - `extract_and_validate()` fonction de commodite

#### Endpoints API
- `GET /graph/cochain/export` - Export JSON/CSV pour visualisation
- `GET /graph/cochain/stats` - Statistiques par type epistemique

### Modifie
- `database/engine.py`:
  - Import de `SQLiteConnectionPool, get_pool, close_pool`
  - Ajout attribut `_pool` dans `ISpaceDB`
  - Methode `connection()` utilise le pool
  - `close_db()` ferme aussi le pool
- `services/esmm/__init__.py`:
  - Export des nouveaux modules (ModelRotator, prompts, validators)
  - Version 1.1

### Corrige
- Echecs immediats sur contention SQLite (busy_timeout manquant)
- Saturation VRAM sur requetes multi-modeles paralleles

---

## [2.0.0] - 2026-01-21

### Resume
Evolution majeure vers le protocole ESMM (Exploration Semantique Multi-Modeles).

### Ajoute

#### Base de donnees (schema v2)
- **8 nouvelles tables** pour ESMM:
  - `concept_aliases` - Canonicalisation semantique
  - `pending_kappa_recalc` - Queue de calcul kappa differe
  - `canonical_relations` - 20 types de relations normalisees
  - `esmm_runs` - Executions du protocole
  - `exploration_cycles` - Historique des cycles
  - `triplet_extractions` - Triplets extraits
  - `cochain_entries` - 0-Cochaine de consensus
  - `knowledge_gaps` - Lacunes identifiees

- **6 vues utilitaires**:
  - `v_top_concepts`, `v_concept_with_aliases`, `v_active_sessions`
  - `v_esmm_run_stats`, `v_pending_triplets`, `v_active_gaps`

- **4 triggers automatiques**:
  - Mise a jour du degre sur insertion/suppression de relation
  - Queue kappa sur modification de poids
  - Mise a jour session sur nouvel evenement

#### Engine (database/engine.py)
- **~30 nouvelles methodes** pour ESMM:
  - Canonicalisation: `resolve_concept`, `add_alias`, `get_concept_with_aliases`
  - Kappa differe: `queue_kappa_recalc`, `get_pending_kappa_batch`, `mark_kappa_recalc_done/failed`
  - Relations: `get_canonical_relation`, `get_all_canonical_relations`
  - ESMM Runs: `create_esmm_run`, `update_esmm_run_status`, `finalize_esmm_run`
  - ESMM Cycles: `log_exploration_cycle`, `update_cycle_extraction`
  - ESMM Triplets: `store_triplet_extraction`, `mark_triplet_injected`, `skip_triplet_injection`
  - ESMM Cochain: `upsert_cochain_entry`, `get_cochain_entry`, `get_cochain_by_type`, `export_cochain_for_viz`
  - ESMM Gaps: `add_knowledge_gap`, `get_active_gaps`, `mark_gap_addressed`

- **Methodes helper**:
  - `add_concept` - Creation de concepts
  - `get_concepts_with_embeddings` - Pour recherche de similarite
  - `get_relation` - Recuperation d'une relation
  - `update_edge_kappa` - Mise a jour kappa
  - `log_kappa_history` - Historique des calculs

#### Services
- **EntityResolver** (`services/entity_resolver.py`):
  - Resolution semantique via embeddings
  - Seuils: SIMILARITY_THRESHOLD=0.92, REVIEW_THRESHOLD=0.85
  - Fusion automatique des doublons

- **RelationNormalizer** (`services/relation_normalizer.py`):
  - Normalisation vers 20 relations canoniques
  - Gestion des inverses et symetrie
  - Cache en memoire

- **KappaWorker** (`services/kappa_worker.py`):
  - Calcul differe de kappa Ollivier
  - Mode batch et mode continu
  - Integration avec KappaCalculator

#### Documentation
- `docs/fr/DATABASE.md` - Schema v2 complet
- `docs/fr/ESMM_PROTOCOL.md` - Protocole ESMM
- `docs/fr/CHANGELOG.md` - Ce fichier

### Modifie
- `database/schema.sql` - Remplace par schema v2 (18 tables)
- `services/__init__.py` - Export des nouveaux services

### Notes de migration
- **Base de donnees**: Creation a neuf requise (pas de migration)
- **Compatibilite**: API existante preservee

---

## [1.0.0] - 2025-11-01

### Resume
Version initiale de Lyra Clean.

### Ajoute
- Moteur SQLite async avec WAL mode
- Gestion des trajectoires Bezier
- 4 profils par defaut (balanced, creative, safe, analytical)
- API FastAPI complete
- Interface web (Lyra Lite UI)
- Conscience adaptative Phase 2
- Memoire semantique Phase 3
- Graph Delta Management

---

## Liens

- [Documentation](../README.md)
- [Guide Developpeur](DEVELOPER_GUIDE.md)
- [Reference API](API_REFERENCE.md)
