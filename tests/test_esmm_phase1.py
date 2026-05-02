"""
Tests ESMM Phase 1 - Fondations
================================

Tests pour:
- L1.1: GraphPopulator (population depuis topics.txt)
- L1.2: RelationGenerator (génération par similarité)
- L1.3: SeedInjector (injection graine dialectique)

Usage:
    pytest tests/test_esmm_phase1.py -v
"""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Import des modules à tester
from services.esmm.populate_graph import GraphPopulator, PopulationResult
from services.esmm.relation_generator import RelationGenerator, RelationGenerationResult
from services.esmm.seed_injector import SeedInjector, SeedInjectionResult, SEED_TYPES


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock de ISpaceDB pour les tests unitaires."""
    db = AsyncMock()

    # Mock connection context manager
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=(0,))
    mock_cursor.fetchall = AsyncMock(return_value=[])
    mock_conn.execute = AsyncMock(return_value=mock_cursor)
    mock_conn.commit = AsyncMock()

    # Context manager for connection
    async def connection_cm():
        return mock_conn

    db.connection = MagicMock()
    db.connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    db.connection.return_value.__aexit__ = AsyncMock(return_value=None)

    # Mock other methods
    db.add_concept = AsyncMock()
    db.get_concept = AsyncMock(return_value=None)
    db.get_relation = AsyncMock(return_value=None)
    db.apply_delta = AsyncMock()
    db.get_concepts_with_embeddings = AsyncMock(return_value=[])
    db.get_concept_with_aliases = AsyncMock(return_value=None)

    return db


@pytest.fixture
def sample_topics_file(tmp_path):
    """Crée un fichier topics.txt temporaire pour les tests."""
    topics_file = tmp_path / "topics.txt"
    topics_content = """entropy
information
quantum mechanics
machine learning
neural network
# This is a comment
consciousness
emergence
complexity theory

