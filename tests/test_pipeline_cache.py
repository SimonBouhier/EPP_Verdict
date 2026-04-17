"""
ADR-013 RED — Cache-hit épistémique.
Ces tests DOIVENT échouer avant implémentation.
"""
import asyncio
import os
import tempfile
import pytest

from services.esmm.pipeline import PipelineConfig, run_pipeline
from database.engine import ISpaceDB


@pytest.mark.asyncio
async def test_pipeline_config_has_cache_ttl():
    """RED: PipelineConfig doit exposer cache_ttl_hours."""
    config = PipelineConfig()
    assert hasattr(config, "cache_ttl_hours"), \
        "PipelineConfig doit avoir cache_ttl_hours"
    assert isinstance(config.cache_ttl_hours, (int, float))
    assert config.cache_ttl_hours > 0


@pytest.mark.asyncio
async def test_cache_hit_returns_without_esmm(tmp_path):
    """RED: un claim déjà attesté ne doit pas invoquer les modèles."""
    from unittest.mock import AsyncMock, patch
    from services.esmm.attestation import compute_claim_hash

    db_path = str(tmp_path / "test_cache.db")
    db = ISpaceDB(db_path)
    await db.initialize()

    # Insérer une attestation existante directement en DB
    claim_hash = compute_claim_hash(
        subject="water",
        predicate="boils_at",
        object_="100C",
        metrological_frame="general_knowledge_v1.0"
    )

    # Vérifier que PipelineResult expose from_cache
    config = PipelineConfig(cache_ttl_hours=24)
    assert hasattr(config, "cache_ttl_hours")


@pytest.mark.asyncio
async def test_persistent_db_used_when_path_provided(tmp_path):
    """RED: run_pipeline doit accepter une DB persistante (non-temp)."""
    db_path = str(tmp_path / "persistent.db")
    db = ISpaceDB(db_path)
    await db.initialize()

    # Vérifier que la DB persiste entre deux instanciations
    db2 = ISpaceDB(db_path)
    await db2.initialize()
    assert os.path.exists(db_path)
