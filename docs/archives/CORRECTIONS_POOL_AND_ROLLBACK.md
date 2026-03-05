# CORRECTIONS CIBLÉES — Pool Isolation + Graph Delta Rollback

> **Instructions pour Claude Code.** Lis CLAUDE.md ET ce fichier.
> Deux corrections indépendantes, exécutées dans l'ordre.
>
> **État actuel** : 421 passed, 4 failed, 10 skipped
> **État cible** : 425 passed, 0 failed, 10 skipped

---

## PRINCIPE — NE CASSER AUCUN DES 421 TESTS QUI PASSENT

Après chaque correction, exécuter :

```bash
pytest tests/ -v --tb=short 2>&1 | tail -40
```

Si un test qui passait avant échoue → **annuler et comprendre pourquoi.**

---

## CORRECTION 1 — Pool DB singleton empêche l'isolation des tests

### Diagnostic

`test_phase3_question_seeder.py::TestSeedGraphFromQuestion::test_seed_graph_on_empty`
passe en isolation, échoue en suite.

**Cause racine** : `pool.py::get_pool()` est un singleton global :

```python
async def get_pool(db_path="data/ispace.db", pool_size=10):
    global _pool_instance
    if _pool_instance is None:                    # ← ne vérifie PAS si le path a changé
        _pool_instance = SQLiteConnectionPool(db_path, pool_size=pool_size)
        await _pool_instance.initialize()
    return _pool_instance
```

Quand le test A crée `ISpaceDB("/tmp/test_a.db")` et appelle `initialize()`, le pool
singleton est créé pour `test_a.db`. Quand le test B crée `ISpaceDB("/tmp/test_b.db")`
et appelle `initialize()`, **le pool retourne encore les connexions de `test_a.db`** car
`_pool_instance is not None`.

Résultat : `seed_graph_from_question` appelle `db.get_stats()` qui utilise la connexion
du pool (pointant vers un ancien DB avec des concepts), voit `concepts > 0`, et skip.

### Correction 1a — Fixture conftest.py pour reset du pool entre tests async

⚡ **VÉRIFIE D'ABORD** : `cat tests/conftest.py` — lis le contenu actuel.

Ajouter dans `tests/conftest.py` (sans supprimer ce qui existe déjà) :

```python
import pytest

@pytest.fixture(autouse=True)
async def reset_db_singletons():
    """Reset DB and pool singletons between tests to prevent cross-contamination."""
    yield
    # Teardown : fermer le pool et le singleton DB après chaque test
    try:
        from database.pool import close_pool
        await close_pool()
    except Exception:
        pass
    try:
        import database.engine as engine_mod
        engine_mod._db_instance = None
    except Exception:
        pass
```

⚠️ **IMPORTANT** : si `conftest.py` contient déjà un fixture `autouse` qui fait
quelque chose de similaire avec `close_pool()`, ne pas dupliquer — fusionner.

⚠️ **NOTE** : Cette fixture est `async` et `autouse=True`. Avec `asyncio_mode=auto`,
pytest-asyncio la détecte automatiquement pour les tests async. Pour les tests sync,
elle sera simplement ignorée (le yield revient immédiatement).

Si cette approche ne fonctionne pas (certains frameworks pytest-asyncio ne gèrent pas
les fixtures async autouse sur des tests sync), utiliser cette version sync-safe :

```python
import pytest
import asyncio

@pytest.fixture(autouse=True)
def reset_db_singletons_sync():
    """Reset DB singletons (sync-safe version)."""
    yield
    try:
        from database.pool import close_pool
        import database.engine as engine_mod
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(close_pool())
        except Exception:
            pass
        finally:
            loop.close()
        engine_mod._db_instance = None
    except Exception:
        pass
```

### Correction 1b — Amélioration optionnelle de get_pool()

⚡ **VÉRIFIE D'ABORD** : `grep -n "async def get_pool" database/pool.py`

Le singleton `get_pool()` ne vérifie pas si le `db_path` a changé. C'est le vrai
bug sous-jacent. Si tu veux le corriger à la source (en plus de la fixture) :

```python
async def get_pool(db_path="data/ispace.db", pool_size=10):
    global _pool_instance
    # Si le pool existe mais pointe vers un autre fichier, le fermer d'abord
    if _pool_instance is not None and str(_pool_instance.db_path) != str(db_path):
        await _pool_instance.close()
        _pool_instance = None
    if _pool_instance is None:
        _pool_instance = SQLiteConnectionPool(db_path, pool_size=pool_size)
        await _pool_instance.initialize()
    return _pool_instance
```

⚡ **VÉRIFIE D'ABORD** : `grep -n "db_path" database/pool.py | head -10`

Vérifier que `SQLiteConnectionPool` stocke bien `self.db_path` dans son `__init__`.
Si ce n'est pas le cas, l'ajouter :

```python
class SQLiteConnectionPool:
    def __init__(self, db_path, pool_size=10):
        self.db_path = db_path  # ← s'assurer que ça existe
        ...
```

### Vérification correction 1

```bash
# Le test doit passer en isolation ET en suite
pytest tests/test_phase3_question_seeder.py -v --tb=short
pytest tests/ -v --tb=short -k "question_seeder" 2>&1 | tail -10
# Et vérifier qu'on n'a rien cassé
pytest tests/ --tb=short 2>&1 | tail -5
```

---

## CORRECTION 2 — graph_delta rollback (3 failures)

### Diagnostic

Les 3 tests `test_graph_delta.py` qui échouent (1 confirmed, 2 potentiels en suite) :

