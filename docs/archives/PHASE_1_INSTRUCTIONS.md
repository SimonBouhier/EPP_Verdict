# PHASE 1 — PREUVE ON-CHAIN (Semaines 4-6)

> **Instructions pour Claude Code.** Lis CLAUDE.md ET ce fichier avant chaque étape.
> Ce document est ta feuille de route pour la Phase 1. Tu exécutes dans l'ordre, étape par étape.
> **Tu ne passes PAS à l'étape suivante tant que les tests de l'étape courante ne passent pas tous.**
>
> **ZONE CRITIQUE SÉCURITÉ** : Cette phase touche à Solana et à la sérialisation de données
> destinées à la blockchain. Tout le code Rust (Anchor) et le bridge de sérialisation Python ↔ Anchor
> sont marqués `// AUDIT_REQUIRED` ou `# AUDIT_REQUIRED`. Un développeur Solana humain compétent
> devra auditer ces zones AVANT tout déploiement mainnet. Le devnet est un bac à sable expérimental.

---

## CONTEXTE

La Phase 0 (0.1 + 0.2 + 0.3) a posé les fondations :
- **0.1** : Abstraction des providers (ModelProvider/EmbeddingProvider), rotation multi-provider (55 tests)
- **0.2** : Versioning des embeddings, migration sans perte (45 tests)
- **0.3** : Cristallisation des attestations — `EpistemicAttestation`, `crystallize()`, `compute_claim_hash()`,
  `RunLogger`, stockage DB, revalidation (65 tests)

**Ce qui existe** :
- `attestation.py` : `EpistemicAttestation` (Pydantic), `to_portable_json()`, `to_compact_dict()`
- `engine.py` : `store_attestation()`, `get_attestation_by_hash()`, `get_attestations_by_subject()`, `get_attestation_history()`
- Table `attestations` : 19ème table SQLite, champs `solana_tx_signature`, `solana_slot`, `anchored_at` (NULL, prêts)
- Hash SHA-256 déterministe via `compute_claim_hash()`

**Ce qui manque** :
1. **Référentiels métrologiques** — Pas de modèle Python pour `MetrologicalFrame`
2. **Programme Solana** — Aucun code Anchor/Rust
3. **Bridge de sérialisation** — Pas de conversion Python `EpistemicAttestation` → format on-chain
4. **Client Solana** — Pas de code pour signer/envoyer des transactions
5. **CLI** — Pas de commandes `epp ask`, `epp submit`, `epp query`

**Objectif Phase 1** : Soumettre une question, débattre localement (ESMM), poster l'attestation résultante
sur le devnet Solana, et la relire depuis un programme tiers.

**Critère de validation final** : `epp ask "Solana effective TPS exceeds 3000" --models 3 --frame tps_v1`
→ débat visible → `epp submit --devnet` → attestation on-chain → `epp query "Solana" --min-confidence 0.8`
→ résultat affiché avec lien explorer devnet.

---

## DÉCISIONS ARCHITECTURALES FIGÉES

Ces décisions sont prises. Ne les remets pas en question pendant l'implémentation.

### D1 — PDA Seeds

```
seeds = [b"attestation", submitter.key().as_ref(), &claim_hash]
```

**Justification** : Un même claim peut être attesté par plusieurs submitters (LLMs, opérateurs).
Cela permet l'audit par submitter, la détection de consensus/controverse entre opérateurs,
et l'évolution des jugements dans le temps.

**Extension future (Phase 3+)** : Ajout d'un nonce pour multi-version par submitter :
`[b"attestation", submitter, claim_hash, &nonce.to_le_bytes()]`

### D2 — Client Python

