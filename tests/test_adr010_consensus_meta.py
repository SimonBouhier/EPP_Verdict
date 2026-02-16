"""
Tests ADR-010: Traçabilité méthodologique du consensus.

Vérifie que consensus_meta est correctement stocké, sérialisé,
et exclu du claim_hash.
"""

import json
import time
import pytest

from database.engine import ISpaceDB
from database.pool import close_pool


# ============================================================================
# Fixture
# ============================================================================


@pytest.fixture
async def db(tmp_path):
    """Fresh ISpaceDB for ADR-010 tests."""
    database = ISpaceDB(str(tmp_path / "test_adr010.db"))
    await database.initialize()
    try:
        yield database
    finally:
        await close_pool()


# ============================================================================
# SP-1: Schema + Storage Layer
# ============================================================================


@pytest.mark.asyncio
async def test_schema_has_consensus_meta_column(db):
    """SP-1 RED: La table attestations doit avoir une colonne consensus_meta."""
    async with db.connection() as conn:
        cursor = await conn.execute("PRAGMA table_info(attestations)")
        columns = [row[1] for row in await cursor.fetchall()]
    assert "consensus_meta" in columns, (
        f"consensus_meta not found in attestations columns: {columns}"
    )


@pytest.mark.asyncio
async def test_store_attestation_writes_consensus_meta(db):
    """SP-1 RED: store_attestation() doit écrire consensus_meta en DB."""
    meta = {
        "methodology": {
            "consensus_method": "hash_exact_v2",
            "normalization_version": "normalize_triplet_v2_synonyms",
            "weighting_strategy": "brier_weighted",
            "merge_threshold": 0.85,
            "min_consensus": 0.5,
        },
        "conditions": {
            "models": {"mistral:latest": {"resolved_version": "7b-v0.3", "weight": 0.82}},
            "embedding_model": None,
            "cycles_completed": 3,
            "cycle_sequence": ["divergent", "divergent", "debate"],
        },
        "diagnostics": {
            "vote_entropy": 0.72,
            "semantic_dispersion": None,
            "ambiguity_detected": False,
            "variations": [],
            "triplets_before_consensus": 15,
            "triplets_after_consensus": 5,
        },
    }

    attestation = _make_attestation(consensus_meta=meta)
    att_id = await db.store_attestation(attestation)
    assert att_id is not None

    # Read back
    async with db.connection() as conn:
        cursor = await conn.execute(
            "SELECT consensus_meta FROM attestations WHERE attestation_id = ?",
            (att_id,),
        )
        row = await cursor.fetchone()

    assert row is not None
    stored_meta = json.loads(row[0])
    assert stored_meta["methodology"]["consensus_method"] == "hash_exact_v2"
    assert stored_meta["diagnostics"]["vote_entropy"] == 0.72
    assert stored_meta["conditions"]["cycles_completed"] == 3


@pytest.mark.asyncio
async def test_store_attestation_without_consensus_meta_stores_null(db):
    """SP-1 RED: Sans consensus_meta, la colonne est NULL (backward compat)."""
    attestation = _make_attestation(consensus_meta=None)
    att_id = await db.store_attestation(attestation)

    async with db.connection() as conn:
        cursor = await conn.execute(
            "SELECT consensus_meta FROM attestations WHERE attestation_id = ?",
            (att_id,),
        )
        row = await cursor.fetchone()

    assert row is not None
    assert row[0] is None


# ============================================================================
# SP-2: ConsensusResult + vote_entropy
# ============================================================================


@pytest.mark.asyncio
async def test_compute_consensus_returns_consensus_result():
    """SP-2 RED: compute_consensus doit retourner un ConsensusResult, pas une liste."""
    from services.esmm.consensus_engine import ConsensusEngine, ConsensusResult

    engine = ConsensusEngine(min_agreement=0.5)
    model_results = {
        "model_a": [{"subject": "sun", "relation": "is", "object": "star", "confidence": 0.9}],
        "model_b": [{"subject": "sun", "relation": "is", "object": "star", "confidence": 0.8}],
    }
    result = await engine.compute_consensus(model_results)
    assert isinstance(result, ConsensusResult), f"Expected ConsensusResult, got {type(result)}"
    assert hasattr(result, "triplets")
    assert hasattr(result, "triplets_before_consensus")
    assert hasattr(result, "triplets_after_consensus")
    assert hasattr(result, "vote_entropy")


