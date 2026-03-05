# DIRECTIVE — ADR-013 : Graphe Persistant & Cache-Hit Épistémique

## Contexte

Actuellement, chaque run de `run_pipeline()` repart à zéro.
`data/epp.db` existe et contient les 25 tables nécessaires.
`ISpaceDB.get_attestation_by_hash()` existe (engine.py:2873).
`compute_claim_hash()` existe (attestation.py).

Objectif : avant de lancer les cycles ESMM, vérifier si une attestation
récente existe déjà en base. Si oui → retour immédiat (0 modèles invoqués).
Si non → pipeline normal → stockage en base persistante.

---

## Protocole RED-GREEN-FIX obligatoire

Étape 0 — RED d'abord : le test doit échouer AVANT toute modification.
Montrer le log `pytest` rouge. Pas de test rouge = directive rejetée.

---

## Fichiers à modifier (ordre strict)

### 0. `tests/test_pipeline_cache.py` — TEST RED (nouveau fichier)

Créer ce fichier. Il doit échouer immédiatement avec `AssertionError`
car `PipelineConfig` n'a pas encore `cache_ttl_hours`.

```python
"""
ADR-013 RED — Cache-hit épistémique.
Ces tests DOIVENT échouer avant implémentation.
"""
import asyncio
import os
import tempfile
import pytest

from services.esmm.pipeline import PipelineConfig, run_pipeline
from database.engine import ISpaceDB


@pytest.mark.asyncio
async def test_pipeline_config_has_cache_ttl():
    """RED: PipelineConfig doit exposer cache_ttl_hours."""
    config = PipelineConfig()
    assert hasattr(config, "cache_ttl_hours"), \
        "PipelineConfig doit avoir cache_ttl_hours"
    assert isinstance(config.cache_ttl_hours, (int, float))
    assert config.cache_ttl_hours > 0


@pytest.mark.asyncio
async def test_cache_hit_returns_without_esmm(tmp_path):
    """RED: un claim déjà attesté ne doit pas invoquer les modèles."""
    from unittest.mock import AsyncMock, patch
    from services.esmm.attestation import compute_claim_hash

    db_path = str(tmp_path / "test_cache.db")
    db = ISpaceDB(db_path)
    await db.initialize()

    # Insérer une attestation existante directement en DB
    claim_hash = compute_claim_hash(
        subject="water",
        predicate="boils_at",
        object="100C",
        frame="general_knowledge_v1.0"
    )

    # Vérifier que PipelineResult expose from_cache
    config = PipelineConfig(cache_ttl_hours=24)
    assert hasattr(config, "cache_ttl_hours")


@pytest.mark.asyncio
async def test_persistent_db_used_when_path_provided(tmp_path):
    """RED: run_pipeline doit accepter une DB persistante (non-temp)."""
    db_path = str(tmp_path / "persistent.db")
    db = ISpaceDB(db_path)
    await db.initialize()

    # Vérifier que la DB persiste entre deux instanciations
    db2 = ISpaceDB(db_path)
    await db2.initialize()
    assert os.path.exists(db_path)
```

**Vérification RED :**
```bash
pytest tests/test_pipeline_cache.py -v 2>&1 | tail -10
# Attendu : FAILED (AttributeError: 'PipelineConfig' has no attribute 'cache_ttl_hours')
```

---

### 1. `config.yaml` — ajouter section cache

Après la section `esmm:`, ajouter :

```yaml
# ============================================================================
# CACHE ÉPISTÉMIQUE (ADR-013)
# ============================================================================
cache:
  enabled: true
  ttl_hours: 168          # 7 jours — re-délibération si attestation plus ancienne
  min_tier_for_cache: "proposition"  # En dessous de ce tier : toujours re-délibérer
```

---

### 2. `services/esmm/pipeline.py` — 3 modifications

**2a. `PipelineConfig` — ajouter champ (après `metrological_frame`) :**

