# PHASE 3 — FLUX END-TO-END : QUESTION → ATTESTATION RÉELLE

> **Instructions pour Claude Code.** Lis CLAUDE.md ET ce fichier avant chaque étape.
> Ce document est ta feuille de route pour la Phase 3. Tu exécutes dans l'ordre, étape par étape.
> **Tu ne passes PAS à l'étape suivante tant que les tests de l'étape courante ne passent pas tous.**
>
> **CONTEXTE FONDATEUR** : Le fondateur orchestre Claude Code sans savoir coder. Chaque ligne
> de code doit être lisible par un développeur humain futur qui héritera du projet.
> Clarté > Concision. Noms explicites > Commentaires longs. Tests > Documentation.
>
> **DETTE CUMULÉE** : Les Phases 0-2 ont posé l'architecture, les providers, la cristallisation,
> le pipeline. Mais `_extract_triplets_from_question()` retourne `[]`, des tables et méthodes
> documentées n'existent pas, et les confidence tiers sont incohérents entre modules.
> C'est le fossé que cette phase comble.

---

## PRINCIPE CARDINAL — VÉRIFIE AVANT D'AGIR

**Le code réel peut différer de ce que ce document décrit.** Des corrections ont pu être
appliquées entre la rédaction de ces instructions et leur exécution. Avant chaque étape :

1. **Vérifie l'état réel** du fichier ciblé (grep, lecture, tests existants)
2. **Si le problème décrit est déjà corrigé** → passe au point suivant, ne touche à rien
3. **Si le problème existe mais diffère** → adapte ta correction à l'état réel
4. **Ne crée jamais de code mort** — si une fonction existe déjà et fonctionne, ne la duplique pas
5. **Ne casse jamais ce qui fonctionne** — exécute `pytest tests/ -v --tb=short` après chaque modification

Ce pattern s'applique à CHAQUE sous-étape. Il est noté `⚡ VÉRIFIE D'ABORD` dans le document.

---

## CONTEXTE

La Phase 2 a livré :
- **config.yaml** refondu (zéro Lyra, 8 sections EPP)
- **Confidence tiers** définis dans config.yaml : sandbox/proposition/validated/verified
- **pipeline.py** : pont orchestrateur → cristallisation (structure complète, extraction = placeholder)
- **Tables ESMM** : esmm_runs, exploration_cycles, triplet_extractions, cochain_entries, knowledge_gaps
- **Architecture diversity** : `infer_architecture_family()` documentée dans ARCHITECTURE.md
- **3 scénarios** de démonstration (scenario_1/2/3.py)
- **138 tests** passent (3 skipped, 0 failed)

**Ce qui est probablement cassé, manquant ou factice** (à vérifier) :

1. **`_extract_triplets_from_question()` retourne `[]`** — Le pipeline ne produit aucune attestation réelle.
2. **Double création de run** — pipeline.py ET orchestrator.py créent chacun un run ESMM en DB.
3. **`ESMMRunResult` ne contient pas les triplets** — Pas de champ `consensus_triplets`.
4. **`create_cycle_manager()` hardcode OllamaProvider** — cycle_manager.py L845-865.
5. **Pas de chargement centralisé de config.yaml** — Chaque module a ses propres defaults.
6. **`epp query` = TODO** — N'interroge pas la DB.
7. **`epp graph stats` = TODO** — Affiche des `--` au lieu de métriques réelles.
8. **`epp submit` = mock complet** — Même la partie locale (lecture d'attestation en DB) est factice.
9. **Track record non alimenté** — La table `model_track_record` existe peut-être mais rien n'y écrit.
10. **Graphe vide au premier lancement** — Pas de mécanisme de seed.
11. **Tables SQL manquantes** — `attestations`, `metrological_frames`, `model_track_record`, `tier_transitions` sont possiblement absentes de `schema.sql`.
12. **Méthodes ISpaceDB manquantes** — `store_attestation()`, `get_attestation_by_hash()`, `record_model_prediction()`, etc. sont possiblement absentes d'`engine.py`.
13. **Confidence tiers incohérents** — `attestation.py` utilise possiblement `low/medium/high/verified` au lieu de `sandbox/proposition/validated/verified`.
14. **`infer_architecture_family()`** — Documentée dans ARCHITECTURE.md, testée dans test_phase2_diversity.py, mais possiblement absente de `base.py`.
15. **`crystallize()` n'accepte peut-être pas `architecture_families`** — Mais `pipeline.py` le passe (L149).
16. **`get_db()` utilise `"data/ispace.db"`** — Hérité de Lyra, devrait être `"data/epp.db"`.

> **Chaque point ci-dessus doit être vérifié par Claude Code avant correction.**
> Si un point est déjà résolu, ne fais rien. Documente simplement « déjà corrigé ».

**Objectif Phase 3** : Le flux end-to-end fonctionne. À la fin de cette phase :
- `epp ask "..."` consulte des modèles réels, produit un consensus, cristallise des attestations
- Les attestations sont stockées en DB avec confidence tier correct
- Le graphe est enrichi avec les triplets validés
- Le track record de chaque modèle est alimenté
- `epp query` et `epp graph stats` lisent la DB
- 170+ tests passent (138 existants + 30+ nouveaux)

**Critère de validation final** : `epp ask "Solana effective TPS exceeds 3000" --models 3 --frame blockchain_tps_v1.0`
→ modèles Ollama consultés → cycles ESMM exécutés → triplets extraits → consensus calculé
→ attestations cristallisées et stockées en DB → graphe enrichi → track record alimenté
→ `epp query "solana"` retourne les attestations → `epp graph stats` affiche des métriques non-nulles.

---

## DÉCISIONS ARCHITECTURALES FIGÉES

Ces décisions sont prises. Ne les remets pas en question pendant l'implémentation.

### D1 — L'orchestrateur possède le run

Le pipeline NE crée PAS de run ESMM. C'est l'orchestrateur qui crée et possède le run via
`initialize_run()`. Le pipeline récupère le `run_id` après exécution de l'orchestrateur.
Ceci élimine la double création de run.

### D2 — L'orchestrateur collecte et retourne les ConsensusTriplet

`ESMMRunResult` est enrichi avec un champ `consensus_triplets: List[ConsensusTriplet]`.
L'orchestrateur accumule tous les `ConsensusTriplet` produits par chaque cycle et les
retourne dans le résultat final. Le pipeline les consomme pour la cristallisation.

### D3 — Intégration complète de l'orchestrateur

On branche l'orchestrateur complet : adaptation dynamique, gap detection, 0-cochaine.
Pas de version simplifiée. L'orchestrateur a été testé et fonctionne — on l'utilise tel quel,
avec les modifications minimales nécessaires (collecte des triplets, suppression du couplage
hardcodé aux providers).

### D4 — Adaptateur explicite ConsensusTriplet → dict pipeline

La conversion `ConsensusTriplet` → dict exploitable par le pipeline est isolée dans un module
dédié (`triplet_adapter.py`), testé unitairement. Pas de conversion inline.
Conversions : `relation` → `predicate`, `contributing_models` → `votes` enrichis,
`signature_5d` calculée ou approximée, `epistemic_type` dérivé.

### D5 — config_loader.py singleton

Un module `config_loader.py` charge `config.yaml` et expose les sections via un singleton.
Les modules existants gardent leurs defaults mais peuvent être overridés par la config.
Pas de refonte des modules existants — juste un point d'accès centralisé.

Emplacement : `services/config_loader.py` (au niveau services, transversal).

### D6 — create_cycle_manager() utilise le ProviderRegistry

La factory ne hardcode plus `OllamaProvider`. Elle lit les providers depuis le
`ProviderRegistry` ou depuis la config. Les providers doivent être enregistrés avant
l'appel au pipeline (responsabilité du CLI ou du caller).
Fallback Ollama conservé si rien dans le registry.

### D7 — Seed par la question de l'utilisateur

Quand le graphe est vide, la question soumise par l'utilisateur sert de seed initial.
Le pipeline décompose la question en concepts et les injecte dans le graphe avant de
lancer l'orchestrateur. Module dédié : `question_seeder.py`.

### D8 — Hook unique post-cristallisation

Après chaque appel à `crystallize()`, un hook unique (`post_crystallization.py`) :
1. Enregistre les votes de chaque modèle dans `model_track_record`
2. Logue la transition de tier dans `tier_transitions` si applicable

Ceci maintient la compartimentation : le pipeline gère le track record, pas l'orchestrateur.

### D9 — Transactions Solana = mock, attestation locale = réelle

`epp submit` charge l'attestation depuis la DB (réel) mais la transaction Solana reste
en mock. Sans `--claim-hash`, prend la dernière attestation.
`epp query` lit réellement la DB. `epp graph stats` appelle `get_stats()` réel.
Tout ce qui est local fonctionne, tout ce qui coûte des SOL est simulé.

### D10 — Deux modes de test : mock synthétique + mock réaliste

1. **Mock synthétique** : Retourne des `ConsensusTriplet` pré-fabriqués directement.
   Teste la cristallisation, le stockage, le track record. Rapide, déterministe.
2. **MockProvider réaliste** : Implémente `ModelProvider`, retourne du texte contenant
   des triplets extractibles par le `TripletExtractor` existant. Teste le flux complet
   extraction → consensus → cristallisation. Plus lent, plus réaliste.

### D11 — Confidence tiers = sandbox / proposition / validated / verified

C'est le vocabulaire officiel (aligné sur `config.yaml`). `attestation.py` doit utiliser
ces tiers, pas `low/medium/high/verified`. La fonction `derive_confidence_tier()` devient
`compute_confidence_tier()` avec la logique multi-critères de `config.yaml`.

### D12 — Pas de refonte du programme Anchor

Le code Rust/Anchor ne change PAS. Toutes les améliorations sont off-chain (Python).

---

## AXIOMES À RESPECTER (rappel — violations = refus du code)

1. **Obsolescence permanente des modèles** — Aucun nom de modèle dans la logique métier.
   Les providers sont des consommables, identifiés par ID dans le registre.

2. **Le graphe survit à tout** — Les triplets injectés via le pipeline sont la valeur durable.
   Le track record, les transitions de tier, les métriques sont des métadonnées.

3. **Transparence des coupures** — Chaque transition de tier est loggée. Chaque vote de
   modèle est tracé. Rien n'est silencieux.

4. **Calcul local, preuve on-chain** — Phase 3 est 100% off-chain côté transaction.

5. **Le pipeline est le seul pont** — L'orchestrateur ne connaît PAS attestation.py.
   Le pipeline est l'unique chemin orchestrateur → cristallisation.

---

## ZONES DE RÉGRESSION À MONITORER

À chaque étape, avant de passer à la suivante, exécuter :

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```

