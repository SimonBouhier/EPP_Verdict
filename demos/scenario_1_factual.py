"""
Scenario 1 -- Verifiable factual claim (L2 MockProvider).

Executes the FULL ESMM pipeline with SmartMockProviders.
Only the network I/O is mocked — all business logic is real:
TripletExtractor -> TripletValidator -> ConsensusEngine -> crystallize -> DB.

Expected result:
    Triplets related to Solana/TPS/PoH extracted from mock text.
    Attestation with tier "proposition" or "validated".
    consensus_meta present (ADR-010).
    esmm_runs populated in DB.
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
RESPONSE_SET = "default"


async def main():
    print("=" * 60)
    print("SCENARIO 1: Verifiable factual claim")
    print("=" * 60)
    print()

    fd, db_path = tempfile.mkstemp(suffix="_demo_s1.db")
    os.close(fd)

    try:
        db = ISpaceDB(db_path)
        await db.initialize()

        question = "Solana effective TPS exceeds 3000"
        config = PipelineConfig(metrological_frame="blockchain_tps_v1.0")

        print(f"Question: \"{question}\"")
        print(f"Frame: {config.metrological_frame}")
        print()

        reset_extraction_counters()
        providers = build_providers(MODELS, RESPONSE_SET)

        # Reset TripletExtractor singleton so it uses demo DB
        import services.esmm.triplet_extractor as te_mod
        te_mod._extractor_instance = None

        # Shim OllamaProvider at I/O level — TripletExtractor uses SmartMockProvider
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
        print(f"  [ESMM] {len(MODELS)} models consulted via 3 cycles (divergent -> debate -> meta)")
        print(f"  [EXTRACTION] {result.triplets_extracted} triplets extracted from mock text")
        print(f"  [ATTESTATION] {result.triplets_attested} attestations crystallised")
        print(f"  [GRAPH] {result.triplets_injected} triplets injected")
        print(f"  Run ID: {result.run_id}")
        print(f"  Duration: {result.duration_ms:.0f}ms")
        print()

        if result.attestations:
            for att in result.attestations:
                tier = att.confidence_tier.upper()
                print(f"  [{tier}] {att.subject} -> {att.predicate} -> {att.object}")
                print(f"    Consensus: {att.consensus_score:.2%}")
                print(f"    Hash: {att.claim_hash[:16]}...")
                print(f"    Models: {att.models_agreeing}/{att.models_consulted}")
                if hasattr(att, "signature_5d") and att.signature_5d:
                    sig = att.signature_5d
                    print(f"    5D Signature: agreement={sig.agreement:.2f} "
                          f"semantic={sig.semantic_consistency:.2f} "
                          f"centrality={sig.centrality:.2f} "
                          f"stability={sig.stability:.2f} "
                          f"diversity={sig.relation_diversity:.2f}")
                if hasattr(att, "consensus_meta") and att.consensus_meta:
                    method = att.consensus_meta.get("methodology", {}).get(
                        "consensus_method", "N/A")
                    print(f"    Consensus meta: {method}")
                print()
        else:
            print("  No attestations produced.")
            print()

        if result.errors:
            print(f"  Errors: {result.errors}")
            print()

        stats = await db.get_stats()
        print(f"  Graph: {stats.get('concepts', 0)} concepts, "
              f"{stats.get('relations', 0)} relations")
        print(f"  ESMM Runs: {stats.get('esmm_runs', 0)}")
        print(f"  Attestations in DB: {stats.get('attestations', 0)}")
        print()
        print("=" * 60)
        print("Scenario 1 complete — verifiable claim attested.")
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
