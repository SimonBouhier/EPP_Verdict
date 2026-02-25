# ARCHITECTURE.md — EPP_Verdict

> **Fichier vivant.** Mis à jour par Claude Code uniquement quand la structure du code change.
> Ne documente que ce qui EXISTE. Pas de spéculations.

**Dernière mise à jour** : 2026-02-25
**Base** : Fork Lyra ACE → EPP_Verdict

---

## État actuel des composants

### Pipeline ESMM (fonctionnel, hérité de Lyra)

| Fichier | Rôle | État |
|---------|------|------|
| `orchestrator.py` | Pilote les runs ESMM dual-mode (EXPLORE/VERIFY). `ClaimNature` enum (EPISTEMIC/DETERMINISTIC). `ESMMRunConfig` : +`claim_nature` + `source_anchor_spec` + `__post_init__` guard. `execute_cycles()` : short-circuit immédiat si `claim_nature=DETERMINISTIC`. | ✅ Fonctionnel |
| `cycle_manager.py` | Exécution des 6 types de cycles. `_query_models_isolated()` (isolation CHALLENGE). `_extract_verdicts_from_responses()` : majority vote `claim_type` sur réponses modèles + injection triplet `claim_type` dans `raw_model_triplets` (propagation via triplet-as-channel). | ✅ Fonctionnel |
| `cycle_prompts.py` | Prompts dual-mode : DIVERGENT/DEBATE/META (EXPLORE) + ASSESS/CHALLENGE/ADJUDICATE (VERIFY), anglais. ASSESS : STEP 1 classifie `claim_type` (empirical/definitional/normative/speculative) avant STEP 2 verdict. | ✅ Fonctionnel |
| `triplet_extractor.py` | Pipeline complet extraction → validation → consensus. `_parse_verdict_response()` : extrait `verdict`, `confidence`, `evidence`, `claim_type` (normalisation + fallback `"empirical"`). | ✅ Fonctionnel |
| `verdict_encoder.py` | Encodage verdict → triplets (claim→verdict→SUPPORTED/REFUTED, +evidence, +reasoning). Réutilise la pipeline de cristallisation. | ✅ Fonctionnel |
| `triplet_validator.py` | Validation Pydantic, détection patterns invalides | ✅ Fonctionnel |
| `relation_vocabulary.py` | Source unique de vérité : 11 groupes de relations synonymes (superset CE 10 + FM 6). Exports : `build_synonym_map()`, `get_canonical()`, `are_relations_compatible()`. Flag `use_legacy_relation_groups` pour déploiement progressif. | ✅ Fonctionnel |
| `consensus_engine.py` | Vote 2 passes (hash exact + semantic merge), normalize_triplet(), ambiguity detection, ConsensusResult (vote_entropy, semantic_dispersion). Relations via relation_vocabulary.py (flag-conditioned). | ✅ Fonctionnel |
| `response_deduplicator.py` | Déduplication sémantique des réponses (embedding cosine) | ✅ Fonctionnel |
| `cochain_builder.py` | Signature 5D normalisée, typage épistémique | ✅ Fonctionnel |
| `gap_detector.py` | Concepts isolés, triplets instables, ponts manquants | ✅ Fonctionnel |
| `coverage_analyzer.py` | Shannon entropy, métriques de couverture | ✅ Fonctionnel |

**Dual-Mode ESMM** (2026-02-20) :

Le pipeline ESMM supporte deux modes d'opération, auto-détectés par `classify_input()` :

| Mode | Séquence de cycles | Usage |
|------|-------------------|-------|
| **EXPLORE** (défaut) | DIVERGENT → DEBATE → META | Exploration sémantique ouverte |
| **VERIFY** | ASSESS → CHALLENGE → ADJUDICATE | Vérification factuelle d'une claim |

VERIFY impose :

