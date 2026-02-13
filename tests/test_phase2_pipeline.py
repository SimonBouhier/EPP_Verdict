"""Tests Phase 2.2 — Pipeline ESMM -> Cristallisation."""

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
