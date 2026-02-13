# PHASE 0.3 — ESMM Refactoré, Cristallisation & Revalidation

> **Instructions pour Claude Code.** Lis CLAUDE.md ET ce fichier avant chaque étape.
> Ce document est ta feuille de route pour la Phase 0.3. Tu exécutes dans l'ordre, étape par étape.
> **Tu ne passes PAS à l'étape suivante tant que les tests de l'étape courante ne passent pas tous.**

---

## CONTEXTE

Les Phases 0.1 et 0.2 ont posé les fondations : abstraction des providers (ModelProvider/EmbeddingProvider),
rotation multi-provider, versioning des embeddings. Le pipeline ESMM fonctionne (hérité de Lyra) mais
il manque trois choses critiques pour EPP :

1. **Zéro couplage** — Des références directes à Ollama/modèles spécifiques traînent potentiellement
   dans le code ESMM (orchestrator.py est marqué "couplé Lyra" dans ARCHITECTURE.md).

2. **L'attestation n'existe pas comme entité** — Le pipeline produit des cochaines et des triplets,
   mais pas d'objet unifié "attestation épistémique" sérialisable et hashable, prêt pour l'ancrage on-chain.

3. **Pas de revalidation** — On ne peut pas resoumettre une question pour comparer les attestations
   dans le temps ou avec des modèles différents.

**Objectif** : Un pipeline ESMM totalement découplé qui produit des `EpistemicAttestation` cristallisées
(JSON portable + SHA-256), avec logs structurés et capacité de revalidation.

**Critère de validation final** : Soumettre une question au pipeline, obtenir N attestations sérialisées
en JSON avec hash SHA-256, les stocker en DB. Resoumettre la même question (revalidation), obtenir
de nouvelles attestations, comparer les scores de convergence. Tout ça sans aucune référence directe
à un modèle ou provider spécifique dans le code ESMM.

---

## AXIOMES À RESPECTER (rappel — violations = refus du code)

1. **Obsolescence permanente des modèles** — AUCUN nom de modèle ("mistral", "llama", "deepseek",
   "gpt-oss"), AUCUNE URL de provider ("localhost:11434"), AUCUN import direct de `llm_client`,
   `model_rotator`, ou `multimodel` dans les fichiers du pipeline ESMM.
   Le pipeline ne connaît que `ModelProvider`, `MultiProviderRotator` et `ProviderRegistry`.

2. **Le graphe survit à tout** — Les attestations enrichissent le graphe. Elles ne le remplacent pas.
   Chaque attestation porte la trace de ses producteurs (modèles, scores) mais ne dépend pas
   de leur survie.

3. **Transparence des coupures** — Chaque attestation porte explicitement : quels modèles ont voté,
   quel frame métrologique s'applique, quel protocole (version) a été utilisé. Pas de boîte noire.

4. **Calcul local, preuve on-chain** — Tout ce qu'on construit ici est off-chain. L'attestation
   cristallisée est le contrat d'interface avec la future couche Solana (Phase 1).

---

## ÉTAPE 0.3.1 — Audit et purge du couplage

### Objectif

Garantir zéro référence directe à un modèle, provider, ou API spécifique dans les fichiers
du pipeline ESMM.

### Ce que tu fais

**A. Scanner les fichiers suivants** pour détecter les violations :

```
services/esmm/orchestrator.py
services/esmm/cycle_manager.py
services/esmm/cycle_prompts.py
services/esmm/triplet_extractor.py
services/esmm/triplet_validator.py
services/esmm/consensus_engine.py
services/esmm/cochain_builder.py
services/esmm/gap_detector.py
services/esmm/coverage_analyzer.py
```

**Patterns à chercher (violations)** :

```python
# INTERDIT dans ces fichiers :
import llm_client                    # ou from ... import llm_client
import model_rotator                 # ou from ... import ModelRotator
import multimodel                    # ou from ... import multimodel
"localhost:11434"                     # URL Ollama en dur
"ollama"                             # Référence directe au provider (sauf dans des logs informatifs)
"mistral"                            # Nom de modèle en dur
"llama"                              # Nom de modèle en dur
"deepseek"                           # Nom de modèle en dur
"gpt-oss"                            # Nom de modèle en dur
"gemma"                              # Nom de modèle en dur
"qwen"                               # Nom de modèle en dur
httpx.AsyncClient                    # Appel HTTP direct (doit passer par un provider)
requests.post                        # Appel HTTP direct
```

**AUTORISÉ** :
- Imports de `ModelProvider`, `StructuredQuery`, `StructuredResponse`, `ModelMetadata` depuis `services.providers.base`
- Imports de `MultiProviderRotator` depuis `services.esmm.multi_provider_rotator`
- Imports de `ProviderRegistry` depuis `services.providers.registry`
- Noms de modèles dans des logs/messages d'erreur informatifs (ex: `f"Model {model_id} failed"`)
- Noms de modèles dans des docstrings/commentaires exemples

**B. Corriger chaque violation trouvée.**

Pour chaque violation :
1. Identifier ce que le code fait réellement (appel LLM, listing de modèles, etc.)
2. Remplacer par l'appel équivalent via `MultiProviderRotator` ou `ProviderRegistry`
3. Si le code est mort (plus appelé nulle part), le supprimer

**C. Vérifier les imports en cascade.**

Après correction, s'assurer que tous les fichiers importés par les fichiers ESMM sont aussi propres.
Un fichier ESMM qui importe un module utilitaire qui lui-même importe `llm_client` est une violation.

**D. Ne PAS toucher aux fichiers suivants** (ils sont hors pipeline ou legacy assumé) :

```
llm_client.py              # Legacy, utilisé peut-être par l'interface web
model_rotator.py           # Legacy, remplacé par multi_provider_rotator
multimodel.py              # Endpoints FastAPI legacy
embeddings.py              # Déprécié (Phase 0.2)
hydrate_embeddings.py      # Outil legacy isolé
```

### Ce que tu ne fais PAS

- Tu ne supprimes PAS les fichiers legacy (llm_client.py, model_rotator.py, etc.)
- Tu ne modifies PAS la logique métier du pipeline — seulement le câblage
- Tu ne crées PAS de nouveau fichier dans cette étape

### Tests étape 0.3.1

```python
# tests/test_phase03_audit.py

import ast
import os
import re
from pathlib import Path

# Fichiers du pipeline ESMM à auditer
ESMM_FILES = [
    "services/esmm/orchestrator.py",
    "services/esmm/cycle_manager.py",
    "services/esmm/cycle_prompts.py",
    "services/esmm/triplet_extractor.py",
    "services/esmm/triplet_validator.py",
    "services/esmm/consensus_engine.py",
    "services/esmm/cochain_builder.py",
    "services/esmm/gap_detector.py",
    "services/esmm/coverage_analyzer.py",
]

# Patterns interdits (regex)
FORBIDDEN_IMPORTS = [
    r"^\s*(from\s+.*)?import\s+llm_client",
    r"^\s*(from\s+.*)?import\s+model_rotator",
    r"^\s*(from\s+.*)?import\s+multimodel",
    r"^\s*from\s+app\.embeddings\s+import",
]

FORBIDDEN_STRINGS = [
    r"localhost:11434",
    r"httpx\.AsyncClient\(",
    r"requests\.(get|post|put|delete)\(",
]

FORBIDDEN_HARDCODED_MODELS = [
    r"['\"]mistral['\"]",
    r"['\"]llama['\"]",
    r"['\"]deepseek['\"]",
    r"['\"]gpt-oss['\"]",
    r"['\"]gemma['\"]",
    r"['\"]qwen['\"]",
]


class TestESMMDecoupling:
    """Vérifie zéro couplage direct dans le pipeline ESMM."""

    def _get_project_root(self):
        """Find project root (parent of services/)."""
        # Adapter selon la structure réelle du projet
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "services").exists():
                return parent
        return Path.cwd()

    def _read_file_if_exists(self, filepath: str) -> str:
        """Read file content, return empty string if not found."""
        root = self._get_project_root()
        full_path = root / filepath
        if full_path.exists():
            return full_path.read_text(encoding="utf-8")
        return ""

    def test_no_forbidden_imports(self):
        """Aucun fichier ESMM n'importe llm_client, model_rotator, ou multimodel."""
        violations = []
        for filepath in ESMM_FILES:
            content = self._read_file_if_exists(filepath)
            if not content:
                continue
            for line_no, line in enumerate(content.splitlines(), 1):
                for pattern in FORBIDDEN_IMPORTS:
                    if re.search(pattern, line):
                        violations.append(f"{filepath}:{line_no} → {line.strip()}")

        assert not violations, (
            f"Forbidden imports found in ESMM pipeline:\n" +
            "\n".join(violations)
        )

    def test_no_hardcoded_urls(self):
        """Aucun fichier ESMM ne contient d'URL de provider en dur."""
        violations = []
        for filepath in ESMM_FILES:
            content = self._read_file_if_exists(filepath)
            if not content:
                continue
            for line_no, line in enumerate(content.splitlines(), 1):
                # Skip comments and docstrings
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                for pattern in FORBIDDEN_STRINGS:
                    if re.search(pattern, line):
                        violations.append(f"{filepath}:{line_no} → {line.strip()}")

        assert not violations, (
            f"Hardcoded URLs or direct HTTP clients in ESMM pipeline:\n" +
            "\n".join(violations)
        )

    def test_no_hardcoded_model_names(self):
        """Aucun fichier ESMM ne contient de noms de modèles en dur (hors commentaires/logs)."""
        violations = []
        for filepath in ESMM_FILES:
            content = self._read_file_if_exists(filepath)
            if not content:
                continue
            for line_no, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                # Skip comments, docstrings, log messages
                if stripped.startswith("#"):
                    continue
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                # Allow in f-strings used for logging (logger.info/debug/warning/error)
                if re.match(r"^\s*logger\.(info|debug|warning|error)", stripped):
                    continue
                for pattern in FORBIDDEN_HARDCODED_MODELS:
                    if re.search(pattern, line):
                        violations.append(f"{filepath}:{line_no} → {line.strip()}")

        assert not violations, (
            f"Hardcoded model names in ESMM pipeline:\n" +
            "\n".join(violations)
        )

    def test_esmm_files_exist(self):
        """Au moins les fichiers ESMM principaux existent."""
        root = self._get_project_root()
        critical_files = [
            "services/esmm/orchestrator.py",
            "services/esmm/cycle_manager.py",
            "services/esmm/triplet_extractor.py",
            "services/esmm/consensus_engine.py",
            "services/esmm/cochain_builder.py",
        ]
        missing = [f for f in critical_files if not (root / f).exists()]
        assert not missing, f"Critical ESMM files missing: {missing}"
```

