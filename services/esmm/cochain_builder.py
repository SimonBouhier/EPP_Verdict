"""
ESMM Phase 3 - COCHAIN BUILDER
==============================

Construit la 0-cochaine epistemique avec:
- Signature 5D normalisee [0,1]
- Entropie de Shannon pour diversite relationnelle
- Typage epistemique par percentiles

La 0-cochaine associe a chaque concept un vecteur de scores:
- consensus_score: Fiabilite basee sur l'accord multi-modeles
- model_agreement: Ratio de modeles concordants
- semantic_consistency: Coherence des relations
- structural_centrality: Importance topologique
- stability_score: Stabilite temporelle

Author: Lyra-ACE ESMM Protocol
"""
from __future__ import annotations

import math
import logging
from typing import List, Dict, Optional, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter

if TYPE_CHECKING:
    from database.engine import ISpaceDB

logger = logging.getLogger(__name__)


class EpistemicType(str, Enum):
    """Types epistemiques pour classification des concepts."""
    GENERALIST = "generalist"    # Haut degre, relations diverses
    SPECIALIZED = "specialized"  # Domaine-specific, clustered
    HYBRID = "hybrid"            # Mix des deux


@dataclass
class CochainEntry:
    """
    Entree de la 0-cochaine pour un concept.

    Attributes:
        concept_id: ID du concept
        consensus_score: Score de consensus moyen des triplets
        model_agreement: Accord moyen entre modeles
        semantic_consistency: Coherence semantique des relations
        structural_centrality: Centralite dans le graphe
        stability_score: Stabilite temporelle
        relation_diversity: Entropie de Shannon des types de relations
        signature_vector: Vecteur 5D normalise [0,1]
        epistemic_type: Classification epistemique
        contributing_models: Modeles ayant contribue avec leurs poids
        triplet_count: Nombre de triplets impliquant ce concept
    """
    concept_id: str
    consensus_score: float
    model_agreement: float
    semantic_consistency: float
    structural_centrality: float
    stability_score: float
    relation_diversity: float
    signature_vector: List[float]
    epistemic_type: EpistemicType
    contributing_models: Dict[str, float]
    triplet_count: int


