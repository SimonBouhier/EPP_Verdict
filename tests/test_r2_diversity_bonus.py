"""
Tests R-2.2.1 — Diversité architecturale dans le consensus.

RED-GREEN-FIX : ces tests DOIVENT échouer avant implémentation.

Vérifie que :
1. Multi-famille → diversity_bonus_factor = 1.1, adjusted_consensus_score > consensus_score
2. Mono-famille → diversity_bonus_factor = 1.0, adjusted = consensus
3. consensus_score et confidence_tier restent immuables (ADR-005/007)
"""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib

import pytest

from services.esmm.attestation import (
    EpistemicAttestation,
    Signature5D,
    ModelVote,
    crystallize,
)
from services.providers.base import infer_architecture_family


def _make_attestation(model_ids: list[str], consensus_score: float = 0.75) -> EpistemicAttestation:
    """Helper : crée une attestation avec les modèles donnés."""
    votes = [
        ModelVote(
            model_id=m,
            provider_id="ollama",
            agreed=True,
            confidence=consensus_score,
        )
        for m in model_ids
    ]
    families = set(infer_architecture_family(m) for m in model_ids)

    return crystallize(
        subject="Python",
        predicate="is_a",
        object_="programming language",
        consensus_score=consensus_score,
        model_votes=votes,
        signature_5d=Signature5D(
            agreement=consensus_score,
            semantic_consistency=0.5,
            centrality=0.5,
            stability=0.5,
            relation_diversity=len(families) / max(len(votes), 1),
        ),
        epistemic_type="foundational",
        architecture_families=len(families),
    )


class TestDiversityBonusMultiFamily:
    """R-2.2.1 RED 1 — Multi-famille produit un bonus."""

    @pytest.mark.asyncio
    async def test_diversity_bonus_with_multiple_families(self, tmp_path):
        """Triplet confirmé par 2+ familles → adjusted_score > consensus_score."""
        from database.engine import ISpaceDB
        from database.pool import close_pool
        from services.esmm.post_crystallization import post_crystallization_hook

        db = ISpaceDB(str(tmp_path / "test_multi.db"))
        await db.initialize()
        try:
            # mistral = transformer_dense, mixtral = transformer_moe → 2 familles
            att = _make_attestation(["mistral:7b", "mixtral:8x7b"], consensus_score=0.75)

            att_dict = att.model_dump()
            att_dict["portable_json"] = att.to_portable_json()
            att_id = await db.store_attestation(att_dict)

            await post_crystallization_hook(att, db)

            # Vérifier en DB
            stored = await db.get_attestation_by_hash(att.claim_hash)
            assert stored is not None

            assert stored["diversity_bonus_factor"] == 1.1, (
                f"Multi-famille devrait donner factor=1.1, got {stored.get('diversity_bonus_factor')}"
            )
            expected_adjusted = min(att.consensus_score * 1.1, 1.0)
            assert abs(stored["adjusted_consensus_score"] - expected_adjusted) < 1e-4, (
                f"adjusted={stored.get('adjusted_consensus_score')}, expected={expected_adjusted}"
            )
        finally:
            await close_pool()


class TestDiversityBonusMonoFamily:
    """R-2.2.1 RED 2 — Mono-famille = pas de bonus."""

    @pytest.mark.asyncio
    async def test_no_bonus_single_family(self, tmp_path):
        """Tous les modèles de la même famille → factor == 1.0."""
        from database.engine import ISpaceDB
        from database.pool import close_pool
        from services.esmm.post_crystallization import post_crystallization_hook

        db = ISpaceDB(str(tmp_path / "test_mono.db"))
        await db.initialize()
        try:
            # mistral + llama = les deux sont transformer_dense → 1 famille
            att = _make_attestation(["mistral:7b", "llama3:8b"], consensus_score=0.75)

            att_dict = att.model_dump()
            att_dict["portable_json"] = att.to_portable_json()
            att_id = await db.store_attestation(att_dict)

            await post_crystallization_hook(att, db)

            stored = await db.get_attestation_by_hash(att.claim_hash)
            assert stored is not None

            assert stored["diversity_bonus_factor"] == 1.0, (
                f"Mono-famille devrait donner factor=1.0, got {stored.get('diversity_bonus_factor')}"
            )
            assert abs(stored["adjusted_consensus_score"] - att.consensus_score) < 1e-4
        finally:
            await close_pool()


class TestConsensusScoreUnchanged:
    """R-2.2.1 RED 3 — consensus_score original inchangé (ADR-005/007)."""

    @pytest.mark.asyncio
    async def test_consensus_score_unchanged_by_diversity(self, tmp_path):
        """Le consensus_score et le confidence_tier ne changent pas."""
        from database.engine import ISpaceDB
        from database.pool import close_pool
        from services.esmm.post_crystallization import post_crystallization_hook

        db = ISpaceDB(str(tmp_path / "test_adr.db"))
        await db.initialize()
        try:
            att = _make_attestation(["mistral:7b", "mixtral:8x7b"], consensus_score=0.75)
            original_score = att.consensus_score
            original_tier = att.confidence_tier

            att_dict = att.model_dump()
            att_dict["portable_json"] = att.to_portable_json()
            att_id = await db.store_attestation(att_dict)

            await post_crystallization_hook(att, db)

            stored = await db.get_attestation_by_hash(att.claim_hash)
            assert stored is not None

            # consensus_score DOIT rester identique (ADR-005/007)
            assert abs(stored["consensus_score"] - original_score) < 1e-6, (
                f"consensus_score modifié ! original={original_score}, "
                f"stored={stored['consensus_score']}"
            )
            assert stored["confidence_tier"] == original_tier, (
                f"confidence_tier modifié ! original={original_tier}, "
                f"stored={stored['confidence_tier']}"
            )
        finally:
            await close_pool()


# ─────────────────────────────────────────────────────────────────────────
# Single-file runner — `python tests/<this_file>.py`
# Génère un rapport horodaté dans `test_results/individual/`.
# Cf. `tests/_runner.py::run_self` pour le détail.
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from tests._runner import run_self
    raise SystemExit(run_self(__file__))
