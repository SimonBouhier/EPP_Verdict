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
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional

from app.models import (
    GraphDeltaRequest, GraphDeltaResponse, KappaResponse, ErrorResponse,
    PopulateRequest, PopulateResponse,
    GenerateRelationsRequest, GenerateRelationsResponse,
    InjectSeedRequest, InjectSeedResponse,
    SimilarConceptsResponse, Phase1StatsResponse
)
from database import (
    get_db, ISpaceDB, GraphDelta, DeltaOperation,
    DeltaValidationError, MutationLimitExceededError
)
from services.esmm import GraphPopulator, RelationGenerator, SeedInjector


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