- `cycles_per_type = {1, 1, 1}` (chaque cycle query tous les modèles)
- Pas de convergence gaps ni d'adaptation (séquence fixe)
- Isolation épistémique : ASSESS = modèles isolés, CHALLENGE = rotation circulaire (modèle[i] voit uniquement verdict de modèle[(i+1)%N]), ADJUDICATE = synthèse (tous verdicts visibles)
- Verdict triplets routés via `compute_consensus()` pour agreement_ratio réel
- `consensus_meta.verify` enrichi post-cristallisation : `final_verdict`, `verdict_confidence`, `model_verdicts`, `evidence_corpus` (triplets sub-consensus, cap 20)
- Classification `claim_type` (empirical/definitional/normative/speculative) : majority vote sur réponses ASSESS, propagé via triplet-as-channel, pénalité décidabilité appliquée dans pipeline (VERDICT_PENALTIES × CLAIM_TYPE_PENALTIES)

### Provider Layer (Phase 0.1 — fonctionnel)

| Fichier | Rôle | État |
|---------|------|------|
| `services/providers/base.py` | ABC ModelProvider + EmbeddingProvider | ✅ Fonctionnel |
| `services/providers/ollama.py` | Adaptateur Ollama avec VRAM management | ✅ Fonctionnel |
| `services/providers/openai_compat.py` | Adaptateur OpenAI-compatible | ✅ Créé, non branché |
| `services/providers/anthropic.py` | Adaptateur Anthropic | ✅ Créé, non branché |
| `services/providers/ollama_embeddings.py` | Adaptateur embeddings Ollama | ✅ Fonctionnel |
| `services/providers/registry.py` | Registre centralisé des providers | ✅ Fonctionnel |
| `services/esmm/multi_provider_rotator.py` | Rotation multi-provider | ✅ Fonctionnel |

### Cristallisation (Phase 0.3 — fonctionnel)

Système de cristallisation des attestations épistémiques, produisant des objets sérialisables avec hash SHA-256 déterministe.

| Fichier | Rôle | État |
|---------|------|------|
| `services/esmm/attestation.py` | Modèle EpistemicAttestation (+ consensus_meta ADR-010), crystallize(), compute_claim_hash(), RevalidationInput. `models_consulted ge=0` (attestations déterministes). `epistemic_type` : +`"deterministic"`. Guard `crystallize()` : `consensus_method=deterministic_source_v1` requiert `source_anchor_meta`. | ✅ Fonctionnel |
| `services/esmm/run_logger.py` | Logs structurés du pipeline (PhaseEvent, RunLogger) | ✅ Fonctionnel |
| Table `attestations` | Stockage attestations cristallisées (table 20), consensus_meta TEXT (ADR-010) | ✅ Fonctionnel |

**Méthodes ISpaceDB ajoutées** :

- `store_attestation()` — Stocke une attestation cristallisée
- `get_attestation_by_hash()` — Récupère par claim_hash SHA-256
- `get_attestations_by_subject()` — Filtre par sujet + min_consensus
- `get_attestation_history()` — Historique de revalidation d'un claim

### End-to-End Pipeline (Phase 3 — fonctionnel)

Flux complet : CLI -> pipeline -> orchestrator -> crystallization -> DB -> graph.
Le pipeline est le SEUL pont entre l'orchestrateur et la cristallisation.

| Fichier | Rôle | État |
|---------|------|------|
| `services/esmm/pipeline.py` | Pipeline complet : orchestrator -> adapt -> crystallize -> DB -> graph. `_run_deterministic_pipeline()` : chemin court-circuit ADR-012 (fetch source → hash → crystallize → store snapshot + attestation). Constantes `VERDICT_PENALTIES` + `CLAIM_TYPE_PENALTIES` — pénalité décidabilité VERIFY. | ✅ Fonctionnel |
| `services/config_loader.py` | Chargement centralisé config.yaml (singleton) | ✅ Fonctionnel |
| `services/esmm/triplet_adapter.py` | Conversion ConsensusTriplet -> dict pipeline (D4) | ✅ Fonctionnel |
| `services/esmm/question_seeder.py` | Seed graph vide depuis question (D7). `InputType` enum + `classify_input()` auto-détection EXPLORE/VERIFY. | ✅ Fonctionnel |
| `services/esmm/post_crystallization.py` | Hook track record + tier transitions + diversity bonus (D8, R2) | ✅ Fonctionnel |
| `services/providers/mock_provider.py` | MockProvider + make_synthetic_triplets() (D10) | ✅ Fonctionnel |
| `services/providers/base.py` | + infer_architecture_family() pour mesure diversité | ✅ Fonctionnel |