@pytest.mark.asyncio
async def test_vote_entropy_unanimity_is_zero():
    """SP-2 RED: Si tous les modèles s'accordent sur les mêmes triplets, H=0."""
    from services.esmm.consensus_engine import ConsensusEngine

    engine = ConsensusEngine(min_agreement=0.3)
    # 3 models, all extract the same triplet
    triplet = {"subject": "earth", "relation": "orbits", "object": "sun", "confidence": 0.9}
    model_results = {
        "model_a": [triplet],
        "model_b": [triplet],
        "model_c": [triplet],
    }
    result = await engine.compute_consensus(model_results)
    assert result.vote_entropy == 0.0


@pytest.mark.asyncio
async def test_vote_entropy_split_is_positive():
    """SP-2 RED: Si les modèles divergent, H>0."""
    from services.esmm.consensus_engine import ConsensusEngine

    engine = ConsensusEngine(min_agreement=0.3)
    # model_a and model_b agree, model_c produces something different
    model_results = {
        "model_a": [{"subject": "earth", "relation": "orbits", "object": "sun", "confidence": 0.9}],
        "model_b": [{"subject": "earth", "relation": "orbits", "object": "sun", "confidence": 0.8}],
        "model_c": [{"subject": "mars", "relation": "has", "object": "moons", "confidence": 0.7}],
    }
    result = await engine.compute_consensus(model_results)
    assert result.vote_entropy > 0.0


@pytest.mark.asyncio
async def test_triplets_before_after_counts():
    """SP-2 RED: triplets_before >= triplets_after."""
    from services.esmm.consensus_engine import ConsensusEngine

    engine = ConsensusEngine(min_agreement=0.5)
    # 3 models: 2 agree on one triplet, 1 has a different one
    # Only the agreed triplet should pass min_agreement=0.5
    model_results = {
        "model_a": [
            {"subject": "water", "relation": "is", "object": "liquid", "confidence": 0.9},
            {"subject": "fire", "relation": "is", "object": "hot", "confidence": 0.8},
        ],
        "model_b": [
            {"subject": "water", "relation": "is", "object": "liquid", "confidence": 0.85},
        ],
        "model_c": [
            {"subject": "ice", "relation": "is", "object": "cold", "confidence": 0.7},
        ],
    }
    result = await engine.compute_consensus(model_results)
    assert result.triplets_before_consensus >= result.triplets_after_consensus
    assert result.triplets_before_consensus == 3  # 3 unique triplets
    assert result.triplets_after_consensus >= 1  # at least "water is liquid" passes


# ============================================================================
# SP-3: semantic_dispersion
# ============================================================================


@pytest.mark.asyncio
async def test_semantic_dispersion_none_without_embeddings():
    """SP-3 RED: Sans embedding provider, semantic_dispersion doit être None."""
    from services.esmm.consensus_engine import ConsensusEngine

    engine = ConsensusEngine(min_agreement=0.3)
    model_results = {
        "model_a": [{"subject": "sun", "relation": "is", "object": "star", "confidence": 0.9}],
        "model_b": [{"subject": "sun", "relation": "is", "object": "star", "confidence": 0.8}],
    }
    result = await engine.compute_consensus(model_results)
    assert result.semantic_dispersion is None


@pytest.mark.asyncio
async def test_semantic_dispersion_computed_with_embeddings():
    """SP-3 RED: Avec embedding provider, semantic_dispersion est un float >= 0."""
    from services.esmm.consensus_engine import ConsensusEngine
    from tests.test_semantic_merge import MockDeterministicEmbeddingProvider

    engine = ConsensusEngine(min_agreement=0.3)
    provider = MockDeterministicEmbeddingProvider()

    model_results = {
        "model_a": [{"subject": "sun", "relation": "is", "object": "star", "confidence": 0.9}],
        "model_b": [{"subject": "moon", "relation": "orbits", "object": "earth", "confidence": 0.8}],
    }
    result = await engine.compute_consensus(model_results, embedding_provider=provider)
    assert result.semantic_dispersion is not None
    assert isinstance(result.semantic_dispersion, float)
    assert result.semantic_dispersion >= 0.0


