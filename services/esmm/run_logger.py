"""
ESMM Run Logger — Logs structurés du pipeline.

Émet des événements JSON structurés à chaque phase du pipeline.
Double destination : logging Python (stdout/fichier) + DB (exploration_cycles).

Usage :
    logger = RunLogger(run_id=42)
    logger.phase_start("divergent", question="What is Solana?", models=["m1", "m2"])
    logger.model_response("m1", response="...", latency_ms=1234)
    logger.phase_end("divergent", triplets_extracted=5)
    logger.crystallization(attestation)
    summary = logger.get_summary()
"""

import logging
import time
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("esmm.run")


@dataclass
class PhaseEvent:
    """Événement d'une phase du pipeline."""
    phase: str                          # "divergent" | "debate" | "meta" | "extraction" | "consensus" | "crystallization"
    event_type: str                     # "start" | "end" | "model_response" | "triplet" | "attestation" | "error"
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)


class RunLogger:
    """
    Accumule les événements d'un run ESMM.

    Pas de dépendance à la DB — l'orchestrateur peut persister
    le summary en DB après le run si nécessaire.
    """

    def __init__(self, run_id: int, question: str = ""):
        self.run_id = run_id
        self.question = question
        self.events: List[PhaseEvent] = []
        self.started_at = time.time()
        self._current_phase: Optional[str] = None

    def phase_start(self, phase: str, **kwargs) -> None:
        """Début d'une phase."""
        self._current_phase = phase
        event = PhaseEvent(
            phase=phase,
            event_type="start",
            data=kwargs,
        )
        self.events.append(event)
        logger.info(json.dumps({
            "run_id": self.run_id,
            "event": "phase_start",
            "phase": phase,
            **kwargs,
        }))

    def phase_end(self, phase: str, **kwargs) -> None:
        """Fin d'une phase."""
        event = PhaseEvent(
            phase=phase,
            event_type="end",
            data=kwargs,
        )
        self.events.append(event)
        self._current_phase = None
        logger.info(json.dumps({
            "run_id": self.run_id,
            "event": "phase_end",
            "phase": phase,
            **kwargs,
        }))

    def model_response(self, model_id: str, latency_ms: float, success: bool, **kwargs) -> None:
        """Réponse d'un modèle."""
        event = PhaseEvent(
            phase=self._current_phase or "unknown",
            event_type="model_response",
            data={"model_id": model_id, "latency_ms": latency_ms, "success": success, **kwargs},
        )
        self.events.append(event)
        logger.debug(json.dumps({
            "run_id": self.run_id,
            "event": "model_response",
            "model_id": model_id,
            "latency_ms": round(latency_ms, 1),
            "success": success,
        }))

    def triplet_extracted(self, subject: str, predicate: str, object_: str, confidence: float) -> None:
        """Triplet extrait."""
        event = PhaseEvent(
            phase="extraction",
            event_type="triplet",
            data={"subject": subject, "predicate": predicate, "object": object_, "confidence": confidence},
        )
        self.events.append(event)
        logger.info(json.dumps({
            "run_id": self.run_id,
            "event": "triplet_extracted",
            "triplet": f"{subject} → {predicate} → {object_}",
            "confidence": confidence,
        }))

    def crystallization(self, claim_hash: str, consensus_score: float, confidence_tier: str) -> None:
        """Attestation cristallisée."""
        event = PhaseEvent(
            phase="crystallization",
            event_type="attestation",
            data={"claim_hash": claim_hash, "consensus_score": consensus_score, "confidence_tier": confidence_tier},
        )
        self.events.append(event)
        logger.info(json.dumps({
            "run_id": self.run_id,
            "event": "attestation_crystallized",
            "claim_hash": claim_hash[:16] + "...",
            "consensus_score": consensus_score,
            "confidence_tier": confidence_tier,
        }))

    def error(self, phase: str, error: str, **kwargs) -> None:
        """Erreur dans le pipeline."""
        event = PhaseEvent(
            phase=phase,
            event_type="error",
            data={"error": error, **kwargs},
        )
        self.events.append(event)
        logger.error(json.dumps({
            "run_id": self.run_id,
            "event": "error",
            "phase": phase,
            "error": error,
        }))

    def get_summary(self) -> Dict[str, Any]:
        """
        Résumé structuré du run complet.

        Retourne un dict avec :
        - run_id, question, duration_ms
        - phases : liste des phases avec durée et stats
        - models : stats par modèle (appels, latence moyenne)
        - triplets_extracted, attestations_produced
        - errors : liste des erreurs
        """
        duration_ms = (time.time() - self.started_at) * 1000

        # Stats par phase
        phases = {}
        for evt in self.events:
            if evt.phase not in phases:
                phases[evt.phase] = {"events": 0, "errors": 0}
            phases[evt.phase]["events"] += 1
            if evt.event_type == "error":
                phases[evt.phase]["errors"] += 1

        # Stats modèles
        model_stats = {}
        for evt in self.events:
            if evt.event_type == "model_response":
                mid = evt.data.get("model_id", "unknown")
                if mid not in model_stats:
                    model_stats[mid] = {"calls": 0, "total_latency_ms": 0, "failures": 0}
                model_stats[mid]["calls"] += 1
                model_stats[mid]["total_latency_ms"] += evt.data.get("latency_ms", 0)
                if not evt.data.get("success", True):
                    model_stats[mid]["failures"] += 1

        # Comptes
        triplets = sum(1 for e in self.events if e.event_type == "triplet")
        attestations = sum(1 for e in self.events if e.event_type == "attestation")
        errors = [e.data for e in self.events if e.event_type == "error"]

        return {
            "run_id": self.run_id,
            "question": self.question,
            "duration_ms": round(duration_ms, 1),
            "phases": phases,
            "model_stats": model_stats,
            "triplets_extracted": triplets,
            "attestations_produced": attestations,
            "errors": errors,
        }
