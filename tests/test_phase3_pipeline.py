"""Tests Phase 3 — Pipeline with real orchestrator connection."""

import tempfile
import os
import pytest
from unittest.mock import AsyncMock, patch

from services.esmm.pipeline import run_pipeline, PipelineConfig, PipelineResult
from services.providers.mock_provider import make_synthetic_triplets
from services.esmm.triplet_adapter import adapt_all


async def _make_db():
    """Create a temp ISpaceDB."""
    from database.engine import ISpaceDB
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test_pipeline.db")
    db = ISpaceDB(db_path)
    await db.initialize()
    return db


def _make_adapted_triplets(n=3, base_consensus=0.75):
    """Create adapted triplet dicts (simulating orchestrator + adapter output)."""
    triplets = make_synthetic_triplets(n=n, base_consensus=base_consensus)
    return adapt_all(triplets)


def _mock_extract_fn(adapted, run_id=1):
    """Create a proper async mock for _extract_triplets_from_question."""
    async def _extract(*args, **kwargs):
        return (adapted, run_id)
    return _extract


class TestPipelineImports:

    def test_pipeline_imports(self):
        """Pipeline classes are importable."""
        from services.esmm.pipeline import run_pipeline, PipelineConfig, PipelineResult
        assert callable(run_pipeline)

    def test_pipeline_has_providers_param(self):
        """run_pipeline accepts providers parameter."""
        import inspect
        sig = inspect.signature(run_pipeline)
        assert "providers" in sig.parameters


class TestPipelineWithMockedExtraction:
    """Tests using mocked _extract_triplets_from_question (fast, deterministic).
    # MOCK: infrastructure, pas logique métier — l'extraction nécessite des LLM providers réseau.
    """

    async def test_pipeline_produces_attestations(self):
        """Pipeline produces attestations from adapted triplets."""
        db = await _make_db()
        adapted = _make_adapted_triplets(n=3, base_consensus=0.75)

        with patch("services.esmm.pipeline._extract_triplets_from_question",
                    side_effect=_mock_extract_fn(adapted)):
            result = await run_pipeline(
                question="Test question",
                db=db,
                models=["m1", "m2", "m3"],
            )

        assert isinstance(result, PipelineResult)
        assert result.run_id == 1
        assert len(result.attestations) > 0

    async def test_pipeline_no_double_run(self):
        """Pipeline does NOT create an ESMM run (D1 — orchestrator owns it)."""
        db = await _make_db()
        adapted = _make_adapted_triplets()

        with patch("services.esmm.pipeline._extract_triplets_from_question",
                    side_effect=_mock_extract_fn(adapted)):
            await run_pipeline(
                question="Test question",
                db=db,
                models=["m1", "m2", "m3"],
            )

        async with db.connection() as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM esmm_runs")
            count = (await cursor.fetchone())[0]

        assert count == 0  # Pipeline does NOT create runs (D1)

    async def test_pipeline_stores_attestations_in_db(self):
        """Attestations are stored in DB and retrievable by hash."""
        db = await _make_db()
        adapted = _make_adapted_triplets()

        with patch("services.esmm.pipeline._extract_triplets_from_question",
                    side_effect=_mock_extract_fn(adapted)):
            result = await run_pipeline(
                question="Test question",
                db=db,
                models=["m1", "m2", "m3"],
            )

        assert len(result.attestations) > 0
        claim_hash = result.attestations[0].claim_hash
        retrieved = await db.get_attestation_by_hash(claim_hash)
        assert retrieved is not None
        assert retrieved["claim_hash"] == claim_hash

    async def test_pipeline_enriches_graph(self):
        """Pipeline injects triplets into graph."""
        db = await _make_db()
        adapted = _make_adapted_triplets()

        with patch("services.esmm.pipeline._extract_triplets_from_question",
                    side_effect=_mock_extract_fn(adapted)):
            result = await run_pipeline(
                question="Solana TPS",
                db=db,
                models=["m1", "m2", "m3"],
            )

        assert result.triplets_injected > 0

    async def test_pipeline_calls_post_crystallization_hook(self):
        """Track record is populated after crystallization."""
        db = await _make_db()
        adapted = _make_adapted_triplets()

        with patch("services.esmm.pipeline._extract_triplets_from_question",
                    side_effect=_mock_extract_fn(adapted)):
            result = await run_pipeline(
                question="Test question",
                db=db,
                models=["m1", "m2", "m3"],
            )

        assert len(result.attestations) > 0

        async with db.connection() as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM model_track_record")
            predictions = (await cursor.fetchone())[0]

        assert predictions > 0
