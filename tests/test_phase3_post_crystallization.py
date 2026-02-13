"""Tests Phase 3 — Post-crystallization hook."""

import asyncio
import tempfile
import os
import pytest

from services.esmm.attestation import crystallize, ModelVote, Signature5D
from services.esmm.post_crystallization import post_crystallization_hook


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_attestation(consensus=0.75, models=None):
    """Create a test attestation."""
    if models is None:
        models = ["mock-alpha", "mock-beta", "mock-gamma"]
    votes = [
        ModelVote(model_id=m, provider_id="mock", agreed=True, confidence=consensus)
        for m in models
    ]
    sig = Signature5D(
        agreement=0.8, semantic_consistency=0.9,
        centrality=0.5, stability=0.5, relation_diversity=0.6,
    )
    return crystallize(
        subject="solana",
        predicate="achieves",
        object_="high_throughput",
        consensus_score=consensus,
        model_votes=votes,
        signature_5d=sig,
        epistemic_type="foundational",
        architecture_families=2,
    )


def _make_db():
    """Create a temp ISpaceDB."""
    from database.engine import ISpaceDB
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test_hook.db")
    db = ISpaceDB(db_path)
    _run(db.initialize())
    return db


class TestPostCrystallizationHook:

    def test_hook_records_all_votes(self):
        """N votes -> N rows in model_track_record."""
        db = _make_db()
        att = _make_attestation(models=["m1", "m2", "m3"])
        _run(post_crystallization_hook(att, db))

        async def check():
            async with db.connection() as conn:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM model_track_record WHERE claim_hash = ?",
                    (att.claim_hash,)
                )
                return (await cursor.fetchone())[0]

        count = _run(check())
        assert count == 3

    def test_hook_logs_tier_transition(self):
        """Different tier -> transition row in tier_transitions."""
        db = _make_db()
        att = _make_attestation()

        async def count_before():
            async with db.connection() as conn:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM tier_transitions WHERE claim_hash = ?",
                    (att.claim_hash,)
                )
                return (await cursor.fetchone())[0]

        before = _run(count_before())
        _run(post_crystallization_hook(att, db, previous_tier="sandbox"))

        async def count_after():
            async with db.connection() as conn:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM tier_transitions WHERE claim_hash = ?",
                    (att.claim_hash,)
                )
                return (await cursor.fetchone())[0]

        after = _run(count_after())
        # att has consensus=0.75, 3 models, 2 arch families -> "validated"
        # previous_tier="sandbox" != "validated" -> transition logged
        assert after > before

    def test_hook_no_transition_if_same_tier(self):
        """Same tier -> no new rows in tier_transitions."""
        db = _make_db()
        att = _make_attestation()
        actual_tier = att.confidence_tier

        async def count_before():
            async with db.connection() as conn:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM tier_transitions WHERE claim_hash = ?",
                    (att.claim_hash,)
                )
                return (await cursor.fetchone())[0]

        before = _run(count_before())
        _run(post_crystallization_hook(att, db, previous_tier=actual_tier))

        async def count_after():
            async with db.connection() as conn:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM tier_transitions WHERE claim_hash = ?",
                    (att.claim_hash,)
                )
                return (await cursor.fetchone())[0]

        after = _run(count_after())
        assert after == before

    def test_hook_handles_db_error_gracefully(self):
        """DB error -> warning, no crash."""
        # Use a mock that raises on all DB ops
        from unittest.mock import AsyncMock, MagicMock
        db = MagicMock()
        db.record_model_prediction = AsyncMock(side_effect=Exception("DB error"))
        db.log_tier_transition = AsyncMock(side_effect=Exception("DB error"))
        att = _make_attestation()
        # Should not raise
        _run(post_crystallization_hook(att, db, previous_tier="sandbox"))