Stack principal : **solders** + **anchorpy** (consomme l'IDL Anchor).
Si anchorpy pose des problèmes de compatibilité, fallback vers solders + borsh manuel.
Pas de TypeScript dans le MVP.

### D3 — Struct on-chain optimisé

Tableaux à taille fixe (`[u8; N]`), pas de `String`. Les floats [0,1] sont encodés en `u16` [0, 10000].
Le détail complet (model_votes, portable_json) reste off-chain dans SQLite.
L'on-chain est compact : ~430 bytes par attestation ≈ 0.003 SOL de rent.

### D4 — Challenge = contre-attestation (MVP)

Pour le MVP, un challenge est simplement une nouvelle attestation avec le même `claim_hash`
mais un `submitter` différent (ou le même submitter en revalidation).
Le struct porte un champ `is_challenge: bool` et `challenged_attestation: Option<Pubkey>`.
La logique de stake/arbitrage/slashing est documentée mais **non implémentée** — marquée
`// FUTURE: stake mechanism — see PHASE_3_DESIGN.md`.

### D5 — Devnet-only guard

Le client Python refuse catégoriquement d'envoyer des transactions au mainnet.
Un guard explicite vérifie le cluster URL à chaque appel.
Commentaire permanent : `# AUDIT_REQUIRED: Remove devnet guard only after security audit`.

### D6 — Ressource Claude Code

Claude Code a accès au skill `solana-dev-skill` (Solana Foundation) dans `.claude/skills/solana`.
**Consulte ce skill AVANT d'écrire du code Anchor.** Il contient les patterns Anchor à jour.

---

## AXIOMES À RESPECTER (rappel — violations = refus du code)

1. **Obsolescence permanente des modèles** — Aucun nom de modèle ou provider dans le code Solana
   ou le bridge. Le programme Anchor ne sait pas ce qu'est un LLM. Il stocke des attestations.

2. **Le graphe survit à tout** — L'ancrage on-chain est une projection compacte.
   La source de vérité complète reste dans SQLite (avec model_votes, portable_json, etc.).
   Le on-chain est un engagement cryptographique, pas une copie intégrale.

3. **Transparence des coupures** — Le `claim_hash` lie le on-chain au off-chain.
   Le `frame_hash` lie l'attestation à son référentiel. Tout est vérifiable.

4. **Calcul local, preuve on-chain** — Le moteur ESMM tourne off-chain.
   Seul le résultat cristallisé (compact, hashé) est posté on-chain.

5. **Defense in depth pour la sécurité** — Devnet-only. Marqueurs AUDIT_REQUIRED partout.
   Aucune keypair en dur dans le code. Aucun secret dans le repo.

---

## STRUCTURE DE FICHIERS CIBLE

```
epp_verdict/                          # Racine du projet existant
│
├── services/
│   ├── esmm/                         # ✅ Existant (Phase 0)
│   │   ├── attestation.py            # ✅ EpistemicAttestation, crystallize()
│   │   └── run_logger.py             # ✅ RunLogger
│   │
│   ├── providers/                    # ✅ Existant (Phase 0.1)
│   │
│   └── solana/                       # 🆕 NOUVEAU — Phase 1
│       ├── __init__.py
│       ├── config.py                 # Cluster URL, devnet guard, keypair path
│       ├── bridge.py                 # Sérialisation Python ↔ Anchor (AUDIT_REQUIRED)
│       ├── client.py                 # Transaction builder & submitter (AUDIT_REQUIRED)
│       └── metrological_frame.py     # MetrologicalFrame Pydantic + compute_frame_hash()
│
├── programs/                         # 🆕 NOUVEAU — Workspace Anchor
│   └── epp/                          # Programme Anchor (Rust)
│       ├── Anchor.toml
│       ├── Cargo.toml
│       ├── programs/
│       │   └── epp/
│       │       ├── Cargo.toml
│       │       └── src/
│       │           ├── lib.rs        # Point d'entrée, instructions (AUDIT_REQUIRED)
│       │           ├── state.rs      # Structs des comptes (AUDIT_REQUIRED)
│       │           ├── errors.rs     # Codes d'erreur custom
│       │           └── constants.rs  # Tailles, limites
│       └── tests/                    # Tests Anchor (TypeScript minimal)
│           └── epp.ts
│
├── cli/                              # 🆕 NOUVEAU — CLI EPP
│   ├── __init__.py
│   └── epp_cli.py                    # Commandes ask, submit, query, graph
│
├── tests/
│   ├── test_phase03_*.py             # ✅ Existants
│   ├── test_phase1_frame.py          # 🆕 Tests MetrologicalFrame
│   ├── test_phase1_bridge.py         # 🆕 Tests sérialisation bridge
│   ├── test_phase1_client.py         # 🆕 Tests client (mock + localnet)
│   ├── test_phase1_cli.py            # 🆕 Tests CLI
│   └── test_phase1_integration.py    # 🆕 Tests end-to-end (localnet)
│
└── PHASE_1_INSTRUCTIONS.md           # Ce fichier
```

---

## ÉTAPE 1.0 — Référentiels métrologiques

### Objectif

Créer le modèle `MetrologicalFrame` (Pydantic) qui formalise ce qu'on mesure et comment.
C'est un prérequis : le `frame_hash` est un champ du PDA on-chain.

### Ce que tu fais

**A. Créer `services/solana/metrological_frame.py`**

```python
"""
Metrological Frame — Référentiel de mesure versionné.

Définit CE QU'ON MESURE et COMMENT pour un domaine spécifique.
Le hash SHA-256 du frame est ancré on-chain avec chaque attestation.
Le contenu complet du frame est stocké off-chain (SQLite + publication).

Contrat d'interface avec le programme Solana : seul le frame_hash
est transmis on-chain. Le frame complet est vérifiable off-chain.
"""

import hashlib
import json
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator


class FrameGovernance(BaseModel):
    """Gouvernance du référentiel."""
    current_authority: str = Field(
        default="founding_team",
        description="Autorité actuelle (founding_team | expert_panel | dao_vote)"
    )
    amendment_process: str = Field(
        default="version_bump_with_changelog",
        description="Processus de modification"
    )
    target_authority: str = Field(
        default="dao_vote",
        description="Autorité cible à terme"
    )


class MetrologicalFrame(BaseModel):
    """
    Référentiel métrologique versionné.

    Spécifie formellement ce qu'on mesure, comment, et avec quelles
    contraintes. Chaque attestation référence un frame par son hash.
    """
    frame_id: str = Field(
        max_length=64,
        description="Identifiant unique du frame (ex: blockchain_tps_v1.0)"
    )
    version: str = Field(
        description="Version sémantique (ex: 1.0)"
    )
    domain: str = Field(
        description="Domaine couvert (ex: blockchain_metrics, ai_benchmarks)"
    )
    metric: str = Field(
        description="Métrique principale mesurée (ex: transactions_per_second)"
    )
    description: str = Field(
        description="Description humaine du référentiel"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Paramètres spécifiques au domaine"
    )
    required_sources: int = Field(
        default=1, ge=1,
        description="Nombre minimum de sources requises"
    )
    governance: FrameGovernance = Field(
        default_factory=FrameGovernance
    )
    created_at: Optional[float] = Field(default=None)

    @field_validator("frame_id")
    @classmethod
    def validate_frame_id(cls, v: str) -> str:
        """Frame ID : alphanumérique + underscores + dots uniquement."""
        import re
        if not re.match(r'^[a-z0-9][a-z0-9_.]*$', v):
            raise ValueError(
                f"frame_id must be lowercase alphanumeric with _ and . only, got '{v}'"
            )
        return v

    def compute_frame_hash(self) -> str:
        """
        Hash SHA-256 déterministe du frame.

        Sérialise le frame en JSON canonique (sorted keys, compact separators)
        et retourne le hash hex. C'est cette valeur qui est ancrée on-chain.
        """
        # Exclure created_at de la canonicalisation (c'est du metadata temporel)
        canonical_data = self.model_dump(exclude={"created_at"})
        canonical_json = json.dumps(
            canonical_data,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def to_canonical_json(self) -> str:
        """JSON déterministe pour publication et vérification."""
        return json.dumps(
            self.model_dump(),
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
            default=str,
        )


# === FRAMES PRÉDÉFINIS (MVP) ===

def create_blockchain_tps_frame() -> MetrologicalFrame:
    """Premier référentiel concret : blockchain TPS."""
    return MetrologicalFrame(
        frame_id="blockchain_tps_v1.0",
        version="1.0",
        domain="blockchain_metrics",
        metric="transactions_per_second",
        description=(
            "Measures effective transactions per second on a blockchain network. "
            "Excludes vote transactions, counts only successful non-vote transactions "
            "over a 10-minute rolling window."
        ),
        parameters={
            "include_votes": False,
            "success_only": True,
            "window": "10min_rolling",
            "exclusions": ["downtime_gt_30s"],
            "measurement_sources": ["rpc_nodes", "block_explorers"],
            "minimum_sources": 3,
        },
        required_sources=3,
    )


def create_general_knowledge_frame() -> MetrologicalFrame:
    """Référentiel générique pour claims factuels généraux."""
    return MetrologicalFrame(
        frame_id="general_knowledge_v1.0",
        version="1.0",
        domain="general_knowledge",
        metric="factual_accuracy",
        description=(
            "General-purpose frame for factual claims. "
            "Requires claims to be verifiable against publicly available sources. "
            "Consensus is weighted by model diversity."
        ),
        parameters={
            "verification_type": "public_sources",
            "temporal_scope": "current",
            "ambiguity_handling": "flag_as_contested",
        },
        required_sources=1,
    )
```

**B. Créer `services/solana/__init__.py`**

```python
"""
Solana integration layer for EPP.

Handles:
- Metrological frames (off-chain reference, on-chain hash)
- Serialization bridge (Python EpistemicAttestation → Anchor struct)
- Transaction building and submission (devnet only)

SECURITY NOTE: All Solana-facing code is marked AUDIT_REQUIRED.
A qualified Solana developer must review before any mainnet deployment.
"""
```

**C. Créer `services/solana/config.py`**

```python
"""
Solana configuration — cluster, keypair, guards.

# AUDIT_REQUIRED: This entire module manages blockchain connectivity.
# Review devnet guard, keypair handling, and cluster validation
# before ANY mainnet consideration.
"""

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class SolanaCluster(Enum):
    """Clusters Solana supportés."""
    LOCALNET = "http://127.0.0.1:8899"
    DEVNET = "https://api.devnet.solana.com"
    # MAINNET est intentionnellement ABSENT.
    # AUDIT_REQUIRED: N'ajoutez mainnet qu'après audit de sécurité complet.


# === DEVNET GUARD ===
# AUDIT_REQUIRED: Remove this guard ONLY after full security audit.
_ALLOWED_CLUSTERS = {SolanaCluster.LOCALNET, SolanaCluster.DEVNET}


def validate_cluster(cluster: SolanaCluster) -> None:
    """
    Refuse catégoriquement tout cluster non autorisé.

    Raises:
        RuntimeError: Si le cluster n'est pas localnet ou devnet.
    """
    if cluster not in _ALLOWED_CLUSTERS:
        raise RuntimeError(
            f"SECURITY: Cluster {cluster} is NOT allowed. "
            f"EPP MVP is restricted to devnet/localnet. "
            f"Mainnet requires security audit. See AUDIT_REQUIRED markers."
        )


@dataclass
class SolanaConfig:
    """Configuration Solana pour EPP."""
    cluster: SolanaCluster = SolanaCluster.DEVNET
    keypair_path: Optional[str] = None  # None = ~/.config/solana/id.json
    program_id: Optional[str] = None     # Set after deployment
    commitment: str = "confirmed"
    timeout_seconds: int = 30

    def __post_init__(self):
        # Guard systématique
        validate_cluster(self.cluster)

        # Keypair path par défaut
        if self.keypair_path is None:
            default = Path.home() / ".config" / "solana" / "id.json"
            if default.exists():
                self.keypair_path = str(default)

    @property
    def rpc_url(self) -> str:
        return self.cluster.value

    @property
    def is_localnet(self) -> bool:
        return self.cluster == SolanaCluster.LOCALNET
```

### Tests — `tests/test_phase1_frame.py`

```python
"""Tests Phase 1.0 — Référentiels métrologiques."""

import pytest
import json
import hashlib

from services.solana.metrological_frame import (
    MetrologicalFrame,
    FrameGovernance,
    create_blockchain_tps_frame,
    create_general_knowledge_frame,
)
from services.solana.config import (
    SolanaCluster,
    SolanaConfig,
    validate_cluster,
)


class TestMetrologicalFrame:
    """Tests MetrologicalFrame."""

    def test_create_blockchain_tps_frame(self):
        """Le frame blockchain_tps_v1.0 se crée correctement."""
        frame = create_blockchain_tps_frame()
        assert frame.frame_id == "blockchain_tps_v1.0"
        assert frame.version == "1.0"
        assert frame.domain == "blockchain_metrics"
        assert frame.metric == "transactions_per_second"
        assert frame.parameters["include_votes"] is False
        assert frame.required_sources == 3

    def test_frame_hash_deterministic(self):
        """Même frame → même hash, toujours."""
        frame1 = create_blockchain_tps_frame()
        frame2 = create_blockchain_tps_frame()
        assert frame1.compute_frame_hash() == frame2.compute_frame_hash()

    def test_frame_hash_changes_with_content(self):
        """Frame différent → hash différent."""
        frame1 = create_blockchain_tps_frame()
        frame2 = create_general_knowledge_frame()
        assert frame1.compute_frame_hash() != frame2.compute_frame_hash()

    def test_frame_hash_ignores_created_at(self):
        """Le created_at ne change pas le hash (c'est du metadata)."""
        frame1 = create_blockchain_tps_frame()
        frame1.created_at = 1000.0
        frame2 = create_blockchain_tps_frame()
        frame2.created_at = 2000.0
        assert frame1.compute_frame_hash() == frame2.compute_frame_hash()

    def test_frame_hash_is_sha256(self):
        """Le hash est bien un SHA-256 hex (64 chars)."""
        frame = create_blockchain_tps_frame()
        h = frame.compute_frame_hash()
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_frame_id_validation_rejects_uppercase(self):
        """Les IDs en majuscules sont refusés."""
        with pytest.raises(ValueError, match="frame_id must be lowercase"):
            MetrologicalFrame(
                frame_id="Blockchain_TPS_v1",
                version="1.0",
                domain="test",
                metric="test",
                description="test",
            )

    def test_frame_id_validation_rejects_spaces(self):
        """Les espaces dans l'ID sont refusés."""
        with pytest.raises(ValueError):
            MetrologicalFrame(
                frame_id="blockchain tps",
                version="1.0",
                domain="test",
                metric="test",
                description="test",
            )

    def test_canonical_json_is_valid(self):
        """Le JSON canonique est parseable."""
        frame = create_blockchain_tps_frame()
        j = frame.to_canonical_json()
        parsed = json.loads(j)
        assert parsed["frame_id"] == "blockchain_tps_v1.0"

    def test_governance_defaults(self):
        """La gouvernance a des valeurs par défaut correctes."""
        frame = create_blockchain_tps_frame()
        assert frame.governance.current_authority == "founding_team"
        assert frame.governance.target_authority == "dao_vote"

    def test_frame_hash_32_bytes(self):
        """Le hash peut être converti en 32 bytes (pour le PDA on-chain)."""
        frame = create_blockchain_tps_frame()
        h = frame.compute_frame_hash()
        raw = bytes.fromhex(h)
        assert len(raw) == 32


class TestSolanaConfig:
    """Tests configuration Solana."""

    def test_devnet_allowed(self):
        """Devnet est autorisé."""
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        assert config.rpc_url == "https://api.devnet.solana.com"

    def test_localnet_allowed(self):
        """Localnet est autorisé."""
        config = SolanaConfig(cluster=SolanaCluster.LOCALNET)
        assert config.is_localnet is True

    def test_no_mainnet_enum(self):
        """MAINNET n'existe pas dans l'enum (par design)."""
        cluster_names = [c.name for c in SolanaCluster]
        assert "MAINNET" not in cluster_names
        assert "MAINNET_BETA" not in cluster_names

    def test_validate_cluster_devnet(self):
        """validate_cluster accepte devnet."""
        validate_cluster(SolanaCluster.DEVNET)  # Ne doit pas lever

    def test_config_commitment_default(self):
        """Le commitment par défaut est 'confirmed'."""
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        assert config.commitment == "confirmed"
```

**Critère de passage** : `pytest tests/test_phase1_frame.py -v` → tous verts.

---

## ÉTAPE 1.1 — Programme Anchor : struct et instruction submit

### Objectif

Créer le programme Solana (Anchor/Rust) avec la struct `EpistemicAttestation` on-chain
et l'instruction `submit_attestation`.

### Prérequis

- Solana CLI installé (`solana --version`)
- Anchor installé (`anchor --version`)
- Consulte le skill `.claude/skills/solana` AVANT d'écrire du code Rust.

### Ce que tu fais

**A. Initialiser le workspace Anchor**

```bash
cd <project_root>
mkdir -p programs
cd programs
anchor init epp --no-git
```

Vérifie que `Anchor.toml`, `Cargo.toml`, et `programs/epp/src/lib.rs` existent.

**B. Créer `programs/epp/programs/epp/src/constants.rs`**

```rust
// AUDIT_REQUIRED: All size constants affect rent costs and account validation.

/// Maximum length for subject field (UTF-8 bytes, zero-padded)
pub const MAX_SUBJECT_LEN: usize = 64;

/// Maximum length for predicate field
pub const MAX_PREDICATE_LEN: usize = 64;

/// Maximum length for object field
pub const MAX_OBJECT_LEN: usize = 128;

/// Maximum length for protocol version string
pub const MAX_PROTOCOL_VERSION_LEN: usize = 8;

/// Discriminator size (Anchor standard)
pub const DISCRIMINATOR_SIZE: usize = 8;

/// Scale factor for float→u16 conversion (0.0-1.0 → 0-10000)
pub const SCORE_SCALE: u16 = 10000;

/// PDA seed prefix
pub const ATTESTATION_SEED: &[u8] = b"attestation";

/// Challenge PDA seed prefix
pub const CHALLENGE_SEED: &[u8] = b"challenge";
```

**C. Créer `programs/epp/programs/epp/src/errors.rs`**

```rust
use anchor_lang::prelude::*;

// AUDIT_REQUIRED: Error codes must cover all validation failures.

#[error_code]
pub enum EppError {
    #[msg("Subject exceeds maximum length")]
    SubjectTooLong,

    #[msg("Predicate exceeds maximum length")]
    PredicateTooLong,

    #[msg("Object exceeds maximum length")]
    ObjectTooLong,

    #[msg("Consensus score must be between 0 and 10000")]
    InvalidConsensusScore,

    #[msg("Signature 5D values must be between 0 and 10000")]
    InvalidSignatureValue,

    #[msg("Models agreeing cannot exceed models consulted")]
    InvalidModelCount,

    #[msg("Invalid epistemic type")]
    InvalidEpistemicType,

    #[msg("Invalid confidence tier")]
    InvalidConfidenceTier,

    #[msg("Attestation already exists for this submitter and claim")]
    AttestationAlreadyExists,

    #[msg("Challenge references a non-existent attestation")]
    ChallengedAttestationNotFound,

    #[msg("Cannot challenge your own attestation")]
    SelfChallengeNotAllowed,

    // FUTURE: stake mechanism errors
    // #[msg("Insufficient stake for challenge")]
    // InsufficientStake,
}
```

**D. Créer `programs/epp/programs/epp/src/state.rs`**

```rust
use anchor_lang::prelude::*;
use crate::constants::*;

// AUDIT_REQUIRED: Account struct layout directly affects PDA derivation,
// rent costs, and data integrity. Review all field sizes and types.

/// Epistemic attestation stored on-chain.
///
/// This is the compact projection of a full EpistemicAttestation (Python/off-chain).
/// The complete data (model_votes, portable_json) lives in SQLite off-chain.
/// The claim_hash links on-chain ↔ off-chain deterministically.
///
/// PDA seeds: [b"attestation", submitter, claim_hash]
#[account]
pub struct EpistemicAttestation {
    // === PDA METADATA ===
    /// PDA bump seed
    pub bump: u8,                                // 1 byte

    // === IDENTITY ===
    /// Submitter (operator running the ESMM pipeline)
    pub submitter: Pubkey,                       // 32 bytes
    /// SHA-256 of (subject|predicate|object|frame) — deterministic
    pub claim_hash: [u8; 32],                    // 32 bytes

    // === CONTENT (fixed-size, zero-padded UTF-8) ===
    /// Triplet subject (e.g., "solana")
    pub subject: [u8; MAX_SUBJECT_LEN],          // 64 bytes
    /// Triplet predicate (e.g., "has_tps")
    pub predicate: [u8; MAX_PREDICATE_LEN],      // 64 bytes
    /// Triplet object (e.g., "exceeds 3000")
    pub object: [u8; MAX_OBJECT_LEN],            // 128 bytes

    // === CONSENSUS ===
    /// Consensus score × 10000 (0-10000 maps to 0.0-1.0)
    pub consensus_score: u16,                    // 2 bytes
    /// Number of models consulted in the ESMM run
    pub models_consulted: u8,                    // 1 byte
    /// Number of models that agreed
    pub models_agreeing: u8,                     // 1 byte

    // === EPISTEMIC SIGNATURE 5D (0-cochain) ===
    /// Agreement dimension × 10000
    pub sig_agreement: u16,                      // 2 bytes
    /// Semantic consistency dimension × 10000
    pub sig_semantic_consistency: u16,            // 2 bytes
    /// Centrality dimension × 10000
    pub sig_centrality: u16,                     // 2 bytes
    /// Stability dimension × 10000
    pub sig_stability: u16,                      // 2 bytes
    /// Relation diversity dimension × 10000
    pub sig_relation_diversity: u16,             // 2 bytes

    // === CLASSIFICATION ===
    /// 0=Foundational, 1=Bridge, 2=Specialized, 3=Generalist, 4=Hybrid
    pub epistemic_type: u8,                      // 1 byte
    /// 0=Low, 1=Medium, 2=High, 3=Verified
    pub confidence_tier: u8,                     // 1 byte

    // === METROLOGICAL REFERENCE ===
    /// SHA-256 of the MetrologicalFrame JSON (0x00..00 if no frame)
    pub frame_hash: [u8; 32],                    // 32 bytes
    /// SHA-256 of external verifiable source (0x00..00 if none)
    pub source_anchor: [u8; 32],                 // 32 bytes

    // === TEMPORAL ===
    /// Unix timestamp of crystallization
    pub timestamp: i64,                          // 8 bytes
    /// Unix timestamp of last revalidation (= timestamp if first)
    pub last_revalidated: i64,                   // 8 bytes
    /// Number of validations (1 = first, >1 = revalidated)
    pub validation_count: u16,                   // 2 bytes

    // === PROTOCOL ===
    /// Protocol version as packed u16 (e.g., 100 = v1.0.0)
    pub protocol_version: u16,                   // 2 bytes

    // === CHALLENGE ===
    /// Whether this is a challenge to another attestation
    pub is_challenge: bool,                      // 1 byte
    /// Pubkey of the challenged attestation PDA (Pubkey::default() if not a challenge)
    pub challenged_attestation: Pubkey,          // 32 bytes
    // FUTURE: stake mechanism — see PHASE_3_DESIGN.md
    // pub stake_amount: u64,
    // pub arbitration_status: u8,
}

impl EpistemicAttestation {
    /// Total space needed for this account (including Anchor discriminator).
    pub const SIZE: usize = DISCRIMINATOR_SIZE  // 8
        + 1                                     // bump
        + 32                                    // submitter
        + 32                                    // claim_hash
        + MAX_SUBJECT_LEN                       // subject (64)
        + MAX_PREDICATE_LEN                     // predicate (64)
        + MAX_OBJECT_LEN                        // object (128)
        + 2                                     // consensus_score
        + 1                                     // models_consulted
        + 1                                     // models_agreeing
        + 2 * 5                                 // sig_5d (10)
        + 1                                     // epistemic_type
        + 1                                     // confidence_tier
        + 32                                    // frame_hash
        + 32                                    // source_anchor
        + 8                                     // timestamp
        + 8                                     // last_revalidated
        + 2                                     // validation_count
        + 2                                     // protocol_version
        + 1                                     // is_challenge
        + 32;                                   // challenged_attestation
    // Total: 8 + 1 + 32 + 32 + 64 + 64 + 128 + 2 + 1 + 1 + 10 + 1 + 1
    //        + 32 + 32 + 8 + 8 + 2 + 2 + 1 + 32 = 462 bytes
}

// === HELPER: Enum mappings ===

/// Maps epistemic_type string to u8.
pub fn epistemic_type_to_u8(t: &str) -> Result<u8> {
    match t {
        "foundational" => Ok(0),
        "bridge" => Ok(1),
        "specialized" => Ok(2),
        "generalist" => Ok(3),
        "hybrid" => Ok(4),
        _ => err!(crate::errors::EppError::InvalidEpistemicType),
    }
}

/// Maps confidence_tier string to u8.
pub fn confidence_tier_to_u8(t: &str) -> Result<u8> {
    match t {
        "low" => Ok(0),
        "medium" => Ok(1),
        "high" => Ok(2),
        "verified" => Ok(3),
        _ => err!(crate::errors::EppError::InvalidConfidenceTier),
    }
}
```

**E. Créer `programs/epp/programs/epp/src/lib.rs`**

```rust
use anchor_lang::prelude::*;

mod constants;
mod errors;
mod state;

use constants::*;
use errors::*;
use state::*;

// AUDIT_REQUIRED: This is the core Solana program.
// Every instruction, PDA derivation, and validation must be reviewed
// by a qualified Solana developer before mainnet deployment.

declare_id!("EPPxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx");
// ^ Placeholder — will be replaced by `anchor deploy` output

#[program]
pub mod epp {
    use super::*;

    /// Submit a new epistemic attestation on-chain.
    ///
    /// PDA: [b"attestation", submitter, claim_hash]
    ///
    /// # AUDIT_REQUIRED
    /// - Validate all input ranges
    /// - Verify PDA derivation is canonical
    /// - Ensure no reentrancy
    pub fn submit_attestation(
        ctx: Context<SubmitAttestation>,
        claim_hash: [u8; 32],
        subject: [u8; MAX_SUBJECT_LEN],
        predicate: [u8; MAX_PREDICATE_LEN],
        object: [u8; MAX_OBJECT_LEN],
        consensus_score: u16,
        models_consulted: u8,
        models_agreeing: u8,
        sig_agreement: u16,
        sig_semantic_consistency: u16,
        sig_centrality: u16,
        sig_stability: u16,
        sig_relation_diversity: u16,
        epistemic_type: u8,
        confidence_tier: u8,
        frame_hash: [u8; 32],
        source_anchor: [u8; 32],
        timestamp: i64,
        validation_count: u16,
        protocol_version: u16,
        is_challenge: bool,
        challenged_attestation: Pubkey,
    ) -> Result<()> {
        // === VALIDATION ===
        require!(consensus_score <= SCORE_SCALE, EppError::InvalidConsensusScore);
        require!(sig_agreement <= SCORE_SCALE, EppError::InvalidSignatureValue);
        require!(sig_semantic_consistency <= SCORE_SCALE, EppError::InvalidSignatureValue);
        require!(sig_centrality <= SCORE_SCALE, EppError::InvalidSignatureValue);
        require!(sig_stability <= SCORE_SCALE, EppError::InvalidSignatureValue);
        require!(sig_relation_diversity <= SCORE_SCALE, EppError::InvalidSignatureValue);
        require!(models_agreeing <= models_consulted, EppError::InvalidModelCount);
        require!(epistemic_type <= 4, EppError::InvalidEpistemicType);
        require!(confidence_tier <= 3, EppError::InvalidConfidenceTier);

        // === POPULATE ACCOUNT ===
        let attestation = &mut ctx.accounts.attestation;
        attestation.bump = ctx.bumps.attestation;
        attestation.submitter = ctx.accounts.submitter.key();
        attestation.claim_hash = claim_hash;
        attestation.subject = subject;
        attestation.predicate = predicate;
        attestation.object = object;
        attestation.consensus_score = consensus_score;
        attestation.models_consulted = models_consulted;
        attestation.models_agreeing = models_agreeing;
        attestation.sig_agreement = sig_agreement;
        attestation.sig_semantic_consistency = sig_semantic_consistency;
        attestation.sig_centrality = sig_centrality;
        attestation.sig_stability = sig_stability;
        attestation.sig_relation_diversity = sig_relation_diversity;
        attestation.epistemic_type = epistemic_type;
        attestation.confidence_tier = confidence_tier;
        attestation.frame_hash = frame_hash;
        attestation.source_anchor = source_anchor;
        attestation.timestamp = timestamp;
        attestation.last_revalidated = timestamp;
        attestation.validation_count = validation_count;
        attestation.protocol_version = protocol_version;
        attestation.is_challenge = is_challenge;
        attestation.challenged_attestation = challenged_attestation;

        msg!("EPP: Attestation submitted. claim_hash={:?}", &claim_hash[..8]);
        Ok(())
    }

    /// Query attestations by claim_hash (off-chain via getProgramAccounts).
    /// This instruction is a no-op placeholder — queries happen client-side.
    /// Kept as documentation of the query pattern.
    ///
    /// Client-side: Use memcmp filter on claim_hash offset to find all
    /// attestations for a given claim.
    pub fn ping(ctx: Context<Ping>) -> Result<()> {
        msg!("EPP: Program is alive. Program ID: {}", crate::ID);
        Ok(())
    }
}

// === ACCOUNT CONTEXTS ===

#[derive(Accounts)]
#[instruction(claim_hash: [u8; 32])]
pub struct SubmitAttestation<'info> {
    /// The attestation PDA to create.
    /// AUDIT_REQUIRED: Verify seeds match the intended PDA derivation.
    #[account(
        init,
        payer = submitter,
        space = EpistemicAttestation::SIZE,
        seeds = [ATTESTATION_SEED, submitter.key().as_ref(), &claim_hash],
        bump
    )]
    pub attestation: Account<'info, EpistemicAttestation>,

    /// The submitter (pays for account creation).
    #[account(mut)]
    pub submitter: Signer<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Ping<'info> {
    pub signer: Signer<'info>,
}
```

### Tests Anchor (minimal) — `programs/epp/tests/epp.ts`

Ne pas écrire de tests TS exhaustifs. Un seul test de smoke pour valider que le programme compile et se déploie :

```typescript
import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { Epp } from "../target/types/epp";
import { expect } from "chai";

describe("epp", () => {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);
  const program = anchor.workspace.Epp as Program<Epp>;

  it("Ping — programme alive", async () => {
    const tx = await program.methods.ping().rpc();
    console.log("Ping tx:", tx);
  });
});
```

### Validation de l'étape

```bash
cd programs/epp
anchor build
anchor test     # Sur localnet
```

**Critère de passage** : `anchor build` réussit sans erreur. `anchor test` → ping passe.

---

## ÉTAPE 1.2 — Bridge de sérialisation Python ↔ Anchor

### Objectif

Créer la couche de sérialisation intermédiaire qui convertit un `EpistemicAttestation` Python
en arguments prêts pour l'instruction Anchor `submit_attestation`, et inversement.

C'est la zone la plus délicate : une erreur de sérialisation = données corrompues on-chain.

### Ce que tu fais

**A. Créer `services/solana/bridge.py`**

```python
"""
Serialization bridge: Python EpistemicAttestation ↔ Anchor program.

Converts between:
- Python floats [0.0, 1.0] → Rust u16 [0, 10000]
- Python strings → Fixed-size byte arrays (zero-padded UTF-8)
- Python hex strings → Raw bytes [u8; 32]
- Python enum strings → Rust u8 enum values

# AUDIT_REQUIRED: This entire module is security-critical.
# Any serialization bug means corrupted on-chain data.
# Must be reviewed by a Solana developer before mainnet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

# Import depuis attestation.py (Phase 0.3)
from services.esmm.attestation import EpistemicAttestation, Signature5D


# === CONSTANTS (must match programs/epp/src/constants.rs) ===
MAX_SUBJECT_LEN = 64
MAX_PREDICATE_LEN = 64
MAX_OBJECT_LEN = 128
SCORE_SCALE = 10000

# === ENUM MAPPINGS (must match programs/epp/src/state.rs) ===
EPISTEMIC_TYPE_MAP = {
    "foundational": 0,
    "bridge": 1,
    "specialized": 2,
    "generalist": 3,
    "hybrid": 4,
}

CONFIDENCE_TIER_MAP = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "verified": 3,
}

# Reverse maps for deserialization
EPISTEMIC_TYPE_REVERSE = {v: k for k, v in EPISTEMIC_TYPE_MAP.items()}
CONFIDENCE_TIER_REVERSE = {v: k for k, v in CONFIDENCE_TIER_MAP.items()}


@dataclass
class AnchorAttestationArgs:
    """
    Arguments prêts pour l'instruction Anchor submit_attestation.

    Chaque champ correspond EXACTEMENT à un paramètre de l'instruction Rust.
    Les types sont ceux attendus par anchorpy/solders.

    # AUDIT_REQUIRED: Field order and types must match lib.rs instruction signature.
    """
    claim_hash: bytes          # [u8; 32]
    subject: bytes             # [u8; 64] zero-padded
    predicate: bytes           # [u8; 64] zero-padded
    object_field: bytes        # [u8; 128] zero-padded (renamed to avoid Python keyword)
    consensus_score: int       # u16 [0, 10000]
    models_consulted: int      # u8
    models_agreeing: int       # u8
    sig_agreement: int         # u16
    sig_semantic_consistency: int  # u16
    sig_centrality: int        # u16
    sig_stability: int         # u16
    sig_relation_diversity: int   # u16
    epistemic_type: int        # u8
    confidence_tier: int       # u8
    frame_hash: bytes          # [u8; 32]
    source_anchor: bytes       # [u8; 32]
    timestamp: int             # i64
    validation_count: int      # u16
    protocol_version: int      # u16
    is_challenge: bool         # bool
    challenged_attestation: bytes  # Pubkey as 32 bytes


# === ENCODING FUNCTIONS ===

def float_to_u16(value: float) -> int:
    """
    Encode float [0.0, 1.0] → u16 [0, 10000].

    # AUDIT_REQUIRED: Precision loss — 4 decimal places max.
    """
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"Float must be in [0.0, 1.0], got {value}")
    return min(int(round(value * SCORE_SCALE)), SCORE_SCALE)


def u16_to_float(value: int) -> float:
    """Decode u16 [0, 10000] → float [0.0, 1.0]."""
    if not 0 <= value <= SCORE_SCALE:
        raise ValueError(f"u16 must be in [0, {SCORE_SCALE}], got {value}")
    return value / SCORE_SCALE


def string_to_fixed_bytes(s: str, max_len: int) -> bytes:
    """
    Encode string → fixed-size bytes (UTF-8, zero-padded, truncated if needed).

    # AUDIT_REQUIRED: Truncation silently loses data. Log a warning?
    """
    encoded = s.encode("utf-8")[:max_len]
    return encoded.ljust(max_len, b'\x00')


def fixed_bytes_to_string(b: bytes) -> str:
    """Decode fixed-size bytes → string (strip trailing zeros)."""
    return b.rstrip(b'\x00').decode("utf-8", errors="replace")


def hex_to_bytes32(hex_str: Optional[str]) -> bytes:
    """
    Encode hex string → [u8; 32]. Returns 32 zero bytes if None/empty.

    # AUDIT_REQUIRED: Validate hex input length.
    """
    if not hex_str:
        return b'\x00' * 32
    raw = bytes.fromhex(hex_str)
    if len(raw) != 32:
        raise ValueError(f"Expected 32 bytes, got {len(raw)} from hex '{hex_str[:16]}...'")
    return raw


def protocol_version_to_u16(version_str: str) -> int:
    """
    Encode version string → u16. "0.3" → 3, "1.0" → 100, "1.2" → 120.
    Format: major * 100 + minor.
    """
    parts = version_str.split(".")
    if len(parts) != 2:
        raise ValueError(f"Version must be 'major.minor', got '{version_str}'")
    major, minor = int(parts[0]), int(parts[1])
    return major * 100 + minor


def u16_to_protocol_version(value: int) -> str:
    """Decode u16 → version string."""
    return f"{value // 100}.{value % 100}"


# === MAIN BRIDGE FUNCTIONS ===

def attestation_to_anchor_args(
    attestation: EpistemicAttestation,
    frame_hash: Optional[str] = None,
    is_challenge: bool = False,
    challenged_attestation_pubkey: Optional[bytes] = None,
) -> AnchorAttestationArgs:
    """
    Convert a Python EpistemicAttestation to Anchor instruction arguments.

    Args:
        attestation: The crystallized attestation from the ESMM pipeline.
        frame_hash: SHA-256 hex of the MetrologicalFrame (compute_frame_hash()).
                    If None and attestation.metrological_frame exists, uses claim_hash logic.
        is_challenge: Whether this attestation challenges another.
        challenged_attestation_pubkey: 32-byte Pubkey of the challenged PDA.

    Returns:
        AnchorAttestationArgs ready for transaction building.

    # AUDIT_REQUIRED: Verify field mapping completeness and correctness.
    """
    sig = attestation.signature_5d

    return AnchorAttestationArgs(
        claim_hash=hex_to_bytes32(attestation.claim_hash),
        subject=string_to_fixed_bytes(attestation.subject, MAX_SUBJECT_LEN),
        predicate=string_to_fixed_bytes(attestation.predicate, MAX_PREDICATE_LEN),
        object_field=string_to_fixed_bytes(attestation.object, MAX_OBJECT_LEN),
        consensus_score=float_to_u16(attestation.consensus_score),
        models_consulted=attestation.models_consulted,
        models_agreeing=attestation.models_agreeing,
        sig_agreement=float_to_u16(sig.agreement),
        sig_semantic_consistency=float_to_u16(sig.semantic_consistency),
        sig_centrality=float_to_u16(sig.centrality),
        sig_stability=float_to_u16(sig.stability),
        sig_relation_diversity=float_to_u16(sig.relation_diversity),
        epistemic_type=EPISTEMIC_TYPE_MAP[attestation.epistemic_type],
        confidence_tier=CONFIDENCE_TIER_MAP[attestation.confidence_tier],
        frame_hash=hex_to_bytes32(frame_hash),
        source_anchor=hex_to_bytes32(attestation.source_anchor),
        timestamp=int(attestation.timestamp),
        validation_count=attestation.validation_count,
        protocol_version=protocol_version_to_u16(attestation.protocol_version),
        is_challenge=is_challenge,
        challenged_attestation=challenged_attestation_pubkey or (b'\x00' * 32),
    )


def anchor_data_to_attestation_summary(
    data: dict,
) -> dict:
    """
    Convert on-chain account data (from getProgramAccounts) back to
    a human-readable summary dict.

    This is the reverse bridge — used by `epp query` to display results.

    Args:
        data: Raw account data deserialized from Anchor IDL.

    Returns:
        Dict with human-readable field values.

    # AUDIT_REQUIRED: Verify deserialization matches serialization.
    """
    return {
        "claim_hash": data["claim_hash"].hex() if isinstance(data["claim_hash"], bytes) else data["claim_hash"],
        "subject": fixed_bytes_to_string(bytes(data["subject"])) if isinstance(data["subject"], (list, bytes)) else data["subject"],
        "predicate": fixed_bytes_to_string(bytes(data["predicate"])) if isinstance(data["predicate"], (list, bytes)) else data["predicate"],
        "object": fixed_bytes_to_string(bytes(data["object"])) if isinstance(data["object"], (list, bytes)) else data["object"],
        "consensus_score": u16_to_float(data["consensus_score"]),
        "models_consulted": data["models_consulted"],
        "models_agreeing": data["models_agreeing"],
        "signature_5d": {
            "agreement": u16_to_float(data["sig_agreement"]),
            "semantic_consistency": u16_to_float(data["sig_semantic_consistency"]),
            "centrality": u16_to_float(data["sig_centrality"]),
            "stability": u16_to_float(data["sig_stability"]),
            "relation_diversity": u16_to_float(data["sig_relation_diversity"]),
        },
        "epistemic_type": EPISTEMIC_TYPE_REVERSE.get(data["epistemic_type"], f"unknown({data['epistemic_type']})"),
        "confidence_tier": CONFIDENCE_TIER_REVERSE.get(data["confidence_tier"], f"unknown({data['confidence_tier']})"),
        "frame_hash": bytes(data["frame_hash"]).hex() if isinstance(data["frame_hash"], (list, bytes)) else data["frame_hash"],
        "timestamp": data["timestamp"],
        "validation_count": data["validation_count"],
        "protocol_version": u16_to_protocol_version(data["protocol_version"]),
        "is_challenge": data.get("is_challenge", False),
    }
```

### Tests — `tests/test_phase1_bridge.py`

```python
"""Tests Phase 1.2 — Bridge de sérialisation Python ↔ Anchor."""

import pytest
import time

from services.solana.bridge import (
    float_to_u16, u16_to_float,
    string_to_fixed_bytes, fixed_bytes_to_string,
    hex_to_bytes32, protocol_version_to_u16, u16_to_protocol_version,
    attestation_to_anchor_args, anchor_data_to_attestation_summary,
    SCORE_SCALE, MAX_SUBJECT_LEN, MAX_PREDICATE_LEN, MAX_OBJECT_LEN,
    EPISTEMIC_TYPE_MAP, CONFIDENCE_TIER_MAP,
)
from services.esmm.attestation import (
    EpistemicAttestation, Signature5D, ModelVote,
    crystallize, compute_claim_hash,
)


class TestFloatU16:
    """Tests conversion float ↔ u16."""

    def test_zero(self):
        assert float_to_u16(0.0) == 0
        assert u16_to_float(0) == 0.0

    def test_one(self):
        assert float_to_u16(1.0) == SCORE_SCALE
        assert u16_to_float(SCORE_SCALE) == 1.0

    def test_middle(self):
        assert float_to_u16(0.5) == 5000
        assert u16_to_float(5000) == 0.5

    def test_precision(self):
        """4 decimal places preserved."""
        assert float_to_u16(0.8765) == 8765
        assert u16_to_float(8765) == 0.8765

    def test_roundtrip(self):
        """float → u16 → float = same (within precision)."""
        for v in [0.0, 0.1, 0.25, 0.333, 0.5, 0.75, 0.9999, 1.0]:
            assert abs(u16_to_float(float_to_u16(v)) - v) < 0.0001

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            float_to_u16(1.1)
        with pytest.raises(ValueError):
            float_to_u16(-0.1)

    def test_u16_out_of_range_raises(self):
        with pytest.raises(ValueError):
            u16_to_float(10001)


class TestStringBytes:
    """Tests conversion string ↔ fixed bytes."""

    def test_basic(self):
        b = string_to_fixed_bytes("hello", 10)
        assert len(b) == 10
        assert b[:5] == b"hello"
        assert b[5:] == b'\x00' * 5

    def test_exact_length(self):
        b = string_to_fixed_bytes("abcd", 4)
        assert b == b"abcd"

    def test_truncation(self):
        b = string_to_fixed_bytes("this is too long", 8)
        assert len(b) == 8
        assert b == b"this is "

    def test_roundtrip(self):
        original = "solana"
        b = string_to_fixed_bytes(original, MAX_SUBJECT_LEN)
        recovered = fixed_bytes_to_string(b)
        assert recovered == original

    def test_unicode(self):
        """UTF-8 multi-byte characters are handled."""
        b = string_to_fixed_bytes("café", MAX_SUBJECT_LEN)
        recovered = fixed_bytes_to_string(b)
        assert recovered == "café"

    def test_empty_string(self):
        b = string_to_fixed_bytes("", 32)
        assert b == b'\x00' * 32
        assert fixed_bytes_to_string(b) == ""


class TestHexBytes:
    """Tests conversion hex ↔ bytes32."""

    def test_valid_hash(self):
        h = "a" * 64  # 64 hex chars = 32 bytes
        b = hex_to_bytes32(h)
        assert len(b) == 32
        assert b == bytes.fromhex(h)

    def test_none_gives_zeros(self):
        b = hex_to_bytes32(None)
        assert b == b'\x00' * 32

    def test_empty_gives_zeros(self):
        b = hex_to_bytes32("")
        assert b == b'\x00' * 32

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError, match="Expected 32 bytes"):
            hex_to_bytes32("abcd")  # Too short


class TestProtocolVersion:
    """Tests conversion version string ↔ u16."""

    def test_v0_3(self):
        assert protocol_version_to_u16("0.3") == 3

    def test_v1_0(self):
        assert protocol_version_to_u16("1.0") == 100

    def test_roundtrip(self):
        for v in ["0.1", "0.3", "1.0", "1.2", "2.0"]:
            assert u16_to_protocol_version(protocol_version_to_u16(v)) == v


class TestAttestationToAnchorArgs:
    """Test conversion complète attestation → args Anchor."""

    def _make_attestation(self) -> EpistemicAttestation:
        """Helper : crée une attestation de test."""
        return crystallize(
            subject="solana",
            predicate="has_tps",
            object_="exceeds 3000",
            consensus_score=0.85,
            model_votes=[
                ModelVote(model_id="test::model_a", provider_id="test", agreed=True, confidence=0.9),
                ModelVote(model_id="test::model_b", provider_id="test", agreed=True, confidence=0.8),
                ModelVote(model_id="test::model_c", provider_id="test", agreed=False, confidence=0.3),
            ],
            signature_5d=Signature5D(
                agreement=0.85,
                semantic_consistency=0.72,
                centrality=0.45,
                stability=0.90,
                relation_diversity=0.60,
            ),
            epistemic_type="foundational",
            metrological_frame="blockchain_tps_v1.0",
        )

    def test_basic_conversion(self):
        att = self._make_attestation()
        args = attestation_to_anchor_args(att)
        assert len(args.claim_hash) == 32
        assert len(args.subject) == MAX_SUBJECT_LEN
        assert len(args.predicate) == MAX_PREDICATE_LEN
        assert len(args.object_field) == MAX_OBJECT_LEN
        assert args.consensus_score == 8500
        assert args.models_consulted == 3
        assert args.models_agreeing == 2

    def test_signature_5d_encoding(self):
        att = self._make_attestation()
        args = attestation_to_anchor_args(att)
        assert args.sig_agreement == 8500
        assert args.sig_semantic_consistency == 7200
        assert args.sig_centrality == 4500
        assert args.sig_stability == 9000
        assert args.sig_relation_diversity == 6000

    def test_enum_encoding(self):
        att = self._make_attestation()
        args = attestation_to_anchor_args(att)
        assert args.epistemic_type == EPISTEMIC_TYPE_MAP["foundational"]
        assert args.confidence_tier == CONFIDENCE_TIER_MAP["high"]  # 0.85 → high

    def test_claim_hash_matches(self):
        """Le claim_hash dans args = bytes du claim_hash Python."""
        att = self._make_attestation()
        args = attestation_to_anchor_args(att)
        assert args.claim_hash == bytes.fromhex(att.claim_hash)

    def test_challenge_defaults(self):
        att = self._make_attestation()
        args = attestation_to_anchor_args(att)
        assert args.is_challenge is False
        assert args.challenged_attestation == b'\x00' * 32

    def test_roundtrip_summary(self):
        """attestation → anchor_args → simulated on-chain → summary → verify."""
        att = self._make_attestation()
        args = attestation_to_anchor_args(att)

        # Simulate reading back from chain (as dict with same field names)
        on_chain_data = {
            "claim_hash": args.claim_hash,
            "subject": list(args.subject),
            "predicate": list(args.predicate),
            "object": list(args.object_field),
            "consensus_score": args.consensus_score,
            "models_consulted": args.models_consulted,
            "models_agreeing": args.models_agreeing,
            "sig_agreement": args.sig_agreement,
            "sig_semantic_consistency": args.sig_semantic_consistency,
            "sig_centrality": args.sig_centrality,
            "sig_stability": args.sig_stability,
            "sig_relation_diversity": args.sig_relation_diversity,
            "epistemic_type": args.epistemic_type,
            "confidence_tier": args.confidence_tier,
            "frame_hash": list(args.frame_hash),
            "timestamp": args.timestamp,
            "validation_count": args.validation_count,
            "protocol_version": args.protocol_version,
            "is_challenge": args.is_challenge,
        }
        summary = anchor_data_to_attestation_summary(on_chain_data)

        assert summary["subject"] == "solana"
        assert summary["predicate"] == "has_tps"
        assert summary["object"] == "exceeds 3000"
        assert abs(summary["consensus_score"] - 0.85) < 0.001
        assert summary["epistemic_type"] == "foundational"
        assert summary["confidence_tier"] == "high"
        assert summary["signature_5d"]["agreement"] == 0.85
```

**Critère de passage** : `pytest tests/test_phase1_bridge.py -v` → tous verts.

---

## ÉTAPE 1.3 — Client Solana Python

### Objectif

Créer le client Python qui signe et envoie les transactions au programme Anchor,
et qui sait relire les attestations on-chain.

### Prérequis

- Étapes 1.0, 1.1, 1.2 passées.
- Programme déployé sur localnet (`anchor deploy`).
- IDL disponible dans `programs/epp/target/idl/epp.json`.

### Dépendances Python

```bash
pip install solders solana anchorpy --break-system-packages
```

Si anchorpy ne fonctionne pas (problème de version/compat), utilise solders + borsh manuel.
Dans ce cas, documente le choix dans CHANGELOG.md.

### Ce que tu fais

**A. Créer `services/solana/client.py`**

Ce fichier est le plus critique côté sécurité. Chaque fonction est marquée AUDIT_REQUIRED.

Le contrat du client :

```python
"""
Solana client for EPP — transaction building and submission.

# AUDIT_REQUIRED: This entire module handles blockchain transactions.
# Every function that signs, sends, or reads on-chain data must be
# reviewed by a qualified Solana developer before mainnet.
#
# SECURITY INVARIANTS:
# 1. NEVER sends transactions to mainnet (devnet guard in config.py)
# 2. NEVER stores private keys in code or logs
# 3. ALL transactions are logged with tx signature for audit
# 4. PDA derivation uses CANONICAL seeds only
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from services.solana.config import SolanaConfig, validate_cluster
from services.solana.bridge import (
    AnchorAttestationArgs,
    attestation_to_anchor_args,
    anchor_data_to_attestation_summary,
)
from services.esmm.attestation import EpistemicAttestation

logger = logging.getLogger("epp.solana.client")


class EppSolanaClient:
    """
    Client Solana pour EPP.

    # AUDIT_REQUIRED: All methods.

    Responsabilités :
    1. Dériver les PDAs d'attestation
    2. Construire les transactions submit_attestation
    3. Signer et envoyer les transactions
    4. Lire les attestations on-chain (getProgramAccounts)
    5. Mettre à jour la DB locale avec la signature tx

    Usage:
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        client = EppSolanaClient(config)
        tx_sig = await client.submit_attestation(attestation, frame_hash)
    """

    def __init__(self, config: SolanaConfig):
        """
        # AUDIT_REQUIRED: Validate config, load keypair safely.
        """
        validate_cluster(config.cluster)  # Devnet guard
        self.config = config
        self._program_id = config.program_id
        # Load IDL, init connection, load keypair
        # Implementation depends on anchorpy vs solders choice
        ...

    async def submit_attestation(
        self,
        attestation: EpistemicAttestation,
        frame_hash: Optional[str] = None,
        is_challenge: bool = False,
        challenged_pda: Optional[str] = None,
    ) -> str:
        """
        Submit an attestation on-chain.

        Returns: Transaction signature (base58 string).

        # AUDIT_REQUIRED: PDA derivation, transaction construction, signing.
        """
        # 1. Convert to Anchor args via bridge
        # 2. Derive PDA
        # 3. Build transaction
        # 4. Sign with loaded keypair
        # 5. Send and confirm
        # 6. Return tx signature
        ...

    async def get_attestation(
        self,
        submitter_pubkey: str,
        claim_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Read a single attestation by (submitter, claim_hash).

        # AUDIT_REQUIRED: PDA derivation must match submit.
        """
        ...

    async def query_attestations_by_claim(
        self,
        claim_hash: str,
        min_consensus: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Query all attestations for a given claim_hash.
        Uses getProgramAccounts with memcmp filter on claim_hash offset.

        # AUDIT_REQUIRED: Verify memcmp offset matches account layout.
        """
        ...

    async def query_attestations_by_subject(
        self,
        subject: str,
        min_consensus: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Query attestations whose subject field matches.
        Uses getProgramAccounts with memcmp filter on subject offset.

        # AUDIT_REQUIRED: Verify memcmp offset matches account layout.
        """
        ...
```

**Note importante** : Le contrat ci-dessus est l'interface. L'implémentation dépend du choix
anchorpy vs solders. Claude Code doit d'abord tenter anchorpy (qui consomme l'IDL
et génère automatiquement les types). Si ça échoue, implémenter avec solders + borsh.

