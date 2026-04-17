"""Tests Phase 3 — Orchestrator enrichment: ESMMRunResult + consensus_triplets."""

import pytest
from dataclasses import fields

from services.esmm.orchestrator import ESMMRunResult


class TestESMMRunResultEnrichment:

    def test_esmm_run_result_has_consensus_triplets(self):
        """ESMMRunResult has consensus_triplets field."""
        field_names = [f.name for f in fields(ESMMRunResult)]
        assert "consensus_triplets" in field_names

    def test_consensus_triplets_default_empty(self):
        """Default value of consensus_triplets is empty list."""
        result = ESMMRunResult(
            run_id=1,
            status="completed",
            cycles_completed=0,
            total_triplets=0,
            triplets_injected=0,
            cochain_size=0,
            gaps_detected=0,
            coverage_score=0.0,
            consensus_density=0.0,
            epistemic_diversity=0.0,
            structural_stability=0.0,
            duration_ms=0.0,
        )
        assert result.consensus_triplets == []

    def test_consensus_triplets_accepts_list(self):
        """consensus_triplets can be populated."""
        from services.providers.mock_provider import make_synthetic_triplets
        triplets = make_synthetic_triplets(n=3)
        result = ESMMRunResult(
            run_id=1,
            status="completed",
            cycles_completed=1,
            total_triplets=3,
            triplets_injected=3,
            cochain_size=0,
            gaps_detected=0,
            coverage_score=0.5,
            consensus_density=0.5,
            epistemic_diversity=0.5,
            structural_stability=0.5,
            duration_ms=100.0,
            consensus_triplets=triplets,
        )
        assert len(result.consensus_triplets) == 3
        assert result.consensus_triplets[0].subject == "solana"


class TestCycleManagerFactory:

    def test_create_cycle_manager_accepts_providers(self):
        """create_cycle_manager signature accepts providers parameter."""
        import inspect
        from services.esmm.cycle_manager import create_cycle_manager
        sig = inspect.signature(create_cycle_manager)
        assert "providers" in sig.parameters

    def test_create_cycle_manager_providers_is_optional(self):
        """providers parameter defaults to None."""
        import inspect
        from services.esmm.cycle_manager import create_cycle_manager
        sig = inspect.signature(create_cycle_manager)
        param = sig.parameters["providers"]
        assert param.default is None
