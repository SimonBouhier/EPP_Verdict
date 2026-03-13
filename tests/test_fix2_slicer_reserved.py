"""
Fix 2 — RED tests : filtrage des unités fantômes (mots-clés Solidity réservés)

Ces tests DOIVENT échouer avant l'implémentation du filtre dans contract_slicer.py.
"""

import pytest
from pathlib import Path


REENTRANCY_SOL = (
    Path(__file__).parent / "fixtures" / "benchmark" / "not_so_smart" / "reentrancy.sol"
)


def test_slicer_rejects_reserved_keyword_units():
    """
    Le slicer ne doit PAS produire d'unités dont le nom est un mot-clé Solidity réservé.
    Actuellement, reentrancy.sol produit une unité 'if' — ce test doit échouer (RED).
    """
    from services.audit.contract_slicer import slice_contract

    assert REENTRANCY_SOL.exists(), f"Fixture manquante : {REENTRANCY_SOL}"

    result = slice_contract(str(REENTRANCY_SOL))

    unit_names = [u.unit_name for u in result.units]
    assert "if" not in unit_names, (
        f"'if' est un mot-clé réservé Solidity et ne doit pas apparaître dans units. "
        f"unit_names={unit_names}"
    )


def test_slicer_reserved_keywords_appear_in_skipped():
    """
    SOLIDITY_RESERVED_KEYWORDS doit exister dans contract_slicer et contenir les
    mots-clés de contrôle de flux courants.
    """
    from services.audit import contract_slicer

    assert hasattr(contract_slicer, "SOLIDITY_RESERVED_KEYWORDS"), (
        "SOLIDITY_RESERVED_KEYWORDS doit être un attribut public de contract_slicer"
    )

    reserved = contract_slicer.SOLIDITY_RESERVED_KEYWORDS
    required = {"if", "else", "for", "while", "do", "return"}
    missing = required - reserved
    assert not missing, (
        f"SOLIDITY_RESERVED_KEYWORDS manque les mots-clés : {missing}"
    )
