"""
Phase 0.2.2 Tests — Decoupling Hardcoded Dimensions

Tests for:
- SemanticMemory accepts any dimension (not just 1024)
- SemanticMemory rejects empty embeddings
- _cosine_similarity rejects mixed dimensions
- add_concept requires embedding_model when embedding provided
- add_concept writes to both tables
- Legacy embeddings.py emits DeprecationWarning
"""

import pytest
import asyncio
import struct
import warnings
from pathlib import Path

from database.engine import ISpaceDB
from services.consciousness.memory import SemanticMemory, clear_semantic_memory


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


# ============================================================================
# SEMANTIC MEMORY TESTS
# ============================================================================

class TestSemanticMemoryDimensions:
    """Tests for SemanticMemory accepting multiple dimensions."""

    def test_memory_accepts_768d(self):
        """SemanticMemory.store_memory() accepte des vecteurs 768D."""
        clear_semantic_memory()
        memory = SemanticMemory(level=3)

        # 768D embedding
        embeddings_768 = [0.1] * 768

        result = memory.store_memory(
            session_id="test_session",
            content="Test message",
            embeddings=embeddings_768,
            turn_number=1
        )

        assert result is not None, "Should accept 768D embeddings"
        assert result.content == "Test message"
        assert len(result.embeddings) == 768

    def test_memory_accepts_1024d(self):
        """SemanticMemory.store_memory() accepte des vecteurs 1024D."""
        clear_semantic_memory()
        memory = SemanticMemory(level=3)

        # 1024D embedding
        embeddings_1024 = [0.2] * 1024

        result = memory.store_memory(
            session_id="test_session",
            content="Test message 1024",
            embeddings=embeddings_1024,
            turn_number=1
        )

        assert result is not None, "Should accept 1024D embeddings"
        assert len(result.embeddings) == 1024

    def test_memory_accepts_custom_dimension(self):
        """SemanticMemory.store_memory() accepte des dimensions arbitraires."""
        clear_semantic_memory()
        memory = SemanticMemory(level=3)

        # Custom 512D embedding
        embeddings_512 = [0.3] * 512

        result = memory.store_memory(
            session_id="test_session",
            content="Test message 512",
            embeddings=embeddings_512,
            turn_number=1
        )

        assert result is not None, "Should accept custom dimension embeddings"
        assert len(result.embeddings) == 512

    def test_memory_rejects_empty(self):
        """SemanticMemory.store_memory() rejette les vecteurs vides."""
        clear_semantic_memory()
        memory = SemanticMemory(level=3)

        # Empty embedding
        result = memory.store_memory(
            session_id="test_session",
            content="Test message",
            embeddings=[],
            turn_number=1
        )

        assert result is None, "Should reject empty embeddings"

    def test_memory_rejects_none_embeddings(self):
        """SemanticMemory.store_memory() rejette les embeddings None."""
        clear_semantic_memory()
        memory = SemanticMemory(level=3)

        result = memory.store_memory(
            session_id="test_session",
            content="Test message",
            embeddings=None,
            turn_number=1
        )

        assert result is None, "Should reject None embeddings"


class TestCosineSimlarity:
    """Tests for _cosine_similarity dimension checking."""

    def test_cosine_rejects_mixed_dimensions(self):
        """_cosine_similarity retourne 0.0 pour des vecteurs de dimensions différentes."""
        memory = SemanticMemory(level=3)

        vec_768 = [0.1] * 768
        vec_1024 = [0.1] * 1024

        similarity = memory._cosine_similarity(vec_768, vec_1024)

        assert similarity == 0.0, "Should return 0.0 for mixed dimensions"

    def test_cosine_same_dimension_works(self):
        """_cosine_similarity fonctionne pour des vecteurs de même dimension."""
        memory = SemanticMemory(level=3)

        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        similarity = memory._cosine_similarity(vec1, vec2)

        assert similarity == 1.0, "Identical vectors should have similarity 1.0"

    def test_cosine_orthogonal_vectors(self):
        """_cosine_similarity retourne 0 pour des vecteurs orthogonaux."""
        memory = SemanticMemory(level=3)

        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        similarity = memory._cosine_similarity(vec1, vec2)

        assert similarity == 0.0, "Orthogonal vectors should have similarity 0.0"


# ============================================================================
# ADD_CONCEPT TESTS
# ============================================================================

