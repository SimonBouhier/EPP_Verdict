"""ADR-014 Lot 3 — Tests: audit_runner + AuditResult + DB isolée."""
import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures pour contrats Solidity
# ---------------------------------------------------------------------------

REENTRANCY_SOL = Path(__file__).parent / "fixtures" / "contracts" / "reentrancy_vulnerable.sol"
SAFE_TOKEN_SOL = Path(__file__).parent / "fixtures" / "contracts" / "safe_token.sol"
ACCESS_SOL = Path(__file__).parent / "fixtures" / "contracts" / "access_control_simple.sol"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_audit_db(tmp_path):
    """Crée une DB de test isolée (jamais epp_devnet.db)."""
    from database.engine import ISpaceDB

    db = ISpaceDB(str(tmp_path / "epp_audit_test.db"))
    await db.initialize()
    return db


def _make_mock_pipeline_result(severity: str = "high", consensus: float = 0.75):
    """Crée un PipelineResult mock avec consensus_meta dict (pre-DB round-trip)."""
    from services.esmm.pipeline import PipelineResult

    att = MagicMock()
    att.consensus_score = consensus
    att.consensus_meta = {"audit_meta": {"overall_risk": severity}}

    return PipelineResult(
        run_id=1,
        question="mock",
        attestations=[att],
        triplets_extracted=1,
        triplets_attested=1,
        triplets_injected=1,
        duration_ms=50.0,
        errors=[],
    )


def _make_mock_pipeline_result_str_meta(severity: str = "medium", consensus: float = 0.60):
    """PipelineResult avec consensus_meta en str JSON (post-DB round-trip)."""
    import json
    from services.esmm.pipeline import PipelineResult

    att = MagicMock()
    att.consensus_score = consensus
    att.consensus_meta = json.dumps({"audit_meta": {"overall_risk": severity}})

    return PipelineResult(
        run_id=2,
        question="mock_str",
        attestations=[att],
        triplets_extracted=1,
        triplets_attested=1,
        triplets_injected=1,
        duration_ms=60.0,
        errors=[],
    )


# ---------------------------------------------------------------------------
# Tests — AuditResult structure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_audit_returns_audit_result(tmp_path):
    """run_audit() doit retourner une instance AuditResult."""
    from services.audit.audit_runner import AuditResult, run_audit

    db = await _make_audit_db(tmp_path)
    mock_result = _make_mock_pipeline_result()

    with patch("services.audit.audit_runner.run_pipeline", new_callable=AsyncMock) as mock_pipe:
        mock_pipe.return_value = mock_result
        result = await run_audit(str(REENTRANCY_SOL), db)

    assert isinstance(result, AuditResult)


@pytest.mark.asyncio
async def test_run_audit_contract_hash_is_64_hex(tmp_path):
    """contract_hash doit être un SHA-256 hex de 64 caractères."""
    from services.audit.audit_runner import run_audit

    db = await _make_audit_db(tmp_path)
    mock_result = _make_mock_pipeline_result()

    with patch("services.audit.audit_runner.run_pipeline", new_callable=AsyncMock) as mock_pipe:
        mock_pipe.return_value = mock_result
        result = await run_audit(str(REENTRANCY_SOL), db)

    assert len(result.contract_hash) == 64
    assert all(c in "0123456789abcdef" for c in result.contract_hash)


@pytest.mark.asyncio
async def test_run_audit_total_units_audited_positive(tmp_path):
    """Le contrat reentrancy_vulnerable.sol doit produire ≥1 unité auditée."""
    from services.audit.audit_runner import run_audit

    db = await _make_audit_db(tmp_path)
    mock_result = _make_mock_pipeline_result()

    with patch("services.audit.audit_runner.run_pipeline", new_callable=AsyncMock) as mock_pipe:
        mock_pipe.return_value = mock_result
        result = await run_audit(str(REENTRANCY_SOL), db)

    assert result.total_units_audited > 0


