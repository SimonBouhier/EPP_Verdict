"""
Centralized configuration loader for EPP_Verdict.

Loads config.yaml once and exposes sections via a singleton.
Modules keep their defaults but can be overridden by config values.

Usage:
    from services.config_loader import get_config, get_section
    config = get_config()
    db_path = get_section("database").get("path", "data/epp.db")
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_config: Optional[Dict[str, Any]] = None
_config_path: Optional[Path] = None


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load config.yaml and cache as singleton."""
    global _config, _config_path

    if _config is not None and config_path is None:
        return _config

    if config_path:
        path = Path(config_path)
    elif os.environ.get("EPP_CONFIG_PATH"):
        path = Path(os.environ["EPP_CONFIG_PATH"])
    else:
        candidates = [
            Path("config.yaml"),
            Path(__file__).parent.parent / "config.yaml",
        ]
        path = next((c for c in candidates if c.exists()), None)
        if path is None:
            logger.warning("config.yaml not found, using empty config")
            _config = {}
            return _config

    with open(path, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f) or {}

    _config_path = path
    logger.info(f"[config_loader] Loaded config from {path}")
    return _config


def get_config() -> Dict[str, Any]:
    """Get the loaded configuration (loads if not yet loaded)."""
    if _config is None:
        return load_config()
    return _config


def get_section(section: str, default: Optional[Dict] = None) -> Dict[str, Any]:
    """Get a specific section from the configuration."""
    return get_config().get(section, default or {})


def get_value(section: str, key: str, default: Any = None) -> Any:
    """Get a specific value from a section."""
    return get_section(section).get(key, default)


def reset_config() -> None:
    """Reset the singleton (for testing only)."""
    global _config, _config_path
    _config = None
    _config_path = None
