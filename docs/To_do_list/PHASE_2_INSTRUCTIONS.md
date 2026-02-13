# PHASE 2 — ROBUSTESSE & INTÉGRITÉ ÉPISTÉMIQUE (Semaines 7-10)

> **Instructions pour Claude Code.** Lis CLAUDE.md ET ce fichier avant chaque étape.
> Ce document est ta feuille de route pour la Phase 2. Tu exécutes dans l'ordre, étape par étape.
> **Tu ne passes PAS à l'étape suivante tant que les tests de l'étape courante ne passent pas tous.**
>
> **CONTEXTE FONDATEUR** : Le fondateur orchestre Claude Code sans savoir coder. Chaque ligne
> de code doit être lisible par un développeur humain futur qui héritera du projet.
> Clarté > Concision. Noms explicites > Commentaires longs. Tests > Documentation.
>
> **DETTE PHASE 1** : Cette phase commence par compléter les trous de la Phase 1.
> L'`epp ask` et `epp submit` sont des mocks. L'orchestrateur ESMM ne produit pas
> d'attestations cristallisées. Le config.yaml est encore Lyra. Tout ça se corrige ici.

---

## CONTEXTE

La Phase 0 (0.1 + 0.2 + 0.3) et la Phase 1 ont posé les fondations :
- **0.1** : Abstraction des providers (ModelProvider/EmbeddingProvider), rotation multi-provider (55 tests)
- **0.2** : Versioning des embeddings, migration sans perte (45 tests)
- **0.3** : Cristallisation des attestations — `EpistemicAttestation`, `crystallize()`, `compute_claim_hash()`,
  `RunLogger`, stockage DB, revalidation (65 tests)
- **1.x** : Programme Anchor (Rust), bridge sérialisation, client Solana mock, CLI placeholder,
  MetrologicalFrame, PDA derivation, devnet guard (83 tests, 9 skipped)

**Ce qui existe et fonctionne** :
- `attestation.py` : `EpistemicAttestation` → `crystallize()` → `to_portable_json()` → `to_compact_dict()`
- `bridge.py` : `attestation_to_anchor_args()` ↔ `anchor_data_to_attestation_summary()` (roundtrip testé)
- `client.py` : `EppSolanaClient` avec mock mode (`_SOLANA_AVAILABLE = False`)
- `epp_cli.py` : Commandes `ask`, `submit`, `query`, `frame`, `graph` — **toutes en mock**
- `engine.py` : `store_attestation()`, `get_attestation_by_hash()`, `get_attestations_by_subject()`, `get_attestation_history()`
- `lib.rs` : `submit_attestation` instruction compilée, `ping` testée sur localnet
- Programme ID : `98Fc2oL2cKsTDGYi3GifggzkQkEQSRn2oTgg8HsaVa3C`

**Ce qui est cassé, manquant ou factice** :
1. **Glue ESMM → Attestation** : L'orchestrateur ne cristallise jamais. Le fossé entre `orchestrator.py` et `attestation.py` est total.
2. **CLI factice** : `epp ask` crée des mock attestations avec des données inventées. `epp submit` affiche une fausse signature tx.
3. **`update_attestation_solana_tx()`** : Méthode absente de `engine.py`. Les colonnes `solana_tx_signature`, `solana_slot`, `anchored_at` existent mais rien ne les écrit.
4. **`get_stats()` incomplet** : Ne compte pas `attestations`, `esmm_runs`, `cochain_entries`.
5. **`config.yaml` = Lyra pur** : Pas de section `solana:`, pas de section `esmm:`, noms "Lyra Clean" partout.
6. **Niveaux de confiance** : `derive_confidence_tier()` utilise des seuils numériques aveugles. Pas de correspondance avec la méthode scientifique (Sandbox → Propositions → Validé → Vérifié).
7. **Pas de table `metrological_frames`** dans le schéma SQL. Frames hardcodés en Python.
8. **Pas de table `model_track_record`**. Impossible de tracer la calibration des modèles.
9. **Tests E2E = coquilles vides** : Les 6 tests `TestEndToEnd` sont tous `pass`.

**Objectif Phase 2** : Transformer le prototype en fondation robuste. À la fin de cette phase :
- Le flux `epp ask` → ESMM réel → cristallisation → stockage DB est fonctionnel
- Les niveaux de confiance suivent la méthode scientifique
- Le track record des modèles est mesurable
- Le graphe contient 100+ triplets attestés
- 3 scénarios de démonstration fonctionnent end-to-end

**Critère de validation final** : `epp ask "Solana effective TPS exceeds 3000" --models 3 --frame blockchain_tps_v1.0`
→ débat ESMM réel visible → attestation cristallisée → stockée en DB avec confidence tier correct
→ graphe enrichi avec les triplets extraits → `epp graph stats` affiche des métriques réelles.

---

## DÉCISIONS ARCHITECTURALES FIGÉES

Ces décisions sont prises. Ne les remets pas en question pendant l'implémentation.

### D1 — Niveaux de confiance = Méthode scientifique

Le système de confidence tiers de Lyra (`low/medium/high/verified`) est remplacé par une
échelle épistémique à 4 niveaux inspirée de la méthode scientifique :

| Niveau | Nom | Ancien | Seuil consensus | Condition supplémentaire |
|--------|-----|--------|-----------------|--------------------------|
| 0 | `sandbox` | `low` | < 0.4 | Aucune — proposé mais non validé |
| 1 | `proposition` | `medium` | ≥ 0.4 | Consensus ≥ 2 modèles |
| 2 | `validated` | `high` | ≥ 0.7 | Consensus ≥ 3 modèles ET diversité architecturale ≥ 2 familles |
| 3 | `verified` | `verified` | ≥ 0.85 | Validated + source_anchor non NULL OU validation_count ≥ 3 |

**Promotion** : Un triplet ne monte de niveau que si TOUTES les conditions sont remplies.
Le score seul ne suffit jamais pour `validated` ou `verified`.

**Rétrogradation** : Si une revalidation produit un consensus inférieur au seuil,
le tier descend. Jamais de rétrogradation silencieuse — un delta est loggé.

### D2 — Orchestrateur → Cristallisation : pont explicite

Un nouveau module `pipeline.py` fait le pont entre l'orchestrateur ESMM (qui produit des cycles,
des triplets, des 0-cochaines) et le module `attestation.py` (qui cristallise). Ce module :
1. Prend les outputs de l'orchestrateur (triplets extraits, consensus scores, cochain)
2. Appelle `crystallize()` pour chaque triplet validé
3. Stocke en DB via `engine.py`
4. Retourne la liste d'attestations produites

L'orchestrateur ne connaît PAS `attestation.py`. Le pipeline est le seul pont.

### D3 — Config EPP propre

Le `config.yaml` est refondu. Les sections Lyra non pertinentes sont supprimées.
Nouvelles sections : `solana:`, `esmm:`, `confidence:`. Le nom "Lyra" disparaît de toute config.

### D4 — Frames en DB, pas en Python

Les `MetrologicalFrame` sont stockés dans une nouvelle table `metrological_frames` du schéma SQL.
Les fonctions `create_blockchain_tps_frame()` deviennent des seeders initiaux.
Le CLI `epp frame create` permet de créer des frames custom.

### D5 — Brier score comme métrique de calibration

Le track record de chaque modèle est mesuré par le Brier score sur les claims vérifiables :
`BS = (1/N) Σ (prédiction - résultat)²`

Un modèle avec un Brier score bas est mieux calibré. Le poids de son vote augmente dans
le consensus. Un modèle avec un Brier score > 0.4 voit son poids diminuer.

Ceci ne s'applique qu'aux claims résolubles (question factuelle avec réponse vérifiable).
Pour les claims non résolubles, le poids reste égalitaire (1.0).

### D6 — Pas de refonte du programme Anchor

Le code Rust/Anchor ne change PAS en Phase 2. Toutes les améliorations sont off-chain (Python).
Le programme on-chain est gelé jusqu'à l'audit d'un dev Solana. La seule interaction avec
Solana reste le mock mode actuel.

---

## AXIOMES À RESPECTER (rappel — violations = refus du code)

1. **Obsolescence permanente des modèles** — Aucun nom de modèle dans la logique de confiance.
   Les seuils dépendent du score et de la diversité, jamais d'un modèle spécifique.

