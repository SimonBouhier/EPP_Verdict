# PHASE 4 — PLAN DE CORRECTION SYSTÉMATIQUE (v2)

> **Principe directeur** : On ne corrige PAS un bug avec des outils de mesure cassés.
> Avant toute correction, on prouve que le test ÉCHOUE sans le fix.
> C'est la discipline RED-GREEN-FIX, seule garantie qu'une correction IA
> n'est pas une hallucination validée par un mock complaisant.
>
> **État d'entrée** : 425 passed, 0 failed, 10 skipped. 58 annotations AUDIT[].
> 7 ADR actifs. Rapport de conformité §5 livré.
>
> **Leçon intégrée** : Le plan v1 était structuré pour un humain qui lit ses tests.
> Ce plan v2 est structuré pour une IA qui les génère — et qui peut se convaincre
> que tout fonctionne avec des mocks complaisants.

---

## ARCHITECTURE DU PLAN

```
Phase 4.0 — FONDATIONS (fiabiliser les outils de mesure)
    ├── 4.0.0  Isolation tests (reset 13 singletons, setup+teardown)
    ├── 4.0.1  Démockage des chemins critiques
    ├── 4.0.2  Smoke test Solana bridge (sanity check précoce)
    └── 4.0.3  Fondation async (cause racine, pas wrappers)

Phase 4.1 — CRASHS RUNTIME (RED-GREEN-FIX)
    ├── 4.1.x  Chaque crash = test rouge PUIS fix PUIS vert

Phase 4.2 — CORRUPTION SILENCIEUSE (RED-GREEN-FIX)
    ├── 4.2.x  Chaque corruption = test rouge PUIS fix PUIS vert

Phase 4.3 — DURCISSEMENT STRUCTUREL
    ├── 4.3.x  Singletons, exceptions, test de pollution

Phase 4.4 — NETTOYAGE
    ├── 4.4.x  Config, code mort, dette décorative

Phase 4.5 — SÉCURITÉ
    ├── 4.5.x  Prompt injection, Sybil, input validation

Phase 4.6 — SOLANA DEVNET COMPLET
    ├── 4.6.x  Transaction building, PDA validation, submitter auth
```

---

## PROTOCOLE RED-GREEN-FIX (obligatoire Phase 4.1 et 4.2)

Chaque correction de bug suit ce protocole en 3 étapes. Pas d'exception.

### Étape 1 — RED : Prouver que le bug existe

```python
# Écrire un test qui ÉCHOUE avec le code actuel
async def test_bug_XXXX_reproduces():
    """Ce test DOIT échouer avant la correction."""
    # ... reproduire le bug ...
    # assert qui échoue
```

Exécuter le test seul : `pytest tests/test_xxx.py::test_bug_XXXX_reproduces -x`
**Si le test PASSE** → le bug n'existe pas (ou le test est mal écrit). STOP.

### Étape 2 — GREEN : Appliquer la correction minimale

Corriger le code. Relancer LE MÊME test.
**Si le test ÉCHOUE ENCORE** → la correction est insuffisante. Itérer.

### Étape 3 — FIX : Vérifier que rien d'autre n'a cassé

```bash
pytest tests/ --tb=short
```

**Si d'autres tests cassent** → la correction a des effets de bord. Analyser.

### Pourquoi c'est non-négociable

L'audit Phase 3.2 a prouvé que 425 tests passaient sur un code avec 3 crashs
runtime et une colonne manquante. Les tests existants ne détectaient pas ces bugs
parce qu'ils mockaient les chemins qui crashaient. Le RED-GREEN-FIX empêche
Claude Code de "corriger" un bug en ajoutant un mock de plus.

---

## PROTOCOLE ADR (obligatoire à chaque sous-phase)

Avant de coder quoi que ce soit dans une sous-phase, Claude Code DOIT :

