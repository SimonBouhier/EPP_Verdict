"""
Phase 0.2.3 Tests — Migration Pipeline

Tests for:
- store_concept_embedding writes to concept_embeddings
- get_concept_embedding reads from concept_embeddings
- get_concepts_needing_migration returns concepts without target model embedding
- Migration is idempotent (UNIQUE constraint)
- finalize_embedding_migration copies to concepts.embedding
- finalize refuses if concepts_failed > 0
- Migration logging in embedding_migrations
"""

import pytest
import asyncio
import struct
import json
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
# STORE/GET CONCEPT EMBEDDING TESTS
# ============================================================================

class TestStoreGetConceptEmbedding:
    """Tests for store_concept_embedding and get_concept_embedding."""

    @pytest.mark.asyncio
    async def test_store_concept_embedding(self, tmp_path):
        """store_concept_embedding écrit dans concept_embeddings."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            # Add a concept first
            await db.add_concept("test_concept")

            # Store embedding
            embedding = create_embedding(768)
            await db.store_concept_embedding(
                concept_id="test_concept",
                model_id="test-model",
                dimension=768,
                embedding=embedding
            )

            # Verify in database
            async with db.connection() as conn:
                cursor = await conn.execute(
                    "SELECT concept_id, model_id, dimension FROM concept_embeddings WHERE concept_id = ?",
                    ("test_concept",)
                )
                row = await cursor.fetchone()
                assert row is not None
                assert row[0] == "test_concept"
                assert row[1] == "test-model"
                assert row[2] == 768
        finally:
            await cleanup_db(db)

    @pytest.mark.asyncio
    async def test_get_concept_embedding(self, tmp_path):
        """get_concept_embedding lit depuis concept_embeddings."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            await db.add_concept("test_concept")

            embedding = create_embedding(768, 0.5)
            await db.store_concept_embedding(
                concept_id="test_concept",
                model_id="test-model",
                dimension=768,
                embedding=embedding
            )

            # Get it back
            result = await db.get_concept_embedding("test_concept", "test-model")
            assert result is not None
            assert result == embedding

            # Non-existent should return None
            result_none = await db.get_concept_embedding("test_concept", "other-model")
            assert result_none is None
        finally:
            await cleanup_db(db)

    @pytest.mark.asyncio
    async def test_store_is_idempotent(self, tmp_path):
        """store_concept_embedding avec INSERT OR IGNORE est idempotent."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            await db.add_concept("test_concept")

            embedding = create_embedding(768)

            # Store twice - should not raise
            await db.store_concept_embedding(
                concept_id="test_concept",
                model_id="test-model",
                dimension=768,
                embedding=embedding
            )
            await db.store_concept_embedding(
                concept_id="test_concept",
                model_id="test-model",
                dimension=768,
                embedding=embedding
            )

            # Should still have only one entry
            async with db.connection() as conn:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM concept_embeddings WHERE concept_id = ? AND model_id = ?",
                    ("test_concept", "test-model")
                )
                count = (await cursor.fetchone())[0]
                assert count == 1
        finally:
            await cleanup_db(db)


# ============================================================================
# CONCEPTS NEEDING MIGRATION TESTS
# ============================================================================

class TestConceptsNeedingMigration:
    """Tests for get_concepts_needing_migration."""

    @pytest.mark.asyncio
    async def test_concepts_needing_migration(self, tmp_path):
        """get_concepts_needing_migration retourne les concepts sans embedding pour le modèle cible."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            # Create concepts with embeddings in concepts table
            for i in range(5):
                embedding = create_embedding(1024)
                await db.add_concept(
                    f"concept_{i}",
                    embedding=embedding,
                    embedding_model="model-a"
                )

            # Add embedding for model-b for 2 of them
            await db.store_concept_embedding("concept_0", "model-b", 768, create_embedding(768))
            await db.store_concept_embedding("concept_1", "model-b", 768, create_embedding(768))

            # Should return 3 concepts needing migration to model-b
            needing = await db.get_concepts_needing_migration("model-b")
            assert len(needing) == 3
            assert "concept_0" not in needing
            assert "concept_1" not in needing
            assert "concept_2" in needing
            assert "concept_3" in needing
            assert "concept_4" in needing
        finally:
            await cleanup_db(db)

    @pytest.mark.asyncio
    async def test_concepts_needing_migration_with_limit(self, tmp_path):
        """get_concepts_needing_migration respecte la limite."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            for i in range(10):
                embedding = create_embedding(1024)
                await db.add_concept(
                    f"concept_{i}",
                    embedding=embedding,
                    embedding_model="model-a"
                )

            needing = await db.get_concepts_needing_migration("model-b", limit=5)
            assert len(needing) == 5
        finally:
            await cleanup_db(db)


# ============================================================================
# MIGRATION ENTRY TESTS
# ============================================================================

class TestMigrationEntry:
    """Tests for migration logging."""

    @pytest.mark.asyncio
    async def test_create_embedding_migration(self, tmp_path):
        """create_embedding_migration crée une entrée dans embedding_migrations."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            migration_id = await db.create_embedding_migration(
                from_model="model-a",
                to_model="model-b",
                dim_from=1024,
                dim_to=768,
                triggered_by="test"
            )

            assert migration_id is not None
            assert migration_id > 0

            # Verify entry
            migration = await db.get_embedding_migration(migration_id)
            assert migration is not None
            assert migration["from_model"] == "model-a"
            assert migration["to_model"] == "model-b"
            assert migration["status"] == "running"
        finally:
            await cleanup_db(db)

    @pytest.mark.asyncio
    async def test_update_embedding_migration(self, tmp_path):
        """update_embedding_migration met à jour les champs."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            migration_id = await db.create_embedding_migration(
                from_model="model-a",
                to_model="model-b",
                dim_from=1024,
                dim_to=768
            )

            await db.update_embedding_migration(
                migration_id,
                concepts_total=100,
                concepts_migrated=50,
                concepts_failed=5,
                status="running"
            )

            migration = await db.get_embedding_migration(migration_id)
            assert migration["concepts_total"] == 100
            assert migration["concepts_migrated"] == 50
            assert migration["concepts_failed"] == 5
        finally:
            await cleanup_db(db)

    @pytest.mark.asyncio
    async def test_migration_logging(self, tmp_path):
        """Chaque migration est tracée dans embedding_migrations."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            errors = [{"concept_id": "test", "error": "Test error"}]

            migration_id = await db.create_embedding_migration(
                from_model="model-a",
                to_model="model-b",
                dim_from=1024,
                dim_to=768
            )

            await db.update_embedding_migration(
                migration_id,
                error_log=json.dumps(errors)
            )

            migration = await db.get_embedding_migration(migration_id)
            assert migration["error_log"] == errors
        finally:
            await cleanup_db(db)


