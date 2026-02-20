"""
Tests ADR-011-v2 — fingerprint_match.py : Jaro-Winkler, classify_neighbor,
relation-aware waterfall, weighted overlap, connected components.

RED-GREEN-FIX : ces tests DOIVENT échouer avant implémentation.

Sprint 1.2 : Tests 1-6 (Jaro-Winkler reference + classify_neighbor)
Sprint 2.4 : Tests 7-14 (waterfall, overlap, components, anti-false-fusion)
"""
import pytest

from services.esmm.fingerprint_match import (
    ClassifiedNeighbor,
    _cosine_similarity,
    _normalize_entity,
    _normalize_relation,
    _relations_compatible,
    classify_neighbor,
    compute_weighted_overlap,
    find_connected_components,
    jaro_winkler_similarity,
    match_neighbor_pair,
)
from services.esmm.fingerprint_expand import MicroGraph


# ===========================================================================
# Sprint 1.2 — Jaro-Winkler reference values + classify_neighbor
# ===========================================================================


# ---------------------------------------------------------------------------
# Test 1 — Jaro-Winkler reference values (safety net for rapidfuzz)
# ---------------------------------------------------------------------------

def test_jaro_winkler_reference_values():
    """Jaro-Winkler similarity matches known reference values."""
    pairs = [
        # Identical strings
        ("hello", "hello", 1.0),
        # Classic Jaro-Winkler test pairs (verified with rapidfuzz 3.14)
        ("martha", "marhta", 0.9611),
        ("dwayne", "duane", 0.8400),
        ("dixon", "dicksonx", 0.8133),
        # Domain terms
        ("proof of history", "proof-of-history", 0.9500),
        ("proof of history", "proof of work", 0.9067),
        ("blockchain", "block chain", 0.9818),
        ("solana", "solana network", 0.8857),
        # Relations
        ("uses", "used_by", 0.8083),
        ("invented_by", "invented by", 0.9636),
        ("is_a", "is a", 0.8667),
        # Completely different
        ("cat", "zebra", 0.0),
        ("proof of history", "anatoly yakovenko", 0.0),
        # Empty
        ("", "", 1.0),
        ("hello", "", 0.0),
    ]
    for a, b, expected_min in pairs:
        score = jaro_winkler_similarity(a, b)
        assert 0.0 <= score <= 1.0, f"Score out of bounds for ({a!r}, {b!r}): {score}"
        # For exact/empty matches, check equality
        if a == b:
            assert score == pytest.approx(1.0), f"Identical strings ({a!r}) should give 1.0, got {score}"
        elif expected_min == 0.0:
            # Just check it's reasonably low (< 0.7)
            assert score < 0.7, f"Unrelated strings ({a!r}, {b!r}) too high: {score}"
        else:
            # Check within tolerance of reference
            assert score == pytest.approx(expected_min, abs=0.05), (
                f"JW({a!r}, {b!r}) = {score}, expected ~{expected_min}"
            )


# ---------------------------------------------------------------------------
# Test 2 — Jaro-Winkler is symmetric
# ---------------------------------------------------------------------------

def test_jaro_winkler_symmetric():
    """Jaro-Winkler similarity is symmetric: sim(a,b) == sim(b,a)."""
    pairs = [
        ("solana", "solana network"),
        ("proof of history", "PoH"),
        ("uses", "used_by"),
    ]
    for a, b in pairs:
        assert jaro_winkler_similarity(a, b) == pytest.approx(
            jaro_winkler_similarity(b, a)
        )


# ---------------------------------------------------------------------------
# Test 3 — classify_neighbor: Named Entity → Strong Anchor (2.0)
# ---------------------------------------------------------------------------

def test_classify_neighbor_named_entity():
    """Capitalized concept → Strong Anchor, weight 2.0."""
    cn = classify_neighbor("invented_by", "Anatoly Yakovenko")
    assert cn.is_strong_anchor is True
    assert cn.weight == 2.0
    assert cn.relation == "invented_by"
    assert cn.concept == "Anatoly Yakovenko"


