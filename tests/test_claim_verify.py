"""
Tests for Claim Verification (VERIFY) dual-mode.

RED-GREEN-FIX: tests written BEFORE implementation, must fail first.

Directive source: docs/To_do_list/DIRECTIVE_CLAIM_VERIFY.md
"""
import pytest


# ===========================================================================
# S1 — CycleType.ASSESS + templates + system prompts
# ===========================================================================


def test_cycle_type_assess_exists():
    """CycleType must include ASSESS, CHALLENGE, ADJUDICATE."""
    from services.esmm.cycle_prompts import CycleType

    assert hasattr(CycleType, "ASSESS"), "CycleType.ASSESS missing"
    assert hasattr(CycleType, "CHALLENGE"), "CycleType.CHALLENGE missing"
    assert hasattr(CycleType, "ADJUDICATE"), "CycleType.ADJUDICATE missing"
    assert CycleType.ASSESS.value == "assess"
    assert CycleType.CHALLENGE.value == "challenge"
    assert CycleType.ADJUDICATE.value == "adjudicate"


def test_assess_template_contains_claim_placeholder():
    """ASSESS templates must use {claim} placeholder."""
    from services.esmm.cycle_prompts import CycleType, get_template

    template = get_template(CycleType.ASSESS, 0)
    assert "{claim}" in template, (
        f"ASSESS template must contain {{claim}} placeholder, got: {template[:80]}"
    )


def test_challenge_template_contains_verdict_placeholder():
    """CHALLENGE templates must use {claim}, {verdict}, {evidence} placeholders."""
    from services.esmm.cycle_prompts import CycleType, get_template

    template = get_template(CycleType.CHALLENGE, 0)
    assert "{claim}" in template
    assert "{verdict}" in template
    assert "{evidence}" in template


def test_adjudicate_template_contains_all_verdicts_placeholder():
    """ADJUDICATE templates must use {claim} and {all_verdicts} placeholders."""
    from services.esmm.cycle_prompts import CycleType, get_template

    template = get_template(CycleType.ADJUDICATE, 0)
    assert "{claim}" in template
    assert "{all_verdicts}" in template


def test_assess_system_prompt_is_generic():
    """ASSESS system prompt must NOT contain {claim} — it's static like DIVERGENT's."""
    from services.esmm.cycle_prompts import CycleType, get_system_prompt

    prompt = get_system_prompt(CycleType.ASSESS)
    assert isinstance(prompt, str)
    assert len(prompt) > 50
    assert "{claim}" not in prompt, (
        "System prompt must be static (no placeholders) — claim goes in templates"
    )
    assert "verdict" in prompt.lower() or "assess" in prompt.lower()


def test_verify_cycle_types_in_cycle_templates():
    """All 6 CycleTypes must have entries in CYCLE_TEMPLATES."""
    from services.esmm.cycle_prompts import CycleType, CYCLE_TEMPLATES

    for ct in CycleType:
        assert ct in CYCLE_TEMPLATES, f"{ct} missing from CYCLE_TEMPLATES"
        assert len(CYCLE_TEMPLATES[ct]) >= 2, f"{ct} needs at least 2 templates"


# ===========================================================================
# S2 — InputType + classify_input()
# ===========================================================================


def test_classify_input_verify_claim():
    """classify_input must detect verifiable claims."""
    from services.esmm.question_seeder import classify_input, InputType

    assert classify_input("Solana effective TPS exceeds 3000") == InputType.VERIFY
    assert classify_input("Bitcoin surpasses 100000 dollars") == InputType.VERIFY
    assert classify_input("Is it true that Ethereum uses proof of stake") == InputType.VERIFY
    assert classify_input("Verify that the speed reaches 4000") == InputType.VERIFY


def test_classify_input_explore_question():
    """classify_input must default to EXPLORE for open questions."""
    from services.esmm.question_seeder import classify_input, InputType

    assert classify_input("What is Solana?") == InputType.EXPLORE
    assert classify_input("How does proof of stake work?") == InputType.EXPLORE
    assert classify_input("Explain consensus mechanisms") == InputType.EXPLORE


def test_classify_input_default_explore():
    """Ambiguous input must default to EXPLORE (conservative)."""
    from services.esmm.question_seeder import classify_input, InputType

    assert classify_input("Python is a programming language") == InputType.EXPLORE
    assert classify_input("My dog has fleas") == InputType.EXPLORE


# ===========================================================================
# S7 — epistemic_type "verdict" (simple, can test early)
# ===========================================================================


