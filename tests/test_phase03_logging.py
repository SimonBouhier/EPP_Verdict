# tests/test_phase03_logging.py
"""
Phase 0.3.4 Tests — RunLogger Structured Logging

Tests for:
- RunLogger initialization
- Phase lifecycle events (start/end)
- Model response logging
- Triplet extraction logging
- Crystallization logging
- Error logging
- Summary generation with stats
"""

import pytest
import time
from services.esmm.run_logger import RunLogger, PhaseEvent


class TestRunLogger:
    """Tests pour le logging structuré du pipeline."""

    def test_init(self):
        """RunLogger s'initialise avec run_id et question."""
        rl = RunLogger(run_id=42, question="What is Solana?")
        assert rl.run_id == 42
        assert rl.question == "What is Solana?"
        assert len(rl.events) == 0

    def test_phase_lifecycle(self):
        """phase_start + phase_end créent 2 événements."""
        rl = RunLogger(run_id=1)
        rl.phase_start("divergent", models=["m1", "m2"])
        rl.phase_end("divergent", triplets_extracted=5)

        assert len(rl.events) == 2
        assert rl.events[0].event_type == "start"
        assert rl.events[1].event_type == "end"
        assert rl.events[0].phase == "divergent"

    def test_model_response(self):
        """model_response enregistre le modèle et la latence."""
        rl = RunLogger(run_id=1)
        rl.phase_start("divergent")
        rl.model_response("model_a", latency_ms=500, success=True)

        responses = [e for e in rl.events if e.event_type == "model_response"]
        assert len(responses) == 1
        assert responses[0].data["model_id"] == "model_a"
        assert responses[0].data["latency_ms"] == 500

    def test_triplet_extracted(self):
        """triplet_extracted enregistre le triplet."""
        rl = RunLogger(run_id=1)
        rl.triplet_extracted("Solana", "is_a", "blockchain", 0.9)

        triplets = [e for e in rl.events if e.event_type == "triplet"]
        assert len(triplets) == 1
        assert triplets[0].data["subject"] == "Solana"

    def test_crystallization(self):
        """crystallization enregistre l'attestation."""
        rl = RunLogger(run_id=1)
        rl.crystallization("abc123", 0.85, "high")

        atts = [e for e in rl.events if e.event_type == "attestation"]
        assert len(atts) == 1
        assert atts[0].data["claim_hash"] == "abc123"

    def test_error_logging(self):
        """error enregistre l'erreur avec la phase."""
        rl = RunLogger(run_id=1)
        rl.error("debate", "Model timeout", model_id="m1")

        errors = [e for e in rl.events if e.event_type == "error"]
        assert len(errors) == 1
        assert errors[0].data["error"] == "Model timeout"

    def test_get_summary(self):
        """get_summary retourne un résumé structuré complet."""
        rl = RunLogger(run_id=1, question="Test?")
        rl.phase_start("divergent")
        rl.model_response("m1", latency_ms=100, success=True)
        rl.model_response("m2", latency_ms=200, success=True)
        rl.model_response("m3", latency_ms=150, success=False)
        rl.phase_end("divergent")
        rl.triplet_extracted("A", "is", "B", 0.8)
        rl.triplet_extracted("C", "has", "D", 0.7)
        rl.crystallization("hash1", 0.85, "high")

        summary = rl.get_summary()

        assert summary["run_id"] == 1
        assert summary["question"] == "Test?"
        assert summary["triplets_extracted"] == 2
        assert summary["attestations_produced"] == 1
        assert summary["duration_ms"] >= 0  # Can be 0 if test runs fast
        assert "m1" in summary["model_stats"]
        assert summary["model_stats"]["m1"]["calls"] == 1
        assert summary["model_stats"]["m3"]["failures"] == 1
        assert len(summary["errors"]) == 0

    def test_summary_with_errors(self):
        """get_summary inclut les erreurs."""
        rl = RunLogger(run_id=1)
        rl.error("consensus", "Insufficient models")
        summary = rl.get_summary()
        assert len(summary["errors"]) == 1


class TestPhaseEvent:
    """Tests pour la dataclass PhaseEvent."""

    def test_default_timestamp(self):
        """PhaseEvent génère un timestamp par défaut."""
        before = time.time()
        evt = PhaseEvent(phase="test", event_type="start")
        after = time.time()

        assert before <= evt.timestamp <= after

    def test_custom_data(self):
        """PhaseEvent stocke des données arbitraires."""
        evt = PhaseEvent(
            phase="extraction",
            event_type="triplet",
            data={"subject": "A", "predicate": "is", "object": "B"}
        )
        assert evt.data["subject"] == "A"
        assert evt.data["predicate"] == "is"
        assert evt.data["object"] == "B"

    def test_empty_data_default(self):
        """PhaseEvent a un dict vide par défaut pour data."""
        evt = PhaseEvent(phase="test", event_type="end")
        assert evt.data == {}