**Méthodes ISpaceDB ajoutées (Phase 3)** :

- `get_latest_attestation()` — Dernière attestation (par timestamp)
- `get_attestation_count()` — Compteur total attestations
- `update_attestation_submission_status()` — Mise à jour status submission

**Confidence Tiers (Méthode scientifique)** :

| Tier | Seuil | Conditions |
|------|-------|-----------|
| `sandbox` | < 0.40 | Aucune |
| `proposition` | >= 0.40 | + >= 2 modèles |
| `validated` | >= 0.70 | + >= 3 modèles + >= 2 familles archi |
| `verified` | >= 0.85 | + source_anchor OU validation_count >= 3 |

**Tables SQL ajoutées (20-22)** :

- `metrological_frames` — Référentiels métrologiques persistés (seedés automatiquement)
- `model_track_record` — Brier scoring par modèle (prédiction vs résolution)
- `tier_transitions` — Audit des promotions/rétrogradations de confiance
- Vue `v_model_brier_scores` — Brier score agrégé par modèle (90j glissant)

**Méthodes ISpaceDB ajoutées** :

- `update_attestation_solana_tx()` — Mise à jour post-ancrage on-chain
- `store_frame()` / `get_frame()` / `list_frames()` — CRUD frames
- `record_model_prediction()` / `resolve_prediction()` / `get_model_brier_score()` — Track record
- `log_tier_transition()` — Audit des changements de tier

### Embedding Versioning (Phase 0.2 — fonctionnel)

Système de stockage multi-version des embeddings permettant le changement de modèle sans perte de vecteurs.

| Table/Fichier | Rôle | État |
|---------------|------|------|
| `concept_embeddings` | Table multi-version (concept_id, model_id, dimension, embedding) | ✅ Fonctionnel |
| `embedding_migrations` | Traçabilité migrations (from_model → to_model, status, stats) | ✅ Fonctionnel |
| `tools/migrate_embeddings.py` | CLI migration progressive (dry-run, finalize, rollback) | ✅ Fonctionnel |
| `config.yaml::embeddings` | Config active_model, fallback_reembed, similarity_min_score | ✅ Fonctionnel |

**Méthodes ISpaceDB ajoutées** :

- `store_concept_embedding()` / `get_concept_embedding()` — CRUD versioned embeddings
- `get_concepts_with_embeddings_for_model()` — Requête par model_id (pas de mélange dimensions)
- `get_concepts_needing_migration()` — Concepts sans embedding pour un modèle cible
- `create/update/get_embedding_migration()` — Gestion entrées migration
- `finalize_embedding_migration()` — Copie finale vers concepts.embedding
- `rollback_embedding_migration()` — Suppression embeddings du modèle cible

### Interface modèles (legacy)

| Fichier | Rôle | État |
|---------|------|------|
| `llm_client.py` | Client async Ollama (httpx, retry, pooling) | ⚠️ Couplé Ollama |
| `model_rotator.py` | Rotation VRAM-safe, keep_alive=0 | ⚠️ Hérité Lyra, remplacé par multi_provider_rotator.py |
| `multimodel.py` | Endpoints FastAPI multi-modèles | ⚠️ Couplé Ollama |

> `embeddings.py` supprimé en Phase 4.4 (remplacé par `EmbeddingProvider` dans `base.py`).

### Graphe de connaissances (fonctionnel)

