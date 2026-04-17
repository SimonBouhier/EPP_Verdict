"""
Demo helpers — smart mock infrastructure for scenarios 1-3.

Provides a SmartMockProvider shim that:
- Returns prose text for cycle queries (divergent/debate/meta)
- Returns JSON triplets for extraction prompts (TripletExtractor)

This replaces the network I/O layer while keeping all business logic real:
TripletExtractor -> TripletValidator -> ConsensusEngine -> crystallize -> DB.
"""

import json
from typing import Dict, List, Any, Optional

from services.providers.mock_provider import MockProvider, RESPONSE_SETS
from services.providers.base import StructuredQuery, StructuredResponse
from services.esmm.prompts import TRIPLET_EXTRACTION_PROMPT


# ============================================================================
# JSON TRIPLET SETS — what the TripletExtractor expects from models
# ============================================================================
# Each response_set has 3 entries (one per model). For high consensus,
# models should share overlapping triplets. For rejection, models diverge.

EXTRACTION_RESPONSES: Dict[str, List[str]] = {
    # --- Solana/TPS: models agree → high consensus → attestation ---
    "default": [
        json.dumps([
            {"subject": "solana", "relation": "related_to", "object": "proof of history", "confidence": 0.9},
            {"subject": "solana", "relation": "related_to", "object": "high throughput", "confidence": 0.85},
            {"subject": "proof of history", "relation": "enables", "object": "transaction ordering", "confidence": 0.8},
        ]),
        json.dumps([
            {"subject": "solana", "relation": "related_to", "object": "proof of history", "confidence": 0.88},
            {"subject": "solana", "relation": "related_to", "object": "tower bft consensus", "confidence": 0.82},
            {"subject": "solana", "relation": "related_to", "object": "3000 tps", "confidence": 0.78},
        ]),
        json.dumps([
            {"subject": "solana", "relation": "related_to", "object": "proof of history", "confidence": 0.92},
            {"subject": "anatoly yakovenko", "relation": "related_to", "object": "solana", "confidence": 0.85},
            {"subject": "solana", "relation": "related_to", "object": "scalability", "confidence": 0.80},
        ]),
    ],

    # --- False claim: each model extracts different refutation triplets ---
    # No two models share the same (subject, relation, object) →
    # consensus engine finds 0 agreement → no attestation.
    "bitcoin_false_claim": [
        json.dumps([
            {"subject": "bitcoin", "relation": "related_to", "object": "satoshi nakamoto", "confidence": 0.3},
        ]),
        json.dumps([
            {"subject": "elon musk", "relation": "contradicts", "object": "bitcoin inventor claim", "confidence": 0.25},
        ]),
        json.dumps([
            {"subject": "bitcoin whitepaper", "relation": "precedes", "object": "musk crypto involvement", "confidence": 0.2},
        ]),
    ],

    # --- Proof of Stake (Q1 for scenario 3) ---
    "pos": [
        json.dumps([
            {"subject": "proof of stake", "relation": "is_a", "object": "consensus mechanism", "confidence": 0.9},
            {"subject": "proof of stake", "relation": "requires", "object": "token staking", "confidence": 0.85},
        ]),
        json.dumps([
            {"subject": "proof of stake", "relation": "is_a", "object": "consensus mechanism", "confidence": 0.88},
            {"subject": "validators", "relation": "related_to", "object": "proof of stake", "confidence": 0.80},
        ]),
        json.dumps([
            {"subject": "proof of stake", "relation": "is_a", "object": "consensus mechanism", "confidence": 0.92},
            {"subject": "proof of stake", "relation": "related_to", "object": "energy efficiency", "confidence": 0.78},
        ]),
    ],

    # --- Solana consensus (Q2 for scenario 3) ---
    "solana_consensus": [
        json.dumps([
            {"subject": "solana", "relation": "related_to", "object": "proof of history", "confidence": 0.9},
            {"subject": "solana", "relation": "related_to", "object": "tower bft", "confidence": 0.85},
        ]),
        json.dumps([
            {"subject": "solana", "relation": "related_to", "object": "proof of history", "confidence": 0.88},
            {"subject": "proof of history", "relation": "enables", "object": "transaction ordering", "confidence": 0.82},
        ]),
        json.dumps([
            {"subject": "solana", "relation": "related_to", "object": "proof of history", "confidence": 0.92},
            {"subject": "solana", "relation": "related_to", "object": "high throughput", "confidence": 0.80},
        ]),
    ],

    # --- PoS vs PoH comparison (Q3 for scenario 3) ---
    # Includes NEW concepts absent from Q1/Q2 ("validator selection",
    # "time delay function") so the graph grows visibly at every question.
    # Each new-concept triplet appears in 2/3 models (→ 66% consensus > 40% threshold).
    "comparison": [
        json.dumps([
            {"subject": "proof of stake", "relation": "similar_to", "object": "proof of history", "confidence": 0.7},
            {"subject": "validator selection", "relation": "part_of", "object": "proof of stake", "confidence": 0.8},
        ]),
        json.dumps([
            {"subject": "proof of stake", "relation": "similar_to", "object": "proof of history", "confidence": 0.72},
            {"subject": "validator selection", "relation": "part_of", "object": "proof of stake", "confidence": 0.78},
            {"subject": "time delay function", "relation": "part_of", "object": "proof of history", "confidence": 0.75},
        ]),
        json.dumps([
            {"subject": "proof of stake", "relation": "similar_to", "object": "proof of history", "confidence": 0.68},
            {"subject": "time delay function", "relation": "part_of", "object": "proof of history", "confidence": 0.76},
        ]),
    ],
}


