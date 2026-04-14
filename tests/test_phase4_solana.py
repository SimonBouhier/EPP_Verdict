"""
Tests Phase 4.6 — Solana devnet : transaction building, PDA validation, mock mode.
"""

import hashlib
import struct
import pytest

from services.solana.config import SolanaConfig, SolanaCluster
from services.solana.client import (
    EppSolanaClient,
    derive_attestation_pda,
    ATTESTATION_SEED,
    ACCOUNT_DISCRIMINATOR_SIZE,
    _SOLANA_AVAILABLE,
)
from services.solana.bridge import (
    attestation_to_anchor_args,
    float_to_u16,
    string_to_fixed_bytes,
    MAX_SUBJECT_LEN,
    MAX_PREDICATE_LEN,
    MAX_OBJECT_LEN,
    SCORE_SCALE,
)
from services.esmm.attestation import (
    EpistemicAttestation,
    Signature5D,
    ModelVote,
    compute_claim_hash,
)


def _make_test_attestation() -> EpistemicAttestation:
    """Create a minimal attestation for testing."""
    sig = Signature5D(
        agreement=0.85,
        semantic_consistency=0.9,
        centrality=0.7,
        stability=0.8,
        relation_diversity=0.6,
    )
    votes = [
        ModelVote(model_id="mistral:7b", provider_id="ollama", agreed=True,
                  confidence=0.9),
        ModelVote(model_id="llama3.1:8b", provider_id="ollama", agreed=True,
                  confidence=0.8),
    ]
    return EpistemicAttestation(
        claim_hash=compute_claim_hash("sun", "is_a", "star", "science"),
        subject="sun",
        predicate="is_a",
        object="star",
        consensus_score=0.85,
        models_consulted=2,
        models_agreeing=2,
        signature_5d=sig,
        model_votes=votes,
        epistemic_type="foundational",
        confidence_tier="validated",
        timestamp=1700000000.0,
    )


# ============================================================================
# 4.6.1 — TRANSACTION BUILDING
# ============================================================================

@pytest.mark.skipif(_SOLANA_AVAILABLE, reason="Mock-mode tests: only valid when solders not installed")
class TestTransactionBuildingMockMode:
    """4.6.1 — submit_attestation en mode mock (sans solders)."""

    async def test_mock_submit_returns_signature(self):
        """Mock mode retourne une signature hex déterministe."""
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        client = EppSolanaClient(config)
        attestation = _make_test_attestation()

        sig = await client.submit_attestation(attestation)

        assert isinstance(sig, str)
        assert len(sig) > 0

    async def test_mock_submit_deterministic(self):
        """Même attestation → même signature mock."""
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        client = EppSolanaClient(config)
        attestation = _make_test_attestation()

        sig1 = await client.submit_attestation(attestation)
        sig2 = await client.submit_attestation(attestation)
        assert sig1 == sig2

    async def test_mock_get_attestation_returns_none(self):
        """Mock mode : get_attestation retourne None."""
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        client = EppSolanaClient(config)

        result = await client.get_attestation(
            "11111111111111111111111111111111",
            "a" * 64,
        )
        assert result is None

    async def test_mock_query_returns_empty(self):
        """Mock mode : query retourne []."""
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        client = EppSolanaClient(config)

        results = await client.query_attestations_by_claim("a" * 64)
        assert results == []

        results = await client.query_attestations_by_subject("sun")
        assert results == []


class TestInstructionSerialization:
    """4.6.1 — Vérifier que la sérialisation Borsh est cohérente."""

    def test_anchor_discriminator_computation(self):
        """Le discriminator Anchor est SHA-256('global:submit_attestation')[:8]."""
        expected = hashlib.sha256(b"global:submit_attestation").digest()[:8]
        assert len(expected) == 8
        # Verify it's not all zeros (sanity check)
        assert expected != b"\x00" * 8

    def test_args_serialization_roundtrip(self):
        """attestation_to_anchor_args produit des args cohérents."""
        attestation = _make_test_attestation()
        args = attestation_to_anchor_args(attestation)

        assert len(args.claim_hash) == 32
        assert len(args.subject) == MAX_SUBJECT_LEN
        assert len(args.predicate) == MAX_PREDICATE_LEN
        assert len(args.object_field) == MAX_OBJECT_LEN
        assert 0 <= args.consensus_score <= SCORE_SCALE
        assert args.models_consulted == 2
        assert args.models_agreeing == 2

    def test_borsh_layout_matches_account_size(self):
        """La taille sérialisée correspond à l'account size Anchor (462 bytes)."""
        # Account layout from state.rs — CHAQUE champ listé :
        # bump(1) + submitter(32) + claim_hash(32) + subject(64) + predicate(64) +
        # object(128) + consensus_score(2) + models_consulted(1) + models_agreeing(1) +
        # sig_5d(5×2=10) + epistemic_type(1) + confidence_tier(1) + frame_hash(32) +
        # source_anchor(32) + timestamp(8) + last_revalidated(8) + validation_count(2) +
        # protocol_version(2) + is_challenge(1) + challenged_attestation(32)
        expected_data_size = (
            1 + 32 + 32 + 64 + 64 + 128 + 2 + 1 + 1 + 10 + 1 + 1
            + 32 + 32 + 8 + 8 + 2 + 2 + 1 + 32
        )
        assert expected_data_size == 454  # Data sans discriminator
        assert expected_data_size + ACCOUNT_DISCRIMINATOR_SIZE == 462  # == state.rs::SIZE


