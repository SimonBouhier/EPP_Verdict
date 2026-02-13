"""Tests Phase 3 — Triplet adapter: ConsensusTriplet -> dict pipeline."""

import pytest
from services.providers.mock_provider import make_synthetic_triplets
from services.esmm.triplet_adapter import adapt_consensus_triplet, adapt_all


class TestTripletAdapter:

    def test_adapt_single_triplet(self):
        """A ConsensusTriplet -> dict with all required fields."""
        triplets = make_synthetic_triplets(n=1)
        result = adapt_consensus_triplet(triplets[0])
        assert "subject" in result
        assert "predicate" in result
        assert "object" in result
        assert "consensus_score" in result
        assert "votes" in result
        assert "signature_5d" in result
        assert "epistemic_type" in result
        assert "triplet_hash" in result

    def test_relation_becomes_predicate(self):
        """triplet.relation maps to dict['predicate']."""
        triplets = make_synthetic_triplets(n=1)
        result = adapt_consensus_triplet(triplets[0])
        assert result["predicate"] == triplets[0].relation

    def test_votes_from_contributing_models(self):
        """As many votes as contributing models."""
        models = ["model-a", "model-b", "model-c"]
        triplets = make_synthetic_triplets(n=1, models=models)
        result = adapt_consensus_triplet(triplets[0])
        assert len(result["votes"]) == len(triplets[0].contributing_models)
        for vote in result["votes"]:
            assert "model_id" in vote
            assert "provider_id" in vote
            assert "agreed" in vote
            assert "confidence" in vote
            assert "architecture_family" in vote

    def test_signature_5d_present(self):
        """The 5 dimensions exist in signature_5d."""
        triplets = make_synthetic_triplets(n=1)
        result = adapt_consensus_triplet(triplets[0])
        sig = result["signature_5d"]
        assert "agreement" in sig
        assert "semantic_consistency" in sig
        assert "centrality" in sig
        assert "stability" in sig
        assert "relation_diversity" in sig

    def test_adapt_all(self):
        """List of N triplets -> list of N dicts."""
        triplets = make_synthetic_triplets(n=5)
        results = adapt_all(triplets)
        assert len(results) == 5
        for r in results:
            assert "subject" in r
            assert "predicate" in r

    def test_cochain_entry_overrides_signature(self):
        """Cochain entry provides signature_5d if available."""
        triplets = make_synthetic_triplets(n=1)
        custom_sig = {
            "agreement": 0.99,
            "semantic_consistency": 0.88,
            "centrality": 0.77,
            "stability": 0.66,
            "relation_diversity": 0.55,
        }
        cochain = {"triplet_hash": triplets[0].triplet_hash, "signature_5d": custom_sig}
        result = adapt_consensus_triplet(triplets[0], cochain_entry=cochain)
        assert result["signature_5d"] == custom_sig

    def test_infer_provider_id_with_prefix(self):
        """Model with :: prefix infers provider from prefix."""
        from services.esmm.triplet_adapter import _infer_provider_id
        assert _infer_provider_id("openai::gpt-4o") == "openai"
        assert _infer_provider_id("anthropic::claude-3") == "anthropic"
        assert _infer_provider_id("mistral:7b") == "ollama"
