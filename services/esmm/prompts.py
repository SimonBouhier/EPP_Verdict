"""
ESMM - FEW-SHOT PROMPTS FOR TRIPLET EXTRACTION
================================================

Few-shot prompt templates with positive and negative examples to
improve the quality of semantic triplet extraction.

Strategy:
1. Positive examples: valid, well-formed triplets
2. Negative examples: common errors to avoid
3. Canonical relations: strict whitelist
4. Output format: structured JSON

Author: Lyra-ACE ESMM Protocol
"""
from __future__ import annotations

from typing import List, Dict, Any

# Canonical relations whitelist
CANONICAL_RELATIONS = [
    "cause",           # A causes B
    "caused_by",       # A is caused by B
    "is_a",            # A is a type of B
    "has_a",           # A has B as component
    "part_of",         # A is part of B
    "has_part",        # A has B as part
    "related_to",      # General relation
    "similar_to",      # Similarity
    "opposite_of",     # Opposition/antonym
    "implies",         # Logical implication
    "contradicts",     # Logical contradiction
    "supports",        # Evidence support
    "requires",        # Dependency
    "produces",        # Production/output
    "consumes",        # Input/consumption
    "enables",         # Enabling relation
    "prevents",        # Prevention
    "follows",         # Temporal sequence
    "precedes",        # Temporal precedence
    "contains",        # Containment
]

# Main template for triplet extraction
TRIPLET_EXTRACTION_PROMPT = """You are an expert knowledge extractor. You extract semantic triplets (Subject, Relation, Object) from the provided text.

CRITICAL: Regardless of the user's input language, ALL output keys and values
in the JSON (subjects, relations, objects) MUST be in English.

## ALLOWED CANONICAL RELATIONS (USE ONLY THESE)
{canonical_relations}

## VALID EXAMPLES (TO FOLLOW)

Text: "Entropy increases in an isolated system because energy disperses."
Triplets:
[
  {{"subject": "entropy", "relation": "related_to", "object": "isolated system", "confidence": 0.9}},
  {{"subject": "energy", "relation": "cause", "object": "entropy", "confidence": 0.85}}
]

Text: "Photosynthesis is a biological process that produces oxygen from CO2."
Triplets:
[
  {{"subject": "photosynthesis", "relation": "is_a", "object": "biological process", "confidence": 0.95}},
  {{"subject": "photosynthesis", "relation": "produces", "object": "oxygen", "confidence": 0.9}},
  {{"subject": "photosynthesis", "relation": "consumes", "object": "CO2", "confidence": 0.9}}
]

Text: "The Pythagorean theorem implies that the square of the hypotenuse equals the sum of the squares of the sides."
Triplets:
[
  {{"subject": "pythagorean theorem", "relation": "implies", "object": "hypotenuse square relation", "confidence": 0.95}},
  {{"subject": "hypotenuse", "relation": "part_of", "object": "right triangle", "confidence": 0.8}}
]

## INVALID EXAMPLES (NEVER DO THIS)

X Triplets too vague:
  {{"subject": "thing", "relation": "does", "object": "other thing"}} - Too generic
  {{"subject": "it", "relation": "is", "object": "important"}} - Unresolved pronouns

X Non-canonical relations:
  {{"subject": "A", "relation": "interacts_with", "object": "B"}} - Use "related_to" instead
  {{"subject": "X", "relation": "leads_to", "object": "Y"}} - Use "cause" or "implies"

X Opinions and subjectivity:
  {{"subject": "Einstein", "relation": "thought", "object": "time is relative"}} - Opinion, not fact
  {{"subject": "theory", "relation": "seems", "object": "correct"}} - Uncertain

X Incomplete information:
  {{"subject": "he", "relation": "cause", "object": "effect"}} - "he" unresolved
  {{"subject": "", "relation": "is_a", "object": "concept"}} - Empty subject

## STRICT RULES

1. **Concrete concepts**: Subjects and objects must be precise terms (2-100 characters)
2. **Canonical relations**: Use ONLY the relations from the list above
3. **Confidence**: Assign confidence between 0.5 (uncertain) and 1.0 (certain)
4. **No pronouns**: Resolve references before extracting
5. **Factual only**: No opinions, beliefs, or speculation
6. **English ONLY for subjects, relations and objects**

## OUTPUT FORMAT (STRICT JSON)
```json
[
  {{"subject": "subject_concept", "relation": "canonical_relation", "object": "object_concept", "confidence": 0.0-1.0}},
  ...
]
```

If no valid triplet can be extracted, return: []

## TEXT TO ANALYZE
{text}

## EXTRACTED TRIPLETS (JSON only, no explanation)
"""

# Template for validating existing triplets
TRIPLET_VALIDATION_PROMPT = """You are a semantic triplet validator. Evaluate whether the following triplets are valid and well-formed.

## VALIDATION CRITERIA
1. Subject and object non-empty (2-100 characters)
2. Relation in the canonical list: {canonical_relations}
3. No unresolved pronouns (he, she, it, this, that)
4. No opinions or speculation
5. Appropriate confidence (0.5-1.0)

## TRIPLETS TO VALIDATE
{triplets}

## OUTPUT FORMAT
For each triplet, indicate:
```json
[
  {{"index": 0, "valid": true/false, "reason": "explanation if invalid", "corrected": {{...}} or null}}
]
```
"""