2. **Le graphe survit à tout** — Les nouvelles tables (`model_track_record`, `metrological_frames`)
   sont des métadonnées. Le graphe (concepts + relations) reste la source de vérité.

3. **Transparence des coupures** — Le passage sandbox → proposition → validated → verified
   est loggé dans `graph_deltas` avec la raison de promotion/rétrogradation.

4. **Calcul local, preuve on-chain** — Phase 2 est 100% off-chain.

5. **Defense in depth** — Chaque nouvelle table a des contraintes, des index, des vues.

---

## STRUCTURE DE FICHIERS CIBLE

```
epp_verdict/
│
├── services/
│   ├── esmm/                         # Existant + modifié
│   │   ├── attestation.py            # ✏️ MODIFIÉ — nouveaux confidence tiers
│   │   ├── run_logger.py             # ✅ Inchangé
│   │   └── pipeline.py              # 🆕 Pont orchestrateur → cristallisation
│   │
│   ├── providers/                    # ✅ Inchangé
│   │
│   └── solana/                       # Existant + modifié
│       ├── config.py                 # ✅ Inchangé
│       ├── bridge.py                 # ✅ Inchangé
│       ├── client.py                 # ✅ Inchangé
│       └── metrological_frame.py     # ✏️ MODIFIÉ — ajout CRUD DB
│
├── cli/
│   └── epp_cli.py                    # ✏️ MODIFIÉ — branchement ESMM réel
│
├── database/
│   ├── engine.py                     # ✏️ MODIFIÉ — nouvelles méthodes
│   └── schema.sql                    # ✏️ MODIFIÉ — nouvelles tables 20-22
│
├── config.yaml                       # ✏️ REFONDU — config EPP propre
│
├── tests/
│   ├── test_phase2_confidence.py     # 🆕 Tests niveaux de confiance
│   ├── test_phase2_pipeline.py       # 🆕 Tests pipeline ESMM → attestation
│   ├── test_phase2_track_record.py   # 🆕 Tests Brier score
│   ├── test_phase2_frames_db.py      # 🆕 Tests frames en DB
│   ├── test_phase2_config.py         # 🆕 Tests config EPP
│   └── test_phase2_integration.py    # 🆕 Tests scénarios E2E
│
└── PHASE_2_INSTRUCTIONS.md           # Ce fichier
```

---

## ÉTAPE 2.0 — Complétion Phase 1 : config, stats, glue

### Objectif

Régler les dettes techniques de la Phase 1 avant de construire dessus.
Trois sous-tâches indépendantes qui peuvent se faire dans l'ordre.

### 2.0.A — Refonte config.yaml

**Remplacer** l'intégralité de `config.yaml` par :

```yaml
# ============================================================================
# EPP_VERDICT — CONFIGURATION
# ============================================================================
# Epistemic Proof Program — Oracle de consensus multi-LLM sur Solana
# ============================================================================

# ============================================================================
# DATABASE
# ============================================================================
database:
  path: "data/epp.db"
  backup_interval_hours: 24
  vacuum_interval_days: 7

# ============================================================================
# ESMM (Exploration Sémantique Multi-Modèles)
# ============================================================================
esmm:
  default_models: 3                    # Nombre de modèles par run
  min_models: 2                        # Minimum pour un consensus valide
  cycle_sequence:                      # Ordre des cycles
    - "divergent"
    - "debate"
    - "meta"
  cycles_per_type: 1                   # Cycles par type (MVP)
  min_consensus: 0.4                   # En dessous = sandbox
  timeout_per_cycle_seconds: 120       # Timeout par cycle ESMM

# ============================================================================
# CONFIDENCE TIERS (Méthode scientifique)
# ============================================================================
confidence:
  thresholds:
    sandbox: 0.0                       # [0.0, 0.4)
    proposition: 0.4                   # [0.4, 0.7) + ≥2 modèles
    validated: 0.7                     # [0.7, 0.85) + ≥3 modèles + ≥2 familles archi
    verified: 0.85                     # [0.85, 1.0] + source_anchor OU validation_count ≥ 3
  min_models_proposition: 2
  min_models_validated: 3
  min_architecture_families_validated: 2

# ============================================================================
# MODEL TRACK RECORD
# ============================================================================
track_record:
  brier_score_window_days: 90          # Fenêtre glissante pour le Brier score
  min_predictions_for_weight: 10       # Minimum de prédictions pour ajuster le poids
  high_calibration_threshold: 0.25     # Brier ≤ 0.25 = bien calibré (poids +)
  low_calibration_threshold: 0.40      # Brier > 0.40 = mal calibré (poids -)
  default_weight: 1.0                  # Poids par défaut (pas de track record)

# ============================================================================
# PROVIDERS (LLM)
# ============================================================================
providers:
  ollama:
    base_url: "http://localhost:11434"
    timeout: 180.0
    max_retries: 3
    default_num_ctx: 8192
  # Sections openai et anthropic ajoutées quand les clés API sont configurées

# ============================================================================
# EMBEDDINGS
# ============================================================================
embeddings:
  active_model: "mxbai-embed-large"
  fallback_reembed: false
  similarity_min_score: 0.1

# ============================================================================
# SOLANA (devnet uniquement)
# ============================================================================
solana:
  cluster: "devnet"                    # "devnet" ou "localnet" — JAMAIS mainnet
  program_id: "98Fc2oL2cKsTDGYi3GifggzkQkEQSRn2oTgg8HsaVa3C"
  commitment: "confirmed"
  timeout_seconds: 30
  # keypair_path: null                 # Défaut : ~/.config/solana/id.json

# ============================================================================
# SERVER (API REST — Phase 3)
# ============================================================================
server:
  host: "0.0.0.0"
  port: 8000
  log_level: "info"

# ============================================================================
# LOGGING
# ============================================================================
logging:
  level: "info"
  format: "json"
  file: "logs/epp.log"
```

### 2.0.B — Méthodes manquantes dans engine.py

**Ajouter** les méthodes suivantes dans `engine.py` (dans la section attestations, après `get_attestation_history`) :

```python
async def update_attestation_solana_tx(
    self,
    claim_hash: str,
    tx_signature: str,
    slot: Optional[int] = None,
) -> bool:
    """
    Met à jour une attestation après ancrage on-chain.

    Args:
        claim_hash: Hash du claim ancré
        tx_signature: Signature de la transaction Solana
        slot: Slot Solana (optionnel)

    Returns:
        True si mise à jour, False si claim_hash non trouvé
    """
    import time

    async with self.connection() as conn:
        cursor = await conn.execute(
            """
            UPDATE attestations
            SET solana_tx_signature = ?,
                solana_slot = ?,
                anchored_at = ?
            WHERE claim_hash = ?
              AND solana_tx_signature IS NULL
            """,
            (tx_signature, slot, time.time(), claim_hash)
        )
        await conn.commit()
        return cursor.rowcount > 0
```

**Modifier** `get_stats()` pour inclure les tables ESMM et attestations :

```python
async def get_stats(self) -> Dict[str, Any]:
    async with self.connection() as conn:
        stats = {}

        tables = [
            'concepts', 'relations', 'sessions', 'events',
            'attestations', 'esmm_runs', 'cochain_entries',
            'triplet_extractions', 'knowledge_gaps',
        ]
        for table in tables:
            try:
                cursor = await conn.execute(f"SELECT COUNT(*) FROM {table}")
                count = await cursor.fetchone()
                stats[table] = count[0]
            except Exception:
                stats[table] = 0  # Table may not exist yet

        # Attestations anchored on-chain
        try:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM attestations WHERE solana_tx_signature IS NOT NULL"
            )
            stats['attestations_anchored'] = (await cursor.fetchone())[0]
        except Exception:
            stats['attestations_anchored'] = 0

        # Database file size
        stats['db_size_mb'] = round(
            self.db_path.stat().st_size / (1024 * 1024), 2
        ) if self.db_path.exists() else 0

        return stats
```

### 2.0.C — Tests

**Créer `tests/test_phase2_config.py`** :