@pytest.mark.asyncio
async def test_semantic_dispersion_identical_is_zero():
    """SP-3 RED: Si tous les embeddings sont identiques, dispersion = 0."""
    from services.esmm.consensus_engine import ConsensusEngine
    from tests.test_semantic_merge import MockDeterministicEmbeddingProvider

    engine = ConsensusEngine(min_agreement=0.3)
    provider = MockDeterministicEmbeddingProvider()

    # All models produce the same triplet → same hash → one embedding
    model_results = {
        "model_a": [{"subject": "sun", "relation": "is", "object": "star", "confidence": 0.9}],
        "model_b": [{"subject": "sun", "relation": "is", "object": "star", "confidence": 0.8}],
    }
    result = await engine.compute_consensus(model_results, embedding_provider=provider)
    # Only 1 unique triplet hash → 0 pairs → dispersion = 0
    assert result.semantic_dispersion is not None
    assert result.semantic_dispersion == 0.0


# ============================================================================
# SP-4: Ollama version resolution
# ============================================================================


@pytest.mark.asyncio
async def test_resolve_model_version_success():
    """SP-4 RED: resolve_model_version retourne parameter_size+quantization."""
    from unittest.mock import AsyncMock, MagicMock
    from services.providers.ollama import OllamaProvider

    provider = OllamaProvider(base_url="http://localhost:11434", model="gemma3:latest")

    # Mock the HTTP client
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "modelfile": "...",
        "parameters": "...",
        "details": {
            "parent_model": "",
            "format": "gguf",
            "family": "gemma3",
            "families": ["gemma3"],
            "parameter_size": "4.3B",
            "quantization_level": "Q4_K_M",
        },
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    provider._client = mock_client
    provider._initialized = True

    version = await provider.resolve_model_version("gemma3:latest")

    assert version is not None
    assert "4.3B" in version
    assert "Q4_K_M" in version


@pytest.mark.asyncio
async def test_resolve_model_version_failure_returns_none():
    """SP-4 RED: En cas d'erreur HTTP, retourne None (best effort)."""
    from unittest.mock import AsyncMock
    from services.providers.ollama import OllamaProvider
    import httpx

    provider = OllamaProvider(base_url="http://localhost:11434", model="bad_model")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        side_effect=httpx.RequestError("Connection refused")
    )
    provider._client = mock_client
    provider._initialized = True

    version = await provider.resolve_model_version("bad_model")
    assert version is None


# ============================================================================
# SP-5: Threading diagnostics through pipeline dataclasses
# ============================================================================


def test_extraction_result_has_diagnostic_fields():
    """SP-5 RED: ExtractionResult doit avoir les champs diagnostics ADR-010."""
    from dataclasses import fields
    from services.esmm.triplet_extractor import ExtractionResult

    field_names = [f.name for f in fields(ExtractionResult)]
    assert "vote_entropy" in field_names
    assert "semantic_dispersion" in field_names
    assert "triplets_before_consensus" in field_names
    assert "triplets_after_consensus" in field_names


def test_cycle_result_has_diagnostic_fields():
    """SP-5 RED: CycleResult doit avoir les champs diagnostics ADR-010."""
    from dataclasses import fields
    from services.esmm.cycle_manager import CycleResult

    field_names = [f.name for f in fields(CycleResult)]
    assert "vote_entropy" in field_names
    assert "semantic_dispersion" in field_names
    assert "triplets_before_consensus" in field_names
    assert "triplets_after_consensus" in field_names


