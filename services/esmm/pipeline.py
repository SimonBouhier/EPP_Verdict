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

# Decidability penalties for VERIFY mode (applied before crystallization)
VERDICT_PENALTIES = {
    "SUPPORTED": 1.0,
    "CONTESTED": 0.65,
    "INSUFFICIENT_EVIDENCE": 0.45,
}
CLAIM_TYPE_PENALTIES = {
    "empirical": 1.0,
    "definitional": 0.90,
    "normative": 0.70,
    "speculative": 0.75,
    "security_audit": 1.0,  # ADR-014 — pas de pénalité (claim empirique vérifiable)
}


@dataclass
class PipelineConfig:
    """Configuration du pipeline."""
    min_consensus_for_attestation: float = 0.4   # En dessous = pas d'attestation
    min_confidence_for_injection: float = 0.5    # En dessous = pas d'injection graphe
    default_epistemic_type: str = "foundational"
    metrological_frame: Optional[str] = None
    cache_ttl_hours: float = 168.0    # ADR-013 : TTL cache (7 jours par défaut)
    use_cache: bool = True             # ADR-013 : désactivable pour les benchmarks


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
    from_cache: bool = False              # ADR-013 : True si retourné depuis graphe persistant
    cache_hit_hash: Optional[str] = None  # ADR-013 : claim_hash de l'attestation trouvée


def _get_default_models() -> List[str]:
    """Get default model list from config."""
    try:
        from services.config_loader import get_section
        esmm = get_section("esmm", {})
        # AUDIT[A8-001] 🔴→✅ FIXED Phase 4.4: esmm.models ajouté à config.yaml.
        return esmm.get("models", ["mistral:7b", "llama3.1:8b", "qwen2.5:7b"])
    except Exception:
        return ["mistral:7b", "llama3.1:8b", "qwen2.5:7b"]


