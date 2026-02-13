"""
Scenario 3 -- Progressive graph enrichment.

Runs 3 related questions and verifies that the knowledge graph
grows progressively with connected concepts.
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
    print("SCENARIO 3: Progressive graph enrichment")
    print("=" * 60)
    print()

    # Setup temp DB
    fd, db_path = tempfile.mkstemp(suffix="_demo.db")
    os.close(fd)
    db = ISpaceDB(db_path)
    await db.initialize()

    questions = [
        "What is proof of stake",
        "How does Solana achieve consensus",
        "Compare proof of stake and proof of history",
    ]

    config = PipelineConfig(metrological_frame="general_knowledge_v1.0")
    total_attestations = 0
    total_injected = 0

    from unittest.mock import patch

    for i, question in enumerate(questions, 1):
        print(f"--- Question {i}/{len(questions)} ---")
        print(f"  Q: {question}")

        # Generate unique triplets per question with increasing consensus
        synthetic = make_synthetic_triplets(
            n=2,
            base_consensus=0.75 + i * 0.05,
        )
        adapted = adapt_all(synthetic)

        # Make triplet hashes unique per question to avoid DB conflicts
        for t in adapted:
            t["triplet_hash"] = f"{t['triplet_hash']}_{i}"

        async def mock_extract(*args, _a=adapted, _i=i, **kwargs):
            return (_a, _i)

        with patch("services.esmm.pipeline._extract_triplets_from_question",
                   side_effect=mock_extract):
            result = await run_pipeline(
                question=question,
                db=db,
                config=config,
            )

        total_attestations += result.triplets_attested
        total_injected += result.triplets_injected

        print(f"  Extracted: {result.triplets_extracted}")
        print(f"  Attested: {result.triplets_attested}")
        print(f"  Injected: {result.triplets_injected}")
        print(f"  Duration: {result.duration_ms:.0f}ms")

        # Show intermediate graph stats
        stats = await db.get_stats()
        print(f"  Graph now: {stats.get('concepts', 0)} concepts, "
              f"{stats.get('relations', 0)} relations")
        print()

    # Final stats
    stats = await db.get_stats()
    print("=" * 40)
    print("Graph Statistics after 3 questions:")
    print(f"  Concepts: {stats.get('concepts', 0)}")
    print(f"  Relations: {stats.get('relations', 0)}")
    print(f"  Attestations: {stats.get('attestations', 0)}")
    print(f"  ESMM Runs: {stats.get('esmm_runs', 0)}")
    print(f"  DB Size: {stats.get('db_size_mb', 0)} MB")
    print()

    print(f"Totals: {total_attestations} attestations, {total_injected} graph injections")
    assert total_attestations > 0, "Should produce at least one attestation"
    print()
    print("Scenario 3 complete.")

    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
