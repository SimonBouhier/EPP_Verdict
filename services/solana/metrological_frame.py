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
from typing import Optional, Dict, Any, Callable
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


# --- ADR-012 : Frames RWA / sources déterministes ---


def create_compliance_sanctions_frame() -> MetrologicalFrame:
    """Screening sanctions OFAC/EU/ONU via sources autoritaires. Bypass ESMM."""
    return MetrologicalFrame(
        frame_id="compliance_sanctions_v1.0",
        version="1.0",
        domain="regulatory_compliance",
        metric="sanctions_status",
        description=(
            "Déterministe : screening sanctions OFAC SDN, EU CFSP, ONU, OpenSanctions. "
            "Pipeline ESMM court-circuité (esmm_bypass=True). "
            "Tier assigné par concordance de sources (1→proposition, 2→validated, "
            "3+score≥0.95→verified)."
        ),
        parameters={
            "authoritative_sources": ["OFAC_SDN", "EU_CFSP", "UN", "opensanctions"],
            "match_score_threshold": 0.85,
            "snapshot_ttl_hours": 24,
            "esmm_bypass": True,
        },
        required_sources=1,
    )


def create_carbon_credits_vcs_frame() -> MetrologicalFrame:
    """Vérification déterministe L1 serial VCS. L2 épistémique désactivé par défaut."""
    return MetrologicalFrame(
        frame_id="carbon_credits_vcs_v1.0",
        version="1.0",
        domain="environmental_assets",
        metric="carbon_credit_validity",
        description=(
            "L1 déterministe : lookup serial VCS sur Verra Registry. "
            "L2 épistémique (soundness méthodologique) désactivé par défaut "
            "(ADR-012 Q3 — durée de validité on-chain ouverte)."
        ),
        parameters={
            "l1_deterministic": True,
            "l2_epistemic": False,
            "esmm_bypass": True,
        },
        required_sources=1,
    )


def create_rwa_identity_frame() -> MetrologicalFrame:
    """Frame généraliste multi-sources. ESMM optionnel si score source ambigu."""
    return MetrologicalFrame(
        frame_id="rwa_identity_v1.0",
        version="1.0",
        domain="identity_compliance",
        metric="entity_sanctions_composite",
        description=(
            "Frame généraliste combinant plusieurs sources RWA. "
            "Si score source déterministe < ambiguity_threshold, "
            "une couche ESMM peut être déclenchée (désactivé par défaut)."
        ),
        parameters={
            "ambiguity_threshold": 0.6,
            "esmm_on_ambiguity": False,
            "esmm_bypass": True,
        },
        required_sources=2,
    )


# Registre canonique — importable par pipeline.py et cli/epp_cli.py
PREDEFINED_FRAMES: Dict[str, Callable[[], "MetrologicalFrame"]] = {
    "blockchain_tps_v1.0":       create_blockchain_tps_frame,
    "general_knowledge_v1.0":    create_general_knowledge_frame,
    "compliance_sanctions_v1.0": create_compliance_sanctions_frame,
    "carbon_credits_vcs_v1.0":   create_carbon_credits_vcs_frame,
    "rwa_identity_v1.0":         create_rwa_identity_frame,
}
