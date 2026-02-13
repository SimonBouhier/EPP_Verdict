"""
Scenario 2 -- False claim rejection.

Executes the ESMM pipeline with a false claim.
Uses low-consensus synthetic triplets to simulate model disagreement.

Expected result:
    Low consensus (< 0.4), tier `sandbox`, no graph injection.
"""

import asyncio
import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.engine import ISpaceDB
from database.pool import close_pool
from services.esmm.pipeline import run_pipeline, PipelineConfig
from services.providers.mock_provider import make_synthetic_triplets
from services.esmm.triplet_adapter import adapt_all


async def main():
    print("=" * 60)
    print("SCENARIO 2: False claim rejection")
    print("=" * 60)
    print()

    # Setup temp DB
    fd, db_path = tempfile.mkstemp(suffix="_demo.db")
    os.close(fd)
    db = ISpaceDB(db_path)
    await db.initialize()

    question = "Bitcoin was invented by Elon Musk"
    config = PipelineConfig(metrological_frame="general_knowledge_v1.0")

    print(f"Question: {question}")
    print(f"Frame: {config.metrological_frame}")
    print()

    # Use LOW consensus triplets to simulate disagreement on false claim
    synthetic = make_synthetic_triplets(n=1, base_consensus=0.25)
    adapted = adapt_all(synthetic)

    from unittest.mock import patch

    async def mock_extract(*args, **kwargs):
        return (adapted, 1)

    with patch("services.esmm.pipeline._extract_triplets_from_question",
               side_effect=mock_extract):
        result = await run_pipeline(
            question=question,
            db=db,
            config=config,
        )

    # Display results
    print(f"Run ID: {result.run_id}")
    print(f"Triplets extracted: {result.triplets_extracted}")
    print(f"Attestations: {result.triplets_attested}")
    print(f"Injected to graph: {result.triplets_injected}")
    print(f"Duration: {result.duration_ms:.0f}ms")
    print()

    if result.attestations:
        for att in result.attestations:
            print(f"  [{att.confidence_tier.upper()}] {att.subject} -> {att.predicate} -> {att.object}")
            print(f"    Consensus: {att.consensus_score:.2%}")
            if att.confidence_tier == "sandbox":
                print("    CORRECT: False claim stays in sandbox")
    else:
        print("  No attestations produced (consensus too low to attest).")
        print("  CORRECT: False claims should not produce attestations.")

    # Verify no graph injection
    assert result.triplets_injected == 0, "False claims should NOT be injected into graph"
    print()
    print("  Graph injection: 0 (correct -- false claims excluded)")

    print()
    print("Scenario 2 complete.")

    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
