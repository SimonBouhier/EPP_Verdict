"""ADR-012 : Adaptateur OFAC SDN (US Treasury) — POST /screening."""
import os
from typing import Any, Dict

import httpx

from services.sources.adapters.base import SourceAdapter


class OfacAdapter(SourceAdapter):
    """
    Wrapper HTTP mince vers l'API OFAC SDN.
    Credentials via OFAC_API_KEY (env var — jamais en config.yaml versionné).
    """

    def __init__(self) -> None:
        self._endpoint = os.getenv(
            "OFAC_ENDPOINT", "https://api.ofac-api.com/v4/screen"
        )
        self._api_key = os.getenv("OFAC_API_KEY", "")

    async def fetch(self, query: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"apiKey": self._api_key, "Content-Type": "application/json"}
        payload = {
            "apiKey": self._api_key,
            "minScore": 85,
            "source": ["SDN"],
            "cases": [{"name": query.get("name", ""), "type": "individual"}],
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self._endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        results = raw.get("results", [])
        if not results:
            return {"status": "clear", "score": 0.0}
        best_score = max(
            (r.get("matchScore", 0) for case in results for r in case.get("matches", [])),
            default=0,
        )
        score = float(best_score) / 100.0  # OFAC retourne 0-100
        return {"status": "match" if score >= 0.85 else "clear", "score": score}

    def get_source_version(self, raw: Dict[str, Any]) -> str:
        return raw.get("currentProgramDate", raw.get("date", "ofac-unknown"))
