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
    models_consulted: int = Field(ge=0, description="Nombre de modèles consultés (0 pour attestations déterministes ADR-012)")
    models_agreeing: int = Field(ge=0, description="Nombre de modèles en accord")
    model_votes: List[ModelVote] = Field(description="Détail des votes par modèle")

    # === SIGNATURE ÉPISTÉMIQUE 5D ===
    signature_5d: Signature5D

    # === CLASSIFICATION ===
    epistemic_type: str = Field(
        description="Type épistémique : foundational | bridge | specialized"
    )
    confidence_tier: str = Field(
        description="Tier de confiance : sandbox | proposition | validated | verified"
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

    # === TRAÇABILITÉ MÉTHODOLOGIQUE (ADR-010) ===
    consensus_meta: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Métadonnées méthodologiques du consensus (ADR-010)"
    )

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
        allowed = {
            "foundational", "bridge", "specialized", "generalist", "hybrid", "verdict",
            "deterministic",  # ADR-012 : claims via source autoritaire externe (bypass ESMM)
        }
        if v not in allowed:
            raise ValueError(f"epistemic_type must be one of {allowed}, got '{v}'")
        return v

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

    VERIFIED (>= 0.85) :
        - Consensus >= 0.85
        - Toutes conditions de VALIDATED
        - source_anchor non NULL OU validation_count >= 3

    VALIDATED (>= 0.70) :
        - Consensus >= 0.70
        - models_consulted >= 3
        - architecture_families >= 2

    PROPOSITION (>= 0.40) :
        - Consensus >= 0.40
        - models_consulted >= 2

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


# Alias for Phase 3+ — preferred name
compute_confidence_tier = derive_confidence_tier


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
    consensus_meta: Optional[Dict[str, Any]] = None,
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
        architecture_families: Nombre de familles d'architecture distinctes

    Returns:
        EpistemicAttestation cristallisée avec hash SHA-256
    """
    claim_hash = compute_claim_hash(subject, predicate, object_, metrological_frame)

    # ADR-012 : attestation déterministe requiert source_anchor_meta dans consensus_meta
    if (
        consensus_meta is not None
        and consensus_meta.get("methodology", {}).get("consensus_method")
            == "deterministic_source_v1"
        and "source_anchor_meta" not in consensus_meta
    ):
        raise ValueError(
            "crystallize: consensus_method=deterministic_source_v1 "
            "requiert consensus_meta['source_anchor_meta']"
        )

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
        consensus_meta=consensus_meta,
        metrological_frame=metrological_frame,
        source_anchor=source_anchor,
        run_id=run_id,
        question=question,
        timestamp=time.time(),
        validation_count=validation_count,
        previous_hash=previous_hash,
    )


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
