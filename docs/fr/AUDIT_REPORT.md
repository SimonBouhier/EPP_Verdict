# Rapport d'Audit Interne — EPP_Verdict

**Date** : 2026-02-11
**Auditeur** : Claude Code (supervisé)
**Méthodologie** : `docs/To_do_list/AUDIT_INTERNE.md` v1.0
**Périmètre** : 10 angles (A1-A10), fichiers P0-P2

---

## Résumé

| Sévérité | Nombre |
|----------|--------|
| 🔴 CRITIQUE | 38 |
| 🟡 FRAGILE | 124 |
| 🟢 ACCEPTABLE | 14 |
| ⚪ INFO | 13 |

**Fichiers les plus impactés** : `engine.py` (22 trouvailles), `pipeline.py` (11), `pool.py` (8), `orchestrator.py` (7), `bridge.py`/`client.py` (12)

---

## A1 — Singletons et État Global

### 🔴 CRITIQUE

**[A1-001]** `database/engine.py` — `_db_instance` via `get_db()`
Race condition : si deux coroutines appellent `get_db()` avec des `db_path` différents, le second appel obtient l'instance du premier sans avertissement. Le paramètre `db_path` est ignoré après la première initialisation.

**[A1-002]** `services/providers/ollama.py` — `_ollama_instance`
Même pattern. Un changement de `base_url` ou `model_name` après initialisation est silencieusement ignoré.

**[A1-003]** `services/providers/ollama_embeddings.py` — `_ollama_embedding_instance`
Idem. Si le modèle d'embedding change entre deux appels, l'ancien est renvoyé.

**[A1-004]** `app/api/chat.py` — `_client_instance` (llm_client)
Singleton sans vérification des paramètres. Changements de modèle ou d'URL ignorés.

**[A1-005]** `app/api/chat.py` — `_multi_model_instance`
Même problème que A1-004 pour l'instance multi-modèles.

### 🟡 FRAGILE

**[A1-006]** `database/pool.py` — `_pool_instance` : corrigé en Phase 3.1 (vérifie `db_path`), mais `pool_size` ignoré si l'instance existe déjà.
**[A1-007]** `database/pool.py` — `_concept_cache` : dict global sans TTL ni invalidation après mutations DB.
**[A1-008]** `database/pool.py` — `_concurrency_limiter` : Semaphore global, pas lié au pool spécifique.

### 🟢 ACCEPTABLE

**[A1-009]** `services/config_loader.py` — `_config` : Bien conçu, `reset_config()` existe, chargement idempotent.

---

## A2 — Exceptions Avalées

### 🔴 CRITIQUE

**[A2-001]** `database/pool.py` — `close_pool()` : `except Exception: pass` lors de la fermeture des connexions. Si une connexion est corrompue ou verrouillée, l'erreur est invisible.

**[A2-002]** `database/pool.py` — `_cleanup_stale()` : Exceptions avalées pendant le nettoyage. Une connexion zombie peut persister indéfiniment.

**[A2-003]** `app/api/chat.py` — bloc mémoire sémantique : `except Exception as e` loggé en warning, mais si la mémoire renvoie des données corrompues avant l'exception, elles ne sont pas nettoyées.

**[A2-004]** `tests/conftest.py` — `reset_db_singletons` : `except: pass` nu qui masque les erreurs de teardown entre tests, causant potentiellement une contamination d'état inter-tests.

### 🟡 FRAGILE (20 trouvailles)

