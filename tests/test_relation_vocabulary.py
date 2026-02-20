"""
Tests for relation_vocabulary.py — Single Source of Truth for relation synonyms.

Section 1: Module tests (build_synonym_map, get_canonical, are_relations_compatible)
Section 2: Hash stability CI gate (ADR-006 — no existing hash may change)

Reference hashes computed from consensus_engine.py _RELATION_GROUPS snapshot
(2026-02-20, pre-refactoring). These are immutable constants.
"""
import hashlib
import re

import pytest

from services.esmm.relation_vocabulary import (
    RELATION_GROUPS,
    are_relations_compatible,
    build_synonym_map,
    get_canonical,
)


# ===========================================================================
# Section 1 — Module tests
# ===========================================================================


def test_every_synonym_resolves():
    """Every synonym in all 11 groups resolves to the correct canonical."""
    mapping = build_synonym_map(uppercase_canonicals=True)
    for canonical, synonyms in RELATION_GROUPS.items():
        for syn in synonyms:
            assert mapping[syn] == canonical, (
                f"{syn!r} should map to {canonical!r}, got {mapping[syn]!r}"
            )


def test_uppercase_mode():
    """build_synonym_map(True) returns UPPERCASE canonicals."""
    mapping = build_synonym_map(uppercase_canonicals=True)
    assert mapping["uses"] == "USES"
    assert mapping["relies_on"] == "DEPENDS_ON"
    assert mapping["produces"] == "CAUSES"
    assert mapping["invented_by"] == "CREATED_BY"


def test_lowercase_mode():
    """build_synonym_map(False) returns lowercase canonicals."""
    mapping = build_synonym_map(uppercase_canonicals=False)
    assert mapping["uses"] == "uses"
    assert mapping["relies_on"] == "depends_on"
    assert mapping["produces"] == "causes"
    assert mapping["invented_by"] == "created_by"


def test_compatible_same_group():
    """relies_on and depends_on are in the same group → compatible."""
    assert are_relations_compatible("relies_on", "depends_on") is True


def test_incompatible_different_group():
    """uses and depends_on are in different groups → incompatible."""
    assert are_relations_compatible("uses", "depends_on") is False


def test_compatible_self():
    """A relation is compatible with itself."""
    assert are_relations_compatible("uses", "uses") is True


def test_unknown_relation_fallback():
    """Unknown relation falls back to itself."""
    assert get_canonical("unknown_thing") == "unknown_thing"
    assert get_canonical("unknown_thing", uppercase=True) == "unknown_thing"


def test_created_by_group():
    """invented_by and designed_by resolve to the same canonical."""
    assert get_canonical("invented_by", uppercase=True) == "CREATED_BY"
    assert get_canonical("designed_by", uppercase=True) == "CREATED_BY"
    assert are_relations_compatible("invented_by", "designed_by") is True


def test_no_orphan_synonyms():
    """Each synonym belongs to exactly one group (no duplicates across groups)."""
    seen: dict[str, str] = {}
    for canonical, synonyms in RELATION_GROUPS.items():
        for syn in synonyms:
            assert syn not in seen, (
                f"{syn!r} appears in both {seen[syn]!r} and {canonical!r}"
            )
            seen[syn] = canonical


# ===========================================================================
# Section 2 — Hash stability CI gate (ADR-006)
# ===========================================================================
#
# These tests hardcode SHA-256 hashes produced by the ORIGINAL
# consensus_engine.py code (pre-refactoring). The new build_synonym_map()
# MUST produce identical hashes for all pre-existing relations.
#
# Hash formula: sha256(f"{entity}|{relation}|{entity}".encode())[:16]
# where entity/relation are normalized via consensus_engine's logic.
# ===========================================================================

# --- Normalization helpers (mirror consensus_engine.py exactly) ---

_ENTITY_SYNONYMS = {
    "pow": "proof of work", "pos": "proof of stake",
    "dpos": "delegated proof of stake", "defi": "decentralized finance",
    "nft": "non-fungible token", "dao": "decentralized autonomous organization",
    "ai": "artificial intelligence", "ml": "machine learning",
    "llm": "large language model",
}

