"""Tests Phase 2.3 — Frames en DB (metrological_frames table)."""

import pytest
from pathlib import Path


class TestSchemaHasFramesTables:
    """Vérifie que le schéma SQL contient les nouvelles tables."""

    def _read_schema(self) -> str:
        schema_path = Path("database/schema.sql")
        assert schema_path.exists(), "schema.sql missing"
        return schema_path.read_text(encoding="utf-8")

    def test_metrological_frames_table(self):
        schema = self._read_schema()
        assert "CREATE TABLE IF NOT EXISTS metrological_frames" in schema

    def test_model_track_record_table(self):
        schema = self._read_schema()
        assert "CREATE TABLE IF NOT EXISTS model_track_record" in schema

    def test_tier_transitions_table(self):
        schema = self._read_schema()
        assert "CREATE TABLE IF NOT EXISTS tier_transitions" in schema

    def test_brier_score_view(self):
        schema = self._read_schema()
        assert "v_model_brier_scores" in schema

    def test_frames_indexes(self):
        schema = self._read_schema()
        assert "idx_frames_hash" in schema
        assert "idx_frames_domain" in schema

    def test_track_record_indexes(self):
        schema = self._read_schema()
        assert "idx_track_model" in schema
        assert "idx_track_claim" in schema
        assert "idx_track_unresolved" in schema

    def test_transitions_indexes(self):
        schema = self._read_schema()
        assert "idx_transitions_claim" in schema
        assert "idx_transitions_tier" in schema


class TestEngineFrameMethods:
    """Vérifie que les méthodes frame existent dans engine.py."""

    def test_store_frame_exists(self):
        from database.engine import ISpaceDB
        assert hasattr(ISpaceDB, "store_frame")

    def test_get_frame_exists(self):
        from database.engine import ISpaceDB
        assert hasattr(ISpaceDB, "get_frame")

    def test_list_frames_exists(self):
        from database.engine import ISpaceDB
        assert hasattr(ISpaceDB, "list_frames")

    def test_record_model_prediction_exists(self):
        from database.engine import ISpaceDB
        assert hasattr(ISpaceDB, "record_model_prediction")

    def test_resolve_prediction_exists(self):
        from database.engine import ISpaceDB
        assert hasattr(ISpaceDB, "resolve_prediction")

    def test_get_model_brier_score_exists(self):
        from database.engine import ISpaceDB
        assert hasattr(ISpaceDB, "get_model_brier_score")

    def test_log_tier_transition_exists(self):
        from database.engine import ISpaceDB
        assert hasattr(ISpaceDB, "log_tier_transition")
