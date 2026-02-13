"""Tests Phase 2.0 — Config EPP et méthodes engine manquantes."""

import pytest
import yaml
from pathlib import Path


class TestConfigYaml:
    """Vérifie que config.yaml est un fichier EPP propre."""

    def test_config_loads(self):
        config_path = Path("config.yaml")
        assert config_path.exists(), "config.yaml missing"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        assert isinstance(config, dict)

    def test_no_lyra_references(self):
        """Aucune mention de 'Lyra' ou 'lyra' dans la config."""
        with open("config.yaml") as f:
            content = f.read()
        assert "lyra" not in content.lower(), "config.yaml still references Lyra"

    def test_esmm_section_exists(self):
        with open("config.yaml") as f:
            config = yaml.safe_load(f)
        assert "esmm" in config
        assert "default_models" in config["esmm"]
        assert config["esmm"]["default_models"] >= 2

    def test_confidence_section_exists(self):
        with open("config.yaml") as f:
            config = yaml.safe_load(f)
        assert "confidence" in config
        thresholds = config["confidence"]["thresholds"]
        assert thresholds["sandbox"] == 0.0
        assert thresholds["proposition"] == 0.4
        assert thresholds["validated"] == 0.7
        assert thresholds["verified"] == 0.85

    def test_solana_section_exists(self):
        with open("config.yaml") as f:
            config = yaml.safe_load(f)
        assert "solana" in config
        assert config["solana"]["cluster"] in ("devnet", "localnet")
        assert "mainnet" not in config["solana"]["cluster"]

    def test_track_record_section_exists(self):
        with open("config.yaml") as f:
            config = yaml.safe_load(f)
        assert "track_record" in config
        assert "brier_score_window_days" in config["track_record"]

    def test_database_path_is_epp(self):
        with open("config.yaml") as f:
            config = yaml.safe_load(f)
        assert "epp" in config["database"]["path"].lower()