| Zone | Fichiers critiques | Ce qui peut casser |
|------|-------------------|-------------------|
| **Z1** | attestation.py, bridge.py | crystallize() — adapter la signature, pas la casser |
| **Z2** | consensus_engine.py | ConsensusTriplet dataclass — on ajoute un champ, pas de suppression |
| **Z3** | engine.py | create_esmm_run(), store_attestation() — signatures stables |
| **Z4** | base.py, registry.py | ModelProvider ABC, ProviderRegistry singleton — ne pas casser le contrat |
| **Z5** | schema.sql | Tables existantes — on AJOUTE des tables, on ne modifie PAS les existantes |
| **Z6** | test_phase1_*.py, test_phase2_*.py | Tests existants — zéro régression tolérée |
| **Z7** | orchestrator.py, cycle_manager.py | Logique ESMM interne — modifications minimales et ciblées |

---

## STRUCTURE DE FICHIERS CIBLE

```
epp_verdict/
│
├── services/
│   ├── config_loader.py                 # 🆕 Chargement centralisé config.yaml
│   │
│   ├── esmm/                            # Existant + modifié
│   │   ├── attestation.py               # ✏️ MODIFIÉ — aligner tiers, compute_confidence_tier
│   │   ├── run_logger.py                # ✅ Inchangé
│   │   ├── pipeline.py                  # ✏️ MODIFIÉ — branchement orchestrateur réel
│   │   ├── orchestrator.py              # ✏️ MODIFIÉ — collecte ConsensusTriplet
│   │   ├── cycle_manager.py             # ✏️ MODIFIÉ — factory via ProviderRegistry
│   │   ├── triplet_adapter.py           # 🆕 Conversion ConsensusTriplet → dict pipeline
│   │   ├── question_seeder.py           # 🆕 Seed graphe depuis question
│   │   ├── post_crystallization.py      # 🆕 Hook post-cristallisation
│   │   ├── consensus_engine.py          # ✅ Inchangé
│   │   ├── cochain_builder.py           # ✅ Inchangé
│   │   ├── gap_detector.py              # ✅ Inchangé
│   │   ├── coverage_analyzer.py         # ✅ Inchangé
│   │   ├── triplet_extractor.py         # ✅ Inchangé
│   │   ├── triplet_validator.py         # ✅ Inchangé
│   │   └── cycle_prompts.py             # ✅ Inchangé
│   │
│   ├── providers/                       # Existant + ajout
│   │   ├── base.py                      # ✏️ POSSIBLEMENT MODIFIÉ — infer_architecture_family si absent
│   │   ├── ollama.py                    # ✅ Inchangé
│   │   ├── openai_compat.py             # ✅ Inchangé
│   │   ├── anthropic.py                 # ✅ Inchangé
│   │   ├── registry.py                  # ✅ Inchangé
│   │   └── mock_provider.py             # 🆕 MockProvider pour tests
│   │
│   └── solana/                          # ✅ Inchangé (gelé D12)
│
├── cli/
│   └── epp_cli.py                       # ✏️ MODIFIÉ — query, graph stats, submit locaux
│
├── database/
│   ├── engine.py                        # ✏️ MODIFIÉ — méthodes manquantes + fix get_db()
│   └── schema.sql                       # ✏️ MODIFIÉ — +tables manquantes (ajout seulement)
│
├── config.yaml                          # ✅ Inchangé (refondu Phase 2)
│
├── tests/
│   ├── test_phase3_config_loader.py     # 🆕
│   ├── test_phase3_mock_provider.py     # 🆕
│   ├── test_phase3_orchestrator.py      # 🆕
│   ├── test_phase3_pipeline.py          # 🆕
│   ├── test_phase3_cli.py              # 🆕
│   ├── test_phase3_track_record.py      # 🆕
│   └── test_phase3_integration.py       # 🆕
│
├── scenario_1.py                        # ✏️ MODIFIÉ — utilise le vrai pipeline
├── scenario_2.py                        # ✏️ MODIFIÉ — utilise le vrai pipeline
└── scenario_3.py                        # ✏️ MODIFIÉ — utilise le vrai pipeline
```