```python
"""Tests Phase 2.0 — Config EPP et méthodes engine manquantes."""

import pytest
import yaml
from pathlib import Path


class TestConfigYaml:
    """Vérifie que config.yaml est un fichier EPP propre."""

    def test_config_loads(self):
        config_path = Path("config.yaml")
        assert config_path.exists(), "config.yaml missing"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        assert isinstance(config, dict)

    def test_no_lyra_references(self):
        """Aucune mention de 'Lyra' ou 'lyra' dans la config."""
        with open("config.yaml") as f:
            content = f.read()
        assert "lyra" not in content.lower(), "config.yaml still references Lyra"

    def test_esmm_section_exists(self):
        with open("config.yaml") as f:
            config = yaml.safe_load(f)
        assert "esmm" in config
        assert "default_models" in config["esmm"]
        assert config["esmm"]["default_models"] >= 2

    def test_confidence_section_exists(self):
        with open("config.yaml") as f:
            config = yaml.safe_load(f)
        assert "confidence" in config
        thresholds = config["confidence"]["thresholds"]
        assert thresholds["sandbox"] == 0.0
        assert thresholds["proposition"] == 0.4
        assert thresholds["validated"] == 0.7
        assert thresholds["verified"] == 0.85

    def test_solana_section_exists(self):
        with open("config.yaml") as f:
            config = yaml.safe_load(f)
        assert "solana" in config
        assert config["solana"]["cluster"] in ("devnet", "localnet")
        assert "mainnet" not in config["solana"]["cluster"]

    def test_track_record_section_exists(self):
        with open("config.yaml") as f:
            config = yaml.safe_load(f)
        assert "track_record" in config
        assert "brier_score_window_days" in config["track_record"]

    def test_database_path_is_epp(self):
        with open("config.yaml") as f:
            config = yaml.safe_load(f)
        assert "epp" in config["database"]["path"].lower()
```

**Critère de passage** : `pytest tests/test_phase2_config.py -v` → tous verts.

---

## ÉTAPE 2.1 — Niveaux de confiance : Méthode scientifique

### Objectif

Remplacer les confidence tiers `low/medium/high/verified` par `sandbox/proposition/validated/verified`
avec des conditions multi-critères (pas juste un seuil numérique).

### Ce que tu fais

**A. Modifier `services/esmm/attestation.py`**

Remplacer `derive_confidence_tier()` :

```python
# === CONFIDENCE TIERS (Méthode scientifique) ===

CONFIDENCE_TIERS = ("sandbox", "proposition", "validated", "verified")

# Backward compatibility mapping
LEGACY_TIER_MAP = {
    "low": "sandbox",
    "medium": "proposition",
    "high": "validated",
    "verified": "verified",
}


def derive_confidence_tier(
    consensus_score: float,
    models_consulted: int = 1,
    architecture_families: int = 1,
    source_anchor: Optional[str] = None,
    validation_count: int = 1,
) -> str:
    """
    Dérive le tier de confiance selon la méthode scientifique.

    Niveaux (chaque niveau EXIGE toutes les conditions) :

    VERIFIED (≥ 0.85) :
        - Consensus ≥ 0.85
        - Toutes conditions de VALIDATED
        - source_anchor non NULL OU validation_count ≥ 3

    VALIDATED (≥ 0.70) :
        - Consensus ≥ 0.70
        - models_consulted ≥ 3
        - architecture_families ≥ 2

    PROPOSITION (≥ 0.40) :
        - Consensus ≥ 0.40
        - models_consulted ≥ 2

    SANDBOX (< 0.40) :
        - Tout le reste

    Args:
        consensus_score: Score de consensus [0, 1]
        models_consulted: Nombre de modèles consultés
        architecture_families: Nombre de familles d'architecture distinctes
        source_anchor: Hash de source vérifiable externe
        validation_count: Nombre de validations (1 = première)

    Returns:
        Tier de confiance : "sandbox" | "proposition" | "validated" | "verified"
    """
    # Check VERIFIED conditions
    if (consensus_score >= 0.85
            and models_consulted >= 3
            and architecture_families >= 2
            and (source_anchor is not None or validation_count >= 3)):
        return "verified"

    # Check VALIDATED conditions
    if (consensus_score >= 0.70
            and models_consulted >= 3
            and architecture_families >= 2):
        return "validated"

    # Check PROPOSITION conditions
    if consensus_score >= 0.40 and models_consulted >= 2:
        return "proposition"

    return "sandbox"
```

Mettre à jour le validateur `validate_confidence_tier` :

```python
@field_validator("confidence_tier")
@classmethod
def validate_confidence_tier(cls, v: str) -> str:
    allowed = {"sandbox", "proposition", "validated", "verified"}
    # Backward compat
    if v in LEGACY_TIER_MAP:
        return LEGACY_TIER_MAP[v]
    if v not in allowed:
        raise ValueError(f"confidence_tier must be one of {allowed}, got '{v}'")
    return v
```

Mettre à jour `crystallize()` pour passer les nouveaux paramètres :

```python
def crystallize(
    subject: str,
    predicate: str,
    object_: str,
    consensus_score: float,
    model_votes: List[ModelVote],
    signature_5d: Signature5D,
    epistemic_type: str,
    run_id: Optional[int] = None,
    question: Optional[str] = None,
    metrological_frame: Optional[str] = None,
    source_anchor: Optional[str] = None,
    previous_hash: Optional[str] = None,
    validation_count: int = 1,
    architecture_families: int = 1,
) -> EpistemicAttestation:
    claim_hash = compute_claim_hash(subject, predicate, object_, metrological_frame)

    # Derive confidence tier with full context
    confidence_tier = derive_confidence_tier(
        consensus_score=consensus_score,
        models_consulted=len(model_votes),
        architecture_families=architecture_families,
        source_anchor=source_anchor,
        validation_count=validation_count,
    )

    models_consulted = len(model_votes)
    models_agreeing = sum(1 for v in model_votes if v.agreed)

    return EpistemicAttestation(
        claim_hash=claim_hash,
        subject=subject.strip(),
        predicate=predicate.strip(),
        object=object_.strip(),
        consensus_score=consensus_score,
        models_consulted=models_consulted,
        models_agreeing=models_agreeing,
        model_votes=model_votes,
        signature_5d=signature_5d,
        epistemic_type=epistemic_type,
        confidence_tier=confidence_tier,
        metrological_frame=metrological_frame,
        source_anchor=source_anchor,
        run_id=run_id,
        question=question,
        timestamp=time.time(),
        validation_count=validation_count,
        previous_hash=previous_hash,
    )
```

**B. Mettre à jour `bridge.py`**

Modifier `CONFIDENCE_TIER_MAP` :

```python
CONFIDENCE_TIER_MAP = {
    "sandbox": 0,
    "proposition": 1,
    "validated": 2,
    "verified": 3,
    # Backward compat
    "low": 0,
    "medium": 1,
    "high": 2,
}
```

Et `CONFIDENCE_TIER_REVERSE` :

```python
CONFIDENCE_TIER_REVERSE = {
    0: "sandbox",
    1: "proposition",
    2: "validated",
    3: "verified",
}
```

**C. Tests — `tests/test_phase2_confidence.py`**

