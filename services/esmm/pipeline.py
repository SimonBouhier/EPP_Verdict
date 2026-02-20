"""
ESMM Pipeline — Pont entre l'orchestrateur et la cristallisation.

Responsabilites :
1. Lancer un run ESMM via l'orchestrateur
2. Collecter les triplets extraits et leurs scores de consensus
3. Cristalliser chaque triplet valide en EpistemicAttestation
4. Stocker les attestations en DB
5. Enrichir le graphe avec les triplets valides

Ce module est le SEUL pont entre orchestrator.py et attestation.py.
L'orchestrateur ne connait PAS le module attestation.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional, Dict, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass

from .attestation import (
    EpistemicAttestation,
    Signature5D,
    ModelVote,
    crystallize,
    compute_claim_hash,
)
from .run_logger import RunLogger

if TYPE_CHECKING:
    from database.engine import ISpaceDB
    from .orchestrator import ESMMRunConfig

logger = logging.getLogger("esmm.pipeline")

# Phase 4.5.4 — Input validation constants
MAX_QUESTION_LENGTH = 5000
MAX_FRAME_LENGTH = 2000


@dataclass
class PipelineConfig:
    """Configuration du pipeline."""
    min_consensus_for_attestation: float = 0.4   # En dessous = pas d'attestation
    min_confidence_for_injection: float = 0.5    # En dessous = pas d'injection graphe
    default_epistemic_type: str = "foundational"
    metrological_frame: Optional[str] = None


@dataclass
class PipelineResult:
    """Resultat d'un run complet du pipeline."""
    run_id: int
    question: str
    attestations: List[EpistemicAttestation]
    triplets_extracted: int
    triplets_attested: int
    triplets_injected: int
    duration_ms: float
    errors: List[str]


def _get_default_models() -> List[str]:
    """Get default model list from config."""
    try:
        from services.config_loader import get_section
        esmm = get_section("esmm", {})
        # AUDIT[A8-001] 🔴→✅ FIXED Phase 4.4: esmm.models ajouté à config.yaml.
        return esmm.get("models", ["mistral:7b", "llama3.1:8b", "qwen2.5:7b"])
    except Exception:
        return ["mistral:7b", "llama3.1:8b", "qwen2.5:7b"]