---

## ÉTAPES — ORDRE D'EXÉCUTION STRICT

---

### ÉTAPE 0 — AUDIT ET INFRASTRUCTURE MANQUANTE

**Objectif** : Vérifier l'état réel du code et construire ce qui manque.
Cette étape ne change aucun comportement existant — elle ajoute uniquement ce qui est absent.

---

#### 0.1 — Audit automatisé de l'état réel

**Ce que tu fais AVANT TOUT** :

```bash
# 1. Combien de tables dans schema.sql ?
grep -c "CREATE TABLE" schema.sql

# 2. Les 4 tables critiques existent-elles ?
grep -l "attestations\|metrological_frames\|model_track_record\|tier_transitions" schema.sql

# 3. Les méthodes ISpaceDB critiques existent-elles ?
grep -n "def store_attestation\|def get_attestation_by_hash\|def record_model_prediction\|def log_tier_transition\|def get_attestation_count\|def get_latest_attestation" engine.py

# 4. Quels tiers utilise attestation.py ?
grep -n "low.*medium.*high\|sandbox.*proposition.*validated\|allowed.*=.*{" attestation.py

# 5. infer_architecture_family existe-t-elle ?
grep -rn "def infer_architecture_family" services/providers/base.py

# 6. crystallize() accepte-t-elle architecture_families ?
grep -n "architecture_families" attestation.py

# 7. get_db() path par défaut ?
grep -n "def get_db\|data/ispace\|data/epp" engine.py

# 8. Tests existants passent-ils tous ?
pytest tests/ -v --tb=short 2>&1 | tail -20
```

**Documente les résultats.** Pour chaque point : « existe » ou « manque ».
C'est ton état de référence pour le reste de la Phase 3. Si quelque chose est déjà
implémenté et fonctionne, tu ne le touches pas.

---

#### 0.2 — Tables SQL manquantes

⚡ **VÉRIFIE D'ABORD** : `grep "CREATE TABLE" schema.sql | sort`

Pour chaque table ci-dessous, vérifie si elle existe. **Si elle existe déjà, passe.**
Sinon, ajoute-la **à la fin** de schema.sql (avant les vues et triggers).
**Ne modifie aucune table existante.**

**Table `attestations`** (si absente) :
```sql
CREATE TABLE IF NOT EXISTS attestations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_hash TEXT UNIQUE NOT NULL,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    consensus_score REAL NOT NULL,
    models_consulted INTEGER NOT NULL,
    models_agreeing INTEGER NOT NULL,
    model_votes TEXT NOT NULL,          -- JSON sérialisé
    signature_5d TEXT NOT NULL,         -- JSON sérialisé
    epistemic_type TEXT NOT NULL,
    confidence_tier TEXT NOT NULL,
    metrological_frame TEXT,
    source_anchor TEXT,
    run_id INTEGER,
    question TEXT,
    timestamp REAL NOT NULL,
    protocol_version TEXT DEFAULT '0.3',
    validation_count INTEGER DEFAULT 1,
    previous_hash TEXT,
    portable_json TEXT,
    submission_status TEXT DEFAULT 'local',  -- local | queued | submitted
    solana_tx_signature TEXT,
    created_at REAL DEFAULT (unixepoch()),
    FOREIGN KEY (run_id) REFERENCES esmm_runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_attestations_subject ON attestations(subject);
CREATE INDEX IF NOT EXISTS idx_attestations_run ON attestations(run_id);
CREATE INDEX IF NOT EXISTS idx_attestations_tier ON attestations(confidence_tier);
CREATE INDEX IF NOT EXISTS idx_attestations_status ON attestations(submission_status);
```

**Table `metrological_frames`** (si absente) :
```sql
CREATE TABLE IF NOT EXISTS metrological_frames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    frame_id TEXT UNIQUE NOT NULL,
    version TEXT NOT NULL,
    domain TEXT NOT NULL,
    metric TEXT NOT NULL,
    description TEXT,
    parameters TEXT NOT NULL,           -- JSON
    required_sources TEXT,              -- JSON
    governance TEXT,                    -- JSON
    frame_hash TEXT NOT NULL,
    created_at REAL DEFAULT (unixepoch())
);
```

**Table `model_track_record`** (si absente) :
```sql
CREATE TABLE IF NOT EXISTS model_track_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    claim_hash TEXT NOT NULL,
    predicted_confidence REAL NOT NULL,
    agreed INTEGER NOT NULL,            -- 0 ou 1
    resolved INTEGER DEFAULT 0,         -- 0 = en attente, 1 = résolu
    resolution_value REAL,              -- Valeur réelle (pour Brier)
    resolved_at REAL,
    run_id INTEGER,
    created_at REAL DEFAULT (unixepoch()),
    FOREIGN KEY (claim_hash) REFERENCES attestations(claim_hash),
    FOREIGN KEY (run_id) REFERENCES esmm_runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_track_model ON model_track_record(model_id);
CREATE INDEX IF NOT EXISTS idx_track_claim ON model_track_record(claim_hash);
```

**Table `tier_transitions`** (si absente) :
```sql
CREATE TABLE IF NOT EXISTS tier_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_hash TEXT NOT NULL,
    from_tier TEXT NOT NULL,
    to_tier TEXT NOT NULL,
    reason TEXT,
    run_id INTEGER,
    created_at REAL DEFAULT (unixepoch()),
    FOREIGN KEY (claim_hash) REFERENCES attestations(claim_hash)
);
```

**Vue `v_model_brier_scores`** (si absente) :
```sql
CREATE VIEW IF NOT EXISTS v_model_brier_scores AS
SELECT
    model_id,
    provider_id,
    COUNT(*) as total_predictions,
    SUM(CASE WHEN resolved = 1 THEN 1 ELSE 0 END) as resolved_predictions,
    AVG(CASE
        WHEN resolved = 1
        THEN (predicted_confidence - resolution_value) * (predicted_confidence - resolution_value)
        ELSE NULL
    END) as brier_score
FROM model_track_record
WHERE created_at > unixepoch() - (90 * 86400)
GROUP BY model_id, provider_id;
```

