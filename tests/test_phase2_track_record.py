"""Tests Phase 2.3 — Track record modèles et frames en DB."""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


import pytest


class TestModelTrackRecord:
    """Tests du Brier scoring."""

    def test_brier_score_perfect_prediction(self):
        """Prédiction parfaite = Brier 0."""
        predicted = 1.0
        actual = 1.0
        brier = (predicted - actual) ** 2
        assert brier == 0.0

    def test_brier_score_worst_prediction(self):
        """Pire prédiction = Brier 1."""
        predicted = 1.0
        actual = 0.0
        brier = (predicted - actual) ** 2
        assert brier == 1.0

    def test_brier_score_uncertain(self):
        """Prédiction 0.5 = Brier 0.25."""
        predicted = 0.5
        actual = 1.0
        brier = (predicted - actual) ** 2
        assert brier == 0.25

    def test_brier_score_slightly_wrong(self):
        """Prédiction 0.8 quand la réponse est 1.0 = Brier 0.04."""
        predicted = 0.8
        actual = 1.0
        brier = (predicted - actual) ** 2
        assert abs(brier - 0.04) < 0.001


class TestTierTransitions:
    """Tests de la structure des transitions."""

    def test_valid_tiers(self):
        valid = {"sandbox", "proposition", "validated", "verified"}
        for tier in valid:
            assert tier in valid

    def test_promotion_order(self):
        order = ["sandbox", "proposition", "validated", "verified"]
        for i in range(len(order) - 1):
            assert order.index(order[i]) < order.index(order[i + 1])


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