# ---------------------------------------------------------------------------
# Test 4 — classify_neighbor: generic concept → Weak Descriptor (1.0)
# ---------------------------------------------------------------------------

def test_classify_neighbor_generic():
    """Lowercase generic concept → Weak Descriptor, weight 1.0."""
    cn = classify_neighbor("is_a", "consensus mechanism")
    assert cn.is_strong_anchor is False
    assert cn.weight == 1.0


# ---------------------------------------------------------------------------
# Test 5 — classify_neighbor: term in existing graph → Strong Anchor
# ---------------------------------------------------------------------------

def test_classify_neighbor_existing_graph_term():
    """Lowercase concept present in existing_graph_terms → Strong Anchor."""
    existing = {"proof of history", "solana", "ethereum"}
    cn = classify_neighbor("uses", "proof of history", existing_graph_terms=existing)
    assert cn.is_strong_anchor is True
    assert cn.weight == 2.0


# ---------------------------------------------------------------------------
# Test 6 — classify_neighbor: lowercase, not in graph → Weak
# ---------------------------------------------------------------------------

def test_classify_neighbor_not_in_graph():
    """Lowercase concept NOT in existing_graph_terms → Weak Descriptor."""
    existing = {"ethereum", "bitcoin"}
    cn = classify_neighbor("related_to", "fast transactions", existing_graph_terms=existing)
    assert cn.is_strong_anchor is False
    assert cn.weight == 1.0


# ===========================================================================
# Sprint 2.4 — Relation-aware waterfall, weighted overlap, Union-Find
# ===========================================================================


# ---------------------------------------------------------------------------
# Test 7 — match_neighbor_pair: compatible relations + matching concepts → True
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_match_neighbor_pair_compatible():
    """Compatible relations + matching concepts → True."""
    result = await match_neighbor_pair(
        rel_1="uses", concept_1="proof of history",
        rel_2="requires", concept_2="proof of history",
    )
    assert result is True


# ---------------------------------------------------------------------------
# Test 8 — match_neighbor_pair: incompatible relations → False
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_match_neighbor_pair_incompatible_relations():
    """Incompatible relations → False even if concepts identical."""
    result = await match_neighbor_pair(
        rel_1="invented_by", concept_1="blockchain",
        rel_2="is_a", concept_2="blockchain",
    )
    assert result is False


# ---------------------------------------------------------------------------
# Test 9 — match_neighbor_pair: Strong Anchor requires exact match
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_match_neighbor_pair_strong_anchor_exact():
    """Strong Anchor (Named Entity) requires exact concept match after normalize."""
    # Same person, same relation → True
    result_same = await match_neighbor_pair(
        rel_1="invented_by", concept_1="Anatoly Yakovenko",
        rel_2="invented_by", concept_2="anatoly yakovenko",
        is_strong_anchor=True,
    )
    assert result_same is True

    # Different person, same relation → False (no fuzzy JW on named entities)
    result_diff = await match_neighbor_pair(
        rel_1="invented_by", concept_1="Anatoly Yakovenko",
        rel_2="invented_by", concept_2="Satoshi Nakamoto",
        is_strong_anchor=True,
    )
    assert result_diff is False


# ---------------------------------------------------------------------------
# Test 10 — match_neighbor_pair: Weak Descriptor uses JW fuzzy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_match_neighbor_pair_weak_jw():
    """Weak Descriptor uses Jaro-Winkler fuzzy matching on concepts."""
    result = await match_neighbor_pair(
        rel_1="is_a", concept_1="consensus mechanism",
        rel_2="is_a", concept_2="consensus mechanisms",
        is_strong_anchor=False,
    )
    assert result is True


# ---------------------------------------------------------------------------
# Test 11 — weighted overlap: strong anchors dominate score
# ---------------------------------------------------------------------------

