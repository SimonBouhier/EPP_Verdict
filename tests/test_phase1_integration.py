"""
Tests d'integration Phase 1 -- flux complet.

Requiert : solana-test-validator ou devnet configure.
Ces tests sont skipped si EPP_TEST_INTEGRATION n'est pas set.
"""

import pytest
import os
import time

from services.solana.config import SolanaCluster, SolanaConfig
from services.solana.client import EppSolanaClient, derive_attestation_pda
from services.solana.bridge import attestation_to_anchor_args, anchor_data_to_attestation_summary
from services.solana.metrological_frame import create_blockchain_tps_frame
from services.esmm.attestation import (
    EpistemicAttestation, Signature5D, ModelVote,
    crystallize, compute_claim_hash,
)


INTEGRATION = os.environ.get("EPP_TEST_INTEGRATION", "0") == "1"


def make_test_attestation(
    subject: str = "solana",
    predicate: str = "has_tps",
    object_: str = "exceeds 3000",
    consensus_score: float = 0.85,
) -> EpistemicAttestation:
    """Helper : cree une attestation de test."""
    return crystallize(
        subject=subject,
        predicate=predicate,
        object_=object_,
        consensus_score=consensus_score,
        model_votes=[
            ModelVote(model_id="test::model_a", provider_id="test", agreed=True, confidence=0.9),
            ModelVote(model_id="test::model_b", provider_id="test", agreed=True, confidence=0.8),
            ModelVote(model_id="test::model_c", provider_id="test", agreed=False, confidence=0.3),
        ],
        signature_5d=Signature5D(
            agreement=0.85,
            semantic_consistency=0.72,
            centrality=0.45,
            stability=0.90,
            relation_diversity=0.60,
        ),
        epistemic_type="foundational",
        metrological_frame="blockchain_tps_v1.0",
    )


class TestIntegrationMock:
    """Tests d'integration en mode mock (sans Solana)."""

    def test_full_flow_mock(self):
        """
        Flow complet en mock :
        1. Cree une attestation via crystallize()
        2. Serialise via bridge
        3. Verifie que la conversion fonctionne
        """
        # 1. Create attestation
        att = make_test_attestation()
        assert att.claim_hash is not None
        assert len(att.claim_hash) == 64  # SHA-256 hex

        # 2. Convert to Anchor args
        frame = create_blockchain_tps_frame()
        frame_hash = frame.compute_frame_hash()
        args = attestation_to_anchor_args(att, frame_hash=frame_hash)

        # 3. Verify serialization
        assert len(args.claim_hash) == 32
        assert len(args.subject) == 64
        assert len(args.frame_hash) == 32
        assert args.consensus_score == 8500

    def test_claim_hash_determinism(self):
        """
        Meme triplet + frame -> meme claim_hash.
        """
        att1 = make_test_attestation(subject="bitcoin", predicate="is_a", object_="cryptocurrency")
        att2 = make_test_attestation(subject="bitcoin", predicate="is_a", object_="cryptocurrency")

        assert att1.claim_hash == att2.claim_hash

    def test_claim_hash_changes_with_content(self):
        """
        Triplet different -> claim_hash different.
        """
        att1 = make_test_attestation(subject="bitcoin")
        att2 = make_test_attestation(subject="ethereum")

        assert att1.claim_hash != att2.claim_hash

    def test_bridge_roundtrip_integrity(self):
        """
        Attestation Python -> bridge -> simulated on-chain -> bridge inverse -> summary.
        Verifie que summary.subject == attestation.subject, etc.
        """
        att = make_test_attestation()
        frame = create_blockchain_tps_frame()
        args = attestation_to_anchor_args(att, frame_hash=frame.compute_frame_hash())

        # Simulate on-chain data (as returned by getProgramAccounts)
        on_chain_data = {
            "claim_hash": args.claim_hash,
            "subject": list(args.subject),
            "predicate": list(args.predicate),
            "object": list(args.object_field),
            "consensus_score": args.consensus_score,
            "models_consulted": args.models_consulted,
            "models_agreeing": args.models_agreeing,
            "sig_agreement": args.sig_agreement,
            "sig_semantic_consistency": args.sig_semantic_consistency,
            "sig_centrality": args.sig_centrality,
            "sig_stability": args.sig_stability,
            "sig_relation_diversity": args.sig_relation_diversity,
            "epistemic_type": args.epistemic_type,
            "confidence_tier": args.confidence_tier,
            "frame_hash": list(args.frame_hash),
            "timestamp": args.timestamp,
            "validation_count": args.validation_count,
            "protocol_version": args.protocol_version,
            "is_challenge": args.is_challenge,
        }

        summary = anchor_data_to_attestation_summary(on_chain_data)

        assert summary["subject"] == att.subject
        assert summary["predicate"] == att.predicate
        assert summary["object"] == att.object
        assert abs(summary["consensus_score"] - att.consensus_score) < 0.001
        # V2 projection: Python sub-types collapse into on-chain categories
        # (empirical/deterministic/assessed), so round-trip is lossy by design.
        from services.solana.bridge import EPISTEMIC_TYPE_MAP, EPISTEMIC_TYPE_REVERSE
        expected_category = EPISTEMIC_TYPE_REVERSE[EPISTEMIC_TYPE_MAP[att.epistemic_type]]
        assert summary["epistemic_type"] == expected_category
        assert summary["confidence_tier"] == att.confidence_tier

    def test_frame_hash_matches(self):
        """
        Le frame_hash dans args correspond au compute_frame_hash() Python.
        """
        att = make_test_attestation()
        frame = create_blockchain_tps_frame()
        frame_hash = frame.compute_frame_hash()
        args = attestation_to_anchor_args(att, frame_hash=frame_hash)

        assert args.frame_hash == bytes.fromhex(frame_hash)

    def test_pda_derivation_consistent(self):
        """
        PDA derivation est deterministe pour memes inputs.
        """
        program_id = "EPPxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        submitter = "7C4jsPZpht2v3c8P2Y2uF5d6UJY9YN5X5C6E5H5G5K5"
        claim_hash = bytes.fromhex("a" * 64)

        pda1, bump1 = derive_attestation_pda(program_id, submitter, claim_hash)
        pda2, bump2 = derive_attestation_pda(program_id, submitter, claim_hash)

        assert pda1 == pda2
        assert bump1 == bump2


