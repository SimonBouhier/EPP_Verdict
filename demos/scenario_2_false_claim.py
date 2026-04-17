"""
Scenario 2 -- False claim rejection (L2 MockProvider).

Executes the FULL ESMM pipeline with a known-false claim.
SmartMockProviders return refutation text — models disagree with the claim.
Only the network I/O is mocked — all business logic is real.

Expected result:
    Low consensus or contradictory triplets.
    Tier "sandbox" or 0 attestations produced.
    0 graph injections — false claims are excluded.
"""

import asyncio
import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.engine import ISpaceDB
from database.pool import close_pool
from services.esmm.pipeline import run_pipeline, PipelineConfig
from demos._demo_helpers import build_providers, make_mock_ollama_class, reset_extraction_counters

MODELS = ["mistral:7b", "llama3.1:8b", "qwen2.5:7b"]
RESPONSE_SET = "bitcoin_false_claim"


async def main():
    print("=" * 60)
    print("SCENARIO 2: False claim rejection")
    print("=" * 60)
    print()

    fd, db_path = tempfile.mkstemp(suffix="_demo_s2.db")
    os.close(fd)

    try:
        db = ISpaceDB(db_path)
        await db.initialize()

        question = "Bitcoin was invented by Elon Musk"
        config = PipelineConfig(metrological_frame="general_knowledge_v1.0")

        print(f"Question: \"{question}\"")
        print(f"Frame: {config.metrological_frame}")
        print()

        reset_extraction_counters()
        providers = build_providers(MODELS, RESPONSE_SET)

        import services.esmm.triplet_extractor as te_mod
        te_mod._extractor_instance = None

        MockOllama = make_mock_ollama_class(RESPONSE_SET)
        with patch("services.providers.ollama.OllamaProvider", MockOllama), \
             patch("database.engine.get_db", return_value=db):
            result = await run_pipeline(
                question=question,
                db=db,
                config=config,
                providers=providers,
                models=MODELS,
            )

        # --- Display ---
        print(f"  [ESMM] {len(MODELS)} models consulted via real orchestrator")
        print(f"  [EXTRACTION] {result.triplets_extracted} triplets surviving consensus")
        print(f"  [NOTE] Each model extracted triplets, but none reached")
        print(f"         the min_consensus threshold — this is correct behavior.")
        print(f"  [ATTESTATION] {result.triplets_attested} attestations")
        print(f"  [GRAPH] {result.triplets_injected} injections")
        print(f"  Run ID: {result.run_id}")
        print(f"  Duration: {result.duration_ms:.0f}ms")
        print()

        # Pedagogical output: explain WHY the claim is rejected
        if not result.attestations:
            print("  CORRECT: False claim rejected — models disagreed, no consensus reached.")
            print(f"  Each model produced different triplets (by design in the mock),")
            print(f"  but none reached the min_consensus threshold ({config.min_consensus_for_attestation}).")
            print(f"  Result: 0 attestations, 0 graph injections.")
        elif all(att.confidence_tier == "sandbox" for att in result.attestations):
            print("  CORRECT: False claim quarantined in sandbox tier.")
            for att in result.attestations:
                print(f"    [{att.confidence_tier.upper()}] "
                      f"{att.subject} -> {att.predicate} -> {att.object}")
                print(f"      Consensus: {att.consensus_score:.2%}")
        else:
            for att in result.attestations:
                print(f"  [{att.confidence_tier.upper()}] "
                      f"{att.subject} -> {att.predicate} -> {att.object}")
                print(f"    Consensus: {att.consensus_score:.2%}")
                print(f"    Hash: {att.claim_hash[:16]}...")

        print()
        assert result.triplets_injected == 0, (
            f"False claims should NOT be injected into graph, got {result.triplets_injected}"
        )
        print("  Graph injection: 0 (correct — false claims excluded)")

        if result.errors:
            print(f"  Errors: {result.errors}")

        print()
        print("=" * 60)
        print("Scenario 2 complete — false claim correctly rejected.")
        print("=" * 60)

    finally:
        import services.esmm.triplet_extractor as te_mod
        te_mod._extractor_instance = None
        await close_pool()
        try:
            os.unlink(db_path)
        except OSError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
