"""
ESMM Phase 3 - ESMM ORCHESTRATOR
=================================

Orchestrateur principal du protocole ESMM.

Responsabilites:
- Initialisation et finalisation des runs
- Execution des cycles d'exploration
- Detection de lacunes
- Construction de la 0-cochaine
- Adaptation dynamique des cycles
- Persistence de l'etat pour reprise

Optimisations:
- Timeouts globaux et par cycle
- Checkpoints intermediaires
- Logs structures (structlog-compatible)
- Regles d'adaptation etendues

Author: Lyra-ACE ESMM Protocol
"""
from __future__ import annotations

import time
import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, field

from .cycle_prompts import CycleType
from .cycle_manager import ExplorationCycleManager, create_cycle_manager
from .gap_detector import KnowledgeGapDetector, create_gap_detector
from .cochain_builder import CochainBuilder, create_cochain_builder
from .coverage_analyzer import CoverageAnalyzer, CoverageMetrics

if TYPE_CHECKING:
    from database.engine import ISpaceDB

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIG HELPERS (read from config.yaml with hardcoded fallback)
# ============================================================================

def _default_cycle_sequence() -> List[str]:
    """Read esmm.cycle_sequence from config.yaml, fallback to hardcoded default."""
    try:
        from services.config_loader import get_section
        esmm = get_section("esmm", {})
        seq = esmm.get("cycle_sequence")
        if isinstance(seq, list) and seq:
            return list(seq)
    except Exception:
        pass
    return ["divergent", "debate", "meta"]


def _default_min_consensus() -> float:
    """Read esmm.min_consensus from config.yaml, fallback to 0.4."""
    try:
        from services.config_loader import get_section
        esmm = get_section("esmm", {})
        val = esmm.get("min_consensus")
        if val is not None:
            return float(val)
    except Exception:
        pass
    return 0.4


# ============================================================================
# ADR-012 : Bifurcation déterministe / épistémique
# ============================================================================


class ClaimNature(str, Enum):
    """Nature épistémique d'un claim — déclarée par l'appelant (Axiome 3)."""

    EPISTEMIC = "epistemic"          # Pipeline ESMM complet (défaut)
    DETERMINISTIC = "deterministic"  # Lookup source autoritaire, bypass ESMM


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class ESMMRunConfig:
    """
    Configuration d'un run ESMM.

    Attributes:
        models: Liste des modeles a utiliser
        seed_type: Type de graine (minimal, standard, extended)
        cycles_per_type: Nombre de cycles par type
        cycle_sequence: Ordre d'execution des cycles
        min_consensus: Seuil minimum de consensus
        min_confidence: Seuil minimum de confiance
        max_questions_per_cycle: Questions max par cycle
        inject_triplets: Injecter les triplets dans le graphe
        build_cochain: Construire la 0-cochaine
        detect_gaps: Detecter les lacunes
        adaptive_cycles: Adapter dynamiquement les cycles
        max_total_cycles: Limite pour eviter boucles infinies
        max_duration_hours: Timeout global en heures
    """
    models: List[str] = field(default_factory=list)  # Must be provided by caller
    seed_type: str = "standard"
    cycles_per_type: Dict[str, int] = field(default_factory=lambda: {
        "divergent": 3,
        "debate": 2,
        "meta": 1
    })
    # AUDIT[A8-004] 🟡→✅ FIXED Phase Audit: lu depuis config.yaml::esmm.cycle_sequence.
    cycle_sequence: List[str] = field(default_factory=_default_cycle_sequence)
    # AUDIT[A8-003] 🟡→✅ FIXED Phase Audit: lu depuis config.yaml::esmm.min_consensus.
    min_consensus: float = field(default_factory=_default_min_consensus)
    min_confidence: float = 0.5
    max_questions_per_cycle: int = 10
    inject_triplets: bool = True
    build_cochain: bool = True
    detect_gaps: bool = True
    adaptive_cycles: bool = True
    max_total_cycles: int = 9  # ~3 phases × 3 iterations
    max_duration_hours: float = 24.0
    # Dual-mode: VERIFY support
    input_mode: str = "explore"               # "explore" or "verify"
    original_claim: Optional[str] = None      # Full claim text for VERIFY mode
    # ADR-012 : bifurcation déterministe
    claim_nature: ClaimNature = ClaimNature.EPISTEMIC
    source_anchor_spec: Optional[Any] = None  # SourceAnchorSpec — Any évite import circulaire
    subject_override: Optional[str] = None    # Fix 1 (Lot A) : override subject pour les audits

    def __post_init__(self) -> None:
        if (
            self.claim_nature == ClaimNature.DETERMINISTIC
            and self.source_anchor_spec is None
        ):
            raise ValueError(
                "ESMMRunConfig: claim_nature=DETERMINISTIC requiert source_anchor_spec"
            )


