"""
Centralized configuration loader for EPP_Verdict.

Loads config.yaml once and exposes sections via a singleton.
Modules keep their defaults but can be overridden by config values.

Usage:
    from services.config_loader import get_config, get_section
    config = get_config()
    db_path = get_section("database").get("path", "data/epp.db")
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

logger = logging.getLogger(__name__)

_config: Optional[Dict[str, Any]] = None
_config_path: Optional[Path] = None


# ---------------------------------------------------------------------------
# S6-001 — Pydantic schema for config.yaml.
# Every declared key must actually be read somewhere in the codebase (§5.6).
# `extra="forbid"` at every level rejects typos and stale decorative keys.
# ---------------------------------------------------------------------------

class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatabaseSchema(_Strict):
    # Read by engine.py::get_db() fallback and demos.
    path: str


class FingerprintSchema(_Strict):
    # Read by services/esmm/fingerprint_config.py::load_fingerprint_config().
    enabled: Optional[bool] = None
    max_neighbors: Optional[int] = None
    min_neighbors: Optional[int] = None
    merge_threshold: Optional[float] = None
    subnode_threshold: Optional[float] = None
    matching_algorithm: Optional[str] = None
    timeout_seconds: Optional[int] = None
    min_unique_terms: Optional[int] = None
    inject_micro_graphs: Optional[bool] = None


class EsmmSchema(_Strict):
    # Read by pipeline.py, orchestrator.py, audit_runner.py, cli/epp_cli.py,
    # consensus_engine.py, fingerprint_match.py, fingerprint_config.py.
    default_models: Optional[int] = None
    models: Optional[List[str]] = None
    min_consensus: Optional[float] = None
    cycle_sequence: Optional[List[str]] = None
    use_legacy_relation_groups: Optional[bool] = None
    fingerprint: Optional[FingerprintSchema] = None


class ThresholdsSchema(_Strict):
    # Read by tests/test_phase2_config.py (scientific tier thresholds).
    sandbox: Optional[float] = None
    proposition: Optional[float] = None
    validated: Optional[float] = None
    verified: Optional[float] = None


class ConfidenceSchema(_Strict):
    thresholds: Optional[ThresholdsSchema] = None


class TrackRecordSchema(_Strict):
    # Read by tests/test_phase2_config.py.
    brier_score_window_days: Optional[int] = None


class EmbeddingsSchema(_Strict):
    # Read by tests/test_phase02_search.py.
    active_model: Optional[str] = None
    fallback_reembed: Optional[bool] = None
    similarity_min_score: Optional[float] = None


class SolanaSchema(_Strict):
    # Read by tests/test_phase2_config.py (cluster guard: devnet or localnet).
    cluster: Optional[str] = None


class AdapterSchema(_Strict):
    # Declared in config.yaml for all source adapters (OpenSanctions, OFAC,
    # EU-CFSP, Verra VCS). Fields documented for future runtime toggles.
    enabled: Optional[bool] = None
    ttl_hours: Optional[int] = None


class SourcesSchema(_Strict):
    adapters: Optional[Dict[str, AdapterSchema]] = None


class CacheSchema(_Strict):
    # min_tier_for_cache is read by pipeline.py::_check_cache().
    # enabled / ttl_hours are exposed via PipelineConfig defaults.
    enabled: Optional[bool] = None
    ttl_hours: Optional[int] = None
    min_tier_for_cache: Optional[str] = None


class AuditSchema(_Strict):
    # Read by cli/epp_cli.py (enabled, db_path) and audit_runner.py (slice_strategy).
    # severity_taxonomy / slither_path are declared for future use.
    enabled: Optional[bool] = None
    db_path: Optional[str] = None
    slice_strategy: Optional[str] = None
    severity_taxonomy: Optional[str] = None
    slither_path: Optional[str] = None


class GeopoliticalSchema(_Strict):
    # default_limit read by services/sources/adapters/acled.py.
    # *_env keys are the names of env vars carrying credentials.
    acled_email_env: Optional[str] = None
    acled_password_env: Optional[str] = None
    default_limit: Optional[int] = None


class FlywheelSchema(_Strict):
    # Read by pipeline.py (ADR-018).
    enabled: Optional[bool] = None


class ConfigSchema(_Strict):
    """Top-level config.yaml schema (S6-001)."""
    database: Optional[DatabaseSchema] = None
    esmm: Optional[EsmmSchema] = None
    confidence: Optional[ConfidenceSchema] = None
    track_record: Optional[TrackRecordSchema] = None
    embeddings: Optional[EmbeddingsSchema] = None
    solana: Optional[SolanaSchema] = None
    sources: Optional[SourcesSchema] = None
    cache: Optional[CacheSchema] = None
    audit: Optional[AuditSchema] = None
    geopolitical: Optional[GeopoliticalSchema] = None
    flywheel: Optional[FlywheelSchema] = None


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load config.yaml and cache as singleton.

    S6-001: the parsed dict is validated against ConfigSchema before caching.
    Any unknown key or wrong-typed value raises pydantic.ValidationError at
    startup (fail-fast — no silent fallback to partial config).
    """
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
        raw = yaml.safe_load(f) or {}

    # S6-001: fail-fast validation before the singleton is published.
    try:
        ConfigSchema.model_validate(raw)
    except ValidationError as exc:
        logger.error("Config validation failed for %s: %s", path, exc)
        raise

    _config = raw
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