def test_esmm_run_result_has_diagnostic_fields():
    """SP-5 RED: ESMMRunResult doit avoir les champs diagnostics ADR-010."""
    from dataclasses import fields
    from services.esmm.orchestrator import ESMMRunResult

    field_names = [f.name for f in fields(ESMMRunResult)]
    assert "vote_entropy" in field_names
    assert "semantic_dispersion" in field_names
    assert "triplets_before_consensus" in field_names
    assert "triplets_after_consensus" in field_names


def test_esmm_run_result_defaults():
    """SP-5 RED: ESMMRunResult diagnostics ont des valeurs par défaut saines."""
    from services.esmm.orchestrator import ESMMRunResult

    result = ESMMRunResult(
        run_id=1,
        status="completed",
        cycles_completed=0,
        total_triplets=0,
        triplets_injected=0,
        cochain_size=0,
        gaps_detected=0,
        coverage_score=0.0,
        consensus_density=0.0,
        epistemic_diversity=0.0,
        structural_stability=0.0,
        duration_ms=0.0,
    )
    assert result.vote_entropy == 0.0
    assert result.semantic_dispersion is None
    assert result.triplets_before_consensus == 0
    assert result.triplets_after_consensus == 0


# ============================================================================
# SP-6: Assemblage consensus_meta dans pipeline + attestation
# ============================================================================


def test_epistemic_attestation_has_consensus_meta_field():
    """SP-6 RED: EpistemicAttestation a un champ consensus_meta optionnel."""
    from services.esmm.attestation import EpistemicAttestation
    fields = EpistemicAttestation.model_fields
    assert "consensus_meta" in fields


def test_crystallize_accepts_consensus_meta():
    """SP-6 RED: crystallize() accepte un param consensus_meta."""
    import inspect
    from services.esmm.attestation import crystallize
    sig = inspect.signature(crystallize)
    assert "consensus_meta" in sig.parameters


def test_consensus_meta_in_portable_json():
    """SP-6 RED: consensus_meta est inclus dans portable_json."""
    from services.esmm.attestation import crystallize, Signature5D, ModelVote

    meta = {"methodology": {"consensus_method": "hash_exact_v2"}}
    att = crystallize(
        subject="sun",
        predicate="is",
        object_="star",
        consensus_score=0.8,
        model_votes=[
            ModelVote(model_id="m1", provider_id="p1", agreed=True, confidence=0.9),
            ModelVote(model_id="m2", provider_id="p2", agreed=True, confidence=0.8),
        ],
        signature_5d=Signature5D(
            agreement=0.8, semantic_consistency=0.7,
            centrality=0.6, stability=0.5, relation_diversity=0.4,
        ),
        epistemic_type="foundational",
        consensus_meta=meta,
    )
    portable = att.to_portable_json()
    import json
    data = json.loads(portable)
    assert "consensus_meta" in data
    assert data["consensus_meta"]["methodology"]["consensus_method"] == "hash_exact_v2"


def test_consensus_meta_not_in_claim_hash():
    """SP-6 RED: claim_hash est identique avec ou sans consensus_meta."""
    from services.esmm.attestation import crystallize, Signature5D, ModelVote

    common = dict(
        subject="sun",
        predicate="is",
        object_="star",
        consensus_score=0.8,
        model_votes=[
            ModelVote(model_id="m1", provider_id="p1", agreed=True, confidence=0.9),
        ],
        signature_5d=Signature5D(
            agreement=0.8, semantic_consistency=0.7,
            centrality=0.6, stability=0.5, relation_diversity=0.4,
        ),
        epistemic_type="foundational",
    )

    att_without = crystallize(**common)
    att_with = crystallize(**common, consensus_meta={"methodology": {"x": 1}})

    assert att_without.claim_hash == att_with.claim_hash


# ============================================================================
# SP-7: Version resolution integration in pipeline
# ============================================================================