```python
    metrological_frame: Optional[str] = None
    cache_ttl_hours: float = 168.0    # ADR-013 : TTL cache (7 jours par défaut)
    use_cache: bool = True             # ADR-013 : désactivable pour les scénarios de test
```

**2b. `PipelineResult` — ajouter champ :**

```python
    errors: List[str]
    from_cache: bool = False           # ADR-013 : True si retourné depuis le graphe persistant
    cache_hit_hash: Optional[str] = None  # ADR-013 : claim_hash de l'attestation trouvée
```

**2c. `run_pipeline()` — ajouter le cache-hit AVANT `_extract_triplets_from_question` :**

Insérer juste après la validation d'input (ligne ~285) et AVANT le bloc
`if esmm_config is not None and claim_nature == "deterministic"` :

```python
        # ADR-013 : Cache-hit — vérifier si une attestation récente existe
        if config.use_cache and config.cache_ttl_hours > 0:
            cached = await _check_cache(
                question=question,
                db=db,
                config=config,
                esmm_config=esmm_config,
            )
            if cached is not None:
                logger.info("[Pipeline] Cache-hit: %s", cached.cache_hit_hash)
                return cached
```

**2d. Nouvelle fonction `_check_cache()` — ajouter après `_run_deterministic_pipeline()` :**

```python
async def _check_cache(
    question: str,
    db: "ISpaceDB",
    config: "PipelineConfig",
    esmm_config: Optional["ESMMRunConfig"],
) -> Optional["PipelineResult"]:
    """
    ADR-013 : Vérifie si une attestation récente existe pour ce claim.

    Retourne PipelineResult.from_cache=True si hit, None si miss.
    Ne fait AUCUNE modification en base.
    """
    import time
    from .attestation import compute_claim_hash, EpistemicAttestation, Signature5D

    try:
        # Calculer le claim_hash anticipé pour la question principale
        # Le subject/predicate/object sont inconnus avant ESMM — on cherche
        # par question dans les attestations récentes
        rows = await db.get_attestations_by_subject(
            subject=question[:64],
            min_consensus=config.min_consensus_for_attestation,
        )

        if not rows:
            return None

        # Filtrer par TTL
        now = time.time()
        ttl_seconds = config.cache_ttl_hours * 3600
        fresh_rows = [
            r for r in rows
            if (now - r.get("timestamp", 0)) < ttl_seconds
        ]

        if not fresh_rows:
            return None

        # Filtrer par tier minimum
        TIER_ORDER = {"sandbox": 0, "proposition": 1, "validated": 2, "verified": 3}
        min_tier_val = TIER_ORDER.get(config.get_min_tier_for_cache(), 1)
        eligible = [
            r for r in fresh_rows
            if TIER_ORDER.get(r.get("confidence_tier", "sandbox"), 0) >= min_tier_val
        ]

        if not eligible:
            return None

        best = eligible[0]

        # Reconstruire un EpistemicAttestation minimal depuis le dict DB
        cached_att = EpistemicAttestation(
            claim_hash=best["claim_hash"],
            subject=best["subject"],
            predicate=best["predicate"],
            object=best["object"],
            consensus_score=best.get("consensus_score", 0.0),
            models_consulted=best.get("models_consulted", 0),
            models_agreeing=best.get("models_agreeing", 0),
            model_votes=[],
            signature=Signature5D(
                agreement=best.get("sig_agreement", 0.0),
                semantic_consistency=best.get("sig_semantic_consistency", 0.0),
                centrality=best.get("sig_centrality", 0.0),
                stability=best.get("sig_stability", 0.0),
                relation_diversity=best.get("sig_relation_diversity", 0.0),
            ),
            epistemic_type=best.get("epistemic_type", "foundational"),
            confidence_tier=best.get("confidence_tier", "sandbox"),
            metrological_frame=best.get("metrological_frame", ""),
            consensus_meta=best.get("consensus_meta", {}),
        )

        return PipelineResult(
            run_id=best.get("run_id", 0),
            question=question,
            attestations=[cached_att],
            triplets_extracted=0,
            triplets_attested=1,
            triplets_injected=0,
            duration_ms=0.0,
            errors=[],
            from_cache=True,
            cache_hit_hash=best["claim_hash"],
        )

    except Exception as e:
        # Cache miss en cas d'erreur — ne pas bloquer le pipeline
        logger.warning("[Pipeline] Cache lookup failed (continuing): %s", e)
        return None
```