| Fichier | Rôle | État |
|---------|------|------|
| `engine.py` | ISpaceDB — ~100 méthodes, WAL mode, O(log N) indexes | ✅ Fonctionnel |
| `pool.py` | Pool 10 connexions, 30s busy_timeout, cache LRU | ✅ Fonctionnel |
| `graph.py` | Opérations graphe sémantique (PPMI, voisinage) | ✅ Fonctionnel |
| `graph_delta.py` | GraphDelta + KappaCalculator (Ollivier + Jaccard) | ✅ Fonctionnel |
| `schema.sql` | 24 tables, 8 vues SQLite | ✅ Fonctionnel |
| `entity_resolver.py` | Résolution d'entités | ✅ Fonctionnel |
| `relation_normalizer.py` | 20 relations canoniques | ✅ Fonctionnel |
| `relation_generator.py` | Génération de relations | ✅ Fonctionnel |

### Conscience & Physique (héritage Lyra, usage TBD dans EPP)

| Fichier | Rôle | État |
|---------|------|------|
| `metrics.py` | Monitoring passif (cohérence, tension, fit) | ✅ Hérité |
| `adaptation.py` | Auto-ajustement paramètres | ✅ Hérité |
| `memory.py` | Mémoire sémantique (cosine + decay temporel) | ✅ Hérité |
| `bezier.py` | Courbes Bézier cubiques (τ_c, ρ, δ_r, κ) | ✅ Hérité |

### Application & Support

| Fichier | Rôle | État |
|---------|------|------|
| `main.py` | FastAPI entry point, lifecycle, CORS | ✅ Fonctionnel |
| `models.py` | Modèles Pydantic (requêtes/réponses) | ✅ Fonctionnel |
| `config.yaml` | Configuration centralisée (purgé Phase 4.4 : 12 clés effectives) | ✅ Fonctionnel |
| `injector.py` | Injection contexte sémantique (TF-IDF + PPMI) | ✅ Fonctionnel |
| `sessions.py` | Gestion sessions | ✅ Fonctionnel |
| `session_storage.py` | Export/import sessions JSON | ✅ Fonctionnel |
| `prompts.py` | Prompts extraction triplets (few-shot, 20 relations) | ✅ Fonctionnel |
| `seed_injector.py` | Injection graines sémantiques | ✅ Fonctionnel |
| `populate_graph.py` | Population initiale graphe | ✅ Fonctionnel |
| `hydrate_embeddings.py` | Hydratation vecteurs | ✅ Fonctionnel |

### Couche Solana (Phase 1 — MVP)

Programme ID : `98Fc2oL2cKsTDGYi3GifggzkQkEQSRn2oTgg8HsaVa3C`

| Fichier | Rôle | État |
|---------|------|------|
| `services/solana/config.py` | Config cluster, devnet guard, DEFAULT_PROGRAM_ID, keypair path | ✅ Fonctionnel |
| `services/solana/metrological_frame.py` | MetrologicalFrame Pydantic, compute_frame_hash() SHA-256. 5 frames : `blockchain_tps_v1.0`, `general_knowledge_v1.0`, `compliance_sanctions_v1.0`, `carbon_credits_vcs_v1.0`, `rwa_identity_v1.0`. | ✅ Fonctionnel |
| `services/solana/bridge.py` | Sérialisation Python <-> Anchor (float↔u16, string↔bytes). `CONFIDENCE_TIER_MAP` : bijection stricte 4 clés ↔ 4 arms Rust (sandbox/proposition/validated/verified). | ✅ Fonctionnel |
| `services/solana/client.py` | Transaction builder, PDA derivation, mock mode, account deser (Phase 4.6). CLAIM_HASH_OFFSET=41, SUBJECT_OFFSET=73 vérifiés vs state.rs layout. | ✅ Fonctionnel |
| `programs/epp/src/lib.rs` | Instructions Anchor : submit_attestation, ping | ✅ Build OK (221 KB .so) |
| `programs/epp/src/state.rs` | EpistemicAttestation account (462 bytes) | ✅ Build OK |
| `programs/epp/src/errors.rs` | EppError enum (11 variantes) | ✅ Build OK |
| `programs/epp/src/constants.rs` | Constantes on-chain (MAX_SUBJECT_LEN, SCORE_SCALE, seeds) | ✅ Build OK |
| `cli/epp_cli.py` | CLI : ask, submit (--devnet), query, frame list/show, graph stats, models stats, verify-rwa (ADR-012) | ✅ Fonctionnel |

