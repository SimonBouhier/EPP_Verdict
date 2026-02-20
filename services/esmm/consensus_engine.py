"""
ESMM Phase 2 - CONSENSUS ENGINE
================================

Multi-model voting mechanism for triplet extraction.
Aggregates triplets from multiple models and computes consensus scores.

Key Features:
- SHA256 hashing for efficient triplet comparison (Pass 1)
- Semantic merge via embeddings for cross-language equivalence (Pass 2)
- Pre-filtering by confidence threshold
- Standard deviation calculation for controversy detection
- Customizable scoring weights

Author: Lyra-ACE ESMM Protocol
"""
from __future__ import annotations

import hashlib
import math
import re
import statistics
import logging
from typing import List, Dict, Set, Tuple, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from collections import defaultdict

if TYPE_CHECKING:
    from services.providers.base import EmbeddingProvider

logger = logging.getLogger(__name__)

# Semantic merge threshold — distinct from sybil detection (0.95)
SEMANTIC_MERGE_THRESHOLD = 0.85

# ---------------------------------------------------------------------------
# Relation synonym mapping — canonical forms for hash normalization
# SOURCE OF TRUTH: see relation_vocabulary.py — do NOT define local synonym groups
# TODO: Remove _LEGACY after staging validation — see PLAN_RELATION_VOCABULARY.md §3.2
# ---------------------------------------------------------------------------
from .relation_vocabulary import build_synonym_map

# Legacy groups — frozen snapshot pre-refactoring, used when use_legacy_relation_groups=true
_LEGACY_RELATION_SYNONYMS: Dict[str, str] = {}
_LEGACY_RELATION_GROUPS = {
    "USES": ["uses", "requires", "needs", "employs", "utilizes", "utilises"],
    "IS_A": ["is_a", "type_of", "is_type", "is_type_of", "kind_of", "instance_of"],
    "HAS": ["has", "contains", "includes", "possesses", "owns"],
    "PART_OF": ["part_of", "component_of", "belongs_to", "member_of", "subset_of"],
    "CAUSES": ["causes", "leads_to", "results_in", "produces", "triggers"],
    "ENABLES": ["enables", "allows", "permits", "facilitates", "supports"],
    "PREVENTS": ["prevents", "blocks", "inhibits", "stops", "hinders"],
    "RELATES_TO": ["relates_to", "related_to", "associated_with", "connected_to", "linked_to"],
    "DEPENDS_ON": ["depends_on", "relies_on", "based_on", "built_on"],
    "PROVIDES": ["provides", "offers", "supplies", "gives", "delivers"],
}
for _canonical, _synonyms in _LEGACY_RELATION_GROUPS.items():
    for _syn in _synonyms:
        _LEGACY_RELATION_SYNONYMS[_syn] = _canonical


def _get_relation_synonyms() -> Dict[str, str]:
    """Return active synonym map based on config flag."""
    try:
        from services.config_loader import get_section
        esmm_cfg = get_section("esmm", {})
        if esmm_cfg.get("use_legacy_relation_groups", True):
            return _LEGACY_RELATION_SYNONYMS
    except Exception:
        pass  # Config unavailable (tests, CLI) → use new
    return build_synonym_map(uppercase_canonicals=True)


# WARNING: _RELATION_SYNONYMS is frozen at import time. Monkeypatching
# use_legacy_relation_groups after import has NO EFFECT on this module.
# fingerprint_match.py reads the flag per-call — this asymmetry is intentional
# (consensus hashing must be deterministic within a process lifetime).
_RELATION_SYNONYMS: Dict[str, str] = _get_relation_synonyms()

# Entity abbreviation mapping — common short forms
_ENTITY_SYNONYMS: Dict[str, str] = {
    "pow": "proof of work",
    "pos": "proof of stake",
    "dpos": "delegated proof of stake",
    "defi": "decentralized finance",
    "nft": "non-fungible token",
    "dao": "decentralized autonomous organization",
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "llm": "large language model",
}