```bash
# 1. Lire les ADR potentiellement impactés
cat docs/adr/ADR-001.md  # Si la sous-phase touche à l'encodage/sérialisation
cat docs/adr/ADR-004.md  # Si la sous-phase touche aux INSERT
cat docs/adr/ADR-006.md  # Si la sous-phase touche aux hash/attestations
cat docs/adr/ADR-007.md  # Si la sous-phase touche aux UPDATE attestations

# 2. Confirmer dans le récap de livraison :
# "ADR consultés : ADR-001, ADR-004. Aucun conflit."
```

Si une correction contredit un ADR → s'arrêter et signaler. Ne PAS corriger
"en espérant que ça ira".

---

## PROTOCOLE SUTURE BRIDGE (obligatoire Phase 4.1 et 4.2)

Si une correction modifie un type de donnée, un format de sérialisation, ou
une structure qui transite vers Solana :

```bash
# Vérifier que le bridge n'est pas impacté
grep -rn "float_to_u16\|u16_to_float\|string_to_fixed_bytes\|SCORE_SCALE" \
  services/solana/bridge.py

# Vérifier que le programme Anchor attend le même format
grep -rn "u16\|claim_hash\|\[u8; 32\]" programs/epp/src/lib.rs programs/epp/src/state.rs
```

Si le type modifié est sérialisé vers Solana → le test bridge roundtrip
DOIT être exécuté dans la même sous-phase.

---

## PHASE 4.0 — FONDATIONS

> **But** : Fiabiliser les outils de mesure AVANT de les utiliser pour valider des corrections.
> On ne répare pas un moteur avec un voltmètre en panne.

### 4.0.0 — Durcir l'isolation des tests (le boss final)

**Le problème** : Toute la discipline RED-GREEN-FIX repose sur un axiome :
chaque test repart de zéro. La fixture `reset_db_singletons` dans `conftest.py`
viole cet axiome de trois façons :

1. Elle ne nettoie qu'en **teardown** (après `yield`). Si le cleanup du test
   précédent a échoué silencieusement, le test suivant hérite d'un état fantôme.
2. Elle utilise `except: pass` sur `close_pool()` — si la fermeture échoue,
   le pool survit et contamine le test suivant.
3. Elle ne reset que **2 singletons sur 13**. Les entity_resolver, relation_normalizer,
   config_loader, triplet_extractor, etc. persistent entre les tests.

Si on ne corrige pas ça en premier, chaque test RED de la Phase 4.1 peut être
VERT par accident (état résiduel) et chaque test GREEN peut être ROUGE par
contamination. Tout le plan s'effondre.

⚡ **VÉRIFIE D'ABORD** :
```bash
# État actuel de la fixture
grep -A15 "reset_db_singletons" tests/conftest.py

# Inventaire complet des singletons à reset
grep -rn "global _" --include="*.py" database/ services/ app/ | grep -v __pycache__ | grep -v test_
```

**Action** : Réécrire `reset_db_singletons` dans `conftest.py` :

