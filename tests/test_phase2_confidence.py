"""Tests Phase 2.1 — Niveaux de confiance (Méthode scientifique)."""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


import pytest

from services.esmm.attestation import (
    derive_confidence_tier,
    crystallize,
    Signature5D,
    ModelVote,
    CONFIDENCE_TIERS,
    LEGACY_TIER_MAP,
)


class TestDeriveConfidenceTier:
    """Tests de la fonction de classification."""

    def test_sandbox_low_consensus(self):
        assert derive_confidence_tier(0.2, models_consulted=3) == "sandbox"

    def test_sandbox_single_model(self):
        """Même un consensus parfait avec 1 seul modèle = sandbox."""
        assert derive_confidence_tier(0.99, models_consulted=1) == "sandbox"

    def test_proposition_basic(self):
        assert derive_confidence_tier(0.5, models_consulted=2) == "proposition"

    def test_proposition_not_enough_models(self):
        """Consensus OK mais 1 seul modèle → sandbox, pas proposition."""
        assert derive_confidence_tier(0.6, models_consulted=1) == "sandbox"

    def test_validated_basic(self):
        assert derive_confidence_tier(
            0.75, models_consulted=3, architecture_families=2
        ) == "validated"

    def test_validated_needs_3_models(self):
        """Consensus et diversité OK mais seulement 2 modèles → proposition."""
        assert derive_confidence_tier(
            0.75, models_consulted=2, architecture_families=2
        ) == "proposition"

    def test_validated_needs_architecture_diversity(self):
        """3 modèles mais tous de la même famille → proposition."""
        assert derive_confidence_tier(
            0.75, models_consulted=3, architecture_families=1
        ) == "proposition"

    def test_verified_with_source_anchor(self):
        assert derive_confidence_tier(
            0.90, models_consulted=3, architecture_families=2,
            source_anchor="abc123"
        ) == "verified"

    def test_verified_with_revalidation(self):
        """3 validations successives sans source externe = verified."""
        assert derive_confidence_tier(
            0.90, models_consulted=3, architecture_families=2,
            validation_count=3
        ) == "verified"

    def test_verified_needs_validated_conditions(self):
        """Score 0.9 mais seulement 2 modèles → proposition (pas validated, pas verified)."""
        assert derive_confidence_tier(
            0.90, models_consulted=2, architecture_families=2
        ) == "proposition"

    def test_verified_needs_source_or_revalidation(self):
        """0.9, 3 modèles, 2 familles, mais pas de source ni revalidation → validated."""
        assert derive_confidence_tier(
            0.90, models_consulted=3, architecture_families=2,
            source_anchor=None, validation_count=1
        ) == "validated"

    def test_boundary_040(self):
        assert derive_confidence_tier(0.4, models_consulted=2) == "proposition"
        assert derive_confidence_tier(0.39, models_consulted=2) == "sandbox"

    def test_boundary_070(self):
        assert derive_confidence_tier(0.7, models_consulted=3, architecture_families=2) == "validated"
        assert derive_confidence_tier(0.69, models_consulted=3, architecture_families=2) == "proposition"

    def test_boundary_085(self):
        assert derive_confidence_tier(
            0.85, models_consulted=3, architecture_families=2, source_anchor="x"
        ) == "verified"
        assert derive_confidence_tier(
            0.84, models_consulted=3, architecture_families=2, source_anchor="x"
        ) == "validated"


class TestLegacyCompatibility:
    """Vérifie la backward compat avec les anciens tiers."""

    def test_legacy_mapping(self):
        assert LEGACY_TIER_MAP["low"] == "sandbox"
        assert LEGACY_TIER_MAP["medium"] == "proposition"
        assert LEGACY_TIER_MAP["high"] == "validated"
        assert LEGACY_TIER_MAP["verified"] == "verified"

    def test_tiers_tuple(self):
        assert CONFIDENCE_TIERS == ("sandbox", "proposition", "validated", "verified")


class TestCrystallizeWithNewTiers:
    """Vérifie que crystallize() utilise les nouveaux tiers."""

    def _votes(self, n: int, agreed: bool = True) -> list:
        return [
            ModelVote(
                model_id=f"test::model_{i}",
                provider_id="test",
                agreed=agreed,
                confidence=0.8,
            )
            for i in range(n)
        ]

    def _sig(self) -> Signature5D:
        return Signature5D(
            agreement=0.8, semantic_consistency=0.7,
            centrality=0.5, stability=0.8, relation_diversity=0.6,
        )

    def test_crystallize_sandbox(self):
        att = crystallize(
            subject="test", predicate="is", object_="low",
            consensus_score=0.2, model_votes=self._votes(1),
            signature_5d=self._sig(), epistemic_type="foundational",
        )
        assert att.confidence_tier == "sandbox"

    def test_crystallize_proposition(self):
        att = crystallize(
            subject="test", predicate="is", object_="medium",
            consensus_score=0.5, model_votes=self._votes(2),
            signature_5d=self._sig(), epistemic_type="foundational",
        )
        assert att.confidence_tier == "proposition"

    def test_crystallize_validated(self):
        att = crystallize(
            subject="test", predicate="is", object_="high",
            consensus_score=0.75, model_votes=self._votes(3),
            signature_5d=self._sig(), epistemic_type="foundational",
            architecture_families=2,
        )
        assert att.confidence_tier == "validated"

    def test_crystallize_verified_with_anchor(self):
        att = crystallize(
            subject="test", predicate="is", object_="verified",
            consensus_score=0.90, model_votes=self._votes(3),
            signature_5d=self._sig(), epistemic_type="foundational",
            architecture_families=2, source_anchor="abcdef1234567890" * 4,
        )
        assert att.confidence_tier == "verified"


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