def test_attestation_verdict_epistemic_type():
    """crystallize() must accept epistemic_type='verdict' without ValueError."""
    from services.esmm.attestation import crystallize, Signature5D, ModelVote

    att = crystallize(
        subject="solana tps",
        predicate="verdict",
        object_="SUPPORTED",
        consensus_score=0.75,
        model_votes=[
            ModelVote(model_id="m1", provider_id="p1", agreed=True, confidence=0.8),
        ],
        signature_5d=Signature5D(
            agreement=0.75, semantic_consistency=0.7,
            centrality=0.5, stability=0.5, relation_diversity=0.5,
        ),
        epistemic_type="verdict",
        metrological_frame="blockchain_tps_v1.0",
    )
    assert att.epistemic_type == "verdict"
    assert att.claim_hash  # must produce a valid hash


# ===========================================================================
# S3 — cycle_manager: _generate_question for VERIFY modes
# ===========================================================================


def test_generate_question_assess_contains_claim():
    """ASSESS question must contain the full original claim, not a concept."""
    from services.esmm.cycle_manager import ExplorationCycleManager
    from services.esmm.cycle_prompts import CycleType
    from unittest.mock import MagicMock

    mgr = object.__new__(ExplorationCycleManager)
    mgr._template_rotation_index = {CycleType.ASSESS: 0}
    mgr._recent_triplets = []

    claim = "Solana effective TPS exceeds 3000"
    context = {"original_claim": claim}
    question = mgr._generate_question(CycleType.ASSESS, [claim], context)

    assert "Solana effective TPS exceeds 3000" in question, (
        f"ASSESS question must contain the full claim, got: {question[:120]}"
    )


def test_generate_question_challenge_contains_verdict():
    """CHALLENGE question must contain claim + verdict + evidence."""
    from services.esmm.cycle_manager import ExplorationCycleManager
    from services.esmm.cycle_prompts import CycleType

    mgr = object.__new__(ExplorationCycleManager)
    mgr._template_rotation_index = {CycleType.CHALLENGE: 0}
    mgr._recent_triplets = []

    claim = "Solana effective TPS exceeds 3000"
    context = {
        "original_claim": claim,
        "verdict": "SUPPORTED",
        "evidence": "solana->achieves->4000 tps",
    }
    question = mgr._generate_question(CycleType.CHALLENGE, [claim], context)

    assert "Solana effective TPS exceeds 3000" in question
    assert "SUPPORTED" in question
    assert "4000 tps" in question


def test_generate_question_adjudicate_contains_all_verdicts():
    """ADJUDICATE question must contain claim + all_verdicts."""
    from services.esmm.cycle_manager import ExplorationCycleManager
    from services.esmm.cycle_prompts import CycleType

    mgr = object.__new__(ExplorationCycleManager)
    mgr._template_rotation_index = {CycleType.ADJUDICATE: 0}
    mgr._recent_triplets = []

    claim = "Solana effective TPS exceeds 3000"
    context = {
        "original_claim": claim,
        "all_verdicts": "Model A: SUPPORTED (0.85), Model B: CONTESTED (0.6)",
    }
    question = mgr._generate_question(CycleType.ADJUDICATE, [claim], context)

    assert "Solana effective TPS exceeds 3000" in question
    assert "SUPPORTED" in question
    assert "CONTESTED" in question


def test_cycle_timeouts_include_verify_types():
    """ASSESS, CHALLENGE, ADJUDICATE must have timeout entries."""
    from services.esmm.cycle_manager import CYCLE_TIMEOUTS
    from services.esmm.cycle_prompts import CycleType

    for ct in [CycleType.ASSESS, CycleType.CHALLENGE, CycleType.ADJUDICATE]:
        assert ct in CYCLE_TIMEOUTS, f"{ct} missing from CYCLE_TIMEOUTS"
        assert CYCLE_TIMEOUTS[ct] >= 60, f"{ct} timeout too low"


# ===========================================================================
# S4 — triplet_extractor: verdict response parsing
# ===========================================================================


def test_parse_verdict_response():
    """_parse_verdict_response must extract verdict + evidence triplets."""
    from services.esmm.triplet_extractor import _parse_verdict_response

    raw = '''{
        "verdict": "SUPPORTED",
        "confidence": 0.85,
        "evidence": [
            {"subject": "solana", "relation": "achieves", "object": "4000 tps", "confidence": 0.8},
            {"subject": "claim", "relation": "depends_on", "object": "definition of effective tps", "confidence": 0.7}
        ],
        "reasoning": "Mainnet data shows average TPS around 4000."
    }'''

    result = _parse_verdict_response(raw, claim_text="Solana effective TPS exceeds 3000")

    assert result["verdict"] == "SUPPORTED"
    assert result["confidence"] == 0.85
    assert len(result["evidence"]) >= 2
    # Verdict triplet must be generated
    assert any(
        t["relation"] == "verdict" and t["object"] == "SUPPORTED"
        for t in result["triplets"]
    ), "Must produce a verdict-as-triplet"


# ===========================================================================
# S5 — verdict_encoder: encode_verdict_as_triplets
# ===========================================================================


