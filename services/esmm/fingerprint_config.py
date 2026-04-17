"""
ADR-011-v2 — FingerprintConfig dataclass + loader.

Configuration for Semantic Fingerprinting (EXPAND → MATCH → APPLY).
Follows the config pattern from orchestrator.py (_default_cycle_sequence).
"""

from dataclasses import dataclass
from services.config_loader import get_section


@dataclass
class FingerprintConfig:
    """Configuration for semantic fingerprinting reconciliation."""

    enabled: bool = True
    max_neighbors: int = 5
    min_neighbors: int = 3
    merge_threshold: float = 0.6
    subnode_threshold: float = 0.3
    matching_algorithm: str = "jaro_winkler"
    timeout_seconds: int = 60
    min_unique_terms: int = 5
    inject_micro_graphs: bool = False


def load_fingerprint_config() -> FingerprintConfig:
    """Read esmm.fingerprint from config.yaml, fallback to defaults."""
    try:
        esmm = get_section("esmm", {})
        fp = esmm.get("fingerprint", {})
        if not isinstance(fp, dict):
            fp = {}
    except Exception:
        fp = {}

    return FingerprintConfig(
        enabled=fp.get("enabled", True),
        max_neighbors=fp.get("max_neighbors", 5),
        min_neighbors=fp.get("min_neighbors", 3),
        merge_threshold=fp.get("merge_threshold", 0.6),
        subnode_threshold=fp.get("subnode_threshold", 0.3),
        matching_algorithm=fp.get("matching_algorithm", "jaro_winkler"),
        timeout_seconds=fp.get("timeout_seconds", 60),
        min_unique_terms=fp.get("min_unique_terms", 5),
        inject_micro_graphs=fp.get("inject_micro_graphs", False),
    )
