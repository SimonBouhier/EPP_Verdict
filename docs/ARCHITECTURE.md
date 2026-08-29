# ARCHITECTURE.md — EPP_Verdict

> **Fichier vivant.** Mis à jour par Claude Code uniquement quand la structure du code change.
> Ne documente que ce qui EXISTE. Pas de spéculations.

**Dernière mise à jour** : 2026-08-12
**Base** : Fork Lyra ACE → EPP_Verdict

---

## État actuel des composants

### Pipeline ESMM (fonctionnel, hérité de Lyra)

| Fichier | Rôle | État |
|---------|------|------|
| `orchestrator.py` | Pilote les runs ESMM dual-mode (EXPLORE/VERIFY). `ClaimNature` enum (EPISTEMIC/DETERMINISTIC). `ESMMRunConfig` : +`claim_nature` + `source_anchor_spec` + `__post_init__` guard + `anchor_context: str = ""` (ADR-018). `execute_cycles()` : short-circuit immédiat si `claim_nature=DETERMINISTIC` ; injecte `cycle_context["anchor_context"]` si non vide (VERIFY mode). | ✅ Fonctionnel |
| `cycle_manager.py` | Exécution des 6 types de cycles. `_query_models_isolated()` (isolation CHALLENGE). `_extract_verdicts_from_responses()` : majority vote `claim_type` sur réponses modèles + injection triplet `claim_type` dans `raw_model_triplets` (propagation via triplet-as-channel). **ADR-018** : `_query_models(anchor_ctx: str = "")` et `_query_models_isolated(anchor_ctx: str = "")` — concatènent `anchor_ctx` au system prompt si non vide. `execute_cycle()` extrait `anchor_ctx` depuis `context["anchor_context"]`. | ✅ Fonctionnel |
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
| `services/esmm/attestation.py` | Modèle EpistemicAttestation (+ consensus_meta ADR-010), crystallize(), compute_claim_hash(), RevalidationInput. `models_consulted ge=0` (attestations déterministes). `epistemic_type` : +`"deterministic"`. Guard `crystallize()` : `consensus_method=deterministic_source_v1` requiert `source_anchor_meta`. Projection on-chain V2 (8 strings Python → 3 catégories u8 : `empirical=0`, `deterministic=1`, `assessed=2`) effectuée dans `services/solana/bridge.py::EPISTEMIC_TYPE_MAP` — ADR-019. | ✅ Fonctionnel |
| `services/esmm/run_logger.py` | Logs structurés du pipeline (PhaseEvent, RunLogger) | ✅ Fonctionnel |
| Table `attestations` | Stockage attestations cristallisées (table 20), consensus_meta TEXT (ADR-010) | ✅ Fonctionnel |

**Méthodes ISpaceDB ajoutées** :

- `store_attestation()` — Stocke une attestation cristallisée
- `get_attestation_by_hash()` — Récupère par claim_hash SHA-256
- `get_attestations_by_subject()` — Filtre par sujet + min_consensus
- `get_attestation_history()` — Historique de revalidation d'un claim

### Métrologie et gouvernance Git (ADR-021 — fonctionnel)

La métrologie appartient au noyau EPP. La promotion est une décision externe
portée par GitHub ; elle ne modifie ni le contenu de l'attestation ni son tier
épistémique.

| Fichier | Rôle | État |
|---------|------|------|
| `services/metrology.py` | Modèles `MetrologicalFrame` / `FrameGovernance`, hash canonique et registre des 7 frames prédéfinis. Aucun import Solana. | ✅ Fonctionnel |
| `services/governance/proposal.py` | Enveloppe `AttestationProposal` : frame hash obligatoire, preuves adressées par SHA-256, hash de proposition déterministe, rejet des altérations. `decision` est limité à `proposed`; le merge porte l'acceptation. | ✅ Fonctionnel |
| `governance/proposals/` | Surface canonique des artefacts JSON proposés à la revue Git. Les corpus bruts en sont exclus. | ✅ Créé |
| `scripts/validate_proposals.py` | Validation hors réseau des artefacts et vérification byte-for-byte des preuves locales ; les références HTTPS sont déclarées mais jamais téléchargées en CI. | ✅ Fonctionnel |
| `services/solana/metrological_frame.py` | Shim d'import historique réexportant `services.metrology` sans dupliquer la logique. | ✅ Compatible |
| `.github/workflows/python_governance_ci.yml` | Suite Python + validation des propositions, sans secrets, permissions `contents: read`, destinée à devenir un check de merge obligatoire. | ✅ Créé |

