"""ADR-012 : Source Anchor Builder — chemin déterministe."""
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class SourceAnchorSpec:
    """Spécification d'une requête vers une source autoritaire externe."""

    source_id: str       # "ofac_sdn" | "opensanctions" | "verra_vcs" | "eu_cfsp"
    frame_id: str        # Frame métrologique associé
    query: Dict[str, Any]       # Paramètres de la requête
    max_age_hours: int = 24     # TTL — au-delà, re-fetch obligatoire
    min_sources: int = 1        # Sources concordantes requises pour tier "verified"


@dataclass
class SourceAnchorResult:
    """Résultat d'une interrogation de source autoritaire."""

    source_id: str
    raw_response: Dict[str, Any]       # JSON complet — stocké off-chain (SQLite)
    normalized_result: Dict[str, Any]  # {"status": "clear"|"match", "score": float}
    source_anchor: str                 # SHA-256(raw_response canonique) → on-chain
    fetched_at: float
    source_version: str                # Ex: "OFAC-2026-02-25"
    is_fresh: bool
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))


def _canonical_hash(obj: Dict[str, Any]) -> str:
    """SHA-256 du JSON canonique (sorted keys, compact, UTF-8)."""
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def build_source_anchor(spec: SourceAnchorSpec) -> SourceAnchorResult:
    """
    Interroge la source définie par spec, valide, retourne SourceAnchorResult.

    Import tardif de get_adapter pour éviter le cycle esmm → rwa → esmm.
    Lève ValueError si source_id inconnu.
    """
    from services.rwa.adapters import get_adapter  # import tardif — évite cycle circulaire

    adapter = get_adapter(spec.source_id)
    raw = await adapter.fetch(spec.query)
    normalized = adapter.normalize(raw)
    source_anchor = _canonical_hash(raw)

    return SourceAnchorResult(
        source_id=spec.source_id,
        raw_response=raw,
        normalized_result=normalized,
        source_anchor=source_anchor,
        fetched_at=time.time(),
        source_version=adapter.get_source_version(raw),
        is_fresh=True,
    )