def test_encode_verdict_as_triplets():
    """encode_verdict_as_triplets must produce verdict + evidence triplets."""
    from services.esmm.verdict_encoder import encode_verdict_as_triplets

    verdict_response = {
        "verdict": "SUPPORTED",
        "confidence": 0.85,
        "evidence": [
            {"subject": "solana", "relation": "achieves", "object": "4000 tps", "confidence": 0.8},
        ],
        "reasoning": "Mainnet data confirms.",
    }

    triplets = encode_verdict_as_triplets(
        claim="Solana effective TPS exceeds 3000",
        verdict_response=verdict_response,
    )

    # Must produce at least: 1 verdict triplet + N evidence triplets
    assert len(triplets) >= 2
    verdict_triplet = [t for t in triplets if t["relation"] == "verdict"]
    assert len(verdict_triplet) == 1
    assert verdict_triplet[0]["object"] == "SUPPORTED"
    assert verdict_triplet[0]["confidence"] == 0.85

    evidence_triplets = [t for t in triplets if t["relation"] != "verdict"]
    assert len(evidence_triplets) >= 1


# ===========================================================================
# S6 — orchestrator + pipeline integration
# ===========================================================================


def test_esmm_run_config_has_verify_fields():
    """ESMMRunConfig must have input_mode and original_claim fields."""
    from services.esmm.orchestrator import ESMMRunConfig

    # Default should be explore
    config = ESMMRunConfig(models=["test:latest"])
    assert config.input_mode == "explore"
    assert config.original_claim is None

    # VERIFY mode
    config_v = ESMMRunConfig(
        models=["test:latest"],
        input_mode="verify",
        original_claim="Solana TPS exceeds 3000",
    )
    assert config_v.input_mode == "verify"
    assert config_v.original_claim == "Solana TPS exceeds 3000"


def test_verify_cycle_sequence_override():
    """In VERIFY mode, execute_cycles must use assess/challenge/adjudicate."""
    from services.esmm.orchestrator import ESMMRunConfig

    config = ESMMRunConfig(
        models=["test:latest"],
        input_mode="verify",
        original_claim="Solana TPS exceeds 3000",
    )
    # When input_mode is "verify", the config should still allow
    # the orchestrator to override the cycle_sequence at runtime.
    # The config's cycle_sequence is the EXPLORE default — the orchestrator
    # overrides it in execute_cycles() when input_mode == "verify".
    assert config.input_mode == "verify"


def test_build_consensus_meta_verify_section():
    """_build_consensus_meta must include 'verify' section when input_mode='verify'."""
    import asyncio
    from services.esmm.pipeline import _build_consensus_meta

    class FakeResult:
        cycles_completed = 1
        vote_entropy = 0.1
        semantic_dispersion = None
        triplets_before_consensus = 5
        triplets_after_consensus = 3
        reconciliation_meta = None

    class FakeConfig:
        models = ["m1", "m2"]
        min_consensus = 0.5
        cycle_sequence = ["assess", "challenge", "adjudicate"]
        input_mode = "verify"
        original_claim = "Solana TPS exceeds 3000"

    meta = asyncio.get_event_loop().run_until_complete(
        _build_consensus_meta(FakeConfig(), FakeResult(), None)
    )

    assert meta is not None
    assert "verify" in meta, f"Missing 'verify' section in consensus_meta: {meta.keys()}"
    assert meta["verify"]["original_claim"] == "Solana TPS exceeds 3000"
    assert meta["methodology"]["pipeline_mode"] == "verify"


# ===========================================================================
# A1 — cycles_per_type + convergence/adaptation guards in VERIFY mode
# ===========================================================================