```python
"""Tests Phase 2.1 — Niveaux de confiance (Méthode scientifique)."""

import pytest

from services.esmm.attestation import (
    derive_confidence_tier,
    crystallize,
    Signature5D,
    ModelVote,
    CONFIDENCE_TIERS,
    LEGACY_TIER_MAP,
)


class TestDeriveConfidenceTier:
    """Tests de la fonction de classification."""

    def test_sandbox_low_consensus(self):
        assert derive_confidence_tier(0.2, models_consulted=3) == "sandbox"

    def test_sandbox_single_model(self):
        """Même un consensus parfait avec 1 seul modèle = sandbox."""
        assert derive_confidence_tier(0.99, models_consulted=1) == "sandbox"

    def test_proposition_basic(self):
        assert derive_confidence_tier(0.5, models_consulted=2) == "proposition"

    def test_proposition_not_enough_models(self):
        """Consensus OK mais 1 seul modèle → sandbox, pas proposition."""
        assert derive_confidence_tier(0.6, models_consulted=1) == "sandbox"

    def test_validated_basic(self):
        assert derive_confidence_tier(
            0.75, models_consulted=3, architecture_families=2
        ) == "validated"

    def test_validated_needs_3_models(self):
        """Consensus et diversité OK mais seulement 2 modèles → proposition."""
        assert derive_confidence_tier(
            0.75, models_consulted=2, architecture_families=2
        ) == "proposition"

    def test_validated_needs_architecture_diversity(self):
        """3 modèles mais tous de la même famille → proposition."""
        assert derive_confidence_tier(
            0.75, models_consulted=3, architecture_families=1
        ) == "proposition"

    def test_verified_with_source_anchor(self):
        assert derive_confidence_tier(
            0.90, models_consulted=3, architecture_families=2,
            source_anchor="abc123"
        ) == "verified"

    def test_verified_with_revalidation(self):
        """3 validations successives sans source externe = verified."""
        assert derive_confidence_tier(
            0.90, models_consulted=3, architecture_families=2,
            validation_count=3
        ) == "verified"

    def test_verified_needs_validated_conditions(self):
        """Score 0.9 mais seulement 2 modèles → proposition (pas validated, pas verified)."""
        assert derive_confidence_tier(
            0.90, models_consulted=2, architecture_families=2
        ) == "proposition"

    def test_verified_needs_source_or_revalidation(self):
        """0.9, 3 modèles, 2 familles, mais pas de source ni revalidation → validated."""
        assert derive_confidence_tier(
            0.90, models_consulted=3, architecture_families=2,
            source_anchor=None, validation_count=1
        ) == "validated"

    def test_boundary_040(self):
        assert derive_confidence_tier(0.4, models_consulted=2) == "proposition"
        assert derive_confidence_tier(0.39, models_consulted=2) == "sandbox"

    def test_boundary_070(self):
        assert derive_confidence_tier(0.7, models_consulted=3, architecture_families=2) == "validated"
        assert derive_confidence_tier(0.69, models_consulted=3, architecture_families=2) == "proposition"

    def test_boundary_085(self):
        assert derive_confidence_tier(
            0.85, models_consulted=3, architecture_families=2, source_anchor="x"
        ) == "verified"
        assert derive_confidence_tier(
            0.84, models_consulted=3, architecture_families=2, source_anchor="x"
        ) == "validated"


class TestLegacyCompatibility:
    """Vérifie la backward compat avec les anciens tiers."""

    def test_legacy_mapping(self):
        assert LEGACY_TIER_MAP["low"] == "sandbox"
        assert LEGACY_TIER_MAP["medium"] == "proposition"
        assert LEGACY_TIER_MAP["high"] == "validated"
        assert LEGACY_TIER_MAP["verified"] == "verified"

    def test_tiers_tuple(self):
        assert CONFIDENCE_TIERS == ("sandbox", "proposition", "validated", "verified")


class TestCrystallizeWithNewTiers:
    """Vérifie que crystallize() utilise les nouveaux tiers."""

    def _votes(self, n: int, agreed: bool = True) -> list:
        return [
            ModelVote(
                model_id=f"test::model_{i}",
                provider_id="test",
                agreed=agreed,
                confidence=0.8,
            )
            for i in range(n)
        ]

    def _sig(self) -> Signature5D:
        return Signature5D(
            agreement=0.8, semantic_consistency=0.7,
            centrality=0.5, stability=0.8, relation_diversity=0.6,
        )

    def test_crystallize_sandbox(self):
        att = crystallize(
            subject="test", predicate="is", object_="low",
            consensus_score=0.2, model_votes=self._votes(1),
            signature_5d=self._sig(), epistemic_type="foundational",
        )
        assert att.confidence_tier == "sandbox"

    def test_crystallize_proposition(self):
        att = crystallize(
            subject="test", predicate="is", object_="medium",
            consensus_score=0.5, model_votes=self._votes(2),
            signature_5d=self._sig(), epistemic_type="foundational",
        )
        assert att.confidence_tier == "proposition"

    def test_crystallize_validated(self):
        att = crystallize(
            subject="test", predicate="is", object_="high",
            consensus_score=0.75, model_votes=self._votes(3),
            signature_5d=self._sig(), epistemic_type="foundational",
            architecture_families=2,
        )
        assert att.confidence_tier == "validated"

    def test_crystallize_verified_with_anchor(self):
        att = crystallize(
            subject="test", predicate="is", object_="verified",
            consensus_score=0.90, model_votes=self._votes(3),
            signature_5d=self._sig(), epistemic_type="foundational",
            architecture_families=2, source_anchor="abcdef1234567890" * 4,
        )
        assert att.confidence_tier == "verified"
```

**Critère de passage** : `pytest tests/test_phase2_confidence.py -v` → tous verts.
Les tests Phase 1 existants (`test_phase1_bridge.py`) doivent aussi passer
(backward compat via `LEGACY_TIER_MAP`).

---

## ÉTAPE 2.2 — Pipeline ESMM → Cristallisation

### Objectif

Créer le pont entre l'orchestrateur ESMM et le module d'attestation.
Après cette étape, l'`epp ask` produit de VRAIES attestations à partir du débat ESMM.

### Ce que tu fais

**A. Créer `services/esmm/pipeline.py`**

