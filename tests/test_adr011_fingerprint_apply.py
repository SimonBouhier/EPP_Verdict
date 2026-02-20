"""
Tests ADR-011-v2 — fingerprint_apply.py : canonical selection, alignment table,
triplet rewriting.

RED-GREEN-FIX : ces tests DOIVENT échouer avant implémentation.
"""
import pytest

from services.esmm.fingerprint_apply import (
    AlignmentEntry,
    AlignmentTable,
    apply_alignment_to_triplets,
    build_alignment_table,
    select_canonical,
)


# ---------------------------------------------------------------------------
# Test 1 — select_canonical: most frequent term wins
# ---------------------------------------------------------------------------

def test_select_canonical_most_frequent():
    """Most frequent term in the cluster is selected as canonical."""
    cluster = [
        ("solana", "m1"), ("solana", "m2"), ("solana network", "m3"),
    ]
    canonical = select_canonical(cluster)
    assert canonical == "solana"


# ---------------------------------------------------------------------------
# Test 2 — select_canonical: tiebreak → longest, then alphabetical
# ---------------------------------------------------------------------------

def test_select_canonical_tiebreak():
    """On tie, select longest term; if still tied, alphabetical."""
    cluster = [("PoH", "m1"), ("proof of history", "m2")]
    canonical = select_canonical(cluster)
    assert canonical == "proof of history"  # longer wins

    # Same length, alphabetical
    cluster2 = [("beta", "m1"), ("alpha", "m2")]
    canonical2 = select_canonical(cluster2)
    assert canonical2 == "alpha"


# ---------------------------------------------------------------------------
# Test 3 — build_alignment_table: basic case
# ---------------------------------------------------------------------------

def test_build_alignment_table_basic():
    """Alignment table maps non-canonical terms to canonical."""
    clusters = [
        [("solana", "m1"), ("solana", "m2"), ("solana network", "m3")],
    ]
    pair_scores = {
        (("solana", "m1"), ("solana network", "m3")): 0.85,
        (("solana", "m2"), ("solana network", "m3")): 0.80,
    }
    table = build_alignment_table(clusters, pair_scores)
    assert isinstance(table, AlignmentTable)
    # "solana network" should map to "solana" (canonical)
    entries_for_solana_net = [e for e in table.entries if e.original == "solana network"]
    assert len(entries_for_solana_net) == 1
    assert entries_for_solana_net[0].canonical == "solana"
    # "solana" is canonical — should NOT appear as original
    entries_for_solana = [e for e in table.entries if e.original == "solana"]
    assert len(entries_for_solana) == 0


# ---------------------------------------------------------------------------
# Test 4 — apply_alignment_to_triplets: substitution in S/R/O
# ---------------------------------------------------------------------------

def test_apply_alignment_basic():
    """Alignment table substitutes terms in subject, relation, and object."""
    model_triplets = {
        "m1": [
            {"subject": "solana", "relation": "uses", "object": "proof of history", "confidence": 0.9},
        ],
        "m3": [
            {"subject": "solana network", "relation": "uses", "object": "PoH", "confidence": 0.8},
        ],
    }
    table = AlignmentTable(entries=[
        AlignmentEntry(original="solana network", canonical="solana", entry_type="fusion", overlap_score=0.85),
        AlignmentEntry(original="PoH", canonical="proof of history", entry_type="fusion", overlap_score=0.90),
    ])
    result = apply_alignment_to_triplets(model_triplets, table)
    # Check m3 triplet is now aligned
    assert result["m3"][0]["subject"] == "solana"
    assert result["m3"][0]["object"] == "proof of history"
    # m1 unchanged (already canonical)
    assert result["m1"][0]["subject"] == "solana"
    assert result["m1"][0]["object"] == "proof of history"
    # Confidence preserved
    assert result["m3"][0]["confidence"] == 0.8


# ---------------------------------------------------------------------------
# Test 5 — apply_alignment_to_triplets: non-matched terms preserved
# ---------------------------------------------------------------------------

def test_apply_alignment_preserves_unmatched():
    """Terms not in alignment table are preserved as-is."""
    model_triplets = {
        "m1": [
            {"subject": "ethereum", "relation": "is_a", "object": "blockchain", "confidence": 0.95},
        ],
    }
    table = AlignmentTable(entries=[
        AlignmentEntry(original="solana network", canonical="solana", entry_type="fusion", overlap_score=0.85),
    ])
    result = apply_alignment_to_triplets(model_triplets, table)
    assert result["m1"][0]["subject"] == "ethereum"
    assert result["m1"][0]["object"] == "blockchain"
    # Original dict not mutated
    assert model_triplets["m1"][0]["subject"] == "ethereum"


# ---------------------------------------------------------------------------
# Test 6 — C5: apply_alignment_to_triplets handles non-dict objects
# ---------------------------------------------------------------------------

def test_apply_alignment_object_triplets():
    """Alignment works on objects with subject/relation/object attributes (safety net)."""
    class FakeTriplet:
        def __init__(self, subject, relation, obj, confidence):
            self.subject = subject
            self.relation = relation
            self.object = obj
            self.confidence = confidence

    model_triplets = {
        "m1": [
            FakeTriplet("solana network", "uses", "PoH", 0.8),
        ],
    }
    table = AlignmentTable(entries=[
        AlignmentEntry(original="solana network", canonical="solana", entry_type="fusion", overlap_score=0.85),
        AlignmentEntry(original="PoH", canonical="proof of history", entry_type="fusion", overlap_score=0.90),
    ])
    result = apply_alignment_to_triplets(model_triplets, table)
    aligned = result["m1"][0]
    assert aligned.subject == "solana"
    assert aligned.object == "proof of history"
    assert aligned.confidence == 0.8