### Tests — `tests/test_phase1_client.py`

Les tests du client ont deux niveaux :

1. **Tests unitaires (mock)** : Vérifient la logique sans réseau
2. **Tests localnet** : Requièrent `solana-test-validator` (skip si indisponible)

```python
"""Tests Phase 1.3 — Client Solana."""

import pytest
import os

# Skip si pas de validator
LOCALNET_AVAILABLE = os.environ.get("EPP_TEST_LOCALNET", "0") == "1"


class TestClientUnit:
    """Tests unitaires (pas de réseau)."""

    def test_client_refuses_mainnet(self):
        """Le client refuse catégoriquement le mainnet."""
        from services.solana.config import SolanaCluster, SolanaConfig
        # Il n'y a pas de MAINNET dans l'enum, mais testons un contournement
        with pytest.raises((RuntimeError, AttributeError)):
            # Attempt to create config with forged mainnet URL
            SolanaConfig(cluster=SolanaCluster.DEVNET)
            # This should work — but mainnet should not exist


@pytest.mark.skipif(not LOCALNET_AVAILABLE, reason="Localnet not running")
class TestClientLocalnet:
    """Tests contre solana-test-validator."""

    @pytest.mark.asyncio
    async def test_submit_and_read_back(self):
        """Submit une attestation sur localnet et la relit."""
        # Ce test sera implémenté une fois le client fonctionnel
        pass

    @pytest.mark.asyncio
    async def test_query_by_claim_hash(self):
        """Query par claim_hash retourne l'attestation soumise."""
        pass

    @pytest.mark.asyncio
    async def test_two_submitters_same_claim(self):
        """Deux submitters différents peuvent attester le même claim."""
        pass
```

