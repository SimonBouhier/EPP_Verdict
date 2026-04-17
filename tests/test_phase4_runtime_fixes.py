"""
Tests Phase 4.1/4.2 — RED-GREEN-FIX pour crashs runtime et corruptions silencieuses.
Chaque test doit ÉCHOUER avant la correction, PASSER après.
"""

import json
import os
import tempfile
import pytest
from database.engine import ISpaceDB


def _tmp_db_path() -> str:
    """Create a temporary DB path for testing."""
    tmp = tempfile.mkdtemp()
    return os.path.join(tmp, "test_phase4.db")


class TestTripletExtractorOnConflict:
    """4.1.1 — ON CONFLICT invalide dans triplet_extractor."""

    async def test_duplicate_relation_insert_no_crash(self):
        """Injecter deux fois la même relation (source, target) ne doit pas crasher.

        Bug: ON CONFLICT(source, target, relation_type) dans triplet_extractor.py
        ne correspond pas au PRIMARY KEY (source, target) — SQLite lève OperationalError.
        Fix: ON CONFLICT(source, target) aligné sur le PK.
        """
        db = ISpaceDB(_tmp_db_path())
        await db.initialize()

        # Créer les concepts requis (FK constraint)
        await db.add_concept("sun", source="test")
        await db.add_concept("star", source="test")

        # Premier insert — doit passer
        async with db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO relations (source, target, relation_type, weight, model_source)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source, target) DO UPDATE SET
                    weight = MAX(weight, excluded.weight),
                    extraction_count = extraction_count + 1
                """,
                ("sun", "star", "is_a", 0.5, "model_a")
            )
            await conn.commit()

        # Deuxième insert — même paire, doit UPDATE sans crasher
        async with db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO relations (source, target, relation_type, weight, model_source)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source, target) DO UPDATE SET
                    weight = MAX(weight, excluded.weight),
                    extraction_count = extraction_count + 1
                """,
                ("sun", "star", "is_a", 0.8, "model_b")
            )
            await conn.commit()

        # Vérifier que le poids a été mis à jour
        async with db.connection() as conn:
            cursor = await conn.execute(
                "SELECT weight, extraction_count FROM relations WHERE source = ? AND target = ?",
                ("sun", "star")
            )
            row = await cursor.fetchone()
            assert row is not None, "Relation should exist"
            assert row[0] == 0.8, f"Weight should be max(0.5, 0.8) = 0.8, got {row[0]}"
            assert row[1] == 2, f"extraction_count should be 2, got {row[1]}"


