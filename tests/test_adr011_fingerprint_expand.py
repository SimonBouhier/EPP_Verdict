"""
Tests ADR-011-v2 — fingerprint_expand.py : EXPAND prompt + JSON parser.

RED-GREEN-FIX : ces tests DOIVENT échouer avant implémentation.

Sprint 1.3 : Tests 1-4 (prompt format, parse valid JSON, parse invalid, parse partial)
Sprint 2.6 : Tests 5-7 (expand_terms async, timeout, single model)
"""
import pytest
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

from services.esmm.fingerprint_expand import (
    ExpandResult,
    MicroGraph,
    build_expand_prompt,
    expand_terms,
    parse_expand_response,
)
from services.esmm.fingerprint_config import FingerprintConfig


# ===========================================================================
# Sprint 1.3 — Prompt format + JSON parser
# ===========================================================================


# ---------------------------------------------------------------------------
# Test 1 — Prompt format contains all terms
# ---------------------------------------------------------------------------

def test_build_expand_prompt_contains_terms():
    """Prompt includes all provided terms."""
    terms = ["solana", "proof of history", "consensus"]
    prompt = build_expand_prompt(terms)
    for term in terms:
        assert term in prompt
    # Must mention JSON output format
    assert "JSON" in prompt or "json" in prompt.lower()
    # Must mention relationship types
    assert "is_a" in prompt
    assert "part_of" in prompt


# ---------------------------------------------------------------------------
# Test 2 — Parse valid JSON response
# ---------------------------------------------------------------------------

def test_parse_expand_response_valid_json():
    """Valid JSON is parsed into MicroGraph objects."""
    response = '''{
        "solana": [["is_a", "blockchain"], ["uses", "proof of history"]],
        "proof of history": [["invented_by", "Anatoly Yakovenko"], ["is_a", "consensus mechanism"]]
    }'''
    result = parse_expand_response(response, model_id="mistral:7b")
    assert "solana" in result
    assert "proof of history" in result
    mg = result["solana"]
    assert isinstance(mg, MicroGraph)
    assert mg.term == "solana"
    assert mg.model_id == "mistral:7b"
    assert ("is_a", "blockchain") in mg.neighbors
    assert ("uses", "proof of history") in mg.neighbors
    assert len(mg.neighbors) == 2


# ---------------------------------------------------------------------------
# Test 3 — Parse invalid JSON → empty dict (no exception)
# ---------------------------------------------------------------------------

def test_parse_expand_response_invalid_json():
    """Invalid JSON returns empty dict, never raises."""
    result = parse_expand_response("this is not json at all", model_id="llama3:8b")
    assert result == {}


# ---------------------------------------------------------------------------
# Test 4 — Parse partial JSON (some terms valid, some invalid)
# ---------------------------------------------------------------------------

def test_parse_expand_response_partial():
    """Partial JSON: valid entries kept, invalid entries skipped."""
    response = '''{
        "solana": [["is_a", "blockchain"]],
        "bad_entry": "not a list of pairs",
        "proof of history": [["uses", "tower bft"], ["oops"]],
        "empty": []
    }'''
    result = parse_expand_response(response, model_id="qwen2.5:7b")
    # solana: valid
    assert "solana" in result
    assert result["solana"].neighbors == [("is_a", "blockchain")]
    # bad_entry: value is not a list of pairs → skipped
    assert "bad_entry" not in result
    # proof of history: first pair valid, second invalid (single element) → only valid kept
    assert "proof of history" in result
    assert ("uses", "tower bft") in result["proof of history"].neighbors
    assert len(result["proof of history"].neighbors) == 1
    # empty: no neighbors → skipped (below min useful threshold)
    assert "empty" not in result


# ===========================================================================
# Sprint 2.6 — expand_terms async orchestration
# ===========================================================================


