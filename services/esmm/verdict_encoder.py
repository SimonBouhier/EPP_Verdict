"""
ESMM Verdict Encoder — Encode VERIFY-mode verdicts as consensus-ready triplets.

Transforms LLM verdict responses into triplet format compatible with
the existing ConsensusEngine pipeline. This allows VERIFY mode to reuse
the entire crystallization and attestation chain without modifications.

Encoding strategy (Directive §2.5):
    claim_hash -> verdict -> SUPPORTED    (confidence: 0.85)
    claim_hash -> evidence -> "evidence text" (confidence: 0.7)
"""
from __future__ import annotations

from typing import Dict, Any, List


def encode_verdict_as_triplets(
    claim: str,
    verdict_response: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Encode a verdict response as consensus-ready triplets.

    Args:
        claim: Original claim text (used as subject)
        verdict_response: Dict with verdict, confidence, evidence, reasoning

    Returns:
        List of triplet dicts with subject, relation, object, confidence
    """
    triplets = []

    verdict = verdict_response.get("verdict", "INSUFFICIENT_EVIDENCE")
    confidence = float(verdict_response.get("confidence", 0.0))

    # Truncate subject to 64 chars (attestation field limit).
    # Full claim is preserved in consensus_meta["verify"]["original_claim"].
    subject = claim[:64]

    # 1. Verdict triplet
    triplets.append({
        "subject": subject,
        "relation": "verdict",
        "object": verdict,
        "confidence": confidence,
    })

    # 2. Evidence triplets
    for ev in verdict_response.get("evidence", []):
        if isinstance(ev, dict) and "subject" in ev and "object" in ev:
            triplets.append({
                "subject": ev.get("subject", ""),
                "relation": ev.get("relation", "related_to"),
                "object": ev.get("object", ""),
                "confidence": float(ev.get("confidence", 0.5)),
            })

    # 3. Reasoning as triplet (if present)
    reasoning = verdict_response.get("reasoning", "")
    if reasoning:
        triplets.append({
            "subject": subject,
            "relation": "reasoning",
            "object": reasoning[:500],  # Truncate long reasoning
            "confidence": confidence,
        })

    return triplets
