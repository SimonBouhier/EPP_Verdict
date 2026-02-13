# CHANGELOG.md — EPP_Verdict

> Journal factuel des modifications. Format : date, titre court, 2-3 lignes de faits.

---

## [2026-02-12] Phase 4 — Correction systematique (v2)

### Phase 4.0 — Fondations

- Isolation tests: reset 16 singletons (setup+teardown), conftest.py reecrit
- Demockage: 0 mock complaisant trouve, 1 annote
- Smoke test Solana bridge: 7 tests (types Python/Anchor compatibles)
- Migration async: 4 fichiers tests migres de asyncio.run() vers async def natif
- Baseline: 425 -> 432 passed

### Phase 4.1 — Crashs runtime (RED-GREEN-FIX)

- triplet_extractor: ON CONFLICT(source, target, relation_type) -> ON CONFLICT(source, target)
- 5 imports deprecies app.embeddings migres vers services.providers.ollama_embeddings
- session_storage: 4 INSERT -> INSERT OR IGNORE (ADR-004)
- Baseline: 435 passed

### Phase 4.2 — Corruption silencieuse (RED-GREEN-FIX)

- graph_delta ADD_EDGE: INSERT OR REPLACE -> INSERT ON CONFLICT DO UPDATE (preserve relation_type)
- pool.py: 2 except:pass -> except Exception as e: logger.warning()
- Baseline: 438 passed

### Phase 4.3 — Durcissement structurel

- get_db() warning si appele avec db_path different
- close_entity_resolver(), close_relation_normalizer() ajoutes
- 5 except:pass restants annotes ou fixes en production
- Test singleton pollution permanent
- Baseline: 440 passed

### Phase 4.4 — Nettoyage

- config.yaml: 35 cles -> 12 effectives, 3 sections mortes supprimees (providers, server, logging)
- esmm.models ajoute a config.yaml (AUDIT[A8-001] fixe)
- app/embeddings.py supprime (fully replaced by EmbeddingProvider)
- semantic_memory table supprimee du schema (in-memory only)
- Baseline: 440 passed

### Phase 4.5 — Securite

- Prompt injection: XML boundary delimiters (<system_instruction>, <user_query>)
- Concept sanitization: _sanitize_concept() dans cycle_manager.py
- Sybil: infer_architecture_family() durci (first-token match, provider prefix strip)
- Pipeline input validation: MAX_QUESTION_LENGTH=5000, control char stripping
- ADR-005 respecte: pas de retour au seuil simple
- 16 tests securite ajoutes
- Baseline: 456 passed

### Phase 4.6 — Solana devnet complet

- Transaction building: _build_and_send_submit_tx() via solders (Borsh manual)
- Account deserialization: _deserialize_attestation_account()
- PDA validation: check_pda_exists()
- Query methods: query_attestations_by_claim/subject (memcmp filters)
- Mock mode: submit retourne signature deterministe sans solders
- ADR-008 cree: strategie auth submitter
- 14 tests Solana ajoutes
- Baseline finale: 470 passed, 0 failed, 11 skipped

---

## [2026-02-12] Phase 3.3 — Relecture framework + ADR

- Audit de conformité CLAUDE.md §5 (7 règles anti-dette IA)
- Créé 7 Architecture Decision Records (docs/adr/ADR-001 à ADR-007)
- Annoté 7 violations §5.1-§5.7 dans le code (2 §5.1, 2 §5.2, 2 §5.5, 1 §5.1 session_storage)
- Corrigé 1 INSERT brut : engine.py sessions → INSERT OR IGNORE (§5.1 bloquant)
- Rapport de conformité : 2 INSERT bruts critiques, 16 except:pass (4 déjà annotés), 13 singletons, 0 mismatch signatures
- Tests: 425 passed, 0 failed, 10 skipped

## Rapport de Conformité §5 — CLAUDE.md
Date : 2026-02-12

