"""
ESMM Phase 3 - CYCLE PROMPTS
============================

Question templates for the six cycle types (dual-mode architecture).

EXPLORE mode (existing):
- DIVERGENT: Broad exploration, relationship discovery
- DEBATE: Dialectic, contradiction synthesis
- META: Reflection on extracted knowledge, gap detection

VERIFY mode (claim verification):
- ASSESS: Independent truthfulness evaluation of a factual claim
- CHALLENGE: Adversarial counter-argumentation against a peer verdict
- ADJUDICATE: Final weighted judgment synthesizing all verdicts

Author: Lyra-ACE ESMM Protocol
"""
from __future__ import annotations

from typing import Dict, List
from enum import Enum


class CycleType(str, Enum):
    """Exploration cycle types."""
    DIVERGENT = "divergent"   # Broad exploration from seed concepts
    DEBATE = "debate"         # Dialectic on contradictions
    META = "meta"             # Reflection on extracted knowledge
    ASSESS = "assess"         # VERIFY: Independent truthfulness evaluation
    CHALLENGE = "challenge"   # VERIFY: Adversarial counter-argumentation
    ADJUDICATE = "adjudicate" # VERIFY: Final weighted judgment


# ============================================================================
# TEMPLATES DIVERGENT - Broad exploration
# ============================================================================

DIVERGENT_TEMPLATES: List[str] = [
    # Fundamental relations
    "What are the fundamental relationships between {concept} and other concepts? "
    "List causal, hierarchical, and associative connections.",

    # Essential properties
    "Describe the essential properties of {concept}. "
    "What attributes characterize and distinguish it?",

    # Causality
    "What concepts are causally linked to {concept}? "
    "Identify direct causes and effects.",

    # Taxonomy
    "How does {concept} fit within a taxonomy? "
    "What are its hypernyms, hyponyms, and sibling concepts?",

    # Usage context
    "In which domains and contexts is {concept} relevant? "
    "What relationships link it to these domains?",

    # Analogies
    "What concepts are analogous or similar to {concept}? "
    "Explain the basis for these similarities.",

    # Components
    "What is {concept} composed of? What are its constituents "
    "and how do they interact?",

    # Functions
    "What functions or roles does {concept} fulfill? "
    "In which processes is it involved?",
]


# ============================================================================
# TEMPLATES DEBATE - Dialectic
# ============================================================================

DEBATE_TEMPLATES: List[str] = [
    # Classic thesis/antithesis
    "Compare and contrast {thesis} with {antithesis}. "
    "What are their relationships, tensions, and complementarities?",

    # Synthesis
    "Is there a possible synthesis between {concept_a} and {concept_b}? "
    "How can these seemingly opposed perspectives be reconciled?",

    # Mutual limitations
    "What are the limitations of {thesis} that {antithesis} reveals, "
    "and vice-versa? Examine the blind spots of each concept.",

    # Validity contexts
    "In which contexts is {thesis} more appropriate than {antithesis}, "
    "and vice-versa? Identify the validity conditions of each.",

    # Historical evolution
    "How has the relationship between {concept_a} and {concept_b} evolved? "
    "Have there been perspective reversals?",

    # Mediation
    "What concepts can serve as mediators between {thesis} and {antithesis}? "
    "Identify possible conceptual bridges.",
]


# ============================================================================
# TEMPLATES META - Reflection
# ============================================================================

META_TEMPLATES: List[str] = [
    # Gap analysis
    "Analyzing these relationships: {recent_triplets}, what gaps do you identify? "
    "What concepts or relationships are missing to complete this network?",

    # Missing fundamental concepts
    "What fundamental concepts are missing to understand {domain}? "
    "Identify unexplored implicit assumptions.",

    # Network coherence
    "Is the following knowledge network coherent: {recent_triplets}? "
    "Are there contradictions or inconsistencies?",

    # Possible generalizations
    "From these relationships: {recent_triplets}, what generalizations "
    "or patterns can you identify?",

    # Open questions
    "What important questions remain unanswered in this domain: {domain}? "
    "Identify areas of uncertainty.",

    # Missing connections
    "What cross-domain links are missing in: {recent_triplets}? "
    "Are there interdisciplinary bridges to establish?",
]