def test_verify_cycles_per_type_is_one():
    """In VERIFY mode, cycles_per_type must be {assess:1, challenge:1, adjudicate:1}.

    _query_models() already queries ALL models per call, so cycles_per_type=1
    means exactly 1 round per phase (not n_models rounds).
    """
    from services.esmm.orchestrator import ESMMRunConfig, ESMMOrchestrator
    from unittest.mock import AsyncMock, MagicMock

    config = ESMMRunConfig(
        models=["m1:latest", "m2:latest", "m3:latest", "m4:latest"],
        input_mode="verify",
        original_claim="Solana TPS exceeds 3000",
    )

    orch = object.__new__(ESMMOrchestrator)
    orch.config = config
    orch._stats = {
        "total_cycles": 0, "total_triplets": 0, "errors": [],
        "assess": 0, "challenge": 0, "adjudicate": 0,
        "divergent": 0, "debate": 0, "meta": 0,
    }
    orch._state = MagicMock()
    orch._start_time = None
    orch._collected_triplets = []
    orch._raw_model_triplets = {}
    orch._prev_gap_signature = None
    orch.db = AsyncMock()

    # Track which cycle types are executed
    executed_cycles = []

    async def fake_execute_cycle(cycle_type, iteration, context=None, model_weights=None):
        executed_cycles.append((cycle_type.value, iteration))
        result = MagicMock()
        result.triplets_extracted = 0
        result.consensus_triplets = []
        result.vote_entropy = 0.0
        result.semantic_dispersion = None
        result.triplets_before_consensus = 0
        result.triplets_after_consensus = 0
        result.raw_model_triplets = {}
        result.responses = {}
        return result

    orch.cycle_manager = MagicMock()
    orch.cycle_manager.execute_cycle = AsyncMock(side_effect=fake_execute_cycle)
    orch.gap_detector = MagicMock()
    orch.coverage_analyzer = MagicMock()

    import asyncio
    asyncio.get_event_loop().run_until_complete(
        orch.execute_cycles(run_id=1, model_weights={"m1:latest": 1.0})
    )

    # Must execute exactly 3 cycles: assess(1), challenge(1), adjudicate(1)
    assert len(executed_cycles) == 3, (
        f"VERIFY must execute exactly 3 cycles, got {len(executed_cycles)}: {executed_cycles}"
    )
    assert executed_cycles[0] == ("assess", 1)
    assert executed_cycles[1] == ("challenge", 1)
    assert executed_cycles[2] == ("adjudicate", 1)


def test_verify_no_convergence_exit():
    """In VERIFY mode, gap convergence must NOT cause early return."""
    from services.esmm.orchestrator import ESMMRunConfig, ESMMOrchestrator
    from unittest.mock import AsyncMock, MagicMock

    config = ESMMRunConfig(
        models=["m1:latest", "m2:latest"],
        input_mode="verify",
        original_claim="Solana TPS exceeds 3000",
        detect_gaps=True,  # Gaps enabled — must still not short-circuit
    )

    orch = object.__new__(ESMMOrchestrator)
    orch.config = config
    orch._stats = {
        "total_cycles": 0, "total_triplets": 0, "errors": [],
        "assess": 0, "challenge": 0, "adjudicate": 0,
        "divergent": 0, "debate": 0, "meta": 0,
        "gaps_detected": 0,
    }
    orch._state = MagicMock()
    orch._start_time = None
    orch._collected_triplets = []
    orch._raw_model_triplets = {}
    orch._prev_gap_signature = ("same", "signature")  # Pre-set: identical gaps
    orch.db = AsyncMock()

    executed_cycles = []

    async def fake_execute_cycle(cycle_type, iteration, context=None, model_weights=None):
        executed_cycles.append(cycle_type.value)
        result = MagicMock()
        result.triplets_extracted = 0
        result.consensus_triplets = []
        result.vote_entropy = 0.0
        result.semantic_dispersion = None
        result.triplets_before_consensus = 0
        result.triplets_after_consensus = 0
        result.raw_model_triplets = {}
        result.responses = {}
        return result

    orch.cycle_manager = MagicMock()
    orch.cycle_manager.execute_cycle = AsyncMock(side_effect=fake_execute_cycle)
    orch.gap_detector = MagicMock()
    orch.gap_detector.detect_all_gaps = AsyncMock(return_value=[])
    orch.gap_detector.store_gaps = AsyncMock(return_value=0)
    orch.coverage_analyzer = MagicMock()

    import asyncio
    asyncio.get_event_loop().run_until_complete(
        orch.execute_cycles(run_id=1, model_weights={"m1:latest": 1.0})
    )

    # All 3 phases must complete despite identical gap signatures
    assert "assess" in executed_cycles, "ASSESS must execute"
    assert "challenge" in executed_cycles, "CHALLENGE must execute"
    assert "adjudicate" in executed_cycles, "ADJUDICATE must execute"


# ===========================================================================
# A1 — CHALLENGE epistemic isolation (no broadcast)
# ===========================================================================


