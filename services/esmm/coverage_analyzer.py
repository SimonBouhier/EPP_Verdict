"""
ESMM Phase 3 - COVERAGE ANALYZER
================================

Calcule les métriques de couverture sémantique du graphe.

Métriques calculées:
- Coverage score (composite): 0.4*density + 0.3*diversity + 0.3*stability
- Consensus density: Moyenne des scores de consensus
- Epistemic diversity: Entropie de Shannon sur types épistémiques
- Structural stability: Coefficient de clustering moyen
- Graph density: edges / (nodes * (nodes-1))
- Isolated ratio: Proportion de nœuds isolés

Author: Lyra-ACE ESMM Protocol
"""
from __future__ import annotations

import math
import logging
from typing import Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from database.engine import ISpaceDB

logger = logging.getLogger(__name__)


@dataclass
class CoverageMetrics:
    """
    Métriques de couverture sémantique du graphe.

    Attributes:
        coverage_score: Score composite [0,1]: 0.4*density + 0.3*diversity + 0.3*stability
        consensus_density: Moyenne des scores de consensus des triplets
        epistemic_diversity: Entropie de Shannon sur distribution des types épistémiques
        structural_stability: Coefficient de clustering moyen (cohésion locale)
        graph_density: Densité du graphe: edges / (nodes * (nodes-1))
        isolated_ratio: Proportion de concepts avec degré 0
        clustering_coefficient: Coefficient de clustering global
    """
    coverage_score: float
    consensus_density: float
    epistemic_diversity: float
    structural_stability: float
    graph_density: float
    isolated_ratio: float
    clustering_coefficient: float