def test_weighted_overlap_strong_anchors_dominate():
    """Strong anchors (weight=2.0) contribute more to overlap score."""
    micro_a = MicroGraph(
        term="solana", model_id="m1",
        neighbors=[("is_a", "blockchain"), ("invented_by", "Anatoly Yakovenko")],
    )
    micro_b = MicroGraph(
        term="solana network", model_id="m2",
        neighbors=[("is_a", "blockchain"), ("invented_by", "Anatoly Yakovenko")],
    )
    # Both have: is_a+blockchain (weak=1.0) and invented_by+Yakovenko (strong=2.0)
    cn_a = [
        ClassifiedNeighbor("is_a", "blockchain", 1.0, False),
        ClassifiedNeighbor("invented_by", "Anatoly Yakovenko", 2.0, True),
    ]
    cn_b = [
        ClassifiedNeighbor("is_a", "blockchain", 1.0, False),
        ClassifiedNeighbor("invented_by", "Anatoly Yakovenko", 2.0, True),
    ]
    matched_pairs = [(cn_a[0], cn_b[0]), (cn_a[1], cn_b[1])]

    score = compute_weighted_overlap(micro_a, micro_b, matched_pairs, cn_a, cn_b)
    # Numerator: max(1.0,1.0) + max(2.0,2.0) = 3.0
    # Denominator: min(1.0+2.0, 1.0+2.0) = 3.0
    # Score = 3.0 / 3.0 = 1.0
    assert score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Test 12 — weighted overlap: partial match
# ---------------------------------------------------------------------------

def test_weighted_overlap_partial():
    """Partial overlap: only one of two neighbors match."""
    micro_a = MicroGraph(
        term="PoH", model_id="m1",
        neighbors=[("is_a", "consensus mechanism"), ("used_by", "solana")],
    )
    micro_b = MicroGraph(
        term="proof of history", model_id="m2",
        neighbors=[("is_a", "consensus mechanism"), ("invented_by", "Anatoly Yakovenko")],
    )
    cn_a = [
        ClassifiedNeighbor("is_a", "consensus mechanism", 1.0, False),
        ClassifiedNeighbor("used_by", "solana", 1.0, False),
    ]
    cn_b = [
        ClassifiedNeighbor("is_a", "consensus mechanism", 1.0, False),
        ClassifiedNeighbor("invented_by", "Anatoly Yakovenko", 2.0, True),
    ]
    # Only the first pair matches
    matched_pairs = [(cn_a[0], cn_b[0])]

    score = compute_weighted_overlap(micro_a, micro_b, matched_pairs, cn_a, cn_b)
    # Numerator: max(1.0, 1.0) = 1.0
    # Denominator: min(1.0+1.0, 1.0+2.0) = min(2.0, 3.0) = 2.0
    # Score = 1.0 / 2.0 = 0.5
    assert score == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Test 13 — connected components: transitive A-B + B-C → {A,B,C}
# ---------------------------------------------------------------------------

def test_connected_components_transitive():
    """A-B and B-C edges produce one cluster {A,B,C}."""
    pair_scores = {
        (("solana", "m1"), ("solana network", "m2")): 0.8,
        (("solana network", "m2"), ("sol", "m3")): 0.7,
    }
    clusters = find_connected_components(pair_scores, merge_threshold=0.6)
    assert len(clusters) == 1
    flat = set(clusters[0])
    assert ("solana", "m1") in flat
    assert ("solana network", "m2") in flat
    assert ("sol", "m3") in flat


# ---------------------------------------------------------------------------
# Test 14 — connected components: no edges above threshold → no clusters
# ---------------------------------------------------------------------------

def test_connected_components_no_edges():
    """No pairs above threshold → empty clusters."""
    pair_scores = {
        (("solana", "m1"), ("bitcoin", "m2")): 0.2,
    }
    clusters = find_connected_components(pair_scores, merge_threshold=0.6)
    assert len(clusters) == 0


# ---------------------------------------------------------------------------
# Test 15 — Anti-false-fusion: PoH vs blockchain (invented_by mismatch)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anti_false_fusion_poh_blockchain():
    """PoH and blockchain must NOT fuse: invented_by→Yakovenko vs invented_by→Nakamoto."""
    # Even though both have "invented_by" relation, the named entities differ
    # Strong Anchor exact match prevents false fusion
    result = await match_neighbor_pair(
        rel_1="invented_by", concept_1="Anatoly Yakovenko",
        rel_2="invented_by", concept_2="Satoshi Nakamoto",
        is_strong_anchor=True,
    )
    assert result is False