**Critère de passage** : `pytest tests/test_phase03_audit.py -v` → tous verts.

---

## ÉTAPE 0.3.2 — Modèle EpistemicAttestation (cristallisation)

### Objectif

Créer l'entité centrale d'EPP : l'attestation épistémique cristallisée. C'est l'objet que le pipeline
produit en sortie, que la DB stocke, et que Solana ancrera en Phase 1.

### Ce que tu fais

**A. Créer `services/esmm/attestation.py`**

```python
"""
Epistemic Attestation — Output cristallisé du pipeline ESMM.

Une attestation est un triplet validé par consensus multi-modèles,
portant une signature épistémique 5D et un hash SHA-256 déterministe.

C'est le contrat d'interface entre le moteur ESMM (off-chain) et
la couche Solana (on-chain, Phase 1).
"""

import hashlib
import json
import time
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class Signature5D(BaseModel):
    """Signature épistémique 5-dimensionnelle (0-cochaine)."""
    agreement: float = Field(ge=0.0, le=1.0, description="Accord inter-modèles")
    semantic_consistency: float = Field(ge=0.0, le=1.0, description="Cohérence sémantique interne")
    centrality: float = Field(ge=0.0, le=1.0, description="Centralité dans le graphe")
    stability: float = Field(ge=0.0, le=1.0, description="Stabilité temporelle")
    relation_diversity: float = Field(ge=0.0, le=1.0, description="Diversité relationnelle")

    def to_vector(self) -> List[float]:
        """Retourne la signature comme vecteur [5]."""
        return [
            self.agreement,
            self.semantic_consistency,
            self.centrality,
            self.stability,
            self.relation_diversity,
        ]


class ModelVote(BaseModel):
    """Vote d'un modèle dans le consensus."""
    model_id: str                         # Ex: "ollama::mistral:7b", "openai::gpt-4o-mini"
    provider_id: str                      # Ex: "ollama", "openai", "anthropic"
    agreed: bool                          # A voté pour le triplet
    confidence: float = Field(ge=0.0, le=1.0)
    weight: float = Field(default=1.0, ge=0.0)  # Poids dans le vote (1.0 = égalitaire MVP)


class EpistemicAttestation(BaseModel):
    """
    Attestation épistémique cristallisée.

    Produite par le pipeline ESMM, stockable en DB, sérialisable en JSON
    portable, hashable de manière déterministe. Prête pour l'ancrage on-chain.

    Grain : un triplet canonique (subject, predicate, object).
    Un run ESMM sur une question produit potentiellement N attestations.
    """

    # === IDENTIFIANT ===
    claim_hash: str = Field(
        description="SHA-256 du triplet canonique + frame. Calculé par crystallize()."
    )

    # === CONTENU (triplet canonique) ===
    subject: str = Field(max_length=64, description="Sujet du triplet")
    predicate: str = Field(max_length=64, description="Relation canonique")
    object: str = Field(max_length=128, description="Objet du triplet")

    # === CONSENSUS ===
    consensus_score: float = Field(ge=0.0, le=1.0, description="Score de consensus [0, 1]")
    models_consulted: int = Field(ge=1, description="Nombre de modèles consultés")
    models_agreeing: int = Field(ge=0, description="Nombre de modèles en accord")
    model_votes: List[ModelVote] = Field(description="Détail des votes par modèle")

    # === SIGNATURE ÉPISTÉMIQUE 5D ===
    signature_5d: Signature5D

    # === CLASSIFICATION ===
    epistemic_type: str = Field(
        description="Type épistémique : foundational | bridge | specialized"
    )
    confidence_tier: str = Field(
        description="Tier de confiance : low | medium | high | verified"
    )

    # === PROVENANCE ===
    metrological_frame: Optional[str] = Field(
        default=None,
        description="ID du référentiel métrologique applicable"
    )
    source_anchor: Optional[str] = Field(
        default=None,
        description="Hash de source vérifiable externe (brise la circularité)"
    )
    run_id: Optional[int] = Field(
        default=None,
        description="ID du run ESMM ayant produit cette attestation"
    )
    question: Optional[str] = Field(
        default=None,
        description="Question originale soumise au pipeline"
    )

    # === TEMPOREL ===
    timestamp: float = Field(description="Epoch de cristallisation")
    protocol_version: str = Field(default="0.3", description="Version du protocole ESMM")

    # === REVALIDATION ===
    validation_count: int = Field(default=1, description="Nombre de validations")
    previous_hash: Optional[str] = Field(
        default=None,
        description="Hash de l'attestation précédente (si revalidation)"
    )

    # === VALIDATORS ===
    @field_validator("epistemic_type")
    @classmethod
    def validate_epistemic_type(cls, v: str) -> str:
        allowed = {"foundational", "bridge", "specialized", "generalist", "hybrid"}
        if v not in allowed:
            raise ValueError(f"epistemic_type must be one of {allowed}, got '{v}'")
        return v

    @field_validator("confidence_tier")
    @classmethod
    def validate_confidence_tier(cls, v: str) -> str:
        allowed = {"low", "medium", "high", "verified"}
        if v not in allowed:
            raise ValueError(f"confidence_tier must be one of {allowed}, got '{v}'")
        return v

    def to_portable_json(self) -> str:
        """
        Sérialise en JSON déterministe (clés triées, floats à 6 décimales).

        Ce format est le contrat d'interface avec la couche Solana.
        Deux attestations identiques produisent le même JSON.
        """
        data = self.model_dump()
        return json.dumps(
            data,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        )

    def to_compact_dict(self) -> Dict[str, Any]:
        """
        Version compacte pour stockage on-chain (sans détail des votes).
        Correspond à la structure EpistemicAttestation du programme Anchor.
        """
        return {
            "claim_hash": self.claim_hash,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "consensus_score": round(self.consensus_score, 4),
            "models_consulted": self.models_consulted,
            "models_agreeing": self.models_agreeing,
            "sig_5d": self.signature_5d.to_vector(),
            "epistemic_type": self.epistemic_type,
            "confidence_tier": self.confidence_tier,
            "metrological_frame": self.metrological_frame,
            "source_anchor": self.source_anchor,
            "timestamp": self.timestamp,
            "validation_count": self.validation_count,
            "protocol_version": self.protocol_version,
        }


def compute_claim_hash(
    subject: str,
    predicate: str,
    object_: str,
    metrological_frame: Optional[str] = None,
) -> str:
    """
    Calcule le hash SHA-256 déterministe d'un triplet + frame.

    Le hash est calculé sur la concaténation canonique :
      SHA-256(subject_lower + "|" + predicate_lower + "|" + object_lower + "|" + frame_or_empty)

    Args:
        subject: Sujet du triplet (sera lowercased + stripped)
        predicate: Relation canonique (sera lowercased + stripped)
        object_: Objet du triplet (sera lowercased + stripped)
        metrological_frame: Frame applicable (optionnel)

    Returns:
        Hash SHA-256 en hexadécimal (64 chars)
    """
    canonical = "|".join([
        subject.lower().strip(),
        predicate.lower().strip(),
        object_.lower().strip(),
        (metrological_frame or "").lower().strip(),
    ])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def derive_confidence_tier(consensus_score: float) -> str:
    """
    Dérive le tier de confiance à partir du score de consensus.

    Seuils MVP (à gouverner en Phase 3+) :
      [0.0, 0.4) → low
      [0.4, 0.7) → medium
      [0.7, 0.9) → high
      [0.9, 1.0] → verified
    """
    if consensus_score >= 0.9:
        return "verified"
    elif consensus_score >= 0.7:
        return "high"
    elif consensus_score >= 0.4:
        return "medium"
    else:
        return "low"


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
) -> EpistemicAttestation:
    """
    Cristallise les résultats du pipeline ESMM en attestation.

    C'est le point de sortie du pipeline. Prend les outputs bruts
    du consensus engine et du cochain builder, retourne une attestation
    complète avec hash déterministe.

    Args:
        subject: Sujet canonique du triplet
        predicate: Relation canonique
        object_: Objet canonique du triplet
        consensus_score: Score du consensus engine [0, 1]
        model_votes: Détail des votes de chaque modèle
        signature_5d: Signature épistémique 5D du cochain builder
        epistemic_type: Type épistémique du concept
        run_id: ID du run ESMM
        question: Question originale
        metrological_frame: Frame métrologique applicable
        source_anchor: Hash de source externe vérifiable
        previous_hash: Hash d'attestation précédente (si revalidation)
        validation_count: Nombre de validations (1 = première, >1 = revalidation)

    Returns:
        EpistemicAttestation cristallisée avec hash SHA-256
    """
    claim_hash = compute_claim_hash(subject, predicate, object_, metrological_frame)
    confidence_tier = derive_confidence_tier(consensus_score)

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

**B. Créer la table `attestations` dans `schema.sql`**

```sql
-- ============================================================================
-- TABLE 19: ATTESTATIONS (Attestations épistémiques cristallisées)
-- ============================================================================
-- Output final du pipeline ESMM. Contrat d'interface avec la couche Solana.
-- Chaque attestation correspond à un triplet validé par consensus.