async def run_pipeline(
    question: str,
    db: "ISpaceDB",
    models: Optional[List[str]] = None,
    config: Optional[PipelineConfig] = None,
    metrological_frame: Optional[str] = None,
    providers: Optional[Dict] = None,
    model_weights: Optional[Dict[str, float]] = None,
    esmm_config: Optional["ESMMRunConfig"] = None,
) -> PipelineResult:
    """
    Execute le pipeline complet : question -> ESMM -> attestations -> graphe.

    D1: L'orchestrateur possede le run — le pipeline ne cree PAS de run ESMM.

    Args:
        question: Question soumise au pipeline
        db: Instance ISpaceDB
        models: Liste des modeles a utiliser (None = config default)
        config: Configuration du pipeline
        metrological_frame: Frame metrologique applicable
        providers: Dict {provider_id: ModelProvider} pre-configured (optional)

    Returns:
        PipelineResult avec les attestations produites
    """
    # Phase 4.5.4 — Input validation
    import re as _re
    if not question or not isinstance(question, str):
        raise ValueError("question must be a non-empty string")
    if len(question) > MAX_QUESTION_LENGTH:
        raise ValueError(f"question exceeds {MAX_QUESTION_LENGTH} characters")
    # Strip control characters (keep newlines and tabs)
    question = _re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", question)
    if metrological_frame and len(metrological_frame) > MAX_FRAME_LENGTH:
        raise ValueError(f"metrological_frame exceeds {MAX_FRAME_LENGTH} characters")

    if config is None:
        config = PipelineConfig()
    if metrological_frame:
        config.metrological_frame = metrological_frame

    start_time = time.time()
    errors = []
    attestations = []
    triplets_injected = 0
    extracted_triplets = []
    run_id = 0

    # D1: Pas de create_esmm_run ici — l'orchestrateur possede le run
    run_logger = RunLogger(run_id=0, question=question)

    try:
        run_logger.phase_start("pipeline", question=question)

        # Extract triplets via real orchestrator (D1, D2, D3)
        extract_result = await _extract_triplets_from_question(
            question, db, models, run_logger, config.metrological_frame, providers,
            model_weights=model_weights, esmm_config=esmm_config,
        )

        # Backward compat: mocks may return 2-tuple, real code returns 4-tuple
        if len(extract_result) == 4:
            extracted_triplets, run_id, esmm_result, esmm_config = extract_result
        elif len(extract_result) == 3:
            extracted_triplets, run_id, esmm_result = extract_result
        else:
            extracted_triplets, run_id = extract_result
            esmm_result = None

        # ADR-010: Build consensus_meta from ESMMRunResult + config
        consensus_meta = await _build_consensus_meta(
            esmm_config, esmm_result, model_weights, providers=providers
        )

        # Update run_logger with real run_id
        run_logger = RunLogger(run_id=run_id, question=question)

        # COMMUNITY_DECISION_REQUIRED: The treatment of CONTESTED consensus
        # (ambiguity_detected=True) is deliberately left open. Possible future
        # policies include: cap confidence_tier, reduce diversity_bonus, require
        # additional debate cycles, or flag for human review. This decision
        # should be made by the open-source community, not by the founding team.
        # See ADR-009 (pending) for context.

        # F5: dedup within a single run. Cross-run dedup requires DB lookup
        # on attestations.claim_hash — deferred to Phase 2 cleanup.
        seen_hashes = set()
        for triplet in extracted_triplets:
            h = compute_claim_hash(
                triplet["subject"], triplet["predicate"], triplet["object"],
                metrological_frame=config.metrological_frame,
            )
            if h in seen_hashes:
                logger.info(
                    "Skipping duplicate triplet claim_hash=%s subject=%s",
                    h[:16], triplet["subject"],
                )
                continue
            seen_hashes.add(h)

            if triplet["consensus_score"] < config.min_consensus_for_attestation:
                continue

            # Construire les ModelVote depuis les donnees du triplet
            model_votes = [
                ModelVote(
                    model_id=v["model_id"],
                    provider_id=v["provider_id"],
                    agreed=v["agreed"],
                    confidence=v["confidence"],
                )
                for v in triplet.get("votes", [])
            ]

            # Compter les familles d'architecture
            families = set(
                v.get("architecture_family", "unknown")
                for v in triplet.get("votes", [])
            )

            attestation = crystallize(
                subject=triplet["subject"],
                predicate=triplet["predicate"],
                object_=triplet["object"],
                consensus_score=triplet["consensus_score"],
                model_votes=model_votes,
                signature_5d=Signature5D(**triplet.get("signature_5d", {
                    "agreement": triplet["consensus_score"],
                    "semantic_consistency": 0.5,
                    "centrality": 0.5,
                    "stability": 0.5,
                    "relation_diversity": len(families) / max(len(model_votes), 1),
                })),
                epistemic_type=triplet.get("epistemic_type", config.default_epistemic_type),
                run_id=run_id,
                question=question,
                metrological_frame=config.metrological_frame,
                architecture_families=len(families),
                consensus_meta=consensus_meta,
            )

            # Stocker en DB
            attestation_dict = attestation.model_dump()
            attestation_dict["portable_json"] = attestation.to_portable_json()
            # AUDIT[A3-005] 🟡 FRAGILE: store_attestation() attend un dict — conversion implicite via model_dump().
            await db.store_attestation(attestation_dict)

            # Hook post-cristallisation (D8)
            try:
                from .post_crystallization import post_crystallization_hook
                await post_crystallization_hook(attestation, db)
            # AUDIT[A2-011] 🟡 FRAGILE: post_crystallization_hook failure ignorée — attestation stockée quand même.
            except Exception as e:
                logger.warning(f"Post-crystallization hook failed: {e}")

            # Logger
            run_logger.crystallization(
                claim_hash=attestation.claim_hash,
                consensus_score=attestation.consensus_score,
                confidence_tier=attestation.confidence_tier,
            )

            attestations.append(attestation)

            # Injecter dans le graphe si confiance suffisante
            if triplet["consensus_score"] >= config.min_confidence_for_injection:
                try:
                    await _inject_triplet_to_graph(
                        db, triplet["subject"], triplet["predicate"], triplet["object"],
                        confidence=triplet["consensus_score"],
                        model_source=f"esmm_run_{run_id}",
                    )
                    triplets_injected += 1
                except Exception as e:
                    # AUDIT[A2-010,A9-001] 🟡 FRAGILE: erreurs accumulées sans arrêt du pipeline.
                    errors.append(f"Injection failed for {triplet['subject']}: {e}")

        # P1: Enrich verify section with final verdict post-crystallization
        if consensus_meta and consensus_meta.get("verify") and attestations:
            verdict_attestations = [
                a for a in attestations if a.predicate == "verdict"
            ]
            if verdict_attestations:
                best = max(verdict_attestations, key=lambda a: a.consensus_score)
                consensus_meta["verify"]["final_verdict"] = best.object
                consensus_meta["verify"]["verdict_confidence"] = best.consensus_score
                consensus_meta["verify"]["model_verdicts"] = {
                    v.model_id: {"agreed": v.agreed, "confidence": v.confidence}
                    for a in verdict_attestations for v in a.model_votes
                }

        # P2: Preserve sub-consensus evidence in verify section (ADR-010)
        if consensus_meta and consensus_meta.get("verify"):
            sub_consensus_evidence = []
            for triplet in extracted_triplets:
                if triplet["consensus_score"] < config.min_consensus_for_attestation:
                    sub_consensus_evidence.append({
                        "subject": triplet["subject"],
                        "predicate": triplet["predicate"],
                        "object": triplet["object"],
                        "consensus_score": round(triplet["consensus_score"], 4),
                        "models": triplet.get("contributing_models", []),
                    })
            if sub_consensus_evidence:
                consensus_meta["verify"]["evidence_corpus"] = sub_consensus_evidence[:20]
                consensus_meta["verify"]["evidence_total"] = len(sub_consensus_evidence)

        run_logger.phase_end("pipeline", attestations=len(attestations))

    except Exception as e:
        # AUDIT[A2-010,A9-001] 🟡 FRAGILE: erreurs accumulées sans arrêt du pipeline.
        errors.append(f"Pipeline error: {e}")
        run_logger.error("pipeline", str(e))
        logger.exception(f"Pipeline failed: {e}")
        run_id = 0

    duration_ms = (time.time() - start_time) * 1000

    return PipelineResult(
        run_id=run_id,
        question=question,
        attestations=attestations,
        triplets_extracted=len(extracted_triplets),
        triplets_attested=len(attestations),
        triplets_injected=triplets_injected,
        duration_ms=round(duration_ms, 1),
        errors=errors,
    )


