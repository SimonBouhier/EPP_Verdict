"""Tests Phase 1.2 -- Bridge de serialisation Python <-> Anchor."""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


import pytest
import time

from services.solana.bridge import (
    float_to_u16, u16_to_float,
    string_to_fixed_bytes, fixed_bytes_to_string,
    hex_to_bytes32, protocol_version_to_u16, u16_to_protocol_version,
    attestation_to_anchor_args, anchor_data_to_attestation_summary,
    SCORE_SCALE, MAX_SUBJECT_LEN, MAX_PREDICATE_LEN, MAX_OBJECT_LEN,
    EPISTEMIC_TYPE_MAP, CONFIDENCE_TIER_MAP, CONFIDENCE_TIER_REVERSE,
)
from services.esmm.attestation import (
    EpistemicAttestation, Signature5D, ModelVote,
    crystallize, compute_claim_hash,
)


class TestFloatU16:
    """Tests conversion float <-> u16."""

    def test_zero(self):
        assert float_to_u16(0.0) == 0
        assert u16_to_float(0) == 0.0

    def test_one(self):
        assert float_to_u16(1.0) == SCORE_SCALE
        assert u16_to_float(SCORE_SCALE) == 1.0

    def test_middle(self):
        assert float_to_u16(0.5) == 5000
        assert u16_to_float(5000) == 0.5

    def test_precision(self):
        """4 decimal places preserved."""
        assert float_to_u16(0.8765) == 8765
        assert u16_to_float(8765) == 0.8765

    def test_roundtrip(self):
        """float -> u16 -> float = same (within precision)."""
        for v in [0.0, 0.1, 0.25, 0.333, 0.5, 0.75, 0.9999, 1.0]:
            assert abs(u16_to_float(float_to_u16(v)) - v) < 0.0001

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            float_to_u16(1.1)
        with pytest.raises(ValueError):
            float_to_u16(-0.1)

    def test_u16_out_of_range_raises(self):
        with pytest.raises(ValueError):
            u16_to_float(10001)


class TestStringBytes:
    """Tests conversion string <-> fixed bytes."""

    def test_basic(self):
        b = string_to_fixed_bytes("hello", 10)
        assert len(b) == 10
        assert b[:5] == b"hello"
        assert b[5:] == b'\x00' * 5

    def test_exact_length(self):
        b = string_to_fixed_bytes("abcd", 4)
        assert b == b"abcd"

    def test_truncation(self):
        b = string_to_fixed_bytes("this is too long", 8)
        assert len(b) == 8
        assert b == b"this is "

    def test_roundtrip(self):
        original = "solana"
        b = string_to_fixed_bytes(original, MAX_SUBJECT_LEN)
        recovered = fixed_bytes_to_string(b)
        assert recovered == original

    def test_unicode(self):
        """UTF-8 multi-byte characters are handled."""
        b = string_to_fixed_bytes("cafe", MAX_SUBJECT_LEN)
        recovered = fixed_bytes_to_string(b)
        assert recovered == "cafe"

    def test_empty_string(self):
        b = string_to_fixed_bytes("", 32)
        assert b == b'\x00' * 32
        assert fixed_bytes_to_string(b) == ""


class TestHexBytes:
    """Tests conversion hex <-> bytes32."""

    def test_valid_hash(self):
        h = "a" * 64  # 64 hex chars = 32 bytes
        b = hex_to_bytes32(h)
        assert len(b) == 32
        assert b == bytes.fromhex(h)

    def test_none_gives_zeros(self):
        b = hex_to_bytes32(None)
        assert b == b'\x00' * 32

    def test_empty_gives_zeros(self):
        b = hex_to_bytes32("")
        assert b == b'\x00' * 32

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError, match="Expected 32 bytes"):
            hex_to_bytes32("abcd")  # Too short


class TestProtocolVersion:
    """Tests conversion version string <-> u16."""

    def test_v0_3(self):
        assert protocol_version_to_u16("0.3") == 3

    def test_v1_0(self):
        assert protocol_version_to_u16("1.0") == 100

    def test_roundtrip(self):
        for v in ["0.1", "0.3", "1.0", "1.2", "2.0"]:
            assert u16_to_protocol_version(protocol_version_to_u16(v)) == v