---

#### 0.3 — Méthodes ISpaceDB manquantes

⚡ **VÉRIFIE D'ABORD** pour chaque méthode : `grep -n "def <method_name>" engine.py`

**Si la méthode existe déjà et a la bonne signature, passe.**
Sinon, ajoute-la dans `engine.py` dans la classe `ISpaceDB`.

Méthodes à vérifier/ajouter :

- `store_attestation(attestation_dict: dict) -> int`
- `get_attestation_by_hash(claim_hash: str) -> Optional[dict]`
- `get_attestations_by_subject(subject: str, min_consensus: float = 0.0) -> List[dict]`
- `get_latest_attestation() -> Optional[dict]`
- `get_attestation_count() -> int`
- `update_attestation_submission_status(claim_hash: str, status: str) -> None`
- `update_attestation_solana_tx(claim_hash: str, tx_signature: str) -> None`
- `store_frame(frame_dict: dict) -> None`
- `get_frame(frame_id: str) -> Optional[dict]`
- `list_frames() -> List[dict]`
- `record_model_prediction(model_id, provider_id, claim_hash, predicted_confidence, agreed, run_id=None) -> None`
- `get_model_brier_score(model_id: str) -> Optional[float]`
- `log_tier_transition(claim_hash, from_tier, to_tier, reason=None, run_id=None) -> None`

Pour `store_attestation`, les champs JSON (`model_votes`, `signature_5d`) doivent être
sérialisés en JSON string avant l'INSERT. Les méthodes `get_*` doivent désérialiser.

---

#### 0.4 — Aligner les confidence tiers (D11)

⚡ **VÉRIFIE D'ABORD** : `grep -n "allowed\|low.*medium.*high\|sandbox.*proposition" attestation.py`

**Si `attestation.py` utilise déjà sandbox/proposition/validated/verified, passe.**

Sinon, modifier :

1. **`validate_confidence_tier()`** :
   `allowed = {"sandbox", "proposition", "validated", "verified"}`

2. **`derive_confidence_tier()`** → renommer en `compute_confidence_tier()` avec logique multi-critères :

```python
def compute_confidence_tier(
    consensus_score: float,
    models_consulted: int = 1,
    architecture_families: int = 1,
    source_anchor: Optional[str] = None,
    validation_count: int = 1,
) -> str:
    """
    Calcule le tier de confiance selon les critères de config.yaml.

    Seuils :
      verified   : score ≥ 0.85 + ≥3 modèles + ≥2 familles + (source_anchor OU validation ≥ 3)
      validated  : score ≥ 0.70 + ≥3 modèles + ≥2 familles
      proposition: score ≥ 0.40 + ≥2 modèles
      sandbox    : tout le reste
    """
    if (consensus_score >= 0.85
        and models_consulted >= 3
        and architecture_families >= 2
        and (source_anchor is not None or validation_count >= 3)):
        return "verified"
    if (consensus_score >= 0.70
        and models_consulted >= 3
        and architecture_families >= 2):
        return "validated"
    if consensus_score >= 0.40 and models_consulted >= 2:
        return "proposition"
    return "sandbox"
```

3. **`crystallize()`** — vérifier qu'elle accepte `architecture_families: int = 1` comme paramètre
   et l'utilise dans l'appel à `compute_confidence_tier()`. Si le paramètre existe déjà,
   vérifier qu'il est propagé. Si non, l'ajouter.

4. **Conserver `derive_confidence_tier`** comme alias déprécié si des tests Phase 2 l'utilisent :
```python
# Backward compatibility — tests Phase 2
derive_confidence_tier = lambda score: compute_confidence_tier(score)
```

---

#### 0.5 — `infer_architecture_family()` dans base.py

⚡ **VÉRIFIE D'ABORD** : `grep -n "def infer_architecture_family" services/providers/base.py`

**Si la fonction existe déjà, passe.** Les tests Phase 2 (`test_phase2_diversity.py`) l'importent
depuis `services.providers.base` — elle doit être là pour que ces tests passent.

Si absente, ajouter dans `base.py` :

```python
ARCHITECTURE_FAMILIES = {
    "mistral": "transformer_dense",
    "llama": "transformer_dense",
    "gemma": "transformer_dense",
    "qwen": "transformer_dense",
    "phi": "transformer_dense",
    "mixtral": "transformer_moe",
    "deepseek": "transformer_moe",
    "gpt": "openai_family",
    "claude": "anthropic_family",
}

def infer_architecture_family(model_id: str) -> str:
    """
    Infère la famille d'architecture depuis l'identifiant du modèle.
    Utilisé pour mesurer la diversité architecturale (anti-Sybil).
    """
    model_lower = model_id.lower()
    for pattern, family in ARCHITECTURE_FAMILIES.items():
        if pattern in model_lower:
            return family
    return "unknown"
```

---

#### 0.6 — config_loader.py

⚡ **VÉRIFIE D'ABORD** : `ls services/config_loader.py services/esmm/config_loader.py 2>/dev/null`

**Si un config_loader existe déjà et fonctionne, passe.**

Sinon, créer `services/config_loader.py` :

```python
"""
Centralized configuration loader for EPP_Verdict.

Loads config.yaml once and exposes sections via a singleton.
Modules keep their defaults but can be overridden by config values.

Usage:
    from services.config_loader import get_config, get_section
    config = get_config()
    db_path = get_section("database").get("path", "data/epp.db")
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_config: Optional[Dict[str, Any]] = None
_config_path: Optional[Path] = None


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load config.yaml and cache as singleton."""
    global _config, _config_path

    if _config is not None and config_path is None:
        return _config

    if config_path:
        path = Path(config_path)
    elif os.environ.get("EPP_CONFIG_PATH"):
        path = Path(os.environ["EPP_CONFIG_PATH"])
    else:
        candidates = [
            Path("config.yaml"),
            Path(__file__).parent.parent / "config.yaml",
        ]
        path = next((c for c in candidates if c.exists()), None)
        if path is None:
            logger.warning("config.yaml not found, using empty config")
            _config = {}
            return _config

    with open(path, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f) or {}

    _config_path = path
    logger.info(f"[config_loader] Loaded config from {path}")
    return _config


def get_config() -> Dict[str, Any]:
    """Get the loaded configuration (loads if not yet loaded)."""
    if _config is None:
        return load_config()
    return _config


def get_section(section: str, default: Optional[Dict] = None) -> Dict[str, Any]:
    """Get a specific section from the configuration."""
    return get_config().get(section, default or {})


def get_value(section: str, key: str, default: Any = None) -> Any:
    """Get a specific value from a section."""
    return get_section(section).get(key, default)


def reset_config() -> None:
    """Reset the singleton (for testing only)."""
    global _config, _config_path
    _config = None
    _config_path = None
```

