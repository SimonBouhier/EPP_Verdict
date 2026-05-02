"""Tests Phase 3 — Question seeder."""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


import asyncio
import tempfile
import pytest

from services.esmm.question_seeder import extract_seed_concepts, seed_graph_from_question


class TestExtractSeedConcepts:

    def test_extract_seed_concepts(self):
        """'Solana effective TPS exceeds 3000' -> expected concepts."""
        concepts = extract_seed_concepts("Solana effective TPS exceeds 3000")
        assert "solana" in concepts
        assert "effective" in concepts
        assert "tps" in concepts
        assert "exceeds" in concepts
        assert "3000" in concepts

    def test_stop_words_filtered(self):
        """'the', 'is', 'a' are removed."""
        concepts = extract_seed_concepts("The cat is a small animal")
        assert "the" not in concepts
        assert "is" not in concepts
        assert "cat" in concepts
        assert "small" in concepts
        assert "animal" in concepts

    def test_short_words_filtered(self):
        """Single character words filtered."""
        concepts = extract_seed_concepts("I am a B student")
        # 'i' and 'a' are stop words, 'b' is 1 char -> filtered
        assert "student" in concepts
        assert "am" in concepts  # 2 chars, not a stop word

    def test_duplicates_removed(self):
        """No duplicate concepts."""
        concepts = extract_seed_concepts("Solana Solana solana SOLANA")
        assert concepts.count("solana") == 1

    def test_empty_question(self):
        """Empty or stop-only question returns empty list."""
        assert extract_seed_concepts("") == []
        # "the is a" -> all stop words
        concepts = extract_seed_concepts("the is a")
        assert len(concepts) == 0


class TestSeedGraphFromQuestion:

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_seed_graph_on_empty(self):
        """Seeds graph if concepts count is 0."""
        from database.engine import ISpaceDB
        import tempfile, os
        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "test_seed.db")
        db = ISpaceDB(db_path)
        self._run(db.initialize())

        count = self._run(seed_graph_from_question(db, "Solana effective TPS exceeds 3000"))
        assert count >= 4  # at least solana, effective, tps, exceeds, 3000

    def test_seed_graph_skips_if_not_empty(self):
        """Returns 0 if graph has concepts."""
        from database.engine import ISpaceDB
        import tempfile, os
        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "test_seed2.db")
        db = ISpaceDB(db_path)
        self._run(db.initialize())

        # First seed
        self._run(seed_graph_from_question(db, "Bitcoin proof of work"))
        # Second seed should skip
        count = self._run(seed_graph_from_question(db, "Solana TPS exceeds 3000"))
        assert count == 0


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
