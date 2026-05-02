"""Tests Phase 3 — config_loader singleton."""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


import os
import tempfile
import pytest
import yaml

from services.config_loader import (
    load_config,
    get_config,
    get_section,
    get_value,
    reset_config,
)


@pytest.fixture(autouse=True)
def clean_singleton():
    """Reset singleton before each test."""
    reset_config()
    yield
    reset_config()


class TestConfigLoader:

    def test_load_from_explicit_path(self, tmp_path):
        """Loads a config.yaml from an explicit path."""
        cfg_file = tmp_path / "test_config.yaml"
        cfg_file.write_text(yaml.dump({"database": {"path": "data/test.db"}}))
        config = load_config(str(cfg_file))
        assert config["database"]["path"] == "data/test.db"

    def test_get_config_is_singleton(self, tmp_path):
        """get_config() returns the same object on repeated calls."""
        cfg_file = tmp_path / "test_config.yaml"
        cfg_file.write_text(yaml.dump({"database": {"path": "data/test.db"}}))
        load_config(str(cfg_file))
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2

    def test_get_section_returns_section(self, tmp_path):
        """get_section() returns the requested section."""
        cfg_file = tmp_path / "test_config.yaml"
        cfg_file.write_text(yaml.dump({
            "database": {"path": "data/epp.db"},
            "esmm": {"default_models": 3},
        }))
        load_config(str(cfg_file))
        db_section = get_section("database")
        assert db_section["path"] == "data/epp.db"
        esmm_section = get_section("esmm")
        assert esmm_section["default_models"] == 3

    def test_get_section_returns_default_if_missing(self, tmp_path):
        """Default for missing section."""
        cfg_file = tmp_path / "test_config.yaml"
        cfg_file.write_text(yaml.dump({"database": {"path": "data/epp.db"}}))
        load_config(str(cfg_file))
        missing = get_section("nonexistent", {"fallback": True})
        assert missing == {"fallback": True}

    def test_reset_config_clears_singleton(self, tmp_path):
        """reset allows to reload."""
        cfg_file = tmp_path / "test_config.yaml"
        cfg_file.write_text(yaml.dump({"audit": {"enabled": True}}))
        load_config(str(cfg_file))
        assert get_config()["audit"]["enabled"] is True

        reset_config()
        cfg_file.write_text(yaml.dump({"audit": {"enabled": False}}))
        load_config(str(cfg_file))
        assert get_config()["audit"]["enabled"] is False

    def test_missing_config_returns_empty(self, tmp_path, monkeypatch):
        """No crash if config file absent."""
        # Point to a directory where config.yaml does not exist
        # Also patch the module-relative path to prevent finding the real config
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("EPP_CONFIG_PATH", raising=False)
        import services.config_loader as cl
        original_file = cl.__file__
        monkeypatch.setattr(cl, "__file__", str(tmp_path / "fake_module.py"))
        config = load_config()
        assert config == {}
        monkeypatch.setattr(cl, "__file__", original_file)

    def test_env_variable_override(self, tmp_path, monkeypatch):
        """EPP_CONFIG_PATH environment variable is honored."""
        cfg_file = tmp_path / "env_config.yaml"
        cfg_file.write_text(yaml.dump({"database": {"path": "data/env.db"}}))
        monkeypatch.setenv("EPP_CONFIG_PATH", str(cfg_file))
        config = load_config()
        assert config["database"]["path"] == "data/env.db"

    def test_get_value(self, tmp_path):
        """get_value() retrieves a specific key from a section."""
        cfg_file = tmp_path / "test_config.yaml"
        cfg_file.write_text(yaml.dump({
            "database": {"path": "data/epp.db"},
            "esmm": {"default_models": 5},
        }))
        load_config(str(cfg_file))
        assert get_value("database", "path") == "data/epp.db"
        assert get_value("esmm", "default_models") == 5
        assert get_value("database", "missing", "default") == "default"
        assert get_value("nonexistent", "key", "fallback") == "fallback"


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
