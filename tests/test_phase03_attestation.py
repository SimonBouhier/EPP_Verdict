# tests/test_phase03_attestation.py
"""
Phase 0.3.2 Tests — EpistemicAttestation Model

Tests for:
- compute_claim_hash determinism
- Signature5D validation
- derive_confidence_tier thresholds
- crystallize function
- Portable JSON serialization
- Pydantic validation
"""

import pytest
import json
import hashlib
import time
import sys
from pathlib import Path
# Add project root to path to enable direct import
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import directly from the attestation module (avoid __init__.py chain)
from services.esmm.attestation import (
    EpistemicAttestation,
    Signature5D,
    ModelVote,
    crystallize,
    compute_claim_hash,
    derive_confidence_tier,
)


class TestComputeClaimHash:
    """Tests pour le hash déterministe."""

    def test_hash_is_deterministic(self):
        """Même triplet + frame → même hash."""
        h1 = compute_claim_hash("Solana", "has_property", "high_tps", "tps_v1")
        h2 = compute_claim_hash("Solana", "has_property", "high_tps", "tps_v1")
        assert h1 == h2

    def test_hash_is_case_insensitive(self):
        """Le hash est insensible à la casse."""
        h1 = compute_claim_hash("Solana", "HAS_PROPERTY", "high_tps")
        h2 = compute_claim_hash("solana", "has_property", "HIGH_TPS")
        assert h1 == h2

    def test_hash_strips_whitespace(self):
        """Le hash ignore les espaces en début/fin."""
        h1 = compute_claim_hash("  Solana  ", "has_property", "high_tps")
        h2 = compute_claim_hash("Solana", "has_property", "high_tps")
        assert h1 == h2

    def test_hash_differs_with_frame(self):
        """Le hash change si le frame métrologique change."""
        h1 = compute_claim_hash("Solana", "has_property", "high_tps", "tps_v1")
        h2 = compute_claim_hash("Solana", "has_property", "high_tps", "tps_v2")
        assert h1 != h2

    def test_hash_differs_without_frame(self):
        """Le hash sans frame diffère de celui avec frame."""
        h1 = compute_claim_hash("Solana", "has_property", "high_tps")
        h2 = compute_claim_hash("Solana", "has_property", "high_tps", "tps_v1")
        assert h1 != h2

    def test_hash_is_sha256(self):
        """Le hash est un SHA-256 valide (64 chars hex)."""
        h = compute_claim_hash("test", "is_a", "thing")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_different_triplets(self):
        """Deux triplets différents → deux hash différents."""
        h1 = compute_claim_hash("A", "is_a", "B")
        h2 = compute_claim_hash("A", "is_a", "C")
        assert h1 != h2


class TestSignature5D:
    """Tests pour la signature épistémique."""

    def test_to_vector(self):
        """to_vector retourne une liste de 5 floats."""
        sig = Signature5D(
            agreement=0.9,
            semantic_consistency=0.8,
            centrality=0.7,
            stability=0.6,
            relation_diversity=0.5,
        )
        vec = sig.to_vector()
        assert len(vec) == 5
        assert vec == [0.9, 0.8, 0.7, 0.6, 0.5]

    def test_validation_bounds(self):
        """Les valeurs hors [0, 1] sont rejetées."""
        with pytest.raises(Exception):
            Signature5D(agreement=1.5, semantic_consistency=0.5,
                        centrality=0.5, stability=0.5, relation_diversity=0.5)
        with pytest.raises(Exception):
            Signature5D(agreement=-0.1, semantic_consistency=0.5,
                        centrality=0.5, stability=0.5, relation_diversity=0.5)


class TestDeriveConfidenceTier:
    """Tests pour la dérivation du tier de confiance."""

    def test_sandbox(self):
        assert derive_confidence_tier(0.2) == "sandbox"
        assert derive_confidence_tier(0.0) == "sandbox"
        assert derive_confidence_tier(0.39) == "sandbox"

    def test_proposition(self):
        assert derive_confidence_tier(0.4, models_consulted=2) == "proposition"
        assert derive_confidence_tier(0.5, models_consulted=2) == "proposition"
        assert derive_confidence_tier(0.69, models_consulted=2) == "proposition"

    def test_validated(self):
        assert derive_confidence_tier(0.7, models_consulted=3, architecture_families=2) == "validated"
        assert derive_confidence_tier(0.8, models_consulted=3, architecture_families=2) == "validated"
        assert derive_confidence_tier(0.84, models_consulted=3, architecture_families=2) == "validated"

    def test_verified(self):
        assert derive_confidence_tier(0.9, models_consulted=3, architecture_families=2, source_anchor="test") == "verified"
        assert derive_confidence_tier(1.0, models_consulted=3, architecture_families=2, validation_count=3) == "verified"


