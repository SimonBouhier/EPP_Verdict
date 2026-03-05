# AUDIT_INTERNE.md — EPP_Verdict

> **Document de travail pour Claude Code.** Méthodologie d'audit systématique du code.
> Objectif : identifier les fragilités structurelles AVANT qu'elles ne deviennent des bugs.
>
> **Règle absolue : NE RIEN MODIFIER pendant l'audit.** Ce document produit un RAPPORT,
> pas des corrections. On avise après, ensemble.

---

## CONTEXTE

Ce code a été produit par collaboration humain/IA à travers 7 phases (0.1 → 3.1).
L'IA génère du code fonctionnel pour le cas nominal mais a des angles morts récurrents :

| Pattern observé | Exemple trouvé dans EPP |
|---|---|
| Singletons qui ne détectent pas les changements de contexte | `get_pool()` ignorait le changement de `db_path` |
| Retours silencieux au lieu d'erreurs | `rollback_deltas()` retournait 0 sans avertissement |
| INSERT brut au lieu de INSERT OR REPLACE | Rollback de DELETE_EDGE explosait sur UNIQUE |
| Tests qui affirment le succès sans vérifier le contenu | Tests Phase 0.3 avec anciens tiers qui passaient par coïncidence |
| Mismatch de signatures entre appelant et appelé | `from_tier/to_tier` vs `old_tier/new_tier` |

L'audit cherche systématiquement ces patterns et leurs variantes.

---

## MODE OPÉRATOIRE

Pour chaque angle d'audit (A1 à A10) :

1. **Exécuter les commandes de détection** (grep, ast, imports)
2. **Classer chaque trouvaille** :
   - 🔴 **CRITIQUE** — bug latent, perte de données, crash en production
   - 🟡 **FRAGILE** — fonctionne maintenant, cassera au prochain changement
   - 🟢 **ACCEPTABLE** — pattern intentionnel, documenter pourquoi
   - ⚪ **INFO** — observation sans impact, ignorer
3. **Consigner dans le rapport** avec fichier, ligne, extrait, classification

### Format du rapport

Pour chaque trouvaille :

```
[A1-003] 🟡 FRAGILE
Fichier : services/esmm/pipeline.py:42
Code    : except Exception as e: errors.append(str(e))
Risque  : L'erreur est loguée mais le pipeline continue — un triplet corrompu
          pourrait être injecté dans le graphe si l'erreur survient après
          la validation mais avant la cristallisation.
```

Le numéro [AX-NNN] est séquentiel par angle. Le rapport final est un seul fichier
markdown avec toutes les trouvailles triées par sévérité.

---

## A1 — SINGLETONS ET ÉTAT GLOBAL

### Ce qu'on cherche

Toute variable globale `_instance`, `_pool`, `_config`, `_db` qui persiste entre
les appels. Risque : contamination d'état entre requêtes, tests, ou contextes.

### Commandes de détection

```bash
# Toutes les variables globales singleton
grep -rn "^_[a-z_]*_instance\|^_[a-z_]*:" --include="*.py" \
  database/ services/ app/ | grep -v "__pycache__\|test_\|\.pyc"

# Fonctions get_xxx() qui créent des singletons
grep -rn "global _\|if _.*is None" --include="*.py" \
  database/ services/ app/ | grep -v "__pycache__\|test_"

# Singletons qui ne vérifient PAS le changement de paramètres
# (pattern dangereux : if instance is None, sans vérifier les args)
grep -A5 "if _.*is None:" --include="*.py" -rn \
  database/ services/ | grep -v "__pycache__\|test_"
```

### Questions à poser pour chaque singleton trouvé

1. Que se passe-t-il si on l'appelle avec des paramètres différents la 2ème fois ?
2. Y a-t-il un `reset()` ou `close()` pour les tests ?
3. Le singleton est-il thread-safe en contexte async (asyncio) ?
4. Qui est responsable de la fermeture (lifecycle ownership) ?

### Singletons connus (vérifier leur état actuel)

- `database/pool.py` : `_pool_instance` → corrigé en Phase 3.1 (vérifie db_path)
- `database/engine.py` : `_db_instance` via `get_db()` → close_db() existe
- `services/config_loader.py` : `_config` → `reset_config()` existe
- `services/esmm/entity_resolver.py` : `_resolver_instance` → pas de reset ?
- `services/providers/ollama_embeddings.py` : `_ollama_embedding_instance` → close existe
- `services/providers/ollama.py` : vérifier si singleton similaire

---

## A2 — EXCEPTIONS AVALÉES (except: pass)

### Ce qu'on cherche