async def _run_deterministic_pipeline(
    question: str,
    db: "ISpaceDB",
    esmm_config: "ESMMRunConfig",
    config: "PipelineConfig",
    start_time: float,
) -> "PipelineResult":
    """
    ADR-012 : chemin déterministe — bypass complet de l'ESMM.

    Interroge la source autoritaire via source_anchor_spec, construit une
    attestation avec consensus_meta.source_anchor_meta, stocke en DB.
    """
    from services.esmm.source_anchor_builder import build_source_anchor

    spec = esmm_config.source_anchor_spec
    errors: List[str] = []

    try:
        anchor_result = await build_source_anchor(spec)
    except Exception as exc:
        logger.error(f"[Pipeline] Deterministic source fetch failed: {exc}")
        return PipelineResult(
            run_id=0,
            question=question,
            attestations=[],
            triplets_extracted=0,
            triplets_attested=0,
            triplets_injected=0,
            duration_ms=(time.time() - start_time) * 1000,
            errors=[str(exc)],
        )

    # Construire consensus_meta déterministe (ADR-012 + ADR-010 compat)
    status = anchor_result.normalized_result["status"]
    score = float(anchor_result.normalized_result.get("score", 0.0))
    consensus_meta: Dict[str, Any] = {
        "methodology": {
            "consensus_method": "deterministic_source_v1",
            "esmm_invoked": False,
        },
        "source_anchor_meta": {
            "source_id": anchor_result.source_id,
            "source_version": anchor_result.source_version,
            "fetched_at": anchor_result.fetched_at,
            "is_fresh": anchor_result.is_fresh,
            "snapshot_id": anchor_result.snapshot_id,
        },
        "diagnostics": {
            "sources_checked": spec.min_sources,
            "concordant_sources": 1,
            "result": status,
        },
    }

    # Signature5D neutre — ESMM non invoqué (B2 FIX : zéros explicites)
    sig_neutre = Signature5D(
        agreement=0.0,
        semantic_consistency=0.0,
        centrality=0.0,
        stability=0.0,
        relation_diversity=0.0,
    )

    # Triplet synthétique — subject, frame, predicate (P1+P2 FIX ADR-012 audit)
    # P2 : Verra VCS utilise "serial"/"project_id", pas "name"
    subject = (
        spec.query.get("name")
        or spec.query.get("serial")
        or spec.query.get("project_id")
        or question
    )[:64]
    frame_id = spec.frame_id or config.metrological_frame
    # P1 : predicate = metric du frame (pas "sanctions_status" hardcodé)
    from services.solana.metrological_frame import PREDEFINED_FRAMES as _FRAMES
    _frame_factory = _FRAMES.get(frame_id)
    predicate = _frame_factory().metric if _frame_factory else "rwa_status"

    try:
        attestation = crystallize(
            subject=subject,
            predicate=predicate,
            object_=status,
            consensus_score=score,
            model_votes=[],
            signature_5d=sig_neutre,
            epistemic_type="deterministic",
            source_anchor=anchor_result.source_anchor,
            metrological_frame=frame_id,
            consensus_meta=consensus_meta,
            question=question,  # ADR-018 B4 fix: peuple la colonne pour get_attestations_by_question()
        )
    except Exception as exc:
        logger.error(f"[Pipeline] Deterministic crystallize failed: {exc}")
        return PipelineResult(
            run_id=0,
            question=question,
            attestations=[],
            triplets_extracted=0,
            triplets_attested=0,
            triplets_injected=0,
            duration_ms=(time.time() - start_time) * 1000,
            errors=[str(exc)],
        )

    # Stocker l'attestation
    try:
        await db.store_attestation(attestation.model_dump())
    except Exception as exc:
        logger.warning(f"[Pipeline] Deterministic store_attestation failed: {exc}")
        errors.append(str(exc))

    # Stocker le snapshot source (disponible après étape 4 — graceful if absent)
    _store_snap = getattr(db, "store_source_anchor_snapshot", None)
    if _store_snap is not None:
        import json as _json
        import hashlib as _hashlib
        query_hash = _hashlib.sha256(
            _json.dumps(spec.query, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        try:
            await _store_snap({
                "snapshot_id": anchor_result.snapshot_id,
                "source_id": anchor_result.source_id,
                "source_version": anchor_result.source_version,
                "query_hash": query_hash,
                "raw_response": _json.dumps(anchor_result.raw_response),
                "source_anchor": anchor_result.source_anchor,
                "fetched_at": anchor_result.fetched_at,
                "frame_id": spec.frame_id,
            })
        except Exception as exc:
            logger.warning(f"[Pipeline] store_source_anchor_snapshot failed: {exc}")

    return PipelineResult(
        run_id=0,
        question=question,
        attestations=[attestation],
        triplets_extracted=1,
        triplets_attested=1,
        triplets_injected=0,  # pas d'injection graphe pour claims déterministes
        duration_ms=(time.time() - start_time) * 1000,
        errors=errors,
    )


async def _lookup_existing_anchors(
    question: str,
    db: "ISpaceDB",
) -> list[dict]:
    """
    ADR-018 §2.2 : Cherche les attestations déterministes existantes pour une question.

    Lookup par `question` (PAS par claim_hash — cf. bug B1 : les deux chemins
    produisent des hashes distincts). Filtre post-query sur consensus_method.

    Returns:
        Liste de dicts {source_id, score, status, fetched_at, source_version}
    """
    import json as _json

    rows = await db.get_attestations_by_question(
        question=question,
        min_consensus=0.0,
    )

    anchors = []
    for row in rows:
        # Filtre : epistemic_type est dans le SELECT — consensus_meta ne l'est pas (B5)
        if row.get("epistemic_type") != "deterministic":
            continue

        # Récupérer consensus_meta depuis portable_json (absent du SELECT de get_attestations_by_question)
        meta = {}
        portable = row.get("portable_json")
        if portable:
            try:
                parsed = _json.loads(portable) if isinstance(portable, str) else portable
                raw_meta = parsed.get("consensus_meta")
                if isinstance(raw_meta, str):
                    meta = _json.loads(raw_meta)
                elif isinstance(raw_meta, dict):
                    meta = raw_meta
            except Exception:
                pass

        source_meta = meta.get("source_anchor_meta", {})
        diagnostics = meta.get("diagnostics", {})
        anchors.append({
            "source_id": source_meta.get("source_id", row.get("metrological_frame", "unknown")),
            "score": row.get("consensus_score", 0.0),
            "status": diagnostics.get("result", row.get("object", "unknown")),
            "fetched_at": source_meta.get("fetched_at", row.get("timestamp", 0)),
            "source_version": source_meta.get("source_version", "unknown"),
            "subject": row.get("subject", ""),
            "predicate": row.get("predicate", ""),
            "object": row.get("object", ""),
        })

    return anchors


def _format_anchor_context(anchors: list[dict]) -> str:
    """
    ADR-018 §2.3 : Formate les ancres déterministes pour injection dans le prompt LLM.

    Returns:
        Chaîne vide si pas d'ancres, sinon bloc [VERIFIED DATA ...].
    """
    if not anchors:
        return ""

    lines = ["[VERIFIED DATA — from deterministic sources, for context]"]
    for a in anchors:
        fact = ""
        if a.get("subject") and a.get("predicate") and a.get("object"):
            fact = f" verified that '{a['subject']}' {a['predicate']} = '{a['object']}'"
        lines.append(
            f"- Source: {a['source_id']}{fact}"
            f" (score: {a['score']}, status: {a['status']},"
            f" fetched: {a['fetched_at']}, version: {a['source_version']})"
        )
    lines.append(
        "[END VERIFIED DATA — you may contest these findings if your analysis disagrees]"
    )
    return "\n".join(lines)


async def _check_cache(
    question: str,
    db: "ISpaceDB",
    config: "PipelineConfig",
    esmm_config: Optional["ESMMRunConfig"],
) -> Optional["PipelineResult"]:
    """
    ADR-013 : Vérifie si une attestation récente existe pour ce claim.

    Retourne PipelineResult(from_cache=True) si hit, None si miss.
    Ne fait AUCUNE modification en base.
    """
    import time as _time
    from .attestation import EpistemicAttestation, Signature5D

    try:
        from services.config_loader import get_section
        cache_cfg = get_section("cache", {})
        min_tier_str = cache_cfg.get("min_tier_for_cache", "proposition")

        rows = await db.get_attestations_by_question(
            question=question,
            min_consensus=config.min_consensus_for_attestation,
        )

        if not rows:
            return None

        # Filtrer par TTL
        now = _time.time()
        ttl_seconds = config.cache_ttl_hours * 3600
        fresh_rows = [
            r for r in rows
            if (now - r.get("timestamp", 0)) < ttl_seconds
        ]

        if not fresh_rows:
            return None

        # Filtrer par tier minimum
        TIER_ORDER = {"sandbox": 0, "proposition": 1, "validated": 2, "verified": 3}
        min_tier_val = TIER_ORDER.get(min_tier_str, 1)
        eligible = [
            r for r in fresh_rows
            if TIER_ORDER.get(r.get("confidence_tier", "sandbox"), 0) >= min_tier_val
        ]

        if not eligible:
            return None

        best = eligible[0]

        # Reconstruire un EpistemicAttestation minimal depuis le dict DB
        cached_att = EpistemicAttestation(
            claim_hash=best["claim_hash"],
            subject=best["subject"],
            predicate=best["predicate"],
            object=best["object"],
            consensus_score=best.get("consensus_score", 0.0),
            models_consulted=best.get("models_consulted", 0),
            models_agreeing=best.get("models_agreeing", 0),
            model_votes=[],
            signature_5d=Signature5D(
                agreement=best.get("sig_agreement", 0.0),
                semantic_consistency=best.get("sig_semantic_consistency", 0.0),
                centrality=best.get("sig_centrality", 0.0),
                stability=best.get("sig_stability", 0.0),
                relation_diversity=best.get("sig_relation_diversity", 0.0),
            ),
            epistemic_type=best.get("epistemic_type", "foundational"),
            confidence_tier=best.get("confidence_tier", "sandbox"),
            metrological_frame=best.get("metrological_frame", ""),
            consensus_meta=best.get("consensus_meta", {}),
            timestamp=best.get("timestamp", 0),
        )

        return PipelineResult(
            run_id=best.get("run_id", 0),
            question=question,
            attestations=[cached_att],
            triplets_extracted=0,
            triplets_attested=1,
            triplets_injected=0,
            duration_ms=0.0,
            errors=[],
            from_cache=True,
            cache_hit_hash=best["claim_hash"],
        )

    except Exception as e:
        # Cache miss en cas d'erreur — ne pas bloquer le pipeline
        logger.warning("[Pipeline] Cache lookup failed (continuing): %s", e)
        return None


async def run_pipeline(
    question: str,
    db: "ISpaceDB",
    models: Optional[List[str]] = None,
    config: Optional[PipelineConfig] = None,
    metrological_frame: Optional[str] = None,
    providers: Optional[Dict] = None,
    model_weights: Optional[Dict[str, float]] = None,
    esmm_config: Optional["ESMMRunConfig"] = None,
    extra_system_context: Optional[str] = None,
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
        extra_system_context: Contexte système injecté en tête de question (ex. condition β)

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
    if extra_system_context:
        question = f"{extra_system_context}\n\n{question}"
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

        # ADR-013 : Cache-hit — vérifier si une attestation récente existe
        if config.use_cache and config.cache_ttl_hours > 0:
            cached = await _check_cache(
                question=question,
                db=db,
                config=config,
                esmm_config=esmm_config,
            )
            if cached is not None:
                logger.info("[Pipeline] Cache-hit: %s", cached.cache_hit_hash)
                return cached

        # ADR-012 : chemin déterministe — bypass ESMM
        if (
            esmm_config is not None
            and getattr(esmm_config, "claim_nature", "epistemic") == "deterministic"
        ):
            return await _run_deterministic_pipeline(
                question=question,
                db=db,
                esmm_config=esmm_config,
                config=config,
                start_time=start_time,
            )

        # ADR-018 Flywheel — VERIFY mode only (ADR-018 §4)
        is_verify = (
            esmm_config is not None
            and getattr(esmm_config, "input_mode", None) == "verify"
        )

        flywheel_injection = ""
        anchors: list[dict] = []
        flywheel_enabled = False  # initialisé hors try — évite NameError dans §3.6

        if is_verify:
            try:
                from services.config_loader import get_section
                flywheel_cfg = get_section("flywheel", {})
                flywheel_enabled = flywheel_cfg.get("enabled", True)
                if flywheel_enabled:
                    anchors = await _lookup_existing_anchors(question, db)
                    flywheel_injection = _format_anchor_context(anchors)
                    if flywheel_injection:
                        logger.info(
                            "[Pipeline] Flywheel: %d deterministic anchor(s) found",
                            len(anchors),
                        )
            except Exception as exc:
                logger.warning("[Pipeline] Flywheel lookup failed (continuing): %s", exc)

        # Extract triplets via real orchestrator (D1, D2, D3)
        extract_result = await _extract_triplets_from_question(
            question, db, models, run_logger, config.metrological_frame, providers,
            model_weights=model_weights, esmm_config=esmm_config,
            anchor_context=flywheel_injection,
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

        # ADR-018: Flywheel traceability — variables flywheel_enabled/anchors toujours en scope
        if consensus_meta:
            consensus_meta.setdefault("methodology", {})["flywheel"] = {
                "enabled": flywheel_enabled,
                "anchors_found": len(anchors),
                "sources_injected": [a["source_id"] for a in anchors],
            }

        # Update run_logger with real run_id
        run_logger = RunLogger(run_id=run_id, question=question)

        # COMMUNITY_DECISION_REQUIRED: The treatment of CONTESTED consensus
        # (ambiguity_detected=True) is deliberately left open. Possible future
        # policies include: cap confidence_tier, reduce diversity_bonus, require
        # additional debate cycles, or flag for human review. This decision
        # should be made by the open-source community, not by the founding team.
        # See ADR-009 (pending) for context.

        # Fix B: Extract claim_type from consensus triplet, filter before crystallization
        verify_claim_type = "empirical"
        if esmm_config and getattr(esmm_config, "input_mode", None) == "verify":
            for t in extracted_triplets:
                if t.get("predicate") == "claim_type":
                    verify_claim_type = t["object"]
                    break
            extracted_triplets = [t for t in extracted_triplets if t.get("predicate") != "claim_type"]
            if consensus_meta and consensus_meta.get("verify"):
                consensus_meta["verify"]["claim_type"] = verify_claim_type

        # Fix 5 (Lot A) : override claim_type pour les audits de sécurité
        if config.default_epistemic_type == "security_audit":
            verify_claim_type = "security_audit"
            # Fix 5 corrigé : propager dans consensus_meta (construit avant cet override)
            if consensus_meta and "verify" in consensus_meta:
                consensus_meta["verify"]["claim_type"] = "security_audit"

        # ADR-018: Synthesize verdict from raw model triplets when
        # flywheel-induced split prevents consensus verdict formation
        if (esmm_config
                and getattr(esmm_config, "input_mode", None) == "verify"
                and not any(t.get("predicate") == "verdict" for t in extracted_triplets)
                and esmm_result is not None
                and flywheel_injection):

            raw = getattr(esmm_result, "raw_model_triplets", {})
            verdict_votes = []
            for model_id, triplets in raw.items():
                for t in triplets:
                    td = t if isinstance(t, dict) else vars(t)
                    rel = td.get("predicate") or td.get("relation", "")
                    if rel == "verdict":
                        verdict_votes.append({
                            "model_id": model_id,
                            "verdict": td.get("object", "CONTESTED"),
                            "confidence": float(td.get("confidence", 0.5)),
                        })
                        break  # un verdict par modèle

            if verdict_votes:
                # Score pondéré par confidence
                total_conf = sum(v["confidence"] for v in verdict_votes) or 1.0
                weighted = {}
                for v in verdict_votes:
                    weighted[v["verdict"]] = weighted.get(v["verdict"], 0.0) + v["confidence"]

                best_verdict = max(weighted, key=weighted.get)
                best_score = round(weighted[best_verdict] / total_conf, 4)

                extracted_triplets.append({
                    "subject": question[:64],
                    "predicate": "verdict",
                    "object": best_verdict,
                    "consensus_score": best_score,
                    "votes": [
                        {"model_id": v["model_id"], "provider_id": v["model_id"],
                         "agreed": v["verdict"] == best_verdict,
                         "confidence": v["confidence"]}
                        for v in verdict_votes
                    ],
                    "contributing_models": [v["model_id"] for v in verdict_votes],
                })
                logger.info(
                    "[Pipeline] Flywheel verdict synthesis: %s (%.2f) from %d models",
                    best_verdict, best_score, len(verdict_votes),
                )

        # F5: dedup within a single run. Cross-run dedup requires DB lookup
        # on attestations.claim_hash — deferred to Phase 2 cleanup.
        seen_hashes = set()
        _pending: list = []  # (attestation, triplet) — storage deferred until consensus_meta enriched
        for triplet in extracted_triplets:
            # Fix 1 (Lot A) : subject_override pour les audits (remplace le prompt brut)
            effective_subject = (
                esmm_config.subject_override
                if esmm_config and getattr(esmm_config, "subject_override", None)
                else triplet["subject"]
            )
            h = compute_claim_hash(
                effective_subject, triplet["predicate"], triplet["object"],
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

            # Fix B: Decidability penalty for VERIFY verdict triplets
            actual_score = triplet["consensus_score"]
            if esmm_config and getattr(esmm_config, "input_mode", None) == "verify":
                if triplet.get("predicate") == "verdict":
                    v_penalty = VERDICT_PENALTIES.get(triplet["object"], 0.65)
                    t_penalty = CLAIM_TYPE_PENALTIES.get(verify_claim_type, 1.0)
                    actual_score = round(actual_score * v_penalty * t_penalty, 4)

            attestation = crystallize(
                subject=effective_subject,
                predicate=triplet["predicate"],
                object_=triplet["object"],
                consensus_score=actual_score,
                model_votes=model_votes,
                signature_5d=Signature5D(**triplet.get("signature_5d", {
                    "agreement": triplet["consensus_score"],
                    "semantic_consistency": 0.5,
                    "centrality": 0.5,
                    "stability": 0.5,
                    "relation_diversity": len(families) / max(len(model_votes), 1),
                })),
                epistemic_type=(
                    config.default_epistemic_type
                    if config.default_epistemic_type != "foundational"
                    else triplet.get("epistemic_type", "foundational")
                ),
                run_id=run_id,
                question=question,
                metrological_frame=config.metrological_frame,
                architecture_families=len(families),
                consensus_meta=consensus_meta,
            )

            # Logger
            run_logger.crystallization(
                claim_hash=attestation.claim_hash,
                consensus_score=attestation.consensus_score,
                confidence_tier=attestation.confidence_tier,
            )

            attestations.append(attestation)
            _pending.append((attestation, triplet))  # defer storage until consensus_meta enriched

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
                # Fix B4: Decidability traceability
                raw_score = triplet["consensus_score"] if triplet else 0.0
                consensus_meta["verify"]["raw_consensus_score"] = round(raw_score, 4)
                consensus_meta["verify"]["decidability_penalty"] = {
                    "verdict_penalty": VERDICT_PENALTIES.get(best.object, 0.65),
                    "claim_type_penalty": CLAIM_TYPE_PENALTIES.get(verify_claim_type, 1.0),
                    "claim_type": verify_claim_type,
                }
                consensus_meta["verify"]["adjusted_consensus_score"] = round(best.consensus_score, 4)

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

        # Passe 2: store + inject with enriched consensus_meta (final_verdict now populated)
        for _att, _triplet in _pending:
            # AUDIT[A3-005] 🟡 FRAGILE: store_attestation() attend un dict — conversion implicite via model_dump().
            _att_dict = _att.model_dump()
            _att_dict["portable_json"] = _att.to_portable_json()
            await db.store_attestation(_att_dict)

            # Hook post-cristallisation (D8)
            try:
                from .post_crystallization import post_crystallization_hook
                await post_crystallization_hook(_att, db)
            # AUDIT[A2-011] 🟡 FRAGILE: post_crystallization_hook failure ignorée — attestation stockée quand même.
            except Exception as e:
                logger.warning(f"Post-crystallization hook failed: {e}")

            # Injecter dans le graphe si confiance suffisante
            if _triplet["consensus_score"] >= config.min_confidence_for_injection:
                try:
                    await _inject_triplet_to_graph(
                        db, _triplet["subject"], _triplet["predicate"], _triplet["object"],
                        confidence=_triplet["consensus_score"],
                        model_source=f"esmm_run_{run_id}",
                    )
                    triplets_injected += 1
                except Exception as e:
                    # AUDIT[A2-010,A9-001] 🟡 FRAGILE: erreurs accumulées sans arrêt du pipeline.
                    errors.append(f"Injection failed for {_triplet['subject']}: {e}")

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
        "fingerprint_merges": getattr(esmm_result, "fingerprint_merges", None),
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
    anchor_context: str = "",  # ADR-018: flywheel injection
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

    # Dual-mode: auto-detect VERIFY claims only if caller hasn't already set input_mode
    if getattr(esmm_config, "input_mode", None) != "verify":
        input_mode = classify_input(question)
        if input_mode == InputType.VERIFY:
            esmm_config.input_mode = "verify"
            esmm_config.original_claim = question
            logger.info(f"Auto-detected VERIFY mode for claim: {question[:80]}")

    # ADR-018: Frontière 1 — passer anchor_context à l'orchestrateur via ESMMRunConfig
    if anchor_context:
        esmm_config.anchor_context = anchor_context

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
