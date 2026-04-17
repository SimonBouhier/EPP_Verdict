"""
ADR-011-v2 — Phase MATCH : relation-aware fingerprint matching.

Sprint 1.2: Jaro-Winkler wrapper + classify_neighbor
Sprint 2.4: waterfall matching, weighted overlap, Union-Find components
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from rapidfuzz.distance import JaroWinkler

logger = logging.getLogger(__name__)


# ============================================================================
# SELF-CONTAINED NORMALIZATION (no cross-module dependency)
# SOURCE OF TRUTH: see relation_vocabulary.py — do NOT define local synonym groups
# TODO: Remove legacy branch after staging validation — see PLAN_RELATION_VOCABULARY.md §3.2
# ============================================================================
from .relation_vocabulary import get_canonical, are_relations_compatible


def _normalize_entity(entity: str) -> str:
    """Normalize entity for comparison: lowercase, strip, collapse whitespace."""
    return " ".join(entity.lower().strip().split())


def _normalize_relation(relation: str) -> str:
    """Normalize relation to canonical group."""
    norm = relation.lower().strip().replace("-", "_").replace(" ", "_")
    try:
        from services.config_loader import get_section
        esmm_cfg = get_section("esmm", {})
        if esmm_cfg.get("use_legacy_relation_groups", True):
            # Frozen legacy 6 groups — exact pre-refactoring behavior
            _LEGACY = {
                "uses": {"uses", "relies_on", "utilizes", "employs", "depends_on",
                         "requires", "needs"},
                "is_a": {"is_a", "is_type_of", "is_kind_of", "type_of"},
                "part_of": {"part_of", "component_of", "belongs_to", "contained_in"},
                "produces": {"produces", "generates", "creates", "outputs"},
                "invented_by": {"invented_by", "created_by", "designed_by", "developed_by"},
                "related_to": {"related_to", "associated_with", "connected_to"},
            }
            for canonical, group in _LEGACY.items():
                if norm in group:
                    return canonical
            return norm
    except Exception:
        pass
    return get_canonical(norm)


def _cosine_similarity(vec_a: list, vec_b: list) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ============================================================================
# JARO-WINKLER WRAPPER
# ============================================================================

def jaro_winkler_similarity(a: str, b: str) -> float:
    """Compute Jaro-Winkler similarity via rapidfuzz.

    Returns float in [0.0, 1.0]. Delegates entirely to rapidfuzz — no
    hand-rolled implementation.
    """
    return JaroWinkler.similarity(a, b)


# ============================================================================
# NEIGHBOR CLASSIFICATION
# ============================================================================

@dataclass
class ClassifiedNeighbor:
    """A micro-graph neighbor with weight classification."""

    relation: str
    concept: str
    weight: float  # 2.0 (Strong Anchor) or 1.0 (Weak Descriptor)
    is_strong_anchor: bool


def classify_neighbor(
    relation: str,
    concept: str,
    existing_graph_terms: Optional[Set[str]] = None,
) -> ClassifiedNeighbor:
    """Classify a neighbor as Strong Anchor (2.0) or Weak Descriptor (1.0).

    Strong Anchor if:
      - concept starts with an uppercase letter (Named Entity), OR
      - concept is present in existing_graph_terms
    Otherwise: Weak Descriptor.
    """
    is_strong = False

    # Check for Named Entity: first letter is uppercase
    if concept and concept[0].isupper():
        is_strong = True

    # Check if present in existing graph
    if not is_strong and existing_graph_terms:
        if concept.lower() in {t.lower() for t in existing_graph_terms}:
            is_strong = True

    weight = 2.0 if is_strong else 1.0
    return ClassifiedNeighbor(
        relation=relation,
        concept=concept,
        weight=weight,
        is_strong_anchor=is_strong,
    )


# ============================================================================
# RELATION-AWARE WATERFALL MATCHING
# ============================================================================

def _relations_compatible(rel_1: str, rel_2: str) -> bool:
    """Check if two relations are compatible (same canonical group or JW > 0.9)."""
    try:
        from services.config_loader import get_section
        esmm_cfg = get_section("esmm", {})
        use_legacy = esmm_cfg.get("use_legacy_relation_groups", True)
    except Exception:
        use_legacy = False

    if use_legacy:
        # Legacy: compare via local _normalize_relation (which uses legacy groups)
        norm_1 = _normalize_relation(rel_1)
        norm_2 = _normalize_relation(rel_2)
        if norm_1 == norm_2:
            return True
    else:
        if are_relations_compatible(rel_1, rel_2):
            return True

    if jaro_winkler_similarity(rel_1.lower(), rel_2.lower()) > 0.9:
        return True
    return False


async def match_neighbor_pair(
    rel_1: str, concept_1: str,
    rel_2: str, concept_2: str,
    is_strong_anchor: bool = False,
    embedding_provider=None,
) -> bool:
    """Relation-aware neighbor matching (waterfall cascade).

    Step 1: Relations must be compatible (same canonical group or JW > 0.9).
    Step 2: Concepts must match:
      - Strong Anchor (Named Entity): exact match after normalize only
      - Weak Descriptor: waterfall (exact → JW > 0.9 → embedding cosine > 0.85)
    """
    # Step 1 — Relations compatible?
    if not _relations_compatible(rel_1, rel_2):
        return False

    # Step 2 — Concepts match?
    norm_1 = _normalize_entity(concept_1)
    norm_2 = _normalize_entity(concept_2)

    # 2a. Exact after normalize
    if norm_1 == norm_2:
        return True

    # Strong Anchor: exact only (no fuzzy on named entities)
    if is_strong_anchor:
        return False

    # 2b. Jaro-Winkler > 0.9
    if jaro_winkler_similarity(norm_1, norm_2) > 0.9:
        return True

    # 2c. Embedding cosine > 0.85 (if provider available)
    if embedding_provider is not None:
        try:
            vec_1 = await embedding_provider.embed(norm_1)
            vec_2 = await embedding_provider.embed(norm_2)
            if _cosine_similarity(vec_1, vec_2) > 0.85:
                return True
        except Exception:
            pass

    # 2d. No match
    return False


# ============================================================================
# WEIGHTED OVERLAP SCORE
# ============================================================================

def compute_weighted_overlap(
    micro_a,
    micro_b,
    matched_pairs: List[Tuple[ClassifiedNeighbor, ClassifiedNeighbor]],
    classifications_a: List[ClassifiedNeighbor],
    classifications_b: List[ClassifiedNeighbor],
) -> float:
    """Compute weighted overlap score between two micro-graphs.

    score = sum(max(weight_a, weight_b) for matched pairs) / min(sum_A, sum_B)
    """
    if not classifications_a or not classifications_b:
        return 0.0

    numerator = sum(max(cn_a.weight, cn_b.weight) for cn_a, cn_b in matched_pairs)
    sum_a = sum(cn.weight for cn in classifications_a)
    sum_b = sum(cn.weight for cn in classifications_b)
    denominator = min(sum_a, sum_b)

    if denominator == 0:
        return 0.0

    return numerator / denominator


# ============================================================================
# CONNECTED COMPONENTS (UNION-FIND)
# ============================================================================

class _UnionFind:
    """Union-Find with path compression and union by rank."""

    def __init__(self):
        self._parent = {}
        self._rank = {}

    def find(self, x):
        if x not in self._parent:
            self._parent[x] = x
            self._rank[x] = 0
        if self._parent[x] != x:
            self._parent[x] = self.find(self._parent[x])
        return self._parent[x]

    def union(self, x, y):
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self._rank[rx] < self._rank[ry]:
            rx, ry = ry, rx
        self._parent[ry] = rx
        if self._rank[rx] == self._rank[ry]:
            self._rank[rx] += 1


def find_connected_components(
    pair_scores: Dict[Tuple, float],
    merge_threshold: float,
) -> List[List[Tuple[str, str]]]:
    """Find connected components from pair scores using Union-Find.

    Nodes are (term, model_id) tuples.
    Edges are pairs with score >= merge_threshold.
    Returns list of clusters (each cluster is a list of (term, model_id) tuples).
    Only returns clusters with 2+ members.
    """
    uf = _UnionFind()

    for (node_a, node_b), score in pair_scores.items():
        if score >= merge_threshold:
            uf.union(node_a, node_b)

    # Group by root
    groups: Dict = {}
    for (node_a, node_b), score in pair_scores.items():
        if score >= merge_threshold:
            root = uf.find(node_a)
            if root not in groups:
                groups[root] = set()
            groups[root].add(node_a)
            groups[root].add(node_b)

    # Filter: only clusters with 2+ members
    return [list(members) for members in groups.values() if len(members) >= 2]


# ============================================================================
# MATCH RESULT
# ============================================================================

@dataclass
class MatchResult:
    """Result of the MATCH phase."""

    clusters: List[List[Tuple[str, str]]]  # List of clusters of (term, model_id)
    pair_scores: Dict  # {((term_a, model_a), (term_b, model_b)): score}
    duration_ms: float = 0.0


# ============================================================================
# MATCH_FINGERPRINTS — ASYNC ORCHESTRATION
# ============================================================================

async def match_fingerprints(
    expand_result,
    config,
    embedding_provider=None,
    existing_graph_terms: Optional[Set[str]] = None,
) -> MatchResult:
    """Phase MATCH: compare micro-graphs across models, build clusters.

    For each pair of (term_a, model_a) vs (term_b, model_b) where model_a != model_b,
    classify neighbors, run waterfall matching, compute weighted overlap, then
    find connected components.
    """
    import time
    start = time.time()

    pair_scores: Dict = {}

    # Collect all (term, model_id, MicroGraph) entries
    entries: List[Tuple[str, str, object]] = []
    for model_id, term_graphs in expand_result.micro_graphs.items():
        for term, mg in term_graphs.items():
            entries.append((term, model_id, mg))

    # Compare all cross-model pairs
    for i in range(len(entries)):
        term_a, model_a, mg_a = entries[i]
        for j in range(i + 1, len(entries)):
            term_b, model_b, mg_b = entries[j]

            # Only cross-model comparisons
            if model_a == model_b:
                continue

            # Classify neighbors
            cn_a = [
                classify_neighbor(rel, concept, existing_graph_terms)
                for rel, concept in mg_a.neighbors
            ]
            cn_b = [
                classify_neighbor(rel, concept, existing_graph_terms)
                for rel, concept in mg_b.neighbors
            ]

            # Find matched pairs via waterfall
            matched_pairs: List[Tuple[ClassifiedNeighbor, ClassifiedNeighbor]] = []
            used_b = set()

            for idx_a, cna in enumerate(cn_a):
                for idx_b, cnb in enumerate(cn_b):
                    if idx_b in used_b:
                        continue
                    is_strong = cna.is_strong_anchor or cnb.is_strong_anchor
                    match = await match_neighbor_pair(
                        rel_1=cna.relation, concept_1=cna.concept,
                        rel_2=cnb.relation, concept_2=cnb.concept,
                        is_strong_anchor=is_strong,
                        embedding_provider=embedding_provider,
                    )
                    if match:
                        matched_pairs.append((cna, cnb))
                        used_b.add(idx_b)
                        break

            # Compute weighted overlap
            score = compute_weighted_overlap(mg_a, mg_b, matched_pairs, cn_a, cn_b)
            node_a = (term_a, model_a)
            node_b = (term_b, model_b)
            pair_scores[(node_a, node_b)] = score

    # Find connected components
    clusters = find_connected_components(pair_scores, config.merge_threshold)
    duration_ms = (time.time() - start) * 1000

    return MatchResult(
        clusters=clusters,
        pair_scores=pair_scores,
        duration_ms=duration_ms,
    )
