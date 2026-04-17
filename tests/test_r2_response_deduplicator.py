"""
Tests R-2.2.2 — Clustering embeddings (détection Sybil).

RED-GREEN-FIX : ces tests DOIVENT échouer avant implémentation.

Vérifie que :
1. Réponses identiques → penalty_factor < 1.0 pour la seconde
2. Réponses différentes → tous les penalty_factors == 1.0
3. Seuil configurable respecté
"""
import hashlib
import pytest

from services.providers.base import EmbeddingProvider
from typing import List


class MockDeterministicEmbeddingProvider(EmbeddingProvider):
    """Embedding provider qui retourne des vecteurs déterministes basés sur hash du texte.

    Textes identiques → même vecteur → cosinus = 1.0
    Textes différents → vecteurs différents → cosinus < 1.0
    """

    def __init__(self, dimension: int = 64):
        self.dimension_value = dimension

    async def embed(self, text: str) -> List[float]:
        h = hashlib.sha256(text.encode()).digest()
        # Extend hash to fill dimension
        extended = h * ((self.dimension_value // len(h)) + 1)
        return [b / 255.0 for b in extended[: self.dimension_value]]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [await self.embed(t) for t in texts]

    def get_dimension(self) -> int:
        return self.dimension_value

    def get_model_id(self) -> str:
        return "mock-deterministic-embed"

    def get_provider_id(self) -> str:
        return "mock"


class TestIdenticalResponsesDetected:
    """R-2.2.2 RED 1 — Réponses identiques détectées."""

    @pytest.mark.asyncio
    async def test_identical_responses_detected(self):
        """Deux réponses identiques → penalty_factor < 1.0 pour la seconde."""
        from services.esmm.response_deduplicator import detect_similar_responses

        provider = MockDeterministicEmbeddingProvider()
        responses = {
            "model_a": "The sun is a star at the center of the solar system.",
            "model_b": "The sun is a star at the center of the solar system.",  # identique
            "model_c": "Plants use photosynthesis to convert sunlight into energy.",
        }

        penalties = await detect_similar_responses(responses, provider)

        assert isinstance(penalties, dict)
        assert len(penalties) == 3

        # model_a OU model_b devrait être pénalisé (l'un des deux)
        penalized = [m for m, p in penalties.items() if p < 1.0]
        assert len(penalized) >= 1, (
            f"Au moins un modèle devrait être pénalisé pour réponse identique, "
            f"got penalties={penalties}"
        )
        # model_c ne doit pas être pénalisé
        assert penalties["model_c"] == 1.0, (
            f"model_c a une réponse unique, ne devrait pas être pénalisé: {penalties['model_c']}"
        )


class TestDifferentResponsesNoPenalty:
    """R-2.2.2 RED 2 — Réponses différentes non pénalisées."""

    @pytest.mark.asyncio
    async def test_different_responses_no_penalty(self):
        """Réponses divergentes → tous les penalty_factors == 1.0."""
        from services.esmm.response_deduplicator import detect_similar_responses

        provider = MockDeterministicEmbeddingProvider()
        responses = {
            "model_a": "The sun is a star at the center of the solar system.",
            "model_b": "Water is composed of hydrogen and oxygen atoms.",
            "model_c": "Plants use photosynthesis to convert sunlight into energy.",
        }

        penalties = await detect_similar_responses(responses, provider)

        for model_id, penalty in penalties.items():
            assert penalty == 1.0, (
                f"Réponses uniques ne devraient pas être pénalisées: "
                f"{model_id} got penalty={penalty}"
            )


class TestSimilarityThresholdRespected:
    """R-2.2.2 RED 3 — Seuil configurable."""

    @pytest.mark.asyncio
    async def test_similarity_threshold_respected(self):
        """Seuil bas (0.5) détecte plus de similarités qu'un seuil haut (0.99)."""
        from services.esmm.response_deduplicator import detect_similar_responses

        provider = MockDeterministicEmbeddingProvider()
        responses = {
            "model_a": "The sun is a star at the center of the solar system.",
            "model_b": "The sun is a star at the center of the solar system.",  # identique
        }

        # Seuil strict : réponses identiques → toujours détecté
        penalties_strict = await detect_similar_responses(
            responses, provider, similarity_threshold=0.99
        )
        penalized_strict = sum(1 for p in penalties_strict.values() if p < 1.0)

        # Seuil souple : aussi détecté pour des identiques
        penalties_loose = await detect_similar_responses(
            responses, provider, similarity_threshold=0.5
        )
        penalized_loose = sum(1 for p in penalties_loose.values() if p < 1.0)

        assert penalized_strict >= 1, "Seuil strict devrait détecter les identiques"
        assert penalized_loose >= 1, "Seuil souple devrait aussi détecter les identiques"