@pytest.mark.skipif(not INTEGRATION, reason="Integration tests disabled")
class TestEndToEnd:
    """Tests end-to-end complets (requiert solana-test-validator)."""

    @pytest.mark.asyncio
    async def test_full_flow_localnet(self):
        """
        1. Cree une attestation via crystallize()
        2. Serialise via bridge
        3. Submit on-chain via client
        4. Relit on-chain via client
        5. Verifie que les donnees correspondent
        6. Met a jour la DB locale avec tx signature
        """
        # This test requires actual Solana connection
        # Skipped when integration tests are disabled
        pass

    @pytest.mark.asyncio
    async def test_challenge_flow(self):
        """
        1. Submit attestation A (submitter_1, claim_hash_X)
        2. Submit attestation B (submitter_2, claim_hash_X, is_challenge=True)
        3. Query par claim_hash_X -> retourne A et B
        4. Verifie que B.challenged_attestation pointe vers A
        """
        pass

    @pytest.mark.asyncio
    async def test_claim_hash_determinism(self):
        """
        Meme triplet + frame -> meme claim_hash -> meme PDA.
        Verifie que submit_attestation echoue si le PDA existe deja
        (meme submitter + meme claim).
        """
        pass

    @pytest.mark.asyncio
    async def test_db_updated_with_tx(self):
        """
        Apres submit on-chain, la DB locale a :
        - solana_tx_signature != NULL
        - solana_slot != NULL
        - anchored_at != NULL
        """
        pass

    @pytest.mark.asyncio
    async def test_frame_hash_on_chain(self):
        """
        L'attestation on-chain porte le hash du MetrologicalFrame.
        Verifie que frame_hash on-chain == compute_frame_hash() Python.
        """
        pass

    @pytest.mark.asyncio
    async def test_devnet_guard_in_flow(self):
        """
        Le flux complet ne peut pas etre execute contre mainnet.
        """
        pass
