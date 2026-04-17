"""
Tests R-2.2.3 — Commit-reveal complet.

RED-GREEN-FIX : ces tests DOIVENT échouer avant implémentation.

Vérifie que :
1. store_commit + verify avec même réponse → True
2. store_commit + verify avec réponse altérée → False
3. attestation.commit_reveal_verified est mis à jour
4. Schema : table commit_reveal existe, colonne commit_reveal_verified existe
"""
import hashlib
import pytest


class TestCommitStoredAndVerifiable:
    """R-2.2.3 RED 1 — Commit stocké et vérifiable."""

    @pytest.mark.asyncio
    async def test_commit_stored_and_verifiable(self, tmp_path):
        """store_commit → verify_and_update_commit avec même réponse → True."""
        from database.engine import ISpaceDB
        from database.pool import close_pool

        db = ISpaceDB(str(tmp_path / "test_commit.db"))
        await db.initialize()
        try:
            response_text = "The sun is a star at the center of the solar system."
            response_hash = hashlib.sha256(response_text.encode()).hexdigest()

            await db.store_commit(
                run_id=1,
                model_id="mistral:7b",
                phase="divergent",
                response_hash=response_hash,
            )

            # Verify with the same response
            verified = await db.verify_and_update_commit(
                run_id=1,
                model_id="mistral:7b",
                phase="divergent",
                revealed_response=response_text,
            )
            assert verified is True

            # Check commit record is updated
            commit = await db.get_commit(1, "mistral:7b", "divergent")
            assert commit is not None
            assert commit["verified"] == 1
            assert commit["revealed_at"] is not None
        finally:
            await close_pool()


class TestAlteredResponseDetected:
    """R-2.2.3 RED 2 — Réponse altérée détectée."""

    @pytest.mark.asyncio
    async def test_altered_response_detected(self, tmp_path):
        """store_commit → verify_and_update_commit avec réponse différente → False."""
        from database.engine import ISpaceDB
        from database.pool import close_pool

        db = ISpaceDB(str(tmp_path / "test_altered.db"))
        await db.initialize()
        try:
            original = "The sun is a star at the center of the solar system."
            altered = "The sun is a planet in the solar system."

            response_hash = hashlib.sha256(original.encode()).hexdigest()
            await db.store_commit(
                run_id=1, model_id="mistral:7b", phase="divergent",
                response_hash=response_hash,
            )

            # Verify with altered response
            verified = await db.verify_and_update_commit(
                run_id=1, model_id="mistral:7b", phase="divergent",
                revealed_response=altered,
            )
            assert verified is False

            commit = await db.get_commit(1, "mistral:7b", "divergent")
            assert commit["verified"] == 0
        finally:
            await close_pool()


class TestAttestationCommitVerified:
    """R-2.2.3 RED 3 — Colonne commit_reveal_verified dans attestations."""

    @pytest.mark.asyncio
    async def test_attestation_commit_verified_column(self, tmp_path):
        """Après update, attestation.commit_reveal_verified == 1."""
        from database.engine import ISpaceDB
        from database.pool import close_pool
        from services.esmm.attestation import crystallize, Signature5D, ModelVote

        db = ISpaceDB(str(tmp_path / "test_att_verify.db"))
        await db.initialize()
        try:
            att = crystallize(
                subject="Sun", predicate="is_a", object_="star",
                consensus_score=0.85,
                model_votes=[
                    ModelVote(model_id="m1", provider_id="ollama",
                              agreed=True, confidence=0.9),
                ],
                signature_5d=Signature5D(
                    agreement=0.85, semantic_consistency=0.5,
                    centrality=0.5, stability=0.5, relation_diversity=0.5,
                ),
                epistemic_type="foundational",
            )
            att_dict = att.model_dump()
            att_dict["portable_json"] = att.to_portable_json()
            await db.store_attestation(att_dict)

            # Update commit_reveal_verified
            await db.update_attestation_commit_verified(att.claim_hash, verified=True)

            stored = await db.get_attestation_by_hash(att.claim_hash)
            assert stored is not None
            assert stored["commit_reveal_verified"] == 1
        finally:
            await close_pool()


class TestCommitRevealSchema:
    """R-2.2.3 RED 4 — Schema check."""

    def test_commit_reveal_table_exists(self):
        """Table commit_reveal existe dans le schéma."""
        import sqlite3
        conn = sqlite3.connect(":memory:")
        with open("database/schema.sql") as f:
            conn.executescript(f.read())

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='commit_reveal'"
        )
        assert cursor.fetchone() is not None, "Table commit_reveal not found in schema"

    def test_attestation_commit_verified_column_exists(self):
        """Colonne commit_reveal_verified dans attestations."""
        import sqlite3
        conn = sqlite3.connect(":memory:")
        with open("database/schema.sql") as f:
            conn.executescript(f.read())

        cursor = conn.execute("PRAGMA table_info(attestations)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "commit_reveal_verified" in columns, (
            f"commit_reveal_verified not found in attestations columns: {columns}"
        )
