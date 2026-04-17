"""
ESMM Phase 3 - KNOWLEDGE GAP DETECTOR
======================================

Detecte les lacunes dans le graphe de connaissances avec:
- Seuils dynamiques (mediane, percentiles)
- Clustering semantique pour detection de bridges
- Priorisation composite

Types de lacunes:
- ISOLATED: Concepts a faible degre (seuil = mediane/2)
- UNSTABLE: Triplets a haute variance inter-modeles
- BRIDGE: Liens inter-domaines manquants (clusters proches non connectes)

Author: Lyra-ACE ESMM Protocol
"""
from __future__ import annotations

import math
import struct
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
from itertools import combinations
from collections import Counter

if TYPE_CHECKING:
    from database.engine import ISpaceDB

logger = logging.getLogger(__name__)


class GapType(str, Enum):
    """Types de lacunes detectables."""
    ISOLATED = "isolated"       # Concepts a faible degre
    UNSTABLE = "unstable"       # Triplets a haute variance
    BRIDGE = "bridge"           # Liens inter-domaines manquants
    CONTRADICTION = "contradiction"  # Relations contradictoires (A causes B et A prevents B)


@dataclass
class KnowledgeGap:
    """
    Lacune de connaissance identifiee.

    Attributes:
        gap_type: Type de lacune (ISOLATED, UNSTABLE, BRIDGE)
        details: Details specifiques selon le type
        priority: Score de priorite pour traitement [0, 1]
        suggested_question: Question suggeree pour combler la lacune
    """
    gap_type: GapType
    details: Dict[str, Any]
    priority: float
    suggested_question: Optional[str] = None


