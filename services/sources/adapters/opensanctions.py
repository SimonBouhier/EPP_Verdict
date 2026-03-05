"""ADR-012 : Adaptateur OpenSanctions (yente) — POST /match."""
import os
from typing import Any, Dict

import httpx

from services.sources.adapters.base import SourceAdapter


class OpenSanctionsAdapter(SourceAdapter):
    """Wrapper HTTP mince vers yente. Zéro logique métier."""

    def __init__(self) -> None:
        self._endpoint = os.getenv("OPENSANCTIONS_ENDPOINT", "http://localhost:8080")

    async def fetch(self, query: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._endpoint}/match",
                json={"queries": {"q": query}},
            )
            resp.raise_for_status()
            return resp.json()

    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        results = raw.get("responses", {}).get("q", {}).get("results", [])
        if not results:
            return {"status": "clear", "score": 0.0}
        best = max(results, key=lambda r: r.get("score", 0.0))
        score = float(best.get("score", 0.0))
        return {"status": "match" if score >= 0.85 else "clear", "score": score}

    def get_source_version(self, raw: Dict[str, Any]) -> str:
        # yente inclut "version" dans la réponse si disponible
        return raw.get("version", "opensanctions-unknown")