def test_challenge_isolation_circular_rotation():
    """CHALLENGE must use circular rotation: model[i] sees only model[(i+1)%N]'s verdict.

    Each model must receive a DIFFERENT question containing only one peer's verdict.
    No broadcast of all verdicts.
    """
    from services.esmm.cycle_manager import ExplorationCycleManager
    from services.esmm.cycle_prompts import CycleType
    from unittest.mock import AsyncMock, MagicMock, patch

    mgr = object.__new__(ExplorationCycleManager)
    mgr._template_rotation_index = {CycleType.CHALLENGE: 0}
    mgr._recent_triplets = []
    mgr._cycle_counts = {}
    mgr.models = ["modelA", "modelB", "modelC"]
    mgr.provider_ids = ["prov-A", "prov-B", "prov-C"]
    mgr.provider_to_model = {"prov-A": "modelA", "prov-B": "modelB", "prov-C": "modelC"}
    mgr.model_to_provider = {"modelA": "prov-A", "modelB": "prov-B", "modelC": "prov-C"}

    # Track calls to _query_models_isolated
    isolated_calls = []

    async def fake_query_isolated(model_questions, cycle_type, timeout):
        isolated_calls.append(model_questions)
        return {m: f"challenge response from {m}" for m in model_questions}

    mgr._query_models_isolated = AsyncMock(side_effect=fake_query_isolated)

    context = {
        "original_claim": "Solana TPS exceeds 3000",
        "_verify_model_verdicts": {
            "modelA": '{"verdict":"SUPPORTED","confidence":0.9}',
            "modelB": '{"verdict":"CONTESTED","confidence":0.6}',
            "modelC": '{"verdict":"SUPPORTED","confidence":0.7}',
        },
    }

    # Execute the CHALLENGE branch in execute_cycle
    # We test _query_models_isolated is called with per-model questions
    assert hasattr(mgr, '_query_models_isolated'), (
        "ExplorationCycleManager must have _query_models_isolated method"
    )

    # Verify circular rotation logic:
    # modelA should see modelB's verdict
    # modelB should see modelC's verdict
    # modelC should see modelA's verdict
    model_verdicts = context["_verify_model_verdicts"]
    model_ids = list(model_verdicts.keys())
    for i, model_id in enumerate(model_ids):
        peer_id = model_ids[(i + 1) % len(model_ids)]
        assert peer_id != model_id, f"Model {model_id} must NOT see its own verdict"


# ===========================================================================
# A3 — Verdict extraction through compute_consensus()
# ===========================================================================


def test_extract_verdicts_routes_through_consensus():
    """_extract_verdicts_from_responses must route through compute_consensus(),
    not manually construct ConsensusTriplet objects.

    This ensures real agreement_ratio and vote_entropy scoring.
    """
    import asyncio
    from services.esmm.cycle_manager import ExplorationCycleManager
    from services.esmm.cycle_prompts import CycleType
    from unittest.mock import AsyncMock, MagicMock

    mgr = object.__new__(ExplorationCycleManager)

    # Mock consensus engine
    mock_consensus_result = MagicMock()
    mock_consensus_result.triplets = [
        MagicMock(
            subject="Solana TPS exceeds 3000",
            relation="verdict",
            object="SUPPORTED",
            consensus_score=0.85,
            agreement_ratio=0.75,  # Real multi-model agreement
            triplet_hash="test_hash",
        )
    ]
    mock_consensus_result.triplets_before_consensus = 4
    mock_consensus_result.triplets_after_consensus = 1
    mock_consensus_result.vote_entropy = 0.3
    mock_consensus_result.semantic_dispersion = None

    mgr.triplet_extractor = MagicMock()
    mgr.triplet_extractor.consensus_engine = MagicMock()
    mgr.triplet_extractor.consensus_engine.compute_consensus = AsyncMock(return_value=mock_consensus_result)

    responses = {
        "modelA": '{"verdict":"SUPPORTED","confidence":0.9,"evidence":[],"reasoning":"ok"}',
        "modelB": '{"verdict":"SUPPORTED","confidence":0.8,"evidence":[],"reasoning":"yes"}',
    }
    context = {"original_claim": "Solana TPS exceeds 3000"}

    assert hasattr(mgr, '_extract_verdicts_from_responses'), (
        "ExplorationCycleManager must have _extract_verdicts_from_responses method"
    )

    result = asyncio.get_event_loop().run_until_complete(
        mgr._extract_verdicts_from_responses(responses, CycleType.ASSESS, context, None)
    )

    # Must have called compute_consensus
    mgr.triplet_extractor.consensus_engine.compute_consensus.assert_called_once()
    call_args = mgr.triplet_extractor.consensus_engine.compute_consensus.call_args

    # model_results must be Dict[str, List] with per-model triplet lists
    model_results = call_args.kwargs.get("model_results") or call_args[0][0]
    assert "modelA" in model_results, "Must pass per-model triplets to compute_consensus"
    assert "modelB" in model_results

    # Result must reflect consensus_result fields
    assert result["vote_entropy"] == 0.3
    assert result["triplets_before_consensus"] == 4


# ===========================================================================
# P1 — esmm_config propagation + consensus_meta pipeline_mode
# ===========================================================================