**Note :** `config.get_min_tier_for_cache()` nécessite d'ajouter une méthode
à `PipelineConfig` ou de lire depuis `config.yaml`. Lire depuis `config.yaml`
via `get_section("cache", {}).get("min_tier_for_cache", "proposition")`.

---

### 3. `demos/scenario_6_full_pipeline.py` — désactiver le cache pour les benchmarks

Dans `run_epistemic_claim()`, modifier la création de `PipelineConfig` :

```python
        # ADR-013 : cache désactivé en mode benchmark — chaque claim doit
        # déclencher une délibération complète pour mesurer les performances réelles
        config = PipelineConfig(
            metrological_frame=claim_entry.get("frame", "general_knowledge_v1.0"),
            use_cache=False,   # ← ajouter
        )
```

Idem dans `run_rwa_claim()`.

---

### 4. `cli/epp_cli.py` — utiliser `data/epp.db` (base persistante)

Vérifier que la CLI instancie `ISpaceDB("data/epp.db")` et non un temp.
Si ce n'est pas le cas, corriger. La CLI est le seul point d'entrée
qui DOIT écrire dans la base persistante.

---

## Vérification complète

```bash
# 1. RED → GREEN
pytest tests/test_pipeline_cache.py -v 2>&1 | tail -5
# → 3 passed

# 2. Non-régression
pytest tests/ --tb=short -q 2>&1 | tail -3
# → 706+ passed, 0 failed

# 3. Test fonctionnel manuel
# Soumettre le même claim deux fois via CLI
python -m cli.epp_cli ask "Water boils at 100 degrees Celsius" --frame general_knowledge_v1.0
# Run 1 : ~150s (délibération complète)
python -m cli.epp_cli ask "Water boils at 100 degrees Celsius" --frame general_knowledge_v1.0
# Run 2 : <1s (cache-hit — [Pipeline] Cache-hit: <hash>)

# 4. Vérifier que le scénario 6 ignore le cache (use_cache=False)
python demos/scenario_6_full_pipeline.py 2>&1 | grep -i "cache"
# → aucune ligne "Cache-hit" attendue
```

---

## Invariants à respecter

- `_check_cache()` ne modifie JAMAIS la base — lecture seule
- En cas d'exception dans `_check_cache()` → pipeline normal (jamais bloquant)
- `use_cache=False` dans tous les scénarios de benchmark
- Le cache ne s'applique PAS au chemin déterministe (ADR-012) — celui-ci
  a déjà son propre TTL via `is_snapshot_fresh()`
- `from_cache=True` dans le PipelineResult est loggué mais ne part pas on-chain

---

## CHANGELOG à ajouter

```
## [2026-03-XX] ADR-013 — Graphe persistant & cache-hit épistémique

- `PipelineConfig` : +`cache_ttl_hours` (défaut 168h), +`use_cache` (défaut True)
- `PipelineResult` : +`from_cache`, +`cache_hit_hash`
- `run_pipeline()` : cache-hit lookup avant cycles ESMM via `_check_cache()`
- `_check_cache()` : lecture seule, filtrage TTL + tier minimum, non-bloquant
- `config.yaml` : section `cache` (enabled, ttl_hours, min_tier_for_cache)
- Scénarios benchmark : `use_cache=False` (délibération complète toujours)
- N tests RED-GREEN-FIX. Baseline : 706 → XXX passed.
```
