"""
Relation Vocabulary — Single Source of Truth for relation synonym groups.

Consolidates the relation groups previously duplicated in:
- consensus_engine.py (_RELATION_GROUPS, 10 groups, UPPERCASE canonicals)
- fingerprint_match.py (RELATION_GROUPS, 6 groups, lowercase canonicals)

11 groups total: the 10 from consensus_engine (ADR-006 hash stability) plus
CREATED_BY (from fingerprint_match, no prior consensus_engine mapping).

Conflict resolutions:
- relies_on, depends_on → DEPENDS_ON (semantically correct; was mis-classified
  in fingerprint_match as "uses")
- produces ∈ CAUSES (hash stability ADR-006)
- creates, generates, outputs ∈ CAUSES (coherent with produces)

See PLAN_RELATION_VOCABULARY.md for full rationale.

SOURCE OF TRUTH: do NOT define local synonym groups elsewhere.
TODO: Remove _LEGACY branches after staging validation — see §3.2
"""
from typing import Dict, Set


RELATION_GROUPS: Dict[str, Set[str]] = {
    "USES": {"uses", "requires", "needs", "employs", "utilizes", "utilises"},
    "IS_A": {"is_a", "type_of", "is_type", "is_type_of", "kind_of", "instance_of",
             "is_kind_of"},
    "HAS": {"has", "contains", "includes", "possesses", "owns"},
    "PART_OF": {"part_of", "component_of", "belongs_to", "member_of", "subset_of",
                "contained_in"},
    "CAUSES": {"causes", "leads_to", "results_in", "produces", "triggers",
               "creates", "generates", "outputs"},
    "ENABLES": {"enables", "allows", "permits", "facilitates", "supports"},
    "PREVENTS": {"prevents", "blocks", "inhibits", "stops", "hinders"},
    "RELATES_TO": {"relates_to", "related_to", "associated_with", "connected_to",
                   "linked_to"},
    "DEPENDS_ON": {"depends_on", "relies_on", "based_on", "built_on"},
    "PROVIDES": {"provides", "offers", "supplies", "gives", "delivers"},
    "CREATED_BY": {"invented_by", "created_by", "designed_by", "developed_by"},
}


def build_synonym_map(uppercase_canonicals: bool = False) -> Dict[str, str]:
    """Build flat synonym → canonical lookup.

    Args:
        uppercase_canonicals: If True, canonicals are UPPERCASE (for
            consensus_engine hashing). If False, lowercase (for
            fingerprint_match comparison).

    Returns:
        Dict mapping each synonym to its canonical form.
    """
    result: Dict[str, str] = {}
    for canonical, synonyms in RELATION_GROUPS.items():
        target = canonical if uppercase_canonicals else canonical.lower()
        for syn in synonyms:
            result[syn] = target
    return result


def get_canonical(relation: str, uppercase: bool = False) -> str:
    """Get canonical form for a relation. Fallback: the relation itself.

    Args:
        relation: Raw relation string (will be lowercased for lookup).
        uppercase: If True, return UPPERCASE canonical.

    Returns:
        Canonical relation string, or the input if not found.
    """
    norm = relation.lower().strip().replace("-", "_").replace(" ", "_")
    mapping = build_synonym_map(uppercase_canonicals=uppercase)
    return mapping.get(norm, norm)


def are_relations_compatible(rel_a: str, rel_b: str) -> bool:
    """Check if two relations belong to the same canonical group.

    Args:
        rel_a: First relation string.
        rel_b: Second relation string.

    Returns:
        True if both resolve to the same canonical group.
    """
    norm_a = rel_a.lower().strip().replace("-", "_").replace(" ", "_")
    norm_b = rel_b.lower().strip().replace("-", "_").replace(" ", "_")
    mapping = build_synonym_map(uppercase_canonicals=True)
    return mapping.get(norm_a, norm_a) == mapping.get(norm_b, norm_b)