---

#### 0.7 — Corriger get_db() path

⚡ **VÉRIFIE D'ABORD** : `grep -n "def get_db\|ispace\|epp.db" engine.py`

**Si `get_db()` utilise déjà `"data/epp.db"` ou la config, passe.**

Sinon, modifier le default de `get_db()` :

```python
async def get_db(db_path: Optional[str] = None) -> "ISpaceDB":
    """Get or create the singleton ISpaceDB instance."""
    if db_path is None:
        try:
            from services.config_loader import get_value
            db_path = get_value("database", "path", "data/epp.db")
        except Exception:
            db_path = "data/epp.db"
    # ... reste inchangé
```

#### Tests de passage — Étape 0

```bash
# Tests existants ne régressent pas
pytest tests/ -v --tb=short 2>&1 | tail -20

# Nouveau test config_loader (si créé)
pytest tests/test_phase3_config_loader.py -v
```

Créer `tests/test_phase3_config_loader.py` avec au minimum :
- `test_load_from_explicit_path` — charge un config.yaml temporaire
- `test_get_config_is_singleton` — get_config() retourne le même objet
- `test_get_section_returns_section` — get_section() retourne la section demandée
- `test_get_section_returns_default_if_missing` — default pour section absente
- `test_reset_config_clears_singleton` — reset permet de recharger
- `test_missing_config_returns_empty` — pas de crash si fichier absent
- `test_env_variable_override` — EPP_CONFIG_PATH est honoré

**Critère : 7+ tests verts, 0 régression.**

---

### ÉTAPE 1 — MockProvider : Infrastructure de test

**Objectif** : Créer un MockProvider et un helper de triplets synthétiques pour tester
tout le flux sans Ollama.

⚡ **VÉRIFIE D'ABORD** : `ls services/providers/mock_provider.py 2>/dev/null`

**Si un MockProvider existe déjà et fonctionne, vérifie qu'il implémente les deux niveaux
de mock (D10) et passe.**

Sinon, créer `services/providers/mock_provider.py` :

Le MockProvider doit :
1. Hériter de `ModelProvider` (ABC dans `base.py`)
2. Implémenter `generate()`, `list_models()`, `health_check()`, `get_metadata()` — vérifie la signature exacte de l'ABC avant d'implémenter
3. Retourner des réponses contenant des triplets au format extractible par TripletExtractor
4. Supporter plusieurs `response_set` (au minimum "default" et "bitcoin")
5. Cycler entre les réponses à chaque appel (pour simuler la diversité des modèles)

Le helper `make_synthetic_triplets(n, base_consensus, models)` doit :
1. Retourner des `ConsensusTriplet` pré-fabriqués — vérifie les champs exacts du dataclass avant
2. Avoir des hashes uniques par triplet
3. Être déterministe (même input → même output)

**Response sets** :

- `"default"` : 3 réponses variées sur Solana/blockchain avec triplets extractibles
- `"bitcoin"` : 3 réponses sur Bitcoin/Satoshi/PoW — pour tester le scénario "false claim"

**ATTENTION** : Vérifie l'interface exacte de `ModelProvider` dans `base.py` avant d'implémenter.
Les méthodes abstraites peuvent être `generate(query: StructuredQuery) -> StructuredResponse`
ou un autre format. **Implémente ce qui existe, pas ce que ce document suppose.**

#### Tests de passage

Créer `tests/test_phase3_mock_provider.py` :
- `test_mock_provider_generate` — retourne un StructuredResponse non-vide
- `test_mock_provider_cycles_responses` — réponses différentes à chaque appel
- `test_mock_provider_metadata` — retourne un ModelMetadata valide
- `test_mock_provider_different_response_sets` — "default" vs "bitcoin" diffèrent
- `test_synthetic_triplets_default` — 3 triplets, champs non-vides
- `test_synthetic_triplets_custom_count` — n=5 retourne 5 triplets
- `test_synthetic_triplets_unique_hashes` — hashes tous différents

**Critère : 7+ tests verts, 0 régression.**

---

### ÉTAPE 2 — Orchestrateur enrichi : collecte des ConsensusTriplet

**Objectif** : Modifier l'orchestrateur pour retourner les triplets dans ESMMRunResult.
Modifier le factory pour accepter des providers du registry.

⚡ **VÉRIFIE D'ABORD** :
```bash
grep -n "consensus_triplets" orchestrator.py
grep -n "_collected_triplets" orchestrator.py
grep -n "ProviderRegistry\|registry" cycle_manager.py
```

**Si l'orchestrateur collecte déjà les triplets et cycle_manager utilise déjà le registry, passe.**

#### 2.1 — ESMMRunResult + consensus_triplets

Ajouter à `ESMMRunResult` :
```python
consensus_triplets: List = field(default_factory=list)
```

Importer `ConsensusTriplet` :
```python
from .consensus_engine import ConsensusTriplet
```

#### 2.2 — Collecte dans execute_cycles()

Ajouter `self._collected_triplets: List[ConsensusTriplet] = []` dans `__init__`.

Dans `execute_cycles()`, après que chaque cycle produit ses triplets, les ajouter :
```python
# Vérifie comment le CycleResult expose ses triplets avant d'écrire ce code
# Cherche : grep -n "consensus_triplets\|class CycleResult" cycle_manager.py
self._collected_triplets.extend(result.consensus_triplets)
```

⚠️ **Vérifie le nom exact du champ dans CycleResult** — il peut s'appeler
`consensus_triplets`, `triplets`, ou autre chose. Adapte.

#### 2.3 — Retourner dans finalize_run()

```python
result = ESMMRunResult(
    # ... champs existants inchangés ...
    consensus_triplets=self._collected_triplets,
)
```

#### 2.4 — create_cycle_manager() via ProviderRegistry

Modifier la factory pour accepter un paramètre optionnel `registry` ou `providers` :

```python
async def create_cycle_manager(db, run_id, models, providers=None, registry=None):
    # Si providers fournis directement → les utiliser
    # Sinon si registry → lire le registry
    # Sinon → fallback OllamaProvider (comportement actuel conservé)
```

⚠️ **Vérifie la signature actuelle de `create_cycle_manager()`** avant de modifier.
Ne casse pas les appels existants — ajoute des paramètres optionnels.

#### Tests de passage

Créer `tests/test_phase3_orchestrator.py` :
- `test_esmm_run_result_has_consensus_triplets` — le champ existe
- `test_consensus_triplets_default_empty` — default = []
- `test_create_cycle_manager_accepts_providers` — le paramètre est accepté
- `test_create_cycle_manager_fallback_ollama` — sans providers → OllamaProvider

**Critère : 4+ tests verts, 0 régression.**

---

### ÉTAPE 3 — Adaptateur ConsensusTriplet → dict pipeline

**Objectif** : Créer le module de conversion isolé et testé.

Créer `services/esmm/triplet_adapter.py` :