# Word-level synonyms for fuzzy entity matching
_WORD_SYNONYMS: Dict[str, str] = {
    "computational": "computing",
    "decentralised": "decentralized",
    "utilise": "use",
    "utilises": "uses",
    "utilisation": "use",
    "verification": "validation",
    "verify": "validate",
    "algorithm": "mechanism",
    "algorithms": "mechanisms",
}


def _normalize_text(text: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _normalize_entity(entity: str) -> str:
    """Normalize an entity: lowercase + collapse whitespace + synonym expansion + word synonyms."""
    normalized = _normalize_text(entity)
    # Replace underscores with spaces for matching
    lookup = normalized.replace("_", " ")
    # Check full-entity synonym first
    if lookup in _ENTITY_SYNONYMS:
        return _ENTITY_SYNONYMS[lookup]
    # Apply word-level synonyms
    words = normalized.split()
    words = [_WORD_SYNONYMS.get(w, w) for w in words]
    return " ".join(words)


def _normalize_relation(relation: str) -> str:
    """Normalize a relation: lowercase + collapse whitespace + synonym mapping."""
    normalized = _normalize_text(relation)
    # Replace spaces with underscores for lookup
    lookup = normalized.replace(" ", "_")
    return _RELATION_SYNONYMS.get(lookup, normalized)


def normalize_triplet(subject: str, relation: str, obj: str) -> Tuple[str, str, str]:
    """Normalize a triplet to canonical form for hashing.

    - lowercase + strip + collapse whitespace
    - entity synonym expansion (PoW -> proof of work, etc.)
    - relation synonym mapping (uses/requires/needs -> USES, etc.)

    Returns:
        Tuple (normalized_subject, canonical_relation, normalized_object)
    """
    return (
        _normalize_entity(subject),
        _normalize_relation(relation),
        _normalize_entity(obj),
    )


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _get_triplet_fields(triplet) -> Tuple[str, str, str]:
    """Extract (subject, relation, object) from a triplet (dict or object)."""
    if isinstance(triplet, dict):
        return (
            triplet.get('subject', ''),
            triplet.get('relation', ''),
            triplet.get('object', ''),
        )
    return (
        getattr(triplet, 'subject', ''),
        getattr(triplet, 'relation', ''),
        getattr(triplet, 'object', ''),
    )


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
        variations: All alternative formulations from the semantic cluster
        ambiguity_detected: True if the cluster contained tied/close-score candidates
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
    variations: List[Tuple[str, str, str]] = field(default_factory=list)
    ambiguity_detected: bool = False
    # COMMUNITY_DECISION_REQUIRED: The treatment of CONTESTED consensus
    # (ambiguity_detected=True) is deliberately left open. Possible future
    # policies include: cap confidence_tier, reduce diversity_bonus, require
    # additional debate cycles, or flag for human review. This decision
    # should be made by the open-source community, not by the founding team.
    # See ADR-009 (pending) for context.


@dataclass
class ConsensusResult:
    """
    Result of consensus computation with diagnostics (ADR-010).

    Attributes:
        triplets: List of ConsensusTriplet sorted by score descending
        triplets_before_consensus: Unique triplets before min_agreement filter
        triplets_after_consensus: Triplets passing the min_agreement filter
        vote_entropy: Shannon entropy of the vote distribution (0 = unanimity)
        semantic_dispersion: Mean pairwise cosine distance (None if no embeddings)
    """
    triplets: List[ConsensusTriplet]
    triplets_before_consensus: int
    triplets_after_consensus: int
    vote_entropy: float
    semantic_dispersion: Optional[float] = None


def _compute_vote_entropy(triplet_data: Dict[str, Dict], total_models: int) -> float:
    """Compute Shannon entropy of the aggregate vote distribution.

    For each unique triplet, each model either contributed or did not.
    Entropy is computed on the aggregate (agreed, total) ratio.

    Returns 0.0 for unanimous agreement or empty data.
    """
    if total_models == 0 or not triplet_data:
        return 0.0

    total_slots = len(triplet_data) * total_models
    agreed_slots = sum(len(data["models"]) for data in triplet_data.values())

    if total_slots == 0:
        return 0.0

    p = agreed_slots / total_slots
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return round(-(p * math.log2(p) + (1 - p) * math.log2(1 - p)), 6)


class ConsensusEngine:
    """
    Multi-model consensus engine for triplet extraction.

    Aggregates triplets extracted by multiple models and computes
    consensus scores based on model agreement and confidence levels.

    Two-pass architecture:
    - Pass 1: Exact hash after normalize_triplet() (free, 0 latency)
    - Pass 2: Semantic merge via embeddings (optional, requires provider)

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

    async def compute_consensus(
        self,
        model_results: Dict[str, List],
        pre_filter_confidence: float = 0.3,
        model_weights: Optional[Dict[str, float]] = None,
        embedding_provider: Optional["EmbeddingProvider"] = None,
    ) -> ConsensusResult:
        """
        Compute consensus from multi-model extraction results.

        Two-pass architecture:
        - Pass 1: Group by exact hash (after normalize_triplet)
        - Pass 2: If embedding_provider given, cluster remaining singletons
                   by cosine similarity > SEMANTIC_MERGE_THRESHOLD

        Args:
            model_results: Dict mapping model names to lists of ExtractedTriplet
            pre_filter_confidence: Minimum confidence to consider a triplet
            model_weights: Optional Brier-based model quality weights
            embedding_provider: Optional embedding provider for Pass 2
                               (semantic merge). If None, Pass 2 is skipped.

        Returns:
            ConsensusResult with triplets and diagnostics (ADR-010)
        """
        _empty = ConsensusResult(
            triplets=[], triplets_before_consensus=0,
            triplets_after_consensus=0, vote_entropy=0.0,
        )
        if not model_results:
            return _empty

        total_models = len(model_results)
        if total_models == 0:
            return _empty

        # Aggregation structure — track per-model contributions for weighting
        triplet_data: Dict[str, Dict] = defaultdict(lambda: {
            "count": 0,
            "confidences": [],
            "models": set(),
            "model_confidences": {},
            "triplet": None,
            "all_triplets": [],
        })

        triplets_processed = 0
        triplets_filtered = 0

        # Pass 1: Aggregate triplets by exact hash
        for model, triplets in model_results.items():
            for triplet in triplets:
                triplets_processed += 1

                # Pre-filter by confidence
                confidence = (
                    triplet.get('confidence', 0.0) if isinstance(triplet, dict)
                    else getattr(triplet, 'confidence', 0.0)
                )
                if confidence < pre_filter_confidence:
                    triplets_filtered += 1
                    continue

                # Hash for grouping
                triplet_hash = self._hash_triplet(triplet)

                triplet_data[triplet_hash]["count"] += 1
                triplet_data[triplet_hash]["confidences"].append(confidence)
                triplet_data[triplet_hash]["models"].add(model)
                triplet_data[triplet_hash]["model_confidences"][model] = confidence
                triplet_data[triplet_hash]["all_triplets"].append(triplet)

                # Keep reference to triplet (any one is fine, they're equivalent)
                if triplet_data[triplet_hash]["triplet"] is None:
                    triplet_data[triplet_hash]["triplet"] = triplet

        # Pass 2: Semantic merge via embeddings (if provider available)
        semantic_dispersion = None
        if embedding_provider is not None:
            triplet_data, semantic_dispersion = await self._semantic_merge(
                triplet_data, embedding_provider
            )

        # Determine if weighted mode is active
        use_weights = model_weights is not None

        # Pre-compute total weight sum for agreement ratio denominator
        if use_weights:
            total_weight = sum(
                model_weights.get(m, 1.0) for m in model_results.keys()
            )
        else:
            total_weight = float(total_models)

        # Calculate consensus for each unique triplet
        consensus_results = []

        for triplet_hash, data in triplet_data.items():
            if use_weights:
                # Weighted agreement: sum of contributing model weights / total weights
                contributing_weight = sum(
                    model_weights.get(m, 1.0) for m in data["models"]
                )
                agreement_ratio = contributing_weight / total_weight if total_weight > 0 else 0.0

                # Weighted avg_confidence
                mc = data["model_confidences"]
                weight_sum = sum(model_weights.get(m, 1.0) for m in mc)
                if weight_sum > 0:
                    avg_confidence = sum(
                        mc[m] * model_weights.get(m, 1.0) for m in mc
                    ) / weight_sum
                else:
                    avg_confidence = statistics.mean(data["confidences"])
            else:
                agreement_ratio = data["count"] / total_models
                avg_confidence = statistics.mean(data["confidences"])

            # Filter by minimum agreement
            if agreement_ratio < self.min_agreement:
                continue

            # Standard deviation (0 if only one value) — unweighted, descriptive
            confidences = data["confidences"]
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
            subject, relation, obj = _get_triplet_fields(triplet)

            # Build variations list and detect ambiguity
            variations = data.get("variations", [])
            ambiguity_detected = data.get("ambiguity_detected", False)

            consensus_results.append(ConsensusTriplet(
                subject=subject,
                relation=relation,
                object=obj,
                avg_confidence=round(avg_confidence, 4),
                std_confidence=round(std_confidence, 4),
                agreement_ratio=round(agreement_ratio, 4),
                consensus_score=round(consensus_score, 4),
                contributing_models=sorted(list(data["models"])),
                triplet_hash=triplet_hash,
                variations=variations,
                ambiguity_detected=ambiguity_detected,
            ))

        # Sort by consensus score descending
        consensus_results.sort(key=lambda x: x.consensus_score, reverse=True)

        # ADR-010: Compute diagnostics
        triplets_before = len(triplet_data)
        triplets_after = len(consensus_results)
        vote_entropy = _compute_vote_entropy(triplet_data, total_models)

        logger.info(
            f"[ConsensusEngine] Consensus computed: "
            f"{triplets_after}/{triplets_before} unique triplets passed "
            f"(min_agreement={self.min_agreement}, models={total_models}, "
            f"processed={triplets_processed}, filtered={triplets_filtered}, "
            f"semantic_merge={'on' if embedding_provider else 'off'})",
            extra={
                "total_models": total_models,
                "triplets_processed": triplets_processed,
                "triplets_filtered": triplets_filtered,
                "unique_triplets": triplets_before,
                "consensus_triplets": triplets_after,
                "min_agreement": self.min_agreement,
                "pre_filter_confidence": pre_filter_confidence,
                "weighted": use_weights,
                "semantic_merge": embedding_provider is not None,
            }
        )

        return ConsensusResult(
            triplets=consensus_results,
            triplets_before_consensus=triplets_before,
            triplets_after_consensus=triplets_after,
            vote_entropy=vote_entropy,
            semantic_dispersion=semantic_dispersion,
        )

    async def _semantic_merge(
        self,
        triplet_data: Dict[str, Dict],
        embedding_provider: "EmbeddingProvider",
    ) -> Tuple[Dict[str, Dict], float]:
        """
        Pass 2: Cluster triplets by embedding cosine similarity.

        Triplets with sim > SEMANTIC_MERGE_THRESHOLD are merged.
        The canonical representative is chosen by:
        - Most votes (highest count) wins
        - On tie: shortest text form (deterministic)

        Merged entries track all variations and flag ambiguity when tied.

        Args:
            triplet_data: Hash-grouped triplet data from Pass 1
            embedding_provider: Provider for computing embeddings

        Returns:
            Tuple of (updated triplet_data, semantic_dispersion)
        """
        hashes = list(triplet_data.keys())
        if len(hashes) <= 1:
            return triplet_data, 0.0

        # Build triplet text for each hash group
        hash_texts: Dict[str, str] = {}
        for h in hashes:
            triplet = triplet_data[h]["triplet"]
            s, r, o = _get_triplet_fields(triplet)
            hash_texts[h] = f"{s} {r} {o}"

        # Compute embeddings for all unique triplet texts
        texts = [hash_texts[h] for h in hashes]
        embeddings: Dict[str, List[float]] = {}
        for i, h in enumerate(hashes):
            embeddings[h] = await embedding_provider.embed(texts[i])

        # ADR-010: Compute semantic dispersion (mean pairwise cosine distance)
        pairwise_distances = []
        for i in range(len(hashes)):
            for j in range(i + 1, len(hashes)):
                sim = _cosine_similarity(embeddings[hashes[i]], embeddings[hashes[j]])
                pairwise_distances.append(1.0 - sim)
        semantic_dispersion = round(
            statistics.mean(pairwise_distances), 6
        ) if pairwise_distances else 0.0

        # Find clusters by pairwise similarity
        merged: Set[str] = set()
        merge_groups: List[List[str]] = []

        for i in range(len(hashes)):
            if hashes[i] in merged:
                continue
            group = [hashes[i]]
            for j in range(i + 1, len(hashes)):
                if hashes[j] in merged:
                    continue
                sim = _cosine_similarity(embeddings[hashes[i]], embeddings[hashes[j]])
                if sim >= SEMANTIC_MERGE_THRESHOLD:
                    group.append(hashes[j])
                    merged.add(hashes[j])
            if len(group) > 1:
                merge_groups.append(group)

        # Apply merges
        for group in merge_groups:
            # Pick canonical representative: most votes, then shortest text
            group.sort(key=lambda h: (
                -triplet_data[h]["count"],
                len(hash_texts[h]),
            ))
            canonical_hash = group[0]
            canonical_data = triplet_data[canonical_hash]

            # Collect all variations from the group
            all_variations: List[Tuple[str, str, str]] = []
            for h in group:
                triplet = triplet_data[h]["triplet"]
                s, r, o = _get_triplet_fields(triplet)
                all_variations.append((s, r, o))

            # Detect ambiguity: tied vote counts between candidates
            counts = [triplet_data[h]["count"] for h in group]
            max_count = max(counts)
            tied = counts.count(max_count) > 1
            canonical_data["ambiguity_detected"] = tied
            canonical_data["variations"] = all_variations

            # Merge data from non-canonical entries into canonical
            for h in group[1:]:
                other = triplet_data[h]
                canonical_data["count"] += other["count"]
                canonical_data["confidences"].extend(other["confidences"])
                canonical_data["models"].update(other["models"])
                canonical_data["model_confidences"].update(other["model_confidences"])
                canonical_data["all_triplets"].extend(other["all_triplets"])

            # Remove merged entries
            for h in group[1:]:
                del triplet_data[h]

        logger.debug(
            f"[ConsensusEngine] Semantic merge: {len(merge_groups)} clusters merged "
            f"from {len(hashes)} unique hashes, dispersion={semantic_dispersion}"
        )

        return triplet_data, semantic_dispersion

    def _hash_triplet(self, triplet) -> str:
        """
        Create deterministic SHA256 hash for triplet comparison.

        Uses normalize_triplet() for synonym mapping + whitespace normalization
        so that equivalent formulations (PoW/proof of work, uses/requires) hash
        identically.

        Args:
            triplet: ExtractedTriplet or any object with subject, relation, object attrs

        Returns:
            16-character hex hash
        """
        raw_subject, raw_relation, raw_obj = _get_triplet_fields(triplet)
        subject, relation, obj = normalize_triplet(raw_subject, raw_relation, raw_obj)

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
