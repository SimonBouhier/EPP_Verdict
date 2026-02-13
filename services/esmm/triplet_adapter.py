"""Adaptateur ConsensusTriplet -> dict exploitable par le pipeline."""

from typing import List, Dict, Any, Optional
from .consensus_engine import ConsensusTriplet


def adapt_consensus_triplet(
    triplet: ConsensusTriplet,
    cochain_entry: Optional[dict] = None,
    epistemic_type: str = "foundational",
) -> Dict[str, Any]:
    """
    Convertit un ConsensusTriplet en dict exploitable par le pipeline.

    Conversions :
    - relation -> predicate
    - contributing_models -> votes (enrichi avec provider_id, agreed, confidence)
    - signature_5d calculee ou recuperee de la 0-cochaine
    - epistemic_type derive ou passe en parametre
    """
    votes = []
    for model_name in triplet.contributing_models:
        try:
            from services.providers.base import infer_architecture_family
            family = infer_architecture_family(model_name)
        except ImportError:
            family = "unknown"

        votes.append({
            "model_id": model_name,
            "provider_id": _infer_provider_id(model_name),
            "agreed": True,
            "confidence": triplet.avg_confidence,
            "architecture_family": family,
        })

    # Signature 5D
    if cochain_entry and "signature_5d" in cochain_entry:
        sig_5d = cochain_entry["signature_5d"]
    else:
        families = set(v["architecture_family"] for v in votes)
        sig_5d = {
            "agreement": triplet.agreement_ratio,
            "semantic_consistency": 1.0 - triplet.std_confidence,
            "centrality": 0.5,
            "stability": 0.5,
            "relation_diversity": len(families) / max(len(votes), 1),
        }

    return {
        "subject": triplet.subject,
        "predicate": triplet.relation,
        "object": triplet.object,
        "consensus_score": triplet.consensus_score,
        "votes": votes,
        "signature_5d": sig_5d,
        "epistemic_type": epistemic_type,
        "triplet_hash": triplet.triplet_hash,
    }


def _infer_provider_id(model_name: str) -> str:
    if "::" in model_name:
        return model_name.split("::")[0]
    return "ollama"


def adapt_all(
    triplets: List[ConsensusTriplet],
    cochain_entries: Optional[List[dict]] = None,
) -> List[Dict[str, Any]]:
    """Adapte une liste de ConsensusTriplet."""
    entries_map = {}
    if cochain_entries:
        for entry in cochain_entries:
            entries_map[entry.get("triplet_hash", "")] = entry

    return [
        adapt_consensus_triplet(t, cochain_entry=entries_map.get(t.triplet_hash))
        for t in triplets
    ]