class CochainBuilder:
    """
    Constructeur de la 0-cochaine epistemique.

    Agregge les donnees des triplets pour chaque concept et
    calcule les scores composants de la signature 5D.
    """

    # Seuils pour le typage epistemique
    DEFAULT_CENTRALITY_P80 = 0.8
    DEFAULT_CENTRALITY_P20 = 0.2
    DEFAULT_DIVERSITY_THRESHOLD = 0.5

    def __init__(
        self,
        db: "ISpaceDB",
        run_id: Optional[int] = None
    ):
        """
        Initialise le constructeur de cochaine.

        Args:
            db: Instance de la base de donnees ISpace
            run_id: ID du run ESMM courant
        """
        self.db = db
        self.run_id = run_id

        # Cache pour les percentiles de centralite
        self._centrality_percentiles: Optional[Dict[str, float]] = None

        # Cache pour les stats globales
        self._global_stats: Optional[Dict[str, float]] = None

        logger.info(
            "[CochainBuilder] Initialized",
            extra={"run_id": run_id}
        )

    async def build_cochain(
        self,
        min_triplet_count: int = 2
    ) -> List[CochainEntry]:
        """
        Construit la 0-cochaine complete.

        Pipeline:
        1. Agrege les donnees des triplets par concept
        2. Calcule les scores composants
        3. Calcule la diversite relationnelle (entropie Shannon)
        4. Calcule la signature 5D normalisee
        5. Determine le type epistemique
        6. Stocke dans la base de donnees

        Args:
            min_triplet_count: Nombre minimum de triplets pour inclure un concept

        Returns:
            Liste des entrees de cochaine creees
        """
        logger.info(
            "[CochainBuilder] Building cochain",
            extra={"min_triplet_count": min_triplet_count, "run_id": self.run_id}
        )

        # Charger les percentiles de centralite
        await self._load_centrality_percentiles()

        # Obtenir les concepts candidats
        concepts = await self._get_candidate_concepts(min_triplet_count)

        logger.debug(f"[CochainBuilder] Found {len(concepts)} candidate concepts")

        entries = []
        for concept_data in concepts:
            try:
                entry = await self._build_entry(concept_data)
                if entry:
                    entries.append(entry)

                    # Stocker dans la DB
                    await self.db.upsert_cochain_entry(
                        concept_id=entry.concept_id,
                        consensus_score=entry.consensus_score,
                        model_agreement=entry.model_agreement,
                        semantic_consistency=entry.semantic_consistency,
                        structural_centrality=entry.structural_centrality,
                        stability_score=entry.stability_score,
                        signature_vector=entry.signature_vector,
                        epistemic_type=entry.epistemic_type.value,
                        contributing_models=entry.contributing_models,
                        triplet_count=entry.triplet_count,
                        run_id=self.run_id
                    )

            except Exception as e:
                logger.warning(
                    f"[CochainBuilder] Error building entry for {concept_data.get('concept_id')}: {e}"
                )

        logger.info(
            "[CochainBuilder] Cochain built",
            extra={"entries_created": len(entries), "run_id": self.run_id}
        )

        return entries

    async def _get_candidate_concepts(
        self,
        min_triplet_count: int
    ) -> List[Dict[str, Any]]:
        """
        Recupere les concepts candidats pour la cochaine.

        Returns:
            Liste de dicts avec concept_id et metriques de base
        """
        try:
            async with self.db.connection() as conn:
                # Concepts avec suffisamment de triplets
                cursor = await conn.execute("""
                    SELECT
                        c.id as concept_id,
                        c.degree,
                        COUNT(DISTINCT te.extraction_id) as triplet_count,
                        AVG(te.confidence) as avg_confidence,
                        GROUP_CONCAT(DISTINCT te.model_source) as models
                    FROM concepts c
                    LEFT JOIN triplet_extractions te ON
                        te.subject_canonical = c.id OR te.object_canonical = c.id
                    GROUP BY c.id
                    HAVING triplet_count >= ? OR c.degree >= 2
                    ORDER BY triplet_count DESC
                """, (min_triplet_count,))

                rows = await cursor.fetchall()

                return [
                    {
                        "concept_id": row[0],
                        "degree": row[1] or 0,
                        "triplet_count": row[2] or 0,
                        "avg_confidence": row[3] or 0.5,
                        "models": row[4] or ""
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.warning(f"[CochainBuilder] Error getting candidates: {e}")
            # Fallback: tous les concepts avec degre > 0
            return await self._get_fallback_candidates()

    async def _get_fallback_candidates(self) -> List[Dict[str, Any]]:
        """Fallback pour obtenir les concepts candidats."""
        try:
            async with self.db.connection() as conn:
                cursor = await conn.execute("""
                    SELECT id, degree FROM concepts
                    WHERE degree > 0
                    ORDER BY degree DESC
                    LIMIT 1000
                """)

                return [
                    {
                        "concept_id": row[0],
                        "degree": row[1] or 0,
                        "triplet_count": row[1] or 0,  # Approximation
                        "avg_confidence": 0.5,
                        "models": ""
                    }
                    for row in await cursor.fetchall()
                ]

        except Exception as e:
            logger.error(f"[CochainBuilder] Fallback also failed: {e}")
            return []

    async def _build_entry(
        self,
        concept_data: Dict[str, Any]
    ) -> Optional[CochainEntry]:
        """
        Construit une entree de cochaine pour un concept.

        Args:
            concept_data: Donnees du concept

        Returns:
            CochainEntry ou None si erreur
        """
        concept_id = concept_data["concept_id"]

        # Calculer les scores composants
        consensus_score = await self._compute_consensus_score(concept_id)
        model_agreement = await self._compute_model_agreement(concept_id)
        semantic_consistency = await self._compute_semantic_consistency(concept_id)
        structural_centrality = await self._compute_structural_centrality(concept_id)
        stability_score = await self._compute_stability_score(concept_id)
        relation_diversity = await self._compute_relation_diversity(concept_id)

        # Signature 5D normalisee
        signature_vector = self._compute_signature_vector(
            consensus_score,
            model_agreement,
            semantic_consistency,
            structural_centrality,
            stability_score
        )

        # Modeles contributeurs
        contributing_models = await self._get_contributing_models(concept_id)

        # Type epistemique
        epistemic_type = await self._determine_epistemic_type(
            structural_centrality,
            relation_diversity
        )

        return CochainEntry(
            concept_id=concept_id,
            consensus_score=round(consensus_score, 4),
            model_agreement=round(model_agreement, 4),
            semantic_consistency=round(semantic_consistency, 4),
            structural_centrality=round(structural_centrality, 4),
            stability_score=round(stability_score, 4),
            relation_diversity=round(relation_diversity, 4),
            signature_vector=[round(v, 4) for v in signature_vector],
            epistemic_type=epistemic_type,
            contributing_models=contributing_models,
            triplet_count=concept_data.get("triplet_count", 0)
        )

    # ========================================================================
    # SCORES COMPOSANTS
    # ========================================================================

    async def _compute_consensus_score(self, concept_id: str) -> float:
        """
        Calcule le score de consensus moyen pour un concept.

        Moyenne des consensus_score des triplets impliquant ce concept.

        Returns:
            Score [0, 1]
        """
        try:
            async with self.db.connection() as conn:
                cursor = await conn.execute("""
                    SELECT AVG(r.weight) as avg_consensus
                    FROM relations r
                    WHERE r.source = ? OR r.target = ?
                """, (concept_id, concept_id))

                row = await cursor.fetchone()
                return row[0] if row and row[0] else 0.5

        except Exception as e:
            logger.debug(f"[CochainBuilder] Error computing consensus for {concept_id}: {e}")
            return 0.5

    async def _compute_model_agreement(self, concept_id: str) -> float:
        """
        Calcule l'accord moyen entre modeles pour un concept.

        Returns:
            Ratio [0, 1]
        """
        try:
            async with self.db.connection() as conn:
                # Compter les modeles distincts ayant extrait des triplets
                cursor = await conn.execute("""
                    SELECT COUNT(DISTINCT model_source) as model_count
                    FROM triplet_extractions
                    WHERE subject_canonical = ? OR object_canonical = ?
                """, (concept_id, concept_id))

                row = await cursor.fetchone()
                model_count = row[0] if row and row[0] else 1

                # Normaliser: 2+ modeles = bon accord
                return min(1.0, model_count / 3.0)

        except Exception as e:
            logger.debug(f"[CochainBuilder] Error computing agreement for {concept_id}: {e}")
            return 0.5

    async def _compute_semantic_consistency(self, concept_id: str) -> float:
        """
        Calcule la coherence semantique des relations d'un concept.

        Base sur la variance des types de relations.

        Returns:
            Score [0, 1]
        """
        try:
            async with self.db.connection() as conn:
                cursor = await conn.execute("""
                    SELECT relation_type, COUNT(*) as count
                    FROM relations
                    WHERE source = ? OR target = ?
                    GROUP BY relation_type
                """, (concept_id, concept_id))

                rows = await cursor.fetchall()
                if not rows:
                    return 0.5

                # Coherence = inverse de l'entropie (normalise)
                # Haute entropie = beaucoup de types differents = moins coherent
                counts = [row[1] for row in rows]
                total = sum(counts)
                if total == 0:
                    return 0.5

                probas = [c / total for c in counts]
                entropy = -sum(p * math.log(p) for p in probas if p > 0)

                # Normaliser (max entropy = log(n))
                max_entropy = math.log(len(counts)) if len(counts) > 1 else 1.0
                normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0

                # Coherence = 1 - entropie normalisee
                return 1.0 - normalized_entropy

        except Exception as e:
            logger.debug(f"[CochainBuilder] Error computing consistency for {concept_id}: {e}")
            return 0.5

    async def _compute_structural_centrality(self, concept_id: str) -> float:
        """
        Calcule la centralite structurelle d'un concept.

        Base sur le degre normalise.

        Returns:
            Score [0, 1]
        """
        try:
            async with self.db.connection() as conn:
                # Degre du concept
                cursor = await conn.execute(
                    "SELECT degree FROM concepts WHERE id = ?",
                    (concept_id,)
                )
                row = await cursor.fetchone()
                degree = row[0] if row and row[0] else 0

                # Degre max pour normalisation
                cursor = await conn.execute(
                    "SELECT MAX(degree) FROM concepts"
                )
                row = await cursor.fetchone()
                max_degree = row[0] if row and row[0] else 1

                return degree / max(1, max_degree)

        except Exception as e:
            logger.debug(f"[CochainBuilder] Error computing centrality for {concept_id}: {e}")
            return 0.0

    async def _compute_stability_score(self, concept_id: str) -> float:
        """
        Calcule la stabilite temporelle d'un concept.

        Base sur la variance des poids des relations dans le temps.

        Returns:
            Score [0, 1] (1 = stable)
        """
        try:
            async with self.db.connection() as conn:
                # Moyenne et variance des poids
                cursor = await conn.execute("""
                    SELECT AVG(weight), COUNT(*)
                    FROM relations
                    WHERE source = ? OR target = ?
                """, (concept_id, concept_id))

                row = await cursor.fetchone()
                if not row or not row[0]:
                    return 0.5

                avg_weight = row[0]
                relation_count = row[1]

                # Plus de relations = plus stable (approximation)
                stability = min(1.0, relation_count / 10.0) * avg_weight

                return stability

        except Exception as e:
            logger.debug(f"[CochainBuilder] Error computing stability for {concept_id}: {e}")
            return 0.5

    async def _compute_relation_diversity(self, concept_id: str) -> float:
        """
        Calcule la diversite relationnelle via entropie de Shannon.

        H = -sum(p_i * log(p_i)) sur les types de relations.

        Returns:
            Entropie normalisee [0, 1]
        """
        try:
            async with self.db.connection() as conn:
                cursor = await conn.execute("""
                    SELECT relation_type, COUNT(*) as count
                    FROM relations
                    WHERE source = ? OR target = ?
                    GROUP BY relation_type
                """, (concept_id, concept_id))

                rows = await cursor.fetchall()
                if not rows:
                    return 0.0

                # Compter les types
                counts = [row[1] for row in rows]
                total = sum(counts)
                if total == 0:
                    return 0.0

                # Entropie de Shannon
                probas = [c / total for c in counts]
                entropy = -sum(p * math.log(p) for p in probas if p > 0)

                # Normaliser par l'entropie maximale
                n_types = len(counts)
                max_entropy = math.log(n_types) if n_types > 1 else 1.0

                return entropy / max_entropy if max_entropy > 0 else 0.0

        except Exception as e:
            logger.debug(f"[CochainBuilder] Error computing diversity for {concept_id}: {e}")
            return 0.0

    # ========================================================================
    # SIGNATURE 5D
    # ========================================================================

    def _compute_signature_vector(
        self,
        consensus_score: float,
        model_agreement: float,
        semantic_consistency: float,
        structural_centrality: float,
        stability_score: float
    ) -> List[float]:
        """
        Calcule le vecteur signature 5D normalise.

        Chaque dimension est clampee a [0, 1].

        Returns:
            Liste de 5 floats normalises
        """
        return [
            min(1.0, max(0.0, consensus_score)),
            min(1.0, max(0.0, model_agreement)),
            min(1.0, max(0.0, semantic_consistency)),
            min(1.0, max(0.0, structural_centrality)),
            min(1.0, max(0.0, stability_score))
        ]

    # ========================================================================
    # TYPAGE EPISTEMIQUE
    # ========================================================================

    async def _load_centrality_percentiles(self) -> None:
        """Charge les percentiles de centralite depuis la DB."""
        if self._centrality_percentiles is not None:
            return

        try:
            async with self.db.connection() as conn:
                # Calculer P20 et P80
                cursor = await conn.execute("""
                    SELECT degree FROM concepts
                    WHERE degree IS NOT NULL
                    ORDER BY degree
                """)

                degrees = [row[0] for row in await cursor.fetchall() if row[0]]

                if degrees:
                    n = len(degrees)
                    p20_idx = int(n * 0.2)
                    p80_idx = int(n * 0.8)

                    max_degree = max(degrees) if degrees else 1

                    self._centrality_percentiles = {
                        "p20": degrees[p20_idx] / max(1, max_degree) if p20_idx < n else 0.2,
                        "p80": degrees[p80_idx] / max(1, max_degree) if p80_idx < n else 0.8
                    }
                else:
                    self._centrality_percentiles = {"p20": 0.2, "p80": 0.8}

        except Exception as e:
            logger.warning(f"[CochainBuilder] Error loading percentiles: {e}")
            self._centrality_percentiles = {"p20": 0.2, "p80": 0.8}

    async def _determine_epistemic_type(
        self,
        structural_centrality: float,
        relation_diversity: float
    ) -> EpistemicType:
        """
        Determine le type epistemique d'un concept.

        Regles:
        - GENERALIST: Top 20% centralite ET diversite > seuil
        - SPECIALIZED: Bottom 20% centralite
        - HYBRID: Entre les deux

        Returns:
            EpistemicType
        """
        if self._centrality_percentiles is None:
            await self._load_centrality_percentiles()

        p80 = self._centrality_percentiles.get("p80", self.DEFAULT_CENTRALITY_P80)
        p20 = self._centrality_percentiles.get("p20", self.DEFAULT_CENTRALITY_P20)

        if structural_centrality > p80 and relation_diversity > self.DEFAULT_DIVERSITY_THRESHOLD:
            return EpistemicType.GENERALIST
        elif structural_centrality < p20:
            return EpistemicType.SPECIALIZED
        else:
            return EpistemicType.HYBRID

    # ========================================================================
    # HELPERS
    # ========================================================================

    async def _get_contributing_models(
        self,
        concept_id: str
    ) -> Dict[str, float]:
        """
        Recupere les modeles ayant contribue a l'extraction d'un concept.

        Returns:
            Dict model_name -> contribution_weight
        """
        try:
            async with self.db.connection() as conn:
                cursor = await conn.execute("""
                    SELECT model_source, COUNT(*) as count, AVG(confidence) as avg_conf
                    FROM triplet_extractions
                    WHERE subject_canonical = ? OR object_canonical = ?
                    GROUP BY model_source
                """, (concept_id, concept_id))

                rows = await cursor.fetchall()
                if not rows:
                    return {}

                total = sum(row[1] for row in rows)
                return {
                    row[0]: round(row[1] / max(1, total) * (row[2] or 0.5), 4)
                    for row in rows
                    if row[0]
                }

        except Exception as e:
            logger.debug(f"[CochainBuilder] Error getting models for {concept_id}: {e}")
            return {}

    def clear_cache(self) -> None:
        """Vide les caches internes."""
        self._centrality_percentiles = None
        self._global_stats = None


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_cochain_builder(
    db: "ISpaceDB",
    run_id: Optional[int] = None
) -> CochainBuilder:
    """
    Factory function pour CochainBuilder.

    Args:
        db: Instance de la base de donnees
        run_id: ID du run ESMM courant

    Returns:
        Instance configuree de CochainBuilder
    """
    return CochainBuilder(db, run_id)