**[A2-005]** `engine.py` — `initialize()` : 8 blocs `except: pass` pour les migrations ALTER TABLE. Individuel­lement acceptables (colonne déjà existante), mais collectivement dangereux : une erreur de syntaxe SQL dans une migration est invisible.
**[A2-006]** `engine.py` — `get_stats()` : retourne `{}` sur exception — l'appelant ne distingue pas "pas de données" de "erreur".
**[A2-007]** `engine.py` — `get_multi_neighbors()` : retourne `[]` sur exception.
**[A2-008]** `engine.py` — `find_similar_concepts()` : retourne `[]` sur exception — une erreur d'embedding passe inaperçue.
**[A2-009]** `engine.py` — JSON decode dans plusieurs méthodes : `json.loads()` dans un try/except retournant valeur par défaut.
**[A2-010]** `pipeline.py` — `errors.append(str(e))` : les erreurs sont accumulées mais le pipeline continue (voir aussi A9-010).
**[A2-011]** `pipeline.py` — post_crystallization_hook : exception → warning, attestation stockée quand même.
**[A2-012]** `orchestrator.py` — timeout de cycle : exception logguée, cycle sauté, run continue.
**[A2-013]** `cycle_manager.py` — extraction de triplets : échecs individuels accumulés sans arrêt.
**[A2-014]** `triplet_extractor.py` — parsing LLM : JSON invalide → retourne liste vide.
**[A2-015 à A2-024]** Divers blocs `except Exception` retournant `None`, `[]`, `0`, ou `{}` dans `engine.py`, `memory.py`, `injector.py`, `sessions.py`.

---

## A3 — Cohérence des Interfaces

### 🔴 CRITIQUE

**[A3-001]** `services/esmm/seed_injector.py` → `add_concept()` : Appel avec `embedding=vector` mais sans `embedding_model`. Depuis Phase 0.2, `add_concept()` exige `embedding_model` quand `embedding` est fourni → `ValueError` garanti au runtime.

**[A3-002]** `services/esmm/populate_graph.py` → `add_concept()` : Même problème qu'A3-001.

**[A3-003]** `services/esmm/question_seeder.py` → `add_concept()` : Même problème qu'A3-001 (3ème occurrence).

**[A3-004]** `services/esmm/triplet_extractor.py` — SQL `ON CONFLICT` : Clause invalide dans un INSERT qui ne correspond pas au schéma de la table cible. Silencieux car le chemin est rarement atteint.

### 🟡 FRAGILE

**[A3-005]** `pipeline.py` → `store_attestation()` : Attend un dict, pas un objet Pydantic. Conversion implicite via `model_dump()`.
**[A3-006]** `post_crystallization.py` → `record_model_prediction()` : Noms de params à vérifier si la signature change.
**[A3-007]** `post_crystallization.py` → `log_tier_transition()` : Corrigé Phase 3.1 (`from_tier/to_tier`), mais fragile si renommé.
**[A3-008]** `pipeline.py` → `upsert_relations_batch()` : Le format du dict doit matcher exactement — pas de validation intermédiaire.
**[A3-009]** `orchestrator.py` → `create_esmm_run()` : Vérifier que la double création est bien éliminée.
**[A3-010]** Conversions de type implicites (float→str, Optional manquants) dans plusieurs appels ISpaceDB.

---

## A4 — SQL : Intégrité et Sécurité

### 🔴 CRITIQUE

**[A4-001]** `engine.py` — `upsert_relations_batch()` : Le champ `relation_type` est perdu lors de INSERT OR REPLACE sur la table `relations`. La clé primaire est `(source, target)`, donc un REPLACE sur un doublon écrase le `relation_type` existant avec le nouveau, sans vérifier si c'est le même type.

**[A4-002]** `engine.py` — INSERT OR REPLACE sur `concepts` : Perd les métadonnées existantes (`created_at`, anciens embeddings) lors du remplacement. Aucun MERGE intelligent.

**[A4-003]** `engine.py` — Colonne `submission_status` : Référencée dans `update_attestation_submission_status()` mais absente du schéma `schema.sql`. La méthode crashera si appelée.

**[A4-004]** `engine.py` — UPDATE sur `attestations` : Le design est append-only (cf. ARCHITECTURE.md), mais `update_attestation_solana_tx()` fait un UPDATE. Incohérence entre le design documenté et le code.

### 🟡 FRAGILE