@pytest.mark.asyncio
async def test_run_audit_aggregate_severity_in_tob_4level(tmp_path):
    """aggregate_severity doit être l'un des 4 niveaux Trail of Bits."""
    from services.audit.audit_runner import run_audit
    from services.audit.swc_taxonomy import TOB_4LEVEL

    db = await _make_audit_db(tmp_path)
    mock_result = _make_mock_pipeline_result(severity="medium")

    with patch("services.audit.audit_runner.run_pipeline", new_callable=AsyncMock) as mock_pipe:
        mock_pipe.return_value = mock_result
        result = await run_audit(str(REENTRANCY_SOL), db)

    assert result.aggregate_severity in TOB_4LEVEL


@pytest.mark.asyncio
async def test_run_audit_db_path_contains_epp_audit(tmp_path):
    """db_path dans AuditResult doit contenir 'epp_audit'."""
    from services.audit.audit_runner import run_audit

    db = await _make_audit_db(tmp_path)
    mock_result = _make_mock_pipeline_result()

    with patch("services.audit.audit_runner.run_pipeline", new_callable=AsyncMock) as mock_pipe:
        mock_pipe.return_value = mock_result
        result = await run_audit(str(REENTRANCY_SOL), db)

    assert "epp_audit" in result.db_path


@pytest.mark.asyncio
async def test_run_audit_errors_is_list(tmp_path):
    """errors doit être une liste (peut être vide)."""
    from services.audit.audit_runner import run_audit

    db = await _make_audit_db(tmp_path)
    mock_result = _make_mock_pipeline_result()

    with patch("services.audit.audit_runner.run_pipeline", new_callable=AsyncMock) as mock_pipe:
        mock_pipe.return_value = mock_result
        result = await run_audit(str(REENTRANCY_SOL), db)

    assert isinstance(result.errors, list)


@pytest.mark.asyncio
async def test_run_audit_frame_passed_to_pipeline(tmp_path):
    """Le frame 'smartcontract_audit_v1.0' doit être passé à run_pipeline."""
    from services.audit.audit_runner import run_audit
    from services.esmm.pipeline import PipelineConfig

    db = await _make_audit_db(tmp_path)
    mock_result = _make_mock_pipeline_result()

    with patch("services.audit.audit_runner.run_pipeline", new_callable=AsyncMock) as mock_pipe:
        mock_pipe.return_value = mock_result
        await run_audit(str(REENTRANCY_SOL), db, frame="smartcontract_audit_v1.0")

    assert mock_pipe.called
    # Vérifier que le config passé contient le frame
    call_kwargs = mock_pipe.call_args.kwargs
    config = call_kwargs.get("config")
    assert config is not None
    assert config.metrological_frame == "smartcontract_audit_v1.0"


@pytest.mark.asyncio
async def test_run_audit_external_calls_units_first(tmp_path):
    """Les unités avec external_calls doivent être auditées en premier (priorité)."""
    from services.audit.audit_runner import run_audit, _sort_units_by_priority
    from services.audit.contract_slicer import slice_contract

    slice_result = slice_contract(str(REENTRANCY_SOL))
    sorted_units = _sort_units_by_priority(slice_result.units)

    # Les unités avec external_calls doivent apparaître avant celles sans
    has_external = [u for u in sorted_units if u.external_calls]
    no_external = [u for u in sorted_units if not u.external_calls]

    # Vérifier l'ordre dans la liste triée
    if has_external and no_external:
        first_no_external_idx = next(
            (i for i, u in enumerate(sorted_units) if not u.external_calls), len(sorted_units)
        )
        last_external_idx = max(
            i for i, u in enumerate(sorted_units) if u.external_calls
        )
        assert last_external_idx < first_no_external_idx


@pytest.mark.asyncio
async def test_run_audit_total_units_skipped_matches_slice(tmp_path):
    """total_units_skipped doit correspondre aux unités skippées par le slicer."""
    from services.audit.audit_runner import run_audit
    from services.audit.contract_slicer import slice_contract

    db = await _make_audit_db(tmp_path)
    mock_result = _make_mock_pipeline_result()
    slice_result = slice_contract(str(SAFE_TOKEN_SOL))
    expected_skipped = len(slice_result.skipped_units)

    with patch("services.audit.audit_runner.run_pipeline", new_callable=AsyncMock) as mock_pipe:
        mock_pipe.return_value = mock_result
        result = await run_audit(str(SAFE_TOKEN_SOL), db)

    assert result.total_units_skipped == expected_skipped


