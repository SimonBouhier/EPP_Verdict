"""
Scenario 1 -- Verifiable factual claim.

Executes the ESMM pipeline with MockProviders to produce an attestation
for a verifiable blockchain claim.

Expected result:
    Attestation with tier `validated` or `proposition` based on synthetic
    consensus from MockProviders.
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
    print("SCENARIO 1: Verifiable factual claim")
    print("=" * 60)
    print()

    # Setup temp DB for demo
    fd, db_path = tempfile.mkstemp(suffix="_demo.db")
    os.close(fd)
    db = ISpaceDB(db_path)
    await db.initialize()

    question = "Solana effective TPS exceeds 3000"
    config = PipelineConfig(metrological_frame="blockchain_tps_v1.0")

    print(f"Question: {question}")
    print(f"Frame: {config.metrological_frame}")
    print()

    # Use synthetic triplets via adapted pipeline
    synthetic = make_synthetic_triplets(n=3, base_consensus=0.82)
    adapted = adapt_all(synthetic)

    # Mock extraction to use synthetic triplets
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
            print(f"    Hash: {att.claim_hash[:16]}...")
            print(f"    Models: {att.models_agreeing}/{att.models_consulted}")
            print()
    else:
        print("  No attestations produced.")

    if result.errors:
        print(f"  Errors: {result.errors}")

    # Show graph stats
    stats = await db.get_stats()
    print(f"Graph: {stats.get('concepts', 0)} concepts, {stats.get('relations', 0)} relations")
    print()
    print("Scenario 1 complete.")

    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