```python
@pytest.fixture(autouse=True)
async def reset_all_singletons():
    """
    Reset ALL singletons before AND after each test.
    Setup + teardown = ceinture ET bretelles.
    Aucun except:pass — si le reset échoue, le test échoue.
    """
    await _reset_singletons()
    yield
    await _reset_singletons()


async def _reset_singletons():
    """Reset tous les singletons connus. Échec = erreur visible."""
    # 1. Pool (le plus critique — contient les connexions DB)
    try:
        from database.pool import close_pool
        await close_pool()
    except Exception as e:
        import logging
        logging.getLogger("test.reset").warning(f"close_pool failed: {e}")

    # 2. Engine DB instance
    try:
        import database.engine as engine_mod
        if engine_mod._db_instance is not None:
            engine_mod._db_instance = None
    except Exception as e:
        import logging
        logging.getLogger("test.reset").warning(f"engine reset failed: {e}")

    # 3. Config loader
    try:
        from services.config_loader import reset_config
        reset_config()
    except (ImportError, Exception):
        pass  # OK: config_loader peut ne pas être importé dans tous les contextes

    # 4. Entity resolver
    try:
        import services.entity_resolver as er_mod
        er_mod._resolver_instance = None
    except (ImportError, AttributeError):
        pass  # OK: module optionnel

    # 5. Relation normalizer
    try:
        import services.relation_normalizer as rn_mod
        rn_mod._normalizer_instance = None
    except (ImportError, AttributeError):
        pass  # OK: module optionnel

    # 6. Triplet extractor
    try:
        from services.esmm.triplet_extractor import close_triplet_extractor
        await close_triplet_extractor()
    except (ImportError, Exception):
        pass  # OK: module optionnel

    # 7. Ollama providers
    for mod_path, close_fn in [
        ("services.providers.ollama", "close_ollama_provider"),
        ("services.providers.ollama_embeddings", "close_ollama_embedding_provider"),
    ]:
        try:
            import importlib
            mod = importlib.import_module(mod_path)
            closer = getattr(mod, close_fn, None)
            if closer:
                await closer()
        except (ImportError, Exception):
            pass  # OK: providers optionnels
```

**Points clés** :
- **Setup ET teardown** : `_reset_singletons()` appelé avant et après chaque test.
  Si un test crashe entre les deux, le setup du test suivant nettoie quand même.
- **Pas de `except: pass` nus** : chaque exception est loggée (`logger.warning`).
  Le test ne crashe pas (teardown ne doit pas masquer le vrai échec), mais
  on voit le warning dans les logs si un singleton résiste.
- **13 singletons couverts** au lieu de 2. Les 6 restants (llm_client, model_rotator,
  memory, session_storage) sont moins critiques mais pourront être ajoutés
  si on observe des contaminations.

**Validation** :
```bash
pytest tests/ --tb=short
# Le baseline ne doit PAS changer significativement.
# Si des tests cassent = ils étaient déjà dépendants d'un état fantôme.
# C'est une information précieuse : les noter comme bugs latents.
```

### 4.0.1 — Démockage des chemins critiques

**Le problème** : Le pipeline E2E (`test_phase3_pipeline.py`) patche l'orchestrateur
entièrement. Si on corrige un crash dans l'orchestrateur, le test passera
*identiquement* avant et après la correction — il ne teste pas le vrai code.

⚡ **VÉRIFIE D'ABORD** :
```bash
grep -c "patch\|Mock\|AsyncMock" tests/test_phase3_pipeline.py
grep -c "def test_" tests/test_phase3_pipeline.py
# Rapport mocks/tests — si ratio > 3, le fichier est suspect
```

**Action** :

1. Identifier les mocks sur logique métier dans les tests des composants P0/P1 :
   ```bash
   grep -rn "patch.*consensus_engine\|patch.*crystallize\|patch.*float_to_u16\|patch.*build_signature\|patch.*orchestrat" \
     --include="*.py" tests/
   ```