Tout bloc `except` qui avale l'erreur sans la propager ni la loguer de manière
exploitable. C'est le pattern le plus dangereux : le code échoue silencieusement
et les effets se manifestent loin de la cause.

### Commandes de détection

```bash
# except: pass nu (le pire)
grep -rn "except.*:" --include="*.py" -A1 database/ services/ app/ \
  | grep -B1 "pass$" | grep -v "__pycache__\|test_"

# except Exception sans re-raise ni log
grep -rn "except Exception" --include="*.py" -A2 database/ services/ app/ \
  | grep -v "logger\.\|logging\.\|raise\|__pycache__\|test_"

# Blocs try/except qui retournent une valeur par défaut silencieuse
grep -rn "except.*:" --include="*.py" -A2 database/ services/ app/ \
  | grep -B1 "return \[\]\|return None\|return 0\|return {}" \
  | grep -v "__pycache__\|test_"
```

### Classification

- 🔴 `except: pass` dans du code qui modifie la DB → CRITIQUE
- 🟡 `except: pass` dans de l'initialisation/migration → FRAGILE (masque les vrais bugs)
- 🟢 `except: pass` documenté avec commentaire expliquant pourquoi → ACCEPTABLE
- 🟢 `except Exception as e: logger.warning(...)` → ACCEPTABLE si le warning est utile

### Attention particulière

Le fichier `engine.py::initialize()` contient plusieurs `except: pass` pour les
migrations et le seeding. Chacun doit être classifié individuellement :
- Les migrations ALTER TABLE qui échouent car la colonne existe déjà → 🟢
- Le seeding de frames qui échoue car la table n'existe pas → 🟡 (pourquoi la
  table n'existerait-elle pas après executescript(schema_sql) ?)

---

## A3 — COHÉRENCE DES INTERFACES (signatures appelant ↔ appelé)

### Ce qu'on cherche

Chaque méthode publique de `engine.py` (ISpaceDB) est appelée depuis plusieurs
endroits. Un changement de signature non propagé = crash au runtime.

### Commandes de détection

```bash
# Lister toutes les méthodes publiques de ISpaceDB
grep -n "async def [a-z]" database/engine.py | grep -v "^.*_[a-z]" | head -50

# Pour chaque méthode critique, trouver tous les appels
# (remplacer METHOD par le nom réel)
grep -rn "db\.store_attestation\|await.*store_attestation" --include="*.py" \
  services/ cli/ tests/ | grep -v "__pycache__"

grep -rn "db\.record_model_prediction\|await.*record_model_prediction" --include="*.py" \
  services/ cli/ tests/ | grep -v "__pycache__"

grep -rn "db\.log_tier_transition\|await.*log_tier_transition" --include="*.py" \
  services/ cli/ tests/ | grep -v "__pycache__"

grep -rn "db\.add_concept\|await.*add_concept" --include="*.py" \
  services/ cli/ tests/ | grep -v "__pycache__"
```

### Méthode d'analyse

Pour chaque paire (définition, appel) :
1. La définition a-t-elle des paramètres obligatoires que l'appel ne fournit pas ?
2. L'appel utilise-t-il des noms de paramètres qui n'existent pas dans la définition ?
3. Les types correspondent-ils ? (str vs int, Optional vs required)

### Interfaces critiques à vérifier en priorité

| Méthode | Appelée depuis | Risque |
|---|---|---|
| `add_concept()` | question_seeder, populate_graph, triplet_extractor | 🔴 Signature changée en Phase 0.2 |
| `store_attestation()` | pipeline.py | 🟡 Dict attendu, pas un objet |
| `record_model_prediction()` | post_crystallization.py | 🟡 Noms de params |
| `log_tier_transition()` | post_crystallization.py | 🟡 Corrigé en Phase 3.1, revérifier |
| `create_esmm_run()` | orchestrator.py, pipeline.py | 🔴 Double création éliminée D1 ? |
| `upsert_relations_batch()` | pipeline.py (_inject_triplet_to_graph) | 🟡 Format du dict |

---

## A4 — SQL : INTÉGRITÉ ET SÉCURITÉ

### Ce qu'on cherche

- INSERT sans gestion de conflit (UNIQUE constraint)
- Requêtes avec f-string (injection SQL)
- Transactions non commitées ou non rollbackées
- Index manquants pour les patterns de requête fréquents

### Commandes de détection

