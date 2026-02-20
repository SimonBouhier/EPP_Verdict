"""
Tests for bugs F1, F2, F3 discovered via scenario_3_enrichment.py.

RED-GREEN-FIX: tests written BEFORE fixes, must fail first.
"""
import pytest


# ===========================================================================
# F2 — _check_db_duplicate: phantom column 'id' in SQL query
# ===========================================================================


@pytest.mark.asyncio
async def test_check_db_duplicate_returns_dict_for_existing_relation(tmp_path):
    """_check_db_duplicate must return a non-None dict when relation exists in DB.

    BUG: The query uses SELECT id, weight, extraction_count FROM relations,
    but the relations table has no 'id' column (composite PK source+target).
    The query fails silently → always returns None → duplicate detection broken.
    """
    from database.engine import ISpaceDB

    db = ISpaceDB(str(tmp_path / "test_f2.db"))
    await db.initialize()

    # Insert a concept pair + relation into the DB
    async with db.connection() as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO concepts (id) VALUES (?)",
            ("solana",),
        )
        await conn.execute(
            "INSERT OR IGNORE INTO concepts (id) VALUES (?)",
            ("proof_of_history",),
        )
        await conn.execute(
            """INSERT OR IGNORE INTO relations (source, target, relation_type, weight, extraction_count)
               VALUES (?, ?, ?, ?, ?)""",
            ("solana", "proof_of_history", "uses", 0.8, 3),
        )
        await conn.commit()

    # Now use TripletExtractor._check_db_duplicate
    from services.esmm.triplet_extractor import TripletExtractor

    extractor = TripletExtractor(
        db=db, models=["mock:7b"], min_consensus=0.5, min_confidence=0.3
    )

    result = await extractor._check_db_duplicate(
        "solana", "proof_of_history", "uses"
    )

    # Must return a dict (not None)
    assert result is not None, (
        "_check_db_duplicate returned None for an existing relation — "
        "phantom 'id' column bug (F2)"
    )
    assert "weight" in result
    assert result["weight"] == pytest.approx(0.8)
    assert result["count"] == 3

    # tmp_path cleanup handles DB file removal


# ===========================================================================
# F3 — format_triplets_for_prompt: eager eval crash with ConsensusTriplet
# ===========================================================================


def test_format_triplets_for_prompt_with_consensus_triplet():
    """format_triplets_for_prompt must work with ConsensusTriplet dataclass objects.

    BUG: getattr(t, 'subject', t.get('subject', '?')) eagerly evaluates
    t.get() even when t is a dataclass (no .get() method) → AttributeError.
    """
    from services.esmm.consensus_engine import ConsensusTriplet
    from services.esmm.cycle_prompts import format_triplets_for_prompt

    triplets = [
        ConsensusTriplet(
            subject="solana",
            relation="uses",
            object="proof of history",
            avg_confidence=0.85,
            std_confidence=0.05,
            agreement_ratio=1.0,
            consensus_score=0.9,
            contributing_models=["mistral:7b", "llama3.1:8b"],
            triplet_hash="abc123",
        ),
    ]

    # Must not raise AttributeError
    result = format_triplets_for_prompt(triplets)
    assert "solana" in result
    assert "uses" in result
    assert "proof of history" in result


def test_format_triplets_for_prompt_with_dict():
    """format_triplets_for_prompt must also still work with plain dicts."""
    from services.esmm.cycle_prompts import format_triplets_for_prompt

    triplets = [
        {"subject": "bitcoin", "relation": "is_a", "object": "cryptocurrency"},
    ]

    result = format_triplets_for_prompt(triplets)
    assert "bitcoin" in result
    assert "is_a" in result
    assert "cryptocurrency" in result


# ===========================================================================
# F1 — get_triplet_extractor: db param + singleton invalidation
# ===========================================================================