```python
"""Adaptateur ConsensusTriplet → dict exploitable par le pipeline."""

from typing import List, Dict, Any, Optional
from .consensus_engine import ConsensusTriplet


def adapt_consensus_triplet(
    triplet: ConsensusTriplet,
    cochain_entry: Optional[dict] = None,
    epistemic_type: str = "foundational",
) -> Dict[str, Any]:
    """
    Convertit un ConsensusTriplet en dict exploitable par le pipeline.

    Conversions :
    - relation → predicate
    - contributing_models → votes (enrichi avec provider_id, agreed, confidence)
    - signature_5d calculée ou récupérée de la 0-cochaine
    - epistemic_type dérivé ou passé en paramètre
    """
    # Construire les votes depuis contributing_models
    votes = []
    for model_name in triplet.contributing_models:
        # Vérifie si infer_architecture_family est disponible
        try:
            from services.providers.base import infer_architecture_family
            family = infer_architecture_family(model_name)
        except ImportError:
            family = "unknown"

        votes.append({
            "model_id": model_name,
            "provider_id": _infer_provider_id(model_name),
            "agreed": True,
            "confidence": triplet.avg_confidence,
            "architecture_family": family,
        })

    # Signature 5D
    if cochain_entry and "signature_5d" in cochain_entry:
        sig_5d = cochain_entry["signature_5d"]
    else:
        families = set(v["architecture_family"] for v in votes)
        sig_5d = {
            "agreement": triplet.agreement_ratio,
            "semantic_consistency": 1.0 - triplet.std_confidence,
            "centrality": 0.5,
            "stability": 0.5,
            "relation_diversity": len(families) / max(len(votes), 1),
        }

    return {
        "subject": triplet.subject,
        "predicate": triplet.relation,
        "object": triplet.object,
        "consensus_score": triplet.consensus_score,
        "votes": votes,
        "signature_5d": sig_5d,
        "epistemic_type": epistemic_type,
        "triplet_hash": triplet.triplet_hash,
    }


def _infer_provider_id(model_name: str) -> str:
    if "::" in model_name:
        return model_name.split("::")[0]
    return "ollama"


def adapt_all(
    triplets: List[ConsensusTriplet],
    cochain_entries: Optional[List[dict]] = None,
) -> List[Dict[str, Any]]:
    """Adapte une liste de ConsensusTriplet."""
    entries_map = {}
    if cochain_entries:
        for entry in cochain_entries:
            entries_map[entry.get("triplet_hash", "")] = entry

    return [
        adapt_consensus_triplet(t, cochain_entry=entries_map.get(t.triplet_hash))
        for t in triplets
    ]
```

#### Tests de passage

Créer les tests unitaires — utiliser `make_synthetic_triplets()` du MockProvider pour les données :
- `test_adapt_single_triplet` — un ConsensusTriplet → dict avec les bons champs
- `test_relation_becomes_predicate` — triplet.relation = dict["predicate"]
- `test_votes_from_contributing_models` — autant de votes que de models
- `test_signature_5d_present` — les 5 dimensions existent
- `test_adapt_all` — liste de N triplets → liste de N dicts

**Critère : 5+ tests verts, 0 régression.**

---

### ÉTAPE 4 — Seed graphe depuis question

**Objectif** : Permettre au premier `epp ask` de fonctionner sur un graphe vide.

Créer `services/esmm/question_seeder.py` :

Le seeder doit :
1. Tokeniser la question (mots alphanumériques)
2. Retirer les stop words (anglais + français)
3. Garder les mots de 2+ caractères, normaliser en lowercase
4. Injecter les concepts dans le graphe via `db.add_concept()` si le graphe est vide
5. Retourner le nombre de concepts injectés

⚡ **VÉRIFIE D'ABORD** : `grep -n "def add_concept\|def get_concept\|def get_stats" engine.py`
pour connaître les signatures exactes des méthodes DB.

#### Tests de passage

- `test_extract_seed_concepts` — "Solana effective TPS exceeds 3000" → ["solana", "effective", "tps", "exceeds", "3000"]
- `test_stop_words_filtered` — "the", "is", "a" supprimés
- `test_empty_question_returns_something` — au moins 1 concept
- `test_seed_graph_skips_if_not_empty` — retourne 0 si graphe non-vide

**Critère : 4+ tests verts, 0 régression.**

---

### ÉTAPE 5 — Hook post-cristallisation

**Objectif** : Alimenter le track record et loguer les transitions de tier.

Créer `services/esmm/post_crystallization.py` :

```python
"""Hook unique post-cristallisation — track record + tier transitions."""

import logging
from typing import Optional, TYPE_CHECKING

from .attestation import EpistemicAttestation

if TYPE_CHECKING:
    from database.engine import ISpaceDB

logger = logging.getLogger("esmm.post_crystallization")


async def post_crystallization_hook(
    attestation: EpistemicAttestation,
    db: "ISpaceDB",
    previous_tier: Optional[str] = None,
) -> None:
    """
    Actions post-cristallisation :
    1. Enregistre chaque vote dans model_track_record
    2. Logue la transition de tier si applicable
    """
    # 1. Track record
    for vote in attestation.model_votes:
        try:
            await db.record_model_prediction(
                model_id=vote.model_id,
                provider_id=vote.provider_id,
                claim_hash=attestation.claim_hash,
                predicted_confidence=vote.confidence,
                agreed=vote.agreed,
                run_id=attestation.run_id,
            )
        except Exception as e:
            logger.warning(f"Track record failed for {vote.model_id}: {e}")

    # 2. Tier transition
    from_tier = previous_tier or "sandbox"
    to_tier = attestation.confidence_tier

    if from_tier != to_tier:
        try:
            await db.log_tier_transition(
                claim_hash=attestation.claim_hash,
                from_tier=from_tier,
                to_tier=to_tier,
                reason=f"crystallization (consensus={attestation.consensus_score:.3f})",
                run_id=attestation.run_id,
            )
        except Exception as e:
            logger.warning(f"Tier transition log failed: {e}")
```

⚠️ **VÉRIFIE** que les signatures de `record_model_prediction()` et `log_tier_transition()`
correspondent à ce que tu as implémenté en étape 0.3. Adapte si nécessaire.

#### Tests de passage

- `test_hook_records_all_votes` — N votes → N lignes dans model_track_record
- `test_hook_logs_tier_transition` — tier différent → 1 ligne dans tier_transitions
- `test_hook_no_transition_if_same_tier` — même tier → 0 ligne dans tier_transitions
- `test_hook_handles_db_error_gracefully` — exception DB → warning, pas crash

**Critère : 4+ tests verts, 0 régression.**

---

### ÉTAPE 6 — Pipeline : branchement réel

**Objectif** : Réécrire `_extract_triplets_from_question()` pour appeler l'orchestrateur réel.
C'est l'étape centrale qui comble le fossé.

⚡ **VÉRIFIE D'ABORD** :
```bash
grep -n "def _extract_triplets_from_question\|return \[\]" pipeline.py
grep -n "def run_pipeline\|create_esmm_run" pipeline.py
```

