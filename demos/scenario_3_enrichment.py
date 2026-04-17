"""
Scenario 3 -- Progressive graph enrichment (L2 MockProvider).

Runs 3 related questions through the FULL ESMM pipeline.
Each question uses a topic-specific mock response set so the graph
grows with distinct concepts at each iteration.
Only the network I/O is mocked — all business logic is real.

Expected result:
    Q1: PoS concepts appear in graph.
    Q2: Solana/PoH concepts added, links to existing PoS.
    Q3: Comparative relations enrich the graph.
    Stats grow at each iteration.
    Hashes computed by real compute_claim_hash (no manual hack).
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

# Each question gets a topic-specific response set → diverse triplets → graph growth
QUESTIONS = [
    ("What is proof of stake", "pos"),
    ("How does Solana achieve consensus", "solana_consensus"),
    ("Compare proof of stake and proof of history", "comparison"),
]


async def main():
    print("=" * 60)
    print("SCENARIO 3: Progressive graph enrichment")
    print("=" * 60)
    print()

    fd, db_path = tempfile.mkstemp(suffix="_demo_s3.db")
    os.close(fd)

    try:
        db = ISpaceDB(db_path)
        await db.initialize()

        config = PipelineConfig(metrological_frame="general_knowledge_v1.0")
        total_attestations = 0
        total_injected = 0
        prev_concepts = 0
        prev_relations = 0

        import services.esmm.triplet_extractor as te_mod

        for i, (question, response_set) in enumerate(QUESTIONS, 1):
            print(f"--- Question {i}/{len(QUESTIONS)} ---")
            print(f"  Q: \"{question}\"")
            print()

            # Fresh providers + topic-specific response set per question
            reset_extraction_counters()
            providers = build_providers(MODELS, response_set)
            MockOllama = make_mock_ollama_class(response_set)

            # Reset TripletExtractor singleton per question
            te_mod._extractor_instance = None

            with patch("services.providers.ollama.OllamaProvider", MockOllama), \
                 patch("database.engine.get_db", return_value=db):
                result = await run_pipeline(
                    question=question,
                    db=db,
                    config=config,
                    providers=providers,
                    models=MODELS,
                )

            total_attestations += result.triplets_attested
            total_injected += result.triplets_injected

            print(f"  Extracted: {result.triplets_extracted}")
            print(f"  Attested: {result.triplets_attested}")
            print(f"  Injected: {result.triplets_injected}")
            print(f"  Duration: {result.duration_ms:.0f}ms")

            if result.attestations:
                for att in result.attestations:
                    tier = att.confidence_tier.upper()
                    print(f"    [{tier}] {att.subject} -> {att.predicate} -> {att.object}")
                    print(f"      Consensus: {att.consensus_score:.2%} | "
                          f"Hash: {att.claim_hash[:12]}...")

            stats = await db.get_stats()
            concepts = stats.get("concepts", 0)
            relations = stats.get("relations", 0)
            growth_c = f" (+{concepts - prev_concepts})" if i > 1 else ""
            growth_r = f" (+{relations - prev_relations})" if i > 1 else ""
            print(f"  Graph now: {concepts} concepts{growth_c}, "
                  f"{relations} relations{growth_r}")
            prev_concepts = concepts
            prev_relations = relations
            print()

        # Final summary (graph should show growth from diverse topics)
        stats = await db.get_stats()
        print("=" * 40)
        print("Graph Statistics after 3 questions:")
        print(f"  Concepts:     {stats.get('concepts', 0)}")
        print(f"  Relations:    {stats.get('relations', 0)}")
        print(f"  Attestations: {stats.get('attestations', 0)}")
        print(f"  ESMM Runs:    {stats.get('esmm_runs', 0)}")
        print()

        print(f"Totals: {total_attestations} attestations, "
              f"{total_injected} graph injections")
        assert total_attestations > 0, "Should produce at least one attestation"
        print()
        print("=" * 60)
        print("Scenario 3 complete — progressive enrichment demonstrated.")
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