class TestAddConceptEmbeddingModel:
    """Tests for add_concept embedding_model requirement."""

    def test_add_concept_requires_model_with_embedding(self, tmp_path):
        """add_concept() avec embedding mais sans embedding_model lève ValueError."""
        async def run_test():
            db_path = str(tmp_path / "test_db.db")
            db = await create_fresh_db(db_path)
            try:
                embedding = struct.pack(f'{768}f', *([0.1] * 768))

                with pytest.raises(ValueError) as exc_info:
                    await db.add_concept(
                        concept_id="test_concept",
                        embedding=embedding,
                        # embedding_model missing!
                    )

                assert "embedding_model is required" in str(exc_info.value)
            finally:
                await cleanup_db(db)

        asyncio.run(run_test())

    def test_add_concept_without_embedding_no_model_ok(self, tmp_path):
        """add_concept() sans embedding n'a pas besoin de embedding_model."""
        async def run_test():
            db_path = str(tmp_path / "test_db.db")
            db = await create_fresh_db(db_path)
            try:
                # Should not raise
                await db.add_concept(
                    concept_id="test_concept_no_emb",
                    rho_static=0.5,
                    source="test"
                )

                # Verify it was added
                concept = await db.get_concept("test_concept_no_emb")
                assert concept is not None
            finally:
                await cleanup_db(db)

        asyncio.run(run_test())

    def test_add_concept_writes_to_both_tables(self, tmp_path):
        """add_concept() avec embedding écrit dans concepts ET concept_embeddings."""
        async def run_test():
            db_path = str(tmp_path / "test_db.db")
            db = await create_fresh_db(db_path)
            try:
                embedding = struct.pack(f'{768}f', *([0.1] * 768))

                await db.add_concept(
                    concept_id="dual_table_concept",
                    embedding=embedding,
                    embedding_model="test-model-768",
                    source="test"
                )

                async with db.connection() as conn:
                    # Check concepts table
                    cursor = await conn.execute(
                        "SELECT id, embedding, embedding_model FROM concepts WHERE id = ?",
                        ("dual_table_concept",)
                    )
                    row = await cursor.fetchone()
                    assert row is not None, "Concept should be in concepts table"
                    assert row[1] == embedding, "Embedding should match"
                    assert row[2] == "test-model-768", "Model should match"

                    # Check concept_embeddings table
                    cursor = await conn.execute(
                        """
                        SELECT concept_id, model_id, dimension, embedding
                        FROM concept_embeddings
                        WHERE concept_id = ? AND model_id = ?
                        """,
                        ("dual_table_concept", "test-model-768")
                    )
                    row = await cursor.fetchone()
                    assert row is not None, "Embedding should be in concept_embeddings table"
                    assert row[2] == 768, f"Dimension should be 768, got {row[2]}"
                    assert row[3] == embedding, "Embedding blob should match"
            finally:
                await cleanup_db(db)

        asyncio.run(run_test())

    def test_add_concept_dimension_calculated_correctly(self, tmp_path):
        """add_concept() calcule correctement la dimension depuis le blob."""
        async def run_test():
            db_path = str(tmp_path / "test_db.db")
            db = await create_fresh_db(db_path)
            try:
                # 1024D embedding
                embedding_1024 = struct.pack(f'{1024}f', *([0.2] * 1024))

                await db.add_concept(
                    concept_id="concept_1024",
                    embedding=embedding_1024,
                    embedding_model="mxbai-embed-large",
                )

                async with db.connection() as conn:
                    cursor = await conn.execute(
                        "SELECT dimension FROM concept_embeddings WHERE concept_id = ?",
                        ("concept_1024",)
                    )
                    row = await cursor.fetchone()
                    assert row is not None
                    assert row[0] == 1024, f"Dimension should be 1024, got {row[0]}"
            finally:
                await cleanup_db(db)

        asyncio.run(run_test())


# ============================================================================
# DEPRECATION WARNING TEST
# ============================================================================

class TestLegacyDeprecation:
    """Tests for legacy module removal (Phase 4.4.2)."""

    def test_legacy_embeddings_module_removed(self):
        """app/embeddings.py a été supprimé (Phase 4.4.2)."""
        import pathlib
        assert not pathlib.Path("app/embeddings.py").exists(), (
            "app/embeddings.py should be deleted — fully replaced by "
            "services.providers.ollama_embeddings"
        )