#### 6.1 — Supprimer la double création de run (D1)

Dans `run_pipeline()`, supprimer l'appel à `db.create_esmm_run()`.
Le pipeline récupérera le `run_id` de l'orchestrateur.

⚠️ **Vérifie que rien d'autre dans run_pipeline() ne dépend de ce run_id précoce.**
Si oui, réorganise : le run_id arrive après l'appel à `_extract_triplets_from_question()`.

#### 6.2 — Réécrire _extract_triplets_from_question()

```python
async def _extract_triplets_from_question(
    question: str,
    db: "ISpaceDB",
    models: Optional[List[str]],
    run_logger: RunLogger,
    metrological_frame: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Extrait les triplets via l'orchestrateur ESMM complet.

    Returns:
        Tuple (triplets adaptés en dicts, run_id)
    """
    from .question_seeder import seed_graph_from_question
    from .triplet_adapter import adapt_all

    # Seed le graphe si vide (D7)
    seeded = await seed_graph_from_question(db, question)
    if seeded > 0:
        logger.info(f"Seeded graph with {seeded} concepts from question")

    # Configurer et lancer l'orchestrateur (D1, D2, D3)
    # VÉRIFIE la signature exacte de ESMMRunConfig et ESMMOrchestrator
    from .orchestrator import ESMMOrchestrator, ESMMRunConfig
    config = ESMMRunConfig(models=models or _get_default_models())
    orchestrator = ESMMOrchestrator(db=db, config=config)

    run_logger.phase_start("esmm_orchestrator", question=question)
    result = await orchestrator.run()
    run_logger.phase_end("esmm_orchestrator",
                         cycles=result.cycles_completed,
                         triplets=result.total_triplets)

    # Adapter les ConsensusTriplet → format pipeline (D4)
    adapted = adapt_all(result.consensus_triplets)

    return adapted, result.run_id
```

⚠️ **ATTENTION** :
- Vérifie la signature exacte de `ESMMRunConfig` — le champ peut être `models`, `model_names`, ou autre
- Vérifie comment `ESMMOrchestrator.run()` fonctionne — c'est peut-être `initialize_run()` + `execute_cycles()` + `finalize_run()` en séquence, pas un seul `.run()`
- Si `.run()` n'existe pas, chaîne les appels existants

#### 6.3 — Modifier run_pipeline() pour utiliser le run_id retourné

```python
async def run_pipeline(...) -> PipelineResult:
    # ... config init ...

    # PAS de create_esmm_run ici (D1)

    extracted_triplets, run_id = await _extract_triplets_from_question(
        question, db, models, RunLogger(run_id=0, question=question),
        metrological_frame
    )

    # Recréer le run_logger avec le vrai run_id
    run_logger = RunLogger(run_id=run_id, question=question)

    # Boucle de cristallisation (logique existante conservée)
    for triplet in extracted_triplets:
        # ... crystallize() ...

        # Hook post-cristallisation (D8)
        from .post_crystallization import post_crystallization_hook
        await post_crystallization_hook(attestation, db)

        # ... injection graphe (existant) ...
```

#### Tests de passage

Créer `tests/test_phase3_pipeline.py` — avec MockProviders enregistrés dans le registry :
- `test_pipeline_produces_attestations` — au moins 1 attestation avec MockProvider
- `test_pipeline_no_double_run` — 1 seul run ESMM en DB après un pipeline
- `test_pipeline_stores_attestations_in_db` — attestation récupérable par hash
- `test_pipeline_enriches_graph` — au moins 1 nouveau triplet dans le graphe
- `test_pipeline_calls_post_crystallization_hook` — track record alimenté

**Critère : 5+ tests verts, 0 régression.**

---

### ÉTAPE 7 — CLI : branchement sur DB réelle

**Objectif** : Brancher `epp ask`, `epp query`, `epp graph stats`, `epp submit` sur la DB.

⚡ **VÉRIFIE D'ABORD** : `grep -n "TODO\|mock\|placeholder" epp_cli.py`

#### 7.1 — `epp ask`

Remplacer le mock par l'appel réel au pipeline. Vérifie comment le CLI actuel est structuré
(click, argparse, ou autre) et adapte.

```python
async def _run_ask(question, models, frame):
    from database.engine import get_db
    from services.esmm.pipeline import run_pipeline, PipelineConfig

    db = await get_db()
    config = PipelineConfig(metrological_frame=frame)
    result = await run_pipeline(
        question=question,
        db=db,
        models=models,
        config=config,
    )
    return result
```

#### 7.2 — `epp query`

```python
async def _run_query(subject, min_confidence):
    db = await get_db()
    return await db.get_attestations_by_subject(subject, min_confidence)
```

#### 7.3 — `epp graph stats`

```python
async def _run_graph_stats():
    db = await get_db()
    stats = await db.get_stats()
    attestation_count = await db.get_attestation_count()
    return {**stats, "attestations": attestation_count}
```

#### 7.4 — `epp submit` (D9)

```python
async def _run_submit(claim_hash=None):
    db = await get_db()
    if claim_hash is None:
        att = await db.get_latest_attestation()
        if att is None:
            return None, "No attestation found"
        claim_hash = att["claim_hash"]

    att = await db.get_attestation_by_hash(claim_hash)
    if att is None:
        return None, f"Attestation {claim_hash} not found"

    await db.update_attestation_submission_status(claim_hash, "queued")
    return att, None
```

Affichage : récapitulatif de l'attestation + "Attestation queued for on-chain anchoring."
**Pas de faux TX hash.**

#### Tests de passage

Créer `tests/test_phase3_cli.py` :
- `test_ask_command_exists` — la commande "ask" est enregistrée
- `test_query_reads_db` — retourne des attestations depuis la DB
- `test_graph_stats_returns_numbers` — compteurs non-nuls après un pipeline
- `test_submit_queues_attestation` — status passe à "queued"
- `test_submit_without_hash_uses_latest` — prend la dernière attestation

**Critère : 5+ tests verts, 0 régression.**

---

### ÉTAPE 8 — Tests d'intégration + track record

**Objectif** : Tester le flux complet : question → orchestrateur → cristallisation → DB → query.

Créer `tests/test_phase3_integration.py` :

