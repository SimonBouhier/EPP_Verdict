"""
Phase 0.2.4 Tests — Cross-version Search and Config

Tests for:
- get_concepts_with_embeddings_for_model returns only vectors for specified model
- get_concepts_with_embeddings() with model_id parameter
- No cross-dimension comparison (vectors from different models are separate)
- Config file has embeddings section
"""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


import pytest
import struct
import yaml
from pathlib import Path

from database.engine import ISpaceDB


# ============================================================================
# HELPERS
# ============================================================================

async def create_fresh_db(db_path: str) -> ISpaceDB:
    """Create a fresh database."""
    db = ISpaceDB(db_path)
    await db.initialize()
    return db


async def cleanup_db(db: ISpaceDB):
    """Cleanup database connections."""
    if db._pool:
        from database.pool import close_pool
        await close_pool()


def create_embedding(dim: int, value: float = 0.1) -> bytes:
    """Create a test embedding blob."""
    return struct.pack(f'{dim}f', *([value] * dim))


# ============================================================================
# GET EMBEDDINGS FOR MODEL TESTS
# ============================================================================

class TestGetEmbeddingsForModel:
    """Tests for get_concepts_with_embeddings_for_model."""

    async def test_get_embeddings_for_specific_model(self, tmp_path):
        """get_concepts_with_embeddings_for_model retourne uniquement les vecteurs du modèle demandé."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            # Create concepts
            for i in range(5):
                await db.add_concept(f"concept_{i}")

            # Store embeddings for model-a (3 concepts)
            for i in range(3):
                await db.store_concept_embedding(
                    f"concept_{i}", "model-a", 1024, create_embedding(1024, 0.1)
                )

            # Store embeddings for model-b (5 concepts)
            for i in range(5):
                await db.store_concept_embedding(
                    f"concept_{i}", "model-b", 768, create_embedding(768, 0.2)
                )

            # Get embeddings for model-a
            embeddings_a = await db.get_concepts_with_embeddings_for_model("model-a")
            assert len(embeddings_a) == 3
            for emb in embeddings_a:
                assert emb["model_id"] == "model-a"
                assert emb["dimension"] == 1024

            # Get embeddings for model-b
            embeddings_b = await db.get_concepts_with_embeddings_for_model("model-b")
            assert len(embeddings_b) == 5
            for emb in embeddings_b:
                assert emb["model_id"] == "model-b"
                assert emb["dimension"] == 768
        finally:
            await cleanup_db(db)

    async def test_get_embeddings_respects_limit(self, tmp_path):
        """get_concepts_with_embeddings_for_model respecte la limite."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            for i in range(10):
                await db.add_concept(f"concept_{i}")
                await db.store_concept_embedding(
                    f"concept_{i}", "model-a", 768, create_embedding(768)
                )

            embeddings = await db.get_concepts_with_embeddings_for_model("model-a", limit=5)
            assert len(embeddings) == 5
        finally:
            await cleanup_db(db)

    async def test_get_embeddings_default_uses_legacy(self, tmp_path):
        """get_concepts_with_embeddings() sans model_id utilise concepts.embedding."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            # Create concept with embedding in concepts table (legacy)
            embedding = create_embedding(1024)
            await db.add_concept(
                "legacy_concept",
                embedding=embedding,
                embedding_model="legacy-model"
            )

            # Get without model_id - should use legacy
            embeddings = await db.get_concepts_with_embeddings()
            assert len(embeddings) == 1
            assert embeddings[0]["id"] == "legacy_concept"
        finally:
            await cleanup_db(db)

    async def test_get_embeddings_with_model_id_parameter(self, tmp_path):
        """get_concepts_with_embeddings() avec model_id utilise concept_embeddings."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            # Create concept
            await db.add_concept("test_concept")

            # Store in concept_embeddings
            await db.store_concept_embedding(
                "test_concept", "new-model", 768, create_embedding(768)
            )

            # Get with model_id parameter
            embeddings = await db.get_concepts_with_embeddings(model_id="new-model")
            assert len(embeddings) == 1
            assert embeddings[0]["model_id"] == "new-model"
        finally:
            await cleanup_db(db)


