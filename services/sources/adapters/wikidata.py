"""
Wikidata SPARQL adapter — factual claims anchor.
Endpoint: https://query.wikidata.org/sparql
No API key required. CC-0 license.
"""
import hashlib
import httpx
from typing import Optional


SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {"Accept": "application/sparql-results+json"}

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