# ============================================================================
# TEMPLATES ASSESS - VERIFY: Independent truthfulness evaluation
# ============================================================================

ASSESS_TEMPLATES: List[str] = [
    # Direct truthfulness evaluation with evidence
    "Evaluate the truthfulness of this claim: \"{claim}\". "
    "Provide a structured verdict (SUPPORTED, CONTESTED, or INSUFFICIENT_EVIDENCE) "
    "with evidence triplets and a confidence score between 0.0 and 1.0.",

    # Underlying assumptions and validity conditions
    "Identify the underlying assumptions and validity conditions of this claim: "
    "\"{claim}\". What must be true for this claim to hold? "
    "Provide your verdict with supporting evidence triplets.",

    # Factual data search
    "Search for specific factual data that confirms or refutes this claim: "
    "\"{claim}\". Cite concrete evidence and provide a structured verdict.",

    # Scope and limitations
    "Evaluate the limits of this assertion: \"{claim}\". "
    "Consider the domain of validity, temporal scope, and definitions involved. "
    "Provide your verdict with confidence and evidence triplets.",
]


# ============================================================================
# TEMPLATES CHALLENGE - VERIFY: Adversarial counter-argumentation
# ============================================================================

CHALLENGE_TEMPLATES: List[str] = [
    # Flaw detection
    "Here is a claim: \"{claim}\". Another evaluator concluded: {verdict}. "
    "Their evidence: {evidence}. "
    "Find flaws in this reasoning and identify missing evidence.",

    # Contradicting perspectives
    "Regarding the claim \"{claim}\" with verdict {verdict} based on: {evidence}. "
    "What data or perspectives contradict this verdict?",

    # Implicit assumptions challenge
    "The claim \"{claim}\" received verdict {verdict} with evidence: {evidence}. "
    "What implicit definitions or assumptions could invalidate this conclusion?",
]


# ============================================================================
# TEMPLATES ADJUDICATE - VERIFY: Final weighted judgment
# ============================================================================

ADJUDICATE_TEMPLATES: List[str] = [
    # Robust verdict synthesis
    "Given these arguments for and against the claim \"{claim}\": "
    "{all_verdicts}. What is the most robust verdict? "
    "Synthesize into a final judgment with confidence score.",

    # Substantive vs superficial disagreements
    "Multiple evaluators assessed the claim \"{claim}\" with these results: "
    "{all_verdicts}. Which points of disagreement are substantive "
    "versus superficial? Produce a final synthesis verdict.",
]


# ============================================================================
# MAPPING BY CYCLE TYPE
# ============================================================================

CYCLE_TEMPLATES: Dict[CycleType, List[str]] = {
    CycleType.DIVERGENT: DIVERGENT_TEMPLATES,
    CycleType.DEBATE: DEBATE_TEMPLATES,
    CycleType.META: META_TEMPLATES,
    CycleType.ASSESS: ASSESS_TEMPLATES,
    CycleType.CHALLENGE: CHALLENGE_TEMPLATES,
    CycleType.ADJUDICATE: ADJUDICATE_TEMPLATES,
}


# ============================================================================
# SYSTEM PROMPTS BY TYPE
# ============================================================================