async def _build_consensus_meta(
    esmm_config: Optional[Any],
    esmm_result: Optional[Any],
    model_weights: Optional[Dict[str, float]],
    providers: Optional[Dict] = None,
) -> Optional[Dict[str, Any]]:
    """
    ADR-010: Assemble consensus_meta from ESMMRunConfig + ESMMRunResult.

    Returns None if no ESMMRunResult is available (e.g. mocked extraction).
    """
    if esmm_result is None:
        return None

    from .consensus_engine import SEMANTIC_MERGE_THRESHOLD

    # Section 1: methodology
    methodology = {
        "consensus_method": "hash_exact_v2+semantic_merge_v1",
        "normalization_version": "normalize_triplet_v2_synonyms",
        "weighting_strategy": "brier_weighted" if model_weights else "uniform",
        "merge_threshold": SEMANTIC_MERGE_THRESHOLD,
        "min_consensus": getattr(esmm_config, "min_consensus", 0.5) if esmm_config else 0.5,
    }

    # Section 2: conditions
    models_info = {}
    if model_weights:
        for model_id, weight in model_weights.items():
            models_info[model_id] = {"resolved_version": None, "weight": weight}
    elif esmm_config and hasattr(esmm_config, "models"):
        for model_id in esmm_config.models:
            models_info[model_id] = {"resolved_version": None, "weight": 1.0}

    # ADR-010 / SP-7: Resolve model versions via providers (best effort)
    if providers and models_info:
        for provider in providers.values():
            if hasattr(provider, "resolve_model_version"):
                for model_id in list(models_info.keys()):
                    try:
                        version = await provider.resolve_model_version(model_id)
                        if version:
                            models_info[model_id]["resolved_version"] = version
                    except Exception:
                        pass  # Best effort — ADR-010 §2

    conditions = {
        "models": models_info,
        "embedding_model": None,
        "cycles_completed": getattr(esmm_result, "cycles_completed", 0),
        "cycle_sequence": list(getattr(esmm_config, "cycle_sequence", [])) if esmm_config else [],
    }

    # Section 3: diagnostics
    diagnostics = {
        "vote_entropy": getattr(esmm_result, "vote_entropy", 0.0),
        "semantic_dispersion": getattr(esmm_result, "semantic_dispersion", None),
        "ambiguity_detected": False,
        "variations": [],
        "triplets_before_consensus": getattr(esmm_result, "triplets_before_consensus", 0),
        "triplets_after_consensus": getattr(esmm_result, "triplets_after_consensus", 0),
    }

    meta = {
        "methodology": methodology,
        "conditions": conditions,
        "diagnostics": diagnostics,
    }

    # Dual-mode: add verify section if applicable
    if esmm_config and getattr(esmm_config, "input_mode", "explore") == "verify":
        methodology["pipeline_mode"] = "verify"
        meta["verify"] = {
            "original_claim": getattr(esmm_config, "original_claim", None),
            "final_verdict": None,       # Set downstream after consensus
            "verdict_confidence": None,   # Set downstream after consensus
            "model_verdicts": {},         # Set downstream after consensus
        }
    else:
        methodology["pipeline_mode"] = "explore"

    # ADR-011-v2: reconciliation metadata
    reconciliation = getattr(esmm_result, "reconciliation_meta", None)
    if reconciliation:
        meta["reconciliation"] = reconciliation
        if reconciliation.get("method") == "semantic_fingerprinting":
            methodology["consensus_method"] = "hash_exact_v2+fingerprint_v1+semantic_merge_v1"

    return meta