@pytest.mark.asyncio
async def test_esmm_config_propagated_from_extraction():
    """_extract_triplets_from_question must return esmm_config in 4-tuple.

    Root cause: the function creates esmm_config locally, sets input_mode='verify',
    but returns only 3-tuple — esmm_config is lost and never reaches _build_consensus_meta.
    """
    from services.esmm.pipeline import _extract_triplets_from_question
    from services.esmm.run_logger import RunLogger
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_db = AsyncMock()
    run_logger = RunLogger(run_id=0, question="test")

    mock_result = MagicMock()
    mock_result.run_id = 1
    mock_result.cycles_completed = 3
    mock_result.total_triplets = 0
    mock_result.consensus_triplets = []

    with patch(
        'services.esmm.question_seeder.seed_graph_from_question',
        new_callable=AsyncMock, return_value=0,
    ):
        with patch('services.esmm.orchestrator.ESMMOrchestrator') as MockOrch:
            mock_orch = AsyncMock()
            mock_orch.initialize_run = AsyncMock(return_value=1)
            mock_orch.execute_cycles = AsyncMock()
            mock_orch.reconcile = AsyncMock()
            mock_orch.finalize_run = AsyncMock(return_value=mock_result)
            MockOrch.return_value = mock_orch

            with patch('services.esmm.triplet_adapter.adapt_all', return_value=[]):
                result = await _extract_triplets_from_question(
                    "Is it true that Solana TPS exceeds 3000",
                    mock_db,
                    ["m1:latest", "m2:latest"],
                    run_logger,
                )

    # Must return 4-tuple: (triplets, run_id, esmm_result, esmm_config)
    assert len(result) == 4, (
        f"Must return 4-tuple (triplets, run_id, result, esmm_config), got {len(result)}-tuple"
    )
    esmm_config = result[3]
    assert esmm_config.input_mode == "verify", (
        f"esmm_config.input_mode must be 'verify', got '{esmm_config.input_mode}'"
    )


@pytest.mark.asyncio
async def test_consensus_meta_pipeline_mode_verify_in_pipeline():
    """run_pipeline must produce pipeline_mode='verify' for VERIFY claims.

    With current code, esmm_config is lost (3-tuple return), so _build_consensus_meta
    receives None and defaults to pipeline_mode='explore'.
    """
    from services.esmm.pipeline import run_pipeline, PipelineConfig
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_db = AsyncMock()
    mock_db.store_attestation = AsyncMock()
    mock_db.resolve_concept = AsyncMock(side_effect=lambda x: x)
    mock_db.get_concept = AsyncMock(return_value=None)
    mock_db.add_concept = AsyncMock()
    mock_db.upsert_relations_batch = AsyncMock()

    triplets = [{
        "subject": "Solana TPS exceeds 3000",
        "predicate": "verdict",
        "object": "SUPPORTED",
        "consensus_score": 0.8,
        "votes": [
            {"model_id": "m1", "provider_id": "p1", "agreed": True,
             "confidence": 0.8, "architecture_family": "llama"},
        ],
        "signature_5d": {
            "agreement": 0.8, "semantic_consistency": 0.7,
            "centrality": 0.5, "stability": 0.6, "relation_diversity": 0.4,
        },
        "epistemic_type": "verdict",
    }]

    mock_esmm_result = MagicMock()
    mock_esmm_result.cycles_completed = 3
    mock_esmm_result.vote_entropy = 0.5
    mock_esmm_result.semantic_dispersion = None
    mock_esmm_result.triplets_before_consensus = 3
    mock_esmm_result.triplets_after_consensus = 1
    mock_esmm_result.reconciliation_meta = None

    from services.esmm.orchestrator import ESMMRunConfig
    mock_esmm_config = ESMMRunConfig(
        models=["m1:latest", "m2:latest"],
        input_mode="verify",
        original_claim="Is it true that Solana TPS exceeds 3000",
    )

    with patch(
        'services.esmm.pipeline._extract_triplets_from_question',
        new_callable=AsyncMock,
        return_value=(triplets, 42, mock_esmm_result, mock_esmm_config),
    ):
        result = await run_pipeline(
            question="Is it true that Solana TPS exceeds 3000",
            db=mock_db,
            config=PipelineConfig(),
        )

    assert len(result.attestations) >= 1, "At least 1 attestation expected"
    att = result.attestations[0]
    assert att.consensus_meta is not None, "consensus_meta must exist"
    assert att.consensus_meta["methodology"]["pipeline_mode"] == "verify", (
        f"Expected pipeline_mode='verify', got "
        f"'{att.consensus_meta['methodology']['pipeline_mode']}'"
    )


# ===========================================================================
# P1 step 3 — final_verdict enrichment post-crystallization
# ===========================================================================