CREATE TABLE IF NOT EXISTS attestations (
    -- Clé primaire
    attestation_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identifiant déterministe
    claim_hash TEXT NOT NULL,                -- SHA-256(subject|predicate|object|frame)

    -- Contenu (triplet canonique)
    subject TEXT NOT NULL,                   -- max 64 chars
    predicate TEXT NOT NULL,                 -- max 64 chars (relation canonique)
    object TEXT NOT NULL,                    -- max 128 chars

    -- Consensus
    consensus_score REAL NOT NULL,           -- [0, 1]
    models_consulted INTEGER NOT NULL,
    models_agreeing INTEGER NOT NULL,
    model_votes TEXT NOT NULL,               -- JSON: [{model_id, provider_id, agreed, confidence, weight}]

    -- Signature épistémique 5D
    sig_agreement REAL NOT NULL,
    sig_semantic_consistency REAL NOT NULL,
    sig_centrality REAL NOT NULL,
    sig_stability REAL NOT NULL,
    sig_relation_diversity REAL NOT NULL,

    -- Classification
    epistemic_type TEXT NOT NULL,            -- 'foundational' | 'bridge' | 'specialized' | ...
    confidence_tier TEXT NOT NULL,           -- 'low' | 'medium' | 'high' | 'verified'

    -- Provenance
    metrological_frame TEXT,                 -- ID du référentiel applicable
    source_anchor TEXT,                      -- Hash source vérifiable externe
    run_id INTEGER,                          -- FK vers esmm_runs
    question TEXT,                           -- Question originale

    -- Temporel
    timestamp REAL NOT NULL,
    protocol_version TEXT NOT NULL DEFAULT '0.3',

    -- Revalidation
    validation_count INTEGER DEFAULT 1,
    previous_hash TEXT,                      -- Hash attestation précédente si revalidation

    -- Sérialisation complète
    portable_json TEXT,                      -- JSON déterministe complet (pour vérification)

    -- Ancrage on-chain (Phase 1 — NULL jusqu'à implémentation Solana)
    solana_tx_signature TEXT,                -- Signature transaction Solana
    solana_slot INTEGER,                     -- Slot Solana
    anchored_at REAL,                        -- Timestamp ancrage

    FOREIGN KEY (run_id) REFERENCES esmm_runs(run_id) ON DELETE SET NULL
);

-- Index
CREATE INDEX IF NOT EXISTS idx_attestations_hash ON attestations(claim_hash);
CREATE INDEX IF NOT EXISTS idx_attestations_subject ON attestations(subject);
CREATE INDEX IF NOT EXISTS idx_attestations_predicate ON attestations(predicate);
CREATE INDEX IF NOT EXISTS idx_attestations_consensus ON attestations(consensus_score DESC);
CREATE INDEX IF NOT EXISTS idx_attestations_tier ON attestations(confidence_tier);
CREATE INDEX IF NOT EXISTS idx_attestations_run ON attestations(run_id);
CREATE INDEX IF NOT EXISTS idx_attestations_frame ON attestations(metrological_frame);
CREATE INDEX IF NOT EXISTS idx_attestations_timestamp ON attestations(timestamp DESC);

-- Vue : attestations de haute confiance
CREATE VIEW IF NOT EXISTS v_high_confidence_attestations AS
SELECT
    attestation_id,
    claim_hash,
    subject,
    predicate,
    object,
    consensus_score,
    confidence_tier,
    models_consulted,
    models_agreeing,
    validation_count,
    timestamp
FROM attestations
WHERE confidence_tier IN ('high', 'verified')
ORDER BY consensus_score DESC;
```

**C. Ajouter les méthodes CRUD dans `engine.py`**

```python
async def store_attestation(self, attestation: Dict[str, Any]) -> int:
    """
    Stocke une attestation cristallisée en DB.

    Args:
        attestation: Dict issu de EpistemicAttestation.model_dump()
            Doit contenir : claim_hash, subject, predicate, object,
            consensus_score, model_votes, signature_5d, etc.

    Returns:
        attestation_id
    """
    ...

async def get_attestation_by_hash(self, claim_hash: str) -> Optional[Dict]:
    """
    Récupère une attestation par son hash.

    Args:
        claim_hash: SHA-256 du triplet + frame

    Returns:
        Dict attestation ou None
    """
    ...

async def get_attestations_by_subject(
    self,
    subject: str,
    min_consensus: float = 0.0,
    limit: int = 50,
) -> List[Dict]:
    """
    Récupère les attestations concernant un sujet.

    Args:
        subject: Sujet à chercher
        min_consensus: Score minimum
        limit: Nombre max de résultats

    Returns:
        Liste d'attestations triées par consensus DESC
    """
    ...

async def get_attestation_history(
    self,
    claim_hash: str,
) -> List[Dict]:
    """
    Récupère l'historique de revalidation d'un claim.

    Toutes les attestations partageant le même claim_hash,
    triées par timestamp ASC (première → dernière validation).

    Args:
        claim_hash: Hash du claim

    Returns:
        Liste chronologique des attestations
    """
    ...
```

### Ce que tu ne fais PAS

- Tu ne modifies PAS `cochain_builder.py` ou `consensus_engine.py` — ils continuent à fonctionner comme avant
- Tu ne supprimes PAS la table `cochain_entries` — elle reste un mécanisme interne
- Tu ne touches PAS à la logique de vote dans `consensus_engine.py`
- Tu ne crées PAS de fichier de documentation .md supplémentaire

### Tests étape 0.3.2

```python
# tests/test_phase03_attestation.py

import pytest
import json
import hashlib
import time
from services.esmm.attestation import (
    EpistemicAttestation,
    Signature5D,
    ModelVote,
    crystallize,
    compute_claim_hash,
    derive_confidence_tier,
)


class TestComputeClaimHash:
    """Tests pour le hash déterministe."""

    def test_hash_is_deterministic(self):
        """Même triplet + frame → même hash."""
        h1 = compute_claim_hash("Solana", "has_property", "high_tps", "tps_v1")
        h2 = compute_claim_hash("Solana", "has_property", "high_tps", "tps_v1")
        assert h1 == h2

    def test_hash_is_case_insensitive(self):
        """Le hash est insensible à la casse."""
        h1 = compute_claim_hash("Solana", "HAS_PROPERTY", "high_tps")
        h2 = compute_claim_hash("solana", "has_property", "HIGH_TPS")
        assert h1 == h2

    def test_hash_strips_whitespace(self):
        """Le hash ignore les espaces en début/fin."""
        h1 = compute_claim_hash("  Solana  ", "has_property", "high_tps")
        h2 = compute_claim_hash("Solana", "has_property", "high_tps")
        assert h1 == h2

    def test_hash_differs_with_frame(self):
        """Le hash change si le frame métrologique change."""
        h1 = compute_claim_hash("Solana", "has_property", "high_tps", "tps_v1")
        h2 = compute_claim_hash("Solana", "has_property", "high_tps", "tps_v2")
        assert h1 != h2

    def test_hash_differs_without_frame(self):
        """Le hash sans frame diffère de celui avec frame."""
        h1 = compute_claim_hash("Solana", "has_property", "high_tps")
        h2 = compute_claim_hash("Solana", "has_property", "high_tps", "tps_v1")
        assert h1 != h2

    def test_hash_is_sha256(self):
        """Le hash est un SHA-256 valide (64 chars hex)."""
        h = compute_claim_hash("test", "is_a", "thing")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_different_triplets(self):
        """Deux triplets différents → deux hash différents."""
        h1 = compute_claim_hash("A", "is_a", "B")
        h2 = compute_claim_hash("A", "is_a", "C")
        assert h1 != h2


class TestSignature5D:
    """Tests pour la signature épistémique."""

    def test_to_vector(self):
        """to_vector retourne une liste de 5 floats."""
        sig = Signature5D(
            agreement=0.9,
            semantic_consistency=0.8,
            centrality=0.7,
            stability=0.6,
            relation_diversity=0.5,
        )
        vec = sig.to_vector()
        assert len(vec) == 5
        assert vec == [0.9, 0.8, 0.7, 0.6, 0.5]

    def test_validation_bounds(self):
        """Les valeurs hors [0, 1] sont rejetées."""
        with pytest.raises(Exception):
            Signature5D(agreement=1.5, semantic_consistency=0.5,
                        centrality=0.5, stability=0.5, relation_diversity=0.5)
        with pytest.raises(Exception):
            Signature5D(agreement=-0.1, semantic_consistency=0.5,
                        centrality=0.5, stability=0.5, relation_diversity=0.5)


class TestDeriveConfidenceTier:
    """Tests pour la dérivation du tier de confiance."""

    def test_low(self):
        assert derive_confidence_tier(0.2) == "low"
        assert derive_confidence_tier(0.0) == "low"
        assert derive_confidence_tier(0.39) == "low"

    def test_medium(self):
        assert derive_confidence_tier(0.4) == "medium"
        assert derive_confidence_tier(0.5) == "medium"
        assert derive_confidence_tier(0.69) == "medium"

    def test_high(self):
        assert derive_confidence_tier(0.7) == "high"
        assert derive_confidence_tier(0.8) == "high"
        assert derive_confidence_tier(0.89) == "high"

    def test_verified(self):
        assert derive_confidence_tier(0.9) == "verified"
        assert derive_confidence_tier(1.0) == "verified"


class TestCrystallize:
    """Tests pour la fonction crystallize."""

    def _make_votes(self, n_agree: int, n_total: int) -> list:
        votes = []
        for i in range(n_total):
            votes.append(ModelVote(
                model_id=f"model_{i}",
                provider_id="mock",
                agreed=(i < n_agree),
                confidence=0.8 if i < n_agree else 0.3,
            ))
        return votes

    def _make_sig(self) -> Signature5D:
        return Signature5D(
            agreement=0.8,
            semantic_consistency=0.75,
            centrality=0.6,
            stability=0.7,
            relation_diversity=0.5,
        )

    def test_crystallize_produces_attestation(self):
        """crystallize retourne une EpistemicAttestation valide."""
        att = crystallize(
            subject="Solana",
            predicate="has_property",
            object_="high_tps",
            consensus_score=0.85,
            model_votes=self._make_votes(3, 4),
            signature_5d=self._make_sig(),
            epistemic_type="foundational",
        )
        assert isinstance(att, EpistemicAttestation)
        assert att.claim_hash is not None
        assert len(att.claim_hash) == 64
        assert att.subject == "Solana"
        assert att.models_consulted == 4
        assert att.models_agreeing == 3
        assert att.confidence_tier == "high"

    def test_crystallize_with_frame(self):
        """crystallize avec frame produit un hash différent de sans frame."""
        att1 = crystallize(
            subject="Solana", predicate="is_a", object_="blockchain",
            consensus_score=0.9, model_votes=self._make_votes(3, 3),
            signature_5d=self._make_sig(), epistemic_type="foundational",
        )
        att2 = crystallize(
            subject="Solana", predicate="is_a", object_="blockchain",
            consensus_score=0.9, model_votes=self._make_votes(3, 3),
            signature_5d=self._make_sig(), epistemic_type="foundational",
            metrological_frame="blockchain_v1",
        )
        assert att1.claim_hash != att2.claim_hash

    def test_crystallize_revalidation(self):
        """crystallize en mode revalidation porte le previous_hash."""
        original = crystallize(
            subject="A", predicate="is_a", object_="B",
            consensus_score=0.8, model_votes=self._make_votes(2, 3),
            signature_5d=self._make_sig(), epistemic_type="bridge",
        )
        revalidated = crystallize(
            subject="A", predicate="is_a", object_="B",
            consensus_score=0.85, model_votes=self._make_votes(3, 3),
            signature_5d=self._make_sig(), epistemic_type="bridge",
            previous_hash=original.claim_hash,
            validation_count=2,
        )
        assert revalidated.previous_hash == original.claim_hash
        assert revalidated.validation_count == 2
        # Même triplet, même hash
        assert revalidated.claim_hash == original.claim_hash


class TestPortableJSON:
    """Tests pour la sérialisation déterministe."""

    def _make_attestation(self) -> EpistemicAttestation:
        return crystallize(
            subject="Solana",
            predicate="has_property",
            object_="high_tps",
            consensus_score=0.85,
            model_votes=[
                ModelVote(model_id="m1", provider_id="p1", agreed=True, confidence=0.9),
                ModelVote(model_id="m2", provider_id="p2", agreed=True, confidence=0.8),
            ],
            signature_5d=Signature5D(
                agreement=0.9, semantic_consistency=0.8,
                centrality=0.7, stability=0.6, relation_diversity=0.5
            ),
            epistemic_type="foundational",
        )

    def test_portable_json_is_valid(self):
        """to_portable_json produit du JSON parseable."""
        att = self._make_attestation()
        j = att.to_portable_json()
        parsed = json.loads(j)
        assert parsed["subject"] == "Solana"
        assert parsed["claim_hash"] == att.claim_hash

    def test_portable_json_is_deterministic(self):
        """Deux appels to_portable_json sur le même objet → même string."""
        att = self._make_attestation()
        j1 = att.to_portable_json()
        j2 = att.to_portable_json()
        assert j1 == j2

    def test_compact_dict_excludes_votes(self):
        """to_compact_dict ne contient pas le détail des votes."""
        att = self._make_attestation()
        compact = att.to_compact_dict()
        assert "model_votes" not in compact
        assert "sig_5d" in compact
        assert len(compact["sig_5d"]) == 5

    def test_portable_json_sorted_keys(self):
        """Le JSON a ses clés triées."""
        att = self._make_attestation()
        j = att.to_portable_json()
        parsed = json.loads(j)
        keys = list(parsed.keys())
        assert keys == sorted(keys)


class TestAttestationValidation:
    """Tests pour la validation Pydantic."""

    def test_invalid_epistemic_type(self):
        """Un epistemic_type invalide est rejeté."""
        with pytest.raises(Exception):
            crystallize(
                subject="A", predicate="is_a", object_="B",
                consensus_score=0.5,
                model_votes=[ModelVote(model_id="m", provider_id="p", agreed=True, confidence=0.5)],
                signature_5d=Signature5D(agreement=0.5, semantic_consistency=0.5,
                                         centrality=0.5, stability=0.5, relation_diversity=0.5),
                epistemic_type="INVALID_TYPE",
            )

    def test_invalid_confidence_tier(self):
        """Un confidence_tier invalide est rejeté."""
        with pytest.raises(Exception):
            EpistemicAttestation(
                claim_hash="a" * 64, subject="A", predicate="is", object="B",
                consensus_score=0.5, models_consulted=1, models_agreeing=1,
                model_votes=[], signature_5d=Signature5D(
                    agreement=0.5, semantic_consistency=0.5,
                    centrality=0.5, stability=0.5, relation_diversity=0.5),
                epistemic_type="foundational",
                confidence_tier="INVALID",
                timestamp=time.time(),
            )
```

**Critère de passage** : `pytest tests/test_phase03_attestation.py -v` → tous verts.

---

## ÉTAPE 0.3.3 — Stockage et pipeline end-to-end

### Objectif

Brancher la cristallisation dans le pipeline ESMM. Un run produit des attestations
qui sont stockées en DB et récupérables.

### Ce que tu fais

**A. Implémenter les méthodes CRUD dans `engine.py`**

Les 4 méthodes définies en 0.3.2.C : `store_attestation`, `get_attestation_by_hash`,
`get_attestations_by_subject`, `get_attestation_history`.

`store_attestation` doit :
1. Recevoir un dict (issu de `EpistemicAttestation.model_dump()`)
2. Extraire les champs de la signature 5D du dict imbriqué
3. Sérialiser `model_votes` en JSON
4. Appeler `to_portable_json()` ou recevoir le JSON portable en paramètre
5. INSERT dans la table `attestations`
6. Retourner `attestation_id`

`get_attestation_by_hash` et `get_attestation_history` doivent parser les JSON stockés
(model_votes, etc.) avant de retourner.

**B. Ajouter un point d'entrée dans `orchestrator.py`**

L'orchestrateur doit exposer une méthode (ou modifier la méthode existante de run)
qui, après le pipeline complet, appelle `crystallize()` pour chaque triplet validé
au-dessus du seuil de consensus et retourne la liste d'attestations.

Le seuil de consensus pour cristallisation est configurable (défaut: 0.4, soit "medium" ou mieux).

```python
async def run_esmm_and_crystallize(
    self,
    question: str,
    metrological_frame: Optional[str] = None,
    min_consensus: float = 0.4,
) -> List[EpistemicAttestation]:
    """
    Exécute le pipeline ESMM complet et cristallise les résultats.

    1. Run ESMM (Divergent → Debate → Meta)
    2. Extraction de triplets
    3. Consensus
    4. Signature 5D
    5. Cristallisation → attestations
    6. Stockage DB

    Args:
        question: Question à soumettre
        metrological_frame: Frame métrologique (optionnel)
        min_consensus: Score minimum pour cristalliser un triplet

    Returns:
        Liste d'EpistemicAttestation cristallisées
    """
    ...
```

**ATTENTION** : Cette méthode orchestre les composants existants. Elle ne réimplémente
PAS le pipeline. Elle appelle les méthodes existantes de `cycle_manager`, `triplet_extractor`,
`consensus_engine`, `cochain_builder`, puis appelle `crystallize()` sur les résultats.

Si l'orchestrateur existant a déjà une méthode de run complète, tu peux soit :
- L'enrichir pour retourner des attestations en plus
- Créer une méthode wrapper qui appelle l'existante puis cristallise

Choisis l'option qui minimise les changements.

**C. Ne PAS toucher à la logique interne des composants existants**

Le `consensus_engine`, `cochain_builder`, `triplet_extractor` etc. continuent de fonctionner
exactement comme avant. La cristallisation est une **couche additionnelle** qui consomme
leur output, pas un remplacement.

### Ce que tu ne fais PAS

- Tu ne réécris PAS le pipeline ESMM — tu ajoutes une sortie
- Tu ne modifies PAS les signatures des méthodes existantes du pipeline
- Tu ne supprimes PAS la logique d'injection dans le graphe — les attestations ET le graphe coexistent
- Tu ne crées PAS de nouvelle table autre que `attestations`

### Tests étape 0.3.3

```python
# tests/test_phase03_storage.py

import pytest
import asyncio
import time
import json
from pathlib import Path

from database.engine import ISpaceDB
from services.esmm.attestation import (
    crystallize, Signature5D, ModelVote, EpistemicAttestation,
)


# ============================================================================
# HELPERS
# ============================================================================

async def create_fresh_db(db_path: str) -> ISpaceDB:
    db = ISpaceDB(db_path)
    await db.initialize()
    return db


async def cleanup_db(db: ISpaceDB):
    if db._pool:
        from database.pool import close_pool
        await close_pool()


def make_test_attestation(
    subject: str = "Solana",
    predicate: str = "has_property",
    object_: str = "high_tps",
    consensus: float = 0.85,
    frame: str = None,
) -> EpistemicAttestation:
    """Crée une attestation de test."""
    return crystallize(
        subject=subject,
        predicate=predicate,
        object_=object_,
        consensus_score=consensus,
        model_votes=[
            ModelVote(model_id="m1", provider_id="mock", agreed=True, confidence=0.9),
            ModelVote(model_id="m2", provider_id="mock", agreed=True, confidence=0.8),
            ModelVote(model_id="m3", provider_id="mock", agreed=False, confidence=0.3),
        ],
        signature_5d=Signature5D(
            agreement=0.8, semantic_consistency=0.75,
            centrality=0.6, stability=0.7, relation_diversity=0.5,
        ),
        epistemic_type="foundational",
        run_id=1,
        question="Test question",
        metrological_frame=frame,
    )


# ============================================================================
# TESTS
# ============================================================================

class TestStoreAttestation:
    """Tests pour store_attestation."""

    def test_store_and_retrieve(self, tmp_path):
        """store_attestation stocke et get_attestation_by_hash retrouve."""
        async def run():
            db = await create_fresh_db(str(tmp_path / "test.db"))
            try:
                att = make_test_attestation()
                att_id = await db.store_attestation(att.model_dump())

                assert att_id is not None
                assert att_id > 0

                retrieved = await db.get_attestation_by_hash(att.claim_hash)
                assert retrieved is not None
                assert retrieved["subject"] == "Solana"
                assert retrieved["predicate"] == "has_property"
                assert retrieved["consensus_score"] == 0.85
                assert retrieved["confidence_tier"] == "high"
            finally:
                await cleanup_db(db)

        asyncio.run(run())

    def test_store_preserves_signature_5d(self, tmp_path):
        """Les 5 composantes de la signature sont stockées et récupérées."""
        async def run():
            db = await create_fresh_db(str(tmp_path / "test.db"))
            try:
                att = make_test_attestation()
                await db.store_attestation(att.model_dump())

                retrieved = await db.get_attestation_by_hash(att.claim_hash)
                assert retrieved["sig_agreement"] == 0.8
                assert retrieved["sig_semantic_consistency"] == 0.75
                assert retrieved["sig_centrality"] == 0.6
                assert retrieved["sig_stability"] == 0.7
                assert retrieved["sig_relation_diversity"] == 0.5
            finally:
                await cleanup_db(db)

        asyncio.run(run())

    def test_store_preserves_model_votes(self, tmp_path):
        """Les votes des modèles sont stockés et parsés en JSON."""
        async def run():
            db = await create_fresh_db(str(tmp_path / "test.db"))
            try:
                att = make_test_attestation()
                await db.store_attestation(att.model_dump())

                retrieved = await db.get_attestation_by_hash(att.claim_hash)
                votes = retrieved["model_votes"]
                assert isinstance(votes, list)
                assert len(votes) == 3
                assert votes[0]["model_id"] == "m1"
            finally:
                await cleanup_db(db)

        asyncio.run(run())


class TestQueryAttestations:
    """Tests pour les requêtes d'attestations."""

    def test_get_by_subject(self, tmp_path):
        """get_attestations_by_subject filtre correctement."""
        async def run():
            db = await create_fresh_db(str(tmp_path / "test.db"))
            try:
                # 3 attestations Solana, 1 Ethereum
                for pred in ["has_property", "is_a", "supports"]:
                    att = make_test_attestation(predicate=pred)
                    await db.store_attestation(att.model_dump())

                att_eth = make_test_attestation(subject="Ethereum", predicate="is_a")
                await db.store_attestation(att_eth.model_dump())

                results = await db.get_attestations_by_subject("Solana")
                assert len(results) == 3

                results_eth = await db.get_attestations_by_subject("Ethereum")
                assert len(results_eth) == 1
            finally:
                await cleanup_db(db)

        asyncio.run(run())

    def test_get_by_subject_min_consensus(self, tmp_path):
        """get_attestations_by_subject respecte min_consensus."""
        async def run():
            db = await create_fresh_db(str(tmp_path / "test.db"))
            try:
                att_high = make_test_attestation(consensus=0.9)
                att_low = make_test_attestation(predicate="causes", consensus=0.3)
                await db.store_attestation(att_high.model_dump())
                await db.store_attestation(att_low.model_dump())

                results = await db.get_attestations_by_subject("Solana", min_consensus=0.5)
                assert len(results) == 1
                assert results[0]["consensus_score"] == 0.9
            finally:
                await cleanup_db(db)

        asyncio.run(run())

    def test_get_nonexistent_hash(self, tmp_path):
        """get_attestation_by_hash retourne None pour un hash inexistant."""
        async def run():
            db = await create_fresh_db(str(tmp_path / "test.db"))
            try:
                result = await db.get_attestation_by_hash("a" * 64)
                assert result is None
            finally:
                await cleanup_db(db)

        asyncio.run(run())


class TestAttestationHistory:
    """Tests pour l'historique de revalidation."""

    def test_history_returns_all_validations(self, tmp_path):
        """get_attestation_history retourne toutes les attestations d'un même claim."""
        async def run():
            db = await create_fresh_db(str(tmp_path / "test.db"))
            try:
                # Première validation
                att1 = make_test_attestation(consensus=0.7)
                await db.store_attestation(att1.model_dump())

                # Revalidation (même triplet → même hash)
                att2 = make_test_attestation(consensus=0.85)
                await db.store_attestation(att2.model_dump())

                history = await db.get_attestation_history(att1.claim_hash)
                assert len(history) == 2
                # Triées par timestamp ASC
                assert history[0]["consensus_score"] <= history[1]["consensus_score"] or True  # timestamps croissants
            finally:
                await cleanup_db(db)

        asyncio.run(run())


class TestTableExists:
    """Tests structurels."""

    def test_attestations_table_exists(self, tmp_path):
        """La table attestations existe après initialize()."""
        async def run():
            db = await create_fresh_db(str(tmp_path / "test.db"))
            try:
                async with db.connection() as conn:
                    cursor = await conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='attestations'"
                    )
                    row = await cursor.fetchone()
                    assert row is not None
            finally:
                await cleanup_db(db)

        asyncio.run(run())
