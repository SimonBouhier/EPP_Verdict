"""ADR-012 : Adaptateur Verra VCS Registry — L1 déterministe (serial lookup)."""
from typing import Any, Dict

import httpx

from services.rwa.adapters.base import SourceAdapter

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
        serial = query.get("serial")
        project_id = query.get("project_id")

        async with httpx.AsyncClient(timeout=20.0) as client:
            if serial:
                # Credits endpoint par numéro de série
                resp = await client.get(
                    f"{_VERRA_BASE}/credits/{serial}",
                    params={"$format": "json"},
                )
            elif project_id:
                # Projects endpoint par ID
                resp = await client.get(
                    f"{_VERRA_BASE}/projects/{project_id}",
                    params={"$format": "json"},
                )
            else:
                raise ValueError("VerraVcsAdapter.fetch: 'serial' or 'project_id' required in query")

            resp.raise_for_status()
            return resp.json()

    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        # Verra retourne un objet avec "status" ("active", "retired", etc.)
        status_raw = raw.get("status", raw.get("resourceStatus", "unknown")).lower()
        if status_raw == "active":
            return {"status": "active", "score": 1.0}
        elif status_raw in ("retired", "cancelled"):
            return {"status": "retired", "score": 1.0}
        else:
            return {"status": status_raw, "score": 0.5}

    def get_source_version(self, raw: Dict[str, Any]) -> str:
        # Verra inclut parfois "lastUpdated" ou "issuanceDate"
        return raw.get("lastUpdated", raw.get("issuanceDate", "verra-vcs-unknown"))
