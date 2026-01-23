"""
LYRA-ACE - GRAPH MUTATION API
=============================

Endpoints pour les opérations sur le graphe sémantique.

Inclut les endpoints ESMM Phase 1:
- POST /graph/populate - Population depuis topics.txt
- POST /graph/generate-relations - Génération par similarité
- POST /graph/inject-seed - Injection graine ESMM
- GET /graph/phase1-stats - Statistiques Phase 1
- GET /graph/similar/{concept_id} - Recherche de concepts similaires

ESMM Phase 2:
- POST /graph/extract-triplets - Extraction multi-modèles avec consensus
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional

from app.models import (
    GraphDeltaRequest, GraphDeltaResponse, KappaResponse, ErrorResponse,
    PopulateRequest, PopulateResponse,
    GenerateRelationsRequest, GenerateRelationsResponse,
    InjectSeedRequest, InjectSeedResponse,
    SimilarConceptsResponse, Phase1StatsResponse,
    TripletExtractionRequest, TripletExtractionResponse, ExtractedTripletResponse,
    # Phase 3 models
    ESMMRunRequest, ESMMRunStatusResponse, ESMMRunResultResponse,
    KnowledgeGapResponse, CoverageMetricsResponse
)
from database import (
    get_db, ISpaceDB, GraphDelta, DeltaOperation,
    DeltaValidationError, MutationLimitExceededError
)
from services.esmm import (
    GraphPopulator, RelationGenerator, SeedInjector,
    TripletExtractor, get_triplet_extractor, close_triplet_extractor
)


router = APIRouter(prefix="/graph", tags=["graph"])


async def get_database() -> ISpaceDB:
    """Dependency: Database instance."""
    return await get_db()


@router.post("/delta", response_model=GraphDeltaResponse)
async def apply_delta(
    request: GraphDeltaRequest,
    session_id: Optional[str] = Query(None, description="Session ID for audit"),
    kappa_alpha: float = Query(0.5, ge=0.0, le=1.0, description="Kappa hybrid coefficient"),
    db: ISpaceDB = Depends(get_database)
):
    """
    Applique un delta au graphe sémantique.

    Le delta est enregistré dans l'historique pour permettre le rollback.

    Example:
        POST /graph/delta?session_id=abc-123&kappa_alpha=0.5
        {
            "operation": "add_edge",
            "source": "entropy",
            "target": "chaos",
            "weight": 0.75,
            "confidence": 0.9
        }
    """
    try:
        delta = GraphDelta(
            operation=DeltaOperation(request.operation),
            source=request.source,
            target=request.target,
            weight=request.weight,
            confidence=request.confidence,
            model_source=request.model_source,
            reason=request.reason
        )

        result = await db.apply_delta(delta, session_id, kappa_alpha)

        return GraphDeltaResponse(
            delta_id=result.delta_id,
            operation=result.operation.value,
            source=result.source,
            target=result.target,
            old_weight=result.old_weight,
            new_weight=result.weight,
            old_kappa=result.old_kappa,
            new_kappa=result.new_kappa,
            applied_at=result.applied_at
        )

    except DeltaValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except MutationLimitExceededError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/kappa/{source}/{target}", response_model=KappaResponse)
async def compute_kappa(
    source: str,
    target: str,
    alpha: float = Query(0.5, ge=0.0, le=1.0, description="Hybrid coefficient"),
    store_history: bool = Query(False, description="Store in kappa_history table"),
    db: ISpaceDB = Depends(get_database)
):
    """
    Calcule la courbure κ hybride pour une arête.

    Formules:
    - Ollivier: κ_o = 1/deg(u) + 1/deg(v) - 2/w
    - Jaccard: κ_j = |N(u) ∩ N(v)| / |N(u) ∪ N(v)|
    - Hybride: κ = α * κ_o_norm + (1-α) * κ_j

    Example:
        GET /graph/kappa/entropy/information?alpha=0.6
    """
    result = await db.compute_kappa_live(source, target, alpha, store_history)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Edge {source} -> {target} not found"
        )

    return KappaResponse(
        source=source,
        target=target,
        kappa_ollivier=result["kappa_ollivier"],
        kappa_jaccard=result["kappa_jaccard"],
        kappa_hybrid=result["kappa_hybrid"],
        alpha=result["alpha"]
    )


@router.get("/deltas")
async def get_delta_history(
    session_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    include_rolled_back: bool = Query(False),
    db: ISpaceDB = Depends(get_database)
):
    """
    Récupère l'historique des deltas.

    Example:
        GET /graph/deltas?session_id=abc-123&limit=50
    """
    deltas = await db.get_delta_history(session_id, limit, include_rolled_back)
    return {"deltas": deltas, "count": len(deltas)}


@router.post("/rollback")
async def rollback_deltas(
    session_id: str = Query(..., description="Session ID"),
    to_timestamp: Optional[float] = Query(None, description="Rollback to this timestamp"),
    delta_ids: Optional[List[int]] = Query(None, description="Specific delta IDs to rollback"),
    db: ISpaceDB = Depends(get_database)
):
    """
    Annule des deltas (restaure l'état précédent).

    Example:
        POST /graph/rollback?session_id=abc-123&to_timestamp=1704067200
    """
    if not to_timestamp and not delta_ids:
        raise HTTPException(
            status_code=400,
            detail="Either to_timestamp or delta_ids must be provided"
        )

    count = await db.rollback_deltas(session_id, to_timestamp, delta_ids)
    return {"rolled_back": count, "session_id": session_id}


@router.get("/stats")
async def get_mutation_stats(db: ISpaceDB = Depends(get_database)):
    """
    Statistiques sur les mutations du graphe.

    Example:
        GET /graph/stats
    """
    stats = await db.get_graph_mutation_stats()
    return stats


# ============================================================================
# ESMM PHASE 1 ENDPOINTS
# ============================================================================

@router.post("/populate", response_model=PopulateResponse)
async def populate_graph(
    request: PopulateRequest,
    db: ISpaceDB = Depends(get_database)
):
    """
    Charge les concepts depuis topics.txt et génère leurs embeddings.

    Cette opération peut prendre plusieurs minutes selon le nombre de concepts
    et la génération d'embeddings.

    Example:
        POST /graph/populate
        {
            "source_file": "data/topics.txt",
            "generate_embeddings": true,
            "batch_size": 50,
            "skip_existing": true
        }

    Returns:
        - concepts_loaded: Nombre de concepts chargés
        - concepts_skipped: Nombre de concepts ignorés (existants)
        - embeddings_generated: Nombre d'embeddings générés
        - duration_ms: Durée de l'opération
    """
    try:
        populator = GraphPopulator(db, batch_size=request.batch_size)

        result = await populator.populate_from_file(
            file_path=request.source_file,
            generate_embeddings=request.generate_embeddings,
            skip_existing=request.skip_existing
        )

        return PopulateResponse(
            concepts_loaded=result.concepts_loaded,
            concepts_skipped=result.concepts_skipped,
            embeddings_generated=result.embeddings_generated,
            embeddings_failed=result.embeddings_failed,
            duplicates_found=result.duplicates_found,
            duration_ms=result.duration_ms,
            errors=result.errors
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Population failed: {str(e)}")


@router.post("/generate-relations", response_model=GenerateRelationsResponse)
async def generate_relations(
    request: GenerateRelationsRequest,
    db: ISpaceDB = Depends(get_database)
):
    """
    Génère des relations basées sur la similarité des embeddings.

    Pour chaque concept, trouve les concepts les plus similaires et crée
    des arêtes avec un poids égal à la similarité cosinus.

    Example:
        POST /graph/generate-relations
        {
            "similarity_threshold": 0.6,
            "confidence": 0.7,
            "max_neighbors": 20
        }

    Returns:
        - relations_created: Nombre de relations créées
        - concepts_processed: Nombre de concepts traités
        - average_similarity: Similarité moyenne des relations créées
    """
    try:
        generator = RelationGenerator(db, max_neighbors=request.max_neighbors)

        result = await generator.generate_initial_relations(
            similarity_threshold=request.similarity_threshold,
            confidence=request.confidence,
            limit_concepts=request.limit_concepts
        )

        return GenerateRelationsResponse(
            relations_created=result.relations_created,
            relations_skipped=result.relations_skipped,
            concepts_processed=result.concepts_processed,
            average_similarity=result.average_similarity,
            duration_ms=result.duration_ms,
            errors=result.errors
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Relation generation failed: {str(e)}")


@router.post("/inject-seed", response_model=InjectSeedResponse)
async def inject_seed(
    request: InjectSeedRequest,
    db: ISpaceDB = Depends(get_database)
):
    """
    Injecte la graine sémantique ESMM dans le graphe.

    La graine contient des paires dialectiques fondamentales qui structurent
    l'espace sémantique (cause/effet, théorie/pratique, etc.).

    Seed types:
    - minimal: ~10 paires essentielles
    - standard: ~40 paires couvrant les domaines principaux
    - extended: ~80 paires incluant sciences, cognition, langage

    Example:
        POST /graph/inject-seed
        {
            "seed_type": "standard",
            "generate_embeddings": true
        }
    """
    try:
        injector = SeedInjector(db)

        result = await injector.inject_seed(
            seed_type=request.seed_type,
            generate_embeddings=request.generate_embeddings,
            skip_existing_concepts=request.skip_existing_concepts
        )

        return InjectSeedResponse(
            concepts_created=result.concepts_created,
            relations_created=result.relations_created,
            concepts_existed=result.concepts_existed,
            duration_ms=result.duration_ms,
            seed_type=result.seed_type,
            errors=result.errors
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Seed injection failed: {str(e)}")


@router.get("/similar/{concept_id}", response_model=SimilarConceptsResponse)
async def find_similar_concepts(
    concept_id: str,
    top_k: int = Query(10, ge=1, le=100, description="Nombre de résultats"),
    min_similarity: float = Query(0.5, ge=0.0, le=1.0, description="Similarité minimum"),
    db: ISpaceDB = Depends(get_database)
):
    """
    Trouve les concepts les plus similaires à un concept donné.

    Utilise la similarité cosinus entre embeddings 1024D.

    Example:
        GET /graph/similar/entropy?top_k=10&min_similarity=0.6

    Returns:
        Liste de concepts avec leur score de similarité
    """
    try:
        generator = RelationGenerator(db)
        similar = await generator.find_similar_concepts(
            concept_id=concept_id,
            top_k=top_k,
            min_similarity=min_similarity
        )

        return SimilarConceptsResponse(
            concept_id=concept_id,
            similar_concepts=similar,
            count=len(similar)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Similarity search failed: {str(e)}")


@router.get("/phase1-stats", response_model=Phase1StatsResponse)
async def get_phase1_stats(db: ISpaceDB = Depends(get_database)):
    """
    Retourne les statistiques complètes de la Phase 1 ESMM.

    Inclut:
    - Stats de population (concepts, embeddings)
    - Stats de relations (par source, distribution des poids)
    - Stats de la graine ESMM (couverture)

    Example:
        GET /graph/phase1-stats
    """
    try:
        populator = GraphPopulator(db)
        generator = RelationGenerator(db)
        injector = SeedInjector(db)

        population_stats = await populator.get_population_stats()
        relation_stats = await generator.get_generation_stats()
        seed_stats = await injector.get_seed_status()

        return Phase1StatsResponse(
            population=population_stats,
            relations=relation_stats,
            seed=seed_stats
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {str(e)}")


@router.get("/seeds/available")
async def get_available_seeds():
    """
    Liste les types de graines disponibles avec leurs statistiques.

    Example:
        GET /graph/seeds/available

    Returns:
        Dict avec les types de graines et leurs caractéristiques
    """
    from services.esmm import SeedInjector

    # Créer un SeedInjector temporaire sans DB pour accéder aux seeds
    return SeedInjector.__new__(SeedInjector).get_available_seeds()


# ============================================================================
# ESMM PHASE 2 ENDPOINTS - Triplet Extraction
# ============================================================================

@router.post("/extract-triplets", response_model=TripletExtractionResponse)
async def extract_triplets(request: TripletExtractionRequest):
    """
    Extrait des triplets depuis du texte avec consensus multi-modèles.

    PIPELINE:
    1. Génération multi-modèles (batch séquentiel VRAM-optimal)
    2. Parsing et validation des triplets
    3. Calcul du consensus (min_agreement filtrage)
    4. Résolution des entités et normalisation des relations
    5. Injection dans le graphe (si inject_to_graph=true)

    VRAM-OPTIMISÉ:
    - Charge modèle 1 → traite le texte → décharge
    - Charge modèle 2 → traite le texte → décharge

    Example:
        POST /graph/extract-triplets
        {
            "text": "L'entropie augmente dans les systèmes isolés car l'énergie se disperse.",
            "models": ["llama3.1:8b", "mistral:7b"],
            "min_consensus": 0.5,
            "min_confidence": 0.5,
            "inject_to_graph": true
        }

    Returns:
        TripletExtractionResponse avec les triplets extraits et métriques
    """
    try:
        # Créer l'extracteur avec les paramètres de la requête
        # Note: Le singleton peut ne pas respecter les nouveaux paramètres si déjà initialisé
        extractor = await get_triplet_extractor(
            models=request.models,
            min_consensus=request.min_consensus,
            min_confidence=request.min_confidence
        )

        # Extraire les triplets
        result = await extractor.extract_from_text(
            text=request.text,
            session_id=request.session_id,
            inject_to_graph=request.inject_to_graph
        )

        # Construire la réponse avec les triplets formatés
        triplet_responses = []
        for triplet in result.consensus_triplets:
            # Déterminer si ce triplet a été injecté ou skippé
            triplet_hash = triplet.triplet_hash
            was_skipped = triplet_hash in result.skipped_reasons if hasattr(result, 'skipped_hashes') else False
            skip_reason = None

            # Approximation: si le triplet est dans consensus mais pas injecté, c'est un doublon
            if result.triplets_skipped > 0 and not request.inject_to_graph:
                skip_reason = "injection_disabled"

            triplet_responses.append(ExtractedTripletResponse(
                subject=triplet.subject,
                relation=triplet.relation,
                object=triplet.object,
                consensus_score=triplet.consensus_score,
                agreement_ratio=triplet.agreement_ratio,
                avg_confidence=triplet.avg_confidence,
                std_confidence=triplet.std_confidence,
                contributing_models=triplet.contributing_models,
                triplet_hash=triplet.triplet_hash,
                injected=request.inject_to_graph and not was_skipped,
                skip_reason=skip_reason
            ))

        return TripletExtractionResponse(
            triplets=triplet_responses,
            triplets_extracted=result.triplets_extracted,
            triplets_injected=result.triplets_injected,
            triplets_skipped=result.triplets_skipped,
            new_concepts_created=result.new_concepts_created,
            models_used=result.models_used,
            duration_ms=result.duration_ms,
            input_hash=result.input_hash,
            skipped_reasons=result.skipped_reasons
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Triplet extraction failed: {str(e)}"
        )


# ============================================================================
# COCHAIN EXPORT ENDPOINTS
# ============================================================================

@router.get("/cochain/export")
async def export_cochain_viz(
    format: str = Query("json", pattern="^(json|csv)$", description="Export format"),
    min_consensus: float = Query(0.0, ge=0.0, le=1.0, description="Minimum consensus score"),
    db: ISpaceDB = Depends(get_database)
):
    """
    Exporte la 0-cochaîne pour visualisation externe (PCA/t-SNE).

    Le format JSON inclut les coordonnées x, y, z issues du signature_vector 5D.

    Example:
        GET /graph/cochain/export?format=json&min_consensus=0.5

    Returns:
        JSON: {"points": [...], "count": N}
        CSV: Fichier CSV téléchargeable
    """
    try:
        points = await db.export_cochain_for_viz()

        # Filtrer par consensus si spécifié
        if min_consensus > 0:
            points = [p for p in points if p.get("consensus", 0) >= min_consensus]

        if format == "csv":
            # Générer CSV
            import io
            from fastapi.responses import StreamingResponse

            output = io.StringIO()
            output.write("id,consensus,type,x,y,z\n")
            for p in points:
                output.write(
                    f"{p['id']},{p['consensus']},{p['type']},"
                    f"{p['x']},{p['y']},{p['z']}\n"
                )

            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=cochain_export.csv"}
            )

        return {"points": points, "count": len(points)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cochain export failed: {str(e)}")


@router.get("/cochain/stats")
async def get_cochain_stats(db: ISpaceDB = Depends(get_database)):
    """
    Statistiques de la 0-cochaîne ESMM.

    Example:
        GET /graph/cochain/stats

    Returns:
        Dict avec statistiques par type épistémique
    """
    try:
        async with db.connection() as conn:
            # Total entries
            cursor = await conn.execute("SELECT COUNT(*) FROM cochain_entries")
            total = (await cursor.fetchone())[0]

            # Par type épistémique
            cursor = await conn.execute("""
                SELECT epistemic_type, COUNT(*), AVG(consensus_score)
                FROM cochain_entries
                GROUP BY epistemic_type
            """)
            by_type = {
                row[0]: {"count": row[1], "avg_consensus": round(row[2] or 0, 4)}
                for row in await cursor.fetchall()
            }

            # Consensus moyen global
            cursor = await conn.execute(
                "SELECT AVG(consensus_score), AVG(stability_score) FROM cochain_entries"
            )
            row = await cursor.fetchone()
            avg_consensus = row[0] or 0
            avg_stability = row[1] or 0

            # Distribution des scores
            cursor = await conn.execute("""
                SELECT
                    CASE
                        WHEN consensus_score >= 0.8 THEN 'high'
                        WHEN consensus_score >= 0.5 THEN 'medium'
                        ELSE 'low'
                    END as level,
                    COUNT(*)
                FROM cochain_entries
                GROUP BY level
            """)
            distribution = {row[0]: row[1] for row in await cursor.fetchall()}

            return {
                "total_entries": total,
                "by_epistemic_type": by_type,
                "average_consensus": round(avg_consensus, 4),
                "average_stability": round(avg_stability, 4),
                "consensus_distribution": distribution
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cochain stats failed: {str(e)}")


# ============================================================================
# ESMM PHASE 3 ENDPOINTS - Full Protocol
# ============================================================================

from fastapi import BackgroundTasks
from services.esmm.orchestrator import (
    ESMMOrchestrator, ESMMRunConfig,
    run_esmm_protocol, resume_esmm_protocol
)
from services.esmm.gap_detector import create_gap_detector
from services.esmm.coverage_analyzer import CoverageAnalyzer


@router.post("/esmm-run", response_model=ESMMRunStatusResponse)
async def start_esmm_run(
    request: ESMMRunRequest,
    background_tasks: BackgroundTasks,
    db: ISpaceDB = Depends(get_database)
):
    """
    Demarre un run ESMM complet en arriere-plan.

    Le run execute:
    1. Cycles d'exploration (divergent, debate, meta)
    2. Detection des lacunes
    3. Construction de la 0-cochaine
    4. Adaptation dynamique

    Example:
        POST /graph/esmm-run
        {
            "models": ["llama3.1:8b", "mistral:7b"],
            "seed_type": "standard",
            "cycles_per_type": {"divergent": 2, "debate": 1, "meta": 1}
        }

    Returns:
        ESMMRunStatusResponse avec run_id et status initial
    """
    try:
        # Construire la configuration
        config = ESMMRunConfig(
            models=request.models,
            seed_type=request.seed_type,
            cycles_per_type=request.cycles_per_type or {
                "divergent": 3, "debate": 2, "meta": 1
            },
            min_consensus=request.min_consensus,
            min_confidence=request.min_confidence,
            adaptive_cycles=request.adaptive_cycles,
            detect_gaps=request.detect_gaps,
            build_cochain=request.build_cochain,
            max_total_cycles=request.max_total_cycles
        )

        # Creer le run dans la DB
        run_id = await db.create_esmm_run(
            config=config.__dict__,
            models=config.models,
            seed_type=config.seed_type
        )

        # Lancer en arriere-plan
        background_tasks.add_task(run_esmm_protocol, run_id, config, db)

        return ESMMRunStatusResponse(
            run_id=run_id,
            status="started",
            current_cycle=None,
            cycles_completed=0,
            progress_percent=0.0
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start ESMM run: {str(e)}")


@router.get("/esmm-run/{run_id}", response_model=ESMMRunStatusResponse)
async def get_esmm_run_status(
    run_id: int,
    db: ISpaceDB = Depends(get_database)
):
    """
    Recupere le statut d'un run ESMM.

    Example:
        GET /graph/esmm-run/1

    Returns:
        ESMMRunStatusResponse avec progression et metriques
    """
    try:
        async with db.connection() as conn:
            cursor = await conn.execute("""
                SELECT run_id, status, current_cycle, current_iteration,
                       cycles_completed, started_at, error_message,
                       (SELECT COUNT(*) FROM exploration_cycles WHERE run_id = esmm_runs.run_id) as actual_cycles
                FROM esmm_runs WHERE run_id = ?
            """, (run_id,))

            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

            # Calculer la progression
            cycles_completed = row[7] or row[4] or 0
            # Estimation: 6 cycles par defaut (3 divergent + 2 debate + 1 meta)
            estimated_total = 6
            progress = min(100.0, (cycles_completed / estimated_total) * 100)

            import datetime
            started_at = None
            if row[5]:
                started_at = datetime.datetime.fromtimestamp(row[5]).isoformat() + "Z"

            return ESMMRunStatusResponse(
                run_id=row[0],
                status=row[1],
                current_cycle=row[2],
                current_iteration=row[3],
                cycles_completed=cycles_completed,
                progress_percent=round(progress, 1),
                started_at=started_at,
                error_message=row[6]
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.get("/esmm-run/{run_id}/result", response_model=ESMMRunResultResponse)
async def get_esmm_run_result(
    run_id: int,
    db: ISpaceDB = Depends(get_database)
):
    """
    Recupere le resultat complet d'un run ESMM termine.

    Example:
        GET /graph/esmm-run/1/result

    Returns:
        ESMMRunResultResponse avec metriques finales
    """
    try:
        async with db.connection() as conn:
            cursor = await conn.execute("""
                SELECT run_id, status, cycles_completed, total_triplets,
                       triplets_injected, final_cochain_size,
                       coverage_score, consensus_density,
                       epistemic_diversity, structural_stability,
                       started_at, completed_at, error_message
                FROM esmm_runs WHERE run_id = ?
            """, (run_id,))

            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

            # Calculer la duree
            duration_ms = 0.0
            if row[10] and row[11]:
                duration_ms = (row[11] - row[10]) * 1000

            # Compter les gaps
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM knowledge_gaps WHERE run_id = ?",
                (run_id,)
            )
            gaps_count = (await cursor.fetchone())[0] or 0

            errors = []
            if row[12]:
                errors = [row[12]]

            return ESMMRunResultResponse(
                run_id=row[0],
                status=row[1],
                cycles_completed=row[2] or 0,
                total_triplets=row[3] or 0,
                triplets_injected=row[4] or 0,
                cochain_size=row[5] or 0,
                gaps_detected=gaps_count,
                coverage_score=row[6] or 0.0,
                consensus_density=row[7] or 0.0,
                epistemic_diversity=row[8],
                structural_stability=row[9],
                duration_ms=round(duration_ms, 2),
                errors=errors
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Result fetch failed: {str(e)}")


@router.post("/esmm-run/{run_id}/pause")
async def pause_esmm_run(
    run_id: int,
    db: ISpaceDB = Depends(get_database)
):
    """
    Pause un run ESMM en cours.

    L'etat est sauvegarde pour permettre la reprise.

    Example:
        POST /graph/esmm-run/1/pause
    """
    try:
        await db.update_esmm_run_status(run_id, "paused")
        return {"status": "paused", "run_id": run_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pause failed: {str(e)}")


@router.post("/esmm-run/{run_id}/resume")
async def resume_esmm_run(
    run_id: int,
    background_tasks: BackgroundTasks,
    db: ISpaceDB = Depends(get_database)
):
    """
    Reprend un run ESMM pause.

    Example:
        POST /graph/esmm-run/1/resume
    """
    try:
        # Verifier que le run est bien pause
        async with db.connection() as conn:
            cursor = await conn.execute(
                "SELECT status FROM esmm_runs WHERE run_id = ?",
                (run_id,)
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
            if row[0] not in ("paused", "failed"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Run {run_id} cannot be resumed (status: {row[0]})"
                )

        # Reprendre en arriere-plan
        background_tasks.add_task(resume_esmm_protocol, run_id, db)

        return {"status": "resuming", "run_id": run_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resume failed: {str(e)}")


@router.get("/esmm-run/{run_id}/cycles")
async def get_esmm_run_cycles(
    run_id: int,
    cycle_type: Optional[str] = Query(None, description="Filtrer par type de cycle"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: ISpaceDB = Depends(get_database)
):
    """
    Recupere les cycles d'un run ESMM avec pagination.

    Example:
        GET /graph/esmm-run/1/cycles?cycle_type=divergent&limit=10
    """
    try:
        async with db.connection() as conn:
            if cycle_type:
                cursor = await conn.execute("""
                    SELECT cycle_id, cycle_type, iteration, question_rendered,
                           triplets_extracted, started_at, completed_at
                    FROM exploration_cycles
                    WHERE run_id = ? AND cycle_type = ?
                    ORDER BY started_at DESC
                    LIMIT ? OFFSET ?
                """, (run_id, cycle_type, limit, offset))
            else:
                cursor = await conn.execute("""
                    SELECT cycle_id, cycle_type, iteration, question_rendered,
                           triplets_extracted, started_at, completed_at
                    FROM exploration_cycles
                    WHERE run_id = ?
                    ORDER BY started_at DESC
                    LIMIT ? OFFSET ?
                """, (run_id, limit, offset))

            cycles = []
            for row in await cursor.fetchall():
                duration_ms = 0.0
                if row[5] and row[6]:
                    duration_ms = (row[6] - row[5]) * 1000

                cycles.append({
                    "cycle_id": row[0],
                    "cycle_type": row[1],
                    "iteration": row[2],
                    "question": row[3],
                    "triplets_extracted": row[4] or 0,
                    "duration_ms": round(duration_ms, 2)
                })

            return {"cycles": cycles, "count": len(cycles)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cycles fetch failed: {str(e)}")


@router.get("/esmm-run/{run_id}/gaps", response_model=List[KnowledgeGapResponse])
async def get_esmm_run_gaps(
    run_id: int,
    gap_type: Optional[str] = Query(None, description="Filtrer par type de lacune"),
    limit: int = Query(50, ge=1, le=200),
    db: ISpaceDB = Depends(get_database)
):
    """
    Recupere les lacunes detectees pour un run ESMM.

    Example:
        GET /graph/esmm-run/1/gaps?gap_type=isolated&limit=20
    """
    try:
        gaps = await db.get_active_gaps(gap_type=gap_type, limit=limit)

        # Filtrer par run_id si necessaire
        run_gaps = [g for g in gaps if g.get("run_id") == run_id or not g.get("run_id")]

        return [
            KnowledgeGapResponse(
                gap_id=g["gap_id"],
                gap_type=g["gap_type"],
                priority=g["priority"],
                details=g["details"],
                suggested_question=g.get("suggested_question"),
                addressed=bool(g.get("addressed", False))
            )
            for g in run_gaps[:limit]
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gaps fetch failed: {str(e)}")


@router.get("/coverage/metrics", response_model=CoverageMetricsResponse)
async def get_coverage_metrics(db: ISpaceDB = Depends(get_database)):
    """
    Calcule les metriques de couverture actuelles du graphe.

    Example:
        GET /graph/coverage/metrics

    Returns:
        CoverageMetricsResponse avec tous les scores
    """
    try:
        analyzer = CoverageAnalyzer(db)
        metrics = await analyzer.compute_metrics()

        return CoverageMetricsResponse(
            coverage_score=metrics.coverage_score,
            consensus_density=metrics.consensus_density,
            epistemic_diversity=metrics.epistemic_diversity,
            structural_stability=metrics.structural_stability,
            graph_density=metrics.graph_density,
            isolated_ratio=metrics.isolated_ratio,
            clustering_coefficient=metrics.clustering_coefficient
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics computation failed: {str(e)}")


@router.get("/gaps/active", response_model=List[KnowledgeGapResponse])
async def get_active_gaps(
    gap_type: Optional[str] = Query(None, description="Filtrer par type"),
    limit: int = Query(50, ge=1, le=200),
    db: ISpaceDB = Depends(get_database)
):
    """
    Recupere les lacunes actives (non adressees).

    Example:
        GET /graph/gaps/active?gap_type=bridge&limit=20
    """
    try:
        gaps = await db.get_active_gaps(gap_type=gap_type, limit=limit)

        return [
            KnowledgeGapResponse(
                gap_id=g["gap_id"],
                gap_type=g["gap_type"],
                priority=g["priority"],
                details=g["details"],
                suggested_question=g.get("suggested_question"),
                addressed=False
            )
            for g in gaps
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gaps fetch failed: {str(e)}")


@router.post("/gaps/{gap_id}/address")
async def mark_gap_addressed(
    gap_id: int,
    cycle_id: Optional[int] = Query(None, description="Cycle qui a adresse la lacune"),
    db: ISpaceDB = Depends(get_database)
):
    """
    Marque une lacune comme adressee.

    Example:
        POST /graph/gaps/1/address?cycle_id=42
    """
    try:
        await db.mark_gap_addressed(gap_id, cycle_id or 0)
        return {"status": "addressed", "gap_id": gap_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mark addressed failed: {str(e)}")
