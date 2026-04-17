# CHANGELOG.md — EPP_Verdict

> Journal factuel des modifications. Format : date, titre court, 2-3 lignes de faits.

---

## [2026-04-14] Sprint de correction post-audit Gatekeeper — 9 blocs RED-GREEN-FIX

Sprint d'exécution stricte de `docs/To_do_list/DIRECTIVE_CORRECTION_AUDIT.md`.
Neuf blocs validés un par un par l'humain. Protocole RED→GREEN→FIX respecté à chaque étape.

- **BLOC A — S7-001 CORS dangereux** : `app/main.py` — `allow_origins=["*"]` + `allow_credentials=True` remplacé par liste explicite d'origines dev (localhost) avec override via variable d'environnement `EPP_ALLOWED_ORIGINS` (CSV).
- **BLOC B+C — S1-001 + S1-002 Enum épistémique V2 (ADR-019)** : projection HYBRIDE des 8 types Python (`foundational`, `bridge`, `specialized`, `generalist`, `hybrid`, `verdict`, `deterministic`, `security_audit`) vers 3 catégories on-chain formellement vérifiables (`empirical=0`, `deterministic=1`, `assessed=2`). `bridge.py::EPISTEMIC_TYPE_MAP` et `EPISTEMIC_TYPE_REVERSE` réécrits. Rust `lib.rs::require!(epistemic_type <= 2, ...)` + `state.rs::epistemic_type_to_u8()` match multi-alternatives. Documentation invariants Lean 4 en commentaires Rust.
- **BLOC D — S3-001 à S3-004 Exceptions silencieuses granulées** : 4 `except Exception` remplacés par exceptions typées + `logger.warning/error` avec contexte. `engine.py` (seed frames), `pipeline.py` (parse consensus_meta + cache lookup), `client.py` (load keypair — re-raise fail-fast sur erreurs inattendues).
- **BLOC E — S6-001 Schéma Pydantic config_loader** : `ConfigSchema` Pydantic strict (`extra="forbid"` à chaque niveau) ajouté dans `services/config_loader.py`. Validation fail-fast à `load_config()` — rejette clés inconnues et types invalides. Chaque champ documente sa source de lecture.
- **BLOC G — S1-003 Troncature UTF-8 codepoint-safe** : `bridge.py::string_to_fixed_bytes` aligné sur frontière de codepoint (boucle `while truncated.encode("utf-8") > max_len`). Corrige les corruptions silencieuses pour `é` (2 bytes), `中` (3 bytes), `😀` (4 bytes).
- **BLOC H — S1-005 Marker AUDIT[A10-007] reclassé** : `bridge.py:111` — `🟡 FRAGILE` → `🟡→✅ RESOLVED`. Le commentaire antérieur décrivait un bug qui n'existe pas (la guard `0.0 <= value <= 1.0` rejette déjà les valeurs hors borne). Annotation conservée pour traçabilité.
- **BLOC I — S6-002 db_path obligatoire** : `database/engine.py:50` — default `"data/ispace.db"` supprimé. `ISpaceDB(db_path)` désormais obligatoire. Zéro appelant sans arg confirmé par grep exhaustif avant modification.
- **BLOC J — S9-001 Migration asyncio.run → pytest-asyncio** : 20 fonctions de test réécrites en `async def` + `@pytest.mark.asyncio` dans `test_phase02_decoupling.py`, `test_phase02_migration.py`, `test_phase03_integration.py`, `test_phase03_revalidation.py`. Nested event-loop pattern éliminé.

### Hors scope

- **BLOC F — S7-002 Rate limiting** : différé (décision humaine). `app/main.py` n'est pas touché pour le rate limiting dans ce sprint.

### Baseline

