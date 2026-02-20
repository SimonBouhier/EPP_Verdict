"""
ADR-011-v2 — Phase EXPAND : prompt, JSON parser, expand_terms() async.

Sprint 1.3: MicroGraph dataclass, build_expand_prompt(), parse_expand_response()
Sprint 2.6: expand_terms() async orchestration
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class MicroGraph:
    """A model's description of a term via its neighborhood."""

    term: str
    model_id: str
    neighbors: List[Tuple[str, str]]  # [(relation, neighbor_concept)]


@dataclass
class ExpandResult:
    """Aggregated result of the EXPAND phase across all models."""

    micro_graphs: Dict[str, Dict[str, MicroGraph]]  # model_id → term → MicroGraph
    terms_fingerprinted: int
    models_participated: List[str]
    duration_ms: float
    parse_failures: int


# ============================================================================
# PROMPT
# ============================================================================

_EXPAND_PROMPT_TEMPLATE = """You extracted the following terms: {terms_list}

For EACH term, provide 3-5 directly related concepts with the relationship type.
Use ONLY these relationship types: is_a, part_of, used_by, produces, related_to, invented_by

Output ONLY valid JSON with this exact format (no markdown, no explanation):
{{"term_name": [["relationship", "concept"], ...], ...}}"""


def build_expand_prompt(terms: List[str]) -> str:
    """Build the EXPAND prompt for a list of terms."""
    terms_list = ", ".join(terms)
    return _EXPAND_PROMPT_TEMPLATE.format(terms_list=terms_list)


# ============================================================================
# PARSER
# ============================================================================

def parse_expand_response(text: str, model_id: str) -> Dict[str, MicroGraph]:
    """Parse a model's EXPAND response into MicroGraph objects.

    Resilient: invalid JSON → empty dict, invalid entries skipped.
    Never raises exceptions.
    """
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        # Try to extract JSON from markdown code blocks
        try:
            import re
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
            else:
                logger.debug(f"[EXPAND] Failed to parse JSON from {model_id}")
                return {}
        except (json.JSONDecodeError, TypeError):
            return {}

    if not isinstance(data, dict):
        return {}

    result: Dict[str, MicroGraph] = {}

    for term, neighbors_raw in data.items():
        if not isinstance(neighbors_raw, list):
            continue

        valid_neighbors: List[Tuple[str, str]] = []
        for pair in neighbors_raw:
            if (
                isinstance(pair, (list, tuple))
                and len(pair) == 2
                and isinstance(pair[0], str)
                and isinstance(pair[1], str)
            ):
                valid_neighbors.append((pair[0], pair[1]))

        if not valid_neighbors:
            continue

        result[term] = MicroGraph(
            term=term,
            model_id=model_id,
            neighbors=valid_neighbors,
        )

    return result


# ============================================================================
# EXPAND_TERMS — ASYNC ORCHESTRATION
# ============================================================================

def _extract_unique_terms(triplets: List) -> List[str]:
    """Extract unique terms (subjects + objects) from a list of triplet dicts."""
    terms = set()
    for t in triplets:
        if isinstance(t, dict):
            s = t.get("subject", "").strip()
            o = t.get("object", "").strip()
            if s:
                terms.add(s)
            if o:
                terms.add(o)
    return sorted(terms)


async def expand_terms(
    model_triplets: Dict[str, List],
    rotator,
    provider_ids: List[str],
    provider_to_model: Dict[str, str],
    config,
) -> ExpandResult:
    """Phase EXPAND: each model describes its own terms via micro-graphs.

    Each model only receives its OWN terms (zero inter-model visibility).
    Uses rotator.batch_sequential_providers() for LLM calls.
    """
    start = time.time()
    all_micro_graphs: Dict[str, Dict[str, MicroGraph]] = {}
    parse_failures = 0
    models_participated = []
    all_terms = set()

    # Build per-model term lists and prompts
    per_model_terms: Dict[str, List[str]] = {}
    for provider_id in provider_ids:
        model_id = provider_to_model.get(provider_id, provider_id)
        triplets = model_triplets.get(model_id, [])
        terms = _extract_unique_terms(triplets)
        if terms:
            per_model_terms[provider_id] = terms
            all_terms.update(terms)

    if not per_model_terms:
        return ExpandResult(
            micro_graphs={},
            terms_fingerprinted=0,
            models_participated=[],
            duration_ms=0.0,
            parse_failures=0,
        )

    # Build one prompt per model (each with its own terms)
    prompts = {pid: build_expand_prompt(terms) for pid, terms in per_model_terms.items()}

    # Call each model individually (zero inter-model contamination)
    for provider_id, terms in per_model_terms.items():
        prompt = prompts[provider_id]
        try:
            batch_result = await rotator.batch_sequential_providers(
                provider_ids=[provider_id],
                questions=[[{"role": "user", "content": prompt}]],
            )
        except Exception as e:
            logger.warning(f"[EXPAND] Failed for {provider_id}: {e}")
            parse_failures += 1
            continue

        # Parse response
        model_id = provider_to_model.get(provider_id, provider_id)
        responses = batch_result.results.get(provider_id, [])

        if not responses or not responses[0].success:
            parse_failures += 1
            continue

        text = responses[0].text
        parsed = parse_expand_response(text, model_id=model_id)

        if not parsed:
            parse_failures += 1
            continue

        all_micro_graphs[model_id] = parsed
        models_participated.append(model_id)

    duration_ms = (time.time() - start) * 1000

    return ExpandResult(
        micro_graphs=all_micro_graphs,
        terms_fingerprinted=len(all_terms),
        models_participated=models_participated,
        duration_ms=duration_ms,
        parse_failures=parse_failures,
    )