async def _extract_triplets_from_question(
    question: str,
    db: "ISpaceDB",
    models: Optional[List[str]],
    run_logger: RunLogger,
    metrological_frame: Optional[str] = None,
    providers: Optional[Dict] = None,
    model_weights: Optional[Dict[str, float]] = None,
    esmm_config: Optional["ESMMRunConfig"] = None,
) -> Tuple[List[Dict[str, Any]], int, Any]:
    """
    Extrait les triplets via l'orchestrateur ESMM complet.

    D1: L'orchestrateur cree et possede le run.
    D2: L'orchestrateur collecte et retourne les ConsensusTriplet.
    D4: L'adaptateur convertit ConsensusTriplet -> dict pipeline.
    D7: Le graphe est seede depuis la question si vide.

    Returns:
        Tuple (triplets adaptes en dicts, run_id, ESMMRunResult)
    """
    from .question_seeder import seed_graph_from_question, classify_input, InputType
    from .triplet_adapter import adapt_all
    from .orchestrator import ESMMOrchestrator, ESMMRunConfig

    # D7: Seed le graphe si vide
    seeded = await seed_graph_from_question(db, question)
    if seeded > 0:
        logger.info(f"Seeded graph with {seeded} concepts from question")

    # D1, D3: Configure et lance l'orchestrateur complet
    effective_models = models or _get_default_models()
    if esmm_config is None:
        esmm_config = ESMMRunConfig(models=effective_models)
    elif not esmm_config.models:
        esmm_config.models = effective_models

    # Dual-mode: auto-detect VERIFY claims
    input_mode = classify_input(question)
    if input_mode == InputType.VERIFY:
        esmm_config.input_mode = "verify"
        esmm_config.original_claim = question
        logger.info(f"Auto-detected VERIFY mode for claim: {question[:80]}")

    orchestrator = ESMMOrchestrator(db=db, config=esmm_config, providers=providers)

    run_logger.phase_start("esmm_orchestrator", question=question)

    # The orchestrator flow: initialize -> execute -> reconcile -> finalize
    run_id = await orchestrator.initialize_run()
    await orchestrator.execute_cycles(run_id, model_weights=model_weights)
    await orchestrator.reconcile()  # ADR-011-v2: Semantic Fingerprinting
    result = await orchestrator.finalize_run(run_id)

    run_logger.phase_end(
        "esmm_orchestrator",
        cycles=result.cycles_completed,
        triplets=result.total_triplets,
    )

    # D4: Adapt ConsensusTriplet -> dict pipeline
    adapted = adapt_all(result.consensus_triplets)

    return adapted, result.run_id, result, esmm_config


async def _inject_triplet_to_graph(
    db: "ISpaceDB",
    subject: str,
    predicate: str,
    object_: str,
    confidence: float,
    model_source: str,
) -> None:
    """Injecte un triplet atteste dans le graphe de connaissances."""
    # Resoudre les concepts (canonicalisation)
    subject_canonical = await db.resolve_concept(subject)
    object_canonical = await db.resolve_concept(object_)

    # Ajouter les concepts s'ils n'existent pas
    existing = await db.get_concept(subject_canonical)
    if not existing:
        await db.add_concept(
            concept_id=subject_canonical,
            source="extracted",
            first_seen_model=model_source,
        )

    existing = await db.get_concept(object_canonical)
    if not existing:
        await db.add_concept(
            concept_id=object_canonical,
            source="extracted",
            first_seen_model=model_source,
        )

    # Ajouter la relation
    # AUDIT[A3-008] 🟡 FRAGILE: format du dict doit matcher exactement — pas de validation intermédiaire.
    await db.upsert_relations_batch([{
        "source": subject_canonical,
        "target": object_canonical,
        "weight": confidence,
        "relation_type": predicate,
        "confidence": confidence,
        "model_source": model_source,
    }])