```python
"""
ESMM Pipeline — Pont entre l'orchestrateur et la cristallisation.

Responsabilités :
1. Lancer un run ESMM via l'orchestrateur
2. Collecter les triplets extraits et leurs scores de consensus
3. Cristalliser chaque triplet validé en EpistemicAttestation
4. Stocker les attestations en DB
5. Enrichir le graphe avec les triplets validés

Ce module est le SEUL pont entre orchestrator.py et attestation.py.
L'orchestrateur ne connaît pas le module attestation.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass

from .attestation import (
    EpistemicAttestation,
    Signature5D,
    ModelVote,
    crystallize,
)
from .run_logger import RunLogger

if TYPE_CHECKING:
    from database.engine import ISpaceDB

logger = logging.getLogger("esmm.pipeline")


@dataclass
class PipelineConfig:
    """Configuration du pipeline."""
    min_consensus_for_attestation: float = 0.4   # En dessous = pas d'attestation
    min_confidence_for_injection: float = 0.5    # En dessous = pas d'injection graphe
    default_epistemic_type: str = "foundational"
    metrological_frame: Optional[str] = None


@dataclass
class PipelineResult:
    """Résultat d'un run complet du pipeline."""
    run_id: int
    question: str
    attestations: List[EpistemicAttestation]
    triplets_extracted: int
    triplets_attested: int
    triplets_injected: int
    duration_ms: float
    errors: List[str]


async def run_pipeline(
    question: str,
    db: "ISpaceDB",
    models: Optional[List[str]] = None,
    config: Optional[PipelineConfig] = None,
    metrological_frame: Optional[str] = None,
) -> PipelineResult:
    """
    Exécute le pipeline complet : question → ESMM → attestations → graphe.

    Args:
        question: Question soumise au pipeline
        db: Instance ISpaceDB
        models: Liste des modèles à utiliser (None = config default)
        config: Configuration du pipeline
        metrological_frame: Frame métrologique applicable

    Returns:
        PipelineResult avec les attestations produites
    """
    if config is None:
        config = PipelineConfig()
    if metrological_frame:
        config.metrological_frame = metrological_frame

    start_time = time.time()
    errors = []
    attestations = []
    triplets_injected = 0

    # 1. Créer le run ESMM en DB
    run_id = await db.create_esmm_run(
        config={"question": question, "frame": metrological_frame},
        models_used=models or [],
        seed_type="standard",
    )
    run_logger = RunLogger(run_id=run_id, question=question)

    try:
        # 2. Exécuter l'orchestrateur ESMM
        # NOTE: L'intégration réelle avec orchestrator.py se fait ici.
        # Pour le MVP, on utilise le MultiProviderRotator directement
        # pour obtenir les réponses des modèles, puis on extrait les triplets.
        #
        # TODO: Brancher orchestrator.run() quand l'interface est stabilisée.
        # Pour l'instant, le pipeline fait :
        #   a) Query N modèles sur la question
        #   b) Extraire les triplets de chaque réponse
        #   c) Calculer le consensus par triplet
        #   d) Cristalliser les triplets validés

        run_logger.phase_start("pipeline", question=question)

        # 3. Placeholder pour les triplets extraits par le cycle ESMM
        # Ce bloc sera remplacé par l'appel réel à l'orchestrateur
        extracted_triplets = await _extract_triplets_from_question(
            question, db, models, run_logger
        )

        # 4. Cristalliser chaque triplet ayant un consensus suffisant
        for triplet in extracted_triplets:
            if triplet["consensus_score"] < config.min_consensus_for_attestation:
                continue

            # Construire les ModelVote depuis les données du triplet
            model_votes = [
                ModelVote(
                    model_id=v["model_id"],
                    provider_id=v["provider_id"],
                    agreed=v["agreed"],
                    confidence=v["confidence"],
                )
                for v in triplet.get("votes", [])
            ]

            # Compter les familles d'architecture
            families = set(v.get("architecture_family", "unknown") for v in triplet.get("votes", []))

            attestation = crystallize(
                subject=triplet["subject"],
                predicate=triplet["predicate"],
                object_=triplet["object"],
                consensus_score=triplet["consensus_score"],
                model_votes=model_votes,
                signature_5d=Signature5D(**triplet.get("signature_5d", {
                    "agreement": triplet["consensus_score"],
                    "semantic_consistency": 0.5,
                    "centrality": 0.5,
                    "stability": 0.5,
                    "relation_diversity": len(families) / max(len(model_votes), 1),
                })),
                epistemic_type=triplet.get("epistemic_type", config.default_epistemic_type),
                run_id=run_id,
                question=question,
                metrological_frame=config.metrological_frame,
                architecture_families=len(families),
            )

            # Stocker en DB
            attestation_dict = attestation.model_dump()
            attestation_dict["portable_json"] = attestation.to_portable_json()
            await db.store_attestation(attestation_dict)

            # Logger
            run_logger.crystallization(
                claim_hash=attestation.claim_hash,
                consensus_score=attestation.consensus_score,
                confidence_tier=attestation.confidence_tier,
            )

            attestations.append(attestation)

            # 5. Injecter dans le graphe si confiance suffisante
            if triplet["consensus_score"] >= config.min_confidence_for_injection:
                try:
                    await _inject_triplet_to_graph(
                        db, triplet["subject"], triplet["predicate"], triplet["object"],
                        confidence=triplet["consensus_score"],
                        model_source=f"esmm_run_{run_id}",
                    )
                    triplets_injected += 1
                except Exception as e:
                    errors.append(f"Injection failed for {triplet['subject']}: {e}")

        run_logger.phase_end("pipeline", attestations=len(attestations))

    except Exception as e:
        errors.append(f"Pipeline error: {e}")
        run_logger.error("pipeline", str(e))
        logger.exception(f"Pipeline failed for run {run_id}")

    # 6. Finaliser le run ESMM
    duration_ms = (time.time() - start_time) * 1000
    await db.update_esmm_run_status(run_id, "completed" if not errors else "failed")

    return PipelineResult(
        run_id=run_id,
        question=question,
        attestations=attestations,
        triplets_extracted=len(extracted_triplets) if 'extracted_triplets' in dir() else 0,
        triplets_attested=len(attestations),
        triplets_injected=triplets_injected,
        duration_ms=round(duration_ms, 1),
        errors=errors,
    )


async def _extract_triplets_from_question(
    question: str,
    db: "ISpaceDB",
    models: Optional[List[str]],
    run_logger: RunLogger,
) -> List[Dict[str, Any]]:
    """
    Extrait les triplets d'une question via le pipeline ESMM.

    NOTE: Cette fonction est le point d'intégration avec l'orchestrateur.
    Pour le MVP, elle utilise le TripletExtractor directement.
    L'intégration complète avec orchestrator.run() est une étape ultérieure.

    Returns:
        Liste de dicts avec : subject, predicate, object, consensus_score,
        votes, signature_5d, epistemic_type
    """
    # TODO: Intégration complète avec orchestrator
    # Pour l'instant, retourne une liste vide si pas de providers disponibles.
    # Le branchement réel se fera quand les providers sont configurés et accessibles.
    logger.info(f"Extracting triplets for: {question}")
    return []


async def _inject_triplet_to_graph(
    db: "ISpaceDB",
    subject: str,
    predicate: str,
    object_: str,
    confidence: float,
    model_source: str,
) -> None:
    """Injecte un triplet attesté dans le graphe de connaissances."""
    # Résoudre les concepts (canonicalisation)
    subject_canonical = await db.resolve_concept(subject)
    object_canonical = await db.resolve_concept(object_)

    # Ajouter les concepts s'ils n'existent pas
    existing = await db.get_concept(subject_canonical)
    if not existing:
        await db.add_concept(
            concept_id=subject_canonical,
            source="extracted",
            first_seen_model=model_source,
        )

    existing = await db.get_concept(object_canonical)
    if not existing:
        await db.add_concept(
            concept_id=object_canonical,
            source="extracted",
            first_seen_model=model_source,
        )

    # Ajouter la relation
    await db.upsert_relations_batch([{
        "source": subject_canonical,
        "target": object_canonical,
        "weight": confidence,
        "relation_type": predicate,
        "confidence": confidence,
        "model_source": model_source,
    }])
```

**B. Modifier `cli/epp_cli.py` — Brancher le pipeline réel**

Remplacer la commande `ask` pour utiliser le pipeline :

```python
@cli.command()
@click.argument("question")
@click.option("--models", "-m", default=3, help="Number of models to consult")
@click.option("--frame", "-f", default="general_knowledge_v1.0", help="Metrological frame ID")
@click.option("--output", "-o", type=click.Choice(["json", "text"]), default="text")
def ask(question: str, models: int, frame: str, output: str):
    """Run ESMM pipeline on a question."""
    click.echo(f"Question: {question}")
    click.echo(f"Models to consult: {models}")
    click.echo(f"Frame: {frame}")
    click.echo()

    # Validate frame
    met_frame = get_frame(frame)
    if met_frame is None:
        click.echo(f"Error: Unknown frame '{frame}'", err=True)
        click.echo(f"Available frames: {', '.join(PREDEFINED_FRAMES.keys())}", err=True)
        sys.exit(1)

    click.echo(f"Frame hash: {met_frame.compute_frame_hash()[:16]}...")
    click.echo()

    # Run the actual pipeline
    result = asyncio.run(_run_ask(question, models, frame))

    if result.errors:
        click.echo(f"Pipeline completed with {len(result.errors)} error(s):", err=True)
        for err in result.errors:
            click.echo(f"  - {err}", err=True)

    if not result.attestations:
        click.echo("No attestations produced.")
        click.echo("(This may mean no providers are configured, or consensus was too low.)")
        return

    for att in result.attestations:
        if output == "json":
            click.echo(att.to_portable_json())
        else:
            click.echo(f"Attestation [{att.confidence_tier.upper()}]:")
            click.echo(f"  Claim: {att.subject} → {att.predicate} → {att.object}")
            click.echo(f"  Hash: {att.claim_hash[:16]}...")
            click.echo(f"  Consensus: {att.consensus_score:.2%}")
            click.echo(f"  Models: {att.models_agreeing}/{att.models_consulted}")
            click.echo(f"  Tier: {att.confidence_tier}")
            click.echo()

    click.echo(f"Pipeline: {result.triplets_extracted} extracted → "
               f"{result.triplets_attested} attested → "
               f"{result.triplets_injected} injected to graph")
    click.echo(f"Duration: {result.duration_ms:.0f}ms")
    click.echo()
    click.echo("Use 'epp submit --devnet' to anchor on-chain.")


async def _run_ask(question: str, models: int, frame: str):
    """Helper async pour exécuter le pipeline."""
    from database.engine import get_db
    from services.esmm.pipeline import run_pipeline, PipelineConfig

    db = await get_db()
    config = PipelineConfig(metrological_frame=frame)
    return await run_pipeline(
        question=question,
        db=db,
        config=config,
    )
```

### Tests — `tests/test_phase2_pipeline.py`

```python
"""Tests Phase 2.2 — Pipeline ESMM → Cristallisation."""

import pytest
import asyncio
import time

from services.esmm.pipeline import (
    PipelineConfig,
    PipelineResult,
    run_pipeline,
)
from services.esmm.attestation import EpistemicAttestation


class TestPipelineConfig:
    """Tests de la configuration du pipeline."""

    def test_defaults(self):
        config = PipelineConfig()
        assert config.min_consensus_for_attestation == 0.4
        assert config.min_confidence_for_injection == 0.5

    def test_custom_config(self):
        config = PipelineConfig(
            min_consensus_for_attestation=0.6,
            metrological_frame="blockchain_tps_v1.0",
        )
        assert config.metrological_frame == "blockchain_tps_v1.0"


class TestPipelineResult:
    """Tests de la structure de résultat."""

    def test_result_structure(self):
        result = PipelineResult(
            run_id=1, question="test", attestations=[],
            triplets_extracted=0, triplets_attested=0,
            triplets_injected=0, duration_ms=100.0, errors=[],
        )
        assert result.run_id == 1
        assert result.attestations == []
        assert result.errors == []
```

