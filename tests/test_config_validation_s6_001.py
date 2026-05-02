"""
RED tests for S6-001 — config.yaml must be Pydantic-validated at load time.

Current state (RED):
    services/config_loader.py uses `yaml.safe_load(f) or {}` with no schema
    validation. A typo in a section name or a wrong-typed value is silently
    accepted, and the error surfaces later as a confusing `AttributeError` /
    `TypeError` deep in the pipeline.

Expected state after GREEN:
    load_config() validates the parsed dict against a Pydantic `ConfigSchema`.
    Invalid configs raise a clear `ValidationError` at startup (fail-fast),
    with contextual messages pointing to the offending key/section.
"""
from __future__ import annotations
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


from pathlib import Path

import pytest
import yaml

from services.config_loader import load_config, reset_config


@pytest.fixture(autouse=True)
def clean_singleton():
    reset_config()
    yield
    reset_config()


def _write(tmp_path: Path, payload: dict) -> Path:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.dump(payload), encoding="utf-8")
    return cfg


class TestS6_001_ValidationRejectsUnknownTopLevelKey:
    def test_unknown_top_level_section_is_rejected(self, tmp_path):
        cfg = _write(
            tmp_path,
            {
                "database": {"path": "data/foo.db"},
                "esmm_typo": {"models": ["a"]},  # typo: esmm_typo
            },
        )
        # RED: current loader silently accepts; GREEN: raises ValidationError.
        with pytest.raises(Exception) as excinfo:
            load_config(str(cfg))
        msg = str(excinfo.value)
        assert (
            "esmm_typo" in msg
            or "extra" in msg.lower()
            or "not permitted" in msg.lower()
            or "forbidden" in msg.lower()
        ), f"Expected validation error mentioning unknown key, got: {msg!r}"


class TestS6_001_ValidationRejectsWrongType:
    def test_database_path_must_be_string(self, tmp_path):
        cfg = _write(
            tmp_path,
            {"database": {"path": 12345}},  # int instead of str
        )
        with pytest.raises(Exception) as excinfo:
            load_config(str(cfg))
        assert (
            "path" in str(excinfo.value) or "str" in str(excinfo.value).lower()
        ), f"Expected type error for database.path, got: {excinfo.value!r}"

    def test_esmm_min_consensus_must_be_number(self, tmp_path):
        cfg = _write(
            tmp_path,
            {"esmm": {"min_consensus": "not-a-number"}},
        )
        with pytest.raises(Exception) as excinfo:
            load_config(str(cfg))
        assert (
            "min_consensus" in str(excinfo.value)
            or "float" in str(excinfo.value).lower()
            or "number" in str(excinfo.value).lower()
        ), f"Expected type error for esmm.min_consensus, got: {excinfo.value!r}"


class TestS6_001_RealConfigStillLoads:
    def test_real_config_yaml_is_accepted(self):
        """The actual config.yaml at repo root must remain valid after GREEN."""
        repo_root = Path(__file__).resolve().parents[1]
        cfg_path = repo_root / "config.yaml"
        assert cfg_path.exists(), "config.yaml missing from repo root"
        # Must not raise.
        loaded = load_config(str(cfg_path))
        assert isinstance(loaded, dict)
        assert "database" in loaded
        assert "esmm" in loaded


class TestS6_001_ValidationRejectsUnknownSubKey:
    def test_unknown_key_inside_database_section_is_rejected(self, tmp_path):
        cfg = _write(
            tmp_path,
            {"database": {"path": "data/foo.db", "pools_size_typo": 10}},
        )
        with pytest.raises(Exception) as excinfo:
            load_config(str(cfg))
        assert (
            "pools_size_typo" in str(excinfo.value)
            or "extra" in str(excinfo.value).lower()
        ), f"Expected error for unknown sub-key, got: {excinfo.value!r}"


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