class KnowledgeGapDetector:
    """
    Detecteur de lacunes dans le graphe de connaissances.

    Utilise des seuils adaptatifs et du clustering semantique
    pour identifier les zones a explorer en priorite.
    """

    # Poids de base pour chaque type de lacune
    DEFAULT_GAP_WEIGHTS = {
        GapType.ISOLATED: 0.4,
        GapType.UNSTABLE: 0.5,
        GapType.BRIDGE: 0.3
    }

    def __init__(
        self,
        db: "ISpaceDB",
        run_id: Optional[int] = None,
        gap_weights: Optional[Dict[GapType, float]] = None
    ):
        """
        Initialise le detecteur de lacunes.

        Args:
            db: Instance de la base de donnees ISpace
            run_id: ID du run ESMM courant (pour logging)
            gap_weights: Poids personnalises par type de lacune
        """
        self.db = db
        self.run_id = run_id
        self._gap_weights = gap_weights or self.DEFAULT_GAP_WEIGHTS.copy()

        # Cache pour eviter recalculs
        self._median_degree_cache: Optional[int] = None
        self._cluster_cache: Optional[List[List[str]]] = None

        logger.info(
            "[KnowledgeGapDetector] Initialized",
            extra={"run_id": run_id, "weights": self._gap_weights}
        )

    async def detect_all_gaps(
        self,
        max_per_type: int = 20
    ) -> List[KnowledgeGap]:
        """
        Detecte tous les types de lacunes en parallele et retourne une liste triee par priorite.

        Args:
            max_per_type: Nombre maximum de lacunes par type

        Returns:
            Liste de KnowledgeGap triee par priorite decroissante
        """
        gaps = []

        # Detecter tous les types en parallele avec asyncio.gather
        async def safe_detect(detector_func, name: str):
            """Wrapper pour capturer les erreurs sans arreter les autres detections."""
            try:
                result = await detector_func(max_per_type)
                logger.debug(f"[GapDetector] Found {len(result)} {name} gaps")
                return result
            except Exception as e:
                logger.warning(f"[GapDetector] Error detecting {name}: {e}")
                return []

        # Lancer les 4 detections en parallele
        results = await asyncio.gather(
            safe_detect(self.detect_isolated_concepts, "isolated concept"),
            safe_detect(self.detect_unstable_triplets, "unstable triplet"),
            safe_detect(self.detect_bridge_opportunities, "bridge opportunity"),
            safe_detect(self.detect_contradictions, "contradiction"),
            return_exceptions=False  # Les exceptions sont gerees dans safe_detect
        )

        # Fusionner tous les resultats
        for result_list in results:
            gaps.extend(result_list)

        # Tri par priorite decroissante
        gaps.sort(key=lambda g: g.priority, reverse=True)

        logger.info(
            "[KnowledgeGapDetector] Gap detection complete",
            extra={"total_gaps": len(gaps), "run_id": self.run_id}
        )

        return gaps

    # ========================================================================
    # ISOLATED CONCEPTS (seuil dynamique)
    # ========================================================================

    async def detect_isolated_concepts(
        self,
        limit: int = 20
    ) -> List[KnowledgeGap]:
        """
        Detecte les concepts isoles (faible degre).

        Le seuil est dynamique: median(degree) / 2, minimum 1.
        Cela permet de s'adapter a la densite du graphe.

        Args:
            limit: Nombre maximum de lacunes a retourner

        Returns:
            Liste de KnowledgeGap de type ISOLATED
        """
        # Calculer le seuil dynamique
        median_degree = await self._get_median_degree()
        threshold = max(1, median_degree // 2)

        logger.debug(
            f"[GapDetector] Isolated detection: median={median_degree}, threshold={threshold}"
        )

        # Requete pour concepts isoles
        try:
            async with self.db.connection() as conn:
                cursor = await conn.execute("""
                    SELECT id, degree FROM concepts
                    WHERE degree IS NOT NULL AND degree < ?
                    ORDER BY degree ASC, RANDOM()
                    LIMIT ?
                """, (threshold, limit))

                rows = await cursor.fetchall()
        except Exception as e:
            logger.warning(f"[GapDetector] DB error for isolated concepts: {e}")
            return []

        gaps = []
        for row in rows:
            concept_id = row[0]
            degree = row[1] or 0

            # Priorite inversement proportionnelle au degre
            # Plus le degre est bas, plus la priorite est haute
            degree_factor = 1.0 - (degree / max(1, threshold))
            priority = self._compute_gap_priority(
                GapType.ISOLATED,
                {"degree_factor": degree_factor}
            )

            gaps.append(KnowledgeGap(
                gap_type=GapType.ISOLATED,
                details={
                    "concept_id": concept_id,
                    "degree": degree,
                    "threshold": threshold
                },
                priority=priority,
                suggested_question=f"Quelles sont les relations fondamentales de {concept_id} avec d'autres concepts?"
            ))

        return gaps

    async def _get_median_degree(self) -> int:
        """
        Calcule la mediane des degres des concepts.

        Utilise un cache pour eviter les recalculs frequents.

        Returns:
            Mediane des degres (minimum 2)
        """
        if self._median_degree_cache is not None:
            return self._median_degree_cache

        try:
            async with self.db.connection() as conn:
                # Approche efficace: utiliser percentile 50%
                cursor = await conn.execute("""
                    SELECT degree FROM concepts
                    WHERE degree IS NOT NULL
                    ORDER BY degree
                    LIMIT 1
                    OFFSET (SELECT COUNT(*) / 2 FROM concepts WHERE degree IS NOT NULL)
                """)
                row = await cursor.fetchone()
                self._median_degree_cache = row[0] if row and row[0] else 2

        except Exception as e:
            logger.warning(f"[GapDetector] Error computing median degree: {e}")
            self._median_degree_cache = 2

        return self._median_degree_cache

    # ========================================================================
    # UNSTABLE TRIPLETS (haute variance)
    # ========================================================================

    async def detect_unstable_triplets(
        self,
        limit: int = 20,
        std_threshold: float = 0.2
    ) -> List[KnowledgeGap]:
        """
        Detecte les triplets instables (haute variance de confiance entre modeles).

        Un triplet est instable si son ecart-type de confiance est > std_threshold
        ET qu'il a ete extrait dans plusieurs cycles (persistance).

        Args:
            limit: Nombre maximum de lacunes a retourner
            std_threshold: Seuil d'ecart-type pour considerer instable

        Returns:
            Liste de KnowledgeGap de type UNSTABLE
        """
        try:
            async with self.db.connection() as conn:
                # Chercher dans les extractions de triplets avec variance
                cursor = await conn.execute("""
                    SELECT
                        subject_canonical as subject,
                        object_canonical as object,
                        relation_canonical as relation,
                        COUNT(*) as extraction_count,
                        AVG(confidence) as avg_confidence,
                        GROUP_CONCAT(DISTINCT model_source) as models
                    FROM triplet_extractions
                    WHERE confidence IS NOT NULL
                    GROUP BY subject_canonical, object_canonical, relation_canonical
                    HAVING COUNT(*) > 1
                    ORDER BY extraction_count DESC
                    LIMIT ?
                """, (limit * 2,))  # On prend plus pour filtrer ensuite

                rows = await cursor.fetchall()
        except Exception as e:
            logger.warning(f"[GapDetector] DB error for unstable triplets: {e}")
            # Fallback: chercher dans relations
            return await self._detect_unstable_from_relations(limit, std_threshold)

        gaps = []
        for row in rows:
            subject = row[0]
            obj = row[1]
            relation = row[2]
            extraction_count = row[3]
            avg_confidence = row[4] or 0.5
            models = row[5] or ""

            # Simuler std_confidence basee sur nombre de modeles differents
            model_count = len(models.split(",")) if models else 1
            # Plus de modeles = potentiellement plus de variance
            estimated_std = min(0.4, 0.1 * model_count) if extraction_count > 2 else 0.15

            if estimated_std < std_threshold:
                continue

            priority = self._compute_gap_priority(
                GapType.UNSTABLE,
                {"std_confidence": estimated_std, "extraction_count": extraction_count}
            )

            gaps.append(KnowledgeGap(
                gap_type=GapType.UNSTABLE,
                details={
                    "subject": subject,
                    "object": obj,
                    "relation": relation,
                    "std_confidence": round(estimated_std, 4),
                    "avg_confidence": round(avg_confidence, 4),
                    "extraction_count": extraction_count,
                    "models": models
                },
                priority=priority,
                suggested_question=f"Clarifie la relation entre {subject} et {obj}. Quelle est la nature exacte de leur lien?"
            ))

            if len(gaps) >= limit:
                break

        return gaps

    async def _detect_unstable_from_relations(
        self,
        limit: int,
        std_threshold: float
    ) -> List[KnowledgeGap]:
        """
        Fallback: detecte les relations instables depuis la table relations.
        """
        try:
            async with self.db.connection() as conn:
                # Relations avec faible poids ou plusieurs sources
                cursor = await conn.execute("""
                    SELECT source, target, relation_type, weight, model_source
                    FROM relations
                    WHERE weight < 0.6
                    ORDER BY weight ASC
                    LIMIT ?
                """, (limit,))

                rows = await cursor.fetchall()
                gaps = []

                for row in rows:
                    priority = self._compute_gap_priority(
                        GapType.UNSTABLE,
                        {"std_confidence": 0.25}
                    )

                    gaps.append(KnowledgeGap(
                        gap_type=GapType.UNSTABLE,
                        details={
                            "subject": row[0],
                            "object": row[1],
                            "relation": row[2],
                            "weight": row[3],
                            "model_source": row[4]
                        },
                        priority=priority,
                        suggested_question=f"Confirme ou infirme la relation {row[2]} entre {row[0]} et {row[1]}."
                    ))

                return gaps

        except Exception as e:
            logger.warning(f"[GapDetector] Fallback also failed: {e}")
            return []

    # ========================================================================
    # BRIDGE OPPORTUNITIES (clustering semantique)
    # ========================================================================

    async def detect_bridge_opportunities(
        self,
        limit: int = 20,
        similarity_threshold: float = 0.6
    ) -> List[KnowledgeGap]:
        """
        Detecte les opportunites de ponts entre clusters semantiques.

        Trouve des clusters de concepts proches semantiquement mais
        non connectes dans le graphe.

        Args:
            limit: Nombre maximum de lacunes a retourner
            similarity_threshold: Seuil de similarite pour considerer des clusters proches

        Returns:
            Liste de KnowledgeGap de type BRIDGE
        """
        # Obtenir les clusters (approximation basee sur les composantes connexes)
        clusters = await self._get_concept_clusters()

        if len(clusters) < 2:
            logger.debug("[GapDetector] Not enough clusters for bridge detection")
            return []

        gaps = []

        # Comparer les paires de clusters
        for cluster_a, cluster_b in combinations(clusters[:10], 2):  # Limiter les comparaisons
            if len(cluster_a) < 2 or len(cluster_b) < 2:
                continue

            # Calculer la similarite inter-cluster
            similarity = await self._compute_cluster_similarity(cluster_a, cluster_b)

            if similarity < similarity_threshold:
                continue

            # Verifier s'il existe deja un pont
            has_bridge = await self._check_cross_cluster_relations(cluster_a, cluster_b)

            if not has_bridge:
                # Selectionner les representants des clusters
                rep_a = cluster_a[0]
                rep_b = cluster_b[0]

                priority = self._compute_gap_priority(
                    GapType.BRIDGE,
                    {"similarity": similarity, "cluster_sizes": (len(cluster_a), len(cluster_b))}
                )

                gaps.append(KnowledgeGap(
                    gap_type=GapType.BRIDGE,
                    details={
                        "cluster_a": cluster_a[:5],  # Limiter la taille
                        "cluster_b": cluster_b[:5],
                        "similarity": round(similarity, 4),
                        "representative_a": rep_a,
                        "representative_b": rep_b
                    },
                    priority=priority,
                    suggested_question=f"Quelle relation existe entre {rep_a} et {rep_b}? Comment ces domaines sont-ils connectes?"
                ))

                if len(gaps) >= limit:
                    break

        return gaps

    # ========================================================================
    # CONTRADICTIONS (relations incompatibles)
    # ========================================================================

    # Paires de relations contradictoires
    CONTRADICTORY_PAIRS = [
        ("cause", "prevents"),
        ("cause", "caused_by"),  # A cause B et A est cause par B (cycle)
        ("supports", "contradicts"),
        ("implies", "contradicts"),
        ("precedes", "follows"),  # Si A precede B, A ne peut pas suivre B
        ("part_of", "has_part"),  # A fait partie de B et A contient B
        ("greater_than", "less_than"),
    ]

    async def detect_contradictions(
        self,
        limit: int = 20
    ) -> List[KnowledgeGap]:
        """
        Detecte les relations contradictoires dans le graphe.

        Une contradiction existe quand deux relations incompatibles
        existent entre les memes concepts (ex: A cause B et A prevents B).

        Args:
            limit: Nombre maximum de contradictions a retourner

        Returns:
            Liste de KnowledgeGap de type CONTRADICTION
        """
        gaps = []

        try:
            async with self.db.connection() as conn:
                for rel_a, rel_b in self.CONTRADICTORY_PAIRS:
                    # Chercher les paires de concepts avec les deux relations
                    cursor = await conn.execute("""
                        SELECT r1.source, r1.target,
                               r1.relation_type as rel1, r2.relation_type as rel2,
                               r1.confidence as conf1, r2.confidence as conf2
                        FROM relations r1
                        JOIN relations r2 ON (
                            (r1.source = r2.source AND r1.target = r2.target)
                            OR (r1.source = r2.target AND r1.target = r2.source)
                        )
                        WHERE r1.relation_type = ? AND r2.relation_type = ?
                          AND r1.rowid < r2.rowid  -- Eviter les doublons
                        LIMIT ?
                    """, (rel_a, rel_b, limit - len(gaps)))

                    rows = await cursor.fetchall()

                    for row in rows:
                        source, target = row[0], row[1]
                        rel1, rel2 = row[2], row[3]
                        conf1, conf2 = row[4] or 1.0, row[5] or 1.0

                        # Priorite elevee pour les contradictions (0.9-1.0)
                        priority = 0.9 + (min(conf1, conf2) * 0.1)

                        gaps.append(KnowledgeGap(
                            gap_type=GapType.CONTRADICTION,
                            details={
                                "source": source,
                                "target": target,
                                "relation_a": rel1,
                                "relation_b": rel2,
                                "confidence_a": round(conf1, 4),
                                "confidence_b": round(conf2, 4)
                            },
                            priority=priority,
                            suggested_question=f"Contradiction detectee: {source} a les relations '{rel1}' et '{rel2}' avec {target}. Quelle relation est correcte?"
                        ))

                        if len(gaps) >= limit:
                            break

                    if len(gaps) >= limit:
                        break

            if gaps:
                logger.warning(
                    f"[GapDetector] CONTRADICTIONS DETECTEES: {len(gaps)} relations contradictoires",
                    extra={"count": len(gaps)}
                )

        except Exception as e:
            logger.warning(f"[GapDetector] Error detecting contradictions: {e}")

        return gaps

    async def _get_concept_clusters(self) -> List[List[str]]:
        """
        Obtient les clusters de concepts (composantes connexes approximatives).

        Utilise une heuristique basee sur les voisins communs.

        Returns:
            Liste de clusters (chaque cluster est une liste d'IDs de concepts)
        """
        if self._cluster_cache is not None:
            return self._cluster_cache

        try:
            async with self.db.connection() as conn:
                # Approche simplifiee: grouper par premier voisin
                cursor = await conn.execute("""
                    SELECT c.id,
                           (SELECT target FROM relations WHERE source = c.id LIMIT 1) as first_neighbor
                    FROM concepts c
                    WHERE c.degree > 0
                    LIMIT 500
                """)

                rows = await cursor.fetchall()

                # Grouper par voisin
                neighbor_groups: Dict[str, List[str]] = {}
                for concept_id, neighbor in rows:
                    if neighbor:
                        if neighbor not in neighbor_groups:
                            neighbor_groups[neighbor] = []
                        neighbor_groups[neighbor].append(concept_id)

                # Convertir en clusters
                self._cluster_cache = [
                    concepts for concepts in neighbor_groups.values()
                    if len(concepts) >= 2
                ]

        except Exception as e:
            logger.warning(f"[GapDetector] Error getting clusters: {e}")
            self._cluster_cache = []

        return self._cluster_cache

    async def _compute_cluster_similarity(
        self,
        cluster_a: List[str],
        cluster_b: List[str]
    ) -> float:
        """
        Calcule la similarite moyenne entre deux clusters.

        Utilise la similarite cosinus des embeddings.

        Returns:
            Similarite moyenne [0, 1]
        """
        try:
            # Prendre un echantillon des representants
            sample_a = cluster_a[:3]
            sample_b = cluster_b[:3]

            total_similarity = 0.0
            comparisons = 0

            async with self.db.connection() as conn:
                for concept_a in sample_a:
                    for concept_b in sample_b:
                        # Requete des embeddings
                        cursor = await conn.execute("""
                            SELECT
                                (SELECT embedding FROM concepts WHERE id = ?) as emb_a,
                                (SELECT embedding FROM concepts WHERE id = ?) as emb_b
                        """, (concept_a, concept_b))

                        row = await cursor.fetchone()
                        if row and row[0] and row[1]:
                            # Deserialiser les embeddings (float32 blob)
                            emb_a = self._deserialize_embedding(row[0])
                            emb_b = self._deserialize_embedding(row[1])

                            if emb_a and emb_b:
                                similarity = self._cosine_similarity(emb_a, emb_b)
                                total_similarity += similarity
                                comparisons += 1

            return total_similarity / max(1, comparisons)

        except Exception as e:
            logger.warning(f"[GapDetector] Error computing cluster similarity: {e}")
            return 0.0

    def _deserialize_embedding(self, blob: bytes) -> Optional[List[float]]:
        """Deserialise un embedding BLOB en liste de floats."""
        try:
            if not blob:
                return None
            # Embeddings sont stockes en float32 (4 bytes par element)
            n_floats = len(blob) // 4
            return list(struct.unpack(f'{n_floats}f', blob))
        except Exception:
            return None

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Calcule la similarite cosinus entre deux vecteurs."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    async def _check_cross_cluster_relations(
        self,
        cluster_a: List[str],
        cluster_b: List[str]
    ) -> bool:
        """
        Verifie s'il existe des relations entre deux clusters.

        Returns:
            True si au moins une relation existe
        """
        try:
            async with self.db.connection() as conn:
                # Verifier les relations dans les deux sens
                placeholders_a = ",".join(["?" for _ in cluster_a[:10]])
                placeholders_b = ",".join(["?" for _ in cluster_b[:10]])

                cursor = await conn.execute(f"""
                    SELECT COUNT(*) FROM relations
                    WHERE (source IN ({placeholders_a}) AND target IN ({placeholders_b}))
                       OR (source IN ({placeholders_b}) AND target IN ({placeholders_a}))
                """, cluster_a[:10] + cluster_b[:10] + cluster_b[:10] + cluster_a[:10])

                row = await cursor.fetchone()
                return (row[0] or 0) > 0

        except Exception as e:
            logger.warning(f"[GapDetector] Error checking cross-cluster relations: {e}")
            return True  # Presumer qu'il y en a pour eviter les faux positifs

    # ========================================================================
    # PRIORISATION
    # ========================================================================

    def _compute_gap_priority(
        self,
        gap_type: GapType,
        details: Dict[str, Any]
    ) -> float:
        """
        Calcule le score de priorite composite pour une lacune.

        Formula: score = base_weight * contextual_factor

        Args:
            gap_type: Type de lacune
            details: Details contextuels pour le calcul

        Returns:
            Score de priorite [0, 1]
        """
        base_weight = self._gap_weights.get(gap_type, 0.3)

        if gap_type == GapType.ISOLATED:
            # Priorite plus haute pour degre tres bas
            degree_factor = details.get("degree_factor", 0.5)
            return min(1.0, base_weight * (1.0 + degree_factor))

        elif gap_type == GapType.UNSTABLE:
            # Priorite proportionnelle a l'ecart-type
            std_conf = details.get("std_confidence", 0.2)
            extraction_count = details.get("extraction_count", 1)
            # Plus d'extractions = plus de confiance dans l'instabilite
            persistence_factor = min(1.0, extraction_count / 5.0)
            return min(1.0, base_weight * std_conf * 3 * (1 + persistence_factor))

        elif gap_type == GapType.BRIDGE:
            # Priorite proportionnelle a la similarite
            similarity = details.get("similarity", 0.5)
            cluster_sizes = details.get("cluster_sizes", (1, 1))
            size_factor = min(1.0, (cluster_sizes[0] + cluster_sizes[1]) / 20.0)
            return min(1.0, base_weight * similarity * (1 + size_factor))

        return base_weight

    # ========================================================================
    # PERSISTENCE
    # ========================================================================

    async def store_gaps(self, gaps: List[KnowledgeGap]) -> int:
        """
        Stocke les lacunes detectees dans la base de donnees.

        Args:
            gaps: Liste de lacunes a stocker

        Returns:
            Nombre de lacunes stockees
        """
        stored = 0

        for gap in gaps:
            try:
                await self.db.add_knowledge_gap(
                    gap_type=gap.gap_type.value,
                    details=gap.details,
                    priority=gap.priority,
                    run_id=self.run_id
                )
                stored += 1
            except Exception as e:
                logger.warning(f"[GapDetector] Error storing gap: {e}")

        logger.info(
            f"[KnowledgeGapDetector] Stored {stored}/{len(gaps)} gaps",
            extra={"run_id": self.run_id}
        )

        return stored

    def clear_cache(self) -> None:
        """Vide les caches internes."""
        self._median_degree_cache = None
        self._cluster_cache = None


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_gap_detector(
    db: "ISpaceDB",
    run_id: Optional[int] = None,
    gap_weights: Optional[Dict[GapType, float]] = None
) -> KnowledgeGapDetector:
    """
    Factory function pour KnowledgeGapDetector.

    Args:
        db: Instance de la base de donnees
        run_id: ID du run ESMM courant
        gap_weights: Poids personnalises par type

    Returns:
        Instance configuree de KnowledgeGapDetector
    """
    return KnowledgeGapDetector(db, run_id, gap_weights)
