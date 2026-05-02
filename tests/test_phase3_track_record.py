"""Tests Phase 3 — Track record method signatures and Brier score view."""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


import asyncio
import inspect
import pytest
from pathlib import Path


def _read_schema() -> str:
    schema_path = Path("database/schema.sql")
    assert schema_path.exists(), "schema.sql missing"
    return schema_path.read_text(encoding="utf-8")


class TestRecordModelPrediction:

    def test_record_model_prediction_signature(self):
        """record_model_prediction accepts the expected parameters."""
        from database.engine import ISpaceDB
        method = ISpaceDB.record_model_prediction
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert "model_id" in params
        assert "provider_id" in params
        assert "claim_hash" in params
        assert "predicted_confidence" in params
        assert "predicted_agreed" in params

    def test_record_model_prediction_is_async(self):
        """record_model_prediction is a coroutine function."""
        from database.engine import ISpaceDB
        assert inspect.iscoroutinefunction(ISpaceDB.record_model_prediction)


class TestLogTierTransition:

    def test_log_tier_transition_signature(self):
        """log_tier_transition accepts the expected parameters."""
        from database.engine import ISpaceDB
        method = ISpaceDB.log_tier_transition
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert "claim_hash" in params
        assert "old_tier" in params
        assert "new_tier" in params
        assert "reason" in params

    def test_log_tier_transition_is_async(self):
        """log_tier_transition is a coroutine function."""
        from database.engine import ISpaceDB
        assert inspect.iscoroutinefunction(ISpaceDB.log_tier_transition)


class TestBrierScoreView:

    def test_brier_score_view_exists(self):
        """v_model_brier_scores view is defined in schema."""
        schema = _read_schema()
        assert "v_model_brier_scores" in schema

    def test_brier_score_view_is_create_view(self):
        """v_model_brier_scores is a proper CREATE VIEW statement."""
        schema = _read_schema()
        assert "CREATE VIEW IF NOT EXISTS v_model_brier_scores" in schema


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