@dataclass
class ESMMRunState:
    """
    Etat persistant d'un run pour reprise apres echec.

    Attributes:
        run_id: ID du run
        current_cycle_type: Type de cycle en cours
        current_iteration: Iteration en cours
        triplets_extracted: Total de triplets extraits
        last_checkpoint: Timestamp du dernier checkpoint
    """
    run_id: int
    current_cycle_type: str
    current_iteration: int
    triplets_extracted: int
    last_checkpoint: datetime


@dataclass
class ESMMRunResult:
    """
    Resultat final d'un run ESMM.

    Attributes:
        run_id: ID du run
        status: Statut final (completed, failed, paused)
        cycles_completed: Nombre de cycles completes
        total_triplets: Total de triplets extraits
        triplets_injected: Triplets injectes dans le graphe
        cochain_size: Taille de la 0-cochaine
        gaps_detected: Nombre de lacunes detectees
        coverage_score: Score de couverture final
        consensus_density: Densite de consensus
        epistemic_diversity: Diversite epistemique
        structural_stability: Stabilite structurelle
        duration_ms: Duree totale en ms
        errors: Liste des erreurs rencontrees
    """
    run_id: int
    status: str
    cycles_completed: int
    total_triplets: int
    triplets_injected: int
    cochain_size: int
    gaps_detected: int
    coverage_score: float
    consensus_density: float
    epistemic_diversity: float
    structural_stability: float
    duration_ms: float
    errors: List[str] = field(default_factory=list)
    consensus_triplets: List = field(default_factory=list)
    # ADR-010: accumulated diagnostics across all cycles
    vote_entropy: float = 0.0
    semantic_dispersion: Optional[float] = None
    triplets_before_consensus: int = 0
    triplets_after_consensus: int = 0
    # ADR-011-v2: reconciliation metadata
    reconciliation_meta: Optional[Dict] = None


# ============================================================================
# ORCHESTRATOR
# ============================================================================