class TestCrystallize:
    """Tests pour la fonction crystallize."""

    def _make_votes(self, n_agree: int, n_total: int) -> list:
        votes = []
        for i in range(n_total):
            votes.append(ModelVote(
                model_id=f"model_{i}",
                provider_id="mock",
                agreed=(i < n_agree),
                confidence=0.8 if i < n_agree else 0.3,
            ))
        return votes

    def _make_sig(self) -> Signature5D:
        return Signature5D(
            agreement=0.8,
            semantic_consistency=0.75,
            centrality=0.6,
            stability=0.7,
            relation_diversity=0.5,
        )

    def test_crystallize_produces_attestation(self):
        """crystallize retourne une EpistemicAttestation valide."""
        att = crystallize(
            subject="Solana",
            predicate="has_property",
            object_="high_tps",
            consensus_score=0.85,
            model_votes=self._make_votes(3, 4),
            signature_5d=self._make_sig(),
            epistemic_type="foundational",
            architecture_families=2,
        )
        assert isinstance(att, EpistemicAttestation)
        assert att.claim_hash is not None
        assert len(att.claim_hash) == 64
        assert att.subject == "Solana"
        assert att.models_consulted == 4
        assert att.models_agreeing == 3
        assert att.confidence_tier == "validated"

    def test_crystallize_with_frame(self):
        """crystallize avec frame produit un hash différent de sans frame."""
        att1 = crystallize(
            subject="Solana", predicate="is_a", object_="blockchain",
            consensus_score=0.9, model_votes=self._make_votes(3, 3),
            signature_5d=self._make_sig(), epistemic_type="foundational",
        )
        att2 = crystallize(
            subject="Solana", predicate="is_a", object_="blockchain",
            consensus_score=0.9, model_votes=self._make_votes(3, 3),
            signature_5d=self._make_sig(), epistemic_type="foundational",
            metrological_frame="blockchain_v1",
        )
        assert att1.claim_hash != att2.claim_hash

    def test_crystallize_revalidation(self):
        """crystallize en mode revalidation porte le previous_hash."""
        original = crystallize(
            subject="A", predicate="is_a", object_="B",
            consensus_score=0.8, model_votes=self._make_votes(2, 3),
            signature_5d=self._make_sig(), epistemic_type="bridge",
        )
        revalidated = crystallize(
            subject="A", predicate="is_a", object_="B",
            consensus_score=0.85, model_votes=self._make_votes(3, 3),
            signature_5d=self._make_sig(), epistemic_type="bridge",
            previous_hash=original.claim_hash,
            validation_count=2,
        )
        assert revalidated.previous_hash == original.claim_hash
        assert revalidated.validation_count == 2
        # Même triplet, même hash
        assert revalidated.claim_hash == original.claim_hash


class TestPortableJSON:
    """Tests pour la sérialisation déterministe."""

    def _make_attestation(self) -> EpistemicAttestation:
        return crystallize(
            subject="Solana",
            predicate="has_property",
            object_="high_tps",
            consensus_score=0.85,
            model_votes=[
                ModelVote(model_id="m1", provider_id="p1", agreed=True, confidence=0.9),
                ModelVote(model_id="m2", provider_id="p2", agreed=True, confidence=0.8),
            ],
            signature_5d=Signature5D(
                agreement=0.9, semantic_consistency=0.8,
                centrality=0.7, stability=0.6, relation_diversity=0.5
            ),
            epistemic_type="foundational",
        )

    def test_portable_json_is_valid(self):
        """to_portable_json produit du JSON parseable."""
        att = self._make_attestation()
        j = att.to_portable_json()
        parsed = json.loads(j)
        assert parsed["subject"] == "Solana"
        assert parsed["claim_hash"] == att.claim_hash

    def test_portable_json_is_deterministic(self):
        """Deux appels to_portable_json sur le même objet → même string."""
        att = self._make_attestation()
        j1 = att.to_portable_json()
        j2 = att.to_portable_json()
        assert j1 == j2

    def test_compact_dict_excludes_votes(self):
        """to_compact_dict ne contient pas le détail des votes."""
        att = self._make_attestation()
        compact = att.to_compact_dict()
        assert "model_votes" not in compact
        assert "sig_5d" in compact
        assert len(compact["sig_5d"]) == 5

    def test_portable_json_sorted_keys(self):
        """Le JSON a ses clés triées."""
        att = self._make_attestation()
        j = att.to_portable_json()
        parsed = json.loads(j)
        keys = list(parsed.keys())
        assert keys == sorted(keys)


class TestAttestationValidation:
    """Tests pour la validation Pydantic."""

    def test_invalid_epistemic_type(self):
        """Un epistemic_type invalide est rejeté."""
        with pytest.raises(Exception):
            crystallize(
                subject="A", predicate="is_a", object_="B",
                consensus_score=0.5,
                model_votes=[ModelVote(model_id="m", provider_id="p", agreed=True, confidence=0.5)],
                signature_5d=Signature5D(agreement=0.5, semantic_consistency=0.5,
                                         centrality=0.5, stability=0.5, relation_diversity=0.5),
                epistemic_type="INVALID_TYPE",
            )

    def test_invalid_confidence_tier(self):
        """Un confidence_tier invalide est rejeté."""
        with pytest.raises(Exception):
            EpistemicAttestation(
                claim_hash="a" * 64, subject="A", predicate="is", object="B",
                consensus_score=0.5, models_consulted=1, models_agreeing=1,
                model_votes=[], signature_5d=Signature5D(
                    agreement=0.5, semantic_consistency=0.5,
                    centrality=0.5, stability=0.5, relation_diversity=0.5),
                epistemic_type="foundational",
                confidence_tier="INVALID",
                timestamp=time.time(),
            )