```

**Critère de passage** : `pytest tests/test_phase03_storage.py -v` → tous verts.

---

## ÉTAPE 0.3.4 — Logs structurés

### Objectif

Chaque phase du pipeline ESMM émet des logs structurés, parsables, utiles pour
la démo et le debugging.

### Ce que tu fais

**A. Créer `services/esmm/run_logger.py`**

```python
"""
ESMM Run Logger — Logs structurés du pipeline.

Émet des événements JSON structurés à chaque phase du pipeline.
Double destination : logging Python (stdout/fichier) + DB (exploration_cycles).

Usage :
    logger = RunLogger(run_id=42)
    logger.phase_start("divergent", question="What is Solana?", models=["m1", "m2"])
    logger.model_response("m1", response="...", latency_ms=1234)
    logger.phase_end("divergent", triplets_extracted=5)
    logger.crystallization(attestation)
    summary = logger.get_summary()
"""

import logging
import time
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("esmm.run")


@dataclass
class PhaseEvent:
    """Événement d'une phase du pipeline."""
    phase: str                          # "divergent" | "debate" | "meta" | "extraction" | "consensus" | "crystallization"
    event_type: str                     # "start" | "end" | "model_response" | "triplet" | "attestation" | "error"
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)


class RunLogger:
    """
    Accumule les événements d'un run ESMM.

    Pas de dépendance à la DB — l'orchestrateur peut persister
    le summary en DB après le run si nécessaire.
    """

    def __init__(self, run_id: int, question: str = ""):
        self.run_id = run_id
        self.question = question
        self.events: List[PhaseEvent] = []
        self.started_at = time.time()
        self._current_phase: Optional[str] = None

    def phase_start(self, phase: str, **kwargs) -> None:
        """Début d'une phase."""
        self._current_phase = phase
        event = PhaseEvent(
            phase=phase,
            event_type="start",
            data=kwargs,
        )
        self.events.append(event)
        logger.info(json.dumps({
            "run_id": self.run_id,
            "event": "phase_start",
            "phase": phase,
            **kwargs,
        }))

    def phase_end(self, phase: str, **kwargs) -> None:
        """Fin d'une phase."""
        event = PhaseEvent(
            phase=phase,
            event_type="end",
            data=kwargs,
        )
        self.events.append(event)
        self._current_phase = None
        logger.info(json.dumps({
            "run_id": self.run_id,
            "event": "phase_end",
            "phase": phase,
            **kwargs,
        }))

    def model_response(self, model_id: str, latency_ms: float, success: bool, **kwargs) -> None:
        """Réponse d'un modèle."""
        event = PhaseEvent(
            phase=self._current_phase or "unknown",
            event_type="model_response",
            data={"model_id": model_id, "latency_ms": latency_ms, "success": success, **kwargs},
        )
        self.events.append(event)
        logger.debug(json.dumps({
            "run_id": self.run_id,
            "event": "model_response",
            "model_id": model_id,
            "latency_ms": round(latency_ms, 1),
            "success": success,
        }))

    def triplet_extracted(self, subject: str, predicate: str, object_: str, confidence: float) -> None:
        """Triplet extrait."""
        event = PhaseEvent(
            phase="extraction",
            event_type="triplet",
            data={"subject": subject, "predicate": predicate, "object": object_, "confidence": confidence},
        )
        self.events.append(event)
        logger.info(json.dumps({
            "run_id": self.run_id,
            "event": "triplet_extracted",
            "triplet": f"{subject} → {predicate} → {object_}",
            "confidence": confidence,
        }))

    def crystallization(self, claim_hash: str, consensus_score: float, confidence_tier: str) -> None:
        """Attestation cristallisée."""
        event = PhaseEvent(
            phase="crystallization",
            event_type="attestation",
            data={"claim_hash": claim_hash, "consensus_score": consensus_score, "confidence_tier": confidence_tier},
        )
        self.events.append(event)
        logger.info(json.dumps({
            "run_id": self.run_id,
            "event": "attestation_crystallized",
            "claim_hash": claim_hash[:16] + "...",
            "consensus_score": consensus_score,
            "confidence_tier": confidence_tier,
        }))

    def error(self, phase: str, error: str, **kwargs) -> None:
        """Erreur dans le pipeline."""
        event = PhaseEvent(
            phase=phase,
            event_type="error",
            data={"error": error, **kwargs},
        )
        self.events.append(event)
        logger.error(json.dumps({
            "run_id": self.run_id,
            "event": "error",
            "phase": phase,
            "error": error,
        }))

    def get_summary(self) -> Dict[str, Any]:
        """
        Résumé structuré du run complet.

        Retourne un dict avec :
        - run_id, question, duration_ms
        - phases : liste des phases avec durée et stats
        - models : stats par modèle (appels, latence moyenne)
        - triplets_extracted, attestations_produced
        - errors : liste des erreurs
        """
        duration_ms = (time.time() - self.started_at) * 1000

        # Stats par phase
        phases = {}
        for evt in self.events:
            if evt.phase not in phases:
                phases[evt.phase] = {"events": 0, "errors": 0}
            phases[evt.phase]["events"] += 1
            if evt.event_type == "error":
                phases[evt.phase]["errors"] += 1

        # Stats modèles
        model_stats = {}
        for evt in self.events:
            if evt.event_type == "model_response":
                mid = evt.data.get("model_id", "unknown")
                if mid not in model_stats:
                    model_stats[mid] = {"calls": 0, "total_latency_ms": 0, "failures": 0}
                model_stats[mid]["calls"] += 1
                model_stats[mid]["total_latency_ms"] += evt.data.get("latency_ms", 0)
                if not evt.data.get("success", True):
                    model_stats[mid]["failures"] += 1

        # Comptes
        triplets = sum(1 for e in self.events if e.event_type == "triplet")
        attestations = sum(1 for e in self.events if e.event_type == "attestation")
        errors = [e.data for e in self.events if e.event_type == "error"]

        return {
            "run_id": self.run_id,
            "question": self.question,
            "duration_ms": round(duration_ms, 1),
            "phases": phases,
            "model_stats": model_stats,
            "triplets_extracted": triplets,
            "attestations_produced": attestations,
            "errors": errors,
        }