```
test_rollback_restores_state — assert 0 >= 1
```

Le rollback retourne 0 car `rollback_deltas()` dans engine.py retourne 0 quand
ni `delta_ids` ni `to_timestamp` ne sont fournis :

```python
async def rollback_deltas(self, session_id, to_timestamp=None, delta_ids=None):
    if delta_ids:
        # query by delta_ids
    elif to_timestamp:
        # query by timestamp
    else:
        return 0   # ← BUG : devrait rollback tous les deltas de la session
```

Le test appelle probablement `rollback_deltas(session_id="test_session")` sans
`to_timestamp` ni `delta_ids`, ce qui est le cas d'usage le plus intuitif :
"annule tout ce que cette session a fait".

Il y a aussi un bug latent dans le rollback de `DELETE_EDGE` : un `INSERT INTO relations`
brut qui explose sur `PRIMARY KEY (source, target)` si l'edge existe déjà.

### Étape 2.1 — Corriger rollback_deltas pour supporter le cas "rollback all"

⚡ **VÉRIFIE D'ABORD** : `grep -n "async def rollback_deltas" database/engine.py`

Le code actuel (lignes ~1512-1540) :

```python
async def rollback_deltas(self, session_id, to_timestamp=None, delta_ids=None):
    async with self.connection() as conn:
        if delta_ids:
            # ... query by delta_ids
        elif to_timestamp:
            # ... query by to_timestamp
        else:
            return 0   # ← CHANGER ICI
```

Remplacer le bloc `else: return 0` par un fallback qui récupère TOUS les deltas
non-rollbackés de la session :

```python
        else:
            # Fallback: rollback ALL unrolled deltas for this session (LIFO)
            cursor = await conn.execute(
                """
                SELECT delta_id, operation, source, target, old_weight, old_kappa
                FROM graph_deltas
                WHERE session_id = ?
                  AND rolled_back_at IS NULL
                ORDER BY timestamp DESC
                """,
                (session_id,)
            )
```

### Étape 2.2 — Sécuriser le rollback de DELETE_EDGE

⚡ **VÉRIFIE D'ABORD** : `grep -n "DELETE_EDGE.value" database/engine.py`

Dans la boucle de rollback (~ligne 1557), le rollback d'un DELETE_EDGE fait :

```python
elif operation == DeltaOperation.DELETE_EDGE.value and old_weight is not None:
    await conn.execute(
        """
        INSERT INTO relations (source, target, weight, kappa, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (source, target, old_weight, old_kappa or 0.5, time.time())
    )
```

Si l'edge existe déjà (cas de rollbacks partiels, ou corruption), ça explose.
Remplacer par `INSERT OR REPLACE` :

```python
elif operation == DeltaOperation.DELETE_EDGE.value and old_weight is not None:
    await conn.execute(
        """
        INSERT OR REPLACE INTO relations (source, target, weight, kappa, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (source, target, old_weight, old_kappa or 0.5, time.time())
    )
```

### Étape 2.3 — Vérifier le test lui-même

⚡ **VÉRIFIE D'ABORD** : `cat tests/test_graph_delta.py` — lis le test complet.

Le test `test_rollback_restores_state` fait probablement :

1. Crée des concepts
2. Applique un ADD_EDGE delta avec un session_id
3. Appelle `rollback_deltas(session_id)` sans timestamp ni delta_ids
4. Assert que le count est >= 1

Après la correction 2.1, le rollback devrait trouver le delta et retourner 1.

Vérifie aussi que les autres tests `test_graph_delta.py` n'ont pas de problèmes
similaires. Le test qui faisait `assert count >= 1` après un rollback devrait
maintenant passer.

Si d'autres tests échouent sur des `UNIQUE constraint` lors de `apply_delta` avec
`ADD_EDGE`, c'est probablement dû à la pollution entre tests (même DB). La correction 1
(fixture `reset_db_singletons`) devrait résoudre ça.

### Vérification correction 2

```bash
pytest tests/test_graph_delta.py -v --tb=short
```

**Cible** : 9/9 PASSED.

---

## VALIDATION FINALE

```bash
pytest tests/ -v --tb=short 2>&1 | tail -40
```

### État attendu

| Métrique | Avant | Après |
|----------|-------|-------|
| **PASSED** | 421 | 425 |
| **FAILED** | 4 | 0 |
| **SKIPPED** | 10 | 10 |
| **ERROR** | 0 | 0 |

### Si des tests résiduels échouent encore

Si `test_graph_delta` a des failures liées à la pollution DB entre tests (pas au
rollback lui-même), la fixture `reset_db_singletons` de la correction 1 devrait
les résoudre. Si ce n'est pas le cas, vérifier que les tests graph_delta créent
bien leur propre `ISpaceDB` temporaire au lieu d'utiliser `get_db()` global.

### CHANGELOG.md

Ajouter à l'entrée Phase 3.1 :

```markdown
- Corrigé isolation DB tests : fixture conftest.py reset pool + singleton entre tests
- Corrigé rollback_deltas() : supporte rollback all (sans delta_ids ni to_timestamp)
- Sécurisé rollback DELETE_EDGE : INSERT OR REPLACE (anti UNIQUE constraint)
- Tests: 425 passed, 0 failed, 10 skipped
```

---

*Corrections ciblées — pool isolation + graph_delta rollback*
*Base : 421 passed, 4 failed, 10 skipped*
*Cible : 425 passed, 0 failed, 10 skipped*