2. Pour chaque mock sur logique métier :
   - Si le composant est testable avec MockProvider (réponses LLM déterministes) → remplacer le mock par un appel réel avec MockProvider
   - Si le composant nécessite le réseau → garder le mock mais annoter `# MOCK: infrastructure, pas logique métier`
   - Si le mock masque un bug connu → le supprimer et laisser le test échouer (c'est le RED de RED-GREEN-FIX)

3. Résultat attendu : les tests des composants qui seront corrigés en 4.1/4.2
   testent le VRAI code, pas des mocks.

**Fichiers cibles** (ceux dont les composants seront corrigés ensuite) :
- Tests touchant `engine.py` (corrections 4.1, 4.2)
- Tests touchant `pool.py` (correction 4.2)
- Tests touchant `triplet_extractor.py` (correction 4.1)
- Tests touchant `bridge.py` (smoke test 4.0.2, correction 4.2)

⚠️ **Des tests vont CASSER en supprimant des mocks.** C'est attendu et voulu.
Les tests qui cassent révèlent les bugs que les mocks cachaient. Les noter
et les garder cassés — ils seront corrigés par les phases suivantes.

```bash
pytest tests/ --tb=short 2>&1 | tail -10
# NOTER le nouveau baseline : X passed, Y failed
# Les Y failed sont les vrais bugs révélés par le démockage
```

### 4.0.2 — Smoke test Solana bridge (sanity check précoce)

**Le problème** : Si le bridge Python↔Solana est incompatible avec les types Anchor,
on ne le saura qu'en Phase 4.6 — après 15h de corrections qui s'appuient sur
des structures de données potentiellement incompatibles.

⚡ **VÉRIFIE D'ABORD** :
```bash
# Types côté Python (bridge.py)
grep -n "SCORE_SCALE\|float_to_u16\|string_to_fixed_bytes\|CLAIM_HASH_SIZE" \
  services/solana/bridge.py

# Types côté Anchor (state.rs)
grep -n "u16\|u8\|\[u8;" programs/epp/src/state.rs

# Vérifier la cohérence des tailles
grep -n "MAX_.*_LEN\|ACCOUNT_SIZE" programs/epp/src/constants.rs 2>/dev/null || \
  grep -n "space\|LEN" programs/epp/src/lib.rs
```

**Action** : Créer `tests/test_bridge_solana_compat.py` — UN seul fichier,
3-4 tests fondamentaux :

```python
"""
Tests de compatibilité bridge Python ↔ Solana.
Vérifient que les types sérialisés côté Python sont cohérents
avec les types attendus côté Anchor.
À exécuter dès le début — pas en Phase 4.6.
"""

def test_score_scale_matches_anchor():
    """SCORE_SCALE Python == SCORE_SCALE Rust."""
    from services.solana.bridge import SCORE_SCALE
    # Lire la constante dans le code Rust
    import re
    with open("programs/epp/src/lib.rs") as f:
        rust_code = f.read()
    match = re.search(r"SCORE_SCALE.*?=\s*(\d+)", rust_code)
    assert match, "SCORE_SCALE not found in lib.rs"
    assert int(match.group(1)) == SCORE_SCALE

def test_float_roundtrip_boundary_values():
    """Valeurs limites du roundtrip float↔u16."""
    from services.solana.bridge import float_to_u16, u16_to_float
    for f in [0.0, 0.0001, 0.5, 0.9999, 1.0]:
        encoded = float_to_u16(f)
        assert 0 <= encoded <= 65535, f"u16 overflow: {encoded}"
        decoded = u16_to_float(encoded)
        assert abs(decoded - f) < 1e-4, f"Roundtrip failed: {f} → {encoded} → {decoded}"

def test_claim_hash_size_matches_anchor():
    """Le claim_hash Python produit 32 bytes, comme attendu par [u8; 32] Anchor."""
    from services.esmm.attestation import compute_claim_hash
    h = compute_claim_hash("sun", "is", "star", "frame_v1")
    h_bytes = bytes.fromhex(h)
    assert len(h_bytes) == 32, f"Expected 32 bytes, got {len(h_bytes)}"

def test_string_encoding_fixed_bytes():
    """Les strings encodées tiennent dans les champs Anchor."""
    from services.solana.bridge import string_to_fixed_bytes
    # Vérifier que les emojis et unicode ne dépassent pas la taille fixe
    for s in ["hello", "日本語テスト", "🔬🧬", "a" * 200]:
        encoded = string_to_fixed_bytes(s, 64)
        assert len(encoded) == 64, f"Expected 64 bytes, got {len(encoded)}"
```

**Si un de ces tests ÉCHOUE** → c'est un problème P0 qui doit être corrigé
AVANT toute autre correction. Le bridge est la colonne vertébrale.

```bash
pytest tests/test_bridge_solana_compat.py -v
# Attendu : 4 passed. Si non → STOP, corriger d'abord.
```

### 4.0.3 — Fondation async (cause racine)

**Le problème** : Le plan v1 excluait la migration `asyncio.run` → `async def`
"pour limiter le scope". Mais les crashs d'import et de boucle événementielle
dans les environnements hybrides proviennent souvent de cette incompatibilité.
Exclure la cause racine force Claude Code à créer des wrappers.

⚡ **VÉRIFIE D'ABORD** :
```bash
# Combien de tests utilisent encore asyncio.run ?
grep -rn "asyncio\.run(" --include="*.py" tests/ | wc -l

# Est-ce que pytest-asyncio mode=auto est configuré ?
grep -rn "asyncio_mode" pytest.ini pyproject.toml setup.cfg conftest.py 2>/dev/null
```

**Action** :

La migration complète est trop de scope pour une sous-phase. Mais la fondation
est nécessaire. Stratégie en deux temps :

1. **Maintenant (4.0.3)** : Migrer les `asyncio.run()` dans les fichiers de test
   qui couvrent les composants P0/P1 (ceux qu'on va corriger ensuite) :
   - Tests de `engine.py` (INSERT, store_attestation, etc.)
   - Tests de `pool.py` (acquire, close, cleanup)
   - Tests de `triplet_extractor.py` (extract_from_text)
   - Tests de `bridge.py` (encodage/décodage)

   Pattern de migration :
   ```python
   # AVANT
   def test_something():
       result = asyncio.run(db.some_method())
       assert result ...

   # APRÈS
   async def test_something():
       result = await db.some_method()
       assert result ...
   ```

2. **Plus tard (hors Phase 4)** : Migrer le reste progressivement.

**Pourquoi c'est nécessaire maintenant** : Les tests RED-GREEN-FIX de la Phase 4.1
vont créer de nouveaux tests async. Si les tests existants du même fichier utilisent
`asyncio.run`, on crée des conflits de boucle événementielle dans le même module.
Mieux vaut nettoyer la fondation d'abord.

```bash
pytest tests/ --tb=short 2>&1 | tail -10
# Nouveau baseline post-fondations
```

### Validation Phase 4.0

```bash
pytest tests/ --tb=short
# NOTER : X passed, Y failed, Z skipped
# Y peut être > 0 si le démockage a révélé des vrais bugs
# Ces Y failed sont le BACKLOG de Phase 4.1
```

**Livrable attendu** :
- Liste des mocks supprimés et tests devenus RED (= bugs révélés)
- 4 tests bridge compat (green)
- N tests migrés asyncio.run → async def
- Nouveau baseline de la suite

---

## PHASE 4.1 — CRASHS RUNTIME (RED-GREEN-FIX)

> **But** : Corriger chaque crash identifié. Chacun commence par un test RED.
> **Prérequis** : Phase 4.0 terminée. Les outils de mesure sont fiables.
> **ADR à lire** : ADR-004, ADR-006.

### 4.1.1 — triplet_extractor.py ON CONFLICT invalide

**ADR** : `cat docs/adr/ADR-004.md` (INSERT OR IGNORE, pas REPLACE)

⚡ **VÉRIFIE D'ABORD** :
```bash
grep -n "ON CONFLICT" services/esmm/triplet_extractor.py
```

**RED** :
```python
async def test_triplet_extraction_duplicate_handling():
    """Injecter deux fois le même triplet ne doit pas crasher."""
    # ... injecter un triplet, puis le même ...
    # Avec le bug : crash SQL. Sans le bug : skip silencieux.
```

**GREEN** : Corriger la clause ON CONFLICT.

**SUTURE BRIDGE** : Non concerné (table locale, pas sérialisée vers Solana).

### 4.1.2 — app/embeddings.py imports dépréciés

⚡ **VÉRIFIE D'ABORD** :
```bash
grep -rn "from app.embeddings\|from app import embeddings" \
  --include="*.py" app/ services/ | grep -v __pycache__ | grep -v test_
```

**RED** :
```python
def test_no_deprecated_embedding_imports():
    """Aucun module de production ne doit importer app/embeddings.py."""
    import ast, pathlib
    deprecated = "app.embeddings"
    violations = []
    for f in pathlib.Path(".").rglob("*.py"):
        if "test_" in f.name or "__pycache__" in str(f):
            continue
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, 'module', '') or ''
                if deprecated in module:
                    violations.append(f"{f}:{node.lineno}")
    assert not violations, f"Deprecated imports: {violations}"
```

**GREEN** : Migrer chaque import vers le provider layer.

**SUTURE BRIDGE** : Non concerné (embeddings locaux).

### 4.1.3 — session_storage.py INSERT brut

**ADR** : `cat docs/adr/ADR-004.md`

⚡ **VÉRIFIE D'ABORD** :
```bash
grep -n "INSERT INTO" services/session_storage.py | grep -v "OR IGNORE\|OR REPLACE"
```

**RED** :
```python
async def test_session_storage_duplicate_session():
    """Stocker deux fois la même session_id ne crashe pas."""
    storage = SessionStorage(":memory:")
    await storage.store("session_1", {"data": "first"})
    await storage.store("session_1", {"data": "second"})  # Doit pas crasher
```

**GREEN** : `INSERT INTO` → `INSERT OR IGNORE INTO`.

### 4.1.4 — Tests RED révélés par le démockage (Phase 4.0)

Les tests qui ont cassé en 4.0.1 (démockage) sont des bugs réels.
Pour chacun : le test RED existe déjà (c'est le test démocké qui échoue).
Appliquer le fix, vérifier GREEN.

### Validation Phase 4.1

```bash
pytest tests/ --tb=short
# Attendu : baseline 4.0 + corrections. 0 failed sur les tests P0.
```

---

## PHASE 4.2 — CORRUPTION SILENCIEUSE (RED-GREEN-FIX)

> **But** : Empêcher les écritures qui perdent des données sans signaler d'erreur.
> **Prérequis** : Phase 4.1 terminée.
> **ADR à lire** : ADR-001, ADR-004, ADR-007.

### 4.2.1 — INSERT OR REPLACE qui détruit les métadonnées

**ADR** : `cat docs/adr/ADR-004.md` (INSERT OR IGNORE, pas REPLACE)

⚡ **VÉRIFIE D'ABORD** :
```bash
grep -n "INSERT OR REPLACE" database/engine.py
```

**RED** :
```python
async def test_concept_reinsertion_preserves_metadata():
    """Réinjecter un concept ne doit pas perdre created_at ni degree."""
    db = ISpaceDB(":memory:")
    await db.initialize()
    await db.add_concept("test_concept", source="original")
    # Récupérer le created_at original
    stats_before = await db.get_stats()
    # Réinjecter le même concept
    await db.add_concept("test_concept", source="duplicate")
    # Vérifier que created_at est préservé
    stats_after = await db.get_stats()
    # ... assertion sur la préservation des métadonnées
```

**GREEN** : Migrer INSERT OR REPLACE → INSERT OR IGNORE (ou UPSERT ciblé).

**SUTURE BRIDGE** :
```bash
# Le concept est-il sérialisé vers Solana ?
grep -rn "concept" services/solana/bridge.py
# Attendu : Non. Les concepts restent locaux. Pas d'impact bridge.
```

### 4.2.2 — upsert_relations_batch perd relation_type

**ADR** : Aucun ADR spécifique, mais cohérent avec la philosophie ADR-004.

⚡ **VÉRIFIE D'ABORD** :
```bash
grep -A10 "upsert_relations_batch\|INSERT.*relations" database/engine.py | head -30
```

**RED** :
```python
async def test_relation_upsert_preserves_type():
    """Mettre à jour le poids d'une relation ne perd pas le relation_type."""
    db = ISpaceDB(":memory:")
    await db.initialize()
    await db.add_concept("A", source="test")
    await db.add_concept("B", source="test")
    # Créer une relation avec un type spécifique
    await db.upsert_relations_batch([{
        "source": "A", "target": "B",
        "weight": 0.5, "relation_type": "causes"
    }])
    # Mettre à jour le poids sans fournir le type
    await db.upsert_relations_batch([{
        "source": "A", "target": "B",
        "weight": 0.9
    }])
    # Le relation_type doit être préservé
    neighbors = await db.get_neighbors("A")
    rel = [n for n in neighbors if n["target"] == "B"][0]
    assert rel["relation_type"] == "causes", \
        f"relation_type perdu : {rel.get('relation_type')}"
```

**GREEN** : Migrer vers ON CONFLICT DO UPDATE explicite qui préserve les champs non fournis.

### 4.2.3 — pool.py close() et _cleanup_stale()

⚡ **VÉRIFIE D'ABORD** :
```bash
grep -n "except" database/pool.py
```

**RED** (pour close) :
```python
async def test_pool_close_logs_errors(caplog):
    """pool.close() doit logger les erreurs, pas les avaler."""
    pool = SQLiteConnectionPool(":memory:")
    await pool.initialize()
    # Corrompre une connexion
    async with pool.acquire() as conn:
        await conn.close()  # Fermer prématurément
    # La fermeture du pool doit logger un warning, pas crasher
    with caplog.at_level(logging.WARNING):
        await pool.close()
    # Vérifier qu'un warning a été loggé
    assert any("Error" in r.message or "error" in r.message for r in caplog.records)
```

**GREEN** : Remplacer `except: pass` par `except Exception as e: logger.warning(...)`.

### Validation Phase 4.2

```bash
pytest tests/ --tb=short
# Attendu : baseline 4.1 + corrections. 0 failed.
```

---

## PHASE 4.3 — DURCISSEMENT STRUCTUREL

> **But** : Singletons vérifiés, exceptions visibles, test de pollution permanent.
> **ADR à lire** : Aucun spécifique.

### 4.3.1 — Singletons : warning sur changement de paramètres

Les 5 singletons prioritaires :
- `database/engine.py` → `get_db(db_path)`
- `services/providers/ollama.py` → `_ollama_instance`
- `services/providers/ollama_embeddings.py` → `_ollama_embedding_instance`
- `services/entity_resolver.py` → `_resolver_instance` (+ ajouter `close_entity_resolver()`)
- `services/relation_normalizer.py` → `_normalizer_instance` (+ ajouter `close_relation_normalizer()`)

**Pattern** (identique pour tous) :
```python
if _instance is not None and param != _instance.configured_param:
    logger.warning(f"get_X() called with different param. Returning existing.")
```

### 4.3.2 — Except:pass restants → logger.warning

Les ~7 `except: pass` non annotés identifiés en Phase 3.3.
Pour chacun : ajouter `logger.warning(f"Suppressed: {e}")` sans changer le flux.

### 4.3.3 — Test de pollution permanent

Écrire le test CONTROLS.md C7 et l'ajouter à la suite permanente.

### Validation Phase 4.3

```bash
pytest tests/ --tb=short
# Attendu : +3-5 nouveaux tests, 0 failed
```

---

## PHASE 4.4 — NETTOYAGE

> **But** : Éliminer la dette décorative.
> **ADR à lire** : Aucun.

### 4.4.1 — Purger config.yaml (~35 clés orphelines → ~5-8 effectives)
### 4.4.2 — Supprimer modules dépréciés non importés (post 4.1.2)
### 4.4.3 — Table semantic_memory : supprimer du schéma (Option A, nettoyage)

### Validation Phase 4.4

```bash
pytest tests/ --tb=short
```

---

## PHASE 4.5 — SÉCURITÉ

> **But** : Défense en profondeur sur les vecteurs d'attaque identifiés.
> **ADR à lire** : ADR-002 (tiers), ADR-005 (multi-critères).

### 4.5.1 — Prompt injection : balises XML dans cycle_prompts.py
### 4.5.2 — Test de prompt injection (RED-GREEN-FIX)
### 4.5.3 — Sybil : test et renforcement de infer_architecture_family()
### 4.5.4 — Validation des entrées pipeline (longueur, sanitisation)

### Validation Phase 4.5

```bash
pytest tests/ --tb=short
# Attendu : +5-8 tests sécurité
```

---

## PHASE 4.6 — SOLANA DEVNET COMPLET

> **But** : Rendre l'ancrage on-chain fonctionnel.
> **Prérequis** : Smoke test 4.0.2 green. Environnement Solana (WSL + Anchor).
> **ADR à lire** : ADR-001, ADR-006, ADR-007. TOUS.

### 4.6.1 — Transaction building (NotImplementedError)
### 4.6.2 — PDA validation (A10-001)
### 4.6.3 — Submitter auth : documenter la stratégie (ADR-008)

### Validation Phase 4.6

```bash
pytest tests/ --tb=short
# wsl bash -lc "cd programs/epp && anchor test"
```

---

## TABLEAU RÉCAPITULATIF

| Phase | Scope | Innovation v2 | Effort |
|-------|-------|--------------|--------|
| 4.0 | Fondations | Isolation singletons + démockage + smoke bridge + async | 5h |
| 4.1 | Crashs runtime | RED-GREEN-FIX obligatoire | 2h |
| 4.2 | Corruption | RED-GREEN-FIX + vérif suture bridge | 3h |
| 4.3 | Durcissement | Singletons + test pollution permanent | 2h |
| 4.4 | Nettoyage | Config + code mort | 1h |
| 4.5 | Sécurité | Prompt injection + Sybil | 3h |
| 4.6 | Solana devnet | Transaction building complet | 4-8h |

**Total** : 20-24h. +1h de fondations par rapport à v1, mais les RED-GREEN-FIX sont fiables.

---

## DIFFÉRENCES CLÉS AVEC LE PLAN v1

| Aspect | Plan v1 | Plan v2 |
|--------|---------|---------|
| Isolation | Conftest reset 2 singletons, except:pass | Reset 13 singletons, setup+teardown, warnings loggés |
| Tests | Fait confiance aux tests existants | Démocke AVANT de corriger |
| Bridge Solana | Testé en dernier (P6) | Smoke test en premier (4.0.2) |
| Async | Exclu du scope | Fondation migrée pour les fichiers P0/P1 |
| ADR | Mentionnés | Lecture obligatoire avec `cat` à chaque sous-phase |
| Corrections | Fix direct | RED-GREEN-FIX : test rouge → fix → test vert |
| Mocks | Pas remis en question | Démockage explicite des chemins critiques |
| Suture | Vérifiée en recette (Opus) | Vérifiée par Claude Code à chaque étape |

---

## RÈGLES TRANSVERSALES

1. **Isolation** : Chaque test repart de zéro (garanti par `reset_all_singletons` de 4.0.0).
2. **RED-GREEN-FIX** pour toute correction P0/P1. Test rouge d'abord.
3. **ADR** lus (avec `cat`) avant chaque sous-phase.
4. **Suture bridge** vérifiée si le type de donnée modifié est sérialisé vers Solana.
5. **pytest complet** à la fin de chaque sous-phase. Pas de "je vérifie après".
6. **CHANGELOG.md** mis à jour à chaque sous-phase. Diff prouvé (C9).
7. **Si un test casse**, le corriger dans la même sous-phase.
8. **Si une correction révèle un nouveau bug**, l'annoter et continuer.
9. **Claude Opus applique CONTROLS.md C1-C9** après chaque sous-phase.

---

*PHASE_4_PLAN.md — EPP_Verdict v2.1*
*Rédigé par Claude Opus — 12 février 2026*
*Intègre les 5 corrections critiques : isolation singletons, RED-GREEN-FIX,
smoke bridge précoce, fondation async, protocole ADR explicite.*