### End-to-End Pipeline (Phase 3 — fonctionnel)

Flux complet : CLI -> pipeline -> orchestrator -> crystallization -> DB -> graph.
Le pipeline est le SEUL pont entre l'orchestrateur et la cristallisation.

| Fichier | Rôle | État |
|---------|------|------|
| `services/esmm/pipeline.py` | Pipeline complet : orchestrator -> adapt -> crystallize -> DB -> graph. `_run_deterministic_pipeline()` : chemin court-circuit ADR-012 (fetch source → hash → `crystallize(question=question)` → store snapshot + attestation). Constantes `VERDICT_PENALTIES` + `CLAIM_TYPE_PENALTIES` — pénalité décidabilité VERIFY. **ADR-018** : `_lookup_existing_anchors(question, db)` — lookup ancres déterministes par question (filtre `deterministic_source_v1`, lit `diagnostics.result`). `_format_anchor_context(anchors)` — formate bloc `[VERIFIED DATA...]`. Bloc flywheel dans `run_pipeline()` : guard `is_verify`, `flywheel_enabled` initialisé hors `try`, injection `anchor_context` dans `_extract_triplets_from_question()`, traçabilité `consensus_meta.methodology.flywheel`. `run_pipeline()` signature : pas de paramètre `extra_system_context` (retiré 2026-04-11, hors scope). | ✅ Fonctionnel |
| `services/config_loader.py` | Chargement centralisé config.yaml (singleton) | ✅ Fonctionnel |
| `services/esmm/triplet_adapter.py` | Conversion ConsensusTriplet -> dict pipeline (D4) | ✅ Fonctionnel |
| `services/esmm/question_seeder.py` | Seed graph vide depuis question (D7). `InputType` enum + `classify_input()` auto-détection EXPLORE/VERIFY. | ✅ Fonctionnel |
| `services/esmm/post_crystallization.py` | Hook track record + tier transitions + diversity bonus (D8, R2) | ✅ Fonctionnel |
| `services/providers/mock_provider.py` | MockProvider + make_synthetic_triplets() (D10) | ✅ Fonctionnel |
| `services/providers/base.py` | + infer_architecture_family() pour mesure diversité | ✅ Fonctionnel |

**Méthodes ISpaceDB ajoutées (Phase 3)** :

- `get_latest_attestation()` — Dernière attestation (par `ORDER BY timestamp DESC`). Désérialise `consensus_meta` JSON→dict.
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
| `schema.sql` | 25 tables, 8 vues SQLite | ✅ Fonctionnel |
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
| `config.yaml` | Configuration centralisée. Purge Phase 4.4 suivie d'ajouts (`sources`, `flywheel`, `audit`, `geopolitical`) — 11 sections top-level actuelles. | ✅ Fonctionnel |
| `injector.py` | Injection contexte sémantique (TF-IDF + PPMI) | ✅ Fonctionnel |
| `sessions.py` | Gestion sessions | ✅ Fonctionnel |
| `session_storage.py` | Export/import sessions JSON | ✅ Fonctionnel |
| `prompts.py` | Prompts extraction triplets (few-shot, 20 relations) | ✅ Fonctionnel |
| `seed_injector.py` | Injection graines sémantiques | ✅ Fonctionnel |
| `populate_graph.py` | Population initiale graphe | ✅ Fonctionnel |
| `hydrate_embeddings.py` | Hydratation vecteurs | ✅ Fonctionnel |

### Couche Solana (Phase 1 — publication optionnelle)

Programme ID : `9QtybfyZQFhra1D6S3NtD6jD4z2Z3wcYmf4YXETq8bSD` (aligné `declare_id!`, keypair `target/deploy/epp-keypair.json`, et `Anchor.toml` localnet + devnet après fix `86539e7`)

| Fichier | Rôle | État |
|---------|------|------|
| `services/solana/config.py` | Config cluster, devnet guard, DEFAULT_PROGRAM_ID, keypair path | ✅ Fonctionnel |
| `services/solana/metrological_frame.py` | Shim de compatibilité vers le noyau `services/metrology.py`. | ✅ Compatible |
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

**Test on-chain ADR-019** : `tests/epp_enum_v2_guard.ts` exerce `require!(epistemic_type <= 2)` (lib.rs:69). Protocole C6 Gatekeeper (double run GREEN/RED) — commit `86539e7`. Fix `Anchor.toml [programs.localnet]` aligné sur l'ID canonique (même commit) — corrige `DeclaredProgramIdMismatch` qui bloquait `anchor test`.

