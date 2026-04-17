# tests/test_phase03_storage.py
"""
Phase 0.3.3 Tests — Attestation Storage

Tests for:
- store_attestation stores and retrieves correctly
- Signature 5D components are preserved
- Model votes are stored as JSON and parsed
- get_attestations_by_subject filters correctly
- get_attestation_history returns all validations
- Table attestations exists after initialize
"""

import pytest
import time
import json
from pathlib import Path

from database.engine import ISpaceDB
from services.esmm.attestation import (
    crystallize, Signature5D, ModelVote, EpistemicAttestation,
)


# ============================================================================
# HELPERS
# ============================================================================

async def create_fresh_db(db_path: str) -> ISpaceDB:
    db = ISpaceDB(db_path)
    await db.initialize()
    return db


async def cleanup_db(db: ISpaceDB):
    if db._pool:
        from database.pool import close_pool
        await close_pool()


def make_test_attestation(
    subject: str = "Solana",
    predicate: str = "has_property",
    object_: str = "high_tps",
    consensus: float = 0.85,
    frame: str = None,
) -> EpistemicAttestation:
    """Crée une attestation de test."""
    return crystallize(
        subject=subject,
        predicate=predicate,
        object_=object_,
        consensus_score=consensus,
        model_votes=[
            ModelVote(model_id="m1", provider_id="mock", agreed=True, confidence=0.9),
            ModelVote(model_id="m2", provider_id="mock", agreed=True, confidence=0.8),
            ModelVote(model_id="m3", provider_id="mock", agreed=False, confidence=0.3),
        ],
        signature_5d=Signature5D(
            agreement=0.8, semantic_consistency=0.75,
            centrality=0.6, stability=0.7, relation_diversity=0.5,
        ),
        epistemic_type="foundational",
        run_id=1,
        question="Test question",
        metrological_frame=frame,
        architecture_families=2,
    )


# ============================================================================
# TESTS
# ============================================================================

class TestStoreAttestation:
    """Tests pour store_attestation."""

    async def test_store_and_retrieve(self, tmp_path):
        """store_attestation stocke et get_attestation_by_hash retrouve."""
        db = await create_fresh_db(str(tmp_path / "test.db"))
        try:
            att = make_test_attestation()
            att_id = await db.store_attestation(att.model_dump())

            assert att_id is not None
            assert att_id > 0

            retrieved = await db.get_attestation_by_hash(att.claim_hash)
            assert retrieved is not None
            assert retrieved["subject"] == "Solana"
            assert retrieved["predicate"] == "has_property"
            assert retrieved["consensus_score"] == 0.85
            assert retrieved["confidence_tier"] == "validated"
        finally:
            await cleanup_db(db)

    async def test_store_preserves_signature_5d(self, tmp_path):
        """Les 5 composantes de la signature sont stockées et récupérées."""
        db = await create_fresh_db(str(tmp_path / "test.db"))
        try:
            att = make_test_attestation()
            await db.store_attestation(att.model_dump())

            retrieved = await db.get_attestation_by_hash(att.claim_hash)
            assert retrieved["sig_agreement"] == 0.8
            assert retrieved["sig_semantic_consistency"] == 0.75
            assert retrieved["sig_centrality"] == 0.6
            assert retrieved["sig_stability"] == 0.7
            assert retrieved["sig_relation_diversity"] == 0.5
        finally:
            await cleanup_db(db)

    async def test_store_preserves_model_votes(self, tmp_path):
        """Les votes des modèles sont stockés et parsés en JSON."""
        db = await create_fresh_db(str(tmp_path / "test.db"))
        try:
            att = make_test_attestation()
            await db.store_attestation(att.model_dump())

            retrieved = await db.get_attestation_by_hash(att.claim_hash)
            votes = retrieved["model_votes"]
            assert isinstance(votes, list)
            assert len(votes) == 3
            assert votes[0]["model_id"] == "m1"
        finally:
            await cleanup_db(db)


class TestQueryAttestations:
    """Tests pour les requêtes d'attestations."""

    async def test_get_by_subject(self, tmp_path):
        """get_attestations_by_subject filtre correctement."""
        db = await create_fresh_db(str(tmp_path / "test.db"))
        try:
            # 3 attestations Solana, 1 Ethereum
            for pred in ["has_property", "is_a", "supports"]:
                att = make_test_attestation(predicate=pred)
                await db.store_attestation(att.model_dump())

            att_eth = make_test_attestation(subject="Ethereum", predicate="is_a")
            await db.store_attestation(att_eth.model_dump())

            results = await db.get_attestations_by_subject("Solana")
            assert len(results) == 3

            results_eth = await db.get_attestations_by_subject("Ethereum")
            assert len(results_eth) == 1
        finally:
            await cleanup_db(db)

    async def test_get_by_subject_min_consensus(self, tmp_path):
        """get_attestations_by_subject respecte min_consensus."""
        db = await create_fresh_db(str(tmp_path / "test.db"))
        try:
            att_high = make_test_attestation(consensus=0.9)
            att_low = make_test_attestation(predicate="causes", consensus=0.3)
            await db.store_attestation(att_high.model_dump())
            await db.store_attestation(att_low.model_dump())

            results = await db.get_attestations_by_subject("Solana", min_consensus=0.5)
            assert len(results) == 1
            assert results[0]["consensus_score"] == 0.9
        finally:
            await cleanup_db(db)

    async def test_get_nonexistent_hash(self, tmp_path):
        """get_attestation_by_hash retourne None pour un hash inexistant."""
        db = await create_fresh_db(str(tmp_path / "test.db"))
        try:
            result = await db.get_attestation_by_hash("a" * 64)
            assert result is None
        finally:
            await cleanup_db(db)


class TestAttestationHistory:
    """Tests pour l'historique de revalidation."""

    async def test_history_returns_all_validations(self, tmp_path):
        """get_attestation_history retourne toutes les attestations d'un même claim."""
        db = await create_fresh_db(str(tmp_path / "test.db"))
        try:
            # Première validation
            att1 = make_test_attestation(consensus=0.7)
            await db.store_attestation(att1.model_dump())

            # Revalidation (même triplet → même hash)
            att2 = make_test_attestation(consensus=0.85)
            await db.store_attestation(att2.model_dump())

            history = await db.get_attestation_history(att1.claim_hash)
            assert len(history) == 2
            # Triées par timestamp ASC
            assert history[0]["timestamp"] <= history[1]["timestamp"]
        finally:
            await cleanup_db(db)


class TestTableExists:
    """Tests structurels."""

    async def test_attestations_table_exists(self, tmp_path):
        """La table attestations existe après initialize()."""
        db = await create_fresh_db(str(tmp_path / "test.db"))
        try:
            async with db.connection() as conn:
                cursor = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='attestations'"
                )
                row = await cursor.fetchone()
                assert row is not None
        finally:
            await cleanup_db(db)
