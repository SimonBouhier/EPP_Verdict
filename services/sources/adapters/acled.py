"""ADR-016 : Adaptateur ACLED — données de conflit et prédictions CAST.

Deux modes via query["mode"] :
- "events"   : GET /api/acled/read  — événements de conflit historiques
- "forecast" : GET /api/cast/read   — prédictions CAST sur 6 périodes

Auth : OAuth2 — POST acleddata.com/oauth/token → bearer token, caché 24h.
Credentials : ACLED_EMAIL + ACLED_PASSWORD (env vars uniquement).
"""

import logging
import os
import time
from typing import Any, Dict

import httpx

logger = logging.getLogger("acled")

from services.sources.adapters.base import SourceAdapter


_TOKEN_TTL = 86_400  # 24h en secondes


class ACLEDAdapter(SourceAdapter):
    """Wrapper HTTP mince vers l'API ACLED. Zéro logique métier en dehors de normalize()."""

    # Token OAuth2 caché au niveau de la classe (partagé entre instances)
    _token: str | None = None
    _token_expiry: float = 0.0

    # -----------------------------------------------------------------------
    # Auth OAuth2
    # -----------------------------------------------------------------------

    async def _get_token(self) -> str:
        """Retourne le bearer token OAuth2, en le rafraîchissant si nécessaire."""
        email = os.getenv("ACLED_EMAIL")
        password = os.getenv("ACLED_PASSWORD")
        if not email or not password:
            raise ValueError(
                "ACLED_EMAIL et ACLED_PASSWORD sont requis (env vars). "
                "Configurez-les avant d'utiliser ACLEDAdapter."
            )

        logger.info(f"[ACLED] Token request (cached={bool(ACLEDAdapter._token)})")

        if ACLEDAdapter._token and time.time() < ACLEDAdapter._token_expiry:
            return ACLEDAdapter._token

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://acleddata.com/oauth/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "username": email,
                    "password": password,
                    "grant_type": "password",
                    "client_id": "acled",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        ACLEDAdapter._token = data["access_token"]
        ACLEDAdapter._token_expiry = time.time() + _TOKEN_TTL
        return ACLEDAdapter._token

    # -----------------------------------------------------------------------
    # fetch()
    # -----------------------------------------------------------------------

    async def fetch(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interroge ACLED selon query["mode"].

        Args:
            query: dict avec au minimum {"mode": "events"|"forecast"}.
                   Clés optionnelles : country, event_type, actor1, actor2,
                   event_date_where, fatalities_where, region, baseline.

        Returns:
            Réponse JSON brute de l'API ACLED.
        """
        token = await self._get_token()
        mode = query.get("mode", "events")

        # Construire les paramètres de requête
        from services.config_loader import get_value
        default_limit = get_value("geopolitical", "default_limit", 500)
        params: Dict[str, Any] = {
            "limit": query.get("limit", default_limit),
            "page": query.get("page", 1),
        }
        for key in ("country", "event_type", "actor1", "actor2", "region",
                    "event_date_where", "fatalities_where"):
            if key in query:
                params[key] = query[key]

        if mode == "forecast":
            url = "https://acleddata.com/api/cast/read"
        else:
            url = "https://acleddata.com/api/acled/read"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json()

    # -----------------------------------------------------------------------
    # normalize()
    # -----------------------------------------------------------------------

    def normalize(self, raw: Dict[str, Any], query: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Normalise la réponse brute ACLED.

        Events → {"status": "stable"|"escalation"|"de-escalation"|"no_data",
                  "score": float, "event_count": int, "fatalities": int,
                  "event_types": dict}

        Forecast → {"status": "forecast", "predictions": [...], "periods": int}
        """
        if query is None:
            query = {}

        mode = query.get("mode", "events")

        if mode == "forecast":
            return self._normalize_forecast(raw)
        return self._normalize_events(raw, query)

    def _normalize_events(self, raw: Dict[str, Any], query: Dict[str, Any]) -> Dict[str, Any]:
        """Normalisation pour le mode events."""
        data = raw.get("data", [])
        if not data:
            return {"status": "no_data", "score": 0.0, "event_count": 0,
                    "fatalities": 0, "event_types": {}}

        event_count = len(data)
        fatalities = sum(
            int(e.get("fatalities", 0)) for e in data
            if str(e.get("fatalities", "0")).isdigit()
        )
        event_types: dict[str, int] = {}
        for e in data:
            etype = e.get("event_type", "unknown")
            event_types[etype] = event_types.get(etype, 0) + 1

        baseline = int(query.get("baseline", 500))
        ratio = event_count / baseline if baseline > 0 else 0.0
        score = min(1.0, ratio)

        if ratio > 2.0:
            status = "escalation"
        elif ratio < 0.5:
            status = "de-escalation"
        else:
            status = "stable"

        return {
            "status": status,
            "score": score,
            "event_count": event_count,
            "fatalities": fatalities,
            "event_types": event_types,
        }

    def _normalize_forecast(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalisation pour le mode forecast (CAST)."""
        predictions = raw.get("cast", [])
        if not predictions:
            return {"status": "no_data", "score": 0.0, "event_count": 0,
                    "fatalities": 0, "event_types": {}}

        return {
            "status": "forecast",
            "predictions": predictions,
            "periods": len(predictions),
            "score": float(predictions[0].get("conflict_probability", 0.0))
            if predictions else 0.0,
        }

    # -----------------------------------------------------------------------
    # get_source_version()
    # -----------------------------------------------------------------------

    def get_source_version(self, raw: Dict[str, Any]) -> str:
        """
        Retourne la version de la source :
        - Events → date du dernier événement
        - Forecast → "cast-{N}-periods"
        """
        data = raw.get("data", [])
        if data:
            # Trier par date et retourner la plus récente
            dates = [e.get("event_date", "") for e in data if e.get("event_date")]
            if dates:
                return f"acled-{max(dates)}"

        cast = raw.get("cast", [])
        if cast:
            return f"cast-{len(cast)}-periods"

        return "acled-unknown"
