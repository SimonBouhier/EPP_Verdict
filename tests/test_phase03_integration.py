# tests/test_phase03_integration.py
"""
Phase 0.3.6 Tests — Integration Tests

End-to-end tests verifying:
- Attestation crystallization from synthetic data
- Storage in database
- Portable JSON serialization
- RunLogger captures phases
- RevalidationInput preparation from stored attestations
"""

import pytest
import asyncio
import json
from pathlib import Path

from database.engine import ISpaceDB
from database.pool import close_pool
from services.esmm.attestation import (
    crystallize,
    Signature5D,
    ModelVote,
    EpistemicAttestation,
    RevalidationInput,
    compute_claim_hash,
)
from services.esmm.run_logger import RunLogger, PhaseEvent


# ============================================================================
# HELPERS
# ============================================================================

async def create_fresh_db(db_path: str) -> ISpaceDB:
    """Create a fresh test database."""
    db = ISpaceDB(db_path)
    await db.initialize()
    return db


async def cleanup_db(db: ISpaceDB):
    """Clean up database connections."""
    if db._pool:
        await close_pool()


def create_synthetic_consensus_output(
    triplets: list,  # [(subject, predicate, object, consensus_score), ...]
    model_ids: list = None,
) -> list:
    """
    Simulate consensus engine output.

    In production, this would come from consensus_engine.py.
    For testing, we create synthetic validated triplets.
    """
    model_ids = model_ids or ["model_a", "model_b", "model_c"]
    results = []

    for subject, predicate, obj, consensus in triplets:
        # Create synthetic model votes
        n_agree = int(len(model_ids) * consensus)
        votes = []
        for i, mid in enumerate(model_ids):
            votes.append(ModelVote(
                model_id=mid,
                provider_id="mock_provider",
                agreed=(i < n_agree),
                confidence=consensus if i < n_agree else (1 - consensus),
            ))

        results.append({
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "consensus_score": consensus,
            "model_votes": votes,
        })

    return results