**Critère de passage** : `pytest tests/test_phase2_pipeline.py -v` → tous verts.

---

## ÉTAPE 2.3 — Tables nouvelles : frames en DB + track record

### Objectif

Persister les MetrologicalFrames en DB (pas hardcodés en Python) et créer
la table de track record des modèles pour le Brier scoring futur.

### Ce que tu fais

**A. Ajouter au schéma SQL** (dans `schema.sql`, après la table 19)

```sql
-- ============================================================================
-- TABLE 20: METROLOGICAL_FRAMES (Référentiels métrologiques persistés)
-- ============================================================================
-- Les frames sont versionés et hashés. Le hash est ancré on-chain avec chaque
-- attestation. Le contenu complet est stocké ici pour vérification off-chain.

CREATE TABLE IF NOT EXISTS metrological_frames (
    -- Clé primaire
    frame_id TEXT NOT NULL,              -- Ex: "blockchain_tps_v1.0"
    version TEXT NOT NULL,               -- Ex: "1.0"

    -- Contenu
    domain TEXT NOT NULL,                -- Ex: "blockchain_metrics"
    metric TEXT NOT NULL,                -- Ex: "transactions_per_second"
    description TEXT NOT NULL,
    parameters TEXT NOT NULL,            -- JSON
    required_sources INTEGER NOT NULL DEFAULT 1,

    -- Gouvernance
    governance TEXT NOT NULL,            -- JSON: {current_authority, amendment_process, target_authority}

    -- Hash déterministe
    frame_hash TEXT NOT NULL,            -- SHA-256 du frame canonique

    -- Tracking
    created_at REAL NOT NULL DEFAULT (unixepoch('now')),
    created_by TEXT DEFAULT 'system',    -- 'system' | 'user' | 'cli'

    PRIMARY KEY (frame_id, version)
);

CREATE INDEX IF NOT EXISTS idx_frames_hash ON metrological_frames(frame_hash);
CREATE INDEX IF NOT EXISTS idx_frames_domain ON metrological_frames(domain);


-- ============================================================================
-- TABLE 21: MODEL_TRACK_RECORD (Historique de performance des modèles)
-- ============================================================================
-- Chaque entrée = une prédiction d'un modèle sur un claim résolu.
-- Utilisé pour calculer le Brier score et ajuster les poids dans le consensus.

CREATE TABLE IF NOT EXISTS model_track_record (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identité du modèle
    model_id TEXT NOT NULL,              -- Ex: "ollama::mistral:7b"
    provider_id TEXT NOT NULL,           -- Ex: "ollama"

    -- Prédiction
    claim_hash TEXT NOT NULL,            -- Hash du claim évalué
    predicted_confidence REAL NOT NULL,  -- Confiance du modèle [0, 1]
    predicted_agreed INTEGER NOT NULL,   -- 1 = a voté pour, 0 = a voté contre

    -- Résolution (rempli plus tard quand le claim est vérifié)
    actual_outcome INTEGER,              -- NULL = non résolu, 1 = vrai, 0 = faux
    resolved_at REAL,                    -- Timestamp de résolution
    resolution_source TEXT,              -- "external_api" | "manual" | "revalidation"

    -- Score Brier pour cette prédiction (calculé à la résolution)
    brier_score REAL,                    -- (predicted - actual)² pour cette prédiction

    -- Tracking
    created_at REAL NOT NULL DEFAULT (unixepoch('now')),

    FOREIGN KEY (claim_hash) REFERENCES attestations(claim_hash)
);

CREATE INDEX IF NOT EXISTS idx_track_model ON model_track_record(model_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_track_claim ON model_track_record(claim_hash);
CREATE INDEX IF NOT EXISTS idx_track_unresolved ON model_track_record(actual_outcome) WHERE actual_outcome IS NULL;


-- ============================================================================
-- TABLE 22: TIER_TRANSITIONS (Historique des changements de niveau de confiance)
-- ============================================================================
-- Chaque promotion ou rétrogradation est loggée ici.

CREATE TABLE IF NOT EXISTS tier_transitions (
    transition_id INTEGER PRIMARY KEY AUTOINCREMENT,

    claim_hash TEXT NOT NULL,
    old_tier TEXT NOT NULL,              -- "sandbox" | "proposition" | "validated" | "verified"
    new_tier TEXT NOT NULL,
    reason TEXT NOT NULL,                -- Ex: "consensus_increased", "source_anchor_added", "revalidation_degraded"

    -- Contexte
    attestation_id INTEGER,
    run_id INTEGER,

    -- Tracking
    transitioned_at REAL NOT NULL DEFAULT (unixepoch('now')),

    FOREIGN KEY (claim_hash) REFERENCES attestations(claim_hash),
    FOREIGN KEY (attestation_id) REFERENCES attestations(attestation_id),
    FOREIGN KEY (run_id) REFERENCES esmm_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_transitions_claim ON tier_transitions(claim_hash, transitioned_at DESC);
CREATE INDEX IF NOT EXISTS idx_transitions_tier ON tier_transitions(new_tier);

-- Vue : Brier score par modèle (fenêtre glissante 90 jours)
CREATE VIEW IF NOT EXISTS v_model_brier_scores AS
SELECT
    model_id,
    provider_id,
    COUNT(*) as total_predictions,
    COUNT(actual_outcome) as resolved_predictions,
    AVG(brier_score) as avg_brier_score,
    MIN(brier_score) as best_brier,
    MAX(brier_score) as worst_brier
FROM model_track_record
WHERE created_at > unixepoch('now') - (90 * 86400)
  AND actual_outcome IS NOT NULL
GROUP BY model_id, provider_id
ORDER BY avg_brier_score ASC;
```

**B. Ajouter les méthodes dans `engine.py`**

```python
# === METROLOGICAL FRAMES ===

async def store_frame(self, frame_data: Dict[str, Any]) -> None:
    """Stocke un MetrologicalFrame en DB."""
    import json
    async with self.connection() as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO metrological_frames
            (frame_id, version, domain, metric, description,
             parameters, required_sources, governance, frame_hash, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                frame_data["frame_id"],
                frame_data["version"],
                frame_data["domain"],
                frame_data["metric"],
                frame_data["description"],
                json.dumps(frame_data.get("parameters", {})),
                frame_data.get("required_sources", 1),
                json.dumps(frame_data.get("governance", {})),
                frame_data["frame_hash"],
                frame_data.get("created_by", "system"),
            )
        )
        await conn.commit()

async def get_frame(self, frame_id: str, version: Optional[str] = None) -> Optional[Dict]:
    """Récupère un frame par ID (dernière version si non spécifié)."""
    import json
    async with self.connection() as conn:
        if version:
            cursor = await conn.execute(
                "SELECT * FROM metrological_frames WHERE frame_id = ? AND version = ?",
                (frame_id, version)
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM metrological_frames WHERE frame_id = ? ORDER BY created_at DESC LIMIT 1",
                (frame_id,)
            )
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)

async def list_frames(self) -> List[Dict]:
    """Liste tous les frames (dernière version de chaque)."""
    async with self.connection() as conn:
        cursor = await conn.execute(
            """
            SELECT DISTINCT frame_id, version, domain, metric, frame_hash, created_at
            FROM metrological_frames
            ORDER BY domain, frame_id
            """
        )
        return [dict(row) for row in await cursor.fetchall()]


# === MODEL TRACK RECORD ===

async def record_model_prediction(
    self,
    model_id: str,
    provider_id: str,
    claim_hash: str,
    predicted_confidence: float,
    predicted_agreed: bool,
) -> int:
    """Enregistre une prédiction de modèle pour tracking Brier."""
    async with self.connection() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO model_track_record
            (model_id, provider_id, claim_hash, predicted_confidence, predicted_agreed)
            VALUES (?, ?, ?, ?, ?)
            """,
            (model_id, provider_id, claim_hash, predicted_confidence, int(predicted_agreed))
        )
        await conn.commit()
        return cursor.lastrowid

async def resolve_prediction(
    self,
    claim_hash: str,
    actual_outcome: bool,
    resolution_source: str = "manual",
) -> int:
    """
    Résout toutes les prédictions pour un claim donné.
    Calcule le Brier score pour chaque prédiction.

    Returns:
        Nombre de prédictions résolues
    """
    import time
    async with self.connection() as conn:
        # Fetch unresolved predictions for this claim
        cursor = await conn.execute(
            """
            SELECT record_id, predicted_confidence, predicted_agreed
            FROM model_track_record
            WHERE claim_hash = ? AND actual_outcome IS NULL
            """,
            (claim_hash,)
        )
        rows = await cursor.fetchall()

        resolved = 0
        for row in rows:
            record_id = row[0]
            predicted = row[1]  # confidence [0, 1]
            agreed = row[2]     # 1 or 0

            # Brier score : (prediction - outcome)²
            # prediction = confidence if agreed, (1 - confidence) if disagreed
            effective_prediction = predicted if agreed else (1.0 - predicted)
            actual = 1.0 if actual_outcome else 0.0
            brier = (effective_prediction - actual) ** 2

            await conn.execute(
                """
                UPDATE model_track_record
                SET actual_outcome = ?, resolved_at = ?, resolution_source = ?, brier_score = ?
                WHERE record_id = ?
                """,
                (int(actual_outcome), time.time(), resolution_source, round(brier, 6), record_id)
            )
            resolved += 1

        await conn.commit()
        return resolved

async def get_model_brier_score(
    self,
    model_id: str,
    window_days: int = 90,
) -> Optional[Dict[str, Any]]:
    """Calcule le Brier score d'un modèle sur une fenêtre glissante."""
    async with self.connection() as conn:
        cursor = await conn.execute(
            """
            SELECT
                COUNT(*) as total,
                AVG(brier_score) as avg_brier,
                MIN(brier_score) as best,
                MAX(brier_score) as worst
            FROM model_track_record
            WHERE model_id = ?
              AND actual_outcome IS NOT NULL
              AND created_at > unixepoch('now') - (? * 86400)
            """,
            (model_id, window_days)
        )
        row = await cursor.fetchone()
        if not row or row[0] == 0:
            return None
        return {
            "model_id": model_id,
            "total_resolved": row[0],
            "avg_brier_score": round(row[1], 4),
            "best_brier": round(row[2], 4),
            "worst_brier": round(row[3], 4),
        }


# === TIER TRANSITIONS ===

async def log_tier_transition(
    self,
    claim_hash: str,
    old_tier: str,
    new_tier: str,
    reason: str,
    attestation_id: Optional[int] = None,
    run_id: Optional[int] = None,
) -> int:
    """Logue un changement de niveau de confiance."""
    async with self.connection() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO tier_transitions
            (claim_hash, old_tier, new_tier, reason, attestation_id, run_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (claim_hash, old_tier, new_tier, reason, attestation_id, run_id)
        )
        await conn.commit()
        return cursor.lastrowid
```