@pytest.mark.asyncio
async def test_get_triplet_extractor_uses_provided_db(tmp_path):
    """get_triplet_extractor(db=mock_db) must use the provided db, not get_db().

    BUG: get_triplet_extractor() has no db param, always calls get_db()
    which opens data/epp.db from config.
    """
    from database.engine import ISpaceDB
    from services.esmm.triplet_extractor import get_triplet_extractor
    import services.esmm.triplet_extractor as te_mod

    # Reset singleton to avoid cross-test pollution
    te_mod._extractor_instance = None

    db = ISpaceDB(str(tmp_path / "test_f1.db"))
    await db.initialize()

    extractor = await get_triplet_extractor(
        db=db, models=["mock:7b"], min_consensus=0.5
    )

    assert extractor.db is db, (
        "get_triplet_extractor did not use the provided db — "
        "it called get_db() instead (F1)"
    )

    # tmp_path cleanup handles DB file removal
    te_mod._extractor_instance = None


@pytest.mark.asyncio
async def test_get_triplet_extractor_singleton_invalidation(tmp_path):
    """Calling get_triplet_extractor with a different db must invalidate the singleton.

    If get_triplet_extractor(db=db_A) is called, then get_triplet_extractor(db=db_B),
    the second call must return an instance with db_B, not db_A.
    """
    from database.engine import ISpaceDB
    from services.esmm.triplet_extractor import get_triplet_extractor
    import services.esmm.triplet_extractor as te_mod

    # Reset singleton to avoid cross-test pollution
    te_mod._extractor_instance = None

    db_a = ISpaceDB(str(tmp_path / "test_f1a.db"))
    await db_a.initialize()
    db_b = ISpaceDB(str(tmp_path / "test_f1b.db"))
    await db_b.initialize()

    # First call: creates singleton with db_a
    ext_a = await get_triplet_extractor(
        db=db_a, models=["mock:7b"], min_consensus=0.5
    )
    assert ext_a.db is db_a

    # Second call: different db → must invalidate and recreate
    ext_b = await get_triplet_extractor(
        db=db_b, models=["mock:7b"], min_consensus=0.5
    )
    assert ext_b.db is db_b, (
        "Singleton was NOT invalidated when a different db was provided — "
        "still using stale db_a (F1 singleton bug)"
    )
    assert te_mod._extractor_instance.db is db_b

    # tmp_path cleanup handles DB file removal
    te_mod._extractor_instance = None


# ===========================================================================
# F4 — _sanitize_concept(None) crash in META cycles
# ===========================================================================


def test_sanitize_concept_none_does_not_crash():
    """_sanitize_concept(None) must return empty string, not crash.

    BUG: _sanitize_concept() does re.sub(r"<[^>]*>", "", value) which
    crashes with TypeError when value is None. None enters via META cycle
    concept selection from DB rows where subject_canonical is NULL.
    """
    from services.esmm.cycle_manager import _sanitize_concept

    # Must not raise TypeError
    result = _sanitize_concept(None)
    assert result == "", (
        f"_sanitize_concept(None) should return '' but returned {result!r}"
    )


def test_sanitize_concept_empty_string():
    """_sanitize_concept('') must return empty string."""
    from services.esmm.cycle_manager import _sanitize_concept

    result = _sanitize_concept("")
    assert result == ""


def test_sanitize_concept_normal_value_still_works():
    """_sanitize_concept with a normal string must still sanitize correctly."""
    from services.esmm.cycle_manager import _sanitize_concept

    result = _sanitize_concept("<script>alert('xss')</script>solana")
    assert "<script>" not in result
    assert "solana" in result


def test_sanitize_concept_non_string_coerced():
    """_sanitize_concept with a non-string (e.g. sqlite3.Row) must coerce to str.

    BUG: _select_target_concepts flatten logic appends sqlite3.Row objects
    (not plain strings) when row_factory=aiosqlite.Row. The Row is truthy
    but not a string, so re.sub crashes with TypeError.
    """
    from services.esmm.cycle_manager import _sanitize_concept

    # Simulate a non-string truthy value
    result = _sanitize_concept(42)
    assert isinstance(result, str)
    assert result == "42"


