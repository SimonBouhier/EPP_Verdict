"""
Tests R-2.1.2 — Dashboard performance modèles.

RED-GREEN-FIX : ces tests DOIVENT échouer avant implémentation.

Vérifie que :
1. get_all_model_brier_scores() retourne les stats de tous les modèles
2. La commande CLI 'epp models stats' produit un tableau lisible
3. Les poids calculés (1 - avg_brier) sont affichés
"""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib

import pytest
from click.testing import CliRunner


class TestGetAllModelBrierScores:
    """R-2.1.2 RED 1 — engine.get_all_model_brier_scores()."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_predictions(self, tmp_path):
        """Sans prédictions → liste vide."""
        from database.engine import ISpaceDB
        from database.pool import close_pool

        db = ISpaceDB(str(tmp_path / "test_empty.db"))
        await db.initialize()
        try:
            results = await db.get_all_model_brier_scores()
            assert isinstance(results, list)
            assert len(results) == 0
        finally:
            await close_pool()

    @pytest.mark.asyncio
    async def test_returns_stats_for_resolved_models(self, tmp_path):
        """Modèles avec prédictions résolues → stats complètes."""
        from database.engine import ISpaceDB
        from database.pool import close_pool

        db = ISpaceDB(str(tmp_path / "test_stats.db"))
        await db.initialize()
        try:
            # Enregistrer des prédictions pour 2 modèles
            await db.record_model_prediction(
                model_id="model_alpha",
                provider_id="ollama",
                claim_hash="claim_001",
                predicted_confidence=0.9,
                predicted_agreed=True,
            )
            await db.record_model_prediction(
                model_id="model_beta",
                provider_id="ollama",
                claim_hash="claim_001",
                predicted_confidence=0.6,
                predicted_agreed=True,
            )
            # Résoudre
            await db.resolve_prediction(
                claim_hash="claim_001",
                actual_outcome=1.0,
            )

            results = await db.get_all_model_brier_scores()
            assert isinstance(results, list)
            assert len(results) == 2

            # Vérifier les champs attendus
            model_ids = {r["model_id"] for r in results}
            assert "model_alpha" in model_ids
            assert "model_beta" in model_ids

            for r in results:
                assert "model_id" in r
                assert "provider_id" in r
                assert "total_predictions" in r
                assert "resolved_predictions" in r
                assert "avg_brier_score" in r
                assert "weight" in r
                assert 0.0 <= r["weight"] <= 1.0
        finally:
            await close_pool()

    @pytest.mark.asyncio
    async def test_weight_formula_correct(self, tmp_path):
        """weight = max(0.0, 1.0 - avg_brier_score)."""
        from database.engine import ISpaceDB
        from database.pool import close_pool

        db = ISpaceDB(str(tmp_path / "test_weight.db"))
        await db.initialize()
        try:
            await db.record_model_prediction(
                model_id="model_precise",
                provider_id="ollama",
                claim_hash="claim_w1",
                predicted_confidence=0.9,
                predicted_agreed=True,
            )
            await db.resolve_prediction(claim_hash="claim_w1", actual_outcome=1.0)

            results = await db.get_all_model_brier_scores()
            assert len(results) >= 1

            for r in results:
                expected_weight = max(0.0, 1.0 - r["avg_brier_score"])
                assert abs(r["weight"] - expected_weight) < 1e-4, (
                    f"Weight mismatch for {r['model_id']}: "
                    f"got {r['weight']}, expected {expected_weight}"
                )
        finally:
            await close_pool()


class TestModelsStatsCLI:
    """R-2.1.2 RED 2 — Commande CLI 'epp models stats'."""

    def test_models_stats_command_exists(self):
        """La commande 'models stats' est enregistrée."""
        from cli.epp_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["models", "stats", "--help"])
        assert result.exit_code == 0, f"Command not found: {result.output}"
        assert "model" in result.output.lower() or "stats" in result.output.lower()

    def test_models_stats_outputs_dashboard_header(self):
        """La sortie contient le titre du dashboard et gère le cas vide."""
        from cli.epp_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["models", "stats"])
        assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
        assert "Model Performance Dashboard" in result.output
        # Sans données : message cold start
        assert "cold start" in result.output or "Weight" in result.output


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
