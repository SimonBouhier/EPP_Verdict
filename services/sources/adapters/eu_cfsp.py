"""ADR-012 : Adaptateur EU CFSP / sanctions.network — données ouvertes."""
import os
from typing import Any, Dict
from urllib.parse import quote

import httpx

from services.sources.adapters.base import SourceAdapter


class EuCfspAdapter(SourceAdapter):
    """
    Wrapper HTTP mince vers sanctions.network (EU CFSP — données ouvertes, 0 credential).
    Endpoint: GET /sanctions?q=<name>
    """

    def __init__(self) -> None:
        self._endpoint = os.getenv(
            "EU_CFSP_ENDPOINT", "https://www.sanctions.io/api/search"
        )

    async def fetch(self, query: Dict[str, Any]) -> Dict[str, Any]:
        name = query.get("name", "")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                self._endpoint, params={"q": name, "limit": 5}
            )
            resp.raise_for_status()
            return resp.json()

    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        results = raw.get("results", raw.get("data", []))
        if not results:
            return {"status": "clear", "score": 0.0}
        # Sanctions.io retourne un score de similarité (0.0-1.0)
        best = max(results, key=lambda r: r.get("score", r.get("similarity", 0.0)))
        score = float(best.get("score", best.get("similarity", 0.9)))
        return {"status": "match" if score >= 0.85 else "clear", "score": score}

    def get_source_version(self, raw: Dict[str, Any]) -> str:
        return raw.get("last_updated", raw.get("version", "eu-cfsp-unknown"))