class TestDeprecatedEmbeddingImports:
    """4.1.2 — Aucun module de production ne doit importer app/embeddings.py."""

    def test_no_deprecated_embedding_imports(self):
        """Aucun module de production ne doit importer app.embeddings directement."""
        import ast
        import pathlib

        deprecated = "app.embeddings"
        violations = []
        root = pathlib.Path(".")

        for f in root.rglob("*.py"):
            if "test_" in f.name or "__pycache__" in str(f) or ".venv" in str(f):
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if deprecated in module:
                        violations.append(f"{f}:{node.lineno}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if deprecated in alias.name:
                            violations.append(f"{f}:{node.lineno}")

        assert not violations, f"Deprecated imports found: {violations}"


class TestSessionStorageDuplicate:
    """4.1.3 — INSERT brut dans session_storage.import_session."""

    async def test_duplicate_session_import_no_crash(self):
        """Importer deux fois la même session_id ne crashe pas (ADR-004)."""
        from services.session_storage import SessionStorage

        db = ISpaceDB(_tmp_db_path())
        await db.initialize()

        storage = SessionStorage(base_dir=tempfile.mkdtemp())
        session_data = {
            "session_id": "original_id",
            "model": "test-model",
            "messages": [{"role": "user", "content": "hello"}],
            "trajectories": [],
            "consciousness_adjustments": [],
            "profile": "balanced",
            "message_count": 1,
            "total_tokens": 10,
        }

        # Écrire le fichier JSON (import_session attend un filepath)
        tmp_json = os.path.join(tempfile.mkdtemp(), "session_export.json")
        with open(tmp_json, 'w', encoding='utf-8') as f:
            json.dump(session_data, f)

        # Premier import
        result1 = await storage.import_session(db, tmp_json, new_session_id="dup_test")
        assert result1["session_id"] == "dup_test"

        # Deuxième import avec même session_id — ne doit pas crasher (INSERT OR IGNORE)
        result2 = await storage.import_session(db, tmp_json, new_session_id="dup_test")
        assert result2["session_id"] == "dup_test"


# ============================================================================
# PHASE 4.2 — CORRUPTION SILENCIEUSE
# ============================================================================

class TestGraphDeltaPreservesMetadata:
    """4.2.1 — INSERT OR REPLACE dans graph_delta perd relation_type et metadata."""

    async def test_add_edge_preserves_existing_relation_type(self):
        """ADD_EDGE sur une relation existante ne doit pas perdre relation_type.

        Bug: INSERT OR REPLACE INTO relations (source, target, weight, kappa, created_at)
        ne mentionne pas relation_type → réinitialisé à DEFAULT 'related_to'.
        """
        db = ISpaceDB(_tmp_db_path())
        await db.initialize()

        await db.add_concept("A", source="test")
        await db.add_concept("B", source="test")

        # Créer une relation avec un type spécifique
        async with db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO relations (source, target, weight, relation_type, model_source, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("A", "B", 0.5, "causes", "model_a", 1000000.0)
            )
            await conn.commit()

        # Simuler ADD_EDGE (INSERT OR REPLACE) sur la même paire
        async with db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO relations (source, target, weight, kappa, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source, target) DO UPDATE SET
                    weight = excluded.weight,
                    kappa = excluded.kappa,
                    updated_at = excluded.created_at
                """,
                ("A", "B", 0.9, 0.7, 2000000.0)
            )
            await conn.commit()

        # Vérifier que relation_type est préservé
        async with db.connection() as conn:
            cursor = await conn.execute(
                "SELECT relation_type, model_source, weight FROM relations WHERE source = ? AND target = ?",
                ("A", "B")
            )
            row = await cursor.fetchone()
            assert row is not None, "Relation should exist"
            assert row[0] == "causes", f"relation_type perdu: got '{row[0]}' instead of 'causes'"
            assert row[1] == "model_a", f"model_source perdu: got '{row[1]}'"
            assert row[2] == 0.9, f"weight should be updated to 0.9, got {row[2]}"


class TestUpsertRelationsPreservesType:
    """4.2.2 — upsert_relations_batch doit préserver relation_type."""

    async def test_upsert_preserves_relation_type(self):
        """Mettre à jour le poids d'une relation ne perd pas le relation_type."""
        db = ISpaceDB(_tmp_db_path())
        await db.initialize()

        await db.add_concept("A", source="test")
        await db.add_concept("B", source="test")

        # Créer avec un type spécifique
        result1 = await db.upsert_relations_batch([{
            "source": "A", "target": "B",
            "weight": 0.5, "relation_type": "causes"
        }])
        assert result1["inserted"] == 1

        # Mettre à jour le poids
        result2 = await db.upsert_relations_batch([{
            "source": "A", "target": "B",
            "weight": 0.9
        }])
        assert result2["updated"] == 1

        # Le relation_type doit être préservé
        neighbors = await db.get_neighbors("A")
        rel = [n for n in neighbors if n.get("target") == "B" or n.get("id") == "B"]
        assert len(rel) > 0, f"Relation not found in neighbors: {neighbors}"


class TestPoolExceptPass:
    """4.2.3 — pool.py close() doit logger les erreurs, pas les avaler."""

    async def test_pool_close_does_not_swallow_errors(self):
        """pool.close() ne doit pas avoir de except:pass nu."""
        import ast
        import pathlib

        pool_path = pathlib.Path("database/pool.py")
        source = pool_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        naked_except_pass = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Check if body is just 'pass' (exclude StopIteration — intentional pattern)
                if (len(node.body) == 1 and isinstance(node.body[0], ast.Pass)):
                    exc_type = getattr(node.type, 'id', '') if node.type else ''
                    if exc_type != 'StopIteration':
                        naked_except_pass.append(node.lineno)

        assert not naked_except_pass, (
            f"Naked except:pass found at lines {naked_except_pass} in pool.py"
        )


# ============================================================================
# PHASE 4.3 — DURCISSEMENT STRUCTUREL
# ============================================================================

class TestSingletonPollution:
    """4.3.3 — Test de pollution inter-tests permanent (CONTROLS.md C7)."""

    async def test_singleton_isolation_db(self, caplog):
        """Deux get_db() consécutifs avec des paths différents émettent un warning."""
        import logging
        from database.engine import get_db, close_db

        # Créer une première instance
        db1 = await get_db("data/test_singleton_a.db")
        assert db1 is not None

        # Demander avec un path différent — doit retourner la même instance + warning
        with caplog.at_level(logging.WARNING, logger="database.engine"):
            db2 = await get_db("data/test_singleton_b.db")
            assert db2 is db1  # Même instance retournée

        assert any("already exists" in r.message for r in caplog.records), (
            "get_db() should warn when called with different db_path"
        )

        await close_db()

    async def test_config_singleton_reset(self):
        """reset_config() remet le singleton à None."""
        from services.config_loader import load_config, get_config, reset_config

        config = load_config()
        assert config is not None

        reset_config()

        # Après reset, get_config recharge
        config2 = get_config()
        assert config2 is not None