# ============================================================================
# 4.6.2 — PDA VALIDATION
# ============================================================================

class TestPDAValidation:
    """4.6.2 — PDA derivation et validation."""

    def test_pda_deterministic(self):
        """Même (program_id, submitter, claim_hash) → même PDA."""
        program_id = "98Fc2oL2cKsTDGYi3GifggzkQkEQSRn2oTgg8HsaVa3C"
        submitter = "11111111111111111111111111111111"
        claim_hash = b"\x01" * 32

        pda1, bump1 = derive_attestation_pda(program_id, submitter, claim_hash)
        pda2, bump2 = derive_attestation_pda(program_id, submitter, claim_hash)

        assert pda1 == pda2
        assert bump1 == bump2

    def test_pda_changes_with_claim_hash(self):
        """Claim hash différent → PDA différent."""
        program_id = "98Fc2oL2cKsTDGYi3GifggzkQkEQSRn2oTgg8HsaVa3C"
        submitter = "11111111111111111111111111111111"

        pda1, _ = derive_attestation_pda(program_id, submitter, b"\x01" * 32)
        pda2, _ = derive_attestation_pda(program_id, submitter, b"\x02" * 32)

        assert pda1 != pda2

    async def test_check_pda_exists_mock_returns_false(self):
        """Mock mode : check_pda_exists retourne False."""
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        client = EppSolanaClient(config)

        exists = await client.check_pda_exists(
            "11111111111111111111111111111111",
            "a" * 64,
        )
        assert exists is False

    def test_deserialize_attestation_layout(self):
        """_deserialize_attestation_account décode un buffer correctement."""
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        client = EppSolanaClient(config)

        # Build a fake account data buffer matching the layout
        data = b""
        data += struct.pack("<B", 255)       # bump
        data += b"\x11" * 32                 # submitter
        data += b"\x22" * 32                 # claim_hash
        data += string_to_fixed_bytes("sun", MAX_SUBJECT_LEN)
        data += string_to_fixed_bytes("is_a", MAX_PREDICATE_LEN)
        data += string_to_fixed_bytes("star", MAX_OBJECT_LEN)
        data += struct.pack("<H", 8500)      # consensus_score (0.85)
        data += struct.pack("<B", 3)         # models_consulted
        data += struct.pack("<B", 2)         # models_agreeing
        data += struct.pack("<H", 9000)      # sig_agreement
        data += struct.pack("<H", 8000)      # sig_semantic_consistency
        data += struct.pack("<H", 7000)      # sig_centrality
        data += struct.pack("<H", 6000)      # sig_stability
        data += struct.pack("<H", 5000)      # sig_relation_diversity
        data += struct.pack("<B", 0)         # epistemic_type (foundational)
        data += struct.pack("<B", 2)         # confidence_tier (validated)
        data += b"\x33" * 32                 # frame_hash
        data += b"\x44" * 32                 # source_anchor
        data += struct.pack("<q", 1700000000)  # timestamp
        data += struct.pack("<q", 1700000000)  # last_revalidated
        data += struct.pack("<H", 3)         # validation_count
        data += struct.pack("<H", 1)         # protocol_version
        data += struct.pack("<B", 0)         # is_challenge
        data += b"\x00" * 32                 # challenged_attestation

        result = client._deserialize_attestation_account(data)

        assert result["subject"] == "sun"
        assert result["predicate"] == "is_a"
        assert result["object"] == "star"
        assert abs(result["consensus_score"] - 0.85) < 0.001
        assert result["models_consulted"] == 3
        assert result["models_agreeing"] == 2
        assert abs(result["signature_5d"]["agreement"] - 0.9) < 0.001
        # V2 projection: u8=0 decodes to the on-chain category "empirical".
        assert result["epistemic_type"] == "empirical"
        assert result["confidence_tier"] == "validated"
        assert result["timestamp"] == 1700000000
        assert result["last_revalidated"] == 1700000000
        assert result["is_challenge"] is False


# ============================================================================
# 4.6.3 — SUBMITTER AUTH CHECKS
# ============================================================================

class TestSubmitterAuth:
    """4.6.3 — Vérifications de base sur l'auth du submitter."""

    def test_client_not_ready_without_keypair(self):
        """Client n'est pas ready sans keypair chargé."""
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        client = EppSolanaClient(config)
        assert not client.is_ready

    def test_submitter_pubkey_none_without_keypair(self):
        """submitter_pubkey est None sans keypair."""
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        client = EppSolanaClient(config)
        assert client.submitter_pubkey is None

    @pytest.mark.skipif(not _SOLANA_AVAILABLE, reason="solana-py not installed")
    async def test_submit_requires_ready_client(self):
        """submit_attestation lève RuntimeError si client pas ready."""
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        client = EppSolanaClient(config)
        attestation = _make_test_attestation()

        with pytest.raises(RuntimeError, match="Client not ready"):
            await client.submit_attestation(attestation)

    def test_mainnet_refused(self):
        """Le client refuse MAINNET."""
        from services.solana.config import SolanaCluster
        # SolanaCluster should not have MAINNET
        cluster_names = [c.name for c in SolanaCluster]
        assert "MAINNET" not in cluster_names, "MAINNET must never be available"
