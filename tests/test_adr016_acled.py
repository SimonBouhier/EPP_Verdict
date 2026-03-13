"""
ADR-016 — Tests ACLEDAdapter (Lot 5)

6 tests, tous mockés — pas de connexion ACLED réelle requise.
RED avant implémentation (Lots 1-4).
"""

import os
import pytest
from unittest.mock import patch, AsyncMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_events_raw(event_count: int = 500, fatalities: int = 50) -> dict:
    """Simule une réponse ACLED /api/acled/read avec N événements."""
    data = [
        {
            "event_id_cnty": f"YEM{i}",
            "event_date": "2025-01-15",
            "event_type": "Battles",
            "country": "Yemen",
            "fatalities": fatalities // max(event_count, 1),
        }
        for i in range(event_count)
    ]
    return {"status": 1, "success": True, "count": event_count, "data": data}


def _make_forecast_raw(periods: int = 6) -> dict:
    """Simule une réponse ACLED /api/cast/read."""
    predictions = [
        {"period": i + 1, "conflict_probability": 0.70 + i * 0.01}
        for i in range(periods)
    ]
    return {"status": 1, "success": True, "count": periods, "cast": predictions}


# ---------------------------------------------------------------------------
# Test 1 : normalize events mock → score correct
# ---------------------------------------------------------------------------

def test_normalize_events_score():
    """
    normalize() avec 500 événements et baseline=500 → score=1.0, status=stable.
    normalize() avec 1200 événements et baseline=500 → score=1.0 (capped), status=escalation.
    """
    from services.sources.adapters.acled import ACLEDAdapter

    adapter = ACLEDAdapter()

    # Cas stable : event_count == baseline
    raw_stable = _make_events_raw(event_count=500)
    result = adapter.normalize(raw_stable, query={"baseline": 500, "mode": "events"})
    assert result["status"] == "stable", f"Attendu 'stable', obtenu {result['status']!r}"
    assert result["score"] == 1.0, f"Attendu 1.0, obtenu {result['score']}"
    assert result["event_count"] == 500

    # Cas escalation : event_count > 2x baseline
    raw_esc = _make_events_raw(event_count=1200)
    result_esc = adapter.normalize(raw_esc, query={"baseline": 500, "mode": "events"})
    assert result_esc["status"] == "escalation", f"Attendu 'escalation', obtenu {result_esc['status']!r}"
    assert result_esc["score"] == 1.0  # capped at 1.0


# ---------------------------------------------------------------------------
# Test 2 : normalize vide → no_data
# ---------------------------------------------------------------------------

def test_normalize_empty_returns_no_data():
    """normalize({}) → {"status": "no_data", "score": 0.0, "event_count": 0}"""
    from services.sources.adapters.acled import ACLEDAdapter

    adapter = ACLEDAdapter()
    result = adapter.normalize({}, query={"baseline": 500, "mode": "events"})

    assert result["status"] == "no_data", f"Attendu 'no_data', obtenu {result['status']!r}"
    assert result["score"] == 0.0
    assert result["event_count"] == 0


# ---------------------------------------------------------------------------
# Test 3 : normalize forecast mock → status "forecast"
# ---------------------------------------------------------------------------

def test_normalize_forecast_returns_forecast_status():
    """normalize(cast_raw) → {"status": "forecast", "predictions": [...], "periods": N}"""
    from services.sources.adapters.acled import ACLEDAdapter

    adapter = ACLEDAdapter()
    raw = _make_forecast_raw(periods=6)
    result = adapter.normalize(raw, query={"mode": "forecast"})

    assert result["status"] == "forecast", f"Attendu 'forecast', obtenu {result['status']!r}"
    assert "predictions" in result
    assert result["periods"] == 6
    assert len(result["predictions"]) == 6


# ---------------------------------------------------------------------------
# Test 4 : fetch sans credentials → ValueError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_without_credentials_raises():
    """Sans ACLED_EMAIL/ACLED_PASSWORD → ValueError explicite dans fetch()."""
    from services.sources.adapters.acled import ACLEDAdapter

    adapter = ACLEDAdapter()

    with patch.dict(os.environ, {}, clear=False):
        # Supprimer les variables si présentes
        env_clean = {k: v for k, v in os.environ.items()
                     if k not in ("ACLED_EMAIL", "ACLED_PASSWORD")}
        with patch.dict(os.environ, env_clean, clear=True):
            with pytest.raises(ValueError, match="ACLED_EMAIL"):
                await adapter.fetch({"country": "Yemen", "mode": "events"})


# ---------------------------------------------------------------------------
# Test 5 : get_adapter("acled_events") → ACLEDAdapter
# ---------------------------------------------------------------------------

def test_registry_returns_acled_adapter():
    """get_adapter('acled_events') et get_adapter('acled_cast') → instances ACLEDAdapter."""
    from services.sources.adapters import get_adapter
    from services.sources.adapters.acled import ACLEDAdapter

    adapter_events = get_adapter("acled_events")
    adapter_cast = get_adapter("acled_cast")

    assert isinstance(adapter_events, ACLEDAdapter), (
        f"Attendu ACLEDAdapter, obtenu {type(adapter_events)}"
    )
    assert isinstance(adapter_cast, ACLEDAdapter), (
        f"Attendu ACLEDAdapter, obtenu {type(adapter_cast)}"
    )


# ---------------------------------------------------------------------------
# Test 6 : geopolitical_forecast_v1.0 dans PREDEFINED_FRAMES
# ---------------------------------------------------------------------------

def test_geopolitical_frame_registered():
    """PREDEFINED_FRAMES doit contenir 'geopolitical_forecast_v1.0'."""
    from services.solana.metrological_frame import PREDEFINED_FRAMES

    assert "geopolitical_forecast_v1.0" in PREDEFINED_FRAMES, (
        f"Frame manquant. Frames disponibles : {sorted(PREDEFINED_FRAMES)}"
    )

    frame = PREDEFINED_FRAMES["geopolitical_forecast_v1.0"]()
    assert frame.domain == "geopolitical_analysis"
    assert frame.metric == "conflict_forecast_assessment"
    assert "acled_events" in frame.parameters.get("authoritative_sources", [])
