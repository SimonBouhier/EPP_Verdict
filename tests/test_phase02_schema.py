"""
Phase 0.2.1 Tests — Schema and Versioning

Tests for:
- concept_embeddings table creation
- embedding_migrations table creation
- Migration of existing embeddings from concepts to concept_embeddings
- Idempotency of migration
- UNIQUE constraint enforcement
"""

import pytest
import aiosqlite
import struct
import tempfile
from pathlib import Path

from database.engine import ISpaceDB


# ============================================================================
# HELPERS
# ============================================================================

async def create_db_with_embeddings(db_path: str) -> ISpaceDB:
    """
    Create a database with some concepts and embeddings.

    Sets up:
    - 3 concepts with 1024D embeddings (mxbai-embed-large)
    - 2 concepts with 768D embeddings (nomic-embed-text)
    - 1 concept without embedding
    """
    db = ISpaceDB(db_path)
    await db.initialize()

    async with db.connection() as conn:
        # 3 concepts with mxbai-embed-large (1024D)
        embedding_1024 = struct.pack(f'{1024}f', *([0.1] * 1024))
        for i in range(3):
            await conn.execute(
                """
                INSERT INTO concepts (id, rho_static, degree, embedding, embedding_model, embedding_updated_at, created_at)
                VALUES (?, 0.0, 0, ?, 'mxbai-embed-large', ?, ?)
                """,
                (f"concept_1024_{i}", embedding_1024, 1000000.0 + i, 1000000.0)
            )

        # 2 concepts with nomic-embed-text (768D)
        embedding_768 = struct.pack(f'{768}f', *([0.2] * 768))
        for i in range(2):
            await conn.execute(
                """
                INSERT INTO concepts (id, rho_static, degree, embedding, embedding_model, embedding_updated_at, created_at)
                VALUES (?, 0.0, 0, ?, 'nomic-embed-text', ?, ?)
                """,
                (f"concept_768_{i}", embedding_768, 2000000.0 + i, 2000000.0)
            )

        # 1 concept without embedding
        await conn.execute(
            """
            INSERT INTO concepts (id, rho_static, degree, created_at)
            VALUES ('concept_no_embedding', 0.0, 0, ?)
            """,
            (3000000.0,)
        )

        await conn.commit()

    return db


async def create_fresh_db(db_path: str) -> ISpaceDB:
    """Create a fresh database without pre-existing data."""
    db = ISpaceDB(db_path)
    await db.initialize()
    return db


async def cleanup_db(db: ISpaceDB):
    """Cleanup database connections."""
    if db._pool:
        from database.pool import close_pool
        await close_pool()


# ============================================================================
# SCHEMA CREATION TESTS
# ============================================================================

class TestSchemaCreation:
    """Tests for table creation."""

    async def test_concept_embeddings_table_exists(self, tmp_path):
        """La table concept_embeddings existe après initialize()."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            async with db.connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='concept_embeddings'
                    """
                )
                row = await cursor.fetchone()
                assert row is not None, "Table concept_embeddings should exist"
                assert row[0] == "concept_embeddings"
        finally:
            await cleanup_db(db)

    async def test_embedding_migrations_table_exists(self, tmp_path):
        """La table embedding_migrations existe après initialize()."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            async with db.connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='embedding_migrations'
                    """
                )
                row = await cursor.fetchone()
                assert row is not None, "Table embedding_migrations should exist"
                assert row[0] == "embedding_migrations"
        finally:
            await cleanup_db(db)

    async def test_concept_embeddings_indexes_exist(self, tmp_path):
        """Les index de concept_embeddings sont créés."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            async with db.connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='index' AND name LIKE 'idx_concept_embeddings%'
                    """
                )
                indexes = [row[0] for row in await cursor.fetchall()]
                assert "idx_concept_embeddings_model" in indexes
                assert "idx_concept_embeddings_concept" in indexes
        finally:
            await cleanup_db(db)


# ============================================================================
# EMBEDDING MIGRATION TESTS
# ============================================================================