```bash
# INSERT brut sans OR IGNORE / OR REPLACE
grep -rn "INSERT INTO" --include="*.py" database/ services/ \
  | grep -v "INSERT OR\|INSERT OR IGNORE\|INSERT OR REPLACE\|__pycache__"

# f-string dans des requêtes SQL (injection potentielle)
grep -rn 'f".*SELECT\|f".*INSERT\|f".*UPDATE\|f".*DELETE' --include="*.py" \
  database/ services/ | grep -v "__pycache__"

# Transactions : commit sans rollback dans le même try/except
grep -rn "await conn.commit" --include="*.py" database/ | grep -v "__pycache__"

# Vérifier que chaque commit a un rollback correspondant dans le except
grep -B20 "await conn.commit" database/engine.py \
  | grep "rollback\|except" | head -20
```

### Points d'attention spécifiques

1. **Table `relations`** a un `PRIMARY KEY (source, target)` — tout INSERT sans
   OR IGNORE/REPLACE explosera sur un doublon. Vérifier tous les points d'insertion.

2. **Table `attestations`** — les attestations sont append-only (pas de UPDATE sauf
   pour `solana_tx_signature`). Vérifier qu'aucun code ne fait UPDATE sur le contenu.

3. **Les f-strings SQL** dans engine.py pour les clauses WHERE dynamiques — vérifier
   que les valeurs viennent de paramètres contrôlés, jamais d'input utilisateur.

---

## A5 — LIFECYCLE ASYNC (resources non fermées)

### Ce qu'on cherche

- httpx.AsyncClient créé sans `async with` ni `close()`
- aiosqlite connections non fermées
- Coroutines appelées sans `await`

### Commandes de détection

```bash
# httpx clients potentiellement non fermés
grep -rn "httpx.AsyncClient(" --include="*.py" services/ \
  | grep -v "__pycache__"

# Chercher si ces clients sont fermés
grep -rn "await.*close()\|async with.*AsyncClient" --include="*.py" services/ \
  | grep -v "__pycache__"

# Coroutines appelées sans await (bug subtil en Python)
# Chercher des appels à des fonctions async sans await devant
grep -rn "db\.\(store_\|get_\|add_\|update_\|create_\|delete_\|log_\)" \
  --include="*.py" services/ cli/ | grep -v "await\|__pycache__\|test_\|def "

# Pools/connexions : s'assurer qu'initialize() est toujours appelé avant utilisation
grep -rn "ISpaceDB(" --include="*.py" services/ cli/ tests/ | grep -v "__pycache__"
```

### Pattern à vérifier

Pour chaque `httpx.AsyncClient` :
1. Est-il créé dans un `async with` (auto-close) ?
2. Sinon, y a-t-il un `close()` dans un finally ou un __aexit__ ?
3. Que se passe-t-il si la connexion est interrompue ? (timeout, réseau)

---

## A6 — CODE MORT ET CHEMINS INATTEIGNABLES

### Ce qu'on cherche

- Fonctions définies mais jamais appelées
- Branches `else` qui ne peuvent jamais être atteintes
- Imports inutilisés
- Code commenté (TODO, FIXME, HACK)

### Commandes de détection

```bash
# Fonctions définies dans services/ mais jamais importées/appelées
# (approche : lister les def, puis vérifier les appels)
grep -rn "^def \|^async def " --include="*.py" services/ \
  | sed 's/.*def //' | sed 's/(.*$//' | sort | uniq > /tmp/defined_funcs.txt

# Pour chaque fonction, vérifier si elle est appelée ailleurs
# (échantillon sur les 20 premières)
head -20 /tmp/defined_funcs.txt | while read func; do
  count=$(grep -rn "$func" --include="*.py" services/ cli/ app/ | grep -v "def $func" | wc -l)
  [ "$count" -eq 0 ] && echo "DEAD: $func"
done

# TODO / FIXME / HACK dans le code
grep -rn "TODO\|FIXME\|HACK\|XXX\|AUDIT_REQUIRED" --include="*.py" \
  database/ services/ cli/ app/ | grep -v "__pycache__\|test_"

# Imports qui pourraient être inutilisés
# (chercher les imports au début de fichiers lourds)
python -c "
import ast, sys, os
for root, dirs, files in os.walk('services'):
    for f in files:
        if f.endswith('.py') and not f.startswith('test_'):
            path = os.path.join(root, f)
            try:
                tree = ast.parse(open(path).read())
                imports = [n.names[0].name if isinstance(n, ast.Import) else n.module
                           for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
            except: pass
" 2>/dev/null
```

### Points d'attention

- `model_rotator.py` est marqué comme "remplacé par multi_provider_rotator" dans
  ARCHITECTURE.md mais existe toujours. Est-il encore importé quelque part ?