**Critère de passage** : Tests unitaires verts. Tests localnet verts avec `EPP_TEST_LOCALNET=1`.

---

## ÉTAPE 1.4 — CLI de démonstration

### Objectif

Créer les commandes CLI qui connectent le pipeline ESMM au client Solana.
C'est la couche de présentation du MVP.

### Ce que tu fais

**A. Créer `cli/epp_cli.py`**

Utiliser `click` (ou `argparse` si plus simple).

Commandes requises :

| Commande | Description | Input | Output |
|----------|-------------|-------|--------|
| `epp ask "question" --models N --frame ID` | Run ESMM pipeline | Question + config | Attestations affichées |
| `epp submit --devnet` | Poste la dernière attestation on-chain | Attestation en DB | Tx signature + lien explorer |
| `epp query "subject" --min-confidence X` | Cherche on-chain + local | Subject + seuil | Attestations matchées |
| `epp graph stats` | Stats du graphe local | Rien | Nb triplets, couverture, etc. |
| `epp frame list` | Liste les frames disponibles | Rien | Frames avec hash |
| `epp frame show ID` | Affiche un frame complet | Frame ID | JSON du frame |

Chaque commande affiche un output lisible. `epp submit` affiche systématiquement :
```
⚠️  DEVNET ONLY — This is an experimental sandbox.
    Not for production use. See AUDIT_REQUIRED markers.

✅ Attestation submitted to Solana devnet
   TX: <signature>
   Explorer: https://explorer.solana.com/tx/<signature>?cluster=devnet
   PDA: <address>
   Claim: <claim_hash[:16]>...
```

