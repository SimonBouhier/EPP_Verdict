"""
Phase 1.2 — Tests de désérialisation on-chain.

Vérifie l'alignement byte-par-byte entre state.rs et client.py.
Aucune connexion Solana requise — on construit les bytes manuellement.
"""

import struct

import pytest
from hypothesis import given, strategies as st

from services.solana.bridge import (
    float_to_u16,
    u16_to_float,
    string_to_fixed_bytes,
    MAX_SUBJECT_LEN,
    MAX_PREDICATE_LEN,
    MAX_OBJECT_LEN,
)
from services.solana.client import (
    EppSolanaClient,
    ACCOUNT_DISCRIMINATOR_SIZE,
)
from services.solana.config import SolanaConfig, SolanaCluster


def _build_test_blob(
    subject: str = "solana",
    predicate: str = "has_tps",
    object_field: str = "exceeds_3000",
    consensus_score: int = 8500,
    models_consulted: int = 3,
    models_agreeing: int = 2,
    sig_agreement: int = 7500,
    sig_semantic_consistency: int = 9000,
    sig_centrality: int = 7000,
    sig_stability: int = 8000,
    sig_relation_diversity: int = 6000,
    epistemic_type: int = 0,
    confidence_tier: int = 2,
    timestamp: int = 1700000000,
    last_revalidated: int = 1700000000,
    validation_count: int = 1,
    protocol_version: int = 100,
    is_challenge: bool = False,
    claim_hash: bytes = b"\xAA" * 32,
) -> bytes:
    """Build a 454-byte test blob matching state.rs layout (without discriminator)."""
    data = b""
    data += struct.pack("<B", 255)                                  # bump
    data += b"\x11" * 32                                            # submitter
    data += claim_hash                                              # claim_hash
    data += string_to_fixed_bytes(subject, MAX_SUBJECT_LEN)         # subject
    data += string_to_fixed_bytes(predicate, MAX_PREDICATE_LEN)     # predicate
    data += string_to_fixed_bytes(object_field, MAX_OBJECT_LEN)     # object
    data += struct.pack("<H", consensus_score)                      # consensus_score
    data += struct.pack("<B", models_consulted)                     # models_consulted
    data += struct.pack("<B", models_agreeing)                      # models_agreeing
    data += struct.pack("<H", sig_agreement)                        # sig_agreement
    data += struct.pack("<H", sig_semantic_consistency)             # sig_semantic_consistency
    data += struct.pack("<H", sig_centrality)                       # sig_centrality
    data += struct.pack("<H", sig_stability)                        # sig_stability
    data += struct.pack("<H", sig_relation_diversity)               # sig_relation_diversity
    data += struct.pack("<B", epistemic_type)                       # epistemic_type
    data += struct.pack("<B", confidence_tier)                      # confidence_tier
    data += b"\x33" * 32                                            # frame_hash
    data += b"\x44" * 32                                            # source_anchor
    data += struct.pack("<q", timestamp)                            # timestamp
    data += struct.pack("<q", last_revalidated)                     # last_revalidated
    data += struct.pack("<H", validation_count)                     # validation_count
    data += struct.pack("<H", protocol_version)                     # protocol_version
    data += struct.pack("<B", 1 if is_challenge else 0)             # is_challenge
    data += b"\x00" * 32                                            # challenged_attestation
    assert len(data) == 454, f"Blob size mismatch: {len(data)} != 454"
    return data


def _make_client() -> EppSolanaClient:
    config = SolanaConfig(cluster=SolanaCluster.DEVNET)
    return EppSolanaClient(config)


class TestSolanaDeserialize:
    """Phase 1.2 — Tests de désérialisation on-chain."""

    def test_roundtrip_serialize_deserialize(self):
        """Blob 454 bytes → désérialiser → vérifier valeurs exactes."""
        client = _make_client()
        blob = _build_test_blob()
        result = client._deserialize_attestation_account(blob)

        assert result["subject"] == "solana"
        assert result["predicate"] == "has_tps"
        assert result["object"] == "exceeds_3000"
        assert result["consensus_score"] == pytest.approx(0.85, abs=0.0001)
        assert result["signature_5d"]["agreement"] == pytest.approx(0.75, abs=0.0001)
        assert result["signature_5d"]["semantic_consistency"] == pytest.approx(0.90, abs=0.0001)
        assert result["signature_5d"]["centrality"] == pytest.approx(0.70, abs=0.0001)
        assert result["signature_5d"]["stability"] == pytest.approx(0.80, abs=0.0001)
        assert result["signature_5d"]["relation_diversity"] == pytest.approx(0.60, abs=0.0001)
        assert result["timestamp"] == 1700000000
        assert result["last_revalidated"] == 1700000000
        assert result["validation_count"] == 1
        assert result["protocol_version"] == 100
        assert result["is_challenge"] is False
        assert result["epistemic_type"] == "foundational"
        assert result["confidence_tier"] == "validated"

    def test_deserialize_invalid_size(self):
        """Buffer trop court ou trop long → ValueError."""
        client = _make_client()

        with pytest.raises((ValueError, struct.error)):
            client._deserialize_attestation_account(b"\x00" * 100)

        with pytest.raises((ValueError, struct.error)):
            client._deserialize_attestation_account(b"\x00" * 500)

    def test_claim_hash_offset_matches_layout(self):
        """CLAIM_HASH_OFFSET (41) est cohérent avec le layout réel."""
        client = _make_client()
        known_claim_hash = b"\xAA" * 32
        blob = _build_test_blob(claim_hash=known_claim_hash)

        result = client._deserialize_attestation_account(blob)
        assert result["claim_hash"] == "aa" * 32

        # Arithmétique : discriminator(8) + bump(1) + submitter(32) = 41
        assert ACCOUNT_DISCRIMINATOR_SIZE + 1 + 32 == 41

    def test_subject_offset_matches_layout(self):
        """SUBJECT_OFFSET (73) est cohérent avec le layout réel."""
        client = _make_client()
        blob = _build_test_blob(subject="test_subject")

        result = client._deserialize_attestation_account(blob)
        assert result["subject"] == "test_subject"

        # Arithmétique : discriminator(8) + bump(1) + submitter(32) + claim_hash(32) = 73
        assert ACCOUNT_DISCRIMINATOR_SIZE + 1 + 32 + 32 == 73

    @given(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    def test_roundtrip_float_through_bytes(self, f):
        """Roundtrip float → u16 → LE bytes → u16 → float sans perte (ADR-001)."""
        u16_val = float_to_u16(f)
        packed = struct.pack("<H", u16_val)
        unpacked = struct.unpack("<H", packed)[0]
        restored = u16_to_float(unpacked)
        assert abs(restored - f) <= 0.0001
