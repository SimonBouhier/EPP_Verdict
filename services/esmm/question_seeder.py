"""
Seed graph from user question (D7).

When the graph is empty, the user's question is decomposed into concepts
and injected as seeds to bootstrap the exploration.
"""

import logging
import re
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from database.engine import ISpaceDB

logger = logging.getLogger("esmm.question_seeder")

# Stop words (English + French basics)
STOP_WORDS = frozenset({
    # English
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "must", "need",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "about", "against", "over", "under",
    "and", "but", "or", "nor", "not", "no", "so", "if", "than", "that",
    "this", "these", "those", "it", "its",
    "what", "which", "who", "whom", "how", "when", "where", "why",
    "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "such", "only", "very", "just", "also", "then",
    # French
    "le", "la", "les", "un", "une", "des", "du", "de", "et", "ou",
    "est", "sont", "que", "qui", "dans", "sur", "par", "pour", "avec",
    "ce", "cette", "ces", "ne", "pas", "plus", "se",
})


def extract_seed_concepts(question: str) -> List[str]:
    """
    Extract seed concepts from a question string.

    Tokenizes the question, removes stop words, normalizes to lowercase,
    and keeps words of 2+ characters.

    Args:
        question: User question string

    Returns:
        List of normalized concept strings
    """
    # Tokenize: keep alphanumeric words
    tokens = re.findall(r"[a-zA-Z0-9]+", question)

    # Normalize, filter stop words and short tokens
    concepts = []
    seen = set()
    for token in tokens:
        normalized = token.lower()
        if normalized not in STOP_WORDS and len(normalized) >= 2 and normalized not in seen:
            concepts.append(normalized)
            seen.add(normalized)

    return concepts


async def seed_graph_from_question(
    db: "ISpaceDB",
    question: str,
) -> int:
    """
    Seed the graph with concepts from the question if graph is empty.

    Args:
        db: Database instance
        question: User question

    Returns:
        Number of concepts injected (0 if graph was not empty)
    """
    stats = await db.get_stats()
    if stats.get("concepts", 0) > 0:
        return 0

    concepts = extract_seed_concepts(question)
    if not concepts:
        return 0

    injected = 0
    for concept in concepts:
        try:
            await db.add_concept(
                concept_id=concept,
                source="question_seed",
            )
            injected += 1
        except Exception as e:
            logger.warning(f"Failed to seed concept '{concept}': {e}")

    if injected > 0:
        logger.info(f"Seeded graph with {injected} concepts from question")

    return injected
