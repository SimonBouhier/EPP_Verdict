"""R-2.2.2 — Détection de réponses quasi-identiques via embeddings.

Avant le consensus, les réponses brutes des modèles sont embeddées.
Si deux réponses ont une similarité cosinus > seuil, la seconde voit
son poids effectif divisé par 2 (penalty_factor = 0.5).

Ce n'est PAS une exclusion — c'est une pondération. Un modèle Sybil
vote toujours, mais son influence est réduite proportionnellement.
"""

import logging
import math
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from services.providers.base import EmbeddingProvider

logger = logging.getLogger("esmm.response_deduplicator")


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


async def detect_similar_responses(
    responses: Dict[str, str],
    embedding_provider: "EmbeddingProvider",
    similarity_threshold: float = 0.95,
    penalty_factor: float = 0.5,
) -> Dict[str, float]:
    """Detect quasi-identical responses and return penalty factors.

    Args:
        responses: Dict {model_id: raw_response_text}
        embedding_provider: Provider to generate embeddings
        similarity_threshold: Cosine similarity above which responses are
                             considered quasi-identical (default 0.95)
        penalty_factor: Penalty applied to duplicate models (default 0.5)

    Returns:
        Dict {model_id: penalty_factor} where 1.0 = no penalty, <1.0 = penalized.
        The first model in a similar pair keeps 1.0; the second gets the penalty.
    """
    if len(responses) <= 1:
        return {m: 1.0 for m in responses}

    model_ids = list(responses.keys())
    texts = [responses[m] for m in model_ids]

    # Embed all responses
    embeddings = await embedding_provider.embed_batch(texts)

    # Initialize all penalties to 1.0 (no penalty)
    penalties: Dict[str, float] = {m: 1.0 for m in model_ids}

    # Pairwise comparison — first occurrence wins, duplicates penalized
    penalized = set()
    for i in range(len(model_ids)):
        if model_ids[i] in penalized:
            continue
        for j in range(i + 1, len(model_ids)):
            if model_ids[j] in penalized:
                continue
            sim = _cosine_similarity(embeddings[i], embeddings[j])
            if sim >= similarity_threshold:
                penalties[model_ids[j]] = penalty_factor
                penalized.add(model_ids[j])
                logger.info(
                    f"Similar responses detected: {model_ids[i]} ↔ {model_ids[j]} "
                    f"(cosine={sim:.4f} ≥ {similarity_threshold})"
                )

    return penalties