### Tests — `tests/test_phase1_cli.py`

Tests minimaux vérifiant que les commandes parsent correctement et que les guards fonctionnent.

**Critère de passage** : `epp ask` + `epp submit` + `epp query` fonctionnent en séquence sur localnet.

---

## ÉTAPE 1.5 — Tests d'intégration end-to-end

### Objectif

Valider le flux complet : question → ESMM → cristallisation → sérialisation → on-chain → relecture → vérification.

### Ce que tu fais

**A. Créer `tests/test_phase1_integration.py`**

```python
"""
Tests d'intégration Phase 1 — flux complet.

Requiert : solana-test-validator ou devnet configuré.
"""

import pytest
import os

INTEGRATION = os.environ.get("EPP_TEST_INTEGRATION", "0") == "1"


@pytest.mark.skipif(not INTEGRATION, reason="Integration tests disabled")
class TestEndToEnd:
    """Tests end-to-end complets."""

    @pytest.mark.asyncio
    async def test_full_flow_localnet(self):
        """
        1. Crée une attestation via crystallize()
        2. Sérialise via bridge
        3. Submit on-chain via client
        4. Relit on-chain via client
        5. Vérifie que les données correspondent
        6. Met à jour la DB locale avec tx signature
        """
        pass

    @pytest.mark.asyncio
    async def test_challenge_flow(self):
        """
        1. Submit attestation A (submitter_1, claim_hash_X)
        2. Submit attestation B (submitter_2, claim_hash_X, is_challenge=True)
        3. Query par claim_hash_X → retourne A et B
        4. Vérifie que B.challenged_attestation pointe vers A
        """
        pass

    @pytest.mark.asyncio
    async def test_claim_hash_determinism(self):
        """
        Même triplet + frame → même claim_hash → même PDA
        Vérifie que submit_attestation échoue si le PDA existe déjà
        (même submitter + même claim).
        """
        pass

    @pytest.mark.asyncio
    async def test_bridge_roundtrip_integrity(self):
        """
        Attestation Python → bridge → on-chain → bridge inverse → summary
        Vérifie que summary.subject == attestation.subject, etc.
        """
        pass

    @pytest.mark.asyncio
    async def test_db_updated_with_tx(self):
        """
        Après submit on-chain, la DB locale a :
        - solana_tx_signature != NULL
        - solana_slot != NULL
        - anchored_at != NULL
        """
        pass

    @pytest.mark.asyncio
    async def test_frame_hash_on_chain(self):
        """
        L'attestation on-chain porte le hash du MetrologicalFrame.
        Vérifie que frame_hash on-chain == compute_frame_hash() Python.
        """
        pass

    @pytest.mark.asyncio
    async def test_devnet_guard_in_flow(self):
        """
        Le flux complet ne peut pas être exécuté contre mainnet.
        """
        pass
```

