"""
RED tests for S3-001 à S3-004 — Exceptions silencieuses (blind try/except).

Current state (RED) for each finding:
    S3-001  database/engine.py:137-171 — seed metrological_frames under `except Exception: pass`.
            Any failure (ImportError, SQL corruption, etc.) vanishes with no diagnostic.
    S3-002  services/esmm/pipeline.py:269-277 — portable_json parse uses `except Exception: pass`.
            Malformed JSON is silently skipped; operators cannot distinguish "no meta" from
            "broken meta".
    S3-003  services/esmm/pipeline.py:410-413 — cache lookup swallows ANY Exception with a
            generic warning and returns None. Programming bugs (KeyError, TypeError) are
            indistinguishable from legitimate DB errors.
    S3-004  services/solana/client.py:148-155 — keypair load logs and leaves
            `self._keypair = None` for unexpected errors. The client silently degrades to
            mock mode instead of failing fast.

Expected state after GREEN:
    Each except clause granulates to the expected exception types, logs with meaningful
    context, and (for S3-004 only) re-raises unexpected exceptions.
"""
from __future__ import annotations
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


import json
import logging
import sqlite3
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# S3-001 — engine.initialize() seed frames must log errors, not swallow them.
# ---------------------------------------------------------------------------

class TestS3_001_SeedFramesNotSilent:
    @pytest.mark.asyncio
    async def test_seed_frames_logs_import_error(
        self, tmp_path, caplog, monkeypatch
    ) -> None:
        """If the metrological_frame module import fails, the error must be logged."""
        from database.engine import ISpaceDB

        db_path = tmp_path / "eng_s3001.db"
        db = ISpaceDB(str(db_path))

        # Force an ImportError from the factory module.
        import services.solana.metrological_frame as mod

        def _raise_import(*args: Any, **kwargs: Any) -> Any:
            raise ImportError("forced test failure (S3-001)")

        monkeypatch.setattr(mod, "create_blockchain_tps_frame", _raise_import)
        monkeypatch.setattr(mod, "create_general_knowledge_frame", _raise_import)

        caplog.set_level(logging.WARNING, logger="database.engine")

        await db.initialize()

        # RED: current `except Exception: pass` emits nothing → no matching record.
        matching = [
            r for r in caplog.records
            if "frame" in r.getMessage().lower()
            or "seed" in r.getMessage().lower()
            or "S3-001" in r.getMessage()
        ]
        assert matching, (
            "S3-001: expected a log entry about frame seeding failure, got "
            f"{[r.getMessage() for r in caplog.records]!r}"
        )


# ---------------------------------------------------------------------------
# S3-002 — _lookup_existing_anchors must log malformed portable_json.
# ---------------------------------------------------------------------------

class TestS3_002_PortableJsonParseNotSilent:
    @pytest.mark.asyncio
    async def test_malformed_portable_json_emits_warning(self, caplog) -> None:
        from services.esmm import pipeline as pipe_mod

        mock_db = MagicMock()
        mock_db.get_attestations_by_question = AsyncMock(
            return_value=[
                {
                    "epistemic_type": "deterministic",
                    "portable_json": "{ this is not valid json",  # broken
                    "timestamp": 1700000000,
                    "subject": "s",
                    "predicate": "p",
                    "object": "o",
                    "consensus_score": 0.9,
                    "metrological_frame": "frame_v1",
                }
            ]
        )

        caplog.set_level(logging.WARNING, logger="services.esmm.pipeline")
        anchors = await pipe_mod._lookup_existing_anchors("q", mock_db)

        # Function must keep returning the list (graceful), but it must log.
        assert isinstance(anchors, list)
        matching = [
            r for r in caplog.records
            if "json" in r.getMessage().lower()
            or "portable" in r.getMessage().lower()
            or "consensus_meta" in r.getMessage().lower()
        ]
        assert matching, (
            "S3-002: expected a warning about malformed portable_json, got "
            f"{[r.getMessage() for r in caplog.records]!r}"
        )


# ---------------------------------------------------------------------------
# S3-003 — _check_cache must distinguish specific DB errors from generic Exception.
# ---------------------------------------------------------------------------

class TestS3_003_CacheLookupGranularity:
    @pytest.mark.asyncio
    async def test_cache_lookup_tags_exception_type(self, caplog) -> None:
        from services.esmm import pipeline as pipe_mod

        mock_db = MagicMock()
        mock_db.get_attestations_by_question = AsyncMock(
            side_effect=sqlite3.OperationalError("database is locked (S3-003)")
        )
        mock_cfg = MagicMock()
        mock_cfg.cache_ttl_hours = 24
        mock_cfg.min_consensus_for_attestation = 0.4
        mock_cfg.use_cache = True

        caplog.set_level(logging.WARNING, logger="services.esmm.pipeline")
        result = await pipe_mod._check_cache("q", mock_db, mock_cfg, None)

        assert result is None, "cache miss must still return None on DB error"

        # GREEN: the log must tag the exception type / name explicitly
        # (currently the generic `%s` formatting loses the type).
        matching = [
            r for r in caplog.records
            if "OperationalError" in r.getMessage()
            or "operationalerror" in r.getMessage().lower()
            or getattr(r, "exc_info", None)
        ]
        assert matching, (
            "S3-003: expected log to identify exception type (OperationalError) or carry exc_info, got "
            f"{[(r.getMessage(), r.exc_info) for r in caplog.records]!r}"
        )


# ---------------------------------------------------------------------------
# S3-004 — _load_keypair must re-raise unexpected exceptions (no silent None).
# ---------------------------------------------------------------------------

class TestS3_004_KeypairLoadFailsFast:
    def test_unexpected_error_during_from_bytes_is_reraised(
        self, tmp_path, monkeypatch
    ) -> None:
        """An unexpected exception inside Keypair.from_bytes must propagate.

        Works whether or not the `solders` library is installed: we patch both
        `_SOLANA_AVAILABLE` (so the load branch is taken) and `Keypair` (mock).
        """
        import services.solana.client as client_mod
        from services.solana.client import EppSolanaClient
        from services.solana.config import SolanaConfig, SolanaCluster

        kp_file = tmp_path / "kp_s3004.json"
        kp_file.write_text(json.dumps(list(range(64))))

        config = SolanaConfig(
            cluster=SolanaCluster.LOCALNET,
            keypair_path=str(kp_file),
        )

        class UnexpectedCryptoError(RuntimeError):
            """Not a JSONDecodeError / FileNotFoundError / ValueError."""

        def _blow_up(*args: Any, **kwargs: Any) -> Any:
            raise UnexpectedCryptoError("forced test failure (S3-004)")

        fake_keypair = MagicMock()
        fake_keypair.from_bytes = _blow_up

        monkeypatch.setattr(client_mod, "_SOLANA_AVAILABLE", True)
        monkeypatch.setattr(client_mod, "Keypair", fake_keypair)

        # RED: current code logs + continues with self._keypair = None.
        # GREEN: unexpected error propagates.
        with pytest.raises(UnexpectedCryptoError, match="S3-004"):
            EppSolanaClient(config)


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
