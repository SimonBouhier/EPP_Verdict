# tests/test_phase03_revalidation.py
"""
Phase 0.3.5 Tests — Revalidation

Tests for:
- RevalidationInput serialization
- Convergence comparison logic
- Divergence detection
- Database storage of revalidation inputs
"""

import pytest
import asyncio
import time
from services.esmm.attestation import (
    RevalidationInput,
    EpistemicAttestation,
    crystallize,
    Signature5D,
    ModelVote,
    compute_claim_hash,
)


class TestRevalidationInput:
    """Tests pour RevalidationInput."""

    def test_serialization(self):
        """RevalidationInput se sérialise et désérialise."""
        ri = RevalidationInput(
            question="What is Solana?",
            metrological_frame="tps_v1",
            original_run_id=42,
            original_claim_hashes=["abc123", "def456"],
        )
        j = ri.model_dump_json()
        ri2 = RevalidationInput.model_validate_json(j)
        assert ri2.question == ri.question
        assert ri2.original_run_id == 42
        assert len(ri2.original_claim_hashes) == 2

    def test_required_fields(self):
        """RevalidationInput exige question et original_run_id."""
        with pytest.raises(Exception):
            RevalidationInput(original_run_id=1, original_claim_hashes=[])
        # question is missing

    def test_default_created_at(self):
        """RevalidationInput génère un timestamp par défaut."""
        before = time.time()
        ri = RevalidationInput(
            question="Test?",
            original_run_id=1,
            original_claim_hashes=["h1"],
        )
        after = time.time()
        assert before <= ri.created_at <= after

    def test_optional_fields(self):
        """RevalidationInput accepte les champs optionnels."""
        ri = RevalidationInput(
            question="Test?",
            original_run_id=1,
            original_claim_hashes=[],
            metrological_frame="frame_v1",
            rag_context_snapshot="some context here",
        )
        assert ri.metrological_frame == "frame_v1"
        assert ri.rag_context_snapshot == "some context here"


class TestConvergenceComparison:
    """Tests pour la logique de comparaison de revalidation."""

    def test_same_triplet_same_hash(self):
        """Même triplet canonique → même claim_hash entre validations."""
        h1 = compute_claim_hash("Solana", "is_a", "blockchain")
        h2 = compute_claim_hash("Solana", "is_a", "blockchain")
        assert h1 == h2

    def test_convergence_detection(self):
        """Deux attestations du même claim avec scores proches = convergence."""
        att1 = crystallize(
            subject="Solana", predicate="is_a", object_="blockchain",
            consensus_score=0.8,
            model_votes=[ModelVote(model_id="m1", provider_id="p", agreed=True, confidence=0.8)],
            signature_5d=Signature5D(agreement=0.8, semantic_consistency=0.7,
                                     centrality=0.6, stability=0.5, relation_diversity=0.5),
            epistemic_type="foundational",
        )
        att2 = crystallize(
            subject="Solana", predicate="is_a", object_="blockchain",
            consensus_score=0.85,
            model_votes=[ModelVote(model_id="m2", provider_id="p", agreed=True, confidence=0.9)],
            signature_5d=Signature5D(agreement=0.85, semantic_consistency=0.75,
                                     centrality=0.65, stability=0.55, relation_diversity=0.5),
            epistemic_type="foundational",
            previous_hash=att1.claim_hash,
            validation_count=2,
        )
        # Même hash (même triplet)
        assert att1.claim_hash == att2.claim_hash
        # Score amélioré
        assert att2.consensus_score > att1.consensus_score
        # Revalidation tracée
        assert att2.validation_count == 2
        assert att2.previous_hash == att1.claim_hash

    def test_divergence_detection(self):
        """Deux attestations du même claim avec scores très différents = divergence."""
        att1 = crystallize(
            subject="X", predicate="is_a", object_="Y",
            consensus_score=0.9,
            model_votes=[
                ModelVote(model_id="m1", provider_id="p", agreed=True, confidence=0.9),
                ModelVote(model_id="m2", provider_id="p", agreed=True, confidence=0.9),
                ModelVote(model_id="m3", provider_id="p", agreed=True, confidence=0.9),
            ],
            signature_5d=Signature5D(agreement=0.9, semantic_consistency=0.8,
                                     centrality=0.7, stability=0.6, relation_diversity=0.5),
            epistemic_type="foundational",
            architecture_families=2,
        )
        att2 = crystallize(
            subject="X", predicate="is_a", object_="Y",
            consensus_score=0.3,
            model_votes=[ModelVote(model_id="m4", provider_id="p", agreed=False, confidence=0.3)],
            signature_5d=Signature5D(agreement=0.3, semantic_consistency=0.4,
                                     centrality=0.5, stability=0.3, relation_diversity=0.4),
            epistemic_type="foundational",
        )
        # Même hash mais tiers de confiance différents (validated vs sandbox)
        assert att1.claim_hash == att2.claim_hash
        assert att1.confidence_tier == "validated"
        assert att2.confidence_tier == "sandbox"

    def test_revalidation_input_stores_in_db(self, tmp_path):
        """RevalidationInput est stockable dans esmm_runs."""
        async def run():
            from database.engine import ISpaceDB
            from database.pool import close_pool

            db = ISpaceDB(str(tmp_path / "test.db"))
            await db.initialize()
            try:
                ri = RevalidationInput(
                    question="Test?",
                    original_run_id=1,
                    original_claim_hashes=["hash1"],
                )

                # Créer un run avec revalidation_input
                run_id = await db.create_esmm_run(
                    config={"revalidation_input": ri.model_dump()},
                    models=["m1"],
                    seed_type="revalidation",
                )
                assert run_id > 0
            finally:
                await close_pool()

        asyncio.run(run())


