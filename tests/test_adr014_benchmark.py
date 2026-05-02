"""ADR-014 Lot 4 — Benchmark not-so-smart-contracts.

Tests purement slicer-level : pas de mock pipeline.
Les 4 contrats Solidity sont lus depuis tests/fixtures/benchmark/not_so_smart/.
NE PAS modifier les .sol.
"""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib

import json
from pathlib import Path

import pytest

BENCHMARK_DIR = Path(__file__).parent / "fixtures" / "benchmark" / "not_so_smart"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_gt() -> dict:
    """Charge ground_truth.json depuis le répertoire benchmark."""
    return json.loads((BENCHMARK_DIR / "ground_truth.json").read_text(encoding="utf-8"))


def _slice(filename: str):
    """Lance slice_contract() sur un fichier du répertoire benchmark."""
    from services.audit.contract_slicer import slice_contract

    return slice_contract(str(BENCHMARK_DIR / filename))


def _get_unit(slice_result, unit_name: str):
    """Retourne l'unité avec le nom donné, ou None."""
    return next((u for u in slice_result.units if u.unit_name == unit_name), None)


# ---------------------------------------------------------------------------
# reentrancy.sol — Reentrance — SWC-107
# ---------------------------------------------------------------------------


def test_benchmark_reentrancy_contract_name():
    """Les unités de reentrancy.sol ont contract_name == 'Reentrance'."""
    sr = _slice("reentrancy.sol")
    assert sr.units, "Aucune unité extraite"
    assert sr.units[0].contract_name == "Reentrance"


def test_benchmark_reentrancy_withdrawBalance_in_units():
    """withdrawBalance doit être capturé comme unité auditable."""
    sr = _slice("reentrancy.sol")
    names = [u.unit_name for u in sr.units]
    assert "withdrawBalance" in names


def test_benchmark_reentrancy_withdrawBalance_has_external_call():
    """withdrawBalance doit avoir external_calls non vide (.call)."""
    sr = _slice("reentrancy.sol")
    unit = _get_unit(sr, "withdrawBalance")
    assert unit is not None
    assert unit.external_calls, "withdrawBalance devrait avoir des external_calls"
    assert ".call" in unit.external_calls


def test_benchmark_reentrancy_skipped_count_zero():
    """'if' est skippé (mot-clé réservé, Fix 2 Lot A) — pas de view/pure dans reentrancy.sol."""
    sr = _slice("reentrancy.sol")
    # Fix 2 (Lot A) : 'if' filtered as reserved keyword
    assert any("if" in s for s in sr.skipped_units), (
        f"'if' doit apparaitre dans skipped_units. Got: {sr.skipped_units}"
    )
    unit_names = [u.unit_name for u in sr.units]
    assert "if" not in unit_names


# ---------------------------------------------------------------------------
# integer_overflow.sol — Overflow — SWC-101
# ---------------------------------------------------------------------------


def test_benchmark_overflow_contract_name():
    """Les unités de integer_overflow.sol ont contract_name == 'Overflow'."""
    sr = _slice("integer_overflow.sol")
    assert sr.units, "Aucune unité extraite"
    assert sr.units[0].contract_name == "Overflow"


def test_benchmark_overflow_add_in_units():
    """La fonction 'add' (vulnérable) doit être présente dans les unités auditables."""
    sr = _slice("integer_overflow.sol")
    names = [u.unit_name for u in sr.units]
    assert "add" in names


def test_benchmark_overflow_add_has_state_write():
    """La fonction 'add' doit avoir sellerBalance dans state_writes."""
    sr = _slice("integer_overflow.sol")
    unit = _get_unit(sr, "add")
    assert unit is not None
    assert "sellerBalance" in unit.state_writes


# ---------------------------------------------------------------------------
# unprotected_function.sol — Unprotected — SWC-105
# ---------------------------------------------------------------------------