### §5.1 — INSERT bruts
- 20 trouvés, 1 corrigé (engine.py:691 sessions → INSERT OR IGNORE), 1 annoté (session_storage.py:291)
- 16 low-risk (tables à PK autoincrement), 2 déjà protégés (ON CONFLICT)

### §5.2 — except:pass sans justification
- 16 trouvés, 4 déjà annotés AUDIT[], 5 nouvellement annotés (2 §5.2 FRAGILE, 3 # OK justifiés)
- 7 non annotés (🟢 ACCEPTED : patterns de parsing/fallback idiomatiques)

### §5.3 — Signatures non propagées
- 7 méthodes vérifiées, 45 appelants audités, 0 mismatches trouvés

### §5.4 — Schéma ↔ code
- Tables : 23 dans le code, 24 dans le schéma, 1 divergence (semantic_memory dans schéma mais pas dans code)
- Colonnes critiques vérifiées : concepts ✓, relations ✓, attestations ✓, triplet_extractions ✓, graph_deltas ✓

### §5.5 — Singletons
| Fichier | Variable | Vérifie params | Reset | Annoté |
|---------|----------|---------------|-------|--------|
| database/pool.py | _pool_instance | PARTIEL (db_path) | close_pool() | ✓ A1-006/007/008 |
| database/engine.py | _db_instance | NON | close_db() | ✓ A1-001 |
| services/config_loader.py | _config | NON | reset_config() | — |
| services/entity_resolver.py | _resolver_instance | NON | NON | ✓ §5.5 (nouveau) |
| services/relation_normalizer.py | _normalizer_instance | NON | NON | ✓ §5.5 (nouveau) |
| services/providers/ollama.py | _ollama_instance | NON | close_ollama_provider() | — |
| services/providers/ollama_embeddings.py | _ollama_embedding_instance | NON | close_ollama_embedding_provider() | — |
| app/llm_client.py | _client_instance | NON | close_ollama_client() | — |
| services/esmm/model_rotator.py | _rotator_instance | NON | close_model_rotator() | — |
| services/esmm/triplet_extractor.py | _extractor_instance | NON | close_triplet_extractor() | — |
| services/consciousness/memory.py | _memory_instance | NON | clear_semantic_memory() | — |
| services/relation_normalizer.py | _normalizer_instance | NON | NON | ✓ §5.5 (nouveau) |
| services/session_storage.py | _storage_instance | NON | implicite | — |

### §5.6 — Tests substantifs
- Fichiers avec ratio < 2 : 19 fichiers (test_phase3_post_crystallization 0.75, test_phase2_diversity 1.0, test_phase2_integration 1.0, test_phase2_track_record 1.0, test_phase03_audit 1.0, etc.)
- Assertions faibles : 12 total (4 `is not None`, 8 `is True`)

### §5.7 — Configuration
- Clés orphelines : ~35 (la majorité de config.yaml est décorative — seuls database.path et esmm.* sont lus)
- Valeurs hardcodées : ~30 (seuils de confiance, URLs Ollama, modèles d'embedding, host/port serveur)

### ADR créés : 7 (docs/adr/ADR-001 à ADR-007)

---

## [2026-02-11] Phase 3.2 — Consolidation post-audit

- Ajouté colonne `submission_status` à la table `attestations` dans schema.sql (25 tables, 29 colonnes)
- Corrigé import cassé entity_resolver.py (`get_embedding` → `get_embeddings`)
- Ajouté `embedding_model` aux appels `add_concept()` dans seed_injector.py, populate_graph.py, entity_resolver.py
- Sécurisé `record_model_prediction()` avec INSERT OR IGNORE (anti-doublon retry)
- Annoté 51 points d'audit dans le code (marqueurs `AUDIT[AX-NNN]` : 9 CRITICAL, 31 FRAGILE, 11 ACCEPTED)
- Tests: 425 passed, 0 failed, 10 skipped

## [2026-02-10] Phase 3.1 — Corrections post-audit

- Installé pytest-asyncio, configuré asyncio_mode=auto (résout 32 failures async)
- Corrigé test_esmm_phase1.py: async fixture cleanup avec close_pool() (résout 1 error)
- Migré 10 tests Phase 0.3 vers nouveaux tiers (sandbox/proposition/validated/verified)
- Corrigé test_phase1_client.py: asyncio.get_event_loop() → async/await (résout 2 failures)
- Ajouté run_id dans post_crystallization hook (traçabilité)
- Vérifié alignement signature record_model_prediction (engine.py ↔ post_crystallization.py)
- Corrigé isolation DB tests : fixture conftest.py reset pool + singleton entre tests
- Corrigé rollback_deltas() : utilise applied_at au lieu de timestamp pour le filtre to_timestamp
- Corrigé rollback_deltas() : supporte rollback all (sans delta_ids ni to_timestamp)
- Sécurisé rollback DELETE_EDGE : INSERT OR REPLACE (anti UNIQUE constraint)
- Tests: 425 passed, 0 failed, 10 skipped (avant: 368 passed, 53 failed, 5 errors)

## [2026-02-10] Phase 3 — End-to-end pipeline

- config_loader.py: centralized config.yaml loading (singleton)
- MockProvider: realistic mock for full pipeline testing without Ollama
- orchestrator.py: ESMMRunResult enriched with consensus_triplets field
- cycle_manager.py: create_cycle_manager() accepts optional providers parameter
- pipeline.py: _extract_triplets_from_question() calls real orchestrator (D1-D4)
- pipeline.py: post-crystallization hook for track record + tier transitions (D8)
- pipeline.py: graph seeding from question on empty graph (D7)
- triplet_adapter.py: ConsensusTriplet -> dict pipeline conversion (D4)
- question_seeder.py: tokenizes question and seeds graph concepts (D7)
- post_crystallization.py: records model votes + logs tier transitions (D8)
- epp_cli.py: query reads DB, graph stats reads DB, submit loads/queues attestation (D9)
- engine.py: +3 methods (get_latest_attestation, get_attestation_count, update_attestation_submission_status)
- 3 demo scenarios updated to use MockProviders + real pipeline
- Tests: 264+ pass (76 new Phase 3 tests, 188 Phase 0-2 backward compat)

## [2026-02-08] Phase 2 — Robustesse & Intégrité Épistémique

- Refondu `config.yaml` : zéro référence Lyra, sections EPP complètes (esmm, confidence, solana, track_record, providers)
- Remplacé confidence tiers `low/medium/high` par méthode scientifique : `sandbox/proposition/validated/verified` avec conditions multi-critères (score + modèles + familles archi + source_anchor)
- Créé `services/esmm/pipeline.py` : pont orchestrateur -> cristallisation -> DB -> graphe (remplace les mocks CLI)
- Ajouté tables SQL 20-22 : `metrological_frames`, `model_track_record` (Brier scoring), `tier_transitions` (audit promotions/rétrogradations)
- Ajouté vue `v_model_brier_scores` : Brier score par modèle (fenêtre glissante 90j)
- Ajouté `infer_architecture_family()` dans `base.py` : mesure diversité architecturale pour anti-Sybil
- Ajouté méthodes engine.py : `update_attestation_solana_tx()`, `store_frame()`, `get_frame()`, `list_frames()`, `record_model_prediction()`, `resolve_prediction()`, `get_model_brier_score()`, `log_tier_transition()`
- Ajouté seeder automatique des MetrologicalFrames en DB lors de `initialize()`
- Branché CLI `epp ask` sur pipeline réel (pas de mocks)
- Créé 3 scénarios de démonstration dans `demos/`
- 61 tests Phase 2, 77 tests Phase 1 backward compat (tous verts)

## [2026-02-06] Phase 1 — Finalisation build Anchor + config

- Programme Anchor build OK : `anchor build` produit `epp.so` (221 KB) + IDL
- Programme ID deploye : `98Fc2oL2cKsTDGYi3GifggzkQkEQSRn2oTgg8HsaVa3C`
- Ajout `DEFAULT_PROGRAM_ID` dans `services/solana/config.py` comme constante et valeur par defaut de `SolanaConfig`
- Test Anchor `ping` passe sur localnet via `anchor test`
- Fix tests async `test_phase1_client.py` : conversion sync (pytest-asyncio non charge)
- 83 tests Phase 1 passent (9 skipped, necessitent solana-test-validator)

## [2026-02-05] Phase 1 — Couche Solana (MVP)

- Cree `services/solana/` : config.py (devnet guard), metrological_frame.py, bridge.py, client.py
- Cree `programs/epp/` : programme Anchor (Rust) avec struct EpistemicAttestation (462 bytes), instruction submit_attestation + ping
- Cree `cli/epp_cli.py` : commandes ask, submit, query, frame list/show, graph stats
- PDA seeds : `[b"attestation", submitter, claim_hash]` — permet multi-submitter par claim
- Bridge Python <-> Anchor : float [0,1] <-> u16 [0,10000], strings <-> fixed bytes zero-padded
- Guard devnet-only : MAINNET absent de l'enum SolanaCluster
- Structure workspace Anchor : `programs/epp/programs/epp/src/` (lib.rs, state.rs, errors.rs, constants.rs)

## [2026-02-05] Phase 0.3 — ESMM Découplé, Cristallisation & Revalidation

- Audit et purge : zéro référence directe à un modèle/provider dans le pipeline ESMM
- Créé `services/esmm/attestation.py` : EpistemicAttestation (Pydantic), crystallize(), compute_claim_hash(), RevalidationInput
- Créé table `attestations` (table 19) : stockage attestations avec signature 5D, votes, provenance
- Créé `services/esmm/run_logger.py` : RunLogger avec PhaseEvent, logging JSON structuré
- Ajouté méthodes engine.py : store/get_attestation, get_attestation_history, get_attestations_by_subject
- Ajouté RevalidationInput : sérialisation des inputs pour revalidation
- 65 tests unitaires + intégration (test_phase03_*.py)

## [2026-02-05] Phase 0.2 — Migration Embedding Sans Perte

- Créé tables `concept_embeddings` (stockage multi-version) et `embedding_migrations` (traçabilité)
- Migration automatique des embeddings existants vers `concept_embeddings` lors de `initialize()`
- `add_concept()` écrit désormais dans les deux tables ; exige `embedding_model` si embedding fourni
- Découpé dimension hardcodée 1024 dans `SemanticMemory` — accepte maintenant toute dimension valide
- `app/embeddings.py` marqué déprécié avec `DeprecationWarning`
- Créé `tools/migrate_embeddings.py` : CLI migration progressive (--dry-run, --finalize, --rollback)
- Ajouté section `embeddings` dans `config.yaml` (active_model, fallback_reembed, similarity_min_score)
- 45 tests unitaires (test_phase02_*.py) couvrant schéma, découplage, migration, recherche cross-version

## [2026-02-04] Phase 0.1 — ModelProvider interface + découplage ESMM

- Créé `services/providers/` : ABC ModelProvider/EmbeddingProvider, OllamaProvider, OpenAICompatProvider, AnthropicProvider, ProviderRegistry
- Créé `MultiProviderRotator` remplaçant `ModelRotator` (provider-agnostique)
- Corrections : retry logic OllamaProvider, keep_alive configurable, ProviderRegistry test-friendly (clear_all)
- 55 tests unitaires (test_providers.py + test_rotator.py)
- Refactoré triplet_extractor.py et cycle_manager.py pour utiliser MultiProviderRotator

## [2026-02-03] Initialisation EPP_Verdict

- Fork de Lyra ACE vers EPP_Verdict (Epistemic Proof Program)
- Création `CLAUDE.md` (instructions figées), `ARCHITECTURE.md` (état vivant), `CHANGELOG.md` (ce fichier)
- Objectif : oracle épistémique décentralisé sur Solana — couche de validation sémantique multi-LLM