```python
"""Tests Phase 3 — Intégration end-to-end avec MockProviders."""

# Pattern de test :
# 1. Créer une DB temporaire
# 2. Enregistrer des MockProviders dans le registry
# 3. Appeler run_pipeline()
# 4. Vérifier : attestations en DB, graphe enrichi, track record alimenté

class TestEndToEndPipeline:
    """Flux complet question → attestation."""

    def test_full_pipeline_produces_attestations(self):
        """Un pipeline complet produit au moins 1 attestation."""
        ...

    def test_attestations_stored_in_db(self):
        """Les attestations sont récupérables par hash."""
        ...

    def test_graph_enriched_after_pipeline(self):
        """Le graphe contient plus de triplets après un pipeline."""
        ...

    def test_track_record_populated(self):
        """model_track_record contient des entrées après un pipeline."""
        ...

    def test_tier_transition_logged(self):
        """tier_transitions contient une entrée si le tier a changé."""
        ...

    def test_multiple_questions_grow_graph(self):
        """3 questions successives enrichissent le graphe progressivement."""
        ...

class TestImportsConsistency:
    """Vérifier que tous les imports Phase 3 fonctionnent."""

    def test_pipeline_imports(self):
        from services.esmm.pipeline import run_pipeline, PipelineConfig, PipelineResult

    def test_orchestrator_imports(self):
        from services.esmm.orchestrator import ESMMOrchestrator, ESMMRunConfig, ESMMRunResult

    def test_mock_provider_imports(self):
        from services.providers.mock_provider import MockProvider, make_synthetic_triplets

    def test_config_loader_imports(self):
        from services.config_loader import get_config, get_section, load_config, reset_config

    def test_adapter_imports(self):
        from services.esmm.triplet_adapter import adapt_consensus_triplet, adapt_all

    def test_seeder_imports(self):
        from services.esmm.question_seeder import extract_seed_concepts

    def test_hook_imports(self):
        from services.esmm.post_crystallization import post_crystallization_hook
```

Créer `tests/test_phase3_track_record.py` :

- `test_record_model_prediction_signature` — la méthode accepte les bons paramètres
- `test_log_tier_transition_signature` — la méthode accepte les bons paramètres
- `test_brier_score_view_exists` — la vue v_model_brier_scores est créée

**Critère : 10+ tests verts sur les deux fichiers, 0 régression.**

---

### ÉTAPE 9 — Scénarios de démonstration

**Objectif** : Modifier les 3 scénarios existants pour utiliser le vrai pipeline.

⚡ **VÉRIFIE D'ABORD** : `cat scenario_1.py | head -30` — comprendre la structure actuelle.

**A. Modifier `scenario_1.py` (Verifiable factual claim)**

Le scénario doit :
1. Configurer la DB
2. Enregistrer des MockProviders dans le ProviderRegistry
3. Appeler `run_pipeline("Solana effective TPS exceeds 3000", ...)`
4. Afficher les attestations produites, leurs tiers, les stats du graphe

**B. Modifier `scenario_2.py` (False claim rejection)**

Même structure mais avec un claim faux ("Bitcoin was invented by Elon Musk").
Le MockProvider "bitcoin" retourne des réponses contradictoires → consensus faible → sandbox.

Ajouter un response_set `"bitcoin_false_claim"` dans `mock_provider.py` si nécessaire.

**C. Modifier `scenario_3.py` (Progressive enrichment)**

Exécuter 3 questions successives et montrer que le graphe grandit entre chaque question.

#### Tests de passage

```bash
python scenario_1.py && echo "OK" || echo "FAIL"
python scenario_2.py && echo "OK" || echo "FAIL"
python scenario_3.py && echo "OK" || echo "FAIL"
```

Chaque scénario termine sans erreur et affiche des résultats cohérents.

---

### ÉTAPE 10 — Régression globale + documentation

**Objectif** : Valider que TOUS les tests passent. Mettre à jour ARCHITECTURE.md et CHANGELOG.md.

#### A. Suite complète

```bash
pytest tests/ -v --tb=short
```

**Critère : 170+ tests passent, 0 failed.** Les 138 tests Phase 0-2 passent sans régression.

#### B. Scénarios

```bash
python scenario_1.py && python scenario_2.py && python scenario_3.py && echo "ALL OK"
```

#### C. CHANGELOG.md

Ajouter une entrée factuelle :

```markdown
## [2026-02-XX] Phase 3 — End-to-end pipeline

- config_loader.py: centralized config.yaml loading (singleton)
- MockProvider: realistic mock for full pipeline testing
- orchestrator.py: ESMMRunResult enriched with consensus_triplets
- cycle_manager.py: create_cycle_manager() accepts ProviderRegistry providers
- pipeline.py: _extract_triplets_from_question() calls real orchestrator
- pipeline.py: post-crystallization hook (track record + tier transitions)
- pipeline.py: graph seeding from question on empty graph
- epp_cli.py: query reads DB, graph stats reads DB, submit loads attestation
- engine.py: +13 DB methods for attestations, track record, frames
- schema.sql: +4 tables (attestations, metrological_frames, model_track_record, tier_transitions)
- attestation.py: confidence tiers aligned to sandbox/proposition/validated/verified
- Tests: 170+ pass (30+ new Phase 3 tests)
```

#### D. ARCHITECTURE.md

Ajouter une section Phase 3 (max 10 lignes) documentant :
- config_loader.py role
- Pipeline flow: CLI → pipeline → orchestrator → crystallization → DB
- Nouveaux modules: triplet_adapter, question_seeder, post_crystallization
- MockProvider location and purpose

---

## RÉSUMÉ DES CRITÈRES DE VALIDATION PAR ÉTAPE

| Étape | Quoi | Critère |
|-------|------|---------|
| **0** | Audit + infrastructure (tables, méthodes, tiers, config, get_db) | Audit documenté + 7+ tests config_loader + 0 régression |
| **1** | MockProvider + synthetic triplets | 7+ tests verts |
| **2** | Orchestrateur enrichi + factory | 4+ tests verts |
| **3** | Adaptateur ConsensusTriplet → dict | 5+ tests verts |
| **4** | Seed graphe depuis question | 4+ tests verts |
| **5** | Hook post-cristallisation | 4+ tests verts |
| **6** | Pipeline branchement réel | 5+ tests verts |
| **7** | CLI query/stats/submit | 5+ tests verts |
| **8** | Tests intégration + track record | 10+ tests verts |
| **9** | Scénarios mis à jour | 3 scénarios OK |
| **10** | Régression + docs | 170+ pass, 0 fail |

---

## RAPPEL FINAL

- **Vérifie avant d'agir** : chaque étape commence par `⚡ VÉRIFIE D'ABORD`
- **Ne crée pas de code mort** : si ça existe et fonctionne, ne touche pas
- **Ne casse pas ce qui fonctionne** : `pytest tests/ -v --tb=short` après chaque modification
- **Ordre strict** : 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10
- **Tests avant tout** : tu ne passes pas à l'étape suivante tant que les tests de l'étape courante ne passent pas
- **Régression zéro** : les 138 tests Phase 0-2 doivent passer à chaque étape
- **Le pipeline est le seul pont** : orchestrateur → pipeline → cristallisation. Pas de raccourci.
- **Clarté > Concision** : un développeur humain héritera de ce code

---

*Document d'instructions Phase 3 — Version définitive — 10 février 2026*
*Base : 138 tests passent, architecture auditée, décisions validées par le fondateur*
*Fusionne : diagnostic V1 + rigueur opérationnelle V0 + principe « vérifie avant d'agir »*