class TestEmbeddingMigration:
    """Tests for migrating existing embeddings to concept_embeddings."""

    async def test_existing_embeddings_copied(self, tmp_path):
        """
        Les embeddings existants dans concepts.embedding sont copiés
        dans concept_embeddings avec le bon model_id et la bonne dimension.
        """
        db_path = str(tmp_path / "test_db.db")
        db = await create_db_with_embeddings(db_path)
        try:
            # Re-run initialize to trigger migration
            await db.initialize()

            async with db.connection() as conn:
                # Count total embeddings in concept_embeddings
                cursor = await conn.execute("SELECT COUNT(*) FROM concept_embeddings")
                total = (await cursor.fetchone())[0]
                assert total == 5, f"Should have 5 embeddings copied, got {total}"

                # Check 1024D embeddings
                cursor = await conn.execute(
                    """
                    SELECT concept_id, model_id, dimension
                    FROM concept_embeddings
                    WHERE model_id = 'mxbai-embed-large'
                    """
                )
                rows = await cursor.fetchall()
                assert len(rows) == 3, "Should have 3 mxbai-embed-large embeddings"
                for row in rows:
                    assert row[2] == 1024, f"Dimension should be 1024, got {row[2]}"

                # Check 768D embeddings
                cursor = await conn.execute(
                    """
                    SELECT concept_id, model_id, dimension
                    FROM concept_embeddings
                    WHERE model_id = 'nomic-embed-text'
                    """
                )
                rows = await cursor.fetchall()
                assert len(rows) == 2, "Should have 2 nomic-embed-text embeddings"
                for row in rows:
                    assert row[2] == 768, f"Dimension should be 768, got {row[2]}"
        finally:
            await cleanup_db(db)

    async def test_copy_is_idempotent(self, tmp_path):
        """Appeler initialize() deux fois ne duplique pas les embeddings."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_db_with_embeddings(db_path)
        try:
            # First call already done in fixture, run again
            await db.initialize()
            # Run a third time
            await db.initialize()

            async with db.connection() as conn:
                cursor = await conn.execute("SELECT COUNT(*) FROM concept_embeddings")
                total = (await cursor.fetchone())[0]
                assert total == 5, f"Should still have exactly 5 embeddings, got {total}"
        finally:
            await cleanup_db(db)

    async def test_embeddings_blob_preserved(self, tmp_path):
        """Les blobs d'embedding sont correctement copiés."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_db_with_embeddings(db_path)
        try:
            await db.initialize()

            async with db.connection() as conn:
                # Get an embedding from concept_embeddings
                cursor = await conn.execute(
                    """
                    SELECT ce.embedding, c.embedding
                    FROM concept_embeddings ce
                    JOIN concepts c ON ce.concept_id = c.id
                    WHERE ce.model_id = 'mxbai-embed-large'
                    LIMIT 1
                    """
                )
                row = await cursor.fetchone()
                assert row is not None
                assert row[0] == row[1], "Embedding blob should be identical"
        finally:
            await cleanup_db(db)


# ============================================================================
# UNIQUE CONSTRAINT TESTS
# ============================================================================