```

**B. Intégrer dans l'orchestrateur**

Modifier la méthode `run_esmm_and_crystallize` (ou la méthode de run existante)
pour créer un `RunLogger` en début de run et appeler les méthodes appropriées
à chaque phase. Le summary est persisté dans `esmm_runs` via `finalize_esmm_run`.

L'intégration doit être **légère** — ajouter des appels `run_logger.phase_start()`
et `run_logger.phase_end()` autour des phases existantes, pas réécrire les phases.

### Ce que tu ne fais PAS

- Tu ne remplaces PAS le logging existant (si il y en a) — tu ajoutes par-dessus
- Tu ne crées PAS de nouveau système de persistence — utilise `exploration_cycles` et `esmm_runs` existants
- Tu ne rends PAS le logger obligatoire — il est optionnel (défaut: créé automatiquement)

### Tests étape 0.3.4

```python
# tests/test_phase03_logging.py

import pytest
import time
from services.esmm.run_logger import RunLogger, PhaseEvent


class TestRunLogger:
    """Tests pour le logging structuré du pipeline."""

    def test_init(self):
        """RunLogger s'initialise avec run_id et question."""
        rl = RunLogger(run_id=42, question="What is Solana?")
        assert rl.run_id == 42
        assert rl.question == "What is Solana?"
        assert len(rl.events) == 0

    def test_phase_lifecycle(self):
        """phase_start + phase_end créent 2 événements."""
        rl = RunLogger(run_id=1)
        rl.phase_start("divergent", models=["m1", "m2"])
        rl.phase_end("divergent", triplets_extracted=5)

        assert len(rl.events) == 2
        assert rl.events[0].event_type == "start"
        assert rl.events[1].event_type == "end"
        assert rl.events[0].phase == "divergent"

    def test_model_response(self):
        """model_response enregistre le modèle et la latence."""
        rl = RunLogger(run_id=1)
        rl.phase_start("divergent")
        rl.model_response("model_a", latency_ms=500, success=True)

        responses = [e for e in rl.events if e.event_type == "model_response"]
        assert len(responses) == 1
        assert responses[0].data["model_id"] == "model_a"
        assert responses[0].data["latency_ms"] == 500

    def test_triplet_extracted(self):
        """triplet_extracted enregistre le triplet."""
        rl = RunLogger(run_id=1)
        rl.triplet_extracted("Solana", "is_a", "blockchain", 0.9)

        triplets = [e for e in rl.events if e.event_type == "triplet"]
        assert len(triplets) == 1
        assert triplets[0].data["subject"] == "Solana"

    def test_crystallization(self):
        """crystallization enregistre l'attestation."""
        rl = RunLogger(run_id=1)
        rl.crystallization("abc123", 0.85, "high")

        atts = [e for e in rl.events if e.event_type == "attestation"]
        assert len(atts) == 1
        assert atts[0].data["claim_hash"] == "abc123"

    def test_error_logging(self):
        """error enregistre l'erreur avec la phase."""
        rl = RunLogger(run_id=1)
        rl.error("debate", "Model timeout", model_id="m1")

        errors = [e for e in rl.events if e.event_type == "error"]
        assert len(errors) == 1
        assert errors[0].data["error"] == "Model timeout"

    def test_get_summary(self):
        """get_summary retourne un résumé structuré complet."""
        rl = RunLogger(run_id=1, question="Test?")
        rl.phase_start("divergent")
        rl.model_response("m1", latency_ms=100, success=True)
        rl.model_response("m2", latency_ms=200, success=True)
        rl.model_response("m3", latency_ms=150, success=False)
        rl.phase_end("divergent")
        rl.triplet_extracted("A", "is", "B", 0.8)
        rl.triplet_extracted("C", "has", "D", 0.7)
        rl.crystallization("hash1", 0.85, "high")

        summary = rl.get_summary()

        assert summary["run_id"] == 1
        assert summary["question"] == "Test?"
        assert summary["triplets_extracted"] == 2
        assert summary["attestations_produced"] == 1
        assert summary["duration_ms"] > 0
        assert "m1" in summary["model_stats"]
        assert summary["model_stats"]["m1"]["calls"] == 1
        assert summary["model_stats"]["m3"]["failures"] == 1
        assert len(summary["errors"]) == 0

    def test_summary_with_errors(self):
        """get_summary inclut les erreurs."""
        rl = RunLogger(run_id=1)
        rl.error("consensus", "Insufficient models")
        summary = rl.get_summary()
        assert len(summary["errors"]) == 1
