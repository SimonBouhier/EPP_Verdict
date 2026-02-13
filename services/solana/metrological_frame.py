"""
Metrological Frame -- Referentiel de mesure versionne.

Definit CE QU'ON MESURE et COMMENT pour un domaine specifique.
Le hash SHA-256 du frame est ancre on-chain avec chaque attestation.
Le contenu complet du frame est stocke off-chain (SQLite + publication).

Contrat d'interface avec le programme Solana : seul le frame_hash
est transmis on-chain. Le frame complet est verifiable off-chain.
"""

import hashlib
import json
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class FrameGovernance(BaseModel):
    """Gouvernance du referentiel."""
    current_authority: str = Field(
        default="founding_team",
        description="Autorite actuelle (founding_team | expert_panel | dao_vote)"
    )
    amendment_process: str = Field(
        default="version_bump_with_changelog",
        description="Processus de modification"
    )
    target_authority: str = Field(
        default="dao_vote",
        description="Autorite cible a terme"
    )


class MetrologicalFrame(BaseModel):
    """
    Referentiel metrologique versionne.

    Specifie formellement ce qu'on mesure, comment, et avec quelles
    contraintes. Chaque attestation reference un frame par son hash.
    """
    frame_id: str = Field(
        max_length=64,
        description="Identifiant unique du frame (ex: blockchain_tps_v1.0)"
    )
    version: str = Field(
        description="Version semantique (ex: 1.0)"
    )
    domain: str = Field(
        description="Domaine couvert (ex: blockchain_metrics, ai_benchmarks)"
    )
    metric: str = Field(
        description="Metrique principale mesuree (ex: transactions_per_second)"
    )
    description: str = Field(
        description="Description humaine du referentiel"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parametres specifiques au domaine"
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
        """Frame ID : alphanumerique + underscores + dots uniquement."""
        import re
        if not re.match(r'^[a-z0-9][a-z0-9_.]*$', v):
            raise ValueError(
                f"frame_id must be lowercase alphanumeric with _ and . only, got '{v}'"
            )
        return v

    def compute_frame_hash(self) -> str:
        """
        Hash SHA-256 deterministe du frame.

        Serialise le frame en JSON canonique (sorted keys, compact separators)
        et retourne le hash hex. C'est cette valeur qui est ancree on-chain.
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
        """JSON deterministe pour publication et verification."""
        return json.dumps(
            self.model_dump(),
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
            default=str,
        )


# === FRAMES PREDEFINIS (MVP) ===

def create_blockchain_tps_frame() -> MetrologicalFrame:
    """Premier referentiel concret : blockchain TPS."""
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
    """Referentiel generique pour claims factuels generaux."""
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
