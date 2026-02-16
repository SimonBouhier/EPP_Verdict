"""Hook unique post-cristallisation — track record + tier transitions + diversity bonus."""

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
    3. Calcule et stocke le bonus de diversité architecturale (R-2.2.1)
    """
    # 1. Track record — record each model's vote
    for vote in attestation.model_votes:
        try:
            await db.record_model_prediction(
                model_id=vote.model_id,
                provider_id=vote.provider_id,
                claim_hash=attestation.claim_hash,
                predicted_confidence=vote.confidence,
                predicted_agreed=vote.agreed,
            )
        except Exception as e:
            logger.warning(f"Track record failed for {vote.model_id}: {e}")

    # 2. Tier transition — log if tier changed
    from_tier = previous_tier or "sandbox"
    to_tier = attestation.confidence_tier

    if from_tier != to_tier:
        try:
            await db.log_tier_transition(
                claim_hash=attestation.claim_hash,
                old_tier=from_tier,
                new_tier=to_tier,
                reason=f"crystallization (consensus={attestation.consensus_score:.3f})",
                run_id=attestation.run_id,
            )
        except Exception as e:
            logger.warning(f"Tier transition log failed: {e}")

    # 3. Diversity bonus (R-2.2.1, Option C — post-crystallize, ADR-005/007 safe)
    # COMMUNITY_DECISION_REQUIRED: The treatment of CONTESTED consensus
    # (ambiguity_detected=True) is deliberately left open. Possible future
    # policies include: cap confidence_tier, reduce diversity_bonus, require
    # additional debate cycles, or flag for human review. This decision
    # should be made by the open-source community, not by the founding team.
    # See ADR-009 (pending) for context.
    try:
        from services.providers.base import infer_architecture_family

        families = set(
            infer_architecture_family(vote.model_id)
            for vote in attestation.model_votes
        )
        factor = 1.1 if len(families) >= 2 else 1.0
        adjusted = min(attestation.consensus_score * factor, 1.0)

        await db.update_attestation_diversity_bonus(
            claim_hash=attestation.claim_hash,
            diversity_bonus_factor=factor,
            adjusted_consensus_score=adjusted,
        )
    except Exception as e:
        logger.warning(f"Diversity bonus update failed: {e}")