### Architecture Decision Records (Phase 3.3+)

21 ADR actifs dans `docs/adr/` :

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
| ADR-012 | Intégration sources RWA — bifurcation déterministe/épistémique | Actif |
| ADR-013 | Cache-hit épistémique avant ESMM | Actif |
| ADR-014 | Moteur d'audit épistémique de smart contracts (§2.1 : migration services/rwa/ → services/sources/) | Actif |
| ADR-015 | Le Grand Découplage — architecture tripartite Kernel/Adapters/Domains | Différé (post-hackathon) |
| ADR-016 | Oracle géopolitique ACLED — ancrage données de conflit | Actif |
| ADR-017 | Réseau de Clusters Épistémiques — architecture multi-opérateurs | Proposé |
| ADR-018 | Flywheel Épistémique — injection ancres déterministes dans passes LLM | Actif |
| ADR-019 | Projection Enum V2 — taxonomie on-chain minimale pour vérification formelle (Lean 4-ready) | Actif |
| ADR-020 | Couche de spécification formelle Lean 4 (anciennement « Architecture Dual-Trust » — périmètre clarifié 2026-05-02). Inventaire post-audit P1–P4 + correction P1 cumulativity (cf. `docs/audit/`) : 6 théorèmes substantifs (4 `iff` sur tiers + 2 cumulativité de stratification) + 7 regression tests + 2 contrats au niveau du type (B5 fermé par `Option SourceAnchor`) + 1 corollaire historique + 1 lemme définitionnel. Pont spec/code humain non-mécanisé (TD-005). | Actif |
| ADR-021 | GitHub comme frontière de gouvernance et de promotion ; Solana devient un adaptateur de publication optionnel. | Actif |

### ADR-018 — Flywheel Épistémique (2026-03-13)

Les attestations déterministes existantes (Wikidata, ACLED) sont injectées comme contexte vérifié dans le system prompt des LLMs lors des passes VERIFY, fermant la boucle entre les deux chemins.

**Fix B4 (bloquant)** : `_run_deterministic_pipeline()` appelait `crystallize()` sans `question=question` → colonne NULL → flywheel mort. Corrigé : `crystallize(..., question=question)`.

**Flux flywheel** (VERIFY mode uniquement, ADR-018 §4) :

```text
run_pipeline() [is_verify=True]
  └─ _lookup_existing_anchors(question, db)   # filtre deterministic_source_v1
       └─ get_attestations_by_question()       # ADR-013
  └─ _format_anchor_context(anchors)          # bloc [VERIFIED DATA...]
  └─ _extract_triplets_from_question(anchor_context=...)
       └─ esmm_config.anchor_context = ...
            └─ execute_cycles() → cycle_context["anchor_context"]
                 └─ _query_models(anchor_ctx=...)
                      └─ system_prompt += "\n\n" + anchor_ctx
```

**Traçabilité** : `consensus_meta.methodology.flywheel = {enabled, anchors_found, sources_injected}`.

**Config** : `flywheel.enabled` (config.yaml, défaut `true`). Si `false`, lookup skippé, `anchors_found=0`.

**Méthodes ISpaceDB utilisées** : `get_attestations_by_question()` (ADR-013, lookup par `question` exacte).

**Tests** (`tests/test_adr018_flywheel.py`) : 8 tests — lookup no/with anchors, filtre épistémique, format vide/données, traçabilité meta, flywheel disabled, garde VERIFY-only.

**Attestation SELECT alignment (2026-04-11)** : les 4 méthodes de lecture (`get_attestation_by_hash`, `get_attestations_by_subject`, `get_attestations_by_question`, `get_attestation_history`) sont alignées sur 29 colonnes avec `consensus_meta` en dernière position (index 28). `_row_to_attestation_dict()` désérialise `consensus_meta` via `json.loads`. `get_latest_attestation()` utilise `ORDER BY timestamp` (corrigé depuis `created_at`).

### Vérification formelle (Lean 4 — ADR-019, ADR-020 + audit P1–P4)

Couche Lean 4 auditée ligne par ligne en quatre phases (P1 hygiène, P2 nettoyage tautologies, P3 correction structurelle, P4 alignement Python ↔ Lean). Rapports détaillés sous `docs/audit/SESSION_AUDIT_FORMAL_*`.

