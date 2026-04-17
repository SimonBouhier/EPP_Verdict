"""ADR-014 Lot 1 — Tests: Contract Slicer."""
from pathlib import Path

import pytest

from services.audit.contract_slicer import ContractSliceResult, ContractUnit, slice_contract

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def test_reentrancy_vulnerable_has_external_calls():
    result = slice_contract(str(FIXTURES / "reentrancy_vulnerable.sol"))
    units_with_calls = [u for u in result.units if u.external_calls]
    assert len(units_with_calls) >= 1, "Expected at least one unit with external_calls"


def test_access_control_has_admin_unit():
    result = slice_contract(str(FIXTURES / "access_control_simple.sol"))
    admin_units = [u for u in result.units if u.access_level == "admin"]
    assert len(admin_units) >= 1, "Expected at least one unit with access_level='admin'"


def test_safe_token_all_units_have_visibility():
    result = slice_contract(str(FIXTURES / "safe_token.sol"))
    assert len(result.units) > 0
    for unit in result.units:
        assert unit.visibility != "", f"Unit {unit.unit_name!r} has empty visibility"


def test_contract_hash_is_64_hex_chars():
    result = slice_contract(str(FIXTURES / "reentrancy_vulnerable.sol"))
    assert len(result.contract_hash) == 64
    assert all(c in "0123456789abcdef" for c in result.contract_hash)


def test_slice_strategy_is_function_level_v1():
    result = slice_contract(str(FIXTURES / "reentrancy_vulnerable.sol"))
    assert result.slice_strategy == "function_level_v1"


def test_skipped_units_is_list():
    result = slice_contract(str(FIXTURES / "safe_token.sol"))
    assert isinstance(result.skipped_units, list)


def test_safe_token_view_functions_are_skipped():
    result = slice_contract(str(FIXTURES / "safe_token.sol"))
    # balanceOf and allowance are view without external calls — should be skipped
    assert len(result.skipped_units) >= 1


def test_context_imports_is_non_empty():
    result = slice_contract(str(FIXTURES / "reentrancy_vulnerable.sol"))
    assert len(result.units) > 0
    assert result.units[0].context_imports != ""


def test_line_range_start_less_than_end():
    result = slice_contract(str(FIXTURES / "reentrancy_vulnerable.sol"))
    assert len(result.units) > 0
    for unit in result.units:
        assert unit.line_range[0] < unit.line_range[1], (
            f"Unit {unit.unit_name!r} has invalid line_range: {unit.line_range}"
        )


def test_contract_name_extracted():
    result = slice_contract(str(FIXTURES / "reentrancy_vulnerable.sol"))
    assert result.units[0].contract_name == "VulnerableVault"


def test_unit_id_is_16_hex_chars():
    result = slice_contract(str(FIXTURES / "reentrancy_vulnerable.sol"))
    assert len(result.units) > 0
    for unit in result.units:
        assert len(unit.unit_id) == 16
        assert all(c in "0123456789abcdef" for c in unit.unit_id)


def test_result_is_contract_slice_result():
    result = slice_contract(str(FIXTURES / "reentrancy_vulnerable.sol"))
    assert isinstance(result, ContractSliceResult)


def test_withdraw_has_state_writes():
    result = slice_contract(str(FIXTURES / "reentrancy_vulnerable.sol"))
    withdraw_units = [u for u in result.units if u.unit_name == "withdraw"]
    assert len(withdraw_units) == 1
    assert len(withdraw_units[0].state_writes) >= 1
