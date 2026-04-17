"""
ADR-011-v2 — Phase APPLY : canonical selection, alignment table, triplet rewriting.
"""

import copy
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class AlignmentEntry:
    """Maps an original term to its canonical form."""

    original: str
    canonical: str
    entry_type: str  # "fusion"
    overlap_score: float


@dataclass
class AlignmentTable:
    """Collection of alignment entries."""

    entries: List[AlignmentEntry] = field(default_factory=list)


# ============================================================================
# CANONICAL SELECTION
# ============================================================================

def select_canonical(cluster: List[Tuple[str, str]]) -> str:
    """Select canonical term from a cluster of (term, model_id) pairs.

    Priority: most frequent term → longest → alphabetical.
    """
    term_counts = Counter(term for term, _ in cluster)
    max_count = max(term_counts.values())
    candidates = [t for t, c in term_counts.items() if c == max_count]

    if len(candidates) == 1:
        return candidates[0]

    # Tiebreak: longest
    max_len = max(len(t) for t in candidates)
    candidates = [t for t in candidates if len(t) == max_len]

    if len(candidates) == 1:
        return candidates[0]

    # Tiebreak: alphabetical
    return sorted(candidates)[0]


# ============================================================================
# BUILD ALIGNMENT TABLE
# ============================================================================

def build_alignment_table(
    clusters: List[List[Tuple[str, str]]],
    pair_scores: Dict,
) -> AlignmentTable:
    """Build alignment table from clusters and pair scores.

    Each non-canonical term in a cluster maps to the canonical term.
    """
    entries: List[AlignmentEntry] = []

    for cluster in clusters:
        canonical = select_canonical(cluster)
        unique_terms = set(term for term, _ in cluster)

        for term in unique_terms:
            if term == canonical:
                continue

            # Find best overlap score for this term in this cluster
            best_score = 0.0
            for (node_a, node_b), score in pair_scores.items():
                term_a, _ = node_a
                term_b, _ = node_b
                if (term_a == term and term_b == canonical) or \
                   (term_b == term and term_a == canonical):
                    best_score = max(best_score, score)

            entries.append(AlignmentEntry(
                original=term,
                canonical=canonical,
                entry_type="fusion",
                overlap_score=best_score,
            ))

    return AlignmentTable(entries=entries)


# ============================================================================
# APPLY ALIGNMENT TO TRIPLETS
# ============================================================================

def apply_alignment_to_triplets(
    model_triplets: Dict[str, List],
    alignment_table: AlignmentTable,
) -> Dict[str, List]:
    """Apply alignment table to raw model triplets.

    Replaces terms in subject/relation/object. Preserves confidence and all
    other fields. Returns a NEW dict — never mutates the input.
    """
    # Build lookup: original → canonical
    lookup: Dict[str, str] = {}
    for entry in alignment_table.entries:
        lookup[entry.original] = entry.canonical
        lookup[entry.original.lower()] = entry.canonical

    def _align(value: str) -> str:
        if value in lookup:
            return lookup[value]
        if value.lower() in lookup:
            return lookup[value.lower()]
        return value

    result: Dict[str, List] = {}
    for model_id, triplets in model_triplets.items():
        aligned = []
        for triplet in triplets:
            new_t = copy.copy(triplet)
            if isinstance(new_t, dict):
                new_t = dict(new_t)
                new_t["subject"] = _align(new_t.get("subject", ""))
                new_t["relation"] = _align(new_t.get("relation", ""))
                new_t["object"] = _align(new_t.get("object", ""))
            elif hasattr(new_t, "subject"):
                # ExtractedTriplet or similar dataclass/object
                new_t.subject = _align(getattr(new_t, "subject", ""))
                new_t.relation = _align(getattr(new_t, "relation", ""))
                if hasattr(new_t, "object"):
                    new_t.object = _align(getattr(new_t, "object", ""))
                elif hasattr(new_t, "object_"):
                    new_t.object_ = _align(getattr(new_t, "object_", ""))
            aligned.append(new_t)
        result[model_id] = aligned

    return result