**Critère de passage** : `EPP_TEST_INTEGRATION=1 pytest tests/test_phase1_integration.py -v` → tous verts.

---

## ZONES AUDIT_REQUIRED — Registre complet

Ce registre liste TOUTES les zones nécessitant un audit par un développeur Solana qualifié.
Le fondateur doit pouvoir les montrer à un dev et dire "voilà exactement ce qu'il faut vérifier".

| # | Fichier | Zone | Risque | Priorité |
|---|---------|------|--------|----------|
| A1 | `programs/epp/src/lib.rs` | `submit_attestation` — validation des inputs | Données corrompues on-chain | **CRITIQUE** |
| A2 | `programs/epp/src/lib.rs` | PDA derivation seeds | PDA spoofing, collision | **CRITIQUE** |
| A3 | `programs/epp/src/state.rs` | Account size calculation (`SIZE`) | Rent incorrect, account corruption | **CRITIQUE** |
| A4 | `programs/epp/src/state.rs` | Field layout ordering | Deserialization mismatch | **CRITIQUE** |
| A5 | `services/solana/bridge.py` | `attestation_to_anchor_args` | Serialization bug → data corruption | **HAUTE** |
| A6 | `services/solana/bridge.py` | `float_to_u16` precision | Precision loss silencieuse | Moyenne |
| A7 | `services/solana/client.py` | Transaction signing | Key exposure, replay attacks | **CRITIQUE** |
| A8 | `services/solana/client.py` | `getProgramAccounts` memcmp offsets | Wrong offset → wrong data | **HAUTE** |
| A9 | `services/solana/config.py` | Devnet guard completeness | Accidental mainnet use | **CRITIQUE** |
| A10 | `programs/epp/src/lib.rs` | Challenge mechanism | Future stake/slash expansion | Basse (MVP) |

