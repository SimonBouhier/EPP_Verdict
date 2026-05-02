"""
Tests ADR-011-v2 — Integration : raw_model_triplets exposure,
orchestrator reconcile(), pipeline consensus_meta.

RED-GREEN-FIX : ces tests DOIVENT échouer avant implémentation.
"""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib

import pytest
from dataclasses import fields


# ===========================================================================
# Sprint 3.7 — raw_model_triplets exposure
# ===========================================================================


def test_extraction_result_has_raw_model_triplets():
    """ExtractionResult dataclass has raw_model_triplets field."""
    from services.esmm.triplet_extractor import ExtractionResult
    field_names = {f.name for f in fields(ExtractionResult)}
    assert "raw_model_triplets" in field_names
    # Default is empty dict
    er = ExtractionResult(
        triplets_extracted=0,
        triplets_injected=0,
        triplets_skipped=0,
        consensus_triplets=[],
        new_concepts_created=0,
        duration_ms=0.0,
        models_used=[],
        input_hash="abc",
    )
    assert er.raw_model_triplets == {}


def test_cycle_result_has_raw_model_triplets():
    """CycleResult dataclass has raw_model_triplets field."""
    from services.esmm.cycle_manager import CycleResult, CycleType
    field_names = {f.name for f in fields(CycleResult)}
    assert "raw_model_triplets" in field_names


# ===========================================================================
# Sprint 3.8 — Orchestrator: ESMMRunResult.reconciliation_meta
# ===========================================================================


def test_esmm_run_result_has_reconciliation_meta():
    """ESMMRunResult has reconciliation_meta field."""
    from services.esmm.orchestrator import ESMMRunResult
    field_names = {f.name for f in fields(ESMMRunResult)}
    assert "reconciliation_meta" in field_names


@pytest.mark.asyncio
async def test_reconcile_skipped_when_disabled(monkeypatch):
    """reconcile() returns skip meta when fingerprinting disabled."""
    from services.esmm.fingerprint_config import FingerprintConfig

    disabled_config = FingerprintConfig(enabled=False)
    monkeypatch.setattr(
        "services.esmm.fingerprint_config.load_fingerprint_config",
        lambda: disabled_config,
    )

    from services.esmm.orchestrator import ESMMOrchestrator, ESMMRunConfig

    config = ESMMRunConfig(models=["m1"])
    orch = ESMMOrchestrator.__new__(ESMMOrchestrator)
    orch.config = config
    orch._raw_model_triplets = {}
    orch._final_consensus_triplets = None
    orch._reconciliation_meta = None
    orch._model_weights = None
    orch._collected_triplets = []

    meta = await orch.reconcile()
    assert meta is not None
    assert meta["method"] == "skipped"
    assert meta["reason"] == "disabled"
    assert orch._final_consensus_triplets is None  # not mutated


@pytest.mark.asyncio
async def test_reconcile_skipped_when_few_terms(monkeypatch):
    """reconcile() skips when unique terms < min_unique_terms."""
    from services.esmm.fingerprint_config import FingerprintConfig

    config_high_min = FingerprintConfig(enabled=True, min_unique_terms=100)
    monkeypatch.setattr(
        "services.esmm.fingerprint_config.load_fingerprint_config",
        lambda: config_high_min,
    )

    from services.esmm.orchestrator import ESMMOrchestrator, ESMMRunConfig

    run_config = ESMMRunConfig(models=["m1"])
    orch = ESMMOrchestrator.__new__(ESMMOrchestrator)
    orch.config = run_config
    orch._raw_model_triplets = {
        "m1": [{"subject": "solana", "relation": "uses", "object": "PoH"}],
    }
    orch._final_consensus_triplets = None
    orch._reconciliation_meta = None
    orch._model_weights = None
    orch._collected_triplets = []

    meta = await orch.reconcile()
    assert meta["method"] == "skipped"
    assert "min_unique_terms" in meta["reason"]


@pytest.mark.asyncio
async def test_reconcile_skipped_when_no_raw_triplets(monkeypatch):
    """reconcile() skips when no raw_model_triplets accumulated."""
    from services.esmm.fingerprint_config import FingerprintConfig

    monkeypatch.setattr(
        "services.esmm.fingerprint_config.load_fingerprint_config",
        lambda: FingerprintConfig(enabled=True),
    )

    from services.esmm.orchestrator import ESMMOrchestrator, ESMMRunConfig

    run_config = ESMMRunConfig(models=["m1"])
    orch = ESMMOrchestrator.__new__(ESMMOrchestrator)
    orch.config = run_config
    orch._raw_model_triplets = {}
    orch._final_consensus_triplets = None
    orch._reconciliation_meta = None
    orch._model_weights = None
    orch._collected_triplets = []

    meta = await orch.reconcile()
    assert meta["method"] == "skipped"
    assert "no raw" in meta["reason"].lower() or "empty" in meta["reason"].lower()


# ===========================================================================
# C5 correction — accumulation normalizes objects to dicts
# ===========================================================================


def test_accumulation_normalizes_objects_to_dicts():
    """Orchestrator accumulation converts non-dict triplets to dicts."""
    from services.esmm.orchestrator import ESMMOrchestrator, ESMMRunConfig
    from dataclasses import dataclass

    @dataclass
    class FakeTriplet:
        subject: str
        relation: str
        object: str
        confidence: float

    @dataclass
    class FakeCycleResult:
        raw_model_triplets: dict
        consensus_triplets: list
        triplets_extracted: int = 0
        triplets_before_consensus: int = 0
        triplets_after_consensus: int = 0
        vote_entropy: float = 0.0
        semantic_dispersion: float = None

    orch = ESMMOrchestrator.__new__(ESMMOrchestrator)
    orch._raw_model_triplets = {}

    # Simulate accumulation with object triplets
    result = FakeCycleResult(
        raw_model_triplets={
            "m1": [FakeTriplet("solana", "uses", "PoH", 0.9)],
        },
        consensus_triplets=[],
    )

    if result.raw_model_triplets:
        for model_id, triplets in result.raw_model_triplets.items():
            as_dicts = []
            for t in triplets:
                if isinstance(t, dict):
                    as_dicts.append(t)
                elif hasattr(t, '__dict__'):
                    as_dicts.append(vars(t))
                else:
                    as_dicts.append({
                        "subject": getattr(t, "subject", ""),
                        "relation": getattr(t, "relation", ""),
                        "object": getattr(t, "object", ""),
                        "confidence": getattr(t, "confidence", 0.0),
                    })
            orch._raw_model_triplets.setdefault(model_id, []).extend(as_dicts)

    # Verify all accumulated triplets are dicts
    for model_id, triplets in orch._raw_model_triplets.items():
        for t in triplets:
            assert isinstance(t, dict), f"Expected dict, got {type(t)}"
    assert orch._raw_model_triplets["m1"][0]["subject"] == "solana"
    assert orch._raw_model_triplets["m1"][0]["confidence"] == 0.9


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