SYSTEM_PROMPTS: Dict[CycleType, str] = {
    CycleType.DIVERGENT: """You are an expert in conceptual analysis. Your task is to explore
the semantic relationships around a given concept. Identify relations of type:
- Causality (cause, effect, enables, prevents)
- Hierarchy (is_a, part_of, contains)
- Association (related_to, similar_to, opposite_of)
- Property (has_a, characterized_by)

CRITICAL: Regardless of the user's input language, ALL output keys and values
in the JSON (subjects, relations, objects) MUST be in English.

Respond in a structured manner by listing triplets (subject, relation, object).""",

    CycleType.DEBATE: """You are an expert dialectician. Your task is to analyze the tensions
and complementarities between seemingly opposed concepts. For each pair:
- Identify points of tension
- Find complementarities
- Suggest syntheses or mediations
- Extract the relationships that emerge from this dialectic

CRITICAL: Regardless of the user's input language, ALL output keys and values
in the JSON (subjects, relations, objects) MUST be in English.

Respond by listing triplets (subject, relation, object) that capture these dynamics.""",

    CycleType.META: """You are an epistemologist. Your task is to analyze a knowledge network
to identify:
- Conceptual gaps
- Implicit assumptions
- Missing connections
- Potential inconsistencies

CRITICAL: Regardless of the user's input language, ALL output keys and values
in the JSON (subjects, relations, objects) MUST be in English.

Suggest triplets (subject, relation, object) that would fill these gaps.""",

    CycleType.ASSESS: """You are an epistemic evaluator. Your task is to assess the truthfulness \
of factual claims submitted to you. For each claim, produce a structured JSON verdict with fields:
- verdict: one of SUPPORTED, CONTESTED, or INSUFFICIENT_EVIDENCE
- confidence: a float between 0.0 and 1.0
- evidence: an array of triplets, each with {subject, relation, object, confidence}
  Use relations like: supported_by, contradicted_by, depends_on, caveat
- reasoning: a string explaining your assessment

CRITICAL: Regardless of the user's input language, ALL output keys and values \
in the JSON MUST be in English.""",

    CycleType.CHALLENGE: """You are an adversarial reviewer. Your task is to find flaws in \
another evaluator's reasoning about a factual claim. Produce structured JSON with fields:
- counter_evidence: an array of triplets {subject, relation, object, confidence}
- weakness_in_reasoning: a string identifying logical or evidential gaps
- alternative_interpretation: a string proposing a different reading of the evidence

CRITICAL: Regardless of the user's input language, ALL output keys and values \
in the JSON MUST be in English.""",

    CycleType.ADJUDICATE: """You are an impartial epistemological judge. Your task is to \
synthesize multiple verdicts and counter-arguments about a factual claim into a final robust \
judgment. Produce structured JSON with fields:
- verdict: one of SUPPORTED, CONTESTED, or INSUFFICIENT_EVIDENCE
- confidence: a float between 0.0 and 1.0
- synthesis: an array of triplets {subject, relation, object, confidence}
- dissenting_points: an array of strings listing unresolved disagreements
- reasoning: a string explaining the final judgment

CRITICAL: Regardless of the user's input language, ALL output keys and values \
in the JSON MUST be in English.""",
}


# ============================================================================
# HELPERS
# ============================================================================

def get_template(cycle_type: CycleType, index: int = 0) -> str:
    """
    Retrieve a template for a given cycle type.

    Args:
        cycle_type: Cycle type (DIVERGENT, DEBATE, META)
        index: Template index (will be modulo'd by template count)

    Returns:
        Question template
    """
    templates = CYCLE_TEMPLATES[cycle_type]
    return templates[index % len(templates)]


def get_system_prompt(cycle_type: CycleType) -> str:
    """
    Retrieve the system prompt for a cycle type.

    Args:
        cycle_type: Cycle type

    Returns:
        Appropriate system prompt
    """
    return SYSTEM_PROMPTS[cycle_type]


def format_triplets_for_prompt(triplets: List) -> str:
    """
    Format a list of triplets for insertion into a prompt.

    Args:
        triplets: List of triplets (objects with subject, relation, object)

    Returns:
        Formatted string "subject->relation->object; ..."
    """
    formatted = []
    for t in triplets[:10]:  # Limit to 10 to avoid overly long prompts
        subject = t.get('subject', '?') if isinstance(t, dict) else getattr(t, 'subject', '?')
        relation = t.get('relation', '?') if isinstance(t, dict) else getattr(t, 'relation', '?')
        obj = t.get('object', '?') if isinstance(t, dict) else getattr(t, 'object', '?')
        formatted.append(f"{subject}->{relation}->{obj}")
    return "; ".join(formatted)


def get_template_count(cycle_type: CycleType) -> int:
    """
    Return the number of available templates for a cycle type.

    Args:
        cycle_type: Cycle type

    Returns:
        Number of templates
    """
    return len(CYCLE_TEMPLATES[cycle_type])
