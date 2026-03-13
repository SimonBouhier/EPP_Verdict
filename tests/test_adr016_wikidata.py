"""
ADR-016 — Tests WikidataAdapter

4 tests, tous mockés — pas de connexion Wikidata réelle requise.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sparql_raw(result_count: int = 3) -> dict:
    """Simule une réponse SPARQL Wikidata avec N résultats."""
    bindings = [
        {"item": {"value": f"http://www.wikidata.org/entity/Q{i}"},
         "itemLabel": {"value": f"Result {i}"}}
        for i in range(result_count)
    ]
    return {
        "sparql_results": {
            "results": {"bindings": bindings}
        },
        "raw_text": "{}",
        "fetched_at": "2026-03-10T12:00:00+00:00",
    }


def _make_empty_raw() -> dict:
    """Simule une réponse SPARQL vide."""
    return {
        "sparql_results": {"results": {"bindings": []}},
        "raw_text": "{}",
        "fetched_at": "2026-03-10T12:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# Test 1 : normalize avec résultats → score <= 0.85
# ---------------------------------------------------------------------------

def test_wikidata_normalize_found():
    """normalize() avec résultats → status='found', score <= 0.85 (jamais 1.0)."""
    from services.sources.adapters.wikidata import WikidataAdapter

    adapter = WikidataAdapter()
    raw = _make_sparql_raw(result_count=3)
    result = adapter.normalize(raw)

    assert result["status"] == "found", f"Attendu 'found', obtenu {result['status']!r}"
    assert result["score"] <= 0.85, f"Score {result['score']} dépasse le plafond 0.85"
    assert result["score"] > 0.0, f"Score doit être > 0 si résultats trouvés"
    assert result["result_count"] == 3
    assert len(result["results"]) == 3


# ---------------------------------------------------------------------------
# Test 2 : normalize vide → not_found, score 0.0
# ---------------------------------------------------------------------------

def test_wikidata_normalize_empty():
    """normalize({}) → {\"status\": \"not_found\", \"score\": 0.0}."""
    from services.sources.adapters.wikidata import WikidataAdapter

    adapter = WikidataAdapter()
    raw = _make_empty_raw()
    result = adapter.normalize(raw)

    assert result["status"] == "not_found", f"Attendu 'not_found', obtenu {result['status']!r}"
    assert result["score"] == 0.0
    assert result["result_count"] == 0
    assert result["results"] == []


# ---------------------------------------------------------------------------
# Test 3 : registre → get_adapter("wikidata") retourne WikidataAdapter
# ---------------------------------------------------------------------------

def test_wikidata_adapter_registered():
    """get_adapter('wikidata') → instance WikidataAdapter."""
    from services.sources.adapters import get_adapter
    from services.sources.adapters.wikidata import WikidataAdapter

    adapter = get_adapter("wikidata")
    assert isinstance(adapter, WikidataAdapter), (
        f"Attendu WikidataAdapter, obtenu {type(adapter)}"
    )


# ---------------------------------------------------------------------------
# Test 4 : plafond MAX_CONFIDENCE même avec 100 résultats
# ---------------------------------------------------------------------------

def test_wikidata_max_confidence_cap():
    """Même avec 100 résultats, score ne dépasse jamais MAX_CONFIDENCE (0.85)."""
    from services.sources.adapters.wikidata import WikidataAdapter

    adapter = WikidataAdapter()
    raw = _make_sparql_raw(result_count=100)
    result = adapter.normalize(raw)

    assert result["score"] <= WikidataAdapter.MAX_CONFIDENCE, (
        f"Score {result['score']} > MAX_CONFIDENCE {WikidataAdapter.MAX_CONFIDENCE}"
    )
    assert result["score"] != 1.0, "Score ne doit jamais valoir 1.0 pour Wikidata"
    assert result["result_count"] == 100