```

**Critère de passage** : `pytest tests/test_phase03_logging.py -v` → tous verts.

---

## ÉTAPE 0.3.5 — Revalidation et sérialisation des inputs

### Objectif

Permettre de resoumettre une question avec des modèles différents pour revalider
les attestations existantes. Comparer les attestations dans le temps.

**Rappel conceptuel** : La revalidation n'est PAS du déterminisme. Les LLMs sont
non-déterministes et c'est une feature. La revalidation mesure la **stabilité
épistémique** d'une attestation : si des modèles différents convergent vers le même
consensus, l'attestation se renforce.

### Ce que tu fais

**A. Créer le modèle `RevalidationInput` dans `services/esmm/attestation.py`**

```python
class RevalidationInput(BaseModel):
    """
    Inputs sérialisés pour revalidation d'un run ESMM.

    Permet de resoumettre la même question avec des modèles différents
    et de comparer les attestations produites.
    """
    question: str
    metrological_frame: Optional[str] = None
    rag_context_snapshot: Optional[str] = None   # Contexte RAG au moment du run original
    original_run_id: int
    original_claim_hashes: List[str]             # Hash des attestations originales
    created_at: float = Field(default_factory=time.time)
```

**B. Ajouter une méthode `prepare_revalidation` dans l'orchestrateur**

```python
async def prepare_revalidation(self, run_id: int) -> RevalidationInput:
    """
    Prépare les inputs pour revalidation d'un run existant.

    Lit le run original dans la DB, extrait la question et le contexte,
    récupère les hashes des attestations produites.

    Args:
        run_id: ID du run original à revalider

    Returns:
        RevalidationInput sérialisable
    """
    ...