**Décisions architecturales** :

- PDA seeds : `[b"attestation", submitter.key(), &claim_hash]`
- Float encoding : `[0.0, 1.0]` → `u16 [0, 10000]` (précision 4 décimales)
- Strings : zero-padded UTF-8 → `[u8; 64]` / `[u8; 128]`
- Devnet-only guard : MAINNET intentionnellement absent de `SolanaCluster`

**Prérequis** : Solana CLI 3.0+ / Anchor 0.32+ / Rust 1.70+ (WSL sur Windows).

### Architecture Decision Records (Phase 3.3+)

10 ADR actifs dans `docs/adr/` :

| ADR | Sujet | Statut |
|-----|-------|--------|
| ADR-001 | Encodage float→u16 (bridge, tolérance 1e-4) | Actif |
| ADR-002 | Stratégie INSERT (OR IGNORE vs OR REPLACE) | Actif |
| ADR-003 | Gestion des singletons (get_pool, get_db) | Actif |
| ADR-004 | session_storage INSERT OR IGNORE | Actif |
| ADR-005 | Confidence tiers multi-critères (pas de seuil simple) | Actif |
| ADR-006 | Claim hash déterministe SHA-256 | Actif |
| ADR-007 | Append-only pour events et graph_deltas | Actif |
| ADR-008 | Stratégie auth submitter Solana (keypair, devnet guard) | Actif |
| ADR-009 | Language Neutrality in ESMM Protocol | Actif |
| ADR-010 | Traçabilité méthodologique du consensus (consensus_meta) | Actif |
| ADR-011 | Réconciliation lexicale par empreinte sémantique (Semantic Fingerprinting) | Actif (v2) |

### Phase 4 — Corrections systématiques (2026-02-15)

Corrections appliquées en 8 sous-phases (4.0-4.7). 62 tests ajoutés (425→487).

**4.0 Fondations** : Isolation 16 singletons (setup+teardown dans conftest.py).
**4.1 Crashs** : triplet_extractor ON CONFLICT, imports dépréciés migrés, session_storage INSERT OR IGNORE.
**4.2 Corruption** : graph_delta INSERT ON CONFLICT DO UPDATE, pool.py except:pass → logger.warning.
**4.3 Durcissement** : get_db() warning si db_path change, close_entity_resolver/relation_normalizer ajoutés.
**4.4 Nettoyage** : config.yaml purgé (35→12 clés), embeddings.py supprimé, semantic_memory supprimée du schéma.
**4.5 Sécurité** : XML boundary delimiters, _sanitize_concept(), infer_architecture_family() durci, input validation.
**4.6 Solana** : Transaction building, account deserialization, PDA validation, queries memcmp, mock mode déterministe.
**4.7 Peaufinage** : providers corrigés, tier sync Rust↔Python, property-based tests, print()→logger (§5.2).

### Phase R2 — Consensus robuste & intégrité (2026-02-15)

Renforcement du consensus multi-modèles : pondération par Brier score, normalisation des triplets, diversité, déduplication sémantique, commit-reveal.

**R-2.1.1 Weighted Consensus** : `compute_consensus()` accepte `model_weights: Dict[str, float]` (propagé via 7 signatures : pipeline → orchestrator → cycle_manager → triplet_extractor → consensus_engine). Poids basés sur Brier score via `get_all_model_brier_scores()`.

**R-2.1.2 Normalize Triplet** : `normalize_triplet()` dans consensus_engine.py — lowercase + strip + collapse whitespace + synonym mapping (10 groupes de relations, abréviations entités, synonymes mot-à-mot). Appelé dans `_hash_triplet()` avant SHA-256.

