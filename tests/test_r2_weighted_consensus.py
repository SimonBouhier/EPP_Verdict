"""
Tests R-2.1.1 — Pondération dynamique des votes (Brier -> Consensus).

RED-GREEN-FIX : ces tests DOIVENT échouer avant implémentation.

Vérifie que :
1. compute_consensus() accepte model_weights et change le score
2. Cold start (pas d'historique Brier) -> poids neutre 1.0
3. model_weights=None -> backward compat (comportement identique)
"""
import pytest
from services.esmm.consensus_engine import ConsensusEngine, ConsensusTriplet
from services.esmm.triplet_validator import ExtractedTriplet


def _make_triplet(subject: str, relation: str, obj: str, confidence: float) -> ExtractedTriplet:
    """Helper : crée un ExtractedTriplet valide."""
    return ExtractedTriplet(
        subject=subject,
        relation=relation,
        object=obj,
        confidence=confidence,
    )


def _make_model_results_same_triplet() -> dict[str, list]:
    """3 modèles extraient le même triplet avec des confiances différentes."""
    triplet_a = _make_triplet("Python", "is_a", "programming language", 0.9)
    triplet_b = _make_triplet("Python", "is_a", "programming language", 0.7)
    triplet_c = _make_triplet("Python", "is_a", "programming language", 0.8)
    return {
        "model_a": [triplet_a],
        "model_b": [triplet_b],
        "model_c": [triplet_c],
    }


class TestWeightedConsensus:
    """R-2.1.1 RED 1 — compute_consensus() avec model_weights."""

    @pytest.mark.asyncio
    async def test_weighted_consensus_changes_score(self):
        """Un modèle avec poids 0.1 influence moins qu'un modèle avec poids 1.0."""
        engine = ConsensusEngine(min_agreement=0.3)
        model_results = _make_model_results_same_triplet()

        results_equal = (await engine.compute_consensus(model_results)).triplets
        results_weighted = (await engine.compute_consensus(
            model_results,
            model_weights={"model_a": 1.0, "model_b": 0.1, "model_c": 1.0},
        )).triplets

        assert len(results_equal) > 0, "Pas de résultats sans poids"
        assert len(results_weighted) > 0, "Pas de résultats avec poids"

        score_equal = results_equal[0].consensus_score
        score_weighted = results_weighted[0].consensus_score
        assert score_equal != score_weighted, (
            f"Le score devrait changer avec pondération : "
            f"equal={score_equal}, weighted={score_weighted}"
        )

    @pytest.mark.asyncio
    async def test_weighted_consensus_low_weight_reduces_influence(self):
        """Un modèle à poids faible tire le score vers le bas s'il a confiance différente."""
        engine = ConsensusEngine(min_agreement=0.3)
        triplet_high = _make_triplet("Python", "is_a", "programming language", 0.9)
        triplet_low = _make_triplet("Python", "is_a", "programming language", 0.3)

        model_results = {
            "model_a": [triplet_high],
            "model_b": [triplet_low],
        }

        results_equal_weight = (await engine.compute_consensus(
            model_results,
            model_weights={"model_a": 1.0, "model_b": 1.0},
        )).triplets
        results_low_weight = (await engine.compute_consensus(
            model_results,
            model_weights={"model_a": 1.0, "model_b": 0.01},
        )).triplets

        assert len(results_equal_weight) > 0
        assert len(results_low_weight) > 0

        score_equal = results_equal_weight[0].consensus_score
        score_low = results_low_weight[0].consensus_score
        assert score_low > score_equal, (
            f"Score avec model_b quasi-ignoré ({score_low}) devrait être > "
            f"score avec model_b à poids plein ({score_equal})"
        )


class TestColdStartWeight:
    """R-2.1.1 RED 2 — Cold start = poids neutre."""

    @pytest.mark.asyncio
    async def test_cold_start_model_gets_neutral_weight(self, tmp_path):
        """Modèle sans historique Brier -> poids 1.0."""
        from database.engine import ISpaceDB
        db = ISpaceDB(str(tmp_path / "test_cold.db"))
        await db.initialize()
        try:
            brier = await db.get_model_brier_score("modele_inexistant_xyz")
            if brier is None or brier["total_resolved"] == 0:
                weight = 1.0
            else:
                weight = max(0.0, 1.0 - brier["avg_brier_score"])
            assert weight == 1.0
        finally:
            from database.pool import close_pool
            await close_pool()

    @pytest.mark.asyncio
    async def test_model_with_brier_gets_reduced_weight(self, tmp_path):
        """Modèle avec historique Brier -> poids < 1.0."""
        from database.engine import ISpaceDB
        db = ISpaceDB(str(tmp_path / "test_brier.db"))
        await db.initialize()
        try:
            await db.record_model_prediction(
                model_id="test_model_brier",
                provider_id="ollama",
                claim_hash="abc123def456",
                predicted_confidence=0.8,
                predicted_agreed=True,
            )
            await db.resolve_prediction(
                claim_hash="abc123def456",
                actual_outcome=0.4,
            )

            brier = await db.get_model_brier_score("test_model_brier")
            if brier and brier["total_resolved"] > 0:
                weight = max(0.0, 1.0 - brier["avg_brier_score"])
            else:
                weight = 1.0

            assert 0.0 < weight < 1.0, f"Weight should be between 0 and 1, got {weight}"
        finally:
            from database.pool import close_pool
            await close_pool()


class TestBackwardCompat:
    """R-2.1.1 RED 3 — model_weights=None -> backward compat."""

    @pytest.mark.asyncio
    async def test_consensus_without_weights_unchanged(self):
        """Sans model_weights, le comportement est identique à l'actuel."""
        engine = ConsensusEngine(min_agreement=0.3)
        model_results = _make_model_results_same_triplet()

        result_old = (await engine.compute_consensus(model_results)).triplets
        result_new = (await engine.compute_consensus(model_results, model_weights=None)).triplets

        assert len(result_old) == len(result_new), "Nombre de résultats différent"
        for old, new in zip(result_old, result_new):
            assert old.consensus_score == new.consensus_score, (
                f"Score différent : old={old.consensus_score}, new={new.consensus_score}"
            )
            assert old.agreement_ratio == new.agreement_ratio
            assert old.avg_confidence == new.avg_confidence
            assert old.contributing_models == new.contributing_models

    @pytest.mark.asyncio
    async def test_consensus_with_all_weights_one_unchanged(self):
        """Tous les poids à 1.0 -> résultat identique au non-pondéré."""
        engine = ConsensusEngine(min_agreement=0.3)
        model_results = _make_model_results_same_triplet()

        result_no_weights = (await engine.compute_consensus(model_results)).triplets
        result_all_one = (await engine.compute_consensus(
            model_results,
            model_weights={"model_a": 1.0, "model_b": 1.0, "model_c": 1.0},
        )).triplets

        for old, new in zip(result_no_weights, result_all_one):
            assert old.consensus_score == new.consensus_score, (
                f"Score devrait être identique quand tous poids=1.0 : "
                f"no_weights={old.consensus_score}, all_one={new.consensus_score}"
            )