class CoverageAnalyzer:
    """
    Analyseur de couverture sémantique.

    Calcule diverses métriques pour évaluer la qualité et
    la complétude du graphe de connaissances.
    """

    # Poids pour le score composite
    WEIGHT_DENSITY = 0.4
    WEIGHT_DIVERSITY = 0.3
    WEIGHT_STABILITY = 0.3

    def __init__(self, db: "ISpaceDB"):
        """
        Initialise l'analyseur de couverture.

        Args:
            db: Instance de la base de données ISpace
        """
        self.db = db

    async def compute_metrics(self) -> CoverageMetrics:
        """
        Calcule toutes les métriques de couverture.

        Returns:
            CoverageMetrics avec toutes les métriques calculées
        """
        # Calcul parallèle des métriques de base
        density = await self.compute_graph_density()
        diversity = await self.compute_epistemic_diversity()
        stability = await self.compute_structural_stability()
        consensus = await self.compute_consensus_density()
        isolated = await self.compute_isolated_ratio()
        clustering = await self.compute_clustering_coefficient()

        # Score composite
        coverage_score = (
            self.WEIGHT_DENSITY * density +
            self.WEIGHT_DIVERSITY * diversity +
            self.WEIGHT_STABILITY * stability
        )

        metrics = CoverageMetrics(
            coverage_score=round(coverage_score, 4),
            consensus_density=round(consensus, 4),
            epistemic_diversity=round(diversity, 4),
            structural_stability=round(stability, 4),
            graph_density=round(density, 4),
            isolated_ratio=round(isolated, 4),
            clustering_coefficient=round(clustering, 4)
        )

        logger.info(
            "[CoverageAnalyzer] Metrics computed",
            extra={
                "coverage_score": metrics.coverage_score,
                "consensus_density": metrics.consensus_density,
                "epistemic_diversity": metrics.epistemic_diversity,
                "structural_stability": metrics.structural_stability
            }
        )

        return metrics

    async def compute_coverage_score(self) -> float:
        """
        Calcule le score de couverture composite.

        Formula: 0.4*density + 0.3*diversity + 0.3*stability

        Returns:
            Score de couverture [0, 1]
        """
        density = await self.compute_graph_density()
        diversity = await self.compute_epistemic_diversity()
        stability = await self.compute_structural_stability()

        return (
            self.WEIGHT_DENSITY * density +
            self.WEIGHT_DIVERSITY * diversity +
            self.WEIGHT_STABILITY * stability
        )

    async def compute_graph_density(self) -> float:
        """
        Calcule la densité du graphe.

        Formula: edges / (nodes * (nodes - 1)) pour graphe dirigé

        Returns:
            Densité [0, 1], 0 si moins de 2 nœuds
        """
        try:
            # Compte des nœuds (concepts)
            node_count = await self.db.execute_scalar(
                "SELECT COUNT(*) FROM concepts"
            )

            if node_count < 2:
                return 0.0

            # Compte des arêtes (relations distinctes)
            edge_count = await self.db.execute_scalar(
                "SELECT COUNT(*) FROM relations"
            )

            # Densité pour graphe dirigé
            max_edges = node_count * (node_count - 1)
            density = edge_count / max_edges if max_edges > 0 else 0.0

            return min(1.0, density)  # Cap à 1.0

        except Exception as e:
            logger.warning(f"[CoverageAnalyzer] Error computing graph density: {e}")
            return 0.0

    async def compute_consensus_density(self) -> float:
        """
        Calcule la densité de consensus moyenne.

        Moyenne des scores de confiance de toutes les relations.

        Returns:
            Consensus moyen [0, 1]
        """
        try:
            avg_consensus = await self.db.execute_scalar("""
                SELECT AVG(confidence)
                FROM relations
                WHERE confidence IS NOT NULL
            """)

            return avg_consensus if avg_consensus else 0.0

        except Exception as e:
            logger.warning(f"[CoverageAnalyzer] Error computing consensus density: {e}")
            return 0.0

    async def compute_epistemic_diversity(self) -> float:
        """
        Calcule la diversité épistémique via entropie de Shannon.

        Formula: H = -sum(p_i * log(p_i)) sur la distribution des types

        Returns:
            Entropie normalisée [0, 1]
        """
        try:
            # Distribution des types épistémiques
            type_counts = await self._get_epistemic_type_distribution()

            if not type_counts:
                return 0.0

            total = sum(type_counts.values())
            if total == 0:
                return 0.0

            # Calcul de l'entropie de Shannon
            probas = [count / total for count in type_counts.values() if count > 0]
            entropy = -sum(p * math.log(p) for p in probas if p > 0)

            # Normalisation par l'entropie maximale (log du nombre de classes)
            n_classes = len([c for c in type_counts.values() if c > 0])
            max_entropy = math.log(n_classes) if n_classes > 1 else 1.0

            normalized = entropy / max_entropy if max_entropy > 0 else 0.0

            return min(1.0, normalized)

        except Exception as e:
            logger.warning(f"[CoverageAnalyzer] Error computing epistemic diversity: {e}")
            return 0.0

    async def compute_structural_stability(self) -> float:
        """
        Calcule la stabilité structurelle via coefficient de clustering moyen.

        Le coefficient de clustering mesure la tendance des voisins
        d'un nœud à être eux-mêmes connectés (triangles).

        Returns:
            Coefficient de clustering moyen [0, 1]
        """
        try:
            return await self.compute_clustering_coefficient()
        except Exception as e:
            logger.warning(f"[CoverageAnalyzer] Error computing structural stability: {e}")
            return 0.0

    async def compute_clustering_coefficient(self) -> float:
        """
        Calcule le coefficient de clustering global du graphe.

        Pour chaque nœud: C_i = 2 * triangles / (degree * (degree-1))
        Global: moyenne des C_i

        Returns:
            Coefficient de clustering moyen [0, 1]
        """
        try:
            # Récupère les concepts avec leurs degrés
            concepts = await self.db.execute_query("""
                SELECT id, degree FROM concepts WHERE degree >= 2
            """)

            if not concepts:
                return 0.0

            clustering_sum = 0.0
            valid_count = 0

            for concept in concepts:
                concept_id = concept["id"]
                degree = concept["degree"]

                if degree < 2:
                    continue

                # Compte les triangles pour ce concept
                triangles = await self._count_triangles(concept_id)

                # Coefficient de clustering local
                max_triangles = degree * (degree - 1) / 2
                if max_triangles > 0:
                    local_clustering = triangles / max_triangles
                    clustering_sum += local_clustering
                    valid_count += 1

            if valid_count == 0:
                return 0.0

            return clustering_sum / valid_count

        except Exception as e:
            logger.warning(f"[CoverageAnalyzer] Error computing clustering coefficient: {e}")
            return 0.0

    async def compute_isolated_ratio(self) -> float:
        """
        Calcule la proportion de concepts isolés (degré 0).

        Returns:
            Ratio de nœuds isolés [0, 1]
        """
        try:
            total_concepts = await self.db.execute_scalar(
                "SELECT COUNT(*) FROM concepts"
            )

            if total_concepts == 0:
                return 0.0

            isolated_concepts = await self.db.execute_scalar(
                "SELECT COUNT(*) FROM concepts WHERE degree = 0 OR degree IS NULL"
            )

            return isolated_concepts / total_concepts

        except Exception as e:
            logger.warning(f"[CoverageAnalyzer] Error computing isolated ratio: {e}")
            return 0.0

    async def _get_epistemic_type_distribution(self) -> Dict[str, int]:
        """
        Récupère la distribution des types épistémiques.

        Returns:
            Dict mapping type -> count
        """
        try:
            # Essaie d'abord la table cochain_entries
            rows = await self.db.execute_query("""
                SELECT epistemic_type, COUNT(*) as count
                FROM cochain_entries
                WHERE epistemic_type IS NOT NULL
                GROUP BY epistemic_type
            """)

            if rows:
                return {row["epistemic_type"]: row["count"] for row in rows}

            # Fallback: distribution basée sur le degré des concepts
            # Simule les types: generalist (haut degré), specialized (bas degré), hybrid (moyen)
            rows = await self.db.execute_query("""
                SELECT
                    CASE
                        WHEN degree >= 10 THEN 'generalist'
                        WHEN degree <= 2 THEN 'specialized'
                        ELSE 'hybrid'
                    END as epistemic_type,
                    COUNT(*) as count
                FROM concepts
                GROUP BY epistemic_type
            """)

            return {row["epistemic_type"]: row["count"] for row in rows} if rows else {}

        except Exception as e:
            logger.warning(f"[CoverageAnalyzer] Error getting epistemic distribution: {e}")
            return {}

    async def _count_triangles(self, concept_id: str) -> int:
        """
        Compte le nombre de triangles impliquant un concept.

        Un triangle existe quand deux voisins du concept sont
        eux-mêmes connectés.

        Args:
            concept_id: ID du concept central

        Returns:
            Nombre de triangles
        """
        try:
            # Récupère les voisins (concepts connectés)
            neighbors = await self.db.execute_query("""
                SELECT DISTINCT
                    CASE WHEN source = ? THEN target ELSE source END as neighbor_id
                FROM relations
                WHERE source = ? OR target = ?
            """, (concept_id, concept_id, concept_id))

            if len(neighbors) < 2:
                return 0

            neighbor_ids = [n["neighbor_id"] for n in neighbors]

            # Compte les connexions entre voisins
            triangles = 0
            for i, n1 in enumerate(neighbor_ids):
                for n2 in neighbor_ids[i + 1:]:
                    # Vérifie si n1 et n2 sont connectés
                    exists = await self.db.execute_scalar("""
                        SELECT COUNT(*) FROM relations
                        WHERE (source = ? AND target = ?)
                           OR (source = ? AND target = ?)
                    """, (n1, n2, n2, n1))

                    if exists and exists > 0:
                        triangles += 1

            return triangles

        except Exception as e:
            logger.warning(f"[CoverageAnalyzer] Error counting triangles: {e}")
            return 0


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_coverage_analyzer(db: "ISpaceDB") -> CoverageAnalyzer:
    """
    Factory function pour CoverageAnalyzer.

    Args:
        db: Instance de la base de données

    Returns:
        Instance configurée de CoverageAnalyzer
    """
    return CoverageAnalyzer(db)