**R-2.2.1 Diversity Bonus** : Bonus appliqué APRÈS `crystallize()` (respect ADR-005). Champs enrichis : `adjusted_consensus_score`, `diversity_bonus_factor`. Le `confidence_tier` reste immuable.

**R-2.2.2 Response Deduplication** : `ResponseDeduplicator` dans response_deduplicator.py — déduplication par embedding cosine similarity avant consensus.

**R-2.2.3 Commit-Reveal** : Table `commit_reveal` (hash par modèle/phase). Colonnes `commit_hash`, `commit_verified` dans `attestations`. Vérification post-reveal via `verify_and_update_commit()`.

**Corrections live run** : `_hash_triplet()` / `compute_consensus()` gèrent triplets dict et objets (fix getattr sur dict). CYCLE_TIMEOUTS uniformes 60s. META retry capped à 3. `ESMMRunConfig` dataclass pour contrôle externe (cycles, timeouts, adaptive).

**Tables SQL ajoutées (R2)** :

- `commit_reveal` — Hash commits par modèle/phase (table 24)
- Colonnes `attestations` : `adjusted_consensus_score`, `diversity_bonus_factor`, `commit_reveal_verified`

**Méthodes ISpaceDB ajoutées (R2)** :

- `store_commit()` — Stocke un commit hash (modèle + phase)
- `get_commit()` — Récupère un commit par run_id + model_id + phase
- `verify_and_update_commit()` — Vérifie hash et met à jour `verified`

### Sources RWA / Bifurcation déterministe (ADR-012 — 2026-02-25)

Nouveau chemin déterministe parallèle au pipeline ESMM. L'appelant déclare `claim_nature=DETERMINISTIC` (Axiome 3 — pas d'inférence automatique). Le pipeline court-circuite les cycles LLM, interroge la source autoritaire, hash la réponse brute en SHA-256 (`source_anchor` on-chain), stocke le snapshot complet en SQLite, cristallise une attestation `epistemic_type="deterministic"`.

| Fichier | Rôle | État |
|---------|------|------|
| `services/esmm/source_anchor_builder.py` | `SourceAnchorSpec`, `SourceAnchorResult`, `build_source_anchor()`, `_canonical_hash()` (SHA-256 JSON canonique sorted-keys) | ✅ Fonctionnel |
| `services/rwa/adapters/base.py` | ABC `SourceAdapter` : `fetch(query)`, `normalize(raw)`, `get_source_version(raw)` | ✅ Fonctionnel |
| `services/rwa/adapters/opensanctions.py` | POST `/match` yente (0 credential, testable en local) | ✅ Fonctionnel |
| `services/rwa/adapters/ofac.py` | POST OFAC SDN — `OFAC_API_KEY` env var | ✅ Fonctionnel |
| `services/rwa/adapters/eu_cfsp.py` | GET sanctions.network EU CFSP (données ouvertes) | ✅ Fonctionnel |
| `services/rwa/adapters/verra_vcs.py` | GET Verra Registry L1 (serial/project_id — public) | ✅ Fonctionnel |
| `services/rwa/adapters/__init__.py` | Registre `_REGISTRY` + `get_adapter()` + `register_adapter()` | ✅ Fonctionnel |

**Frames RWA** (dans `metrological_frame.py`) :

| Frame | Domaine | `esmm_bypass` |
|-------|---------|--------------|
| `compliance_sanctions_v1.0` | regulatory_compliance / sanctions_status | `True` |
| `carbon_credits_vcs_v1.0` | environmental_assets / carbon_credit_validity | `True` (L2 désactivé — ADR-012 Q3) |
| `rwa_identity_v1.0` | identity_compliance / entity_sanctions_composite | `True` (ESMM on ambiguity désactivé par défaut) |

**Table SQL ajoutée (table 25)** :

- `source_anchor_snapshots` — snapshot raw_response off-chain, `source_anchor` SHA-256 → on-chain. Contrainte UNIQUE `(source_id, query_hash, source_version)`. Index sur `source_anchor` et `(source_id, fetched_at DESC)`.