"""
    topics_file.write_text(topics_content, encoding='utf-8')
    return str(topics_file)


# ============================================================================
# TESTS GRAPHPOPULATOR (L1.1)
# ============================================================================

class TestGraphPopulator:
    """Tests pour GraphPopulator."""

    def test_normalize_concept_name_basic(self, mock_db):
        """Test de normalisation basique."""
        populator = GraphPopulator(mock_db)

        assert populator.normalize_concept_name("  Entropy  ") == "entropy"
        assert populator.normalize_concept_name("Machine Learning") == "machine learning"
        assert populator.normalize_concept_name("QUANTUM_MECHANICS") == "quantum_mechanics"

    def test_normalize_concept_name_invalid(self, mock_db):
        """Test de normalisation pour entrées invalides."""
        populator = GraphPopulator(mock_db)

        assert populator.normalize_concept_name("") is None
        assert populator.normalize_concept_name("# Comment") is None
        assert populator.normalize_concept_name("a") is None  # Trop court
        assert populator.normalize_concept_name("1. Item") is None  # Numéroté

    def test_normalize_concept_name_special_chars(self, mock_db):
        """Test de normalisation avec caractères spéciaux."""
        populator = GraphPopulator(mock_db)

        # Les caractères spéciaux sont remplacés par des espaces
        result = populator.normalize_concept_name("test@concept!")
        assert "@" not in result
        assert "!" not in result

    def test_load_topics_file(self, mock_db, sample_topics_file):
        """Test de chargement du fichier topics."""
        populator = GraphPopulator(mock_db)
        concepts = populator.load_topics_file(sample_topics_file)

        assert len(concepts) > 0
        assert "entropy" in concepts
        assert "information" in concepts
        assert "quantum mechanics" in concepts
        # Les commentaires ne sont pas inclus
        assert "# this is a comment" not in concepts

    def test_load_topics_file_not_found(self, mock_db):
        """Test de fichier non trouvé."""
        populator = GraphPopulator(mock_db)

        with pytest.raises(FileNotFoundError):
            populator.load_topics_file("/nonexistent/path/topics.txt")

    def test_serialize_deserialize_embedding(self, mock_db):
        """Test de sérialisation/désérialisation des embeddings."""
        populator = GraphPopulator(mock_db)

        # Créer un embedding test
        original = [0.1 * i for i in range(1024)]

        # Sérialiser
        serialized = populator.serialize_embedding(original)
        assert isinstance(serialized, bytes)
        assert len(serialized) == 1024 * 4  # 1024 floats * 4 bytes

        # Désérialiser
        deserialized = populator.deserialize_embedding(serialized)
        assert len(deserialized) == 1024

        # Vérifier quelques valeurs
        for i in range(10):
            assert abs(deserialized[i] - original[i]) < 1e-6

    @pytest.mark.asyncio
    async def test_populate_from_file_empty_db(self, mock_db, sample_topics_file):
        """Test de population avec DB vide (skip embeddings)."""
        # Setup mock
        mock_db.get_concepts_with_embeddings.return_value = []

        populator = GraphPopulator(mock_db, batch_size=10)

        # Exécuter sans générer les embeddings (plus rapide)
        result = await populator.populate_from_file(
            file_path=sample_topics_file,
            generate_embeddings=False,
            skip_existing=True
        )

        assert isinstance(result, PopulationResult)
        assert result.concepts_loaded > 0
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_get_population_stats(self, mock_db):
        """Test de récupération des statistiques."""
        # Setup mock pour simuler des données
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()

        # Simuler les résultats des requêtes
        call_count = [0]
        async def mock_fetchone():
            call_count[0] += 1
            if call_count[0] == 1:
                return (100,)  # total
            elif call_count[0] == 2:
                return (80,)  # with embeddings
            else:
                return (5.5,)  # avg degree

        mock_cursor.fetchone = mock_fetchone
        mock_cursor.fetchall = AsyncMock(return_value=[("topics_file", 100)])
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        mock_db.connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

        populator = GraphPopulator(mock_db)
        stats = await populator.get_population_stats()

        assert "total_concepts" in stats
        assert "with_embeddings" in stats
        assert "by_source" in stats


# ============================================================================
# TESTS RELATIONGENERATOR (L1.2)
# ============================================================================

class TestRelationGenerator:
    """Tests pour RelationGenerator."""

    def test_cosine_similarity_identical(self, mock_db):
        """Test similarité cosinus pour vecteurs identiques."""
        generator = RelationGenerator(mock_db)

        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]

        sim = generator.cosine_similarity(v1, v2)
        assert abs(sim - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self, mock_db):
        """Test similarité cosinus pour vecteurs orthogonaux."""
        generator = RelationGenerator(mock_db)

        v1 = [1.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0]

        sim = generator.cosine_similarity(v1, v2)
        assert abs(sim) < 1e-6

    def test_cosine_similarity_opposite(self, mock_db):
        """Test similarité cosinus pour vecteurs opposés."""
        generator = RelationGenerator(mock_db)

        v1 = [1.0, 0.0, 0.0]
        v2 = [-1.0, 0.0, 0.0]

        sim = generator.cosine_similarity(v1, v2)
        assert abs(sim - (-1.0)) < 1e-6

    def test_cosine_similarity_empty(self, mock_db):
        """Test similarité cosinus pour vecteurs vides."""
        generator = RelationGenerator(mock_db)

        assert generator.cosine_similarity([], []) == 0.0
        assert generator.cosine_similarity([1.0], []) == 0.0

    def test_cosine_similarity_batch(self, mock_db):
        """Test similarité batch."""
        generator = RelationGenerator(mock_db)

        target = [1.0, 0.5, 0.0]
        embeddings = [
            ("concept_a", [1.0, 0.5, 0.0]),  # Identique
            ("concept_b", [0.0, 0.0, 1.0]),  # Orthogonal
            ("concept_c", [0.8, 0.4, 0.0]),  # Similaire
        ]

        results = generator.cosine_similarity_batch(target, embeddings)

        # Vérifie que les résultats sont triés par similarité décroissante
        assert len(results) == 3
        assert results[0][0] == "concept_a"  # Le plus similaire
        assert results[0][1] > 0.99

    @pytest.mark.asyncio
    async def test_find_similar_concepts_no_embedding(self, mock_db):
        """Test recherche sans embedding source."""
        mock_db.get_concept_with_aliases.return_value = None

        generator = RelationGenerator(mock_db)
        results = await generator.find_similar_concepts("unknown", top_k=5)

        assert results == []

    @pytest.mark.asyncio
    async def test_get_generation_stats(self, mock_db):
        """Test des statistiques de génération."""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()

        call_count = [0]
        async def mock_fetchone():
            call_count[0] += 1
            if call_count[0] == 1:
                return (500,)  # total relations
            else:
                return (0.5,)  # avg kappa

        mock_cursor.fetchone = mock_fetchone
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("embedding_similarity", 400),
            ("seed", 100)
        ])
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_db.connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

        generator = RelationGenerator(mock_db)
        stats = await generator.get_generation_stats()

        assert "total_relations" in stats
        assert "by_model_source" in stats


# ============================================================================
# TESTS SEEDINJECTOR (L1.3)
# ============================================================================

class TestSeedInjector:
    """Tests pour SeedInjector."""

    def test_available_seeds(self):
        """Test des types de graines disponibles."""
        assert "minimal" in SEED_TYPES
        assert "standard" in SEED_TYPES
        assert "extended" in SEED_TYPES

    def test_seed_structure(self):
        """Test de la structure des graines."""
        for seed_type, seed in SEED_TYPES.items():
            assert isinstance(seed, dict)
            for category, pairs in seed.items():
                assert isinstance(pairs, list)
                for pair in pairs:
                    assert isinstance(pair, tuple)
                    assert len(pair) == 2

    def test_get_available_seeds(self, mock_db):
        """Test de la méthode get_available_seeds."""
        injector = SeedInjector(mock_db)
        available = injector.get_available_seeds()

        assert "minimal" in available
        assert "standard" in available
        assert "extended" in available

        for seed_type, info in available.items():
            assert "concepts" in info
            assert "relations" in info
            assert "categories" in info
            assert info["concepts"] > 0
            assert info["relations"] > 0

    @pytest.mark.asyncio
    async def test_inject_seed_unknown_type(self, mock_db):
        """Test d'injection avec type inconnu."""
        injector = SeedInjector(mock_db)

        result = await injector.inject_seed(seed_type="unknown_type")

        assert result.concepts_created == 0
        assert len(result.errors) > 0
        assert "Unknown seed type" in result.errors[0]

    @pytest.mark.asyncio
    async def test_inject_seed_minimal(self, mock_db):
        """Test d'injection de la graine minimale."""
        # Setup mocks
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_db.connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

        injector = SeedInjector(mock_db)

        # Injecter sans embeddings pour le test
        result = await injector.inject_seed(
            seed_type="minimal",
            generate_embeddings=False
        )

        assert isinstance(result, SeedInjectionResult)
        assert result.seed_type == "minimal"
        assert result.duration_ms >= 0  # Can be 0.0 with mocked DB (< 1ms)

    @pytest.mark.asyncio
    async def test_get_seed_status(self, mock_db):
        """Test du statut de la graine."""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()

        call_count = [0]
        async def mock_fetchone():
            call_count[0] += 1
            return (10,) if call_count[0] <= 2 else (0.5,)

        mock_cursor.fetchone = mock_fetchone
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_db.connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

        injector = SeedInjector(mock_db)
        status = await injector.get_seed_status()

        assert "seed_concepts" in status
        assert "seed_relations" in status
        assert "seed_coverage" in status