# Template for generating relations between concepts
RELATION_GENERATION_PROMPT = """You generate semantic relations between two given concepts.

## AVAILABLE CANONICAL RELATIONS
{canonical_relations}

## EXAMPLES
Concepts: "cause" and "effect"
Relations:
[
  {{"relation": "opposite_of", "confidence": 0.9, "bidirectional": true}},
  {{"relation": "implies", "confidence": 0.7, "bidirectional": false}}
]

Concepts: "photosynthesis" and "oxygen"
Relations:
[
  {{"relation": "produces", "confidence": 0.95, "bidirectional": false}}
]

## CONCEPTS TO ANALYZE
Concept A: {concept_a}
Concept B: {concept_b}

## POSSIBLE RELATIONS (JSON only)
"""

# Template for concept extraction from text
CONCEPT_EXTRACTION_PROMPT = """You extract key concepts from text to build a semantic graph.

## RULES
1. Extract nouns, technical terms, and abstract concepts
2. Normalize to lowercase
3. Ignore common words (the, a, an, of, etc.)
4. Merge variants (e.g. "entropies" -> "entropy")
5. Maximum 20 concepts per text

## EXAMPLES

Text: "Entropy is a measure of disorder in a thermodynamic system."
Concepts: ["entropy", "measure", "disorder", "thermodynamic system"]

Text: "Einstein's theory of relativity revolutionized modern physics."
Concepts: ["theory of relativity", "einstein", "modern physics", "revolution"]

## TEXT TO ANALYZE
{text}

## EXTRACTED CONCEPTS (JSON array only)
"""


def get_triplet_extraction_prompt(text: str) -> str:
    """
    Generate the complete prompt for triplet extraction.

    Args:
        text: Source text to analyze

    Returns:
        Formatted prompt with examples
    """
    relations_str = ", ".join(CANONICAL_RELATIONS)
    return TRIPLET_EXTRACTION_PROMPT.format(
        canonical_relations=relations_str,
        text=text
    )


def get_triplet_validation_prompt(triplets: List[Dict[str, Any]]) -> str:
    """
    Generate the prompt for triplet validation.

    Args:
        triplets: List of triplets to validate

    Returns:
        Formatted prompt
    """
    import json
    relations_str = ", ".join(CANONICAL_RELATIONS)
    triplets_str = json.dumps(triplets, ensure_ascii=False, indent=2)
    return TRIPLET_VALIDATION_PROMPT.format(
        canonical_relations=relations_str,
        triplets=triplets_str
    )


def get_relation_generation_prompt(concept_a: str, concept_b: str) -> str:
    """
    Generate the prompt for finding relations between two concepts.

    Args:
        concept_a: First concept
        concept_b: Second concept

    Returns:
        Formatted prompt
    """
    relations_str = ", ".join(CANONICAL_RELATIONS)
    return RELATION_GENERATION_PROMPT.format(
        canonical_relations=relations_str,
        concept_a=concept_a,
        concept_b=concept_b
    )


def get_concept_extraction_prompt(text: str) -> str:
    """
    Generate the prompt for concept extraction.

    Args:
        text: Source text

    Returns:
        Formatted prompt
    """
    return CONCEPT_EXTRACTION_PROMPT.format(text=text)


def is_canonical_relation(relation: str) -> bool:
    """
    Check if a relation is in the canonical list.

    Args:
        relation: Relation name

    Returns:
        True if canonical
    """
    return relation.lower() in [r.lower() for r in CANONICAL_RELATIONS]


def normalize_relation(relation: str) -> str:
    """
    Normalize a relation to its canonical form.

    Attempts to map non-canonical relations to equivalents.

    Args:
        relation: Relation to normalize

    Returns:
        Canonical relation or "related_to" as default
    """
    relation = relation.lower().strip()

    # Common mappings
    mappings = {
        # Causality
        "causes": "cause",
        "leads_to": "cause",
        "results_in": "cause",
        "mene_a": "cause",
        "provoque": "cause",
        "entraine": "cause",

        # Reverse causality
        "is_caused_by": "caused_by",
        "results_from": "caused_by",
        "comes_from": "caused_by",

        # Hierarchy
        "type_of": "is_a",
        "kind_of": "is_a",
        "instance_of": "is_a",
        "est_un": "is_a",
        "est_une": "is_a",

        # Composition
        "composed_of": "has_part",
        "consists_of": "has_part",
        "includes": "has_part",
        "component_of": "part_of",
        "element_of": "part_of",
        "membre_de": "part_of",

        # Similarity
        "like": "similar_to",
        "resembles": "similar_to",
        "similar": "similar_to",
        "equivalent_to": "similar_to",

        # Opposition
        "contrary_to": "opposite_of",
        "antonym_of": "opposite_of",
        "contraire_de": "opposite_of",

        # Production
        "creates": "produces",
        "generates": "produces",
        "makes": "produces",
        "outputs": "produces",
        "produit": "produces",

        # Consumption
        "uses": "consumes",
        "needs": "requires",
        "depends_on": "requires",
        "necessite": "requires",

        # Sequence
        "before": "precedes",
        "after": "follows",
        "then": "follows",
        "next": "follows",
        "avant": "precedes",
        "apres": "follows",

        # Implication
        "means": "implies",
        "suggests": "implies",
        "indicates": "implies",

        # Generic relations
        "associated_with": "related_to",
        "connected_to": "related_to",
        "linked_to": "related_to",
        "relates_to": "related_to",
        "lie_a": "related_to",
    }

    if relation in CANONICAL_RELATIONS:
        return relation

    if relation in mappings:
        return mappings[relation]

    # Fallback
    return "related_to"
