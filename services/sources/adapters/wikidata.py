"""
Wikidata SPARQL adapter — faits vérifiables (CC-0, 0 credential).
Endpoint: https://query.wikidata.org/sparql

Confiance limitée : Wikidata est éditable publiquement.
Score plafonné à 0.85 (jamais 1.0) pour refléter cette limite.
Les constantes physiques restent dans nist_codata.py (confiance 1.0).
"""
import hashlib
import httpx
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services.sources.adapters.base import SourceAdapter


SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "EPP_Verdict/1.0 (https://github.com/epp-verdict; contact@epp-verdict) httpx/0.27",
}

# Q-ids catalogue — extend as EPP domains grow
QIDS = {
    "speed of light": "Q2111",
    "solana":         "Q106575843",
    "bitcoin":        "Q131723",
    "ethereum":       "Q1769913",
    "proof of work":  "Q1640456",
    "proof of stake": "Q7250139",
}


def _anchor_hash(raw_response: str) -> str:
    return hashlib.sha256(raw_response.encode()).hexdigest()


def query(sparql: str) -> tuple[dict, str]:
    """Execute SPARQL query, return (parsed_json, raw_text) for hashing."""
    resp = httpx.get(
        SPARQL_ENDPOINT,
        params={"query": sparql, "format": "json"},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json(), resp.text


def get_cannabis_legal_status(country_qid: str) -> Optional[dict]:
    sparql = f"""
    SELECT ?item ?itemLabel WHERE {{
      ?item wdt:P31 wd:Q2135494 .
      ?item wdt:P17 wd:{country_qid} .
      SERVICE wikibase:label {{
        bd:serviceParam wikibase:language "en" .
      }}
    }}
    LIMIT 5
    """
    data, raw = query(sparql)
    bindings = data.get("results", {}).get("bindings", [])

    if not bindings:
        return None

    item_label = bindings[0].get("itemLabel", {}).get("value", "unknown")
    item_uri = bindings[0].get("item", {}).get("value", "")

    return {
        "source": "WIKIDATA",
        "entity": item_label,
        "country_qid": country_qid,
        "item_uri": item_uri,
        "anchor_hash": _anchor_hash(raw),
        "url": item_uri,
    }


class WikidataAdapter(SourceAdapter):
    """
    Wikidata SPARQL — faits vérifiables (CC-0, 0 credential).

    Confiance limitée : Wikidata est éditable publiquement.
    Score plafonné à 0.85 (jamais 1.0) pour refléter cette limite.
    Les constantes physiques restent dans nist_codata.py (confiance 1.0).
    """

    SPARQL_ENDPOINT = SPARQL_ENDPOINT
    MAX_CONFIDENCE = 0.85  # Plafond — Wikidata n'est pas une source primaire

    # -----------------------------------------------------------------------
    # fetch()
    # -----------------------------------------------------------------------

    async def fetch(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interroge Wikidata via SPARQL.

        Args:
            query: dict avec l'une de ces formes :
              {"sparql": "SELECT ?x WHERE {...}"}
                → passe la requête telle quelle.
              {"entity": "Donald Trump", "property": "position held",
               "qualifier_date": "2025"}
                → construit le SPARQL automatiquement (recherche par label).

        Returns:
            Réponse JSON brute de l'endpoint SPARQL + métadonnées internes.
        """
        sparql = query.get("sparql")
        if not sparql:
            sparql = self._build_sparql(query)

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                self.SPARQL_ENDPOINT,
                params={"query": sparql, "format": "json"},
                headers=HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()

        return {
            "sparql_results": data,
            "raw_text": resp.text,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def _build_sparql(self, query: Dict[str, Any]) -> str:
        """Construit un SPARQL basique depuis un query dict entity/property."""
        entity = query.get("entity", "")
        prop = query.get("property", "")
        qualifier_date = query.get("qualifier_date")

        # Recherche par label avec filtre sur la propriété si fournie
        date_filter = ""
        if qualifier_date:
            date_filter = f'FILTER(CONTAINS(STR(?value), "{qualifier_date}"))'

        if prop:
            return f"""
SELECT ?item ?itemLabel ?value WHERE {{
  ?item rdfs:label "{entity}"@en .
  ?item wdt:P31 ?type .
  OPTIONAL {{ ?item ?pred ?value .
    ?propEntity wikibase:directClaim ?pred ;
                rdfs:label "{prop}"@en .
    {date_filter}
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
LIMIT 10
"""
        return f"""
SELECT ?item ?itemLabel WHERE {{
  ?item rdfs:label "{entity}"@en .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
LIMIT 10
"""

    # -----------------------------------------------------------------------
    # normalize()
    # -----------------------------------------------------------------------

    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalise la réponse brute Wikidata.

        Returns:
            {"status": "found"|"not_found", "score": float,
             "results": [...], "result_count": int}

        Score = min(MAX_CONFIDENCE, 0.85) si résultats > 0, sinon 0.0.
        JAMAIS 1.0 — Wikidata est éditable publiquement.
        """
        sparql_results = raw.get("sparql_results", raw)
        bindings = sparql_results.get("results", {}).get("bindings", [])
        result_count = len(bindings)

        if result_count == 0:
            return {
                "status": "not_found",
                "score": 0.0,
                "results": [],
                "result_count": 0,
            }

        # Extraire les valeurs des bindings sous forme lisible
        results = []
        for b in bindings:
            results.append({k: v.get("value", "") for k, v in b.items()})

        return {
            "status": "found",
            "score": self.MAX_CONFIDENCE,  # plafonné — jamais 1.0
            "results": results,
            "result_count": result_count,
        }

    # -----------------------------------------------------------------------
    # get_source_version()
    # -----------------------------------------------------------------------

    def get_source_version(self, raw: Dict[str, Any]) -> str:
        """Retourne "wikidata-{date}" basé sur le timestamp de la query."""
        fetched_at = raw.get("fetched_at")
        if fetched_at:
            # Extraire la date (YYYY-MM-DD) depuis l'ISO timestamp
            date_part = fetched_at[:10]
            return f"wikidata-{date_part}"
        return "wikidata-unknown"