- `app/embeddings.py` est marqué déprécié. Qui l'importe encore ?
- Les helper functions dans `orchestrator.py` (`run_esmm_protocol`,
  `resume_esmm_protocol`) — sont-elles appelées ?

---

## A7 — QUALITÉ DES TESTS

### Ce qu'on cherche

- Tests qui passent mais ne testent rien de substantiel
- Tests qui dépendent de l'ordre d'exécution
- Assertions trop faibles (`assert result is not None` au lieu de vérifier le contenu)
- Mocks qui cachent le vrai comportement

### Commandes de détection

```bash
# Tests avec des assertions faibles
grep -rn "assert.*is not None$\|assert.*is True$\|assert True$" \
  --include="*.py" tests/ | grep -v "__pycache__"

# Tests sans aucune assertion
grep -l "def test_" tests/*.py | while read f; do
  tests=$(grep -c "def test_" "$f")
  asserts=$(grep -c "assert " "$f")
  ratio=$((asserts / tests))
  [ "$ratio" -lt 1 ] && echo "LOW_ASSERT_RATIO: $f ($asserts asserts / $tests tests)"
done

# Tests qui utilisent asyncio.run() au lieu de async def
grep -rn "asyncio.run\|loop.run_until_complete" --include="*.py" tests/ \
  | grep -v "__pycache__"

# Tests qui patchent trop (le mock remplace tout le code testé)
grep -c "patch\|Mock\|AsyncMock" tests/test_phase3_*.py | sort -t: -k2 -rn
```

### Questions par fichier de test

Pour chaque fichier `test_phase3_*.py` :
1. Le test crée-t-il sa propre DB isolée ou utilise-t-il un état partagé ?
2. Les assertions vérifient-elles le comportement métier ou juste la structure ?
3. Si on casse le code testé, le test échoue-t-il vraiment ?

---

## A8 — COHÉRENCE CONFIGURATION ↔ CODE

### Ce qu'on cherche

- Valeurs par défaut dans le code qui diffèrent de config.yaml
- Sections de config.yaml référencées dans le code mais absentes du fichier
- Clés de config dupliquées ou contradictoires

### Commandes de détection

```bash
# Toutes les clés lues depuis config.yaml dans le code
grep -rn "get_section\|get_value\|config\[" --include="*.py" \
  services/ database/ cli/ | grep -v "__pycache__\|test_"

# Valeurs par défaut hardcodées qui devraient venir de config
grep -rn '"data/ispace.db"\|"data/epp.db"\|"http://localhost:11434"' \
  --include="*.py" database/ services/ | grep -v "__pycache__\|test_"

# Vérifier la cohérence : le path DB par défaut dans get_db() vs config.yaml
grep -n "data/.*\.db" database/engine.py config.yaml
```

### Points d'attention

- `engine.py::get_db()` utilise `get_value("database", "path", "data/epp.db")` comme
  fallback. Mais `ISpaceDB.__init__` a un défaut `"data/ispace.db"`. Lequel gagne ?
- `config.yaml` contient-il une section `database.path` ?
- Les seuils de confiance (`min_consensus_for_attestation = 0.4`) sont-ils en dur
  dans `PipelineConfig` ou lus depuis config.yaml ?

---

## A9 — FLUX DE DONNÉES : DU CLI À LA DB

### Ce qu'on cherche

Tracer le chemin complet d'une question de l'entrée CLI jusqu'au stockage en DB.
Identifier chaque point où une donnée pourrait être perdue, transformée incorrectement,
ou non validée.

### Méthode

Tracer le flux `epp ask "question"` pas à pas :

```
1. epp_cli.py::ask() → appelle _run_ask()
2. _run_ask() → get_db() + run_pipeline()
3. pipeline.py::run_pipeline() → _extract_triplets_from_question()
4. _extract_triplets_from_question() → seed_graph + ESMMOrchestrator
5. orchestrator → cycle_manager → triplet_extractor → consensus_engine
6. Retour : ConsensusTriplet[] → triplet_adapter → dict[]
7. pipeline.py → crystallize() → store_attestation() → inject_to_graph()
8. post_crystallization_hook() → record_model_prediction() + log_tier_transition()
```

Pour chaque étape, vérifier :
1. **Entrée** : quel format arrive ? Est-il validé ?
2. **Transformation** : le renommage de champs est-il cohérent ?
   (ex: `relation` → `predicate`, `contributing_models` → `votes`)
3. **Sortie** : le format de sortie correspond-il à ce que l'étape suivante attend ?
4. **Erreur** : que se passe-t-il si cette étape échoue ?

### Points de rupture connus