class TestUniqueConstraint:
    """Tests for UNIQUE(concept_id, model_id) constraint."""

    async def test_unique_constraint(self, tmp_path):
        """On ne peut pas avoir deux embeddings du même modèle pour le même concept."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            embedding = struct.pack(f'{768}f', *([0.1] * 768))

            async with db.connection() as conn:
                # First, add a concept
                await conn.execute(
                    """
                    INSERT INTO concepts (id, rho_static, degree, created_at)
                    VALUES ('test_concept', 0.0, 0, ?)
                    """,
                    (1000000.0,)
                )

                # Insert first embedding
                await conn.execute(
                    """
                    INSERT INTO concept_embeddings (concept_id, model_id, dimension, embedding)
                    VALUES ('test_concept', 'test-model', 768, ?)
                    """,
                    (embedding,)
                )
                await conn.commit()

                # Try to insert duplicate - should fail
                with pytest.raises(aiosqlite.IntegrityError):
                    await conn.execute(
                        """
                        INSERT INTO concept_embeddings (concept_id, model_id, dimension, embedding)
                        VALUES ('test_concept', 'test-model', 768, ?)
                        """,
                        (embedding,)
                    )
        finally:
            await cleanup_db(db)

    async def test_same_concept_different_models_allowed(self, tmp_path):
        """Un concept peut avoir des embeddings de différents modèles."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            embedding_768 = struct.pack(f'{768}f', *([0.1] * 768))
            embedding_1024 = struct.pack(f'{1024}f', *([0.2] * 1024))

            async with db.connection() as conn:
                # Add concept
                await conn.execute(
                    """
                    INSERT INTO concepts (id, rho_static, degree, created_at)
                    VALUES ('multi_model_concept', 0.0, 0, ?)
                    """,
                    (1000000.0,)
                )

                # Insert 768D embedding
                await conn.execute(
                    """
                    INSERT INTO concept_embeddings (concept_id, model_id, dimension, embedding)
                    VALUES ('multi_model_concept', 'nomic-embed-text', 768, ?)
                    """,
                    (embedding_768,)
                )

                # Insert 1024D embedding - should succeed
                await conn.execute(
                    """
                    INSERT INTO concept_embeddings (concept_id, model_id, dimension, embedding)
                    VALUES ('multi_model_concept', 'mxbai-embed-large', 1024, ?)
                    """,
                    (embedding_1024,)
                )
                await conn.commit()

                # Verify both exist
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM concept_embeddings WHERE concept_id = 'multi_model_concept'"
                )
                count = (await cursor.fetchone())[0]
                assert count == 2, "Should have 2 embeddings for the same concept"
        finally:
            await cleanup_db(db)


# ============================================================================
# EMBEDDING MIGRATIONS TABLE TESTS
# ============================================================================

class TestEmbeddingMigrationsTable:
    """Tests for embedding_migrations table structure."""

    async def test_migrations_table_columns(self, tmp_path):
        """La table embedding_migrations a toutes les colonnes requises."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            async with db.connection() as conn:
                cursor = await conn.execute("PRAGMA table_info(embedding_migrations)")
                columns = {row[1]: row[2] for row in await cursor.fetchall()}

                expected_columns = {
                    "migration_id": "INTEGER",
                    "from_model": "TEXT",
                    "to_model": "TEXT",
                    "dimension_from": "INTEGER",
                    "dimension_to": "INTEGER",
                    "status": "TEXT",
                    "concepts_total": "INTEGER",
                    "concepts_migrated": "INTEGER",
                    "concepts_failed": "INTEGER",
                    "started_at": "REAL",
                    "completed_at": "REAL",
                    "triggered_by": "TEXT",
                    "error_log": "TEXT",
                }

                for col_name, col_type in expected_columns.items():
                    assert col_name in columns, f"Column {col_name} should exist"
                    assert columns[col_name] == col_type, f"Column {col_name} should be {col_type}"
        finally:
            await cleanup_db(db)

    async def test_create_migration_entry(self, tmp_path):
        """On peut créer une entrée de migration."""
        db_path = str(tmp_path / "test_db.db")
        db = await create_fresh_db(db_path)
        try:
            async with db.connection() as conn:
                cursor = await conn.execute(
                    """
                    INSERT INTO embedding_migrations
                    (from_model, to_model, dimension_from, dimension_to, status, started_at)
                    VALUES ('mxbai-embed-large', 'nomic-embed-text', 1024, 768, 'running', ?)
                    """,
                    (1000000.0,)
                )
                await conn.commit()

                migration_id = cursor.lastrowid
                assert migration_id is not None

                # Verify entry
                cursor = await conn.execute(
                    "SELECT from_model, to_model, status FROM embedding_migrations WHERE migration_id = ?",
                    (migration_id,)
                )
                row = await cursor.fetchone()
                assert row[0] == "mxbai-embed-large"
                assert row[1] == "nomic-embed-text"
                assert row[2] == "running"
        finally:
            await cleanup_db(db)