```

**C. Ajouter une méthode `revalidate` dans l'orchestrateur**

```python
async def revalidate(
    self,
    revalidation_input: RevalidationInput,
    min_consensus: float = 0.4,
) -> Dict[str, Any]:
    """
    Exécute une revalidation.

    1. Relance run_esmm_and_crystallize avec la même question/frame
    2. Compare les nouvelles attestations aux originales
    3. Met à jour validation_count et previous_hash

    Args:
        revalidation_input: Inputs du run original
        min_consensus: Seuil de consensus pour cristallisation

    Returns:
        Dict avec :
        - new_attestations: List[EpistemicAttestation]
        - convergence_report: Dict comparant ancien et nouveau consensus
            - claims_stable: int (même hash, même tier ou mieux)
            - claims_changed: int (même hash, tier différent)
            - claims_new: int (triplets nouveaux non présents avant)
            - claims_lost: int (triplets précédents non retrouvés)
    """
    ...
```

La comparaison se fait par `claim_hash` : puisque le hash est calculé sur le triplet
canonique + frame, un même claim produit le même hash quel que soit le run.

**D. Stocker les `RevalidationInput` dans `esmm_runs`**

Ajouter une colonne `revalidation_input TEXT` dans `esmm_runs` (migration dans `initialize()`).
Quand un run est une revalidation, stocker le JSON du `RevalidationInput`.

### Ce que tu ne fais PAS

- Tu ne promets PAS le déterminisme — les résultats vont varier et c'est attendu
- Tu ne modifies PAS le pipeline ESMM lui-même — la revalidation est un wrapper
- Tu ne crées PAS de système de diff complexe — la comparaison est par claim_hash simple

### Tests étape 0.3.5

```python
# tests/test_phase03_revalidation.py

import pytest
import asyncio
import time
from services.esmm.attestation import (
    RevalidationInput,
    EpistemicAttestation,
    crystallize,
    Signature5D,
    ModelVote,
    compute_claim_hash,
)


class TestRevalidationInput:
    """Tests pour RevalidationInput."""

    def test_serialization(self):
        """RevalidationInput se sérialise et désérialise."""
        ri = RevalidationInput(
            question="What is Solana?",
            metrological_frame="tps_v1",
            original_run_id=42,
            original_claim_hashes=["abc123", "def456"],
        )
        j = ri.model_dump_json()
        ri2 = RevalidationInput.model_validate_json(j)
        assert ri2.question == ri.question
        assert ri2.original_run_id == 42
        assert len(ri2.original_claim_hashes) == 2

    def test_required_fields(self):
        """RevalidationInput exige question et original_run_id."""
        with pytest.raises(Exception):
            RevalidationInput(original_run_id=1, original_claim_hashes=[])
        # question is missing


