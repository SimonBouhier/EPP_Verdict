# AUDIT GÉNÉRAL EPP_Verdict — État des lieux complet

> **Auteur** : Claude Opus (auditeur adversarial)
> **Date** : 17 février 2026
> **Base** : 552 passed, 1 failed (pré-existant), 11 skipped
> **Méthode** : grep, diff, analyse d'imports — zéro inférence

---

## TABLE DES MATIÈRES

1. [RÉSUMÉ EXÉCUTIF](#1)
2. [BUG ACTIF — test_rollback_restores_state](#2)
3. [CODE MORT — Héritage Lyra](#3)
4. [FICHIERS ORPHELINS — Importés par personne](#4)
5. [FICHIERS NON TESTÉS — EPP production](#5)
6. [SINGLETONS — Couverture conftest (C7)](#6)
7. [AUDIT MARKERS OUVERTS — FRAGILE/CRITICAL](#7)
8. [VARIABLES D'ENVIRONNEMENT LYRA_*](#8)
9. [MOCK RÉSIDUEL EN PRODUCTION](#9)
10. [TODO EN PRODUCTION](#10)
11. [PLAN D'ACTION PRIORISÉ](#11)

---

<a name="1"></a>
## 1. RÉSUMÉ EXÉCUTIF

| Catégorie | Compte | Sévérité |
|:---|:---|:---|
| Bug actif (test fail) | 1 | 🔴 ROUGE |
| Fichiers Lyra legacy (dead code) | 17 | 🟡 NETTOYAGE |
| Fichiers orphelins (0 imports) | 4 | 🟡 NETTOYAGE |
| Fichiers EPP non testés | 6 | 🟠 ORANGE |
| Singletons non reset (C7) | 14/16 | 🟠 ORANGE |
| AUDIT markers ouverts | 21 | 🟡 DOCUMENTÉ |
| AUDIT marker CRITICAL | 1 | 🟠 ORANGE |
| Env vars LYRA_* dans EPP | 4 fichiers | 🟡 COSMÉTIQUE |
| Mock client Solana sans solders | Tout le client | ✅ ACCEPTABLE MVP |
| TODOs en production | 2 | 🟢 MINEUR |

**Verdict global** : Le cœur EPP (pipeline ESMM → attestation → on-chain) est solide
avec 552 tests passants. Mais le repo contient ~17 fichiers legacy Lyra qui ne
participent pas au pipeline EPP et polluent l'espace. L'audit de mutation est
nécessaire sur les ~6 fichiers EPP critiques non couverts par des tests directs.

---

<a name="2"></a>
## 2. BUG ACTIF — test_rollback_restores_state

**Fichier** : `tests/test_graph_delta.py::test_rollback_restores_state`
**Erreur** : `assert 0 >= 1` (ligne 72)
**Sévérité** : 🔴 ROUGE

**Observation critique** : Le traceback pytest pointe vers
`..\\lyra_clean_bis\\tests\\test_graph_delta.py:72`. Le `..` indique que pytest
collecte des tests HORS du répertoire EPP_Verdict, probablement via une
configuration `testpaths` dans `pytest.ini` ou un conftest parent.

**Actions** :
- [ ] P0 : Vérifier `pytest.ini` — s'assurer que `testpaths = tests` est défini
      et que pytest ne remonte pas dans le répertoire parent
- [ ] P0 : Si le test EST dans EPP, corriger le code `graph_delta.py` ou le test
- [ ] P0 : Si le test est importé depuis `lyra_clean_bis`, c'est une contamination
      cross-projet à éliminer immédiatement

**Commande diagnostic** :
```bash
pytest tests/test_graph_delta.py::test_rollback_restores_state -v --tb=long
# Vérifier le chemin réel du fichier dans la traceback
```

---

<a name="3"></a>
## 3. CODE MORT — Héritage Lyra

17 fichiers portent des headers `LYRA CLEAN` ou `LYRA-ACE` et appartiennent
à l'ancienne application web Lyra (FastAPI chat app), PAS au pipeline EPP.

### Fichiers Lyra legacy (non utilisés par la chaîne `epp ask`) :

| Fichier | Header | Rôle Lyra | Utilisé par EPP ? |
|:---|:---|:---|:---|
| `main.py` | LYRA CLEAN - MAIN API SERVER | FastAPI app | ❌ Non (EPP utilise `epp_cli.py`) |
| `chat.py` | LYRA CLEAN - CHAT API ROUTES | Chat endpoints | ❌ Non |
| `llm_client.py` | LYRA CLEAN - ASYNC OLLAMA CLIENT | Client Ollama web | ❌ Non (EPP utilise `ollama.py`) |
| `models.py` | (Pydantic models pour chat) | Request/Response models | ⚠️ Partiellement (importé par `mock_provider`, `cycle_manager`) |
| `memory.py` | (Memory/session management) | Mémoire conversationnelle | ❌ Non |
| `session_storage.py` | (Session persistence) | Sessions web | ❌ Non |
| `injector.py` | LYRA CLEAN - CONTEXT INJECTION | RAG injection Lyra | ❌ Non (EPP utilise `question_seeder.py`) |
| `adaptation.py` | (Physics-driven adaptation) | Bézier adaptation | ❌ Non |
| `bezier.py` | (Physics engine) | Courbes tension/cohérence | ❌ Non |
| `metrics.py` | (Chat metrics) | Métriques Lyra | ⚠️ Partiellement (importé par `cycle_manager`) |
| `hydrate_embeddings.py` | LYRA REPAIR TOOL | Migration embeddings | ❌ Non |
| `kappa_worker.py` | (Background worker) | Worker async | ❌ Non |
| `populate_graph.py` | (Graph seeding) | Peuplement initial | ⚠️ Via `seed_injector` |
| `seed_injector.py` | (Seed injection) | Injection de graines | ⚠️ Via `graph.py` |
| `relation_generator.py` | (Relation generation) | Génération de relations | ❌ Non |
| `model_rotator.py` | LYRA-ACE ESMM Protocol | Rotation modèles v1 | ⚠️ Partiellement (importé par `cycle_manager`) |
| `graph.py` | (Graph operations) | Opérations graphe | ⚠️ Partiellement (importé par `engine.py`) |

### Recommandation

**Ne PAS supprimer** avant le hackathon — risque de casser des imports transitifs.
Mais **marquer clairement** avec un `# LEGACY_LYRA: Not part of EPP pipeline` en
tête de fichier. Post-hackathon : extraire vers un dossier `legacy/` séparé.

**Pour le hackathon** : Vérifier que ces fichiers ne sont PAS inclus dans le README
ou la démo comme composants EPP.

---

<a name="4"></a>
## 4. FICHIERS ORPHELINS — Importés par personne

4 fichiers n'ont **aucun import** depuis aucun autre fichier du projet :

| Fichier | Contenu | Action |
|:---|:---|:---|
| `injector.py` | Context injection Lyra (Bézier, prompts "You are Lyra") | Legacy, ignorer |
| `kappa_worker.py` | Background worker | Legacy, ignorer |
| `relation_generator.py` | Génération de relations | Legacy, ignorer |
| `session_storage.py` | Session persistence web | Legacy, ignorer |

Tous sont du legacy Lyra. **Aucune action EPP requise.**

---

<a name="5"></a>
## 5. FICHIERS NON TESTÉS — EPP production

### Fichiers EPP actifs sans test dédié :

| Fichier | Rôle EPP | Criticité | Testé indirectement ? |
|:---|:---|:---|:---|
| `coverage_analyzer.py` | Analyse couverture du graphe | Moyenne | Oui (via orchestrator tests) |
| `gap_detector.py` | Détection lacunes dans le graphe | Moyenne | Oui (via orchestrator tests) |
| `cochain_builder.py` | Construction cochaines épistémiques | Haute | Oui (via orchestrator tests) |
| `entity_resolver.py` | Résolution d'entités dans triplets | Haute | Oui (via triplet_extractor tests) |
| `graph.py` | Opérations graphe haut niveau | Haute | Partiellement (engine testé, pas graph.py) |
| `model_rotator.py` | Rotation modèles v1 | Moyenne | Via cycle_manager tests |

### Fichiers EPP testés indirectement mais qui méritent des tests unitaires :

- `post_crystallization.py` — 4 tests dans `test_phase3_post_crystallization.py` ✅
- `question_seeder.py` — 7 tests dans `test_phase3_question_seeder.py` ✅
- `config_loader.py` — 8 tests dans `test_phase3_config_loader.py` ✅
- `response_deduplicator.py` — 3 tests dans `test_r2_response_deduplicator.py` ✅

### Action recommandée pour l'audit mutation

Priorité mutation testing (fichiers critiques à tester en premier) :

```
1. consensus_engine.py    — cœur du vote, calculs numériques
2. pipeline.py            — orchestration complète
3. bridge.py              — sérialisation on-chain (déjà bien testé)
4. triplet_extractor.py   — extraction LLM → triplets
5. cycle_manager.py       — gestion des cycles ESMM
6. attestation.py         — structure de données attestation
```

---

<a name="6"></a>
## 6. SINGLETONS — Couverture conftest (C7)

### 16 singletons uniques, 2 reset dans conftest

| Singleton | Fichier | Reset conftest ? | EPP actif ? |
|:---|:---|:---|:---|
| `_pool_instance` | pool.py | ✅ Oui (via `close_pool`) | ✅ |
| `_db_instance` | engine.py | ✅ Oui | ✅ |
| `_concept_cache` | pool.py | ❌ Non | ✅ |
| `_concurrency_limiter` | pool.py | ❌ Non | ✅ |
| `_config, _config_path` | config_loader.py | ❌ Non | ✅ |
| `_extractor_instance` | triplet_extractor.py | ❌ Non | ✅ |
| `_normalizer_instance` | relation_normalizer.py | ❌ Non | ✅ |
| `_resolver_instance` | entity_resolver.py | ❌ Non | ✅ |
| `_ollama_instance` | ollama.py | ❌ Non | ✅ |
| `_ollama_embedding_instance` | ollama_embeddings.py | ❌ Non | ✅ |
| `_rotator_instance` | model_rotator.py | ❌ Non | ⚠️ Lyra/EPP partagé |
| `_client_instance` | llm_client.py | ❌ Non | ❌ Lyra |
| `_multi_model_instance` | llm_client.py | ❌ Non | ❌ Lyra |
| `_memory_instance` | memory.py | ❌ Non | ❌ Lyra |
| `_storage_instance` | session_storage.py | ❌ Non | ❌ Lyra |
| `_startup_time` | main.py | ❌ Non | ❌ Lyra |

### Bilan

- **Singletons EPP actifs** : 10, dont 2 reset = **20% couverture** 🟠
- **Singletons Lyra** : 6, pas besoin de reset pour EPP
- **Risque principal** : `_config` et `_extractor_instance` non reset entre tests
  → un test qui modifie la config pollue les suivants

### Action

- [ ] Étendre `reset_db_singletons` dans conftest pour couvrir les 10 singletons EPP
- [ ] Ou mieux : chaque fichier expose une fonction `close_*()` / `reset_*()`
      et conftest les appelle toutes

---

<a name="7"></a>
## 7. AUDIT MARKERS OUVERTS — FRAGILE/CRITICAL

### 🔴 CRITICAL (1) :

| Marker | Fichier | Problème |
|:---|:---|:---|
| A2-001 | pool.py:231 | `except:pass` masque erreurs de fermeture de connexion |

### 🟡 FRAGILE (14) :

| Marker | Fichier | Problème |
|:---|:---|:---|
| A8-006 | cycle_manager.py:68 | Timeouts hardcodés, config.yaml ignoré |
| A2-013 | cycle_manager.py:752 | Échecs d'extraction accumulés sans arrêt |
| A3-005 | pipeline.py:203 | `store_attestation()` conversion implicite |
| A2-011 | pipeline.py:210 | `post_crystallization` failure ignorée |
| A2-010 | pipeline.py:233,239 | Erreurs accumulées sans arrêt du pipeline |
| A3-008 | pipeline.py:418 | Format dict sans validation intermédiaire |
| A8-004 | orchestrator.py:75 | `cycle_sequence` hardcodé, config ignorée |
| A8-003 | orchestrator.py:79 | `min_consensus=0.5` hardcodé (config dit 0.4) |
| A2-012 | orchestrator.py:420 | Timeout logué, cycle sauté → consensus faussé |
| A10-008 | client.py:118 | Devnet guard contournable via URL RPC directe |
| A10-009 | client.py:130 | Clé privée chargée depuis JSON non chiffré |
| A2-014 | triplet_extractor.py:352 | JSON invalide LLM → liste vide silencieuse |
| A1-007 | pool.py:537 | Cache sans TTL ni invalidation |
| A1-008 | pool.py:539 | Semaphore global non lié au pool spécifique |
| A1-006 | pool.py:549 | `pool_size` ignoré si instance existe déjà |
| A2-002 | pool.py:261 | Exceptions avalées pendant nettoyage |

### AUDIT_REQUIRED (non numérotés) — 7 dans client.py, 2 dans config.py

Ces markers sont des rappels pour audit humain pré-mainnet. Acceptables pour MVP/devnet.

### Action

- [ ] P1 : Corriger A2-001 (pool.py:231) — ajouter `logger.error` dans le except
- [ ] P2 : Corriger A8-003 (orchestrator.py:79) — lire `min_consensus` depuis config
- [ ] P2 : Corriger A8-004 (orchestrator.py:75) — lire `cycle_sequence` depuis config
- [ ] P3 : Les autres sont acceptables pour MVP si documentés

---

<a name="8"></a>
## 8. VARIABLES D'ENVIRONNEMENT LYRA_*

4 fichiers **actifs dans la chaîne EPP** référencent des env vars `LYRA_*` :

| Fichier | Var | Fallback | Utilisé par EPP ? |
|:---|:---|:---|:---|
| `ollama.py:423` | `LYRA_OLLAMA_URL` | localhost:11434 | ✅ Oui (provider Ollama) |
| `ollama.py:425` | `LYRA_MODEL` | gpt-oss:20b | ✅ Oui |
| `ollama.py:426` | `LYRA_NUM_CTX` | 8192 | ✅ Oui |
| `ollama_embeddings.py:222` | `LYRA_OLLAMA_URL` | localhost:11434 | ✅ Oui |
| `ollama_embeddings.py:224` | `LYRA_EMBEDDING_MODEL` | nomic-embed-text | ✅ Oui |
| `model_rotator.py:509` | `LYRA_OLLAMA_URL` | localhost:11434 | ⚠️ Partagé |
| `model_rotator.py:510` | `LYRA_NUM_CTX` | 8192 | ⚠️ Partagé |

### Action

- [ ] P3 : Renommer `LYRA_*` → `EPP_*` dans les 3 fichiers EPP actifs
  (ollama.py, ollama_embeddings.py, model_rotator.py)
- [ ] Ajouter backward compat : `os.environ.get("EPP_OLLAMA_URL", os.environ.get("LYRA_OLLAMA_URL", "..."))`
- [ ] Documenter dans config.yaml ou README

---

<a name="9"></a>
## 9. MOCK RÉSIDUEL EN PRODUCTION

### client.py — Mock mode Solana (ACCEPTABLE)

Quand `solders`/`solana-py` ne sont pas installés, **tout** le client opère en mock :
- `derive_attestation_pda()` → hash SHA-256 au lieu de vraie dérivation PDA
- `submit_attestation()` → signature mock (hash déterministe)
- `get_attestation()` → retourne None
- `query_attestations_by_*()` → retourne []
- `check_pda_exists()` → retourne False

**C'est acceptable pour le MVP** car :
1. Les tests vérifient la logique (sérialisation, offsets, bridge)
2. Le vrai mode nécessite un validator Solana local ou devnet
3. Le client log `MOCK:` clairement à chaque opération

### pipeline.py — Backward compat mock (L135)

```python
# Backward compat: mocks may return 2-tuple, real code returns 3-tuple
```

Pas un mock actif, juste de la robustesse pour les tests avec MockProvider.

### mock_provider.py — Test infrastructure (OK)

Fournit `MockModelProvider` pour les tests. N'est PAS importé par le code de production.
Importé uniquement par `conftest.py` et des fichiers test. ✅

### Aucun mock caché dans la logique métier

Les fichiers critiques (`consensus_engine.py`, `triplet_extractor.py`, `cycle_manager.py`,
`attestation.py`, `bridge.py`) ne contiennent **aucun chemin mock**. ✅

---

<a name="10"></a>
## 10. TODO EN PRODUCTION

| Fichier | Ligne | TODO |
|:---|:---|:---|
| `cycle_manager.py:790` | `response_latencies={} # TODO: track latencies` | 🟢 Non bloquant |
| `main.py:174` | `allow_origins=["*"] # TODO: Restrict in production` | 🟡 Lyra legacy, hors EPP |

**Action** : Aucune action MVP requise. Le premier est un nice-to-have pour le dashboard modèles.

---

<a name="11"></a>
## 11. PLAN D'ACTION PRIORISÉ

### P0 — Bloquant (avant tout le reste)

| # | Action | Effort | Fichier(s) |
|:---|:---|:---|:---|
| P0-1 | Diagnostiquer `test_rollback_restores_state` — contamination cross-projet ou vrai bug | 30min | pytest.ini, test_graph_delta.py |
| P0-2 | Vérifier `pytest.ini` : `testpaths = tests` pour ne PAS collecter depuis `lyra_clean_bis` | 10min | pytest.ini |

### P1 — Corrections ciblées (1-2h total)

| # | Action | Effort | Fichier(s) |
|:---|:---|:---|:---|
| P1-1 | Fix A2-001 : ajouter `logger.error(e)` dans pool.py:231 | 5min | pool.py |
| P1-2 | Fix A8-003 : lire `min_consensus` depuis config au lieu de hardcoder 0.5 | 15min | orchestrator.py |
| P1-3 | Fix A8-004 : lire `cycle_sequence` depuis config au lieu de hardcoder | 15min | orchestrator.py |
| P1-4 | Étendre conftest : reset des singletons EPP critiques (_config, _extractor, _normalizer, _resolver, _concept_cache, _concurrency_limiter, _ollama, _ollama_embedding) | 30min | conftest.py |

### P2 — Audit mutation (3-4h total)

| # | Action | Effort | Fichier(s) |
|:---|:---|:---|:---|
| P2-1 | `mutmut run --paths-to-mutate consensus_engine.py` — tuer tous les mutants | 45min | consensus_engine.py |
| P2-2 | `mutmut run --paths-to-mutate pipeline.py` | 45min | pipeline.py |
| P2-3 | `mutmut run --paths-to-mutate bridge.py` | 30min | bridge.py |
| P2-4 | `mutmut run --paths-to-mutate triplet_extractor.py` | 45min | triplet_extractor.py |
| P2-5 | `mutmut run --paths-to-mutate attestation.py` | 30min | attestation.py |
| P2-6 | `mutmut run --paths-to-mutate cycle_manager.py` | 45min | cycle_manager.py |

### P3 — Cosmétique / Post-hackathon

| # | Action | Effort | Fichier(s) |
|:---|:---|:---|:---|
| P3-1 | Renommer `LYRA_*` → `EPP_*` (avec backward compat) | 30min | ollama.py, ollama_embeddings.py, model_rotator.py |
| P3-2 | Ajouter `# LEGACY_LYRA` header aux 17 fichiers legacy | 15min | Multiples |
| P3-3 | Déplacer legacy vers `legacy/` post-hackathon | 1h | Restructuration |
| P3-4 | `create_consensus_engine()` — fonction dead, supprimer ou connecter | 5min | consensus_engine.py |

---

## RÉSUMÉ POUR CLAUDE CODE

Si tu transmets directement :

> **MISSION : Audit corrections P0+P1**
>
> 1. Diagnostic `test_rollback_restores_state` — est-ce un test EPP ou un import de `lyra_clean_bis` ?
>    Si cross-projet : ajouter `testpaths = tests` dans `pytest.ini`.
>    Si vrai bug : fixer avec RED-GREEN-FIX.
>
> 2. pool.py:231 — remplacer `except: pass` par `except Exception as e: logger.error(f"Pool close error: {e}")`
>
> 3. orchestrator.py:75 — lire `cycle_sequence` depuis `config.yaml::esmm.cycle_sequence`
>    orchestrator.py:79 — lire `min_consensus` depuis `config.yaml::esmm.min_consensus`
>    (garder les valeurs actuelles comme fallback par défaut)
>
> 4. conftest.py — étendre `reset_db_singletons` pour reset les 8 singletons EPP actifs :
>    `_config/_config_path` (config_loader), `_extractor_instance` (triplet_extractor),
>    `_normalizer_instance` (relation_normalizer), `_resolver_instance` (entity_resolver),
>    `_concept_cache/_concurrency_limiter` (pool), `_ollama_instance` (ollama),
>    `_ollama_embedding_instance` (ollama_embeddings)
>
> 5. pytest complet final : 0 failed.
>
> **Protocole** : RED-GREEN-FIX pour le test cassé. Pas de RED nécessaire pour P1-1 à P1-4
> (ce sont des améliorations d'infrastructure, pas des bugs). Mais pytest complet obligatoire.

---

*AUDIT_GENERAL_EPP.md — EPP_Verdict*
*Claude Opus — 17 février 2026*
*Basé sur : 552 passed, grep exhaustif de la codebase production*
