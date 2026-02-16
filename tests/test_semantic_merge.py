"""
Tests Phase 4.8 — Semantic merge & ambiguity preservation.

RED-GREEN-FIX : ces tests DOIVENT échouer avant implémentation.

Vérifie que :
1. Triplets cross-langue fusionnent via embedding similarity > 0.85.
2. Tied votes preserve variations + ambiguity_detected.
3. Triplets sémantiquement distincts ne fusionnent pas.
4. Sans embedding provider, comportement identique à l'existant.
"""
import hashlib
import pytest

from services.esmm.consensus_engine import ConsensusEngine, ConsensusTriplet


# ---------------------------------------------------------------------------
# Mock deterministic embedding provider (hash-based vectors)
# ---------------------------------------------------------------------------

class MockDeterministicEmbeddingProvider:
    """Embedding provider that generates deterministic vectors from text hash.

    Same text -> same vector -> cosine = 1.0
    Different text -> different vector -> cosine < 1.0

    For testing semantic merge, we use controlled vectors:
    - "similar" texts are given manually close vectors via a lookup table.
    """

    def __init__(self, similarity_overrides: dict[tuple[str, str], float] | None = None):
        """
        Args:
            similarity_overrides: Dict mapping (text_a, text_b) pairs to desired
                cosine similarity. Used to control which triplets should merge.
        """
        self._overrides = similarity_overrides or {}
        self._vectors: dict[str, list[float]] = {}
        self._dim = 64

    async def embed(self, text: str) -> list[float]:
        """Generate a deterministic vector based on text hash."""
        if text in self._vectors:
            return self._vectors[text]
        # Generate from hash
        h = hashlib.sha256(text.encode()).digest()
        vector = [b / 255.0 for b in h[:self._dim]]
        # Pad if needed
        while len(vector) < self._dim:
            vector.append(0.0)
        self._vectors[text] = vector
        return vector

    def get_dimension(self) -> int:
        return self._dim

    def get_model_id(self) -> str:
        return "mock-deterministic"

    def get_provider_id(self) -> str:
        return "mock"


class MockSimilarEmbeddingProvider:
    """Provider that returns nearly-identical vectors for designated 'similar' groups.

    Groups of texts share a base vector (cosine > 0.99), while texts in
    different groups get distinct vectors (cosine < 0.5).
    """

    def __init__(self, similar_groups: list[list[str]]):
        """
        Args:
            similar_groups: List of lists. Texts in the same inner list
                are considered semantically equivalent.
        """
        self._dim = 64
        self._text_to_group: dict[str, int] = {}
        for i, group in enumerate(similar_groups):
            for text in group:
                self._text_to_group[text] = i

    async def embed(self, text: str) -> list[float]:
        group_id = self._text_to_group.get(text)
        if group_id is not None:
            # Base vector for this group — deterministic from group_id
            base = [(group_id * 17 + i) % 256 / 255.0 for i in range(self._dim)]
            # Tiny perturbation from text hash for slight variation within group
            h = hashlib.sha256(text.encode()).digest()
            return [base[i] + (h[i % len(h)] / 255.0) * 0.001 for i in range(self._dim)]
        # Unknown text — random-ish vector far from any group
        h = hashlib.sha256(text.encode()).digest()
        return [b / 255.0 for b in h[:self._dim]]

    def get_dimension(self) -> int:
        return self._dim

    def get_model_id(self) -> str:
        return "mock-similar"

    def get_provider_id(self) -> str:
        return "mock"


# ---------------------------------------------------------------------------
# Helper: create triplet dict
# ---------------------------------------------------------------------------

def _triplet(s: str, r: str, o: str, conf: float = 0.8) -> dict:
    return {"subject": s, "relation": r, "object": o, "confidence": conf}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSemanticMerge:
    """Phase 4.8 RED — semantic merge via embeddings."""

    @pytest.mark.asyncio
    async def test_semantic_merge_cross_language(self):
        """Triplets in different languages about the same concept should merge."""
        engine = ConsensusEngine(min_agreement=0.5)

        # _semantic_merge builds text as f"{subject} {relation} {object}" from raw fields
        # These must match what _get_triplet_fields returns joined with spaces
        t_en = "proof of work requires computing power"
        t_fr = "preuve de travail requires puissance de calcul"

        provider = MockSimilarEmbeddingProvider(
            similar_groups=[[t_en, t_fr]]
        )

        model_results = {
            "model_a": [_triplet("proof of work", "requires", "computing power")],
            "model_b": [_triplet("preuve de travail", "requires", "puissance de calcul")],
            "model_c": [_triplet("bitcoin", "is_a", "cryptocurrency")],
        }

        results = (await engine.compute_consensus(
            model_results,
            embedding_provider=provider,
        )).triplets

        # The two PoW triplets should merge → agreement >= 2/3
        pow_triplets = [t for t in results if "work" in t.subject or "travail" in t.subject]
        assert len(pow_triplets) >= 1, (
            f"Expected merged PoW triplet, got {len(pow_triplets)} results: "
            f"{[(t.subject, t.relation, t.object) for t in results]}"
        )
        assert pow_triplets[0].agreement_ratio >= 0.5

    @pytest.mark.asyncio
    async def test_ambiguity_preservation(self):
        """Tied votes must preserve all variations and flag ambiguity."""
        engine = ConsensusEngine(min_agreement=0.5)

        # _semantic_merge builds text as f"{subject} {relation} {object}"
        t_a = "proof of work requires computing power"
        t_b = "proof of work requires computational resources"

        provider = MockSimilarEmbeddingProvider(
            similar_groups=[[t_a, t_b]]
        )

        model_results = {
            "model_a": [_triplet("proof of work", "requires", "computing power")],
            "model_b": [_triplet("proof of work", "requires", "computational resources")],
        }

        results = (await engine.compute_consensus(
            model_results,
            embedding_provider=provider,
        )).triplets

        assert len(results) >= 1
        result = results[0]
        assert result.ambiguity_detected is True, (
            f"Expected ambiguity_detected=True for tied merge"
        )
        assert len(result.variations) >= 2, (
            f"Expected >= 2 variations, got {result.variations}"
        )

    @pytest.mark.asyncio
    async def test_semantic_merge_no_false_merge(self):
        """Triplets about different concepts must NOT merge."""
        engine = ConsensusEngine(min_agreement=0.3)

        # Two completely different triplets
        provider = MockDeterministicEmbeddingProvider()

        model_results = {
            "model_a": [_triplet("proof of work", "requires", "computing power")],
            "model_b": [_triplet("ice cream", "has_a", "flavor")],
        }

        results = (await engine.compute_consensus(
            model_results,
            embedding_provider=provider,
        )).triplets

        # They should remain separate (each with agreement 1/2 = 0.5 > 0.3)
        assert len(results) >= 2, (
            f"Different triplets should NOT merge, got {len(results)}: "
            f"{[(t.subject, t.object) for t in results]}"
        )

    @pytest.mark.asyncio
    async def test_consensus_without_embeddings(self):
        """Without embedding provider, consensus works as before (hash only)."""
        engine = ConsensusEngine(min_agreement=0.3)

        model_results = {
            "model_a": [_triplet("bitcoin", "is_a", "cryptocurrency")],
            "model_b": [_triplet("bitcoin", "is_a", "cryptocurrency")],
        }

        # No embedding_provider → passe 2 skipped
        results = (await engine.compute_consensus(model_results)).triplets

        assert len(results) == 1
        for t in results:
            assert t.ambiguity_detected is False
            assert t.variations == []