def test_benchmark_unprotected_changeOwner_has_no_modifiers():
    """changeOwner (vulnérable) doit avoir modifiers == [] (pas de onlyowner)."""
    sr = _slice("unprotected_function.sol")
    unit = _get_unit(sr, "changeOwner")
    assert unit is not None, "changeOwner devrait être capturé"
    assert unit.modifiers == [], f"changeOwner ne devrait pas avoir de modifiers, got {unit.modifiers}"


def test_benchmark_unprotected_changeOwner_fixed_has_modifier():
    """changeOwner_fixed (sécurisé) doit avoir 'onlyowner' dans modifiers."""
    sr = _slice("unprotected_function.sol")
    unit = _get_unit(sr, "changeOwner_fixed")
    assert unit is not None
    assert "onlyowner" in unit.modifiers


# ---------------------------------------------------------------------------
# unchecked_call.sol — KingOfTheEtherThrone — SWC-104
# ---------------------------------------------------------------------------


def test_benchmark_unchecked_has_auditable_units():
    """unchecked_call.sol produit des unités auditables avec le bon contract_name."""
    sr = _slice("unchecked_call.sol")
    names = [u.unit_name for u in sr.units]
    assert "claimThrone" in names
    assert "sweepCommission" in names
    assert sr.units[0].contract_name == "KingOfTheEtherThrone"


def test_benchmark_unchecked_claimThrone_has_send():
    """claimThrone doit avoir '.send' dans external_calls (return non vérifié)."""
    sr = _slice("unchecked_call.sol")
    unit = _get_unit(sr, "claimThrone")
    assert unit is not None
    assert ".send" in unit.external_calls


def test_benchmark_unchecked_sweepCommission_has_send():
    """sweepCommission doit avoir '.send' dans external_calls."""
    sr = _slice("unchecked_call.sol")
    unit = _get_unit(sr, "sweepCommission")
    assert unit is not None
    assert ".send" in unit.external_calls


# ---------------------------------------------------------------------------
# Priorité de tri cross-contrat
# ---------------------------------------------------------------------------


def test_benchmark_priority_reentrancy_external_first():
    """_sort_units_by_priority : withdrawBalance (external_calls) avant addToBalance (state_writes only)."""
    from services.audit.audit_runner import _sort_units_by_priority

    sr = _slice("reentrancy.sol")
    sorted_units = _sort_units_by_priority(sr.units)

    names = [u.unit_name for u in sorted_units]
    idx_withdraw = names.index("withdrawBalance")
    idx_add = names.index("addToBalance")
    assert idx_withdraw < idx_add, (
        f"withdrawBalance ({idx_withdraw}) devrait précéder addToBalance ({idx_add})"
    )


# ---------------------------------------------------------------------------
# Intégrité du ground_truth.json
# ---------------------------------------------------------------------------


def test_benchmark_ground_truth_swc_ids_valid():
    """Tous les swc_id de ground_truth.json doivent exister dans SWC_REGISTRY."""
    from services.audit.swc_taxonomy import SWC_REGISTRY

    gt = _load_gt()
    for contract in gt["contracts"]:
        for entry in contract["ground_truth"]:
            swc_id = entry["swc_id"]
            assert swc_id in SWC_REGISTRY, f"{swc_id} introuvable dans SWC_REGISTRY"


def test_benchmark_ground_truth_four_contracts():
    """ground_truth.json doit couvrir les 4 contrats benchmark."""
    gt = _load_gt()
    assert len(gt["contracts"]) == 4
    files = {c["file"] for c in gt["contracts"]}
    assert files == {
        "reentrancy.sol",
        "integer_overflow.sol",
        "unprotected_function.sol",
        "unchecked_call.sol",
    }


def test_benchmark_ground_truth_pragma_matches_real_files():
    """Les pragma dans ground_truth.json doivent correspondre aux fichiers réels."""
    gt = _load_gt()
    for contract in gt["contracts"]:
        sol_text = (BENCHMARK_DIR / contract["file"]).read_text(encoding="utf-8")
        expected_pragma = contract["pragma"]
        assert expected_pragma in sol_text, (
            f"{contract['file']}: pragma {expected_pragma!r} non trouvé dans le fichier"
        )


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