class TestConvergenceReport:
    """Tests pour le rapport de convergence entre attestations."""

    def _make_attestation(self, subject: str, predicate: str, object_: str,
                          consensus: float, model_id: str = "m1") -> EpistemicAttestation:
        """Helper pour créer une attestation de test."""
        return crystallize(
            subject=subject,
            predicate=predicate,
            object_=object_,
            consensus_score=consensus,
            model_votes=[ModelVote(model_id=model_id, provider_id="mock", agreed=True, confidence=consensus)],
            signature_5d=Signature5D(
                agreement=consensus,
                semantic_consistency=0.7,
                centrality=0.6,
                stability=0.5,
                relation_diversity=0.5,
            ),
            epistemic_type="foundational",
        )

    def test_stable_claim_detection(self):
        """Claims stables : même hash, même tier (sandbox avec 1 modèle)."""
        att1 = self._make_attestation("A", "is", "B", 0.7)
        att2 = self._make_attestation("A", "is", "B", 0.8)

        assert att1.claim_hash == att2.claim_hash
        assert att1.confidence_tier == att2.confidence_tier == "sandbox"

    def test_improved_claim_detection(self):
        """Claims améliorés : même hash, tier supérieur (sandbox → proposition)."""
        att1 = self._make_attestation("A", "is", "B", 0.35)  # sandbox (< 0.40)
        att2 = crystallize(
            subject="A", predicate="is", object_="B",
            consensus_score=0.50,
            model_votes=[
                ModelVote(model_id="m1", provider_id="mock", agreed=True, confidence=0.50),
                ModelVote(model_id="m2", provider_id="mock", agreed=True, confidence=0.50),
            ],
            signature_5d=Signature5D(
                agreement=0.50, semantic_consistency=0.7,
                centrality=0.6, stability=0.5, relation_diversity=0.5,
            ),
            epistemic_type="foundational",
        )

        assert att1.claim_hash == att2.claim_hash
        assert att1.confidence_tier == "sandbox"
        assert att2.confidence_tier == "proposition"

    def test_degraded_claim_detection(self):
        """Claims dégradés : même hash, tier inférieur (proposition → sandbox)."""
        att1 = crystallize(
            subject="A", predicate="is", object_="B",
            consensus_score=0.50,
            model_votes=[
                ModelVote(model_id="m1", provider_id="mock", agreed=True, confidence=0.50),
                ModelVote(model_id="m2", provider_id="mock", agreed=True, confidence=0.50),
            ],
            signature_5d=Signature5D(
                agreement=0.50, semantic_consistency=0.7,
                centrality=0.6, stability=0.5, relation_diversity=0.5,
            ),
            epistemic_type="foundational",
        )
        att2 = self._make_attestation("A", "is", "B", 0.35)  # sandbox (< 0.40)

        assert att1.claim_hash == att2.claim_hash
        assert att1.confidence_tier == "proposition"
        assert att2.confidence_tier == "sandbox"

    def test_new_claim_in_revalidation(self):
        """Nouveau claim : hash non présent dans l'original."""
        att1 = self._make_attestation("A", "is", "B", 0.8)
        att2 = self._make_attestation("C", "is", "D", 0.8)  # Different triplet

        assert att1.claim_hash != att2.claim_hash

    def test_lost_claim_in_revalidation(self):
        """Claim perdu : présent dans l'original, absent dans la revalidation."""
        original_hashes = [
            compute_claim_hash("A", "is", "B"),
            compute_claim_hash("C", "is", "D"),
        ]
        new_attestations = [
            self._make_attestation("A", "is", "B", 0.8),
            # Note: "C is D" is missing
        ]
        new_hashes = {att.claim_hash for att in new_attestations}
        lost_hashes = set(original_hashes) - new_hashes

        assert len(lost_hashes) == 1
        assert compute_claim_hash("C", "is", "D") in lost_hashes