- La conversion `ConsensusTriplet.relation` → `dict["predicate"]` dans `triplet_adapter.py`
  — si le consensus engine change le nom du champ, l'adaptateur casse silencieusement
- La construction des `ModelVote` dans `pipeline.py` depuis `triplet["votes"]`
  — les clés du dict doivent correspondre exactement aux params de ModelVote()
- Le passage de `architecture_families` à `crystallize()` — d'où vient ce compte ?
  Est-il calculé à partir des votes ou hardcodé ?

---

## A10 — SÉCURITÉ SOLANA (bridge.py / client.py)

### Ce qu'on cherche

Tout le code marqué `AUDIT_REQUIRED` + les risques de sérialisation incorrecte.

### Commandes de détection

```bash
# Tous les marqueurs AUDIT_REQUIRED
grep -rn "AUDIT_REQUIRED" --include="*.py" --include="*.rs" \
  services/solana/ programs/

# Vérifier que les constantes Rust matchent les constantes Python
grep -n "MAX_SUBJECT_LEN\|MAX_PREDICATE_LEN\|MAX_OBJECT_LEN\|SCORE_SCALE" \
  services/solana/bridge.py programs/epp/src/constants.rs

# Overflow potentiel dans float_to_u16
grep -n "float_to_u16\|u16_to_float\|SCORE_SCALE" services/solana/bridge.py

# Vérifier que les enums Python matchent les enums Rust
grep -n "EPISTEMIC_TYPE_MAP\|CONFIDENCE_TIER_MAP" services/solana/bridge.py
grep -n "EpistemicType\|ConfidenceTier" programs/epp/src/state.rs
```

### Points critiques

- Les strings sont tronquées à 64/128 bytes en UTF-8. Un caractère multi-byte
  pourrait être coupé au milieu → bytes invalides on-chain.
- Le `claim_hash` est converti de hex string (64 chars) à bytes (32 bytes).
  Vérifier que la conversion est bien big-endian et déterministe.
- Le devnet guard (`MAINNET absent de l'enum`) est-il contournable ?

---

## RAPPORT FINAL

### Structure attendue

```markdown
# Rapport d'Audit Interne — EPP_Verdict
Date : YYYY-MM-DD
Auditeur : Claude Code (supervisé)

## Résumé
- X trouvailles 🔴 CRITIQUE
- Y trouvailles 🟡 FRAGILE
- Z trouvailles 🟢 ACCEPTABLE

## Trouvailles critiques (🔴)
[détail de chaque trouvaille]

## Trouvailles fragiles (🟡)
[détail de chaque trouvaille]

## Trouvailles acceptables (🟢)
[liste résumée]

## Recommandations prioritaires
[top 5 corrections classées par impact/effort]
```

### Contraintes du rapport

- **Maximum 1 page par angle** (A1-A10). Pas de verbosité.
- **Chaque trouvaille a un identifiant** [AX-NNN] pour référence ultérieure.
- **Pas de corrections dans le rapport.** Seulement des constats et des recommandations.
- **Les trouvailles 🟢 ACCEPTABLE sont listées sans détail** (juste fichier:ligne + un mot).
- **Le rapport est un seul fichier** : `AUDIT_REPORT.md` dans le répertoire racine.

### Périmètre

Fichiers à auditer (par ordre de priorité) :

| Priorité | Fichiers | Raison |
|---|---|---|
| 🔴 P0 | `engine.py` | 3000+ lignes, toute la DB, singletons |
| 🔴 P0 | `pipeline.py` | Pont unique ESMM → DB, point de failure critique |
| 🔴 P0 | `pool.py` | Lifecycle des connexions, singleton corrigé |
| 🟡 P1 | `orchestrator.py` | Gestion d'état, cycles, timeouts |
| 🟡 P1 | `cycle_manager.py` | Fallbacks, rotation, extraction |
| 🟡 P1 | `bridge.py`, `client.py` | Sérialisation on-chain |
| 🟡 P1 | `triplet_extractor.py` | Pipeline extraction multi-modèle |
| 🟢 P2 | `attestation.py` | Pydantic, cristallisation |
| 🟢 P2 | `consensus_engine.py` | Algorithme de vote |
| 🟢 P2 | Tous les autres services/ | |

### Temps estimé

~30 minutes pour les P0, ~30 minutes pour les P1, ~15 minutes pour les P2.
Total : ~1h15 de travail Claude Code.

---

*Méthodologie d'audit interne — EPP_Verdict*
*Version 1.0 — Février 2026*
*Basé sur les patterns de bugs identifiés pendant les Phases 3 et 3.1*