# ===========================================================================
# F5 — Duplicate attestations across cycles
# ===========================================================================


@pytest.mark.asyncio
async def test_duplicate_triplets_produce_single_attestation(tmp_path):
    """Identical triplets from multiple cycles must crystallize only once.

    BUG: orchestrator._collected_triplets.extend(result.consensus_triplets)
    appends without dedup. The crystallization loop in pipeline.py processes
    ALL triplets without checking claim_hash uniqueness.
    """
    from unittest.mock import AsyncMock, patch
    from database.engine import ISpaceDB
    from services.esmm.pipeline import run_pipeline, PipelineConfig

    db = ISpaceDB(str(tmp_path / "test_f5.db"))
    await db.initialize()

    # Two identical triplets (simulating same triplet from two cycles)
    duplicate_triplet = {
        "subject": "solana",
        "predicate": "uses",
        "object": "proof of history",
        "consensus_score": 0.9,
        "votes": [
            {
                "model_id": "mistral:7b",
                "provider_id": "ollama",
                "agreed": True,
                "confidence": 0.9,
                "architecture_family": "mistral",
            }
        ],
        "signature_5d": {
            "agreement": 0.9,
            "semantic_consistency": 0.8,
            "centrality": 0.5,
            "stability": 0.5,
            "relation_diversity": 1.0,
        },
        "epistemic_type": "foundational",
        "triplet_hash": "abc123",
    }

    # Same triplet appearing twice (from two cycles)
    extracted = [duplicate_triplet, duplicate_triplet.copy()]

    with patch(
        "services.esmm.pipeline._extract_triplets_from_question",
        new_callable=AsyncMock,
        return_value=(extracted, 1, None),
    ):
        config = PipelineConfig(min_consensus_for_attestation=0.4)
        result = await run_pipeline(
            question="What consensus mechanism does Solana use?",
            db=db,
            models=["mistral:7b"],
            config=config,
        )

    # BUG: Without dedup, this would be 2. Must be 1.
    assert len(result.attestations) == 1, (
        f"Expected 1 attestation but got {len(result.attestations)} — "
        f"duplicate claim_hash was not deduplicated (F5)"
    )


# ===========================================================================
# F1-residual — entity_resolver + relation_normalizer db param
# ===========================================================================


@pytest.mark.asyncio
async def test_entity_resolver_uses_provided_db(tmp_path):
    """get_entity_resolver(db=mock_db) must use the provided db, not get_db().

    BUG: get_entity_resolver() has no db param, always calls get_db()
    which opens data/epp.db from config — causing pool path mismatch.
    """
    from database.engine import ISpaceDB
    from services.entity_resolver import get_entity_resolver
    import services.entity_resolver as er_mod

    # Reset singleton
    er_mod._resolver_instance = None

    db = ISpaceDB(str(tmp_path / "test_f1res_er.db"))
    await db.initialize()

    resolver = await get_entity_resolver(db=db)

    assert resolver.db is db, (
        "get_entity_resolver did not use the provided db — "
        "it called get_db() instead (F1-residual)"
    )

    er_mod._resolver_instance = None


@pytest.mark.asyncio
async def test_relation_normalizer_uses_provided_db(tmp_path):
    """get_relation_normalizer(db=mock_db) must use the provided db, not get_db().

    BUG: get_relation_normalizer() has no db param, always calls get_db()
    which opens data/epp.db from config — causing pool path mismatch.
    """
    from database.engine import ISpaceDB
    from services.relation_normalizer import get_relation_normalizer
    import services.relation_normalizer as rn_mod

    # Reset singleton
    rn_mod._normalizer_instance = None

    db = ISpaceDB(str(tmp_path / "test_f1res_rn.db"))
    await db.initialize()

    normalizer = await get_relation_normalizer(db=db)

    assert normalizer.db is db, (
        "get_relation_normalizer did not use the provided db — "
        "it called get_db() instead (F1-residual)"
    )

    rn_mod._normalizer_instance = None