class ESMMOrchestrator:
    """
    Orchestrateur principal du protocole ESMM.

    Coordonne l'ensemble du pipeline d'exploration semantique multi-modeles.
    """

    def __init__(
        self,
        db: "ISpaceDB",
        config: ESMMRunConfig = None,
        providers: Optional[Dict] = None,
    ):
        """
        Initialise l'orchestrateur.

        Args:
            db: Instance de la base de donnees
            config: Configuration du run (defaut si None)
            providers: Dict {provider_id: ModelProvider} (D6, optional)
        """
        self.db = db
        self.config = config or ESMMRunConfig()
        self._providers = providers

        # Composants (initialises dans initialize_run)
        self.cycle_manager: Optional[ExplorationCycleManager] = None
        self.gap_detector: Optional[KnowledgeGapDetector] = None
        self.cochain_builder: Optional[CochainBuilder] = None
        self.coverage_analyzer: Optional[CoverageAnalyzer] = None

        # Etat du run
        self._state: Optional[ESMMRunState] = None
        self._start_time: Optional[datetime] = None
        self._run_id: Optional[int] = None
        self._collected_triplets: List = []

        # ADR-011-v2: Semantic Fingerprinting state
        self._raw_model_triplets: Dict[str, List] = {}
        self._final_consensus_triplets: Optional[List] = None
        self._reconciliation_meta: Optional[Dict] = None
        self._model_weights: Optional[Dict[str, float]] = None

        # Convergence detection: previous gap signature
        self._prev_gap_signature: Optional[tuple] = None

        # Statistiques accumulees
        self._stats = {
            "divergent": 0,
            "debate": 0,
            "meta": 0,
            "assess": 0,
            "challenge": 0,
            "adjudicate": 0,
            "total_cycles": 0,
            "total_triplets": 0,
            "triplets_injected": 0,
            "new_concepts": 0,
            "gaps_detected": 0,
            "errors": []
        }

        logger.info(
            "[ESMMOrchestrator] Initialized",
            extra={"config": self.config.__dict__}
        )

    async def run(self) -> ESMMRunResult:
        """
        Execute le protocole ESMM complet.

        Pipeline:
        1. Initialisation du run
        2. Execution des cycles
        3. Detection des lacunes
        4. Construction de la cochaine
        5. Finalisation

        Returns:
            ESMMRunResult avec les metriques finales
        """
        try:
            # Phase 1: Initialisation
            run_id = await self.initialize_run()
            self._run_id = run_id
            self._start_time = datetime.now()

            logger.info(
                "[ESMMOrchestrator] Run started",
                extra={"run_id": run_id}
            )

            # Phase 2: Execution des cycles
            await self.execute_cycles(run_id)

            # Phase 2.5: ADR-011-v2 Semantic Fingerprinting
            await self.reconcile()

            # Phase 3: Finalisation
            return await self.finalize_run(run_id)

        except Exception as e:
            logger.error(
                "[ESMMOrchestrator] Run failed",
                extra={
                    "error": str(e),
                    "run_id": self._run_id
                }
            )

            # Sauvegarder l'etat pour reprise
            if self._state:
                await self._save_state()

            self._stats["errors"].append(str(e))

            # Marquer le run comme echoue
            if self._run_id:
                await self.db.update_esmm_run_status(
                    self._run_id,
                    "failed",
                    error_message=str(e)
                )

            raise

    async def initialize_run(self) -> int:
        """
        Initialise un nouveau run ESMM.

        Returns:
            run_id
        """
        # Creer le run dans la DB
        run_id = await self.db.create_esmm_run(
            config=self.config.__dict__,
            models=self.config.models,
            seed_type=self.config.seed_type
        )

        # Initialiser les composants (D6: pass providers if available)
        self.cycle_manager = await create_cycle_manager(
            db=self.db,
            run_id=run_id,
            models=self.config.models,
            providers=self._providers,
            min_consensus=self.config.min_consensus,
        )

        self.gap_detector = create_gap_detector(
            db=self.db,
            run_id=run_id
        )

        self.cochain_builder = create_cochain_builder(
            db=self.db,
            run_id=run_id
        )

        self.coverage_analyzer = CoverageAnalyzer(self.db)

        # Initialiser l'etat
        self._state = ESMMRunState(
            run_id=run_id,
            current_cycle_type="",
            current_iteration=0,
            triplets_extracted=0,
            last_checkpoint=datetime.now()
        )

        # Mettre a jour le statut
        await self.db.update_esmm_run_status(run_id, "running")

        logger.info(
            "[ESMMOrchestrator] Run initialized",
            extra={"run_id": run_id}
        )

        return run_id

    async def execute_cycles(
        self,
        run_id: int,
        resume: bool = False,
        model_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Execute les cycles d'exploration avec adaptation dynamique.

        Args:
            run_id: ID du run
            resume: True si reprise d'un run pause
            model_weights: Optional Brier-based weights per model.
                          If None, weights are computed from DB at run start.
        """
        # ADR-012 : bypass ESMM pour claims déterministes — la source fait foi
        if self.config.claim_nature == ClaimNature.DETERMINISTIC:
            logger.info(
                "[ESMMOrchestrator] DETERMINISTIC claim — bypassing ESMM cycles",
                extra={"run_id": run_id},
            )
            return

        # R-2.1.1: Compute Brier-based model weights if not provided
        if model_weights is None:
            model_weights = await self._compute_model_weights()
        # ADR-011-v2: store weights for reconcile()
        self._model_weights = model_weights
        cycles_per_type = dict(self.config.cycles_per_type)

        # VERIFY mode: override cycle sequence and cycles_per_type
        # Each execute_cycle() queries ALL models, so cycles_per_type=1 per phase.
        cycle_sequence = list(self.config.cycle_sequence)
        if self.config.input_mode == "verify":
            cycle_sequence = ["assess", "challenge", "adjudicate"]
            self.config.cycle_sequence = cycle_sequence  # sync → _build_consensus_meta reads truth
            cycles_per_type = {
                "assess": 1,
                "challenge": 1,
                "adjudicate": 1,
            }

        # VERIFY state: accumulate per-model verdicts across phases
        _verify_model_verdicts: Dict[str, str] = {}

        for cycle_type_str in cycle_sequence:
            cycle_type = CycleType(cycle_type_str)

            for i in range(cycles_per_type.get(cycle_type_str, 1)):
                # Verification des limites
                if self._stats["total_cycles"] >= self.config.max_total_cycles:
                    logger.warning(
                        "[ESMMOrchestrator] Max cycles reached",
                        extra={"total": self._stats["total_cycles"]}
                    )
                    return

                if self._check_timeout():
                    logger.warning(
                        "[ESMMOrchestrator] Timeout reached",
                        extra={"hours": self.config.max_duration_hours}
                    )
                    return

                # Mettre a jour l'etat
                self._state.current_cycle_type = cycle_type_str
                self._state.current_iteration = i + 1

                # Mettre a jour le statut dans la DB
                await self.db.update_esmm_run_status(
                    run_id,
                    "running",
                    current_cycle=cycle_type_str,
                    current_iteration=i + 1
                )

                # Executer le cycle
                try:
                    # Build context — VERIFY mode includes original_claim
                    cycle_context: Dict[str, Any] = {"domain": "general"}
                    if self.config.input_mode == "verify" and self.config.original_claim:
                        cycle_context["original_claim"] = self.config.original_claim

                        # CHALLENGE: circular rotation — pass per-model verdicts
                        if cycle_type_str == "challenge" and _verify_model_verdicts:
                            cycle_context["_verify_model_verdicts"] = _verify_model_verdicts

                        # ADJUDICATE: synthesis — all verdicts visible
                        if cycle_type_str == "adjudicate" and _verify_model_verdicts:
                            verdicts_summary = "; ".join(
                                f"{m}: {r[:200]}"
                                for m, r in _verify_model_verdicts.items()
                            )
                            cycle_context["all_verdicts"] = verdicts_summary

                    result = await self.cycle_manager.execute_cycle(
                        cycle_type=cycle_type,
                        iteration=i + 1,
                        context=cycle_context,
                        model_weights=model_weights,
                    )

                    # VERIFY: capture per-model responses after ASSESS
                    if self.config.input_mode == "verify" and cycle_type_str == "assess":
                        for mid, rtxt in result.responses.items():
                            _verify_model_verdicts[mid] = rtxt

                    # Accumuler les statistiques
                    self._stats[cycle_type_str] = self._stats.get(cycle_type_str, 0) + 1
                    self._stats["total_cycles"] += 1
                    self._stats["total_triplets"] += result.triplets_extracted
                    self._state.triplets_extracted += result.triplets_extracted

                    # ADR-010: accumulate diagnostics
                    self._stats["triplets_before_consensus"] = (
                        self._stats.get("triplets_before_consensus", 0)
                        + result.triplets_before_consensus
                    )
                    self._stats["triplets_after_consensus"] = (
                        self._stats.get("triplets_after_consensus", 0)
                        + result.triplets_after_consensus
                    )
                    self._stats["vote_entropy"] = max(
                        self._stats.get("vote_entropy", 0.0),
                        result.vote_entropy,
                    )
                    if result.semantic_dispersion is not None:
                        prev = self._stats.get("semantic_dispersion")
                        if prev is None:
                            self._stats["semantic_dispersion"] = result.semantic_dispersion
                        else:
                            self._stats["semantic_dispersion"] = max(prev, result.semantic_dispersion)

                    # Collect consensus triplets (D2)
                    if result.consensus_triplets:
                        self._collected_triplets.extend(result.consensus_triplets)

                    # ADR-011-v2: accumulate raw per-model triplets (normalized to dicts)
                    if result.raw_model_triplets:
                        for model_id, triplets in result.raw_model_triplets.items():
                            as_dicts = []
                            for t in triplets:
                                if isinstance(t, dict):
                                    as_dicts.append(t)
                                elif hasattr(t, '__dict__'):
                                    as_dicts.append(vars(t))
                                else:
                                    as_dicts.append({
                                        "subject": getattr(t, "subject", ""),
                                        "relation": getattr(t, "relation", ""),
                                        "object": getattr(t, "object", ""),
                                        "confidence": getattr(t, "confidence", 0.0),
                                    })
                            self._raw_model_triplets.setdefault(model_id, []).extend(as_dicts)

                    logger.info(
                        "[ESMMOrchestrator] Cycle completed",
                        extra={
                            "cycle_type": cycle_type_str,
                            "iteration": i + 1,
                            "triplets": result.triplets_extracted,
                            "duration_ms": result.duration_ms
                        }
                    )

                # AUDIT[A2-012] 🟡 FRAGILE: timeout logué, cycle sauté — un cycle critique manqué fausse le consensus.
                except Exception as e:
                    logger.error(
                        f"[ESMMOrchestrator] Cycle failed: {e}",
                        extra={"cycle_type": cycle_type_str, "iteration": i + 1}
                    )
                    self._stats["errors"].append(f"{cycle_type_str}_{i+1}: {str(e)}")
                    continue

                # Detection de lacunes (EXPLORE only — gaps are meaningless in VERIFY)
                if self.config.detect_gaps and self.config.input_mode != "verify":
                    try:
                        gaps = await self.gap_detector.detect_all_gaps(max_per_type=10)
                        stored = await self.gap_detector.store_gaps(gaps[:20])
                        self._stats["gaps_detected"] += stored

                        # Convergence: if gaps identical to previous cycle, stop
                        sig = self._gap_signature(gaps)
                        if self._prev_gap_signature is not None and sig == self._prev_gap_signature:
                            logger.info(
                                "[ESMMOrchestrator] Convergence detected — gaps unchanged",
                                extra={"total_cycles": self._stats["total_cycles"]}
                            )
                            return
                        self._prev_gap_signature = sig
                    except Exception as e:
                        logger.warning(f"[ESMMOrchestrator] Gap detection error: {e}")

                # Adaptation dynamique (EXPLORE only — VERIFY sequence is fixed)
                if self.config.adaptive_cycles and self.config.input_mode != "verify":
                    try:
                        metrics = await self.coverage_analyzer.compute_metrics()
                        adaptations = self._should_adapt_cycles(metrics)

                        if adaptations:
                            for ctype, delta in adaptations.items():
                                old_value = cycles_per_type.get(ctype, 0)
                                cycles_per_type[ctype] = max(0, old_value + delta)

                                logger.info(
                                    "[ESMMOrchestrator] Cycle adaptation",
                                    extra={
                                        "cycle_type": ctype,
                                        "delta": delta,
                                        "new_count": cycles_per_type[ctype]
                                    }
                                )
                    except Exception as e:
                        logger.warning(f"[ESMMOrchestrator] Adaptation error: {e}")

                # Checkpoint
                await self._save_state()

    async def reconcile(self) -> Optional[Dict]:
        """ADR-011-v2: Semantic Fingerprinting — EXPAND + MATCH + APPLY.

        Returns reconciliation_meta dict, or None if skipped/failed.
        Side effect: sets self._final_consensus_triplets if alignment found.
        Never mutates self._collected_triplets.
        """
        from services.esmm.fingerprint_config import load_fingerprint_config
        from services.esmm.fingerprint_expand import expand_terms, _extract_unique_terms
        from services.esmm.fingerprint_match import match_fingerprints
        from services.esmm.fingerprint_apply import build_alignment_table, apply_alignment_to_triplets
        from services.esmm.consensus_engine import ConsensusEngine

        config = load_fingerprint_config()

        if not config.enabled:
            self._reconciliation_meta = {"method": "skipped", "reason": "disabled"}
            return self._reconciliation_meta

        if not self._raw_model_triplets:
            self._reconciliation_meta = {"method": "skipped", "reason": "no raw model triplets"}
            return self._reconciliation_meta

        # Count unique terms across all models
        all_terms = set()
        for triplets in self._raw_model_triplets.values():
            all_terms.update(_extract_unique_terms(triplets))

        if len(all_terms) < config.min_unique_terms:
            self._reconciliation_meta = {
                "method": "skipped",
                "reason": f"min_unique_terms not met ({len(all_terms)} < {config.min_unique_terms})",
            }
            return self._reconciliation_meta

        try:
            # Get provider info from cycle_manager
            if self.cycle_manager:
                rotator = self.cycle_manager.model_rotator
                provider_ids = self.cycle_manager.provider_ids
                provider_to_model = self.cycle_manager.provider_to_model
            else:
                # Fallback: use model names as provider IDs
                rotator = None
                provider_ids = list(self._raw_model_triplets.keys())
                provider_to_model = {m: m for m in provider_ids}

            # Phase 1: EXPAND
            expand_result = await asyncio.wait_for(
                expand_terms(
                    model_triplets=self._raw_model_triplets,
                    rotator=rotator,
                    provider_ids=provider_ids,
                    provider_to_model=provider_to_model,
                    config=config,
                ),
                timeout=config.timeout_seconds / 2,
            )

            # Phase 2: MATCH
            match_result = await asyncio.wait_for(
                match_fingerprints(
                    expand_result=expand_result,
                    config=config,
                ),
                timeout=config.timeout_seconds / 2,
            )

            # Phase 3: APPLY
            alignment_table = build_alignment_table(match_result.clusters, match_result.pair_scores)

            if alignment_table.entries:
                aligned = apply_alignment_to_triplets(self._raw_model_triplets, alignment_table)
                engine = ConsensusEngine(min_agreement=self.config.min_consensus)
                consensus = await engine.compute_consensus(aligned, model_weights=self._model_weights)
                self._final_consensus_triplets = list(consensus.triplets)

            self._reconciliation_meta = {
                "method": "semantic_fingerprinting",
                "version": "v1",
                "terms_fingerprinted": expand_result.terms_fingerprinted,
                "models_participated": expand_result.models_participated,
                "clusters_found": len(match_result.clusters),
                "alignments_applied": len(alignment_table.entries),
                "expand_duration_ms": expand_result.duration_ms,
                "match_duration_ms": match_result.duration_ms,
                "config": {
                    "merge_threshold": config.merge_threshold,
                    "matching_algorithm": config.matching_algorithm,
                },
            }
            return self._reconciliation_meta

        except asyncio.TimeoutError:
            self._reconciliation_meta = {"method": "skipped", "reason": "timeout"}
            return self._reconciliation_meta
        except Exception as e:
            logger.error(f"[ESMMOrchestrator] Fingerprinting failed: {e}")
            self._reconciliation_meta = {"method": "skipped", "reason": f"error: {e}"}
            return self._reconciliation_meta

    async def finalize_run(self, run_id: int) -> ESMMRunResult:
        """
        Finalise le run et calcule les metriques finales.

        Args:
            run_id: ID du run

        Returns:
            ESMMRunResult
        """
        logger.info(
            "[ESMMOrchestrator] Finalizing run",
            extra={"run_id": run_id}
        )

        # Construction de la cochaine
        cochain_size = 0
        if self.config.build_cochain:
            try:
                entries = await self.cochain_builder.build_cochain()
                cochain_size = len(entries)
                logger.info(
                    "[ESMMOrchestrator] Cochain built",
                    extra={"entries": cochain_size}
                )
            except Exception as e:
                logger.error(f"[ESMMOrchestrator] Cochain build error: {e}")
                self._stats["errors"].append(f"cochain: {str(e)}")

        # Metriques finales
        try:
            metrics = await self.coverage_analyzer.compute_metrics()
        except Exception as e:
            logger.error(f"[ESMMOrchestrator] Metrics error: {e}")
            metrics = CoverageMetrics(
                coverage_score=0.0,
                consensus_density=0.0,
                epistemic_diversity=0.0,
                structural_stability=0.0,
                graph_density=0.0,
                isolated_ratio=0.0,
                clustering_coefficient=0.0
            )

        # Duree totale
        duration_ms = 0.0
        if self._start_time:
            duration_ms = (datetime.now() - self._start_time).total_seconds() * 1000

        # Statistiques finales
        final_stats = {
            "cycles_completed": self._stats["total_cycles"],
            "total_questions": self._stats["total_cycles"],  # 1 question par cycle
            "total_triplets": self._stats["total_triplets"],
            "triplets_injected": self._stats.get("triplets_injected", self._stats["total_triplets"]),
            "concepts_created": self._stats.get("new_concepts", 0),
            "relations_created": self._stats["total_triplets"],
            "final_cochain_size": cochain_size,
            "coverage_score": metrics.coverage_score,
            "consensus_density": metrics.consensus_density,
            "epistemic_diversity": metrics.epistemic_diversity,
            "structural_stability": metrics.structural_stability
        }

        # Finaliser dans la DB
        await self.db.finalize_esmm_run(run_id, final_stats)

        result = ESMMRunResult(
            run_id=run_id,
            status="completed",
            cycles_completed=self._stats["total_cycles"],
            total_triplets=self._stats["total_triplets"],
            triplets_injected=self._stats.get("triplets_injected", self._stats["total_triplets"]),
            cochain_size=cochain_size,
            gaps_detected=self._stats["gaps_detected"],
            coverage_score=metrics.coverage_score,
            consensus_density=metrics.consensus_density,
            epistemic_diversity=metrics.epistemic_diversity,
            structural_stability=metrics.structural_stability,
            duration_ms=round(duration_ms, 2),
            errors=self._stats["errors"],
            # ADR-011-v2: use fingerprinted consensus if available, else per-cycle
            consensus_triplets=list(
                self._final_consensus_triplets
                if self._final_consensus_triplets is not None
                else self._collected_triplets
            ),
            vote_entropy=self._stats.get("vote_entropy", 0.0),
            semantic_dispersion=self._stats.get("semantic_dispersion"),
            triplets_before_consensus=self._stats.get("triplets_before_consensus", 0),
            triplets_after_consensus=self._stats.get("triplets_after_consensus", 0),
            reconciliation_meta=self._reconciliation_meta,
        )

        logger.info(
            "[ESMMOrchestrator] Run completed",
            extra={
                "run_id": run_id,
                "cycles": result.cycles_completed,
                "triplets": result.total_triplets,
                "coverage": result.coverage_score,
                "duration_ms": result.duration_ms
            }
        )

        return result

    # ========================================================================
    # ADAPTATION DYNAMIQUE
    # ========================================================================

    def _should_adapt_cycles(
        self,
        metrics: CoverageMetrics
    ) -> Optional[Dict[str, int]]:
        """
        Determine les adaptations de cycles basees sur les metriques.

        Regles:
        - coverage < 0.4 -> +1 divergent
        - consensus > 0.85 -> -1 debate
        - diversity < 0.3 -> +1 meta
        - stability < 0.5 -> +1 debate

        Args:
            metrics: Metriques de couverture actuelles

        Returns:
            Dict cycle_type -> delta, ou None si pas d'adaptation
        """
        adaptations = {}

        if metrics.coverage_score < 0.4:
            adaptations["divergent"] = adaptations.get("divergent", 0) + 1

        if metrics.consensus_density > 0.85:
            adaptations["debate"] = adaptations.get("debate", 0) - 1

        if metrics.epistemic_diversity < 0.3:
            adaptations["meta"] = adaptations.get("meta", 0) + 1

        if metrics.structural_stability < 0.5:
            adaptations["debate"] = adaptations.get("debate", 0) + 1

        return adaptations if adaptations else None

    # ========================================================================
    # PERSISTENCE D'ETAT
    # ========================================================================

    async def _save_state(self) -> None:
        """Sauvegarde l'etat actuel pour reprise eventuelle."""
        if not self._state:
            return

        self._state.last_checkpoint = datetime.now()

        try:
            # Stocker dans la DB (via update_esmm_run_status)
            await self.db.update_esmm_run_status(
                self._state.run_id,
                "running",
                current_cycle=self._state.current_cycle_type,
                current_iteration=self._state.current_iteration
            )
        except Exception as e:
            logger.warning(f"[ESMMOrchestrator] State save error: {e}")

    async def resume_from_state(self, run_id: int) -> ESMMRunResult:
        """
        Reprend un run depuis son etat sauvegarde.

        Args:
            run_id: ID du run a reprendre

        Returns:
            ESMMRunResult
        """
        logger.info(
            "[ESMMOrchestrator] Resuming run",
            extra={"run_id": run_id}
        )

        # Charger l'etat
        self._run_id = run_id
        self._start_time = datetime.now()

        # Reinitialiser les composants
        self.cycle_manager = await create_cycle_manager(
            db=self.db,
            run_id=run_id,
            models=self.config.models,
            min_consensus=self.config.min_consensus,
        )

        self.gap_detector = create_gap_detector(db=self.db, run_id=run_id)
        self.cochain_builder = create_cochain_builder(db=self.db, run_id=run_id)
        self.coverage_analyzer = CoverageAnalyzer(self.db)

        # Mettre a jour le statut
        await self.db.update_esmm_run_status(run_id, "running")

        # Reprendre l'execution
        await self.execute_cycles(run_id, resume=True)

        return await self.finalize_run(run_id)

    # ========================================================================
    # HELPERS
    # ========================================================================

    @staticmethod
    def _gap_signature(gaps: list) -> tuple:
        """Hashable signature of gaps for convergence detection."""
        import json
        parts = sorted(
            json.dumps({"t": g.gap_type.value, "d": g.details}, sort_keys=True, default=str)
            for g in gaps
        )
        return tuple(parts)

    def _check_timeout(self) -> bool:
        """Verifie si le timeout global est atteint."""
        if not self._start_time:
            return False

        elapsed_hours = (datetime.now() - self._start_time).total_seconds() / 3600
        return elapsed_hours >= self.config.max_duration_hours

    async def _compute_model_weights(self) -> Dict[str, float]:
        """
        R-2.1.1: Compute Brier-based weights for all configured models.

        Formula: weight = max(0.0, 1.0 - avg_brier_score)
        Cold start (no Brier data): weight = 1.0 (neutral)

        Returns:
            Dict {model_id: weight} for all models in self.config.models.
        """
        weights: Dict[str, float] = {}
        for model_id in self.config.models:
            brier = await self.db.get_model_brier_score(model_id)
            if brier is None:
                weights[model_id] = 1.0  # cold start
            else:
                weights[model_id] = max(0.0, 1.0 - brier["avg_brier_score"])
        return weights

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques accumulees."""
        return dict(self._stats)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def run_esmm_protocol(
    run_id: int,
    config: ESMMRunConfig,
    db: "ISpaceDB"
) -> ESMMRunResult:
    """
    Fonction helper pour executer le protocole ESMM en background.

    Args:
        run_id: ID du run (pre-cree)
        config: Configuration
        db: Instance DB

    Returns:
        ESMMRunResult
    """
    orchestrator = ESMMOrchestrator(db, config)
    orchestrator._run_id = run_id
    orchestrator._start_time = datetime.now()

    # Initialiser les composants
    orchestrator.cycle_manager = await create_cycle_manager(
        db=db,
        run_id=run_id,
        models=config.models,
        min_consensus=config.min_consensus,
    )
    orchestrator.gap_detector = create_gap_detector(db=db, run_id=run_id)
    orchestrator.cochain_builder = create_cochain_builder(db=db, run_id=run_id)
    orchestrator.coverage_analyzer = CoverageAnalyzer(db)

    # Initialiser l'etat
    orchestrator._state = ESMMRunState(
        run_id=run_id,
        current_cycle_type="",
        current_iteration=0,
        triplets_extracted=0,
        last_checkpoint=datetime.now()
    )

    # Executer
    await orchestrator.execute_cycles(run_id)
    return await orchestrator.finalize_run(run_id)


async def resume_esmm_protocol(
    run_id: int,
    db: "ISpaceDB"
) -> ESMMRunResult:
    """
    Reprend un run ESMM pause.

    Args:
        run_id: ID du run a reprendre
        db: Instance DB

    Returns:
        ESMMRunResult
    """
    orchestrator = ESMMOrchestrator(db)
    return await orchestrator.resume_from_state(run_id)
