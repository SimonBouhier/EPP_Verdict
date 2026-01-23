"""
ESMM Phase 2 - CONSENSUS ENGINE
================================

Multi-model voting mechanism for triplet extraction.
Aggregates triplets from multiple models and computes consensus scores.

Key Features:
- SHA256 hashing for efficient triplet comparison
- Pre-filtering by confidence threshold
- Standard deviation calculation for controversy detection
- Customizable scoring weights

Author: Lyra-ACE ESMM Protocol
"""
from __future__ import annotations

import hashlib
import statistics
import logging
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class ConsensusTriplet:
    """
    Triplet with consensus metrics from multi-model voting.

    Attributes:
        subject: Canonical subject entity
        relation: Canonical relation type
        object: Canonical object entity
        avg_confidence: Mean confidence across contributing models
        std_confidence: Standard deviation of confidences (controversy indicator)
        agreement_ratio: Ratio of models that extracted this triplet (0.0-1.0)
        consensus_score: Combined score: agreement * weight_a + confidence * weight_c
        contributing_models: List of model names that extracted this triplet
        triplet_hash: SHA256 hash for deduplication and traceability
    """
    subject: str
    relation: str
    object: str
    avg_confidence: float
    std_confidence: float
    agreement_ratio: float
    consensus_score: float
    contributing_models: List[str]
    triplet_hash: str