# ===========================================================================
# C1 correction — self-contained normalization functions
# ===========================================================================


# ---------------------------------------------------------------------------
# Test 16 — _normalize_entity: lowercase + strip + collapse whitespace
# ---------------------------------------------------------------------------

def test_normalize_entity_basic():
    """_normalize_entity lowercases, strips, collapses whitespace."""
    assert _normalize_entity("  Solana  Network  ") == "solana network"
    assert _normalize_entity("PoH") == "poh"
    assert _normalize_entity("proof  of   history") == "proof of history"
    assert _normalize_entity("") == ""


# ---------------------------------------------------------------------------
# Test 17 — _normalize_relation: synonym groups
# ---------------------------------------------------------------------------

def test_normalize_relation_synonym_groups_legacy(monkeypatch):
    """_normalize_relation maps synonyms to canonical forms (legacy mode)."""
    import services.config_loader as cl
    monkeypatch.setattr(cl, "_config", {
        "esmm": {"use_legacy_relation_groups": True},
    })
    # Direct canonical
    assert _normalize_relation("uses") == "uses"
    assert _normalize_relation("is_a") == "is_a"
    # Synonyms — legacy: relies_on/depends_on → uses
    assert _normalize_relation("relies_on") == "uses"
    assert _normalize_relation("depends_on") == "uses"
    assert _normalize_relation("created_by") == "invented_by"
    assert _normalize_relation("designed_by") == "invented_by"
    assert _normalize_relation("component_of") == "part_of"
    assert _normalize_relation("associated_with") == "related_to"
    # Dash/space normalization
    assert _normalize_relation("relies-on") == "uses"
    assert _normalize_relation("created by") == "invented_by"
    # Unknown → passthrough
    assert _normalize_relation("custom_relation") == "custom_relation"


def test_normalize_relation_synonym_groups_new(monkeypatch):
    """_normalize_relation maps synonyms via relation_vocabulary (new mode)."""
    import services.config_loader as cl
    monkeypatch.setattr(cl, "_config", {
        "esmm": {"use_legacy_relation_groups": False},
    })
    # Direct canonical (lowercase)
    assert _normalize_relation("uses") == "uses"
    assert _normalize_relation("is_a") == "is_a"
    # NEW: relies_on/depends_on → depends_on (DEPENDS_ON group)
    assert _normalize_relation("relies_on") == "depends_on"
    assert _normalize_relation("depends_on") == "depends_on"
    # Created_by → created_by (CREATED_BY group, lowercase)
    assert _normalize_relation("created_by") == "created_by"
    assert _normalize_relation("designed_by") == "created_by"
    # produces → causes (CAUSES group)
    assert _normalize_relation("produces") == "causes"
    assert _normalize_relation("component_of") == "part_of"
    assert _normalize_relation("associated_with") == "relates_to"
    # Dash/space normalization
    assert _normalize_relation("relies-on") == "depends_on"
    assert _normalize_relation("created by") == "created_by"
    # Unknown → passthrough
    assert _normalize_relation("custom_relation") == "custom_relation"


# ---------------------------------------------------------------------------
# Test 18 — _cosine_similarity: known values
# ---------------------------------------------------------------------------

def test_cosine_similarity_known_values():
    """_cosine_similarity computes correct values for known vectors."""
    # Identical vectors → 1.0
    assert _cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)
    # Orthogonal vectors → 0.0
    assert _cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    # Opposite vectors → -1.0
    assert _cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)
    # Zero vector → 0.0
    assert _cosine_similarity([0, 0], [1, 1]) == pytest.approx(0.0)
    # Known value: cos(45°) ≈ 0.707
    assert _cosine_similarity([1, 0], [1, 1]) == pytest.approx(0.7071, abs=0.001)


# ===========================================================================
# relation_vocabulary.py integration — new behavior (flag=false)
# ===========================================================================


# ---------------------------------------------------------------------------
# Test 19 — _relations_compatible: relies_on vs uses → incompatible (new)
# ---------------------------------------------------------------------------

