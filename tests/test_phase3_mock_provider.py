"""Tests Phase 3 — MockProvider and synthetic triplets."""

import asyncio
import pytest

from services.providers.mock_provider import MockProvider, make_synthetic_triplets, RESPONSE_SETS
from services.providers.base import StructuredQuery, StructuredResponse, ModelMetadata


def _run(coro):
    """Helper to run async in sync tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestMockProvider:

    def test_mock_provider_generate(self):
        """Returns a non-empty StructuredResponse."""
        provider = MockProvider()
        query = StructuredQuery(messages=[{"role": "user", "content": "test"}])
        resp = _run(provider.generate(query))
        assert isinstance(resp, StructuredResponse)
        assert resp.success is True
        assert len(resp.text) > 0
        assert resp.model == "mock-model-7b"

    def test_mock_provider_cycles_responses(self):
        """Different responses on successive calls."""
        provider = MockProvider()
        query = StructuredQuery(messages=[{"role": "user", "content": "test"}])
        r1 = _run(provider.generate(query))
        r2 = _run(provider.generate(query))
        r3 = _run(provider.generate(query))
        # With 3 responses in default set, r1 and r4 should match
        r4 = _run(provider.generate(query))
        assert r1.text != r2.text
        assert r2.text != r3.text
        assert r1.text == r4.text  # Cycles back

    def test_mock_provider_metadata(self):
        """Returns valid ModelMetadata."""
        provider = MockProvider(model_id="test-model", provider_id="test-provider")
        meta = provider.get_metadata()
        assert isinstance(meta, ModelMetadata)
        assert meta.model_id == "test-model"
        assert meta.provider_id == "test-provider"
        assert meta.context_window > 0

    def test_mock_provider_different_response_sets(self):
        """'default' and 'bitcoin' produce different responses."""
        query = StructuredQuery(messages=[{"role": "user", "content": "test"}])
        p_default = MockProvider(response_set="default")
        p_bitcoin = MockProvider(response_set="bitcoin")
        r_default = _run(p_default.generate(query))
        r_bitcoin = _run(p_bitcoin.generate(query))
        assert r_default.text != r_bitcoin.text

    def test_mock_provider_health_check(self):
        """Health check returns healthy status."""
        provider = MockProvider()
        result = _run(provider.health_check())
        assert result["status"] == "healthy"

    def test_mock_provider_list_models(self):
        """list_models returns the configured model."""
        provider = MockProvider(model_id="my-model")
        models = _run(provider.list_models())
        assert "my-model" in models


class TestSyntheticTriplets:

    def test_synthetic_triplets_default(self):
        """3 triplets with non-empty fields."""
        triplets = make_synthetic_triplets()
        assert len(triplets) == 3
        for t in triplets:
            assert t.subject
            assert t.relation
            assert t.object
            assert 0 <= t.consensus_score <= 1.0
            assert len(t.contributing_models) >= 2
            assert t.triplet_hash

    def test_synthetic_triplets_custom_count(self):
        """n=5 returns 5 triplets."""
        triplets = make_synthetic_triplets(n=5)
        assert len(triplets) == 5

    def test_synthetic_triplets_unique_hashes(self):
        """All hashes are different."""
        triplets = make_synthetic_triplets(n=10)
        hashes = [t.triplet_hash for t in triplets]
        assert len(set(hashes)) == len(hashes)

    def test_synthetic_triplets_deterministic(self):
        """Same input produces same output."""
        t1 = make_synthetic_triplets(n=3, base_consensus=0.8)
        t2 = make_synthetic_triplets(n=3, base_consensus=0.8)
        for a, b in zip(t1, t2):
            assert a.triplet_hash == b.triplet_hash
            assert a.consensus_score == b.consensus_score

    def test_synthetic_triplets_custom_models(self):
        """Custom model list is used."""
        models = ["model-a", "model-b"]
        triplets = make_synthetic_triplets(n=2, models=models)
        for t in triplets:
            assert all(m in models for m in t.contributing_models)