# ============================================================================
# FINALIZE TESTS
# ============================================================================

class TestFinalizeMigration:
    """Tests for finalize_embedding_migration."""

    @pytest.mark.asyncio
    async def test_finalize_copies_to_concepts(self, tmp_path):
        """finalize_embedding_migration copie vers concepts.embedding."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            # Create concept with old embedding
            old_embedding = create_embedding(1024, 0.1)
            await db.add_concept(
                "test_concept",
                embedding=old_embedding,
                embedding_model="model-a"
            )

            # Store new embedding in concept_embeddings
            new_embedding = create_embedding(768, 0.9)
            await db.store_concept_embedding(
                "test_concept", "model-b", 768, new_embedding
            )

            # Create and finalize migration
            migration_id = await db.create_embedding_migration(
                from_model="model-a",
                to_model="model-b",
                dim_from=1024,
                dim_to=768
            )
            await db.update_embedding_migration(
                migration_id,
                concepts_migrated=1,
                concepts_failed=0
            )

            await db.finalize_embedding_migration(migration_id, "model-b")

            # Verify concepts.embedding was updated
            async with db.connection() as conn:
                cursor = await conn.execute(
                    "SELECT embedding, embedding_model FROM concepts WHERE id = ?",
                    ("test_concept",)
                )
                row = await cursor.fetchone()
                assert row[0] == new_embedding
                assert row[1] == "model-b"
        finally:
            await cleanup_db(db)

    @pytest.mark.asyncio
    async def test_finalize_refuses_if_failures(self, tmp_path):
        """finalize refuse si concepts_failed > 0 dans la migration."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            migration_id = await db.create_embedding_migration(
                from_model="model-a",
                to_model="model-b",
                dim_from=1024,
                dim_to=768
            )

            await db.update_embedding_migration(
                migration_id,
                concepts_migrated=5,
                concepts_failed=2  # Has failures!
            )

            with pytest.raises(ValueError) as exc_info:
                await db.finalize_embedding_migration(migration_id, "model-b")

            assert "concepts failed" in str(exc_info.value).lower()
        finally:
            await cleanup_db(db)


# ============================================================================
# ROLLBACK TESTS
# ============================================================================

class TestRollbackMigration:
    """Tests for rollback_embedding_migration."""

    @pytest.mark.asyncio
    async def test_rollback_deletes_embeddings(self, tmp_path):
        """rollback_embedding_migration supprime les embeddings du modèle cible."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            # Create concepts and embeddings
            for i in range(3):
                await db.add_concept(f"concept_{i}")
                await db.store_concept_embedding(
                    f"concept_{i}", "model-b", 768, create_embedding(768)
                )

            # Create migration
            migration_id = await db.create_embedding_migration(
                from_model="model-a",
                to_model="model-b",
                dim_from=1024,
                dim_to=768
            )

            # Rollback
            deleted = await db.rollback_embedding_migration(migration_id)
            assert deleted == 3

            # Verify embeddings deleted
            async with db.connection() as conn:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM concept_embeddings WHERE model_id = 'model-b'"
                )
                count = (await cursor.fetchone())[0]
                assert count == 0

            # Verify migration status
            migration = await db.get_embedding_migration(migration_id)
            assert migration["status"] == "rolled_back"
        finally:
            await cleanup_db(db)


# ============================================================================
# DRY RUN TESTS (conceptual - actual CLI tests would be integration)
# ============================================================================

class TestMigrationIdempotency:
    """Tests for migration idempotency."""

    @pytest.mark.asyncio
    async def test_migration_is_idempotent(self, tmp_path):
        """Relancer la migration ne duplique pas les embeddings (UNIQUE constraint)."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            await db.add_concept("test_concept")

            embedding = create_embedding(768)

            # Store same embedding multiple times (simulating re-run)
            for _ in range(3):
                await db.store_concept_embedding(
                    "test_concept", "model-b", 768, embedding
                )

            # Should only have one entry
            async with db.connection() as conn:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM concept_embeddings WHERE concept_id = 'test_concept'"
                )
                count = (await cursor.fetchone())[0]
                assert count == 1
        finally:
            await cleanup_db(db)