_WORD_SYNONYMS = {
    "computational": "computing", "decentralised": "decentralized",
    "utilise": "use", "utilises": "uses", "utilisation": "use",
    "verification": "validation", "verify": "validate",
    "algorithm": "mechanism", "algorithms": "mechanisms",
}


def _normalize_text(text: str) -> str:
    text = text.lower().strip()
    return re.sub(r"\s+", " ", text)


def _normalize_entity(entity: str) -> str:
    normalized = _normalize_text(entity)
    lookup = normalized.replace("_", " ")
    if lookup in _ENTITY_SYNONYMS:
        return _ENTITY_SYNONYMS[lookup]
    words = normalized.split()
    words = [_WORD_SYNONYMS.get(w, w) for w in words]
    return " ".join(words)


def _hash_with_new_vocab(subject: str, relation: str, obj: str) -> str:
    """Hash a triplet using relation_vocabulary.py (new code path)."""
    ns = _normalize_entity(subject)
    nr = get_canonical(relation, uppercase=True)
    no = _normalize_entity(obj)
    canonical = f"{ns}|{nr}|{no}"
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


# Reference hashes — IMMUTABLE, computed from pre-refactoring code
# Do NOT modify these constants.

@pytest.mark.ci_gate
def test_hash_stability_uses():
    """('solana', 'uses', 'proof of history') — hash unchanged."""
    h = _hash_with_new_vocab("solana", "uses", "proof of history")
    assert h == "e6cda8e54cc39162"


@pytest.mark.ci_gate
def test_hash_stability_relies_on():
    """('solana', 'relies_on', 'proof of history') — hash unchanged."""
    h = _hash_with_new_vocab("solana", "relies_on", "proof of history")
    assert h == "6e56bf85a897739b"


@pytest.mark.ci_gate
def test_hash_stability_produces():
    """('photosynthesis', 'produces', 'oxygen') — hash unchanged."""
    h = _hash_with_new_vocab("photosynthesis", "produces", "oxygen")
    assert h == "d1b4789f551f9950"


@pytest.mark.ci_gate
def test_hash_stability_leads_to():
    """('entropy', 'leads_to', 'disorder') — hash unchanged."""
    h = _hash_with_new_vocab("entropy", "leads_to", "disorder")
    assert h == "e739715afbbc79ba"


@pytest.mark.ci_gate
def test_hash_stability_enables():
    """('api', 'enables', 'integration') — hash unchanged."""
    h = _hash_with_new_vocab("api", "enables", "integration")
    assert h == "c556c96aa13298b8"


@pytest.mark.ci_gate
def test_hash_stability_related_to():
    """('bitcoin', 'related_to', 'blockchain') — hash unchanged."""
    h = _hash_with_new_vocab("bitcoin", "related_to", "blockchain")
    assert h == "d6005c7dd89ca20c"


@pytest.mark.ci_gate
def test_hash_stability_part_of():
    """('wheel', 'part_of', 'car') — hash unchanged."""
    h = _hash_with_new_vocab("wheel", "part_of", "car")
    assert h == "610b25db5844d67a"


@pytest.mark.ci_gate
def test_hash_stability_unknown():
    """('X', 'unknown_rel', 'Y') — passthrough, hash unchanged."""
    h = _hash_with_new_vocab("X", "unknown_rel", "Y")
    assert h == "01c57609b43f7fff"


@pytest.mark.ci_gate
def test_hash_stability_entity_synonym():
    """('pow', 'uses', 'energy') — PoW → proof of work, hash unchanged."""
    h = _hash_with_new_vocab("pow", "uses", "energy")
    assert h == "621a39aab8c3fae8"


@pytest.mark.ci_gate
def test_hash_stability_created_by():
    """('bitcoin', 'invented_by', 'satoshi') — NEW group, deterministic hash."""
    # invented_by was not in any consensus_engine group before.
    # New vocab maps it to CREATED_BY. This test locks the NEW hash.
    h = _hash_with_new_vocab("bitcoin", "invented_by", "satoshi")
    # New hash (invented_by → CREATED_BY, different from legacy passthrough)
    expected = hashlib.sha256("bitcoin|CREATED_BY|satoshi".encode()).hexdigest()[:16]
    assert h == expected