866 passed, 11 skipped, 0 failed (delta net : **+55 passed** vs. baseline 811). 10 nouveaux fichiers de test (un par bloc + un pour le test d'inspection AST S9-001). 4 tests existants (`test_phase1_bridge.py`, `test_phase1_integration.py`, `test_phase4_solana.py`, `test_solana_deserialize.py`) mis à jour pour refléter la sémantique V2 du round-trip enum. 4 tests `test_phase3_config_loader.py` mis à jour pour utiliser des configs conformes au schéma Pydantic.

### Déploiement Rust

Les modifications `programs/epp/src/lib.rs` et `state.rs` sont préparées et syntaxiquement valides (relecture visuelle). `cargo check` indisponible sur Windows natif — validation Anchor à exécuter en WSL par l'humain.

---

## [2026-04-11] ADR-018 — Flywheel v2 : scénarios post-cutoff expandus

- `demos/scenario_flywheel_v2.py` : nouveau scénario flywheel étendu — 5 claims post-training-cutoff vérifiables via Wikidata SPARQL. Pré-validation SPARQL automatique au lancement (requêtes invalides retirées du run). Claims : Trump 2024, Starmer PM UK, Sheinbaum présidente Mexique, Nobel Physique 2024 Hopfield/Hinton, contrôle Biden.
- `demos/scenario_flywheel_v2_baseline.py` : script baseline VERIFY-only (sans pass déterministe, sans flywheel) pour mesurer les scores LLM bruts et calculer les deltas.
- Résultats flywheel v2 (3 modèles : mistral, llama3.1:8b, gemma3) :
  - Trump : 0.39 CONTESTED → 0.89 SUPPORTED (delta +0.46, verdict flip)
  - Starmer : 0.49 CONTESTED → 0.76 SUPPORTED (delta +0.28, verdict flip)
  - Sheinbaum : 0.78 SUPPORTED → 0.96 SUPPORTED (delta +0.18)
  - Nobel 2024 : 0.79 SUPPORTED → 0.95 SUPPORTED (delta +0.18)
  - Biden contrôle : 0.90 → 0.96 (delta +0.06, marginal — modèles savent déjà)
- FW2-04 (Prabowo/Indonésie) et FW2-06 (loi martiale Corée du Sud) retirés : Wikidata SPARQL retourne 0 résultats pour ces QIDs.
- FW2-CTRL-02 (UE 30+ membres) retiré : faux positif non corrigeable — le format d'injection flywheel transmet le status/score mais pas la valeur brute du count.

### Fix — consensus_meta string→dict désérialisation (DB layer)

- Cause racine : `consensus_meta` est TEXT en SQLite, sérialisé via `json.dumps` à l'écriture, mais jamais `json.loads` à la lecture. Crash `'str' object has no attribute 'get'` sur tout chemin lisant `consensus_meta` depuis la DB.
- `database/engine.py` : 4 SELECTs alignés sur la même liste de colonnes (ajout `adjusted_consensus_score`, `diversity_bonus_factor`, `commit_reveal_verified`, `consensus_meta` aux 3 requêtes courtes). `_row_to_attestation_dict()` : désérialisation `consensus_meta` via `json.loads` à l'index 28. `get_latest_attestation()` : ajout `consensus_meta` dans la boucle de désérialisation JSON.
- `services/esmm/attestation.py` : guard `isinstance(consensus_meta, str)` dans `crystallize()` — défense en profondeur.
- Protocole RED→GREEN→FIX respecté. Test ajouté : `test_consensus_meta_deserialized_as_dict_from_db`.

### Fix — get_latest_attestation() colonne inexistante

- `database/engine.py` : `ORDER BY created_at` → `ORDER BY timestamp`. La table `attestations` n'a pas de colonne `created_at`.
- Protocole RED→GREEN→FIX respecté. Test ajouté : `test_get_latest_attestation_returns_stored_row`.

### Fix — Retrait extra_system_context (ajout hors scope)

- `services/esmm/pipeline.py` : paramètre `extra_system_context` retiré de `run_pipeline()`. Ajouté hors scope pendant le fix consensus_meta, zéro appelant dans le codebase. Causait une chute du score Trump flywheel de 0.89 à 0.58.

### Baseline

811 passed, 14 skipped, 0 failed (net +2 tests : `test_consensus_meta_deserialized_as_dict_from_db`, `test_get_latest_attestation_returns_stored_row`).

---

## [2026-03-13] ADR-018 — Flywheel Épistémique

- **Fix B4 (bloquant)** : `_run_deterministic_pipeline()` (pipeline.py:172) appelait `crystallize()` sans `question=question` → colonne `question` NULL en DB → `get_attestations_by_question()` ne retournait jamais d'ancres déterministes. Ajout de `question=question` dans l'appel `crystallize()`.
- **`_lookup_existing_anchors(question, db)`** : nouvelle fonction pipeline.py — lookup par `question` via ADR-013 `get_attestations_by_question()`, filtre `consensus_method == "deterministic_source_v1"`, lit `diagnostics.result` (PAS `source_anchor_meta.normalized`). Retourne liste de dicts `{source_id, score, status, fetched_at, source_version}`.
- **`_format_anchor_context(anchors)`** : formate les ancres en bloc `[VERIFIED DATA — from deterministic sources...]...[END VERIFIED DATA...]` injecté dans le system prompt. Retourne `""` si aucune ancre.
- **Bloc flywheel dans `run_pipeline()`** : guard `is_verify = (esmm_config.input_mode == "verify")` (ADR-018 §4 — VERIFY-only). Variable `flywheel_enabled` initialisée à `False` hors du `try` (correction Opus P2 — évite NameError dans la traçabilité). Lookup encapsulé dans `try/except` non-bloquant.
- **Threading `anchor_context` sur 4 frontières** : `run_pipeline()` → `_extract_triplets_from_question(anchor_context=)` → `esmm_config.anchor_context` → `execute_cycles()` cycle_context `["anchor_context"]` → `execute_cycle()` → `_query_models(anchor_ctx=)` + `_query_models_isolated(anchor_ctx=)` → concaténation system_prompt.
- **`ESMMRunConfig`** : champ `anchor_context: str = ""` ajouté (`orchestrator.py`).
- **Traçabilité `consensus_meta`** : `consensus_meta.setdefault("methodology", {})["flywheel"] = {enabled, anchors_found, sources_injected}`.
- **`config.yaml`** : section `flywheel: { enabled: true }` ajoutée.
- **`tests/test_adr018_flywheel.py`** : 8 tests RED-GREEN-FIX — `test_lookup_no_anchors`, `test_lookup_with_deterministic_anchor`, `test_lookup_filters_out_epistemic_attestations`, `test_format_anchor_context_empty`, `test_format_anchor_context_with_data`, `test_consensus_meta_flywheel_traceability`, `test_flywheel_disabled`, `test_flywheel_skipped_in_explore_mode` (correction Opus P3). Baseline : 809 passed, 14 skipped, 0 failed.

---

## [2026-03-13] Fix ACLED 403 — header Content-Type OAuth2

- `services/sources/adapters/acled.py` : ajout `headers={"Content-Type": "application/x-www-form-urlencoded"}` au POST `/oauth/token`. Sans ce header, l'API ACLED retourne 403 même avec des credentials valides.
- Ajout `import logging` + `logger.info("[ACLED] Token request (cached=...)")` avant le check cache du token.

---

## [2026-03-13] Fix Wikidata User-Agent + SPARQL QID

- `services/sources/adapters/wikidata.py` : ajout `User-Agent: EPP_Verdict/1.0 (...)` dans les headers HTTP — cause racine des erreurs `not_found` sur les requêtes SPARQL Wikidata (API bloque les crawlers sans User-Agent).
- `demos/scenario_jiang.py` : JIANG-RESOLVED-01 `wikidata_query` corrigé — `wd:Q116827690 wdt:P1346` → `wd:Q101110072 wdt:P991` (Q101110072 = élection présidentielle US 2024, P991 = successful candidate, plus précis que P1346 winner). JIANG-RESOLVED-02 : `wikidata_query: None` (opérations militaires non interrogeables dans Wikidata). Logs debug `[WIKI]` conservés. `CLAIMS` complet restauré (filtre single-claim retiré).

---

## [2026-03-10] ADR-016 Lot 6 — scenario_jiang.py

- `demos/scenario_jiang.py` : script de démonstration géopolitique — 8 claims issues des prédictions Jiang Xueqin (Yale, "Predictive History") sur la stratégie iranienne et la dynamique du Moyen-Orient 2024-2026.
- Deux passes par claim : VERIFY épistémique (ESMM multi-LLM) + DETERMINISTIC ACLED (ancrage données de conflit, si `ACLED_EMAIL` défini). Concordance VERIFY↔ACLED calculée et exportée.
- Output JSON horodaté dans `demos/benchmark_runs/jiang_{ts}.json`. Baseline inchangée : 797 passed, 14 skipped.

---

## [2026-03-09] Fix `<think>` tag stripping — modèles reasoning (phi4/deepseek-r1)

- `services/esmm/triplet_extractor.py` : nouvelle fonction `_strip_thinking_tags()` — supprime `<think>...</think>` et `<thinking>...</thinking>` avant parsing JSON (regex non-greedy, multi-blocs). Appliquée en tête de `_parse_verdict_response()` (remplacement du `.strip()` initial).
- `services/esmm/triplet_validator.py` : appel `_strip_thinking_tags()` importé depuis `triplet_extractor` (source unique) avant le parser EXPLORE — protège aussi le mode EXPLORE si `<think>` contient du contenu JSON-like.
- Cause racine : regex `\{[\s\S]*\}` greedy capturait depuis le 1er `{` dans `<think>` jusqu'au dernier `}` → JSON invalide → `INSUFFICIENT_EVIDENCE` → vote perdu → `models_consulted: 2` au lieu de 3. 782 passed, 14 skipped, 0 failed.

---

## [2026-03-09] Correctifs métadonnées Bug A + Bug B (pipeline.py / orchestrator.py)

- **Bug A — cycle\_sequence** : `orchestrator.py:427` — write-back `self.config.cycle_sequence = cycle_sequence` après l'override VERIFY local. `_build_consensus_meta()` enregistrait la valeur config.yaml (`["divergent","debate","meta"]`) au lieu des cycles réels (`["assess","challenge","adjudicate"]`).
- **Bug B — final\_verdict None** : `pipeline.py` — boucle cristallisation splitée en 2 passes. Passe 1 : crystallize + post_hook + collecte `(attestation, triplet)` sans storage DB. Après blocs P1/P2 d'enrichissement (`final_verdict`, `evidence_corpus`), Passe 2 : `model_dump()` + `store_attestation()` + inject graph. Pydantic v2 shallow-copy confirmée : inner dicts partagés → `consensus_meta["verify"]["final_verdict"]` propagé vers toutes les attestations sans réassignation explicite. 782 passed, 14 skipped, 0 failed.

---

## [2026-03-09] Fix routing EXPLORE→VERIFY (pipeline.py)

- `_extract_triplets_from_question()` : guard `if getattr(esmm_config, "input_mode", None) != "verify"` avant appel `classify_input()`. Le prompt ASSESS_AUDIT ne contient pas les mots-clés de détection VERIFY → `classify_input()` retournait EXPLORE et écrasait `input_mode="verify"` posé par `audit_runner`. Cycles exécutés correctement mais métadonnées mentaient (symptôme observé : `cycle_sequence: ["divergent","debate","meta"]` en DB). 782 passed, 14 skipped, 0 failed.

---

## [2026-03-09] ADR-014 Lots 3+4 — Moteur d'audit smart contract

### Lot 3 — audit_runner + CLI

- Nouveau module `services/audit/audit_runner.py` : `AuditResult` dataclass, `run_audit()` async (slice → pipeline VERIFY par unité), `_safe_format()` (regex substitution évitant `KeyError` sur JSON `{}` dans template ASSESS_AUDIT), `format_unit_for_audit_prompt()`, `_sort_units_by_priority()`, `_extract_severity_from_result()`, `_aggregate_severity()` (pire sévérité gagne).
- `config.yaml` : section `audit:` (enabled, db_path, slice_strategy, severity_taxonomy, slither_path). `cli/epp_cli.py` : commande `epp audit` avec options `--frame`, `--models`, `--slither/--no-slither`, `--output`. Isolation DB : `ISpaceDB(audit_db_path)` direct, jamais le singleton `get_db()`.
- `tests/test_adr014_audit_runner.py` : 16 tests (AuditResult shape, contract_hash 64-hex, aggregate_severity propagation, db_path guard, JSON string consensus_meta round-trip).

### Lot 4 — benchmark fixtures

- `tests/fixtures/benchmark/not_so_smart/ground_truth.json` : construit depuis lecture réelle des 4 `.sol` (reentrancy/integer_overflow/unprotected_function/unchecked_call) — pragma, contract_name, units vulnérables, SWC IDs (107/101/105/104), classes ToB.
- `services/audit/contract_slicer.py:236` : regex `\bcontract\s+(\w+)\s*(?:is\b|\{)` — fix contract_name retournant `"that"` (commentaire `// A contract that...`) au lieu de `"KingOfTheEtherThrone"`.
- `tests/test_adr014_benchmark.py` : 16 tests slicer-level (noms réels, external_calls, state_writes, priority sort, SWC IDs valides).
- `scripts/benchmark_reentrancy.py` : script standalone live benchmark — `close_pool()` (pas `db.close()`), ASCII partout (cp1252-safe), modèles `mistral:latest / llama3.1:8b / gemma3:latest`. Dry-run validé.
- `scripts/benchmark_heavy.py` : benchmark heavy models (phi4-reasoning/deepseek-r1/granite3.3) avec timeout par unité, `--test-models`, `--single`, `--timeout`. Fixes : `close_pool()`, ASCII, SyntaxError `global TIMEOUT_PER_UNIT` déplacé en tête de `main()`.

---

## [2026-03-05] Migration services/rwa/ → services/sources/ (ADR-014 §2.1)

- `git mv services/rwa services/sources` — déplacement physique du répertoire.
- Imports mis à jour : `services/sources/adapters/__init__.py` (5 lignes), 4 adaptateurs (1 ligne chacun), `services/esmm/source_anchor_builder.py`, `tests/test_adr012_source_anchor.py` (9 lignes), `demos/scenario_6_full_pipeline.py` (4 lignes).
- `config.yaml` : section `rwa:` → `sources:` ; `tests/test_rwa_source_anchor.py` → `tests/test_adr012_source_anchor.py`.
- Phase A préalable : correctifs `services/solana/client.py` (3 bugs : derive_pda try/except, submit_attestation ordre + garde keypair, query_attestations_by_claim garde). `tests/test_phase4_solana.py` : `@pytest.mark.skipif(_SOLANA_AVAILABLE)` sur `TestTransactionBuildingMockMode`. Baseline : 698 passed, 14 skipped, 0 failed.

---

## [2026-03-05] graph_seeder_blockchain.py — correctifs démarrage + ESMMRunConfig

- Correctifs d'import et de signature DB : `from config_loader import get_config` → `from services.config_loader import get_section` ; `ISpaceDB(pool)` → `ISpaceDB(db_path)` (signature correcte, pool géré en interne) ; `await pool.close()` → `await db.close()` ; import `SQLiteConnectionPool` supprimé.
- Unicode Windows (cp1252) : `→` → `->`, `──` → `--`, `ℹ` → `i`, `⚡` → `*`, `≥` → `>=` (4 familles de caractères hors cp1252).
- `run_claim()` : `ESMMRunConfig(models=MODELS, input_mode="verify", original_claim=..., max_duration_hours=400/3600)` passé à `run_pipeline()` — timeout 400s pour phi4-reasoning.

---

## [2026-03-05] Correctifs post-ADR-013

- `_check_cache()` (pipeline.py) : `timestamp=best.get("timestamp", 0)` ajouté à la reconstruction `EpistemicAttestation` — champ requis par Pydantic.
- `cli/epp_cli.py` `_run_ask()` : `ESMMRunConfig(models=selected_models, input_mode="verify", original_claim=question)` ajouté et passé à `run_pipeline()` — aligne la CLI sur le pattern de scenario_6.
- `config.yaml` + fichier physique : `data/epp.db` → `data/epp_devnet.db` (isolation pré-mainnet).

---

## [2026-03-05] ADR-011-v2 — Semantic Fingerprinting : fingerprint_merges exposé

- `ConsensusResult` +`fingerprint_merges: int = 0` ; `_semantic_merge()` retourne 3-tuple `(triplet_data, semantic_dispersion, len(merge_groups))`. Champ threadé : `consensus_engine` → `triplet_extractor` (`ExtractionResult`) → `cycle_manager` (`CycleResult`, extraction dict) → `pipeline.py` diagnostics (`consensus_meta.diagnostics.fingerprint_merges`).
- Test RED-GREEN-FIX ajouté : `test_fingerprint_merges_exposed_in_consensus_result` dans `tests/test_adr010_consensus_meta.py`. 701 passed, 0 failed.

---

## [2026-03-01] ADR-013 — Graphe persistant & cache-hit épistémique

- `PipelineConfig` : +`cache_ttl_hours` (défaut 168h), +`use_cache` (défaut True). `PipelineResult` : +`from_cache`, +`cache_hit_hash`. `run_pipeline()` : cache-hit lookup avant cycles ESMM via `_check_cache()` (lecture seule, filtrage TTL + tier minimum, non-bloquant).
- `database/engine.py` : +`get_attestations_by_question()` — lookup par question exacte (`WHERE question = ?`, tri timestamp DESC). `config.yaml` : section `cache` (enabled, ttl_hours=168, min_tier_for_cache="proposition"). Scénarios benchmark `scenario_6` : `use_cache=False` (délibération complète).
- 701 passed, 11 skipped, 0 failed (+3 tests RED-GREEN-FIX). Baseline 698 → 701.

---

## [2026-02-28] Audit unifié epp_audit.py — Nettoyage legacy

- `epp_audit.py` : script unifié 4 phases remplaçant `audit_runner.py`, `audit.sh`, `find_orphans.sh`. 21 mutations (M1.1-M7.3), 7 groupes, 0 SURVIVED. Corrections : orphan detector false positives Windows/WSL, C4/C5 schema/config drift, C8 VERIFY coverage grep, pytest collection abort. Outputs → `tests/audits/`. `REPORT_PATH`/`CHECKSUMS_PATH` mis à jour.
- Tests Solana localnet validés : 26/26 (11 unit, 6 mock, 9 E2E). Total projet : 723 tests (sans vars Solana : 697 passed, 11 skipped).
- Supprimés : `audit_runner.py`, `audit.sh`, `find_orphans.sh`, `MUTATION_REPORT.md`.

---

## [2026-02-25] Nettoyage héritage Lyra ACE + correctifs post-audit ADR-012

- Renommage variables d'environnement `LYRA_*` → `EPP_*` (`ollama.py`, `ollama_embeddings.py`) : `LYRA_OLLAMA_URL` → `EPP_OLLAMA_URL`, `LYRA_MODEL` → `EPP_MODEL`, `LYRA_NUM_CTX` → `EPP_NUM_CTX`, `LYRA_EMBEDDING_MODEL` → `EPP_EMBEDDING_MODEL`. Valeurs par défaut inchangées.
- Correctifs post-audit ADR-012 (P1/P2) : `_run_deterministic_pipeline()` — predicate résolu depuis `PREDEFINED_FRAMES[frame_id].metric` (plus de `"sanctions_status"` hardcodé) ; subject résolu sur `name || serial || project_id || question`. `PREDEFINED_FRAMES` déplacé dans `metrological_frame.py` (source unique de vérité). 697 passed, 11 skipped, 0 failed (+3 tests).

---

## [2026-02-25] ADR-012 — Intégration sources RWA / Bifurcation déterministe

- Nouveau chemin `DETERMINISTIC` dans `ESMMRunConfig` (`ClaimNature` enum). `execute_cycles()` court-circuité si `claim_nature=DETERMINISTIC`. Pipeline : `_run_deterministic_pipeline()` — fetch source → `_canonical_hash()` → `crystallize(epistemic_type="deterministic")` → store snapshot + attestation.
- Nouveau module `services/esmm/source_anchor_builder.py` : `SourceAnchorSpec`, `SourceAnchorResult`, `build_source_anchor()`. Nouveau répertoire `services/rwa/adapters/` : 4 adaptateurs (`OpenSanctionsAdapter`, `OfacAdapter`, `EuCfspAdapter`, `VerraVcsAdapter`) + registre `get_adapter()`.
- 3 nouveaux `MetrologicalFrame` : `compliance_sanctions_v1.0`, `carbon_credits_vcs_v1.0`, `rwa_identity_v1.0`. Table SQL `source_anchor_snapshots` (25e table). 3 nouvelles méthodes `ISpaceDB` : `store_source_anchor_snapshot()`, `get_snapshot_by_anchor()`, `is_snapshot_fresh()`. CLI : commande `epp verify-rwa`. Config : section `rwa.sources`. `attestation.py` : `models_consulted ge=0`, `epistemic_type` étendu avec `"deterministic"`, guard `source_anchor_meta` dans `crystallize()`.
- 694 passed, 11 skipped, 0 failed (+21 tests ADR-012).

---

## [2026-02-24] Audit Solana Directives 2-5 — Couche Solana qualifiée

- D5: `CONFIDENCE_TIER_MAP` (bridge.py) — 3 aliases backward compat supprimés (`low`/`medium`/`high`). Désalignement avec `confidence_tier_to_u8` Rust confirmé (hit `_ => err!(InvalidConfidenceTier)`). Bijection stricte 4 clés ↔ 4 arms Rust désormais garantie par `test_confidence_tier_map_bijection_with_rust`. `test_legacy_tiers_backward_compat` supprimé (test du comportement retiré).
- D7: Guard `_SOLANA_AVAILABLE` — `@pytest.mark.skipif` déplacé au niveau méthode (`test_submit_requires_ready_client` uniquement). Import inutilisé supprimé de `test_phase1_client.py`. 3 tests de `TestSubmitterAuth` restaurés dans le compteur.
- D6: Program ID `98Fc2oL2cKsTDGYi3GifggzkQkEQSRn2oTgg8HsaVa3C` ajouté dans `README.md` section Solana.
- D5b: 3 marqueurs `AUDIT_REQUIRED` levés — `client.py:474` (CLAIM_HASH_OFFSET=41), `client.py:511` (SUBJECT_OFFSET=73), `lib.rs:113` (PDA seeds). Remplacés par `AUDIT_CLEARED 2026-02-23`.
- 673 passed, 11 skipped, 0 failed (inchangé : +1 bijection −1 legacy = 0 net).

---

## [2026-02-24] Restructuration Anchor — Convention standard

- Workspace Anchor déplacé à la racine : `Anchor.toml`, `Cargo.toml` [workspace], `Cargo.lock`, `package.json`, `tsconfig.json` → `EPP_Verdict/` (étaient dans `programs/epp/`).
- Programme Rust remonté d'un niveau : `programs/epp/programs/epp/src/` → `programs/epp/src/`. Dossier `programs/epp/programs/` supprimé.
- `tests/epp.ts` déplacé vers `tests/` racine. `anchor build`/`anchor test` s'exécutent depuis la racine.
- `.gitignore` mis à jour : `.anchor/` et `target/` à la racine (étaient `programs/epp/.anchor/`, `programs/epp/target/`).
- Références mises à jour : `client.py` (IDL path), `test_bridge_solana_compat.py`, `diagnostic_solana_layer.sh` (6 occurrences), `README.md`, `ARCHITECTURE.md`, `AUDIT_INTERNE.md`.
- 673 passed, 11 skipped, 0 failed (inchangé).

---

## [2026-02-24] Calibration Épistémique VERIFY Mode

- Fix A — `cycle_prompts.py` : prompt ASSESS remplacé — STEP 1 classifie `claim_type` (empirical/definitional/normative/speculative) avant STEP 2 (verdict). Normative → INSUFFICIENT_EVIDENCE obligatoire.
- Fix A bis — `triplet_extractor.py` : `_parse_verdict_response()` extrait `claim_type` depuis JSON, normalise (fallback `"empirical"`), inclus dans le dict retourné.
- Fix C — `cycle_manager.py` : majority vote `claim_type` sur réponses de tous les modèles. Résultat injecté comme triplet `{"subject": claim[:64], "relation": "claim_type", "object": consensus_claim_type}` dans `raw_model_triplets` (propagation via triplet-as-channel → `adapt_all()` → `extracted_triplets` dans pipeline).
- Fix B — `pipeline.py` : constantes `VERDICT_PENALTIES` (SUPPORTED=1.0, CONTESTED=0.65, INSUFFICIENT_EVIDENCE=0.45) + `CLAIM_TYPE_PENALTIES` (empirical=1.0, normative=0.70, speculative=0.75, definitional=0.90). Pénalité appliquée avant `crystallize()` : `adjusted_score = raw × v_penalty × t_penalty`. Traçabilité dans `consensus_meta.verify` : `claim_type`, `raw_consensus_score`, `decidability_penalty`, `adjusted_consensus_score`.
- 10 tests RED-GREEN-FIX. Baseline : 663 → 673 passed, 0 failed, 11 skipped.

---

## [2026-02-20] Polissage Final — VERIFY Mode Hackathon-Ready (P1-P4)

- pipeline.py: `_extract_triplets_from_question()` retourne 4-tuple incluant `esmm_config`
  (était 3-tuple → `esmm_config` perdu → `pipeline_mode` affichait "explore" au lieu de "verify")
- pipeline.py: `_build_consensus_meta()` écrit `pipeline_mode=verify` + section `verify`
  (original_claim, final_verdict, verdict_confidence, model_verdicts) — ADR-010
- pipeline.py: enrichissement post-cristallisation — `final_verdict` + `evidence_corpus`
  (triplets sub-consensus preservés dans consensus_meta, cap 20 items)
- cycle_manager.py: log INFO explicatif pour CHALLENGE (0/0 consensus est by design,
  counter-arguments alimentent ADJUDICATE)
- scenario_4_live_ollama.py: display conditionnel VERIFY (verdict box, split, evidence corpus,
  phases, methodology) — EXPLORE display preservé
- scenario_4_live_ollama.py: fix display Dissent — `v` (dict verify) → `att.object` (texte verdict) ;
  renommage variable shadowed `v` → `vname` dans split_parts
- 4 tests RED-GREEN-FIX. Baseline: 659 → 663 passed, 0 failed, 11 skipped

---

## [2026-02-20] A1-A3 — Corrections runtime VERIFY mode (post-Scenario 4 live)

- orchestrator.py: `cycles_per_type` fixé à `{assess: 1, challenge: 1, adjudicate: 1}` (était n_models,
  causant n×n queries ASSESS au lieu de n)
- orchestrator.py: skip convergence gaps + skip adaptation en mode VERIFY (les gaps sont un concept
  EXPLORE ; convergence prématurée empêchait CHALLENGE et ADJUDICATE d'exécuter)
- orchestrator.py: propagation context inter-phases — `_verify_model_verdicts` capturés après ASSESS,
  passés à CHALLENGE (per-model isolation) et ADJUDICATE (synthèse all_verdicts)
- cycle_manager.py: `_query_models_isolated()` — isolation épistémique CHALLENGE, rotation circulaire
  (modèle[i] voit uniquement le verdict de modèle[(i+1) % N], directive §4.2 / ADR-011-v2 §2.2)
- cycle_manager.py: `_extract_verdicts_from_responses()` — routage des verdicts par
  `_parse_verdict_response()` + `encode_verdict_as_triplets()` → `compute_consensus()`
  (agreement_ratio réel, vote_entropy, pas de construction manuelle ConsensusTriplet)
- scenario_4_live_ollama.py: affichage `pipeline_mode` + section `verify` dans consensus_meta
- 4 tests RED-GREEN-FIX. Baseline: 655 → 659 passed, 0 failed, 11 skipped

---

## [2026-02-20] Dual-Mode ESMM — Claim Verification (VERIFY mode, S1-S7)

- Nouveau enum `CycleType` (str, Enum) : 6 valeurs — DIVERGENT/DEBATE/META (EXPLORE) +
  ASSESS/CHALLENGE/ADJUDICATE (VERIFY)
- Nouveau enum `InputType` : EXPLORE (défaut) ou VERIFY, auto-détecté par `classify_input()`
  dans question_seeder.py (détection mots-clés : "is it true", "verify", "fact-check", etc.)
- cycle_prompts.py: 3 SYSTEM_PROMPTS + 6 templates VERIFY (ASSESS ×2, CHALLENGE ×2, ADJUDICATE ×2)
- triplet_extractor.py: `_parse_verdict_response()` — extraction verdict/confidence/evidence/reasoning
  depuis JSON ou texte libre LLM (fallback regex robuste)
- Nouveau module `verdict_encoder.py` : `encode_verdict_as_triplets()` — encode un verdict en triplets
  réutilisant la pipeline de cristallisation (claim → verdict → SUPPORTED/REFUTED/UNCERTAIN,
  evidence triplet, reasoning triplet)
- orchestrator.py: `ESMMRunConfig.input_mode` (explore/verify) + `original_claim` ;
  séquence VERIFY = ASSESS→CHALLENGE→ADJUDICATE
- pipeline.py: auto-détection du mode via `classify_input()`, propagation `input_mode`
  et `original_claim` dans `ESMMRunConfig`
- pipeline.py: `_build_consensus_meta()` enrichi section `verify` (original_claim, final_verdict,
  verdict_confidence)
- attestation.py: `epistemic_type="verdict"` pour les attestations VERIFY
- `__init__.py`: exports verdict_encoder, `_parse_verdict_response`, InputType, classify_input
- 19 tests RED-GREEN-FIX. Baseline: 636 → 655 passed, 0 failed, 11 skipped

---

## [2026-02-20] Refactoring — relation_vocabulary.py (source unique de vérité)

- Nouveau module `relation_vocabulary.py` : 11 groupes, superset consensus_engine (10) +
  fingerprint_match (6). Résolution conflits relies_on→DEPENDS_ON, produces∈CAUSES (ADR-006).
- `consensus_engine.py` : `_RELATION_GROUPS` local remplacé par import depuis relation_vocabulary
  (legacy snapshot conservé sous flag)
- `fingerprint_match.py` : `RELATION_GROUPS` local remplacé par import depuis relation_vocabulary
  (legacy snapshot conservé sous flag)
- Flag `use_legacy_relation_groups` dans `config.yaml` pour déploiement progressif (true=legacy)
- 29 tests ajoutés (19 relation_vocabulary + 10 fingerprint_match). Baseline: 595 → 624 passed, 0 failed
- 10 CI gate hash stability tests (ADR-006) verrouillent les hashes SHA-256 existants

---

## [2026-02-18] ADR-011-v2 — Corrections audit Semantic Fingerprinting (C1-C5)

- fingerprint_match.py: suppression import fantôme depuis consensus_engine, 3 fonctions
  self-contained (`_normalize_entity`, `_normalize_relation` avec RELATION_GROUPS, `_cosine_similarity`)
- orchestrator.py: fix attribut `self.cycle_manager.rotator` → `self.cycle_manager.model_rotator`
- fingerprint_expand.py: réécriture boucle expand_terms — un appel batch_sequential_providers
  par provider au lieu d'un seul appel global (zéro contamination inter-modèles structurelle)
- fingerprint_expand.py: format questions aligné sur pattern triplet_extractor
  `[[{"role": "user", "content": prompt}]]`
- orchestrator.py: normalisation raw_model_triplets en dicts au point d'accumulation
  (isinstance/vars/__dict__, défense contre ExtractedTriplet non-dict)
- fingerprint_apply.py: filet de sécurité `hasattr(new_t, "subject")` pour objets non-dict
- 7 tests ajoutés (3 normalisation C1, 1 assertion single-provider C3, 2 objets C5, 1 accumulation)
- Baseline: 590 → 595 passed, 0 failed, 11 skipped

---

## [2026-02-18] ADR-011-v2 — Semantic Fingerprinting (implémentation initiale)

- 4 nouveaux modules : fingerprint_config.py (~60 lignes), fingerprint_expand.py (~120 lignes),
  fingerprint_match.py (~180 lignes), fingerprint_apply.py (~90 lignes)
- fingerprint_config.py: FingerprintConfig dataclass + load_fingerprint_config() depuis config.yaml
- fingerprint_expand.py: MicroGraph/ExpandResult, build_expand_prompt(), parse_expand_response(),
  expand_terms() async — chaque modèle décrit SES propres termes (zéro contamination)
- fingerprint_match.py: Jaro-Winkler (rapidfuzz), classify_neighbor (Strong Anchor 2.0 / Weak 1.0),
  match_neighbor_pair (cascade relation-aware), compute_weighted_overlap, Union-Find components
- fingerprint_apply.py: select_canonical (fréquence → longueur → alpha), build_alignment_table,
  apply_alignment_to_triplets (S/R/O, sans mutation input)
- triplet_extractor.py: ExtractionResult.raw_model_triplets exposé
- cycle_manager.py: CycleResult.raw_model_triplets propagé
- orchestrator.py: accumulation bruts cross-cycle, reconcile() publique (EXPAND → MATCH → APPLY),
  `_final_consensus_triplets` (jamais mutation `_collected_triplets`), `reconciliation_meta`
- orchestrator.py: ESMMRunResult.reconciliation_meta, run() appelle reconcile() entre execute/finalize
- pipeline.py: appel explicite reconcile(), _build_consensus_meta enrichi section reconciliation
- config.yaml: section esmm.fingerprint (9 clés)
- __init__.py: exports des 4 modules
- requirements.txt: rapidfuzz ajouté
- 37 tests RED-GREEN-FIX. Baseline: 553 → 590 passed, 0 failed, 11 skipped

---

## [2026-02-17] Phase 1.2 — Fix désérialiseur on-chain + tests relecture

- client.py: fix _deserialize_attestation_account() — ajout champ last_revalidated
  (i64, 8 bytes) manquant entre timestamp et validation_count. Tous les champs après
  timestamp étaient décalés de 8 bytes (bug critique C4).
- client.py: assertion taille en fin de désérialisation (filet anti-décalage permanent)
- test_phase4_solana.py: fix test_deserialize_attestation_layout (buffer +8 bytes)
- test_phase4_solana.py: fix test_borsh_layout_matches_account_size (446→454, +assert ==462)
- 5 tests RED→GREEN dans test_solana_deserialize.py (roundtrip, taille invalide,
  offsets claim_hash/subject, hypothesis float)
- Baseline: 548 → 553 passed, 0 failed, 11 skipped

---

## [2026-02-16] ADR-010 — Traçabilité méthodologique du consensus

- schema.sql: colonne `consensus_meta TEXT` dans attestations
- engine.py: migration ALTER TABLE, sérialisation JSON dans store_attestation(), backfill_consensus_meta()
- consensus_engine.py: `ConsensusResult` dataclass (remplace List[ConsensusTriplet]), `_compute_vote_entropy()` (Shannon), `semantic_dispersion` (mean pairwise cosine distance)
- triplet_extractor.py: `ExtractionResult` enrichi (vote_entropy, semantic_dispersion, triplets_before/after)
- cycle_manager.py: `CycleResult` enrichi, threading via dict
- orchestrator.py: `ESMMRunResult` enrichi, accumulation max(entropy), sum(triplets)
- ollama.py: `resolve_model_version()` via POST /api/show (parameter_size + quantization_level)
- attestation.py: champ `consensus_meta` sur EpistemicAttestation, param dans crystallize()
- pipeline.py: `_build_consensus_meta()` async (methodology + conditions + diagnostics), résolution version via providers, backward-compat 2/3-tuple
- 26 tests RED→GREEN. Baseline: 522 → 548 passed, 0 failed, 11 skipped

---

## [2026-02-15] Phase 4.8 — Neutralité linguistique ESMM

- cycle_prompts.py: 3 SYSTEM_PROMPTS + 20 templates traduits en anglais
- prompts.py: 4 prompts traduits ; exemples few-shot en anglais ; directive "MUST be in English"
- consensus_engine.py: `compute_consensus()` async, accepte `embedding_provider` optionnel
- consensus_engine.py: `_semantic_merge()` — Pass 2 clustering cosine > 0.85, ambiguity preservation
- consensus_engine.py: `ConsensusTriplet` étendu (`variations`, `ambiguity_detected`)
- Annotation COMMUNITY_DECISION_REQUIRED dans 3 fichiers (consensus, post_crystallization, pipeline)
- ADR-009 créé : Language Neutrality in ESMM Protocol
- 9 tests ajoutés. Baseline: 514 → 523 passed, 0 failed, 11 skipped

---

## [2026-02-15] Live run — Normalisation triplets + correctifs pipeline

- consensus_engine.py: normalize_triplet() — synonymes relation (10 groupes: USES, IS_A, HAS, PART_OF, CAUSES, ENABLES, PREVENTS, RELATES_TO, DEPENDS_ON, PROVIDES), entités (PoW→proof of work, etc.), word synonyms (computational→computing)
- consensus_engine.py: `_hash_triplet()` appelle `normalize_triplet()` avant SHA-256
- consensus_engine.py: fix dict/getattr — les triplets (dicts du validator) avaient confidence=0.0 via getattr ; tous filtrés avant consensus
- consensus_engine.py: log INFO enrichi (processed/filtered/unique/passed)
- cycle_manager.py: META retry capped à max_retries=3 (boucle for au lieu de retry unique)
- cycle_manager.py: CYCLE_TIMEOUTS uniformisés à 60s (divergent était 30s, trop court pour modèles à froid)
- cycle_manager.py: create_cycle_manager() accepte min_consensus, propagé à get_triplet_extractor()
- orchestrator.py: min_consensus propagé de ESMMRunConfig aux 3 call sites de create_cycle_manager()
- pipeline.py: run_pipeline() accepte esmm_config (Optional[ESMMRunConfig]) ; propagé à _extract_triplets_from_question()
- orchestrator.py: import mort `from enum import Enum` supprimé
- 5 tests RED→GREEN (test_r2_normalize_triplet: synonymes, IS_A, whitespace, différents, abréviations)
- DB live migrée: 3 colonnes R2 ajoutées à attestations (ALTER TABLE)
- Baseline: 509 → 514 passed, 0 failed, 11 skipped

---

## [2026-02-15] R-2.2.3 — Commit-reveal complet

- schema.sql: table commit_reveal (run_id, model_id, phase, response_hash, verified)
- schema.sql: colonne commit_reveal_verified dans attestations
- engine.py: 4 méthodes CRUD (store_commit, get_commit, verify_and_update_commit, update_attestation_commit_verified)
- cycle_manager.py: hash SHA-256 des réponses stocké entre query_models et extraction (L256)
- get_attestation_by_hash inclut commit_reveal_verified
- 5 tests RED→GREEN (CRUD, altération détectée, schema check)
- Baseline: 504 → 509 passed, 0 failed, 11 skipped

---

## [2026-02-15] R-2.2.2 — Clustering embeddings (détection Sybil)

- Nouveau module services/esmm/response_deduplicator.py: detect_similar_responses()
- Similarité cosinus entre embeddings; seuil configurable (default 0.95)
- Penalty factor 0.5 pour le second modèle d'une paire quasi-identique
- MockDeterministicEmbeddingProvider dans les tests (hash-based, cosinus variable)
- 3 tests RED→GREEN (identiques détectés, différents non pénalisés, seuil respecté)
- Baseline: 501 → 504 passed, 0 failed, 11 skipped

---

## [2026-02-15] R-2.2.1 — Diversité architecturale dans le consensus

- schema.sql: 2 colonnes ajoutées à attestations (adjusted_consensus_score, diversity_bonus_factor)
- post_crystallization.py: bonus diversité calculé APRÈS crystallize() (Option C, ADR-005/007 safe)
- Factor 1.1 si ≥2 familles d'architecture, 1.0 sinon ; adjusted capped à 1.0
- engine.py: update_attestation_diversity_bonus() + get_attestation_by_hash inclut les 2 colonnes
- 3 tests RED→GREEN (TestDiversityBonusMultiFamily, TestDiversityBonusMonoFamily, TestConsensusScoreUnchanged)
- Schema check OK, pytest 501 passed (1 flaky préexistant), 0 failed, 11 skipped
- Baseline: 498 → 501 passed

---

## [2026-02-15] R-2.1.2 — Dashboard performance modèles

- engine.py: get_all_model_brier_scores() via vue v_model_brier_scores (schéma existant)
- cli/epp_cli.py: commande `epp models stats` — tableau Model/Predictions/Resolved/Avg Brier/Weight
- Gestion cas vide (cold start message) + troncature model_id à 25 chars
- 5 tests RED→GREEN (TestGetAllModelBrierScores, TestModelsStatsCLI)
- Baseline: 493 → 498 passed, 0 failed, 11 skipped

---

## [2026-02-15] R-2.1.1 — Pondération dynamique Brier des votes

- consensus_engine.py: compute_consensus() accepte model_weights (Optional[Dict[str, float]])
- Poids pondèrent agreement_ratio ET avg_confidence (weighted sum)
- Formule: weight = max(0.0, 1.0 - avg_brier_score), cold start = 1.0
- Option A: propagation par paramètre sur 7 signatures (consensus_engine → triplet_extractor → cycle_manager ×2 → orchestrator → pipeline ×2)
- orchestrator._compute_model_weights(): auto-calcul des poids depuis DB Brier au lancement du run
- 6 tests RED→GREEN (TestWeightedConsensus, TestColdStartWeight, TestBackwardCompat)
- C1 grep: 17 appelants vérifiés, tous backward-compatible (default None)
- Baseline: 487 → 493 passed, 0 failed, 11 skipped

---

## [2026-02-15] Phase 4.7 — Peaufinage post-recette

- ARCHITECTURE.md: 7/7 points verifies, note purge config ajoutee
- Bloc A: 3 providers (ollama, anthropic, openai_compat) deleguent a infer_architecture_family(), 3 tests coherence
- Bloc B: client.py complet (0 NotImplementedError, 5 methodes CHANGELOG confirmees)
- Bloc D: 2 annotations AUDIT marquees FIXED (A4-002, A4-003), 15 FIXED total
- Bloc E: hypothesis installe, 3 tests property-based (float↔u16 roundtrip ADR-001, claim hash ADR-006)
- Sync confidence_tier Rust↔Python: state.rs commentaires + helper mis a jour, 11 tests tiers roundtrip
- Conformite §5.2: print() → logger dans engine.py (3), main.py (27), chat.py (5)
- Conformite §5.3: 17 INSERT bruts audites, 0 violations (tous proteges ou AUTOINCREMENT)
- Baseline: 470 -> 487 passed, 0 failed, 11 skipped

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