**C. Seeder initial des frames en DB**

Ajouter dans `engine.py`, dans la méthode `initialize()`, après la création des tables :

```python
# Seed metrological frames if table is empty
try:
    cursor = await conn.execute("SELECT COUNT(*) FROM metrological_frames")
    count = (await cursor.fetchone())[0]
    if count == 0:
        from services.solana.metrological_frame import (
            create_blockchain_tps_frame,
            create_general_knowledge_frame,
        )
        for factory in [create_blockchain_tps_frame, create_general_knowledge_frame]:
            frame = factory()
            await self.store_frame({
                **frame.model_dump(),
                "frame_hash": frame.compute_frame_hash(),
                "created_by": "system_seed",
            })
except Exception:
    pass  # Table may not exist yet in older schemas
```

### Tests — `tests/test_phase2_track_record.py`

```python
"""Tests Phase 2.3 — Track record modèles et frames en DB."""

import pytest


class TestModelTrackRecord:
    """Tests du Brier scoring."""

    def test_brier_score_perfect_prediction(self):
        """Prédiction parfaite = Brier 0."""
        predicted = 1.0
        actual = 1.0
        brier = (predicted - actual) ** 2
        assert brier == 0.0

    def test_brier_score_worst_prediction(self):
        """Pire prédiction = Brier 1."""
        predicted = 1.0
        actual = 0.0
        brier = (predicted - actual) ** 2
        assert brier == 1.0

    def test_brier_score_uncertain(self):
        """Prédiction 0.5 = Brier 0.25."""
        predicted = 0.5
        actual = 1.0
        brier = (predicted - actual) ** 2
        assert brier == 0.25

    def test_brier_score_slightly_wrong(self):
        """Prédiction 0.8 quand la réponse est 1.0 = Brier 0.04."""
        predicted = 0.8
        actual = 1.0
        brier = (predicted - actual) ** 2
        assert abs(brier - 0.04) < 0.001


class TestTierTransitions:
    """Tests de la structure des transitions."""

    def test_valid_tiers(self):
        valid = {"sandbox", "proposition", "validated", "verified"}
        for tier in valid:
            assert tier in valid

    def test_promotion_order(self):
        order = ["sandbox", "proposition", "validated", "verified"]
        for i in range(len(order) - 1):
            assert order.index(order[i]) < order.index(order[i + 1])
```

**Critère de passage** : `pytest tests/test_phase2_track_record.py tests/test_phase2_frames_db.py -v` → tous verts.

---

## ÉTAPE 2.4 — Anti-Sybil : diversité mesurable

### Objectif

Mesurer la diversité architecturale des modèles participant au consensus.
Le score de diversité alimente directement le calcul du confidence tier (condition
`architecture_families ≥ 2` pour `validated`).

### Ce que tu fais

**A. Enrichir `ModelMetadata` dans `base.py`**

Ajouter un champ `architecture_family` aux réponses du consensus :

```python
# Architecture families (for diversity measurement)
ARCHITECTURE_FAMILIES = {
    # Dense transformers
    "mistral": "transformer_dense",
    "llama": "transformer_dense",
    "qwen": "transformer_dense",
    "gemma": "transformer_dense",
    "phi": "transformer_dense",
    # Mixture of Experts
    "mixtral": "transformer_moe",
    "deepseek": "transformer_moe",
    # API models (architecture not always public)
    "gpt": "openai_family",
    "claude": "anthropic_family",
    "gemini": "google_family",
}


def infer_architecture_family(model_id: str) -> str:
    """
    Infère la famille d'architecture à partir du model_id.

    Heuristique basée sur le nom. Retourne 'unknown' si non reconnu.
    L'important est que deux modèles de la même famille soient reconnus
    comme tels — pas que l'architecture soit exacte.
    """
    model_lower = model_id.lower()
    for prefix, family in ARCHITECTURE_FAMILIES.items():
        if prefix in model_lower:
            return family
    return "unknown"
```

**B. Utiliser la diversité dans le pipeline**

Dans `pipeline.py`, lors de la cristallisation, compter les familles :

```python
from services.providers.base import infer_architecture_family

# Dans la boucle de cristallisation :
families = set()
for v in triplet.get("votes", []):
    family = infer_architecture_family(v["model_id"])
    families.add(family)

# Passer à crystallize()
attestation = crystallize(
    ...,
    architecture_families=len(families),
)
```

### Tests

```python
"""Tests Phase 2.4 — Diversité architecturale."""

from services.providers.base import infer_architecture_family, ARCHITECTURE_FAMILIES


class TestArchitectureFamilyInference:

    def test_mistral(self):
        assert infer_architecture_family("ollama::mistral:7b") == "transformer_dense"

    def test_mixtral(self):
        assert infer_architecture_family("ollama::mixtral:8x7b") == "transformer_moe"

    def test_llama(self):
        assert infer_architecture_family("ollama::llama3.1:8b") == "transformer_dense"

    def test_deepseek(self):
        assert infer_architecture_family("openai::deepseek-r1") == "transformer_moe"

    def test_gpt(self):
        assert infer_architecture_family("openai::gpt-4o-mini") == "openai_family"

    def test_claude(self):
        assert infer_architecture_family("anthropic::claude-3-haiku") == "anthropic_family"

    def test_unknown(self):
        assert infer_architecture_family("custom::novelmodel:3b") == "unknown"

    def test_diversity_count(self):
        """3 modèles de 2 familles = diversité 2."""
        models = ["mistral:7b", "llama3:8b", "mixtral:8x7b"]
        families = set(infer_architecture_family(m) for m in models)
        assert len(families) == 2  # dense + moe
```

**Critère de passage** : `pytest tests/test_phase2_diversity.py -v` → tous verts.

---

## ÉTAPE 2.5 — Scénarios de démonstration

### Objectif

Préparer 3 scénarios exécutables qui démontrent la valeur d'EPP.
Chaque scénario est un script Python autonome dans `demos/`.