class TestAttestationToAnchorArgs:
    """Test conversion complete attestation -> args Anchor."""

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
            architecture_families=2,
        )

    def test_basic_conversion(self):
        att = self._make_attestation()
        args = attestation_to_anchor_args(att)
        assert len(args.claim_hash) == 32
        assert len(args.subject) == MAX_SUBJECT_LEN
        assert len(args.predicate) == MAX_PREDICATE_LEN
        assert len(args.object_field) == MAX_OBJECT_LEN
        assert args.consensus_score == 8500
        assert args.models_consulted == 3
        assert args.models_agreeing == 2

    def test_signature_5d_encoding(self):
        att = self._make_attestation()
        args = attestation_to_anchor_args(att)
        assert args.sig_agreement == 8500
        assert args.sig_semantic_consistency == 7200
        assert args.sig_centrality == 4500
        assert args.sig_stability == 9000
        assert args.sig_relation_diversity == 6000

    def test_enum_encoding(self):
        att = self._make_attestation()
        args = attestation_to_anchor_args(att)
        assert args.epistemic_type == EPISTEMIC_TYPE_MAP["foundational"]
        assert args.confidence_tier == CONFIDENCE_TIER_MAP["validated"]  # 0.85 + 3 models + 2 families -> validated

    def test_claim_hash_matches(self):
        """Le claim_hash dans args = bytes du claim_hash Python."""
        att = self._make_attestation()
        args = attestation_to_anchor_args(att)
        assert args.claim_hash == bytes.fromhex(att.claim_hash)

    def test_challenge_defaults(self):
        att = self._make_attestation()
        args = attestation_to_anchor_args(att)
        assert args.is_challenge is False
        assert args.challenged_attestation == b'\x00' * 32

    def test_roundtrip_summary(self):
        """attestation -> anchor_args -> simulated on-chain -> summary -> verify."""
        att = self._make_attestation()
        args = attestation_to_anchor_args(att)

        # Simulate reading back from chain (as dict with same field names)
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

        assert summary["subject"] == "solana"
        assert summary["predicate"] == "has_tps"
        assert summary["object"] == "exceeds 3000"
        assert abs(summary["consensus_score"] - 0.85) < 0.001
        # V2 projection: foundational (sub-type empirical) round-trips as "empirical".
        assert summary["epistemic_type"] == "empirical"
        assert summary["confidence_tier"] == "validated"
        assert summary["signature_5d"]["agreement"] == 0.85


class TestAllTiersE2E:
    """Test roundtrip serialization for all 4 confidence tiers."""

    TIER_CONFIGS = [
        # (tier, score, n_models, n_families, source_anchor)
        ("sandbox", 0.20, 1, 1, None),
        ("proposition", 0.50, 2, 1, None),
        ("validated", 0.75, 3, 2, None),
        ("verified", 0.90, 3, 2, "a" * 64),
    ]

    def _make_attestation_for_tier(self, score, n_models, n_families, source_anchor):
        votes = [
            ModelVote(model_id=f"test::model_{i}", provider_id="test", agreed=True, confidence=score)
            for i in range(n_models)
        ]
        return crystallize(
            subject="test_subject",
            predicate="test_predicate",
            object_="test_object",
            consensus_score=score,
            model_votes=votes,
            signature_5d=Signature5D(
                agreement=score,
                semantic_consistency=0.50,
                centrality=0.50,
                stability=0.50,
                relation_diversity=0.50,
            ),
            epistemic_type="foundational",
            architecture_families=n_families,
            source_anchor=source_anchor,
        )

    @pytest.mark.parametrize("tier,score,n_models,n_families,source_anchor", [
        ("sandbox", 0.20, 1, 1, None),
        ("proposition", 0.50, 2, 1, None),
        ("validated", 0.75, 3, 2, None),
        ("verified", 0.90, 3, 2, "a" * 64),
    ])
    def test_tier_roundtrip(self, tier, score, n_models, n_families, source_anchor):
        """attestation(tier) -> anchor_args -> summary -> verify tier survives roundtrip."""
        att = self._make_attestation_for_tier(score, n_models, n_families, source_anchor)
        assert att.confidence_tier == tier, f"Expected {tier}, got {att.confidence_tier}"

        args = attestation_to_anchor_args(att)
        assert args.confidence_tier == CONFIDENCE_TIER_MAP[tier]

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
        assert summary["confidence_tier"] == tier


# ─────────────────────────────────────────────────────────────────────────
# Single-file runner — `python tests/<this_file>.py`
# Génère un rapport horodaté dans `test_results/individual/`.
# Cf. `tests/_runner.py::run_self` pour le détail.
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from tests._runner import run_self
    raise SystemExit(run_self(__file__))
