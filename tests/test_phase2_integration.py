"""Tests d'intégration Phase 2 — scénarios de démonstration."""

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