---

## ORDRE D'EXÉCUTION (résumé)

```
ÉTAPE 1.0 — MetrologicalFrame (Python, aucune dépendance Solana)
    │  Fichiers : services/solana/metrological_frame.py, config.py, __init__.py
    │  Tests : test_phase1_frame.py (~12 tests)
    │  Prérequis : Aucun
    ▼
ÉTAPE 1.1 — Programme Anchor (Rust)
    │  Fichiers : programs/epp/programs/epp/src/{lib,state,errors,constants}.rs
    │  Tests : anchor build + anchor test (ping)
    │  Prérequis : Solana CLI + Anchor installés
    ▼
ÉTAPE 1.2 — Bridge sérialisation
    │  Fichiers : services/solana/bridge.py
    │  Tests : test_phase1_bridge.py (~20 tests)
    │  Prérequis : Étape 1.0 (pour types) + 1.1 (pour constants)
    ▼
ÉTAPE 1.3 — Client Solana Python
    │  Fichiers : services/solana/client.py
    │  Tests : test_phase1_client.py (unit + localnet)
    │  Prérequis : Étapes 1.1 + 1.2 + programme déployé localnet
    ▼
ÉTAPE 1.4 — CLI de démonstration
    │  Fichiers : cli/epp_cli.py
    │  Tests : test_phase1_cli.py
    │  Prérequis : Étapes 1.0-1.3 complètes
    ▼
ÉTAPE 1.5 — Intégration end-to-end
    │  Tests : test_phase1_integration.py (~7 tests)
    │  Prérequis : Tout ci-dessus + solana-test-validator
    ▼
✅ PHASE 1 COMPLÈTE
    Critère : epp ask → débat → submit devnet → query → attestation relue
```