**Compte honnête post-audit** : **6 théorèmes substantifs** (4 `iff` complets sur les tiers + 2 cumulativité de stratification, P1 2026-05-01) + **7 regression tests** (5 tier + 2 hash) + **2 contrats au niveau du type** (typage strict `Option SourceAnchor`, B5 fermé) + 1 corollaire historique + 1 lemme définitionnel = **17 énoncés Lean compilés** (`lake build` retourne **16 jobs**, `assignTier` prend désormais 4 paramètres incluant `validationCount` pour aligner sur Python).

| Fichier | Rôle | Énoncés | État |
|---------|------|---------|------|
| `Formal/Formal/Basic.lean` | Types de base : `EpistemicType`, `ConfidenceTier`, `Score`, `SourceAnchor` (non-construible avec hash vide — ajouté P3.A), `Attestation` (10 champs métier dont `source_anchor : Option SourceAnchor`) | — | ✅ Actif |
| `Formal/Formal/TierBoundary.lean` | INV-4 : caractérisation `iff` complète des 4 tiers + 2 théorèmes de cumulativité (`verified ⇒ validated`, `validated ⇒ proposition`) qui ferment le biais B4 (asymétrie soundness/complétude) **et** corrigent le bug de stratification pré-P1 (`assignTier 8500 1 true = verified` était possible avec 1 modèle + anchor, violant l'ordre cumulatif suggéré par les noms). 4ème paramètre `validationCount` aligné sur Python. Ancien théorème directionnel conservé en corollaire. | **6** substantifs + 1 corollaire | ✅ Prouvés (P3.B + P1) |
| `Formal/Formal/ClaimHash.lean` | INV-2 : `claim_hash_purity` — regression test sur la projection `toClaimCore`. Doublons textuels (`claim_hash_timestamp_independent`, `claim_hash_submitter_independent`) supprimés en P1.2 (commentaire de traçabilité préservé). | **1** regression | ✅ Prouvé |
| `Formal/Formal/SourceAnchor.lean` | INV-6 : `wellFormed` adapté à `Option.isSome` (P3.A) ; les deux théorèmes restent tautologiques *en preuve* mais l'invariant qu'ils expriment est désormais porté par le système de types Lean (B5 fermé par construction). | **2** type-level | ✅ Prouvés |
| `Formal/Formal/RedTests.lean` | 6 regression tests : 4 tier red/green + 2 hash red (hypothèses fantômes B7 retirées en P2.6) | **6** regression | ✅ Exercés |
| `Formal/Formal/Sanity.lean` | Tests `#eval` interactifs (renommé d'`Eval.lean` en P1) | — | ✅ Actif |
| `Formal/Main.lean` | Point d'entrée exécutable ; `import Formal` charge toute la lib | — | ✅ Actif |
| `.github/workflows/lean_action_ci.yml` | CI `lake build` à chaque push — 16 jobs après audit P1–P4 | — | ✅ Actif |

**Suppressions de l'audit** :
- `Formal/Basic.lean` (racine, orphelin résiduel `lake init`) — supprimé P1.
- `Formal/Formal/Encoding.lean` — 4 énoncés tautologiques sans `Float` ni roundtrip réel (B1 + B3 *« mauvais étiquetage »*) supprimés P2 ; le bornage des scores reste garanti par la struct `Score` elle-même (`val ≤ 10000` au niveau du type).
- `_RedTestVacuity.lean` — fichier RED temporaire P3.B (preuve observable du biais B4) supprimé après extension `iff`.

**Pont Python ↔ Lean** :
- 26 unitaires + property-based tests dans `tests/test_lean_conformance.py` et `tests/test_lean_conformance_property.py`. Run profond `HYPOTHESIS_MAX_EXAMPLES=10000` couvre ~160 000 inputs aléatoires sans contre-exemple.
- **Alignement P4.2 (2026-05-01)** : `services/esmm/attestation.py::EpistemicAttestation.source_anchor` porte un `pattern=r"^[0-9a-f]{64}$"` Pydantic aligné sur le contrat Lean `SourceAnchor` (longueur 64, charset hex minuscule). Classe `TestInv6SourceAnchorContractEnforced` (5 tests) vérifie le rejet de hash invalides côté Python.

**Méthodologie** : Protocole C6 double falsification (RED → GREEN → restauration) appliqué à chaque nouvel invariant. Toute hypothèse non consommée (B7) ou doublon textuel (cas `claim_hash_*_independent`) signalé et corrigé.

**Limites assumées** (ADR-020 §5) : les preuves portent sur le modèle Lean abstrait ; le lien modèle ↔ code Python est testé empiriquement (suite conformance), le lien modèle ↔ code Rust (programme Anchor) reste non couvert. Levée future possible via Aeneas/hax/Certora ou via property-based testing croisé Python ↔ Lean (chantier P4.1, cf. `TECH_DEBT.md::TD-005`).

Commits : `1d703fd` (init) ; `20ab6f7` (fix TierBoundary + câblage Main) ; `0fea8b3` (INV-2 ClaimHash) ; audit P1–P4 (2026-04-30 → 2026-05-01).

### Dashboard UI (`ui/`) — Sprint hackathon Colosseum (2026-04-23)

Sous-projet TypeScript/React indépendant déployé sur `https://epp-verdict.vercel.app`. Lit les benchmark JSONs locaux + le manifest on-chain et rend une vue navigable des attestations, du flywheel split, et des liens Solana Explorer.

| Fichier | Rôle | État |
|---------|------|------|
| `ui/package.json` | Vite 6 + React 19 + TS strict + Tailwind v4 + TanStack Query + Zod + React Router v7 + Biome + Vitest. Engines `node >= 20`. | ✅ Fonctionnel |
| `ui/vercel.json` | Framework Vite, build/install commands, output `dist`. | ✅ Fonctionnel |
| `ui/scripts/copy-data.mjs` | Hook predev/prebuild local : refresh `ui/public/data/` depuis `demos/benchmark_runs/` + `data/devnet_pushed.json`. No-op gracieux quand sources absentes (cas Vercel monorepo) — préserve les fichiers commités au lieu de les écraser. | ✅ Fonctionnel |
| `ui/public/data/` | **Commité** (24 runs JSONs + manifest.json + devnet_pushed.json, ~700 KB). Build input pour Vercel qui ne peut pas accéder à `../demos/`. À refactorer post-hackathon. | ✅ Fonctionnel (workaround) |
| `ui/src/domain/` | Types + Zod schemas (frontière de validation). `claim.ts` (Verdict + ClaimType + ClaimVerdict), `run.ts` (ScenarioRun avec `raw` préservé pour features scénario-spécifiques), `manifest.json` (RunManifest), `onchain.ts` (OnChainAttestation + OnChainManifest + sentinel `EMPTY_ONCHAIN_MANIFEST`). | ✅ Fonctionnel |
| `ui/src/data/loader.ts` | Boundary I/O unique : `loadManifest()`, `loadRun(filename)`, `loadOnChainManifest()` — fetch + Zod parse + adapter dispatch. Fallback gracieux 404 sur le manifest on-chain. | ✅ Fonctionnel |
| `ui/src/data/adapters/` | 5 adapters scénario : `jiang`, `flywheel-v2`, `flywheel-baseline`, `scenario6` (3 variantes : `scenario_6_1_edge_cases` + `scenario_6_2_qualifier_sensitivity` + `scenario_6_2b_qualifier_sensitivity_big_models`), `deterministic-sources` (mappe `status` → `Verdict`, gère claims `skipped: true`). Pattern : raw JSON → `ScenarioRun` commun + `raw` préservé. Registre `ADAPTERS` + `detectAdapter()` raise explicite si scenario inconnu. | ✅ Fonctionnel |
| `ui/src/config/families.ts` | Taxonomie déclarative : 5 familles (Flywheel, Sources déterministes, Géopolitique, Edge cases, Pipeline). Ajouter une famille = éditer 1 fichier, aucun autre code à toucher. | ✅ Fonctionnel |
| `ui/src/services/families.ts` | `filterRunsByFamily()`, `listFamiliesWithCounts()`, `countUnclassified()`. Sentinels `ALL_FAMILY_ID` + `UNCLASSIFIED_FAMILY_ID`. | ✅ Fonctionnel |
| `ui/src/services/onchain.ts` | `buildOnChainIndex()` produit `Map<question, OnChainAttestation>` indexé par texte de question (clé de matching avec les benchmark JSONs). `lookupOnChain()` accesseur null-safe. | ✅ Fonctionnel |
| `ui/src/features/family-tabs/` | Tabs URL-driven (`?family=X`), comptes par famille, soulignement cyan sur tab actif. | ✅ Fonctionnel |
| `ui/src/features/claim-viewer/` | `ClaimList` + `ClaimRow`. Reçoit `onChainIndex` optionnel via prop drilling depuis la route ; chaque row appelle `lookupOnChain` et passe l'attestation au `OnChainBadge`. | ✅ Fonctionnel |
| `ui/src/features/flywheel-split/` | Vue dédiée à route `/flywheel?run=X`. `parseFlywheelClaims()` extrait `baseline_*` / `delta` / `flywheel_*` du `raw`. Layout BASELINE → FLYWHEEL avec deltas cyan, badges NEW gold pour claims sans baseline. Summary strip (total / migrated / improved ratio / avg Δ). Reçoit aussi `onChainIndex` pour badges inline. | ✅ Fonctionnel |
| `ui/src/ui/OnChainBadge.tsx` | Chip cyan ⛓ avec lien Solana Explorer (`target="_blank"`, `stopPropagation` sur click). Tooltip exposant tx + frame + slot. | ✅ Fonctionnel |
| `ui/src/ui/VerdictBadge.tsx` + `Card.tsx` | Primitives shadcn-style (cva + tailwind-merge). Couleurs verdicts : emerald/amber/zinc/rose. | ✅ Fonctionnel |
| `ui/src/routes/home.tsx` | Liste des runs filtrée par famille (`?family=X`), card par run avec lien vers `/claims?run=X`. | ✅ Fonctionnel |
| `ui/src/routes/claim-viewer.tsx` | Vue générique d'un run, charge l'index on-chain via TanStack Query, transmet à `ClaimList`. CTA "Flywheel split" si `scenario_flywheel_v2`. | ✅ Fonctionnel |
| `ui/src/routes/flywheel.tsx` | Route dédiée flywheel split — refuse les autres scénarios via Card amber d'erreur. | ✅ Fonctionnel |
| `ui/src/routes/onchain.tsx` | Liste des attestations on-chain devnet avec summary card (cluster, program ID, submitter, pushed/failed) + liste cliquable vers Solana Explorer. Empty state avec commande exacte si manifest absent. | ✅ Fonctionnel |
| `ui/src/index.css` | Palette signature lighthouse (Tailwind v4 `@theme inline`) : navy nuit + cyan beam + gold lighthouse, gradient radial subtil. Dark-first. | ✅ Fonctionnel |
| `ui/src/App.tsx` | Layout : header avec dot cyan glow + nav (Runs / On-chain), main router, footer. | ✅ Fonctionnel |

**Architecture en 4 cercles concentriques** : `domain/` (intérieur, types purs) ← `data/` (loader + adapters) ← `services/` (transformations pures) ← `features/` (UI par cas d'usage) ← `routes/` (pages composées). Règle : un cercle ne peut importer **que** depuis l'intérieur. Remplacer la source de données (JSON local → Solana RPC → API) ne touche que `data/`.

**Workflow ajout de scénario** : (1) Python pipeline génère JSON dans `demos/benchmark_runs/` ; (2) `npm run prebuild` (ou `npm run dev`) refresh `ui/public/data/` ; (3) `git add ui/public/data/` ; (4) commit + push ; (5) Vercel auto-déploie.

**Caveat documenté** : le commit de `ui/public/data/` est une concession au workflow Vercel monorepo (Root Directory = `ui/` ne donne pas accès à `../demos/` même avec "Include source files outside of the Root Directory" activé), **pas une bonne pratique générale**. Voir CHANGELOG entrée 2026-04-23 Phase D pour les options de refactoring post-hackathon.

### Push on-chain devnet (`scripts/push_to_devnet.py`)

Script standalone qui complète le plumbing CLI (`cli/epp_cli.py:submit()` qui ne faisait que mettre à jour le statut DB sans appel à `client.submit_attestation()`).

| Élément | Description |
|---------|-------------|
| Source | `data/epp_devnet.db` (57 attestations) + `data/epp_audit_devnet.db` (20 attestations). Rehydration via `EpistemicAttestation.model_validate_json(portable_json)` — aucun re-run ni synthèse de triplets. |
| Sélection par défaut | 8 `general_knowledge_v1.0` + 4 `smartcontract_audit_v1.0`, top consensus_score, dédup intra et inter-bucket pour éviter les collisions PDA. |
| Soumission | `EppSolanaClient.submit_attestation(att, frame_hash)` async. PDA dérivée via `derive_attestation_pda(program_id, submitter, claim_hash)`. Slot enrichment via `getSignatureStatuses` (best-effort). |
| Idempotence | Skip si `claim_hash` déjà dans le manifest avec `tx_signature` OK. Manifest flushé atomiquement (tmp + os.replace) après chaque push pour résister à un crash mid-batch. |
| Garde devnet | Hérite de `services/solana/config.py::validate_cluster()`. Refuse de mocker silencieusement (exit 4 si SDK ou keypair manquants). |
| Write-back DB | Optionnel via `ISpaceDB.update_attestation_solana_tx(claim_hash, tx_signature, slot)`. Best-effort — un échec de write-back n'invalide pas le push on-chain. |
| Sortie | `data/devnet_pushed.json` — manifest pour Phase C.2 UI. Schéma : `{ generatedAt, programId, cluster, submitter, summary, attestations[] }`. |
| 1ère exécution | 12/12 push réussis en ~5s, 0 failed. Submitter `DRAQ7ZppvzUdASF9jR218aPutsirUFwt2ePr6f9n9rJw`, program `9QtybfyZQFhra1D6S3NtD6jD4z2Z3wcYmf4YXETq8bSD`. |

### Demos / Benchmarks

| Fichier | Role | Etat |
|---------|------|------|
| `demos/scenario_flywheel.py` | Flywheel ADR-018 : Trump + Yemen + Suisse (3 claims) | ✅ Fonctionnel |
| `demos/scenario_flywheel_v2.py` | Flywheel v2 : 5 claims post-cutoff (Trump, Starmer, Sheinbaum, Nobel, Biden) + pre-validation SPARQL | ✅ Fonctionnel |
| `demos/scenario_flywheel_v2_baseline.py` | Baseline VERIFY-only pour flywheel v2 (4 claims, sans pass deterministe) | ✅ Fonctionnel |
| `demos/scenario_deterministic_sources.py` | Scénario dédié aux sources déterministes. 4 sources sur 8 testées en live : Wikidata 5/5 checks, Verra VCS 5/5 checks. Commit `1d703fd`. | ✅ Fonctionnel |

---

### Sprint post-audit Gatekeeper (2026-04-14)

Exécution de `docs/To_do_list/DIRECTIVE_CORRECTION_AUDIT.md` en 9 blocs RED-GREEN-FIX validés par l'humain : S7-001 (CORS explicite), S1-001/S1-002 (Enum V2 — ADR-019), S3-001-004 (exceptions typées), S6-001 (schéma Pydantic config_loader), S1-003 (troncature UTF-8 codepoint-safe), S1-005 (marker AUDIT reclassé), S6-002 (`db_path` obligatoire), S9-001 (migration `asyncio.run` → `pytest-asyncio`). Bloc F (rate limiting S7-002) différé. Baseline tests : 811 → 866 (+55). Détails par bloc dans `docs/fr/CHANGELOG.md` entrée 2026-04-14.

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

### Sources déterministes / Bifurcation (ADR-012 — 2026-02-25 ; renommage ADR-014 §2.1)

Nouveau chemin déterministe parallèle au pipeline ESMM. L'appelant déclare `claim_nature=DETERMINISTIC` (Axiome 3 — pas d'inférence automatique). Le pipeline court-circuite les cycles LLM, interroge la source autoritaire, hash la réponse brute en SHA-256 (`source_anchor` on-chain), stocke le snapshot complet en SQLite, cristallise une attestation `epistemic_type="deterministic"`.

| Fichier | Rôle | État |
|---------|------|------|
| `services/esmm/source_anchor_builder.py` | `SourceAnchorSpec`, `SourceAnchorResult`, `build_source_anchor()`, `_canonical_hash()` (SHA-256 JSON canonique sorted-keys) | ✅ Fonctionnel |
| `services/sources/adapters/base.py` | ABC `SourceAdapter` : `fetch(query)`, `normalize(raw)`, `get_source_version(raw)` | ✅ Fonctionnel |
| `services/sources/adapters/opensanctions.py` | POST `/match` yente (0 credential, testable en local) | ✅ Fonctionnel |
| `services/sources/adapters/ofac.py` | POST OFAC SDN — `OFAC_API_KEY` env var | ✅ Fonctionnel |
| `services/sources/adapters/eu_cfsp.py` | GET sanctions.network EU CFSP (données ouvertes) | ✅ Fonctionnel |
| `services/sources/adapters/verra_vcs.py` | GET Verra Registry L1 (serial/project_id — public) | ✅ Fonctionnel |
| `services/sources/adapters/__init__.py` | Registre `_REGISTRY` + `get_adapter()` + `register_adapter()` | ✅ Fonctionnel |
| `services/sources/adapters/acled.py` | OAuth2 POST `acleddata.com/oauth/token` (token 24h caché). Dual-mode : events (`/api/acled/read`) + forecast CAST (`/api/cast/read`). `normalize()` → score=min(1, count/baseline), status=stable/escalation/de-escalation. ADR-016. | ✅ Fonctionnel |
| `services/sources/adapters/wikidata.py` | SPARQL endpoint public (CC-0). Source structurée du Flywheel ADR-018 ; scores plafonnés à 0.85 (éditabilité publique). | ✅ Fonctionnel |
| `services/sources/adapters/nist_codata.py` | Constantes physiques NIST/CODATA 2022. Source autoritaire primaire (scores 1.0). | ✅ En développement |

**Frames** (dans `services/metrology.py`) :

| Frame | Domaine | `esmm_bypass` |
|-------|---------|--------------|
| `compliance_sanctions_v1.0` | regulatory_compliance / sanctions_status | `True` |
| `carbon_credits_vcs_v1.0` | environmental_assets / carbon_credit_validity | `True` (L2 désactivé — ADR-012 Q3) |
| `rwa_identity_v1.0` | identity_compliance / entity_sanctions_composite | `True` (ESMM on ambiguity désactivé par défaut) |
| `smartcontract_audit_v1.0` | smart_contract_security / vulnerability_classification | `False` (ESMM obligatoire — ADR-014) |
| `geopolitical_forecast_v1.0` | geopolitical_analysis / conflict_forecast_assessment | `False` (deux chemins coexistent — ADR-016) |

### Oracle Géopolitique ACLED (ADR-016 — 2026-03-10)

Données de conflit ACLED ancrent les prédictions géopolitiques. Double chemin : VERIFY épistémique (ESMM) + DETERMINISTIC ACLED.

| Fichier | Rôle | État |
|---------|------|------|
| `services/sources/adapters/acled.py` | ACLEDAdapter — OAuth2, events/forecast dual-mode, normalize() | ✅ Fonctionnel |
| `demos/scenario_jiang.py` | 8 claims Jiang Xueqin (Iran/proxy/Hormuz + contrôles). VERIFY + DETERMINISTIC ACLED si credentials. Output JSON horodaté `demos/benchmark_runs/jiang_{ts}.json`. | ✅ Fonctionnel |

**Table SQL ajoutée (table 25)** :

- `source_anchor_snapshots` — snapshot raw_response off-chain, `source_anchor` SHA-256 → on-chain. Contrainte UNIQUE `(source_id, query_hash, source_version)`. Index sur `source_anchor` et `(source_id, fetched_at DESC)`.

**Méthodes ISpaceDB ajoutées (ADR-012)** :

- `store_source_anchor_snapshot()` — INSERT OR IGNORE snapshot
- `get_snapshot_by_anchor()` — Lookup par SHA-256 source_anchor
- `is_snapshot_fresh()` — TTL check par (source_id, query_hash, max_age_hours)

**`config.yaml`** : section `sources.adapters` — 4 sources (enabled/ttl_hours). Credentials via env vars uniquement.
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
  ├── services/metrology.py
  └── services/governance/proposal.py

publication optionnelle
  └── services/solana/
        ├── config.py
        ├── bridge.py
        ├── client.py
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
- **Lean 4** + **Lake** (vérification formelle, ADR-019 — cf. `Formal/lean-toolchain`)
- **Click** pour CLI EPP

---

## Audit Tooling

`epp_audit.py` — Script unifié (remplace `audit_runner.py`, `audit.sh`, `find_orphans.sh`)

| Phase | Contenu |
| :--- | :--- |
| 1 — Statique | Contrôles C2-C8 : singletons, silent except, schema drift, config drift, weak assertions, VERIFY coverage |
| 2 — Orphelins | Détection modules Python non importés (cross-platform, pas de shell) |
| 3 — Régression | `pytest tests/` complet, résilience aux erreurs de collection |
| 4 — Mutations | 21 mutations (M1.1-M7.3), 7 groupes — baseline : 21 KILLED, 0 SURVIVED |

Outputs → `tests/audits/` (`EPP_AUDIT_REPORT.md`, `audit_checksums.txt`)

```bash
python epp_audit.py                  # Audit complet (~10 min)
python epp_audit.py --no-mutations   # Phases 1-3 (~30 sec)
python epp_audit.py --static         # Phase 1 seule
python epp_audit.py --mutations      # Phase 4 seule
```
