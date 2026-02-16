"""
Tests R-2 — Normalisation des triplets avant consensus hash.

RED-GREEN-FIX : ces tests DOIVENT échouer avant implémentation.

Vérifie que :
1. Deux triplets synonymes ("PoW","uses","computing power") et
   ("proof of work","requires","computational power") produisent le même hash.
2. Normalisation: lowercase + strip + collapse whitespace.
3. Relation synonymes mappés (uses/requires/needs → USES, etc.).
4. Triplets réellement différents → hash différent.
"""
import pytest

from services.esmm.consensus_engine import ConsensusEngine


class TestNormalizeTriplet:
    """R-2 RED — normalize_triplet produit des formes canoniques."""

    def test_synonym_relations_same_hash(self):
        """Triplets avec relations synonymes → même hash."""
        engine = ConsensusEngine()

        class FakeTriplet:
            def __init__(self, s, r, o):
                self.subject = s
                self.relation = r
                self.object = o

        t1 = FakeTriplet("PoW", "uses", "computing power")
        t2 = FakeTriplet("proof of work", "requires", "computational power")

        h1 = engine._hash_triplet(t1)
        h2 = engine._hash_triplet(t2)

        assert h1 == h2, (
            f"Synonymous triplets should hash identically after normalization, "
            f"got h1={h1} h2={h2}"
        )

    def test_is_a_synonyms_same_hash(self):
        """is_a / type_of / is_type → même hash."""
        engine = ConsensusEngine()

        class FakeTriplet:
            def __init__(self, s, r, o):
                self.subject = s
                self.relation = r
                self.object = o

        t1 = FakeTriplet("bitcoin", "is_a", "cryptocurrency")
        t2 = FakeTriplet("Bitcoin", "type_of", "cryptocurrency")
        t3 = FakeTriplet("BITCOIN", "is_type", "Cryptocurrency")

        h1 = engine._hash_triplet(t1)
        h2 = engine._hash_triplet(t2)
        h3 = engine._hash_triplet(t3)

        assert h1 == h2 == h3, (
            f"IS_A synonyms should produce same hash: {h1}, {h2}, {h3}"
        )

    def test_whitespace_normalization(self):
        """Espaces multiples + leading/trailing → même hash."""
        engine = ConsensusEngine()

        class FakeTriplet:
            def __init__(self, s, r, o):
                self.subject = s
                self.relation = r
                self.object = o

        t1 = FakeTriplet("proof of work", "uses", "computing power")
        t2 = FakeTriplet("  proof  of  work  ", "uses", "  computing  power  ")

        h1 = engine._hash_triplet(t1)
        h2 = engine._hash_triplet(t2)

        assert h1 == h2, (
            f"Whitespace-normalized triplets should hash identically: {h1} vs {h2}"
        )

    def test_different_triplets_different_hash(self):
        """Triplets réellement différents → hash différent."""
        engine = ConsensusEngine()

        class FakeTriplet:
            def __init__(self, s, r, o):
                self.subject = s
                self.relation = r
                self.object = o

        t1 = FakeTriplet("bitcoin", "uses", "proof of work")
        t2 = FakeTriplet("ethereum", "uses", "proof of stake")

        h1 = engine._hash_triplet(t1)
        h2 = engine._hash_triplet(t2)

        assert h1 != h2, (
            f"Different triplets should have different hashes: {h1} vs {h2}"
        )

    def test_subject_synonym_mapping(self):
        """Sujets avec abréviations connues → même hash."""
        engine = ConsensusEngine()

        class FakeTriplet:
            def __init__(self, s, r, o):
                self.subject = s
                self.relation = r
                self.object = o

        # "proof of work" et "PoW" sont des synonymes de sujet courants
        t1 = FakeTriplet("proof of work", "uses", "energy")
        t2 = FakeTriplet("PoW", "uses", "energy")

        h1 = engine._hash_triplet(t1)
        h2 = engine._hash_triplet(t2)

        assert h1 == h2, (
            f"Known abbreviations should normalize to same form: {h1} vs {h2}"
        )
