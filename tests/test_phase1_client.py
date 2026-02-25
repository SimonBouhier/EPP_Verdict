"""Tests Phase 1.3 -- Client Solana."""

import asyncio
import pytest
import os

from services.solana.config import SolanaCluster, SolanaConfig
from services.solana.client import (
    EppSolanaClient,
    derive_attestation_pda,
)
from services.esmm.attestation import (
    EpistemicAttestation, Signature5D, ModelVote, crystallize,
)

# Skip localnet tests if not running
LOCALNET_AVAILABLE = os.environ.get("EPP_TEST_LOCALNET", "0") == "1"


class TestClientUnit:
    """Tests unitaires (pas de reseau)."""

    def test_client_refuses_mainnet(self):
        """Le client refuse categoriquement le mainnet."""
        # Il n'y a pas de MAINNET dans l'enum, mais testons un contournement
        # En verifiant que l'enum n'a pas de mainnet
        cluster_names = [c.name for c in SolanaCluster]
        assert "MAINNET" not in cluster_names
        assert "MAINNET_BETA" not in cluster_names

    def test_client_accepts_devnet(self):
        """Le client accepte devnet."""
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        client = EppSolanaClient(config)
        assert client.config.cluster == SolanaCluster.DEVNET

    def test_client_accepts_localnet(self):
        """Le client accepte localnet."""
        config = SolanaConfig(cluster=SolanaCluster.LOCALNET)
        client = EppSolanaClient(config)
        assert client.config.is_localnet

    def test_derive_pda_deterministic(self):
        """Meme inputs -> meme PDA."""
        program_id = "EPPxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        submitter = "7C4jsPZpht2v3c8P2Y2uF5d6UJY9YN5X5C6E5H5G5K5"
        claim_hash = b'\x00' * 32

        pda1, bump1 = derive_attestation_pda(program_id, submitter, claim_hash)
        pda2, bump2 = derive_attestation_pda(program_id, submitter, claim_hash)

        assert pda1 == pda2
        assert bump1 == bump2

    def test_derive_pda_changes_with_claim_hash(self):
        """Different claim_hash -> different PDA."""
        program_id = "EPPxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        submitter = "7C4jsPZpht2v3c8P2Y2uF5d6UJY9YN5X5C6E5H5G5K5"

        pda1, _ = derive_attestation_pda(program_id, submitter, b'\x00' * 32)
        pda2, _ = derive_attestation_pda(program_id, submitter, b'\xff' * 32)

        assert pda1 != pda2

    def test_derive_pda_changes_with_submitter(self):
        """Different submitter -> different PDA (meme claim)."""
        program_id = "EPPxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        claim_hash = b'\x00' * 32

        pda1, _ = derive_attestation_pda(
            program_id, "7C4jsPZpht2v3c8P2Y2uF5d6UJY9YN5X5C6E5H5G5K5", claim_hash
        )
        pda2, _ = derive_attestation_pda(
            program_id, "8D5ksPZpht2v3c8P2Y2uF5d6UJY9YN5X5C6E5H5G5L6", claim_hash
        )

        assert pda1 != pda2

    def test_client_not_ready_without_keypair(self):
        """Client non pret sans keypair."""
        config = SolanaConfig(cluster=SolanaCluster.DEVNET, keypair_path=None)
        client = EppSolanaClient(config)
        # Without Solana libs or keypair, not ready
        assert not client.is_ready

    def test_explorer_url_devnet(self):
        """URL Explorer correcte pour devnet."""
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        client = EppSolanaClient(config)
        url = client.get_explorer_url("abc123")
        assert "explorer.solana.com/tx/abc123" in url
        assert "cluster=devnet" in url

    def test_explorer_url_localnet(self):
        """URL Explorer correcte pour localnet."""
        config = SolanaConfig(cluster=SolanaCluster.LOCALNET)
        client = EppSolanaClient(config)
        url = client.get_explorer_url("abc123")
        assert "explorer.solana.com/tx/abc123" in url
        assert "cluster=custom" in url


class TestClientMock:
    """Tests avec le mode mock (sans Solana libs)."""

    def _make_attestation(self) -> EpistemicAttestation:
        """Helper : cree une attestation de test."""
        return crystallize(
            subject="solana",
            predicate="has_tps",
            object_="exceeds 3000",
            consensus_score=0.85,
            model_votes=[
                ModelVote(model_id="test::model_a", provider_id="test", agreed=True, confidence=0.9),
                ModelVote(model_id="test::model_b", provider_id="test", agreed=True, confidence=0.8),
            ],
            signature_5d=Signature5D(
                agreement=0.85,
                semantic_consistency=0.72,
                centrality=0.45,
                stability=0.90,
                relation_diversity=0.60,
            ),
            epistemic_type="foundational",
        )

    async def test_mock_submit_returns_signature(self):
        """En mode mock, submit retourne une signature."""
        config = SolanaConfig(
            cluster=SolanaCluster.DEVNET,
            program_id="EPPxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        )
        client = EppSolanaClient(config)
        await client.connect()

        att = self._make_attestation()

        # Phase 4.6: mock mode returns a fake signature instead of raising
        sig = await client.submit_attestation(att)
        assert isinstance(sig, str) and len(sig) > 0

        await client.disconnect()

    async def test_mock_query_returns_empty(self):
        """En mode mock, query retourne une liste vide."""
        config = SolanaConfig(
            cluster=SolanaCluster.DEVNET,
            program_id="EPPxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        )
        client = EppSolanaClient(config)
        await client.connect()

        results = await client.query_attestations_by_claim("a" * 64)
        assert results == []

        await client.disconnect()


@pytest.mark.skipif(not LOCALNET_AVAILABLE, reason="Localnet not running")
class TestClientLocalnet:
    """Tests contre solana-test-validator."""

    @pytest.mark.asyncio
    async def test_submit_and_read_back(self):
        """Submit une attestation sur localnet et la relit."""
        # Ce test sera implemente une fois le client fonctionnel
        # avec anchorpy et solana-test-validator
        pass

    @pytest.mark.asyncio
    async def test_query_by_claim_hash(self):
        """Query par claim_hash retourne l'attestation soumise."""
        pass

    @pytest.mark.asyncio
    async def test_two_submitters_same_claim(self):
        """Deux submitters differents peuvent attester le meme claim."""
        pass