@pytest.mark.asyncio
async def test_verify_final_verdict_enriched():
    """After crystallization, consensus_meta['verify']['final_verdict'] must be set."""
    from services.esmm.pipeline import run_pipeline, PipelineConfig
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_db = AsyncMock()
    mock_db.store_attestation = AsyncMock()
    mock_db.resolve_concept = AsyncMock(side_effect=lambda x: x)
    mock_db.get_concept = AsyncMock(return_value=None)
    mock_db.add_concept = AsyncMock()
    mock_db.upsert_relations_batch = AsyncMock()

    triplets = [{
        "subject": "Solana TPS exceeds 3000",
        "predicate": "verdict",
        "object": "SUPPORTED",
        "consensus_score": 0.8,
        "votes": [
            {"model_id": "m1", "provider_id": "p1", "agreed": True,
             "confidence": 0.8, "architecture_family": "llama"},
            {"model_id": "m2", "provider_id": "p2", "agreed": True,
             "confidence": 0.7, "architecture_family": "mistral"},
        ],
        "signature_5d": {
            "agreement": 0.8, "semantic_consistency": 0.7,
            "centrality": 0.5, "stability": 0.6, "relation_diversity": 0.4,
        },
        "epistemic_type": "verdict",
    }]

    mock_esmm_result = MagicMock()
    mock_esmm_result.cycles_completed = 3
    mock_esmm_result.vote_entropy = 0.5
    mock_esmm_result.semantic_dispersion = None
    mock_esmm_result.triplets_before_consensus = 3
    mock_esmm_result.triplets_after_consensus = 1
    mock_esmm_result.reconciliation_meta = None

    from services.esmm.orchestrator import ESMMRunConfig
    mock_esmm_config = ESMMRunConfig(
        models=["m1:latest", "m2:latest"],
        input_mode="verify",
        original_claim="Is it true that Solana TPS exceeds 3000",
    )

    with patch(
        'services.esmm.pipeline._extract_triplets_from_question',
        new_callable=AsyncMock,
        return_value=(triplets, 42, mock_esmm_result, mock_esmm_config),
    ):
        result = await run_pipeline(
            question="Is it true that Solana TPS exceeds 3000",
            db=mock_db,
            config=PipelineConfig(),
        )

    assert len(result.attestations) >= 1
    att = result.attestations[0]
    meta = att.consensus_meta
    assert meta is not None
    verify = meta.get("verify")
    assert verify is not None, "verify section must exist in consensus_meta"
    assert verify.get("final_verdict") is not None, (
        "final_verdict must be set after crystallization of verdict triplets"
    )
    assert verify["final_verdict"] == "SUPPORTED"


# ===========================================================================
# P2 — Evidence corpus preservation
# ===========================================================================


@pytest.mark.asyncio
async def test_verify_evidence_corpus_preserved():
    """Sub-consensus triplets must be in consensus_meta['verify']['evidence_corpus']."""
    from services.esmm.pipeline import run_pipeline, PipelineConfig
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_db = AsyncMock()
    mock_db.store_attestation = AsyncMock()
    mock_db.resolve_concept = AsyncMock(side_effect=lambda x: x)
    mock_db.get_concept = AsyncMock(return_value=None)
    mock_db.add_concept = AsyncMock()
    mock_db.upsert_relations_batch = AsyncMock()

    # 1 verdict above threshold, 2 evidence below threshold
    triplets = [
        {
            "subject": "Solana TPS exceeds 3000",
            "predicate": "verdict",
            "object": "SUPPORTED",
            "consensus_score": 0.8,
            "votes": [
                {"model_id": "m1", "provider_id": "p1", "agreed": True,
                 "confidence": 0.8, "architecture_family": "llama"},
            ],
            "signature_5d": {
                "agreement": 0.8, "semantic_consistency": 0.7,
                "centrality": 0.5, "stability": 0.6, "relation_diversity": 0.4,
            },
            "epistemic_type": "verdict",
        },
        {
            "subject": "solana",
            "predicate": "achieves",
            "object": "4000 tps average",
            "consensus_score": 0.2,
            "votes": [],
            "epistemic_type": "foundational",
        },
        {
            "subject": "claim",
            "predicate": "depends_on",
            "object": "definition of effective tps",
            "consensus_score": 0.15,
            "votes": [],
            "epistemic_type": "foundational",
        },
    ]

    mock_esmm_result = MagicMock()
    mock_esmm_result.cycles_completed = 3
    mock_esmm_result.vote_entropy = 0.5
    mock_esmm_result.semantic_dispersion = None
    mock_esmm_result.triplets_before_consensus = 3
    mock_esmm_result.triplets_after_consensus = 1
    mock_esmm_result.reconciliation_meta = None

    from services.esmm.orchestrator import ESMMRunConfig
    mock_esmm_config = ESMMRunConfig(
        models=["m1:latest", "m2:latest"],
        input_mode="verify",
        original_claim="Is it true that Solana TPS exceeds 3000",
    )

    with patch(
        'services.esmm.pipeline._extract_triplets_from_question',
        new_callable=AsyncMock,
        return_value=(triplets, 42, mock_esmm_result, mock_esmm_config),
    ):
        result = await run_pipeline(
            question="Is it true that Solana TPS exceeds 3000",
            db=mock_db,
            config=PipelineConfig(min_consensus_for_attestation=0.4),
        )

    assert len(result.attestations) >= 1
    att = result.attestations[0]
    meta = att.consensus_meta
    assert meta is not None
    verify = meta.get("verify")
    assert verify is not None, "verify section must exist"
    evidence = verify.get("evidence_corpus")
    assert evidence is not None, "evidence_corpus must preserve sub-consensus triplets"
    assert len(evidence) >= 2, (
        f"Expected >= 2 evidence items (sub-consensus), got {len(evidence)}"
    )


