"""Tests Phase 2.2 — Pipeline ESMM -> Cristallisation."""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


import pytest
import asyncio
import time

from services.esmm.pipeline import (
    PipelineConfig,
    PipelineResult,
    run_pipeline,
)
from services.esmm.attestation import EpistemicAttestation


class TestPipelineConfig:
    """Tests de la configuration du pipeline."""

    def test_defaults(self):
        config = PipelineConfig()
        assert config.min_consensus_for_attestation == 0.4
        assert config.min_confidence_for_injection == 0.5

    def test_custom_config(self):
        config = PipelineConfig(
            min_consensus_for_attestation=0.6,
            metrological_frame="blockchain_tps_v1.0",
        )
        assert config.metrological_frame == "blockchain_tps_v1.0"


class TestPipelineResult:
    """Tests de la structure de résultat."""

    def test_result_structure(self):
        result = PipelineResult(
            run_id=1, question="test", attestations=[],
            triplets_extracted=0, triplets_attested=0,
            triplets_injected=0, duration_ms=100.0, errors=[],
        )
        assert result.run_id == 1
        assert result.attestations == []
        assert result.errors == []


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