**Méthodes ISpaceDB ajoutées (ADR-012)** :

- `store_source_anchor_snapshot()` — INSERT OR IGNORE snapshot
- `get_snapshot_by_anchor()` — Lookup par SHA-256 source_anchor
- `is_snapshot_fresh()` — TTL check par (source_id, query_hash, max_age_hours)

**`config.yaml`** : section `rwa.sources` — 4 sources (enabled/ttl_hours). Credentials via env vars uniquement.
- `update_attestation_commit_verified()` — Met à jour `commit_verified` sur attestation
- `get_all_model_brier_scores()` — Tous les Brier scores pour pondération
- `update_attestation_diversity_bonus()` — Met à jour bonus diversité post-cristallisation

**Tests ajoutés** : 25 tests (489→514). Property-based (hypothesis), normalize_triplet, commit-reveal, weighted consensus, diversity bonus, response deduplicator, dashboard models.

### Phase 4.8 — Neutralité linguistique ESMM (2026-02-15)

Prompts traduits en anglais + consensus sémantique deux passes + préservation ambiguïté.

**4.8.1 Prompts anglais** : 3 SYSTEM_PROMPTS + 20 templates + 4 extraction prompts traduits en anglais. Directive "MUST be in English" dans chaque system prompt et TRIPLET_EXTRACTION_PROMPT. `normalize_relation()` et `CANONICAL_RELATIONS` inchangés (déjà anglais).

**4.8.2 Semantic merge** : `compute_consensus()` async, accepte `embedding_provider` optionnel. Pass 1 = hash exact (existant). Pass 2 = clustering cosine > 0.85 via `_semantic_merge()`. `ConsensusTriplet` étendu : `variations: List[Tuple[str,str,str]]`, `ambiguity_detected: bool`. Représentant canonique : plus de votes, puis texte le plus court. Tie → `ambiguity_detected=True`.

**Annotation COMMUNITY_DECISION_REQUIRED** dans consensus_engine.py, post_crystallization.py, pipeline.py — le traitement des triplets CONTESTED est délibérément ouvert (ADR-009).

**Tests ajoutés** : 9 tests (514→523). Prompts anglais (5), semantic merge/ambiguity/no-false-merge/backward-compat (4).

---

## Dépendances critiques

```
orchestrator.py
  ├── cycle_manager.py
  │     ├── cycle_prompts.py
  │     └── multi_provider_rotator.py  ← provider-agnostique
  ├── gap_detector.py
  ├── cochain_builder.py
  └── coverage_analyzer.py

triplet_extractor.py
  ├── multi_provider_rotator.py  ← provider-agnostique
  ├── triplet_validator.py
  ├── consensus_engine.py  ← normalize_triplet(), model_weights
  │     └── relation_vocabulary.py  ← source unique de vérité relations
  ├── response_deduplicator.py  ← embedding cosine dedup
  ├── verdict_encoder.py  ← verdict → triplets (VERIFY mode)
  └── prompts.py

fingerprint_match.py
  └── relation_vocabulary.py  ← source unique de vérité relations

engine.py (ISpaceDB)
  ├── pool.py
  ├── graph_delta.py
  └── schema.sql

cli/epp_cli.py
  ├── services/esmm/pipeline.py  ← pont ESMM → cristallisation
  │     ├── services/esmm/attestation.py
  │     └── services/esmm/run_logger.py
  ├── services/solana/config.py
  ├── services/solana/metrological_frame.py
  ├── services/solana/bridge.py
  └── services/solana/client.py
        └── programs/epp/ (Anchor, Rust)
```

---

## Stack technique

- **Python** 3.11+, async/await
- **FastAPI** + uvicorn
- **SQLite** WAL mode via aiosqlite
- **httpx** pour appels HTTP async
- **Pydantic** v2 pour validation
- **tenacity** pour retry
- **Ollama** comme provider LLM local (à abstraire)
- **Solana CLI** 3.0+ / **Anchor** 0.32+ / **Rust** 1.70+ (couche on-chain)
- **Click** pour CLI EPP