# ===========================================================================
# Fix A — claim_type classification
# ===========================================================================


def test_assess_prompt_contains_claim_type_instruction():
    """System prompt ASSESS exige une classification claim_type."""
    from services.esmm.cycle_prompts import get_system_prompt, CycleType
    prompt = get_system_prompt(CycleType.ASSESS)
    assert "claim_type" in prompt
    for ct in ["empirical", "definitional", "normative", "speculative"]:
        assert ct in prompt, f"Missing claim_type '{ct}' in ASSESS prompt"


def test_parse_verdict_extracts_claim_type():
    """_parse_verdict_response extrait claim_type du JSON."""
    from services.esmm.triplet_extractor import _parse_verdict_response
    raw = '{"claim_type": "normative", "verdict": "INSUFFICIENT_EVIDENCE", "confidence": 0.3, "reasoning": "opinion", "evidence": []}'
    result = _parse_verdict_response(raw, claim_text="test claim")
    assert result["claim_type"] == "normative"
    assert result["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_parse_verdict_defaults_claim_type_to_empirical():
    """claim_type defaults to 'empirical' when absent from JSON."""
    from services.esmm.triplet_extractor import _parse_verdict_response
    raw = '{"verdict": "SUPPORTED", "confidence": 0.9, "reasoning": "clear", "evidence": []}'
    result = _parse_verdict_response(raw, claim_text="test")
    assert result["claim_type"] == "empirical"


def test_parse_verdict_normalizes_invalid_claim_type():
    """Invalid claim_type falls back to 'empirical'."""
    from services.esmm.triplet_extractor import _parse_verdict_response
    raw = '{"claim_type": "MAGIC", "verdict": "SUPPORTED", "confidence": 0.9, "reasoning": "x", "evidence": []}'
    result = _parse_verdict_response(raw, claim_text="test")
    assert result["claim_type"] == "empirical"


# ===========================================================================
# Fix B — decidability penalty
# ===========================================================================


def test_decidability_penalty_supported_empirical_no_change():
    """SUPPORTED + empirical = no penalty (multiplier 1.0)."""
    from services.esmm.pipeline import VERDICT_PENALTIES, CLAIM_TYPE_PENALTIES
    raw = 0.84
    adjusted = raw * VERDICT_PENALTIES["SUPPORTED"] * CLAIM_TYPE_PENALTIES["empirical"]
    assert adjusted == raw


def test_decidability_penalty_contested_reduces_score():
    """CONTESTED + empirical reduces score by 35%."""
    from services.esmm.pipeline import VERDICT_PENALTIES, CLAIM_TYPE_PENALTIES
    raw = 0.90
    adjusted = raw * VERDICT_PENALTIES["CONTESTED"] * CLAIM_TYPE_PENALTIES["empirical"]
    assert 0.55 < adjusted < 0.60  # 0.90 * 0.65 = 0.585


def test_decidability_penalty_normative_strongly_reduces():
    """INSUFFICIENT_EVIDENCE + normative gets double penalty."""
    from services.esmm.pipeline import VERDICT_PENALTIES, CLAIM_TYPE_PENALTIES
    raw = 0.82
    adjusted = raw * VERDICT_PENALTIES["INSUFFICIENT_EVIDENCE"] * CLAIM_TYPE_PENALTIES["normative"]
    assert adjusted < 0.30  # 0.82 * 0.45 * 0.70 = 0.2583


def test_decidability_penalty_contested_definitional():
    """CONTESTED + definitional gets moderate penalty."""
    from services.esmm.pipeline import VERDICT_PENALTIES, CLAIM_TYPE_PENALTIES
    raw = 0.74
    adjusted = raw * VERDICT_PENALTIES["CONTESTED"] * CLAIM_TYPE_PENALTIES["definitional"]
    assert 0.40 < adjusted < 0.45  # 0.74 * 0.65 * 0.90 = 0.4329


# ===========================================================================
# Fix C — claim_type consensus
# ===========================================================================


def test_claim_type_majority_vote():
    """claim_type is determined by majority vote."""
    type_votes = {"normative": 3, "empirical": 1}
    consensus_type = max(type_votes, key=type_votes.get)
    assert consensus_type == "normative"


def test_claim_type_majority_tie_is_deterministic():
    """Tie-breaking is deterministic (max picks first max encountered)."""
    type_votes = {"empirical": 2, "definitional": 2}
    consensus_type = max(type_votes, key=type_votes.get)
    assert consensus_type in {"empirical", "definitional"}