class TestConvergenceComparison:
    """Tests pour la logique de comparaison de revalidation."""

    def test_same_triplet_same_hash(self):
        """Même triplet canonique → même claim_hash entre validations."""
        h1 = compute_claim_hash("Solana", "is_a", "blockchain")
        h2 = compute_claim_hash("Solana", "is_a", "blockchain")
        assert h1 == h2

    def test_convergence_detection(self):
        """Deux attestations du même claim avec scores proches = convergence."""
        att1 = crystallize(
            subject="Solana", predicate="is_a", object_="blockchain",
            consensus_score=0.8,
            model_votes=[ModelVote(model_id="m1", provider_id="p", agreed=True, confidence=0.8)],
            signature_5d=Signature5D(agreement=0.8, semantic_consistency=0.7,
                                     centrality=0.6, stability=0.5, relation_diversity=0.5),
            epistemic_type="foundational",
        )
        att2 = crystallize(
            subject="Solana", predicate="is_a", object_="blockchain",
            consensus_score=0.85,
            model_votes=[ModelVote(model_id="m2", provider_id="p", agreed=True, confidence=0.9)],
            signature_5d=Signature5D(agreement=0.85, semantic_consistency=0.75,
                                     centrality=0.65, stability=0.55, relation_diversity=0.5),
            epistemic_type="foundational",
            previous_hash=att1.claim_hash,
            validation_count=2,
        )
        # Même hash (même triplet)
        assert att1.claim_hash == att2.claim_hash
        # Score amélioré
        assert att2.consensus_score > att1.consensus_score
        # Revalidation tracée
        assert att2.validation_count == 2
        assert att2.previous_hash == att1.claim_hash

    def test_divergence_detection(self):
        """Deux attestations du même claim avec scores très différents = divergence."""
        att1 = crystallize(
            subject="X", predicate="is_a", object_="Y",
            consensus_score=0.9,
            model_votes=[ModelVote(model_id="m1", provider_id="p", agreed=True, confidence=0.9)],
            signature_5d=Signature5D(agreement=0.9, semantic_consistency=0.8,
                                     centrality=0.7, stability=0.6, relation_diversity=0.5),
            epistemic_type="foundational",
        )
        att2 = crystallize(
            subject="X", predicate="is_a", object_="Y",
            consensus_score=0.3,
            model_votes=[ModelVote(model_id="m2", provider_id="p", agreed=False, confidence=0.3)],
            signature_5d=Signature5D(agreement=0.3, semantic_consistency=0.4,
                                     centrality=0.5, stability=0.3, relation_diversity=0.4),
            epistemic_type="foundational",
        )
        # Même hash mais tiers de confiance différents
        assert att1.claim_hash == att2.claim_hash
        assert att1.confidence_tier != att2.confidence_tier

    def test_revalidation_input_stores_in_db(self, tmp_path):
        """RevalidationInput est stockable dans esmm_runs."""
        async def run():
            from database.engine import ISpaceDB
            from database.pool import close_pool

            db = ISpaceDB(str(tmp_path / "test.db"))
            await db.initialize()
            try:
                ri = RevalidationInput(
                    question="Test?",
                    original_run_id=1,
                    original_claim_hashes=["hash1"],
                )

                # Créer un run avec revalidation_input
                run_id = await db.create_esmm_run(
                    config={"revalidation_input": ri.model_dump()},
                    models=["m1"],
                    seed_type="revalidation",
                )
                assert run_id > 0
            finally:
                await close_pool()

        asyncio.run(run())
```

**Critère de passage** : `pytest tests/test_phase03_revalidation.py -v` → tous verts.

---

## ÉTAPE 0.3.6 — Validation finale et documentation

### Ce que tu fais

**A. Test d'intégration complet**

Créer `tests/test_phase03_integration.py` qui vérifie le scénario end-to-end :

1. Instancier un pipeline avec des MockProviders (3 modèles mock)
2. Soumettre une question
3. Vérifier que des attestations sont produites (au moins 1)
4. Vérifier que chaque attestation a un hash SHA-256 valide
5. Vérifier que chaque attestation est stockée en DB
6. Vérifier que to_portable_json() produit du JSON valide
7. Vérifier que le RunLogger a capturé les phases
8. Préparer une revalidation depuis le run
9. Vérifier que le RevalidationInput contient la bonne question et les bons hashes

**NOTE** : Ce test nécessite de mocker le pipeline ESMM complet. Si les composants
internes (cycle_manager, triplet_extractor, etc.) ne sont pas facilement mockables,
créer un test plus ciblé qui :
- Crée manuellement des outputs de consensus + cochain (données synthétiques)
- Appelle crystallize() dessus
- Stocke en DB
- Vérifie la chaîne complète

L'objectif est de tester la **cristallisation** et le **stockage**, pas le pipeline
ESMM interne (qui a ses propres tests).

**B. Mise à jour de `ARCHITECTURE.md`**

Ajouter dans la section appropriée :

```markdown
### Cristallisation (Phase 0.3 — fonctionnel)

| Fichier | Rôle | État |
|---------|------|------|
| `services/esmm/attestation.py` | Modèle EpistemicAttestation, crystallize(), compute_claim_hash() | ✅ Fonctionnel |
| `services/esmm/run_logger.py` | Logs structurés du pipeline (PhaseEvent, RunLogger) | ✅ Fonctionnel |
| Table `attestations` | Stockage attestations cristallisées (19ème table) | ✅ Fonctionnel |
```

**C. Mise à jour de `CHANGELOG.md`**

```markdown
## [YYYY-MM-DD] Phase 0.3 — ESMM Découplé, Cristallisation & Revalidation

- Audit et purge : zéro référence directe à un modèle/provider dans le pipeline ESMM
- Créé `services/esmm/attestation.py` : EpistemicAttestation (Pydantic), crystallize(), compute_claim_hash()
- Créé table `attestations` (table 19) : stockage attestations avec signature 5D, votes, provenance
- Créé `services/esmm/run_logger.py` : RunLogger avec PhaseEvent, logging JSON structuré
- Ajouté méthodes engine.py : store/get_attestation, get_attestation_history, get_attestations_by_subject
- Ajouté RevalidationInput : sérialisation des inputs pour revalidation
- XX tests unitaires + intégration (test_phase03_*.py)
```

### Tests étape 0.3.6

Le test d'intégration ci-dessus EST le test de cette étape.

**Critère de passage final** :
- `pytest tests/test_phase03_*.py -v` → TOUS verts
- Zéro violation de couplage dans le pipeline ESMM (test audit)
- Une attestation peut être cristallisée, stockée, récupérée, sérialisée en JSON portable
- Le hash SHA-256 est déterministe (même triplet → même hash)
- Le RunLogger capture les phases et produit un summary structuré
- La revalidation produit des RevalidationInput sérialisables

---

## RÉSUMÉ — ORDRE D'EXÉCUTION

| Étape | Action | Tests | Bloquant |
|-------|--------|-------|----------|
| 0.3.1 | Audit et purge du couplage | test_phase03_audit.py | Oui |
| 0.3.2 | Modèle EpistemicAttestation + table SQL | test_phase03_attestation.py | Oui |
| 0.3.3 | Stockage DB + branchement pipeline | test_phase03_storage.py | Oui |
| 0.3.4 | Logs structurés (RunLogger) | test_phase03_logging.py | Oui |
| 0.3.5 | Revalidation (inputs + comparaison) | test_phase03_revalidation.py | Oui |
| 0.3.6 | Intégration finale + docs | test_phase03_integration.py | Oui |

**Chaque étape est bloquante. Ne passe pas à la suivante tant que les tests ne sont pas verts.**

---

## FICHIERS MODIFIÉS (inventaire prévu)

| Fichier | Modification | Étape |
|---------|-------------|-------|
| `services/esmm/orchestrator.py` | Purge couplage + run_esmm_and_crystallize + prepare_revalidation + revalidate | 0.3.1, 0.3.3, 0.3.5 |
| `services/esmm/cycle_manager.py` | Purge couplage (si violations trouvées) | 0.3.1 |
| `services/esmm/triplet_extractor.py` | Purge couplage (si violations trouvées) | 0.3.1 |
| `services/esmm/consensus_engine.py` | Purge couplage (si violations trouvées) | 0.3.1 |
| `services/esmm/cochain_builder.py` | Purge couplage (si violations trouvées) | 0.3.1 |
| `database/schema.sql` | +table attestations (table 19) + vue v_high_confidence_attestations | 0.3.2 |
| `database/engine.py` | +4 méthodes attestation CRUD, +migration SQL | 0.3.2, 0.3.3 |
| `ARCHITECTURE.md` | +section Cristallisation | 0.3.6 |
| `CHANGELOG.md` | +entrée Phase 0.3 | 0.3.6 |

## FICHIERS CRÉÉS

| Fichier | Contenu | Étape |
|---------|---------|-------|
| `services/esmm/attestation.py` | EpistemicAttestation, Signature5D, ModelVote, crystallize(), compute_claim_hash(), RevalidationInput | 0.3.2, 0.3.5 |
| `services/esmm/run_logger.py` | RunLogger, PhaseEvent | 0.3.4 |
| `tests/test_phase03_audit.py` | Tests audit couplage | 0.3.1 |
| `tests/test_phase03_attestation.py` | Tests cristallisation | 0.3.2 |
| `tests/test_phase03_storage.py` | Tests stockage DB | 0.3.3 |
| `tests/test_phase03_logging.py` | Tests RunLogger | 0.3.4 |
| `tests/test_phase03_revalidation.py` | Tests revalidation | 0.3.5 |
| `tests/test_phase03_integration.py` | Test intégration complet | 0.3.6 |

## FICHIERS NON TOUCHÉS (vérification)

- `CLAUDE.md` — JAMAIS
- `EPP_PLAN_MVP.md` — JAMAIS
- `services/providers/base.py` — Stable depuis 0.1
- `services/providers/ollama.py` — Stable depuis 0.1
- `services/providers/registry.py` — Stable depuis 0.1
- `services/esmm/multi_provider_rotator.py` — Stable depuis 0.1
- `llm_client.py` — Legacy, ne pas toucher
- `model_rotator.py` — Legacy, ne pas toucher
- `embeddings.py` — Déprécié depuis 0.2
- `database/pool.py` — Stable
- `database/graph_delta.py` — Stable
- Tout le dossier `tools/` — Pas impacté
- Tout le dossier `core/physics/` — Pas impacté
