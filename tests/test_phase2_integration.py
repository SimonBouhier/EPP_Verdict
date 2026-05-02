"""Tests d'intégration Phase 2 — scénarios de démonstration."""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


import pytest


class TestScenarioStructure:
    """Vérifie que les scénarios existent et sont importables."""

    def test_pipeline_import(self):
        from services.esmm.pipeline import run_pipeline, PipelineConfig, PipelineResult
        assert callable(run_pipeline)

    def test_confidence_tier_import(self):
        from services.esmm.attestation import derive_confidence_tier, CONFIDENCE_TIERS
        assert len(CONFIDENCE_TIERS) == 4

    def test_architecture_family_import(self):
        from services.providers.base import infer_architecture_family
        assert callable(infer_architecture_family)


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