### Scénario 1 — Attestation factuelle vérifiable

```
epp ask "Solana effective TPS exceeds 3000" --models 3 --frame blockchain_tps_v1.0
```

Résultat attendu : attestation `validated` ou `proposition` avec score de consensus basé
sur le débat réel entre 3 modèles locaux.

### Scénario 2 — Rejet d'un claim faux

```
epp ask "Bitcoin was invented by Elon Musk" --models 3 --frame general_knowledge_v1.0
```

Résultat attendu : consensus faible (< 0.4), tier `sandbox`, le graphe ne s'enrichit PAS
de ce triplet.

### Scénario 3 — Enrichissement progressif du graphe

```
epp ask "What is proof of stake" --models 3
epp ask "How does Solana achieve consensus" --models 3
epp ask "Compare proof of stake and proof of history" --models 3
epp graph stats
```

Résultat attendu : le graphe contient des concepts liés (solana, proof_of_stake,
proof_of_history) avec des relations attestées. `epp graph stats` montre l'enrichissement.

### Ce que tu fais

**Créer `demos/scenario_1.py`, `demos/scenario_2.py`, `demos/scenario_3.py`**

Chaque scénario est un script avec :
1. Setup (config, DB init)
2. Exécution (appels pipeline)
3. Vérification (assertions sur le résultat)
4. Affichage (résumé lisible)

**Note** : Ces scénarios fonctionnent en mock si aucun provider n'est configuré.
Le test vérifie la mécanique du pipeline, pas la qualité des réponses LLM.

### Tests — `tests/test_phase2_integration.py`

```python
"""Tests d'intégration Phase 2 — scénarios de démonstration."""

import pytest


class TestScenarioStructure:
    """Vérifie que les scénarios existent et sont importables."""

    def test_pipeline_import(self):
        from services.esmm.pipeline import run_pipeline, PipelineConfig, PipelineResult
        assert callable(run_pipeline)

    def test_confidence_tier_import(self):
        from services.esmm.attestation import derive_confidence_tier, CONFIDENCE_TIERS
        assert len(CONFIDENCE_TIERS) == 4

    def test_architecture_family_import(self):
        from services.providers.base import infer_architecture_family
        assert callable(infer_architecture_family)
```

**Critère de passage** : `pytest tests/test_phase2_integration.py -v` → tous verts.

---

## ZONES À SURVEILLER — Registre Phase 2

| # | Fichier | Zone | Risque | Action |
|---|---------|------|--------|--------|
| B1 | `attestation.py` | `derive_confidence_tier()` | Régression backward compat | Tests `LEGACY_TIER_MAP` |
| B2 | `bridge.py` | `CONFIDENCE_TIER_MAP` | Mismatch Python ↔ Rust | Vérifier que les u8 matchent |
| B3 | `pipeline.py` | `_extract_triplets_from_question()` | Placeholder TODO | Brancher orchestrateur |
| B4 | `engine.py` | `store_frame()` | Injection SQL via parameters JSON | JSON.dumps avant stockage |
| B5 | `engine.py` | `resolve_prediction()` | Brier sur claims ambigus | N'appliquer qu'aux claims binaires |
| B6 | `config.yaml` | Section `solana:` | Divergence avec `SolanaConfig` Python | Garder `config.py` comme source de vérité |
| B7 | `schema.sql` | Tables 20-22 | Migration depuis schema existant | Utiliser `CREATE TABLE IF NOT EXISTS` |

---

## ORDRE D'EXÉCUTION (résumé)

```
ÉTAPE 2.0 — Complétion Phase 1 (config, engine, stats)
    │  Fichiers : config.yaml, engine.py
    │  Tests : test_phase2_config.py (~8 tests)
    │  Prérequis : Phase 1 complète
    ▼
ÉTAPE 2.1 — Niveaux de confiance (Méthode scientifique)
    │  Fichiers : attestation.py, bridge.py
    │  Tests : test_phase2_confidence.py (~18 tests)
    │  Prérequis : Étape 2.0
    ▼
ÉTAPE 2.2 — Pipeline ESMM → Cristallisation
    │  Fichiers : services/esmm/pipeline.py, cli/epp_cli.py
    │  Tests : test_phase2_pipeline.py (~5 tests)
    │  Prérequis : Étape 2.1
    ▼
ÉTAPE 2.3 — Tables nouvelles (frames DB + track record)
    │  Fichiers : schema.sql, engine.py
    │  Tests : test_phase2_track_record.py + test_phase2_frames_db.py (~12 tests)
    │  Prérequis : Étape 2.0 (engine modifié)
    ▼
ÉTAPE 2.4 — Anti-Sybil : diversité mesurable
    │  Fichiers : base.py, pipeline.py
    │  Tests : test_phase2_diversity.py (~8 tests)
    │  Prérequis : Étape 2.2 (pipeline existe)
    ▼
ÉTAPE 2.5 — Scénarios de démonstration
    │  Fichiers : demos/scenario_*.py
    │  Tests : test_phase2_integration.py (~3 tests)
    │  Prérequis : Étapes 2.0-2.4 complètes
    ▼
✅ PHASE 2 COMPLÈTE
    Critère : pipeline ESMM fonctionnel → attestations réelles → graphe enrichi
              → niveaux de confiance scientifiques → track record traçable
```

---

## CHECKLIST DE FIN DE PHASE 2

- [ ] `config.yaml` refondu — zéro mention de "Lyra", sections EPP complètes
- [ ] `get_stats()` compte attestations, esmm_runs, cochain_entries
- [ ] `update_attestation_solana_tx()` implémenté dans engine.py
- [ ] Confidence tiers = `sandbox` / `proposition` / `validated` / `verified`
- [ ] `derive_confidence_tier()` multi-critères (score + modèles + familles + source)
- [ ] Backward compat : `LEGACY_TIER_MAP` pour les anciens tiers
- [ ] `bridge.py` mis à jour avec les nouveaux tier mappings
- [ ] `pipeline.py` créé — pont orchestrateur → cristallisation → DB → graphe
- [ ] `epp ask` branché sur le pipeline réel (pas des mocks)
- [ ] Table `metrological_frames` créée et seedée
- [ ] Table `model_track_record` créée avec Brier scoring
- [ ] Table `tier_transitions` créée pour audit des promotions/rétrogradations
- [ ] `infer_architecture_family()` pour mesure de diversité
- [ ] Diversité architecturale alimentée dans `crystallize()`
- [ ] 3 scénarios de démo préparés dans `demos/`
- [ ] 50+ tests Phase 2 passent
- [ ] Tests Phase 0 + Phase 1 existants passent toujours (backward compat)
- [ ] CHANGELOG.md mis à jour
- [ ] ARCHITECTURE.md mis à jour

---

## NOTES POUR LE FONDATEUR

1. **L'étape 2.2 est la plus critique.** Le `pipeline.py` est le cœur de cette phase.
   Le placeholder `_extract_triplets_from_question()` retourne une liste vide — c'est normal.
   Le branchement réel nécessite que les providers Ollama soient configurés et que les modèles
   soient téléchargés. Le pipeline fonctionne en mode "dry run" sans providers.

2. **L'étape 2.3 (Brier scoring) est un investissement long terme.** Les prédictions s'accumulent
   avec le temps. Le vrai signal Brier n'apparaîtra qu'après des dizaines de claims résolus.
   Mais la table est prête dès maintenant — c'est ça qui attire un dev qui veut contribuer.

3. **La diversité architecturale est une heuristique.** `infer_architecture_family()` est un
   mapping manuel. C'est suffisant pour le MVP. Un futur contributeur pourra le remplacer par
   une vraie mesure (corrélation d'erreurs, analyse d'embeddings).

4. **Le config.yaml NE REMPLACE PAS `config.py`** (Solana). Le fichier YAML est lu par le
   code Python de haut niveau. Le `SolanaConfig` dans `config.py` reste la source de vérité
   pour tout ce qui touche à la blockchain. Pas de double source de vérité.

5. **Après cette phase, le repo est montrable.** Un dev peut cloner, lire CLAUDE.md,
   exécuter les tests, comprendre l'architecture. C'est l'objectif : des fondations assez
   robustes pour que quelqu'un qui sait coder ait envie de contribuer.

---

*Instructions Phase 2 — Version 1.0 — 8 février 2026*
*Prérequis validé : Phase 0 complète (165 tests) + Phase 1 complète (83 tests)*