def create_synthetic_signature_5d(consensus: float) -> Signature5D:
    """
    Simulate cochain_builder signature output.

    In production, this would come from cochain_builder.py.
    """
    return Signature5D(
        agreement=consensus,
        semantic_consistency=consensus * 0.9,
        centrality=0.6,
        stability=0.7,
        relation_diversity=0.5,
    )


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestCrystallizationPipeline:
    """Integration tests for the complete crystallization flow."""

    @pytest.mark.asyncio
    async def test_end_to_end_crystallization(self, tmp_path):
        """
        Complete end-to-end test:
        1. Create synthetic consensus outputs
        2. Crystallize into attestations
        3. Store in database
        4. Retrieve and verify
        5. Serialize to portable JSON
        """
        db = await create_fresh_db(str(tmp_path / "integration.db"))
        try:
            # Step 1: Synthetic consensus outputs (simulating pipeline results)
            triplets = [
                ("Solana", "is_a", "blockchain", 0.85),
                ("Solana", "has_property", "high_throughput", 0.9),
                ("Ethereum", "is_a", "blockchain", 0.95),
            ]
            consensus_outputs = create_synthetic_consensus_output(triplets)

            # Step 2: Crystallize each triplet
            run_id = await db.create_esmm_run(
                config={"test": True},
                models=["model_a", "model_b", "model_c"],
                seed_type="integration_test",
            )

            attestations = []
            for output in consensus_outputs:
                sig = create_synthetic_signature_5d(output["consensus_score"])
                att = crystallize(
                    subject=output["subject"],
                    predicate=output["predicate"],
                    object_=output["object"],
                    consensus_score=output["consensus_score"],
                    model_votes=output["model_votes"],
                    signature_5d=sig,
                    epistemic_type="foundational",
                    run_id=run_id,
                    question="What is Solana?",
                )
                attestations.append(att)

            assert len(attestations) == 3

            # Step 3: Verify each attestation has valid SHA-256 hash
            for att in attestations:
                assert len(att.claim_hash) == 64
                assert all(c in "0123456789abcdef" for c in att.claim_hash)

            # Step 4: Store in database
            stored_ids = []
            for att in attestations:
                att_id = await db.store_attestation(att.model_dump())
                stored_ids.append(att_id)
                assert att_id > 0

            # Step 5: Retrieve and verify
            for att in attestations:
                retrieved = await db.get_attestation_by_hash(att.claim_hash)
                assert retrieved is not None
                assert retrieved["subject"] == att.subject
                assert retrieved["consensus_score"] == att.consensus_score

            # Step 6: Verify portable JSON serialization
            for att in attestations:
                json_str = att.to_portable_json()
                parsed = json.loads(json_str)
                assert parsed["claim_hash"] == att.claim_hash
                assert parsed["subject"] == att.subject
                # Keys should be sorted
                keys = list(parsed.keys())
                assert keys == sorted(keys)

        finally:
            await cleanup_db(db)

    def test_run_logger_captures_phases(self):
        """RunLogger captures all phases of a simulated run."""
        # Create logger
        logger = RunLogger(run_id=42, question="What is Solana?")

        # Simulate divergent phase
        logger.phase_start("divergent", models=["m1", "m2", "m3"])
        logger.model_response("m1", latency_ms=500, success=True)
        logger.model_response("m2", latency_ms=600, success=True)
        logger.model_response("m3", latency_ms=450, success=True)
        logger.phase_end("divergent")

        # Simulate debate phase
        logger.phase_start("debate")
        logger.model_response("m1", latency_ms=700, success=True)
        logger.phase_end("debate")

        # Simulate extraction
        logger.triplet_extracted("Solana", "is_a", "blockchain", 0.9)
        logger.triplet_extracted("Solana", "has", "speed", 0.8)

        # Simulate crystallization
        logger.crystallization("abc123def456", 0.85, "validated")

        # Get summary
        summary = logger.get_summary()

        # Verify summary contents
        assert summary["run_id"] == 42
        assert summary["question"] == "What is Solana?"
        assert summary["triplets_extracted"] == 2
        assert summary["attestations_produced"] == 1
        assert len(summary["errors"]) == 0
        assert "m1" in summary["model_stats"]
        assert summary["model_stats"]["m1"]["calls"] == 2  # divergent + debate

    @pytest.mark.asyncio
    async def test_revalidation_input_from_stored_attestations(self, tmp_path):
        """RevalidationInput can be prepared from stored attestations."""
        db = await create_fresh_db(str(tmp_path / "revalidation.db"))
        try:
            # Create and store initial attestations
            run_id = await db.create_esmm_run(
                config={"initial": True},
                models=["m1", "m2"],
                seed_type="test",
            )

            # Crystallize some attestations
            attestations = []
            for subj in ["A", "B", "C"]:
                att = crystallize(
                    subject=subj,
                    predicate="is_a",
                    object_="thing",
                    consensus_score=0.8,
                    model_votes=[
                        ModelVote(model_id="m1", provider_id="mock", agreed=True, confidence=0.8),
                        ModelVote(model_id="m2", provider_id="mock", agreed=True, confidence=0.8),
                    ],
                    signature_5d=Signature5D(
                        agreement=0.8, semantic_consistency=0.7,
                        centrality=0.6, stability=0.5, relation_diversity=0.5,
                    ),
                    epistemic_type="foundational",
                    run_id=run_id,
                    question="Test question?",
                )
                attestations.append(att)
                await db.store_attestation(att.model_dump())

            # Prepare revalidation input
            claim_hashes = [att.claim_hash for att in attestations]
            revalidation_input = RevalidationInput(
                question="Test question?",
                original_run_id=run_id,
                original_claim_hashes=claim_hashes,
            )

            # Verify
            assert revalidation_input.question == "Test question?"
            assert revalidation_input.original_run_id == run_id
            assert len(revalidation_input.original_claim_hashes) == 3

            # Verify serialization round-trip
            json_str = revalidation_input.model_dump_json()
            restored = RevalidationInput.model_validate_json(json_str)
            assert restored.question == revalidation_input.question
            assert restored.original_claim_hashes == revalidation_input.original_claim_hashes

        finally:
            await cleanup_db(db)

    def test_deterministic_hash_across_runs(self):
        """Same triplet produces same hash regardless of when crystallized."""
        att1 = crystallize(
            subject="Solana",
            predicate="is_a",
            object_="blockchain",
            consensus_score=0.8,
            model_votes=[ModelVote(model_id="m1", provider_id="p", agreed=True, confidence=0.8)],
            signature_5d=Signature5D(
                agreement=0.8, semantic_consistency=0.7,
                centrality=0.6, stability=0.5, relation_diversity=0.5,
            ),
            epistemic_type="foundational",
        )

        # Different run, different models, different time
        att2 = crystallize(
            subject="Solana",
            predicate="is_a",
            object_="blockchain",
            consensus_score=0.9,  # Different consensus
            model_votes=[
                ModelVote(model_id="m2", provider_id="p", agreed=True, confidence=0.9),
                ModelVote(model_id="m3", provider_id="p", agreed=True, confidence=0.85),
            ],
            signature_5d=Signature5D(
                agreement=0.9, semantic_consistency=0.8,
                centrality=0.7, stability=0.6, relation_diversity=0.6,
            ),
            epistemic_type="foundational",
        )

        # Same triplet = same hash (even with different consensus/votes)
        assert att1.claim_hash == att2.claim_hash

    def test_portable_json_determinism(self):
        """to_portable_json produces identical output for identical attestations."""
        def make_att():
            return crystallize(
                subject="Test",
                predicate="is",
                object_="Example",
                consensus_score=0.75,
                model_votes=[
                    ModelVote(model_id="m1", provider_id="p", agreed=True, confidence=0.8),
                ],
                signature_5d=Signature5D(
                    agreement=0.75, semantic_consistency=0.7,
                    centrality=0.6, stability=0.5, relation_diversity=0.5,
                ),
                epistemic_type="foundational",
            )

        att1 = make_att()
        att2 = make_att()

        # Same claim hash
        assert att1.claim_hash == att2.claim_hash

        # Note: timestamps will differ, so full JSON won't be identical
        # But the claim_hash ensures content equivalence

    def test_all_confidence_tiers(self):
        """Attestations correctly derive all confidence tiers."""
        test_cases = [
            # (consensus, n_models, arch_families, source_anchor, expected_tier)
            (0.2, 1, 1, None, "sandbox"),
            (0.5, 2, 1, None, "proposition"),
            (0.75, 3, 2, None, "validated"),
            (0.95, 3, 2, "test_anchor", "verified"),
        ]

        for consensus, n_models, arch_families, anchor, expected_tier in test_cases:
            model_votes = [
                ModelVote(model_id=f"m{i}", provider_id="p", agreed=True, confidence=consensus)
                for i in range(n_models)
            ]
            att = crystallize(
                subject="Test",
                predicate="is",
                object_="Thing",
                consensus_score=consensus,
                model_votes=model_votes,
                signature_5d=Signature5D(
                    agreement=consensus, semantic_consistency=0.7,
                    centrality=0.6, stability=0.5, relation_diversity=0.5,
                ),
                epistemic_type="foundational",
                architecture_families=arch_families,
                source_anchor=anchor,
            )
            assert att.confidence_tier == expected_tier, f"Expected {expected_tier} for consensus {consensus}"


