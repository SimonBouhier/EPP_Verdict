"""Tests Phase 3 — Integration end-to-end + import consistency."""

import asyncio
import os
import tempfile
import pytest
from unittest.mock import patch, AsyncMock
from pathlib import Path


def _run(coro):
    """Helper to run async in sync tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _make_temp_db():
    """Create a temp DB, closing any prior pool."""
    from database.engine import ISpaceDB
    from database.pool import close_pool

    await close_pool()

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = ISpaceDB(db_path)
    await db.initialize()
    return db, db_path


async def _cleanup_db():
    """Close DB pool to release file locks."""
    from database.pool import close_pool
    await close_pool()


class TestImportsConsistency:
    """Verify that all Phase 3 imports work."""

    def test_pipeline_imports(self):
        from services.esmm.pipeline import run_pipeline, PipelineConfig, PipelineResult
        assert callable(run_pipeline)

    def test_orchestrator_imports(self):
        from services.esmm.orchestrator import ESMMOrchestrator, ESMMRunConfig, ESMMRunResult
        assert ESMMRunResult is not None

    def test_mock_provider_imports(self):
        from services.providers.mock_provider import MockProvider, make_synthetic_triplets
        assert callable(make_synthetic_triplets)

    def test_config_loader_imports(self):
        from services.config_loader import get_config, get_section, load_config, reset_config
        assert callable(load_config)

    def test_adapter_imports(self):
        from services.esmm.triplet_adapter import adapt_consensus_triplet, adapt_all
        assert callable(adapt_consensus_triplet)

    def test_seeder_imports(self):
        from services.esmm.question_seeder import extract_seed_concepts
        assert callable(extract_seed_concepts)

    def test_hook_imports(self):
        from services.esmm.post_crystallization import post_crystallization_hook
        assert callable(post_crystallization_hook)

    def test_attestation_imports(self):
        from services.esmm.attestation import (
            EpistemicAttestation, crystallize, derive_confidence_tier,
            compute_confidence_tier,
        )
        assert callable(crystallize)
        assert compute_confidence_tier is derive_confidence_tier


def _make_adapted_triplets(subject="Solana", predicate="has_tps", obj="65000",
                            consensus=0.85, triplet_hash="test_hash_001"):
    """Create adapted triplet dicts matching pipeline format."""
    return [
        {
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "consensus_score": consensus,
            "votes": [
                {"model_id": "mock-1", "provider_id": "mock", "agreed": True,
                 "confidence": 0.9, "architecture_family": "transformer_dense"},
                {"model_id": "mock-2", "provider_id": "mock", "agreed": True,
                 "confidence": 0.8, "architecture_family": "transformer_moe"},
            ],
            "signature_5d": {
                "agreement": consensus, "semantic_consistency": 0.9,
                "centrality": 0.5, "stability": 0.5, "relation_diversity": 1.0,
            },
            "epistemic_type": "foundational",
            "triplet_hash": triplet_hash,
        }
    ]


class TestEndToEndPipelineWithMocks:
    """Integration tests using mocked orchestrator to avoid real LLM calls."""

    def test_full_pipeline_produces_attestations(self):
        """Pipeline with mocked extraction produces attestations."""
        from services.esmm.pipeline import run_pipeline, PipelineConfig

        async def _test():
            db, db_path = await _make_temp_db()
            try:
                adapted = _make_adapted_triplets()

                async def mock_extract(*args, **kwargs):
                    return (adapted, 1)

                with patch("services.esmm.pipeline._extract_triplets_from_question",
                           side_effect=mock_extract):
                    config = PipelineConfig()
                    result = await run_pipeline(
                        question="Is Solana TPS > 3000?",
                        db=db,
                        config=config,
                    )

                assert len(result.attestations) >= 1
                assert result.triplets_extracted == 1
            finally:
                await _cleanup_db()

        _run(_test())

    def test_attestations_stored_in_db(self):
        """Attestations produced by pipeline are stored in DB."""
        from services.esmm.pipeline import run_pipeline, PipelineConfig

        async def _test():
            db, db_path = await _make_temp_db()
            try:
                adapted = _make_adapted_triplets()

                async def mock_extract(*args, **kwargs):
                    return (adapted, 1)

                with patch("services.esmm.pipeline._extract_triplets_from_question",
                           side_effect=mock_extract):
                    result = await run_pipeline(
                        question="Test question",
                        db=db,
                        config=PipelineConfig(),
                    )

                if result.attestations:
                    att = result.attestations[0]
                    stored = await db.get_attestation_by_hash(att.claim_hash)
                    assert stored is not None
                    assert stored["claim_hash"] == att.claim_hash
            finally:
                await _cleanup_db()

        _run(_test())

    def test_graph_enriched_after_pipeline(self):
        """The graph contains more concepts after pipeline run."""
        from services.esmm.pipeline import run_pipeline, PipelineConfig

        async def _test():
            db, db_path = await _make_temp_db()
            try:
                stats_before = await db.get_stats()
                concepts_before = stats_before.get("concepts", 0)

                adapted = _make_adapted_triplets()

                async def mock_extract(*args, **kwargs):
                    return (adapted, 1)

                with patch("services.esmm.pipeline._extract_triplets_from_question",
                           side_effect=mock_extract):
                    await run_pipeline(
                        question="Is Solana fast?",
                        db=db,
                        config=PipelineConfig(),
                    )

                stats_after = await db.get_stats()
                concepts_after = stats_after.get("concepts", 0)
                relations_after = stats_after.get("relations", 0)

                assert concepts_after > concepts_before or relations_after > 0
            finally:
                await _cleanup_db()

        _run(_test())

    def test_multiple_questions_grow_graph(self):
        """Multiple pipeline runs grow the graph progressively."""
        from services.esmm.pipeline import run_pipeline, PipelineConfig

        async def _test():
            db, db_path = await _make_temp_db()
            try:
                questions = [
                    ("Is Solana fast?", _make_adapted_triplets(
                        subject="Solana", predicate="has_tps", obj="65000",
                        triplet_hash="hash_q1")),
                    ("Is Bitcoin decentralized?", _make_adapted_triplets(
                        subject="Bitcoin", predicate="is", obj="decentralized",
                        consensus=0.95, triplet_hash="hash_q2")),
                ]

                concept_counts = []
                for q, triplets in questions:
                    async def mock_extract(*args, _t=triplets, **kwargs):
                        return (_t, 1)

                    with patch("services.esmm.pipeline._extract_triplets_from_question",
                               side_effect=mock_extract):
                        await run_pipeline(question=q, db=db, config=PipelineConfig())

                    stats = await db.get_stats()
                    concept_counts.append(stats.get("concepts", 0))

                assert concept_counts[-1] >= concept_counts[0]
            finally:
                await _cleanup_db()

        _run(_test())