class ConsensusEngine:
    """
    Multi-model consensus engine for triplet extraction.

    Aggregates triplets extracted by multiple models and computes
    consensus scores based on model agreement and confidence levels.

    Optimizations:
    - Pre-filtering by confidence reduces computation
    - SHA256 hashing for O(1) triplet comparison
    - defaultdict for efficient aggregation
    - Standard deviation for controversy detection
    """

    def __init__(
        self,
        min_agreement: float = 0.5,
        scoring_weights: Tuple[float, float] = (0.6, 0.4)
    ):
        """
        Initialize consensus engine.

        Args:
            min_agreement: Minimum ratio of models that must agree (0.0-1.0)
                          Default 0.5 means majority (>50%) must agree
            scoring_weights: Tuple of (agreement_weight, confidence_weight)
                            Must sum to 1.0 for normalized scores
        """
        if not 0.0 <= min_agreement <= 1.0:
            raise ValueError("min_agreement must be between 0.0 and 1.0")

        self.min_agreement = min_agreement
        self.agreement_weight, self.confidence_weight = scoring_weights

        logger.debug(
            f"[ConsensusEngine] Initialized: min_agreement={min_agreement}, "
            f"weights=({self.agreement_weight}, {self.confidence_weight})"
        )

    def compute_consensus(
        self,
        model_results: Dict[str, List],
        pre_filter_confidence: float = 0.3
    ) -> List[ConsensusTriplet]:
        """
        Compute consensus from multi-model extraction results.

        Args:
            model_results: Dict mapping model names to lists of ExtractedTriplet
            pre_filter_confidence: Minimum confidence to consider a triplet
                                  (reduces volume before consensus)

        Returns:
            List of ConsensusTriplet sorted by consensus_score descending

        Algorithm:
        1. Pre-filter triplets below confidence threshold
        2. Hash each triplet for grouping
        3. Count model contributions per triplet
        4. Calculate agreement_ratio = count / total_models
        5. Filter by min_agreement
        6. Calculate avg_confidence and std_confidence
        7. Calculate consensus_score
        8. Sort by score descending
        """
        if not model_results:
            return []

        total_models = len(model_results)
        if total_models == 0:
            return []

        # Aggregation structure
        triplet_data: Dict[str, Dict] = defaultdict(lambda: {
            "count": 0,
            "confidences": [],
            "models": set(),
            "triplet": None
        })

        triplets_processed = 0
        triplets_filtered = 0

        # Aggregate triplets by hash
        for model, triplets in model_results.items():
            for triplet in triplets:
                triplets_processed += 1

                # Pre-filter by confidence
                confidence = getattr(triplet, 'confidence', 0.0)
                if confidence < pre_filter_confidence:
                    triplets_filtered += 1
                    continue

                # Hash for grouping
                triplet_hash = self._hash_triplet(triplet)

                triplet_data[triplet_hash]["count"] += 1
                triplet_data[triplet_hash]["confidences"].append(confidence)
                triplet_data[triplet_hash]["models"].add(model)

                # Keep reference to triplet (any one is fine, they're equivalent)
                if triplet_data[triplet_hash]["triplet"] is None:
                    triplet_data[triplet_hash]["triplet"] = triplet

        # Calculate consensus for each unique triplet
        consensus_results = []

        for triplet_hash, data in triplet_data.items():
            agreement_ratio = data["count"] / total_models

            # Filter by minimum agreement
            if agreement_ratio < self.min_agreement:
                continue

            # Calculate statistics
            confidences = data["confidences"]
            avg_confidence = statistics.mean(confidences)

            # Standard deviation (0 if only one value)
            if len(confidences) > 1:
                std_confidence = statistics.stdev(confidences)
            else:
                std_confidence = 0.0

            # Consensus score
            consensus_score = (
                agreement_ratio * self.agreement_weight +
                avg_confidence * self.confidence_weight
            )

            triplet = data["triplet"]
            consensus_results.append(ConsensusTriplet(
                subject=triplet.subject,
                relation=triplet.relation,
                object=triplet.object,
                avg_confidence=round(avg_confidence, 4),
                std_confidence=round(std_confidence, 4),
                agreement_ratio=round(agreement_ratio, 4),
                consensus_score=round(consensus_score, 4),
                contributing_models=sorted(list(data["models"])),
                triplet_hash=triplet_hash
            ))

        # Sort by consensus score descending
        consensus_results.sort(key=lambda x: x.consensus_score, reverse=True)

        logger.info(
            "[ConsensusEngine] Consensus computed",
            extra={
                "total_models": total_models,
                "triplets_processed": triplets_processed,
                "triplets_filtered": triplets_filtered,
                "unique_triplets": len(triplet_data),
                "consensus_triplets": len(consensus_results),
                "min_agreement": self.min_agreement,
                "pre_filter_confidence": pre_filter_confidence
            }
        )

        return consensus_results

    def _hash_triplet(self, triplet) -> str:
        """
        Create deterministic SHA256 hash for triplet comparison.

        Normalizes subject and object to lowercase for case-insensitive matching.
        Relation is kept as-is (should already be normalized).

        Args:
            triplet: ExtractedTriplet or any object with subject, relation, object attrs

        Returns:
            16-character hex hash
        """
        subject = getattr(triplet, 'subject', '').lower().strip()
        relation = getattr(triplet, 'relation', '').lower().strip()
        obj = getattr(triplet, 'object', '').lower().strip()

        canonical = f"{subject}|{relation}|{obj}"
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def get_controversial_triplets(
        self,
        consensus_triplets: List[ConsensusTriplet],
        std_threshold: float = 0.15
    ) -> List[ConsensusTriplet]:
        """
        Identify triplets with high confidence variance (controversial).

        These triplets had significant disagreement in confidence levels
        among contributing models, which may warrant manual review.

        Args:
            consensus_triplets: List of consensus triplets
            std_threshold: Standard deviation threshold for controversy

        Returns:
            List of controversial triplets
        """
        return [
            t for t in consensus_triplets
            if t.std_confidence >= std_threshold
        ]

    def get_high_agreement_triplets(
        self,
        consensus_triplets: List[ConsensusTriplet],
        agreement_threshold: float = 0.9
    ) -> List[ConsensusTriplet]:
        """
        Get triplets with very high model agreement.

        These triplets are highly reliable as most/all models agreed.

        Args:
            consensus_triplets: List of consensus triplets
            agreement_threshold: Minimum agreement ratio

        Returns:
            List of high-agreement triplets
        """
        return [
            t for t in consensus_triplets
            if t.agreement_ratio >= agreement_threshold
        ]


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_consensus_engine(
    min_agreement: float = 0.5,
    weight_agreement: float = 0.6,
    weight_confidence: float = 0.4
) -> ConsensusEngine:
    """
    Factory function for ConsensusEngine with validation.

    Args:
        min_agreement: Minimum model agreement ratio
        weight_agreement: Weight for agreement in scoring
        weight_confidence: Weight for confidence in scoring

    Returns:
        Configured ConsensusEngine instance
    """
    if abs(weight_agreement + weight_confidence - 1.0) > 0.001:
        logger.warning(
            f"Scoring weights don't sum to 1.0: "
            f"{weight_agreement} + {weight_confidence} = "
            f"{weight_agreement + weight_confidence}"
        )

    return ConsensusEngine(
        min_agreement=min_agreement,
        scoring_weights=(weight_agreement, weight_confidence)
    )