@pytest.mark.asyncio
async def test_build_consensus_meta_resolves_versions():
    """SP-7 RED: _build_consensus_meta() peuple resolved_version via providers."""
    from services.esmm.pipeline import _build_consensus_meta
    from services.esmm.orchestrator import ESMMRunConfig, ESMMRunResult

    esmm_config = ESMMRunConfig(models=["gemma3:latest", "mistral:7b"])
    esmm_result = ESMMRunResult(
        run_id=1,
        status="completed",
        cycles_completed=3,
        total_triplets=10,
        triplets_injected=8,
        cochain_size=5,
        gaps_detected=0,
        coverage_score=0.7,
        consensus_density=0.6,
        epistemic_diversity=0.5,
        structural_stability=0.5,
        duration_ms=1000.0,
        vote_entropy=0.42,
        semantic_dispersion=0.15,
        triplets_before_consensus=20,
        triplets_after_consensus=10,
    )

    model_weights = {"gemma3:latest": 0.82, "mistral:7b": 1.0}

    # Mock providers dict with resolve_model_version
    from unittest.mock import AsyncMock, MagicMock

    mock_provider = MagicMock()
    mock_provider.resolve_model_version = AsyncMock(side_effect=lambda m: {
        "gemma3:latest": "4.3B_Q4_K_M",
        "mistral:7b": "7B_Q4_0",
    }.get(m))

    providers = {"ollama": mock_provider}

    meta = await _build_consensus_meta(
        esmm_config, esmm_result, model_weights, providers=providers
    )

    assert meta is not None
    models = meta["conditions"]["models"]
    assert models["gemma3:latest"]["resolved_version"] == "4.3B_Q4_K_M"
    assert models["mistral:7b"]["resolved_version"] == "7B_Q4_0"


# ============================================================================
# SP-8: Migration attestations pré-ADR-010
# ============================================================================


@pytest.mark.asyncio
async def test_migration_backfills_existing(db):
    """SP-8 RED: Attestations sans consensus_meta reçoivent un stub."""
    # Insert an attestation without consensus_meta
    attestation = _make_attestation(consensus_meta=None)
    att_id = await db.store_attestation(attestation)

    # Run the backfill migration
    await db.backfill_consensus_meta()

    async with db.connection() as conn:
        cursor = await conn.execute(
            "SELECT consensus_meta FROM attestations WHERE attestation_id = ?",
            (att_id,),
        )
        row = await cursor.fetchone()

    assert row is not None
    assert row[0] is not None
    stored = json.loads(row[0])
    assert "methodology" in stored
    assert stored["methodology"]["consensus_method"] == "hash_exact_v1"


@pytest.mark.asyncio
async def test_migration_stub_content(db):
    """SP-8 RED: Le stub contient la note pré-ADR-010."""
    attestation = _make_attestation(consensus_meta=None)
    att_id = await db.store_attestation(attestation)
    await db.backfill_consensus_meta()

    async with db.connection() as conn:
        cursor = await conn.execute(
            "SELECT consensus_meta FROM attestations WHERE attestation_id = ?",
            (att_id,),
        )
        row = await cursor.fetchone()

    stored = json.loads(row[0])
    assert stored["methodology"]["note"] == "pre-ADR-010, metadata unavailable"


@pytest.mark.asyncio
async def test_migration_no_overwrite(db):
    """SP-8 RED: Attestations avec consensus_meta ne sont pas écrasées."""
    meta = {"methodology": {"consensus_method": "hash_exact_v2", "custom": True}}
    attestation = _make_attestation(consensus_meta=meta)
    att_id = await db.store_attestation(attestation)

    await db.backfill_consensus_meta()

    async with db.connection() as conn:
        cursor = await conn.execute(
            "SELECT consensus_meta FROM attestations WHERE attestation_id = ?",
            (att_id,),
        )
        row = await cursor.fetchone()

    stored = json.loads(row[0])
    assert stored["methodology"]["consensus_method"] == "hash_exact_v2"
    assert stored["methodology"]["custom"] is True


# ============================================================================
# SP-9: Integration test — full pipeline ADR-010
# ============================================================================