def test_incompatible_relies_on_vs_uses():
    """relies_on (DEPENDS_ON) and uses (USES) are in different groups."""
    # With legacy flag=true (default), these are compatible (same 'uses' group)
    # With flag=false, they are incompatible (DEPENDS_ON vs USES)
    # This test checks the vocabulary-level truth (bypasses flag)
    from services.esmm.relation_vocabulary import are_relations_compatible
    assert are_relations_compatible("relies_on", "uses") is False


# ---------------------------------------------------------------------------
# Test 20 — compatible: relies_on vs depends_on → same group
# ---------------------------------------------------------------------------

def test_compatible_relies_on_vs_depends_on():
    """relies_on and depends_on belong to the same DEPENDS_ON group."""
    from services.esmm.relation_vocabulary import are_relations_compatible
    assert are_relations_compatible("relies_on", "depends_on") is True


# ---------------------------------------------------------------------------
# Test 21 — compatible: creates vs causes → same CAUSES group
# ---------------------------------------------------------------------------

def test_compatible_creates_vs_causes():
    """creates and causes belong to the same CAUSES group."""
    from services.esmm.relation_vocabulary import are_relations_compatible
    assert are_relations_compatible("creates", "causes") is True


# ---------------------------------------------------------------------------
# Test 22 — compatible: invented_by vs designed_by → same CREATED_BY group
# ---------------------------------------------------------------------------

def test_compatible_invented_by_vs_designed_by():
    """invented_by and designed_by belong to the same CREATED_BY group."""
    from services.esmm.relation_vocabulary import are_relations_compatible
    assert are_relations_compatible("invented_by", "designed_by") is True


# ---------------------------------------------------------------------------
# Test 23 — incompatible: enables vs uses → different groups
# ---------------------------------------------------------------------------

def test_incompatible_enables_vs_uses():
    """enables (ENABLES) and uses (USES) are in different groups."""
    from services.esmm.relation_vocabulary import are_relations_compatible
    assert are_relations_compatible("enables", "uses") is False


# ---------------------------------------------------------------------------
# Test 24 — _normalize_relation: relies_on with new vocab → depends_on
# ---------------------------------------------------------------------------

def test_normalize_relies_on_new_vocab():
    """get_canonical maps relies_on to depends_on (lowercase)."""
    from services.esmm.relation_vocabulary import get_canonical
    assert get_canonical("relies_on") == "depends_on"


# ---------------------------------------------------------------------------
# Test 25 — _normalize_relation: produces with new vocab → causes
# ---------------------------------------------------------------------------

def test_normalize_produces_new_vocab():
    """get_canonical maps produces to causes (lowercase)."""
    from services.esmm.relation_vocabulary import get_canonical
    assert get_canonical("produces") == "causes"


# ===========================================================================
# Legacy flag tests — verify flag controls behavior
# ===========================================================================


# ---------------------------------------------------------------------------
# Test 26 — legacy flag=true: relies_on and uses compatible (old behavior)
# ---------------------------------------------------------------------------

def test_legacy_flag_true_preserves_old(monkeypatch):
    """With flag=true, relies_on and uses are compatible (legacy 'uses' group)."""
    import services.config_loader as cl
    monkeypatch.setattr(cl, "_config", {
        "esmm": {"use_legacy_relation_groups": True},
    })
    assert _relations_compatible("relies_on", "uses") is True


# ---------------------------------------------------------------------------
# Test 27 — legacy flag=false: relies_on and uses incompatible (new behavior)
# ---------------------------------------------------------------------------

def test_legacy_flag_false_uses_new(monkeypatch):
    """With flag=false, relies_on and uses are incompatible (DEPENDS_ON vs USES)."""
    import services.config_loader as cl
    monkeypatch.setattr(cl, "_config", {
        "esmm": {"use_legacy_relation_groups": False},
    })
    # relies_on → DEPENDS_ON, uses → USES → different groups
    # JW("relies_on", "uses") < 0.9, so no fuzzy match either
    assert _relations_compatible("relies_on", "uses") is False
