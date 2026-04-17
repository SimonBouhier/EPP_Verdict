"""Tests Phase 1.0 -- Referentiels metrologiques."""

import pytest
import json
import hashlib

from services.solana.metrological_frame import (
    MetrologicalFrame,
    FrameGovernance,
    create_blockchain_tps_frame,
    create_general_knowledge_frame,
)
from services.solana.config import (
    SolanaCluster,
    SolanaConfig,
    validate_cluster,
)


class TestMetrologicalFrame:
    """Tests MetrologicalFrame."""

    def test_create_blockchain_tps_frame(self):
        """Le frame blockchain_tps_v1.0 se cree correctement."""
        frame = create_blockchain_tps_frame()
        assert frame.frame_id == "blockchain_tps_v1.0"
        assert frame.version == "1.0"
        assert frame.domain == "blockchain_metrics"
        assert frame.metric == "transactions_per_second"
        assert frame.parameters["include_votes"] is False
        assert frame.required_sources == 3

    def test_frame_hash_deterministic(self):
        """Meme frame -> meme hash, toujours."""
        frame1 = create_blockchain_tps_frame()
        frame2 = create_blockchain_tps_frame()
        assert frame1.compute_frame_hash() == frame2.compute_frame_hash()

    def test_frame_hash_changes_with_content(self):
        """Frame different -> hash different."""
        frame1 = create_blockchain_tps_frame()
        frame2 = create_general_knowledge_frame()
        assert frame1.compute_frame_hash() != frame2.compute_frame_hash()

    def test_frame_hash_ignores_created_at(self):
        """Le created_at ne change pas le hash (c'est du metadata)."""
        frame1 = create_blockchain_tps_frame()
        frame1.created_at = 1000.0
        frame2 = create_blockchain_tps_frame()
        frame2.created_at = 2000.0
        assert frame1.compute_frame_hash() == frame2.compute_frame_hash()

    def test_frame_hash_is_sha256(self):
        """Le hash est bien un SHA-256 hex (64 chars)."""
        frame = create_blockchain_tps_frame()
        h = frame.compute_frame_hash()
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_frame_id_validation_rejects_uppercase(self):
        """Les IDs en majuscules sont refuses."""
        with pytest.raises(ValueError, match="frame_id must be lowercase"):
            MetrologicalFrame(
                frame_id="Blockchain_TPS_v1",
                version="1.0",
                domain="test",
                metric="test",
                description="test",
            )

    def test_frame_id_validation_rejects_spaces(self):
        """Les espaces dans l'ID sont refuses."""
        with pytest.raises(ValueError):
            MetrologicalFrame(
                frame_id="blockchain tps",
                version="1.0",
                domain="test",
                metric="test",
                description="test",
            )

    def test_canonical_json_is_valid(self):
        """Le JSON canonique est parseable."""
        frame = create_blockchain_tps_frame()
        j = frame.to_canonical_json()
        parsed = json.loads(j)
        assert parsed["frame_id"] == "blockchain_tps_v1.0"

    def test_governance_defaults(self):
        """La gouvernance a des valeurs par defaut correctes."""
        frame = create_blockchain_tps_frame()
        assert frame.governance.current_authority == "founding_team"
        assert frame.governance.target_authority == "dao_vote"

    def test_frame_hash_32_bytes(self):
        """Le hash peut etre converti en 32 bytes (pour le PDA on-chain)."""
        frame = create_blockchain_tps_frame()
        h = frame.compute_frame_hash()
        raw = bytes.fromhex(h)
        assert len(raw) == 32


class TestSolanaConfig:
    """Tests configuration Solana."""

    def test_devnet_allowed(self):
        """Devnet est autorise."""
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        assert config.rpc_url == "https://api.devnet.solana.com"

    def test_localnet_allowed(self):
        """Localnet est autorise."""
        config = SolanaConfig(cluster=SolanaCluster.LOCALNET)
        assert config.is_localnet is True

    def test_no_mainnet_enum(self):
        """MAINNET n'existe pas dans l'enum (par design)."""
        cluster_names = [c.name for c in SolanaCluster]
        assert "MAINNET" not in cluster_names
        assert "MAINNET_BETA" not in cluster_names

    def test_validate_cluster_devnet(self):
        """validate_cluster accepte devnet."""
        validate_cluster(SolanaCluster.DEVNET)  # Ne doit pas lever

    def test_config_commitment_default(self):
        """Le commitment par defaut est 'confirmed'."""
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        assert config.commitment == "confirmed"