@pytest.mark.asyncio
async def test_full_pipeline_adr010(db):
    """SP-9: Test d'intégration complet — pipeline produit consensus_meta."""
    from unittest.mock import patch
    from services.esmm.pipeline import run_pipeline, PipelineConfig
    from services.providers.mock_provider import make_synthetic_triplets
    from services.esmm.triplet_adapter import adapt_all
    from services.esmm.orchestrator import ESMMRunConfig, ESMMRunResult

    adapted = adapt_all(make_synthetic_triplets(n=3, base_consensus=0.75))
    esmm_result = ESMMRunResult(
        run_id=42,
        status="completed",
        cycles_completed=3,
        total_triplets=10,
        triplets_injected=8,
        cochain_size=5,
        gaps_detected=0,
        coverage_score=0.7,
        consensus_density=0.6,
        epistemic_diversity=0.5,
        structural_stability=0.5,
        duration_ms=1000.0,
        vote_entropy=0.42,
        semantic_dispersion=0.15,
        triplets_before_consensus=20,
        triplets_after_consensus=10,
    )

    async def mock_extract(*args, **kwargs):
        return (adapted, 42, esmm_result)

    esmm_config = ESMMRunConfig(
        models=["m1", "m2", "m3"],
        cycle_sequence=["divergent", "debate", "meta"],
    )

    with patch("services.esmm.pipeline._extract_triplets_from_question",
               side_effect=mock_extract):
        result = await run_pipeline(
            question="Test ADR-010 integration",
            db=db,
            models=["m1", "m2", "m3"],
            esmm_config=esmm_config,
        )

    assert len(result.attestations) > 0

    for att in result.attestations:
        # 1. consensus_meta is not None
        assert att.consensus_meta is not None, "consensus_meta must not be None"

        # 2. JSON valid with 3 sections
        meta = att.consensus_meta
        assert "methodology" in meta
        assert "conditions" in meta
        assert "diagnostics" in meta

        # 3. portable_json contains consensus_meta
        portable = json.loads(att.to_portable_json())
        assert "consensus_meta" in portable

        # 4. claim_hash independent of meta
        from services.esmm.attestation import compute_claim_hash
        expected_hash = compute_claim_hash(att.subject, att.predicate, att.object)
        assert att.claim_hash == expected_hash

        # 5. vote_entropy >= 0
        assert meta["diagnostics"]["vote_entropy"] >= 0.0

        # 6. triplets_before >= triplets_after
        assert meta["diagnostics"]["triplets_before_consensus"] >= meta["diagnostics"]["triplets_after_consensus"]

    # 7. Verify stored in DB with consensus_meta
    async with db.connection() as conn:
        cursor = await conn.execute(
            "SELECT consensus_meta FROM attestations WHERE consensus_meta IS NOT NULL"
        )
        rows = await cursor.fetchall()
    assert len(rows) == len(result.attestations)
    for row in rows:
        stored = json.loads(row[0])
        assert "methodology" in stored


# ============================================================================
# Helpers
# ============================================================================


def _make_attestation(
    consensus_meta=None,
    subject="test_subject",
    predicate="relates_to",
    object_val="test_object",
):
    """Build a minimal attestation dict for testing."""
    import hashlib

    canonical = "|".join([
        subject.lower().strip(),
        predicate.lower().strip(),
        object_val.lower().strip(),
        "",
    ])
    claim_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    att = {
        "claim_hash": claim_hash,
        "subject": subject,
        "predicate": predicate,
        "object": object_val,
        "consensus_score": 0.85,
        "models_consulted": 3,
        "models_agreeing": 2,
        "model_votes": [
            {"model_id": "m1", "provider_id": "p1", "agreed": True, "confidence": 0.9},
            {"model_id": "m2", "provider_id": "p2", "agreed": True, "confidence": 0.8},
            {"model_id": "m3", "provider_id": "p3", "agreed": False, "confidence": 0.3},
        ],
        "signature_5d": {
            "agreement": 0.8,
            "semantic_consistency": 0.7,
            "centrality": 0.6,
            "stability": 0.5,
            "relation_diversity": 0.4,
        },
        "epistemic_type": "foundational",
        "confidence_tier": "validated",
        "timestamp": time.time(),
        "protocol_version": "0.3",
    }
    if consensus_meta is not None:
        att["consensus_meta"] = consensus_meta
    return att