# ============================================================================
# NO CROSS-DIMENSION COMPARISON TESTS
# ============================================================================

class TestNoCrossDimensionMixing:
    """Tests ensuring vectors from different models are never mixed."""

    async def test_no_cross_dimension_comparison(self, tmp_path):
        """Les vecteurs 768D et 1024D ne sont jamais mélangés dans un même résultat."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            # Create concepts with different dimension embeddings
            await db.add_concept("concept_1")
            await db.add_concept("concept_2")

            await db.store_concept_embedding(
                "concept_1", "model-768", 768, create_embedding(768)
            )
            await db.store_concept_embedding(
                "concept_2", "model-1024", 1024, create_embedding(1024)
            )

            # Query for model-768 should only get 768D
            embeddings_768 = await db.get_concepts_with_embeddings_for_model("model-768")
            assert len(embeddings_768) == 1
            assert embeddings_768[0]["dimension"] == 768

            # Query for model-1024 should only get 1024D
            embeddings_1024 = await db.get_concepts_with_embeddings_for_model("model-1024")
            assert len(embeddings_1024) == 1
            assert embeddings_1024[0]["dimension"] == 1024

            # No mixing!
            all_dims_768 = [e["dimension"] for e in embeddings_768]
            all_dims_1024 = [e["dimension"] for e in embeddings_1024]
            assert all(d == 768 for d in all_dims_768)
            assert all(d == 1024 for d in all_dims_1024)
        finally:
            await cleanup_db(db)


# ============================================================================
# CONFIG TESTS
# ============================================================================

class TestEmbeddingsConfig:
    """Tests for embeddings configuration."""

    def test_config_has_embeddings_section(self):
        """config.yaml a une section embeddings."""
        config_path = Path("config.yaml")
        assert config_path.exists(), "config.yaml should exist"

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        assert "embeddings" in config, "Config should have 'embeddings' section"
        embeddings_config = config["embeddings"]

        # Check required fields
        assert "active_model" in embeddings_config
        assert "fallback_reembed" in embeddings_config
        assert "similarity_min_score" in embeddings_config

    def test_config_active_model_is_string(self):
        """active_model dans config est une chaîne."""
        config_path = Path("config.yaml")
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        active_model = config["embeddings"]["active_model"]
        assert isinstance(active_model, str)
        assert len(active_model) > 0

    def test_config_fallback_reembed_is_bool(self):
        """fallback_reembed dans config est un booléen."""
        config_path = Path("config.yaml")
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        fallback = config["embeddings"]["fallback_reembed"]
        assert isinstance(fallback, bool)

    def test_config_similarity_min_score_is_number(self):
        """similarity_min_score dans config est un nombre."""
        config_path = Path("config.yaml")
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        min_score = config["embeddings"]["similarity_min_score"]
        assert isinstance(min_score, (int, float))
        assert 0 <= min_score <= 1


# ============================================================================
# FALLBACK TESTS (Conceptual - fallback requires provider)
# ============================================================================

class TestFallbackDisabled:
    """Tests for fallback behavior when disabled."""

    async def test_fallback_disabled_returns_none_for_missing_model(self, tmp_path):
        """Si fallback désactivé, retourne None/empty pour un modèle manquant."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            # Create concept with embedding for one model
            await db.add_concept("test_concept")
            await db.store_concept_embedding(
                "test_concept", "model-a", 768, create_embedding(768)
            )

            # Query for different model - should return empty
            embeddings = await db.get_concepts_with_embeddings_for_model("model-b")
            assert len(embeddings) == 0

            # get_concept_embedding returns None
            result = await db.get_concept_embedding("test_concept", "model-b")
            assert result is None
        finally:
            await cleanup_db(db)


# ─────────────────────────────────────────────────────────────────────────
# Single-file runner — `python tests/<this_file>.py`
# Génère un rapport horodaté dans `test_results/individual/`.
# Cf. `tests/_runner.py::run_self` pour le détail.
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from tests._runner import run_self
    raise SystemExit(run_self(__file__))