# ============================================================================
# TESTS D'INTÉGRATION (nécessite DB réelle)
# ============================================================================

class TestESMMPhase1Integration:
    """Tests d'intégration nécessitant une vraie base de données."""

    @pytest.fixture
    async def real_db(self, tmp_path):
        """Crée une vraie base de données pour les tests d'intégration."""
        from database import ISpaceDB
        from database.pool import close_pool

        db_path = tmp_path / "test_ispace.db"
        db = ISpaceDB(str(db_path))
        await db.initialize()

        yield db

        # Cleanup: close pool first to release file locks
        await close_pool()
        if db_path.exists():
            try:
                db_path.unlink()
            except PermissionError:
                pass

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_phase1_workflow(self, real_db, sample_topics_file):
        """
        Test du workflow complet Phase 1:
        1. Injection de la graine
        2. Population depuis topics.txt
        3. Génération des relations
        """
        # Skip si pas de DB réelle
        pytest.skip("Integration test - requires real database setup")

        # 1. Injection graine
        injector = SeedInjector(real_db)
        seed_result = await injector.inject_seed(
            seed_type="minimal",
            generate_embeddings=False
        )
        assert seed_result.concepts_created > 0

        # 2. Population
        populator = GraphPopulator(real_db)
        pop_result = await populator.populate_from_file(
            file_path=sample_topics_file,
            generate_embeddings=False
        )
        assert pop_result.concepts_loaded > 0

        # 3. Vérifier les stats
        stats = await populator.get_population_stats()
        assert stats["total_concepts"] > 0


# ─────────────────────────────────────────────────────────────────────────
# Single-file runner — `python tests/test_esmm_phase1.py`
# Génère un rapport horodaté dans `test_results/individual/`.
# Cf. `tests/_runner.py::run_self` pour le détail.
# (Remplace l'ancien `pytest.main([__file__, "-v"])` — équivalent fonctionnel
# avec en plus tee console + fichier individuel horodaté.)
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from tests._runner import run_self
    raise SystemExit(run_self(__file__))