@pytest.mark.asyncio
async def test_aggregate_severity_high_when_one_unit_high(tmp_path):
    """aggregate_severity == 'high' quand au moins 1 unité a severity 'high'."""
    from services.audit.audit_runner import run_audit

    db = await _make_audit_db(tmp_path)
    # Toujours retourner high
    mock_result = _make_mock_pipeline_result(severity="high")

    with patch("services.audit.audit_runner.run_pipeline", new_callable=AsyncMock) as mock_pipe:
        mock_pipe.return_value = mock_result
        result = await run_audit(str(REENTRANCY_SOL), db)

    assert result.aggregate_severity == "high"


# ---------------------------------------------------------------------------
# Tests — helpers isolés
# ---------------------------------------------------------------------------


def test_sort_units_by_priority_external_calls_first():
    """_sort_units_by_priority met les unités avec external_calls en premier."""
    from services.audit.audit_runner import _sort_units_by_priority
    from services.audit.contract_slicer import slice_contract

    slice_result = slice_contract(str(REENTRANCY_SOL))
    if not slice_result.units:
        pytest.skip("No units in contract")

    sorted_units = _sort_units_by_priority(slice_result.units)

    # Vérifier que si on a des unités avec external_calls ET des unités sans,
    # les premières viennent avant les dernières
    with_ext = [u for u in sorted_units if u.external_calls]
    without_ext = [u for u in sorted_units if not u.external_calls]

    if with_ext and without_ext:
        idx_last_with = max(i for i, u in enumerate(sorted_units) if u.external_calls)
        idx_first_without = next(i for i, u in enumerate(sorted_units) if not u.external_calls)
        assert idx_last_with < idx_first_without


def test_extract_severity_from_result_dict_meta():
    """_extract_severity_from_result gère consensus_meta dict (pre-DB)."""
    from services.audit.audit_runner import _extract_severity_from_result

    result = _make_mock_pipeline_result(severity="high")
    severity = _extract_severity_from_result(result)
    assert severity == "high"


def test_extract_severity_from_result_str_meta():
    """_extract_severity_from_result gère consensus_meta str JSON (post-DB)."""
    from services.audit.audit_runner import _extract_severity_from_result

    result = _make_mock_pipeline_result_str_meta(severity="medium")
    severity = _extract_severity_from_result(result)
    assert severity == "medium"


def test_extract_severity_from_result_empty_attestations():
    """_extract_severity_from_result retourne 'informational' si pas d'attestations."""
    from services.audit.audit_runner import _extract_severity_from_result
    from services.esmm.pipeline import PipelineResult

    result = PipelineResult(
        run_id=0,
        question="test",
        attestations=[],
        triplets_extracted=0,
        triplets_attested=0,
        triplets_injected=0,
        duration_ms=0.0,
        errors=[],
    )
    assert _extract_severity_from_result(result) == "informational"


def test_aggregate_severity_worst_wins():
    """_aggregate_severity retourne le niveau le plus sévère."""
    from services.audit.audit_runner import _aggregate_severity

    assert _aggregate_severity(["informational", "low", "high", "medium"]) == "high"
    assert _aggregate_severity(["informational", "low", "medium"]) == "medium"
    assert _aggregate_severity(["informational", "low"]) == "low"
    assert _aggregate_severity(["informational"]) == "informational"
    assert _aggregate_severity([]) == "informational"


def test_format_unit_for_audit_prompt():
    """format_unit_for_audit_prompt retourne les 3 clés requises par ASSESS_AUDIT."""
    from services.audit.audit_runner import format_unit_for_audit_prompt
    from services.audit.contract_slicer import slice_contract

    slice_result = slice_contract(str(REENTRANCY_SOL))
    if not slice_result.units:
        pytest.skip("No units")

    unit = slice_result.units[0]
    placeholders = format_unit_for_audit_prompt(unit)

    assert "contract_context" in placeholders
    assert "function_code" in placeholders
    assert "unit_metadata" in placeholders
    assert unit.source_code in placeholders["function_code"]