def _provider_id(model: str) -> str:
    """Generate provider_id matching cycle_manager convention."""
    return f"ollama-{model.replace(':', '_').replace('.', '_')}"


# Stable anchor: first 80 chars of the real template (before any {placeholder}).
# If the prompt evolves, this anchor follows automatically — no fragile keywords.
_EXTRACTION_ANCHOR = TRIPLET_EXTRACTION_PROMPT.split("{")[0][:80]


def _is_extraction_prompt(messages: list[dict]) -> bool:
    """Detect extraction prompt by matching against the real template anchor."""
    for msg in messages:
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if _EXTRACTION_ANCHOR in content:
                return True
    return False


# Global counter: each SmartMockProvider instance gets a unique index
# per response_set, so the 3 models created by TripletExtractor
# (mistral:7b → idx 0, llama3.1:8b → idx 1, qwen2.5:7b → idx 2)
# each receive a different extraction response.
_extraction_instance_counter: Dict[str, int] = {}


def reset_extraction_counters() -> None:
    """Reset per-response_set counters. Call before each pipeline run."""
    _extraction_instance_counter.clear()


class SmartMockProvider(MockProvider):
    """
    MockProvider that returns JSON triplets for extraction prompts
    and prose text for regular cycle queries.

    Each instance gets a distinct index within its response_set, ensuring
    that the 3 models created by TripletExtractor return different triplets.
    For "agreement" sets, models share overlapping triplets (→ consensus).
    For "false claim" sets, models fully diverge (→ no consensus).
    """

    def __init__(
        self,
        model_id: str = "mock-model-7b",
        provider_id: str = "mock",
        response_set: str = "default",
    ):
        super().__init__(
            model_id=model_id,
            provider_id=provider_id,
            response_set=response_set,
        )
        # Assign a unique index per response_set
        _extraction_instance_counter.setdefault(response_set, 0)
        self._model_index = _extraction_instance_counter[response_set]
        _extraction_instance_counter[response_set] += 1

    async def generate(self, query: StructuredQuery) -> StructuredResponse:
        """Return JSON triplets for extraction prompts, prose otherwise."""
        if _is_extraction_prompt(query.messages):
            extraction_set = EXTRACTION_RESPONSES.get(
                self.response_set, EXTRACTION_RESPONSES["default"]
            )
            # Each model gets a different response based on its instance index
            idx = self._model_index % len(extraction_set)
            text = extraction_set[idx]
            return StructuredResponse(
                text=text,
                tokens={"prompt": 100, "completion": len(text.split()), "total": 100 + len(text.split())},
                latency_ms=5.0,
                model=self.model_id,
                success=True,
            )
        return await super().generate(query)


def make_mock_ollama_class(response_set: str):
    """
    Factory: SmartMockProvider subclass with OllamaProvider's __init__ signature.

    The TripletExtractor hardcodes `OllamaProvider(model=..., timeout=...)`.
    This shim intercepts that creation so the pipeline uses mock text
    instead of hitting the real Ollama network.
    """
    class _MockOllamaProvider(SmartMockProvider):
        def __init__(self, model=None, timeout=120.0, **kwargs):
            super().__init__(
                model_id=model or "mock",
                provider_id=_provider_id(model or "mock"),
                response_set=response_set,
            )

        async def close(self):
            pass

        async def preload_model(self, model: str, keep_alive: str = "5m") -> bool:
            return True

        async def unload_model(self, model: str) -> bool:
            return True

    return _MockOllamaProvider


def build_providers(models: list[str], response_set: str) -> dict:
    """Build providers dict with keys matching cycle_manager's expected format."""
    return {
        _provider_id(m): SmartMockProvider(
            model_id=m,
            provider_id=_provider_id(m),
            response_set=response_set,
        )
        for m in models
    }