**[A4-005]** `engine.py` — Dual INSERT (concepts + relations) non-atomique : pas de transaction explicite englobant les deux.
**[A4-006]** `engine.py` — Race condition : deux requêtes concurrentes faisant INSERT OR REPLACE sur le même concept peuvent interleaver.
**[A4-007]** `engine.py` — f-strings SQL : Utilisées pour les clauses WHERE dynamiques dans `get_multi_neighbors()`, `find_similar_concepts()`. Les valeurs viennent de paramètres internes (pas d'input user direct), mais le pattern est fragile.
**[A4-008]** `schema.sql` — Pas d'index sur `attestations(subject)` malgré `get_attestations_by_subject()`.
**[A4-009]** `schema.sql` — Pas d'index sur `graph_deltas(session_id, applied_at)` malgré `rollback_deltas()`.
**[A4-010]** `engine.py` — `record_model_prediction()` : INSERT brut sans OR IGNORE — doublon → crash.
**[A4-011]** `engine.py` — Commit implicite aiosqlite sans rollback explicite dans le except de plusieurs méthodes.
**[A4-012 à A4-018]** Divers : manque de contraintes CHECK, foreign keys non activées, transactions implicites.

---

## A5 — Lifecycle Async

### 🔴 CRITIQUE

**[A5-001]** `services/esmm/entity_resolver.py` — `EntityResolver` : La propriété `db` est accédée avant `initialize()`. Si `resolve()` est appelé avant init, crash avec `AttributeError`.

### 🟡 FRAGILE

**[A5-002]** `services/providers/ollama.py` — `httpx.AsyncClient` créé lazy (dans `_ensure_client()`) mais sans lock async → deux coroutines concurrentes peuvent créer deux clients.
**[A5-003]** `services/providers/ollama.py` — `ModelRotator` : Crée un `httpx.AsyncClient` mais `close()` n'est jamais appelé — pas de `__aexit__`.
**[A5-004]** `services/esmm/cycle_manager.py` — `CycleManager` : Crée des providers internes qui ne sont jamais fermés.
**[A5-005]** `database/pool.py` — `acquire()` : Si `aiosqlite.connect()` échoue, la connexion n'est pas retirée du pool count.
**[A5-006]** `app/main.py` — Shutdown : `close_db()` et `close_pool()` sont appelés mais pas `close()` sur les providers httpx.
**[A5-007 à A5-020]** Divers : timeouts sans cleanup, contextes async non gérés, coroutines potentiellement non-awaited.

---

## A6 — Code Mort et Chemins Inatteignables

### 🔴 CRITIQUE

**[A6-001]** `app/embeddings.py` — Marqué DEPRECATED dans ARCHITECTURE.md mais **activement importé** par :
- `app/api/chat.py` (import direct, utilisé pour embeddings)
- `services/esmm/seed_injector.py`
- `services/esmm/populate_graph.py`
- `services/esmm/entity_resolver.py`

Le module deprecated n'est pas éliminable car 4 fichiers en dépendent.

**[A6-002]** `services/esmm/entity_resolver.py` — **IMPORT CASSÉ** : importe `get_embedding` (singulier) mais le module `app/embeddings.py` n'exporte que `get_embeddings` (pluriel). → `ImportError` au runtime dès que `entity_resolver` est importé.

**[A6-003]** `app/model_rotator.py` — Marqué "remplacé par multi_provider_rotator" mais encore importé par `app/api/chat.py`.

**[A6-004]** `app/multimodel.py` — Endpoints FastAPI multi-modèles couplés Ollama, potentiellement enregistrés sur le router mais non fonctionnels avec le nouveau provider layer.

### 🟡 FRAGILE

**[A6-005]** `services/esmm/orchestrator.py` — `run_esmm_protocol()` et `resume_esmm_protocol()` : fonctions helper potentiellement non appelées (remplacées par pipeline.py).
**[A6-006]** `services/esmm/gap_detector.py` — Plusieurs méthodes exportées mais jamais appelées hors tests.
**[A6-007]** `services/esmm/coverage_analyzer.py` — Shannon entropy calculée mais résultat jamais consommé dans le flux principal.
**[A6-008 à A6-015]** TODO/FIXME/HACK markers non résolus (12 occurrences dans services/).
**[A6-016 à A6-025]** Imports inutilisés dans divers fichiers services/.
**[A6-026 à A6-037]** Branches else inatteignables, variables assignées mais non lues, constantes définies mais non utilisées.

---

## A7 — Qualité des Tests

### 🔴 CRITIQUE

**[A7-001]** `tests/test_phase3_*.py` — **40+ instances de `asyncio.run()`** à l'intérieur de fonctions de test. Conflictuel avec `pytest-asyncio` mode auto configuré dans `pytest.ini`. Fonctionne par accident mais fragile : tout changement de configuration pytest cassera ces tests.

**[A7-002]** `tests/test_phase02_*.py` — Tests "import-only" : certains tests se contentent d'importer un module et de vérifier que l'import ne crashe pas, sans tester de comportement.

**[A7-003]** `tests/test_phase3_orchestrator.py` — Mocking massif : `ESMMOrchestrator` entièrement mocké, le test vérifie que le mock est appelé correctement mais pas que l'orchestrateur fonctionne.

**[A7-004]** `tests/test_phase3_pipeline.py` — Patches qui remplacent l'implémentation réelle : `@patch("services.esmm.pipeline.ESMMOrchestrator")` → le pipeline n'est jamais testé avec un vrai orchestrateur.

**[A7-005]** `tests/test_phase1_client.py` — Client Solana testé uniquement en mode mock. Aucun test avec un vrai cluster (même devnet).

**[A7-006]** `tests/test_phase3_post_crystallization.py` — `log_tier_transition` mocké, on vérifie l'appel mais pas l'effet en DB.

**[A7-007]** `tests/test_phase02_search.py` — Assertions structurelles uniquement (`assert isinstance(result, list)`) sans vérifier le contenu sémantique.

**[A7-008]** `tests/conftest.py` — `reset_db_singletons` avale les exceptions (cf. A2-004), permettant aux tests de passer même si le teardown échoue.

### 🟡 FRAGILE (22 trouvailles)

**[A7-009 à A7-015]** Assertions faibles : `assert result is not None`, `assert len(result) > 0` sans vérifier les valeurs.
**[A7-016 à A7-020]** Tests dépendants de l'ordre : fixtures partagées modifiant l'état global.
**[A7-021 à A7-025]** Cleanup insuffisant : DB temporaires non supprimées, singletons non réinitialisés.
**[A7-026 à A7-030]** Tests dupliqués testant la même chose avec des noms différents.

### 🟢 ACCEPTABLE

**[A7-031]** `tests/test_phase2_confidence.py` — Tests de tiers bien structurés avec assertions précises.
**[A7-032]** `tests/test_phase3_post_crystallization.py` — Hook testé avec des cas limites.
**[A7-033]** `tests/test_phase3_question_seeder.py` — Bonne isolation, assertions sémantiques.
**[A7-034]** `tests/test_phase1_bridge.py` — Roundtrip tests float↔u16, string↔bytes.

---

## A8 — Cohérence Configuration ↔ Code

### 🔴 CRITIQUE

**[A8-001]** `services/esmm/pipeline.py` — `esmm.models` lu depuis config mais **absent de config.yaml**. Le code utilise un fallback hardcodé `["mistral:7b", "llama3.1:8b", "qwen2.5:7b"]`. La sélection de modèles n'est pas configurable sans modifier le code.

### 🟡 FRAGILE

**[A8-002]** Clés config.yaml **définies mais jamais lues** (18 clés orphelines) :
- `database.backup_interval_hours`, `database.vacuum_interval_days`
- `esmm.min_models`, `esmm.cycle_sequence`, `esmm.cycles_per_type`, `esmm.timeout_per_cycle_seconds`
- `confidence.min_models_*`, `confidence.min_architecture_families_*`
- `track_record.*` (toute la section)
- `providers.ollama.*` (base_url, timeout, max_retries)
- `embeddings.fallback_reembed`, `embeddings.similarity_min_score`
- `solana.*` (toute la section)
- `server.*` (host, port, log_level)
- `logging.format`, `logging.file`

**[A8-003]** `esmm.min_consensus` : config.yaml dit `0.4`, `ESMMRunConfig` défaut `0.5`. Le code gagne.

**[A8-004]** Chemin DB incohérent : `config.yaml` → `"data/epp.db"`, `ISpaceDB.__init__` → `"data/ispace.db"`.

**[A8-005]** `esmm.cycles_per_type` : config.yaml définit un `int`, code attend un `dict` (`{"divergent": 3, "debate": 2, "meta": 1}`).

**[A8-006]** Aucune section config validée par Pydantic. `ESMMRunConfig` et `PipelineConfig` sont des `@dataclass` sans validation de schéma.

---

## A9 — Flux de Données

### 🔴 CRITIQUE

**[A9-001]** `services/esmm/pipeline.py` — Erreurs d'extraction accumulées silencieusement : `errors.append(f"Pipeline error: {e}")`. Le pipeline retourne un `PipelineResult` avec une liste d'erreurs que l'appelant peut ignorer. Des triplets partiels ou corrompus pourraient être injectés dans le graphe.

**[A9-002]** `app/api/chat.py` — Pas de validation de longueur avant embedding : `request.text` (max 50 000 chars) est envoyé directement à `get_embeddings()`, mais le modèle d'embedding a une fenêtre de 8192 tokens. Les textes longs provoqueront une erreur ou une troncature silencieuse.

**[A9-003]** Sérialisation mixte : `model_dump()` (Pydantic v2) utilisé dans `attestation.py`, `.dict()` (Pydantic v1 compat) dans `chat.py`. Cassera lors d'une mise à jour Pydantic.

**[A9-004]** `app/api/chat.py` — Texte utilisateur injecté directement dans les prompts LLM sans sanitisation. Vulnérable aux attaques de prompt injection (`"Ignore les instructions précédentes..."`).

### 🟡 FRAGILE

**[A9-005]** Précision flottante incohérente : poids affichés à 2 décimales (`{t['weight']:.2f}`), stockés en pleine précision, consensus arrondi différemment.
**[A9-006]** Dimension embedding calculée depuis blob : `len(embedding) // 4` assume float32 sans validation.
**[A9-007]** Estimation tokens approximative : `len(text) // 4` au lieu d'un vrai tokenizer.
**[A9-008]** `database/engine.py` — Résultats de `commit()` non vérifiés.
**[A9-009]** Post-crystallization hook failures ignorées — attestation stockée même si le hook échoue.
**[A9-010]** Échecs mémoire sémantique avalés — dégradation silencieuse du service.
**[A9-011]** Timestamps : mélange Unix float, datetime objects et ISO 8601 strings selon les couches.
**[A9-012]** Poids des relations non bornés — aucune validation `weight ∈ [0, 1]`.
**[A9-013]** Sensibilité à la casse des concepts non documentée (entropy vs Entropy vs ENTROPY).
**[A9-014 à A9-019]** Divers : physics_state sérialisation custom, format template injection, string interpolation dans prompts ESMM.

---

## A10 — Sécurité Solana

### 🔴 CRITIQUE

**[A10-001]** `programs/epp/src/lib.rs` — `challenged_attestation: Pubkey` accepté sans validation PDA. Un attaquant peut référencer un compte arbitraire comme attestation contestée.

**[A10-002]** `programs/epp/src/lib.rs` — Pas de contrôle d'autorisation du `submitter`. N'importe quel wallet peut soumettre n'importe quelle attestation → spam, pollution de réputation.

**[A10-003]** `services/solana/client.py` — **Transaction building non implémenté** : `TODO` + `raise NotImplementedError`. Le système ne peut pas réellement soumettre de transactions on-chain.

**[A10-004]** `programs/epp/src/lib.rs` — Pas de validation d'ownership explicite sur le compte `attestation`. Anchor devrait l'assurer, mais c'est implicite.

**[A10-005]** `programs/epp/src/lib.rs` — `models_consulted = 0` accepté si `models_agreeing = 0`. Permet des attestations sans aucun modèle consulté.

### 🟡 FRAGILE

**[A10-006]** `services/solana/bridge.py` — `string_to_fixed_bytes()` tronque silencieusement les strings trop longues. Un caractère UTF-8 multi-byte peut être coupé → bytes invalides on-chain.
**[A10-007]** `services/solana/bridge.py` — `float_to_u16()` : valeur `1.000049` arrondie à `10000` (acceptée), mais conceptuellement > 1.0.
**[A10-008]** `services/solana/config.py` — Devnet guard contournable : `SolanaCluster` exclut MAINNET, mais `AsyncClient(rpc_url)` accepte n'importe quelle URL.
**[A10-009]** `services/solana/client.py` — Clé privée chargée depuis JSON non chiffré (`~/.config/solana/id.json`).
**[A10-010]** `programs/epp/src/lib.rs` — Timestamp `i64` sans validation de plage (négatif ou futur lointain accepté).
**[A10-011]** `services/solana/bridge.py` — `hex_to_bytes32()` ne valide pas la longueur du hex string avant parsing.
**[A10-012]** `services/solana/bridge.py` — Protocol version overflow : `"100.0"` → `10000` dépasse u16 silencieusement.
**[A10-013]** `programs/epp/src/lib.rs` — PDA bump stocké mais jamais revalidé en lecture.
**[A10-014]** Pas de rate limiting on-chain. Spam d'attestations possible.

### 🟢 ACCEPTABLE

**[A10-015]** PDA seeds `[b"attestation", submitter, claim_hash]` — déterministes et résistants aux collisions.
**[A10-016]** Float encoding `[0,1]→[0,10000]` — roundtrip testé, précision 4 décimales maintenue.
**[A10-017]** UTF-8 zero-padding — implémenté correctement (hors troncation, cf. A10-006).
**[A10-018]** Devnet guard — design intentionnel, MAINNET absent de l'enum.
**[A10-019]** Account size 462 bytes — calcul vérifié champ par champ.
**[A10-020]** `overflow-checks = true` en release — protection contre overflow entier silencieux.
**[A10-021]** Clé privée jamais loguée — seule la pubkey apparaît dans les logs.
**[A10-022]** Enums Python ↔ Rust — mappings cohérents, testés.
**[A10-023]** SHA-256 claim hash — standard industrie, résistance collision suffisante.

---

## Recommandations Prioritaires

### Top 5 — Impact élevé, effort modéré

| # | Recommandation | Trouvailles | Impact |
|---|---|---|---|
| **1** | **Éliminer les imports de `app/embeddings.py` (deprecated)** et corriger l'import cassé `get_embedding` dans `entity_resolver.py`. Migrer les 4 fichiers vers le provider layer. | A6-001, A6-002 | 🔴 Crash runtime garanti sur entity_resolver, code deprecated maintenu en vie |
| **2** | **Ajouter `embedding_model` aux 3 appels `add_concept()`** dans seed_injector, populate_graph, question_seeder. | A3-001, A3-002, A3-003 | 🔴 ValueError garanti au runtime si ces chemins sont atteints |
| **3** | **Créer un schéma Pydantic pour config.yaml** et supprimer les 18 clés orphelines. Brancher les valeurs config sur les `@dataclass` existants. | A8-001 à A8-006 | 🟡 Configuration actuelle n'a aucun effet sur le comportement du système |
| **4** | **Migrer les 40+ `asyncio.run()` dans les tests** vers `async def` + `@pytest.mark.asyncio`. Unifier la stratégie async des tests. | A7-001 | 🔴 Tout changement de config pytest-asyncio cassera 40+ tests |
| **5** | **Sécuriser les singletons** : ajouter une vérification de paramètres dans `get_db()`, `get_ollama_provider()`, `get_ollama_embedding_provider()`. Pattern : comparer les args avec ceux de l'instance existante, logger un warning ou recréer. | A1-001 à A1-005 | 🔴 Contamination d'état silencieuse en production |

### Top 5 — Impact élevé, effort important

| # | Recommandation | Trouvailles | Impact |
|---|---|---|---|
| **6** | Implémenter le transaction building Solana (actuellement `NotImplementedError`) | A10-003 | 🔴 Fonctionnalité on-chain entièrement non-fonctionnelle |
| **7** | Ajouter validation/autorisation du submitter dans le programme Anchor | A10-002 | 🔴 Spam illimité possible sur devnet |
| **8** | Remplacer les `except: pass` critiques par des logs explicites dans pool.py et engine.py | A2-001 à A2-005 | 🔴 Bugs masqués, diagnostic impossible |
| **9** | Corriger le schéma SQL : ajouter `submission_status`, index manquants, contraintes CHECK | A4-003, A4-008, A4-009 | 🔴 Crash sur appel de méthode existante |
| **10** | Ajouter sanitisation des prompts LLM et validation longueur embedding | A9-002, A9-004 | 🟡 Prompt injection + crash sur textes longs |

---

*Audit interne EPP_Verdict — 11 février 2026*
*Aucune modification de code effectuée. Constats et recommandations uniquement.*
