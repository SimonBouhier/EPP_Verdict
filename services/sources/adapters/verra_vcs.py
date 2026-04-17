"""ADR-012 : Adaptateur Verra VCS Registry — L1 déterministe (serial lookup)."""
from typing import Any, Dict

import httpx

from services.sources.adapters.base import SourceAdapter

# Base URL de l'API publique Verra Registry
_VERRA_BASE = "https://registry.verra.org/uiapi/resource/resourceSummary"


class VerraVcsAdapter(SourceAdapter):
    """
    Wrapper HTTP mince vers Verra VCS Registry (données publiques, 0 credential).

    L1 déterministe : lookup par numéro de série ou ID de projet.
    L2 épistémique (soundness méthodologique) hors périmètre ADR-012 step 6.

    query attendu : {"serial": "VCU-123456"} ou {"project_id": "VCS-001234"}
    """

    async def fetch(self, query: Dict[str, Any]) -> Dict[str, Any]:
        identifier = query.get("project_id") or query.get("serial")
        if not identifier:
            raise ValueError("VerraVcsAdapter.fetch: 'serial' or 'project_id' required")

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{_VERRA_BASE}/{identifier}",
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()

    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        status_raw = "unknown"
        for ps in raw.get("participationSummaries", []):
            for attr in ps.get("attributes", []):
                if attr.get("code") == "PROJECT_STATUS":
                    values = attr.get("values", [])
                    if values:
                        status_raw = values[0].get("value", "unknown").lower()
                    break

        if status_raw in ("registered", "active"):
            return {"status": "registered", "score": 1.0}
        elif status_raw in ("crediting period ended", "inactive"):
            return {"status": "inactive", "score": 0.5}
        else:
            return {"status": status_raw, "score": 0.5}

    def get_source_version(self, raw: Dict[str, Any]) -> str:
        date_raw = None
        for ps in raw.get("participationSummaries", []):
            for attr in ps.get("attributes", []):
                if attr.get("code") == "PROJECT_REGISTRATION_DATE":
                    values = attr.get("values", [])
                    if values:
                        date_raw = values[0].get("value")
                    break
            if date_raw:
                break

        if not date_raw:
            for doc in raw.get("documents", []):
                upload = doc.get("uploadDate")
                if upload:
                    date_raw = upload
                    break

        if not date_raw:
            return "verra-vcs-unknown"

        date_part = str(date_raw)[:10]
        return f"verra-vcs-{date_part}"