def _make_mock_rotator(responses_by_provider: Dict[str, str]):
    """Create a mock rotator that returns preset responses per provider."""
    rotator = AsyncMock()

    @dataclass
    class FakeResponse:
        provider_id: str
        model: str
        text: str
        latency_ms: float = 100.0
        tokens: dict = field(default_factory=dict)
        success: bool = True
        error: Optional[str] = None

    @dataclass
    class FakeBatchResult:
        results: dict
        total_duration_ms: float = 200.0
        providers_processed: int = 0
        questions_per_provider: int = 1

    async def fake_batch(provider_ids, questions, **kwargs):
        # C3 correction: each call MUST receive exactly 1 provider (zero contamination)
        assert len(provider_ids) == 1, (
            f"batch_sequential_providers called with {len(provider_ids)} providers "
            f"— expected 1 (zero contamination violated)"
        )
        results = {}
        for pid in provider_ids:
            text = responses_by_provider.get(pid, "{}")
            results[pid] = [FakeResponse(
                provider_id=pid,
                model=pid.replace(":", "-"),
                text=text,
            )]
        return FakeBatchResult(
            results=results,
            providers_processed=len(provider_ids),
            questions_per_provider=len(questions),
        )

    rotator.batch_sequential_providers = fake_batch
    return rotator


# ---------------------------------------------------------------------------
# Test 5 — expand_terms: per-model isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expand_terms_per_model_isolation():
    """Each model only receives its own terms; results aggregated correctly."""
    model_triplets = {
        "mistral:7b": [
            {"subject": "solana", "relation": "uses", "object": "proof of history"},
        ],
        "llama3:8b": [
            {"subject": "ethereum", "relation": "is_a", "object": "blockchain"},
        ],
    }
    responses = {
        "mistral:7b": '{"solana": [["is_a", "blockchain"]], "proof of history": [["is_a", "consensus mechanism"]]}',
        "llama3:8b": '{"ethereum": [["is_a", "blockchain"]], "blockchain": [["has", "blocks"]]}',
    }
    rotator = _make_mock_rotator(responses)
    config = FingerprintConfig()
    provider_to_model = {"mistral:7b": "mistral:7b", "llama3:8b": "llama3:8b"}

    result = await expand_terms(
        model_triplets=model_triplets,
        rotator=rotator,
        provider_ids=["mistral:7b", "llama3:8b"],
        provider_to_model=provider_to_model,
        config=config,
    )
    assert isinstance(result, ExpandResult)
    assert "mistral:7b" in result.micro_graphs
    assert "llama3:8b" in result.micro_graphs
    assert "solana" in result.micro_graphs["mistral:7b"]
    assert "ethereum" in result.micro_graphs["llama3:8b"]
    assert len(result.models_participated) == 2


# ---------------------------------------------------------------------------
# Test 6 — expand_terms: single model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expand_terms_single_model():
    """Works with a single model."""
    model_triplets = {
        "mistral:7b": [
            {"subject": "solana", "relation": "uses", "object": "PoH"},
        ],
    }
    responses = {
        "mistral:7b": '{"solana": [["is_a", "blockchain"]], "PoH": [["is_a", "consensus"]]}',
    }
    rotator = _make_mock_rotator(responses)
    config = FingerprintConfig()

    result = await expand_terms(
        model_triplets=model_triplets,
        rotator=rotator,
        provider_ids=["mistral:7b"],
        provider_to_model={"mistral:7b": "mistral:7b"},
        config=config,
    )
    assert result.terms_fingerprinted >= 1
    assert result.models_participated == ["mistral:7b"]


# ---------------------------------------------------------------------------
# Test 7 — expand_terms: parse failure counted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expand_terms_parse_failure():
    """Invalid JSON from a model is counted as parse failure."""
    model_triplets = {
        "mistral:7b": [
            {"subject": "solana", "relation": "uses", "object": "PoH"},
        ],
        "llama3:8b": [
            {"subject": "ethereum", "relation": "is_a", "object": "blockchain"},
        ],
    }
    responses = {
        "mistral:7b": '{"solana": [["is_a", "blockchain"]]}',
        "llama3:8b": 'totally invalid json',
    }
    rotator = _make_mock_rotator(responses)
    config = FingerprintConfig()

    result = await expand_terms(
        model_triplets=model_triplets,
        rotator=rotator,
        provider_ids=["mistral:7b", "llama3:8b"],
        provider_to_model={"mistral:7b": "mistral:7b", "llama3:8b": "llama3:8b"},
        config=config,
    )
    assert result.parse_failures >= 1
    assert "mistral:7b" in result.micro_graphs
