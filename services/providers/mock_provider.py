"""
MockProvider for testing the full ESMM pipeline without real LLMs.

Two levels of mock (D10):
  1. Synthetic triplets: make_synthetic_triplets() returns pre-built ConsensusTriplet
  2. Realistic mock: MockProvider implements ModelProvider, returns text containing
     extractible triplets for TripletExtractor.
"""

import hashlib
import time
from typing import List, Dict, Any, Optional

from .base import (
    ModelProvider,
    StructuredQuery,
    StructuredResponse,
    ModelMetadata,
)


# ============================================================================
# RESPONSE SETS — text containing extractible triplets
# ============================================================================

RESPONSE_SETS: Dict[str, List[str]] = {
    "default": [
        (
            "Solana is a high-performance blockchain platform. "
            "Solana uses proof of history as its consensus mechanism. "
            "The effective TPS of Solana exceeds 3000 transactions per second. "
            "Solana was founded by Anatoly Yakovenko in 2017. "
            "Proof of history provides a cryptographic timestamp ordering."
        ),
        (
            "Solana achieves high throughput through proof of history combined with "
            "tower BFT consensus. The network processes over 3000 TPS under normal "
            "conditions. Solana validators use GPU-accelerated transaction verification. "
            "The SOL token is used for staking and transaction fees."
        ),
        (
            "The Solana blockchain utilizes proof of history for transaction ordering. "
            "Anatoly Yakovenko created Solana to solve scalability issues. "
            "Solana's TPS performance exceeds most layer-1 blockchains. "
            "The network uses a leader rotation schedule for block production."
        ),
    ],
    "bitcoin": [
        (
            "Bitcoin was created by Satoshi Nakamoto in 2009. "
            "Bitcoin uses proof of work as its consensus mechanism. "
            "The Bitcoin whitepaper was published in October 2008. "
            "Satoshi Nakamoto's identity remains unknown."
        ),
        (
            "Bitcoin is a decentralized digital currency. "
            "Satoshi Nakamoto designed Bitcoin's proof of work system. "
            "Bitcoin mining requires solving cryptographic hash puzzles. "
            "The genesis block was mined on January 3, 2009."
        ),
        (
            "Bitcoin's creator is known as Satoshi Nakamoto. "
            "The proof of work consensus prevents double spending. "
            "Bitcoin has a fixed supply of 21 million coins. "
            "The Bitcoin network processes about 7 transactions per second."
        ),
    ],
    "bitcoin_false_claim": [
        (
            "There is no evidence that Elon Musk invented Bitcoin. "
            "Bitcoin was created by Satoshi Nakamoto, not Elon Musk. "
            "The claim that Elon Musk invented Bitcoin is false."
        ),
        (
            "Elon Musk has publicly denied being Satoshi Nakamoto. "
            "Bitcoin was invented by an anonymous person or group using "
            "the pseudonym Satoshi Nakamoto. Musk was not involved."
        ),
        (
            "The assertion that Elon Musk created Bitcoin is incorrect. "
            "Satoshi Nakamoto published the Bitcoin whitepaper in 2008. "
            "Elon Musk's involvement with crypto started much later with Dogecoin."
        ),
    ],
}


class MockProvider(ModelProvider):
    """
    Mock LLM provider for testing.

    Implements the full ModelProvider interface. Cycles through response sets
    to simulate diversity across models.

    Args:
        model_id: Simulated model name (default: "mock-model-7b")
        provider_id: Provider identifier (default: "mock")
        response_set: Key in RESPONSE_SETS (default: "default")
    """

    def __init__(
        self,
        model_id: str = "mock-model-7b",
        provider_id: str = "mock",
        response_set: str = "default",
    ):
        self.model_id = model_id
        self.provider_id = provider_id
        self.response_set = response_set
        self._call_count = 0

    async def generate(self, query: StructuredQuery) -> StructuredResponse:
        """Return cycling responses from the configured response set."""
        responses = RESPONSE_SETS.get(self.response_set, RESPONSE_SETS["default"])
        text = responses[self._call_count % len(responses)]
        self._call_count += 1
        return StructuredResponse(
            text=text,
            tokens={"prompt": 50, "completion": len(text.split()), "total": 50 + len(text.split())},
            latency_ms=10.0,
            model=self.model_id,
            success=True,
        )

    async def list_models(self) -> List[str]:
        return [self.model_id]

    async def health_check(self) -> Dict[str, Any]:
        return {"status": "healthy", "provider": self.provider_id, "model": self.model_id}

    def get_metadata(self) -> ModelMetadata:
        return ModelMetadata(
            provider_id=self.provider_id,
            model_id=self.model_id,
            architecture_family="mock_family",
            context_window=8192,
            supports_vram_management=False,
        )


# ============================================================================
# SYNTHETIC TRIPLETS — pre-built ConsensusTriplet for direct testing
# ============================================================================

def make_synthetic_triplets(
    n: int = 3,
    base_consensus: float = 0.75,
    models: Optional[List[str]] = None,
) -> list:
    """
    Create N deterministic synthetic ConsensusTriplet objects.

    Args:
        n: Number of triplets to generate
        base_consensus: Base consensus score (varies slightly per triplet)
        models: Contributing model names

    Returns:
        List of ConsensusTriplet dataclass instances
    """
    from services.esmm.consensus_engine import ConsensusTriplet

    if models is None:
        models = ["mock-alpha-7b", "mock-beta-13b", "mock-gamma-70b"]

    subjects = ["solana", "bitcoin", "ethereum", "proof_of_stake", "proof_of_work",
                "tps", "consensus", "blockchain", "validator", "smart_contract"]
    predicates = ["uses", "achieves", "is_a", "has_property", "exceeds",
                  "implements", "relies_on", "processes", "validates", "produces"]
    objects = ["high_throughput", "proof_of_history", "decentralization",
              "3000_tps", "consensus_mechanism", "smart_contracts",
              "transaction_ordering", "block_production", "staking", "finality"]

    triplets = []
    for i in range(n):
        s = subjects[i % len(subjects)]
        p = predicates[i % len(predicates)]
        o = objects[i % len(objects)]

        # Deterministic hash
        raw = f"{s}:{p}:{o}"
        h = hashlib.sha256(raw.encode()).hexdigest()

        # Vary consensus slightly
        score = min(1.0, max(0.0, base_consensus + (i * 0.03 - 0.05)))

        triplets.append(ConsensusTriplet(
            subject=s,
            relation=p,
            object=o,
            avg_confidence=score,
            std_confidence=0.05 + i * 0.01,
            agreement_ratio=score + 0.1 if score < 0.9 else 1.0,
            consensus_score=score,
            contributing_models=models[:min(len(models), 2 + i % 2)],
            triplet_hash=h,
        ))

    return triplets
