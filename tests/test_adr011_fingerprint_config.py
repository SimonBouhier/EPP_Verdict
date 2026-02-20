"""
Tests ADR-011-v2 — FingerprintConfig dataclass + load_fingerprint_config().

RED-GREEN-FIX : ces tests DOIVENT échouer avant implémentation.

Vérifie que :
1. Les defaults sont corrects quand pas de config.yaml.
2. Lecture config.yaml avec section fingerprint.
3. Section manquante → defaults.
4. Override partiel (seuls les champs présents sont modifiés).
"""
import pytest

from services.esmm.fingerprint_config import FingerprintConfig, load_fingerprint_config


# ---------------------------------------------------------------------------
# Test 1 — Defaults corrects
# ---------------------------------------------------------------------------

def test_fingerprint_config_defaults():
    """FingerprintConfig with no arguments has correct defaults."""
    cfg = FingerprintConfig()
    assert cfg.enabled is True
    assert cfg.max_neighbors == 5
    assert cfg.min_neighbors == 3
    assert cfg.merge_threshold == 0.6
    assert cfg.subnode_threshold == 0.3
    assert cfg.matching_algorithm == "jaro_winkler"
    assert cfg.timeout_seconds == 60
    assert cfg.min_unique_terms == 5
    assert cfg.inject_micro_graphs is False


# ---------------------------------------------------------------------------
# Test 2 — Lecture depuis config.yaml (monkeypatch get_section)
# ---------------------------------------------------------------------------

def test_load_fingerprint_config_from_yaml(monkeypatch):
    """load_fingerprint_config() reads esmm.fingerprint from config.yaml."""
    fake_esmm = {
        "fingerprint": {
            "enabled": False,
            "max_neighbors": 10,
            "min_neighbors": 4,
            "merge_threshold": 0.8,
            "subnode_threshold": 0.5,
            "matching_algorithm": "cosine",
            "timeout_seconds": 120,
            "min_unique_terms": 10,
            "inject_micro_graphs": True,
        }
    }
    monkeypatch.setattr(
        "services.esmm.fingerprint_config.get_section",
        lambda section, default=None: fake_esmm if section == "esmm" else (default or {}),
    )
    cfg = load_fingerprint_config()
    assert cfg.enabled is False
    assert cfg.max_neighbors == 10
    assert cfg.min_neighbors == 4
    assert cfg.merge_threshold == 0.8
    assert cfg.subnode_threshold == 0.5
    assert cfg.matching_algorithm == "cosine"
    assert cfg.timeout_seconds == 120
    assert cfg.min_unique_terms == 10
    assert cfg.inject_micro_graphs is True


# ---------------------------------------------------------------------------
# Test 3 — Section manquante → defaults
# ---------------------------------------------------------------------------

def test_load_fingerprint_config_missing_section(monkeypatch):
    """Missing esmm.fingerprint section returns all defaults."""
    monkeypatch.setattr(
        "services.esmm.fingerprint_config.get_section",
        lambda section, default=None: {} if section == "esmm" else (default or {}),
    )
    cfg = load_fingerprint_config()
    assert cfg.enabled is True
    assert cfg.max_neighbors == 5
    assert cfg.merge_threshold == 0.6
    assert cfg.timeout_seconds == 60


# ---------------------------------------------------------------------------
# Test 4 — Override partiel
# ---------------------------------------------------------------------------

def test_load_fingerprint_config_partial_override(monkeypatch):
    """Partial fingerprint section: only specified fields overridden, rest are defaults."""
    fake_esmm = {
        "fingerprint": {
            "merge_threshold": 0.75,
            "timeout_seconds": 30,
        }
    }
    monkeypatch.setattr(
        "services.esmm.fingerprint_config.get_section",
        lambda section, default=None: fake_esmm if section == "esmm" else (default or {}),
    )
    cfg = load_fingerprint_config()
    # Overridden
    assert cfg.merge_threshold == 0.75
    assert cfg.timeout_seconds == 30
    # Defaults preserved
    assert cfg.enabled is True
    assert cfg.max_neighbors == 5
    assert cfg.min_neighbors == 3
    assert cfg.matching_algorithm == "jaro_winkler"
    assert cfg.min_unique_terms == 5
    assert cfg.inject_micro_graphs is False