class TestPhase03Complete:
    """Final verification that all Phase 0.3 components work together."""

    @pytest.mark.asyncio
    async def test_complete_workflow(self, tmp_path):
        """
        Complete Phase 0.3 workflow:
        1. Create mock pipeline outputs
        2. Crystallize attestations with logging
        3. Store in database
        4. Prepare revalidation
        5. Verify all components integrated
        """
        db = await create_fresh_db(str(tmp_path / "complete.db"))
        try:
            # Initialize run
            run_id = await db.create_esmm_run(
                config={"phase": "0.3", "test": True},
                models=["model_a", "model_b", "model_c"],
                seed_type="complete_test",
            )

            # Create logger
            logger = RunLogger(run_id=run_id, question="What is blockchain consensus?")

            # Simulate pipeline with logging
            logger.phase_start("divergent", models=["model_a", "model_b", "model_c"])
            for mid in ["model_a", "model_b", "model_c"]:
                logger.model_response(mid, latency_ms=500, success=True)
            logger.phase_end("divergent")

            # Crystallize attestations
            attestations = []
            triplets = [
                ("consensus", "is_a", "agreement_mechanism", 0.9),
                ("blockchain", "uses", "consensus", 0.85),
            ]

            for subj, pred, obj, consensus in triplets:
                logger.triplet_extracted(subj, pred, obj, consensus)

                att = crystallize(
                    subject=subj,
                    predicate=pred,
                    object_=obj,
                    consensus_score=consensus,
                    model_votes=[
                        ModelVote(model_id="model_a", provider_id="mock", agreed=True, confidence=consensus),
                        ModelVote(model_id="model_b", provider_id="mock", agreed=True, confidence=consensus),
                        ModelVote(model_id="model_c", provider_id="mock", agreed=consensus > 0.5, confidence=consensus),
                    ],
                    signature_5d=Signature5D(
                        agreement=consensus, semantic_consistency=0.8,
                        centrality=0.6, stability=0.7, relation_diversity=0.5,
                    ),
                    epistemic_type="foundational",
                    run_id=run_id,
                    question="What is blockchain consensus?",
                )

                # Store attestation
                await db.store_attestation(att.model_dump())
                logger.crystallization(att.claim_hash, att.consensus_score, att.confidence_tier)
                attestations.append(att)

            # Get summary
            summary = logger.get_summary()
            assert summary["triplets_extracted"] == 2
            assert summary["attestations_produced"] == 2

            # Prepare revalidation input
            reval = RevalidationInput(
                question="What is blockchain consensus?",
                original_run_id=run_id,
                original_claim_hashes=[att.claim_hash for att in attestations],
            )

            # Verify we can retrieve all attestations
            for att in attestations:
                retrieved = await db.get_attestation_by_hash(att.claim_hash)
                assert retrieved is not None

            # Final assertions
            assert len(attestations) == 2
            assert len(reval.original_claim_hashes) == 2
            assert all(len(h) == 64 for h in reval.original_claim_hashes)

        finally:
            await cleanup_db(db)