---

## CHECKLIST DE FIN DE PHASE 1

- [ ] `MetrologicalFrame` modélisé avec `compute_frame_hash()`
- [ ] Premier frame concret (`blockchain_tps_v1.0`) défini
- [ ] Programme Anchor compile (`anchor build`)
- [ ] Instruction `submit_attestation` fonctionnelle sur localnet
- [ ] PDA dérivé avec seeds `[b"attestation", submitter, claim_hash]`
- [ ] Bridge Python ↔ Anchor avec tests de roundtrip
- [ ] Client Python peut submit + query
- [ ] Guard devnet-only codé et testé
- [ ] CLI `epp ask` + `epp submit` + `epp query` fonctionnels
- [ ] DB locale mise à jour avec `solana_tx_signature` après submit
- [ ] Registre AUDIT_REQUIRED documenté (ce fichier §Zones)
- [ ] CHANGELOG.md mis à jour
- [ ] ARCHITECTURE.md mis à jour avec la couche Solana
- [ ] 40+ tests passent (frame + bridge + client + CLI + intégration)

---

## NOTES POUR LE FUTUR DEV SOLANA

Si tu es le développeur Solana qui audite ce code :

1. **Le fondateur n'est pas développeur.** Le code a été produit par Claude Code (LLM)
   et vérifié par requêtage croisé. La logique métier est solide (165+ tests off-chain)
   mais le code Anchor n'a pas été écrit par un humain expert Solana.

2. **Cherche "AUDIT_REQUIRED"** dans tout le repo. C'est le registre complet.

3. **Le bridge est la zone la plus risquée.** Un bug de sérialisation = données corrompues.
   Vérifie surtout : field order dans le struct Rust vs l'IDL, memcmp offsets dans les queries,
   la conversion float→u16 et les edge cases (NaN, overflow).

4. **Le mécanisme de challenge est un placeholder MVP.** Il pose les bases structurelles
   (PDA, fields) pour un futur mécanisme stake/arbitrage. Vérifie que l'extension est
   faisable sans migration de comptes.

5. **Le devnet guard est intentionnel et permanent** jusqu'à audit complet.
   Ne le supprime pas sans avoir vérifié TOUS les points du registre A1-A10.

---

*Instructions Phase 1 — Version 1.0 — 5 février 2026*
*Prérequis validé : Phase 0 complète (165 tests, 0 couplage)*
