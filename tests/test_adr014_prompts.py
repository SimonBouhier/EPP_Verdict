"""ADR-014 Lot 2 — Tests: Prompts AUDIT + CLAIM_TYPE_PENALTIES."""
import pytest

from services.esmm.cycle_prompts import (
    CycleType,
    CYCLE_TEMPLATES,
    SYSTEM_PROMPTS,
    get_template,
    get_system_prompt,
)
from services.esmm.pipeline import CLAIM_TYPE_PENALTIES


# ===========================================================================
# Existence des 3 nouveaux CycleType
# ===========================================================================


def test_cycle_type_assess_audit_exists():
    assert CycleType.ASSESS_AUDIT == "assess_audit"


def test_cycle_type_challenge_audit_exists():
    assert CycleType.CHALLENGE_AUDIT == "challenge_audit"


def test_cycle_type_adjudicate_audit_exists():
    assert CycleType.ADJUDICATE_AUDIT == "adjudicate_audit"


# ===========================================================================
# Enregistrement dans CYCLE_TEMPLATES et SYSTEM_PROMPTS
# ===========================================================================


def test_new_audit_types_in_cycle_templates():
    for ct in (CycleType.ASSESS_AUDIT, CycleType.CHALLENGE_AUDIT, CycleType.ADJUDICATE_AUDIT):
        assert ct in CYCLE_TEMPLATES, f"{ct} missing from CYCLE_TEMPLATES"
        assert len(CYCLE_TEMPLATES[ct]) >= 1, f"{ct} needs at least 1 template"


def test_new_audit_types_in_system_prompts():
    for ct in (CycleType.ASSESS_AUDIT, CycleType.CHALLENGE_AUDIT, CycleType.ADJUDICATE_AUDIT):
        assert ct in SYSTEM_PROMPTS, f"{ct} missing from SYSTEM_PROMPTS"
        assert len(SYSTEM_PROMPTS[ct]) > 0


# ===========================================================================
# Contenu des templates
# ===========================================================================


def test_assess_audit_template_contains_function_code():
    template = get_template(CycleType.ASSESS_AUDIT)
    assert "{function_code}" in template


def test_assess_audit_template_contains_contract_context():
    template = get_template(CycleType.ASSESS_AUDIT)
    assert "{contract_context}" in template


def test_assess_audit_template_contains_unit_metadata():
    template = get_template(CycleType.ASSESS_AUDIT)
    assert "{unit_metadata}" in template


def test_assess_audit_template_has_xml_tags():
    template = get_template(CycleType.ASSESS_AUDIT)
    assert "<FUNCTION_UNDER_AUDIT>" in template
    assert "<UNIT_METADATA>" in template


def test_challenge_audit_template_contains_peer_verdict():
    template = get_template(CycleType.CHALLENGE_AUDIT)
    assert "{peer_verdict}" in template


def test_adjudicate_audit_template_contains_all_verdicts():
    template = get_template(CycleType.ADJUDICATE_AUDIT)
    assert "{all_verdicts}" in template


# ===========================================================================
# Contenu des system prompts
# ===========================================================================


def test_assess_audit_system_prompt_contains_swc():
    prompt = get_system_prompt(CycleType.ASSESS_AUDIT)
    assert "SWC" in prompt


def test_assess_audit_system_prompt_contains_vulnerability():
    prompt = get_system_prompt(CycleType.ASSESS_AUDIT)
    assert "vulnerability" in prompt.lower()


def test_assess_audit_system_prompt_requires_json():
    prompt = get_system_prompt(CycleType.ASSESS_AUDIT)
    assert "JSON" in prompt


def test_challenge_audit_system_prompt_contains_vulnerability():
    prompt = get_system_prompt(CycleType.CHALLENGE_AUDIT)
    assert "vulnerability" in prompt.lower()


def test_adjudicate_audit_system_prompt_contains_vulnerability():
    prompt = get_system_prompt(CycleType.ADJUDICATE_AUDIT)
    assert "vulnerability" in prompt.lower()


def test_all_audit_system_prompts_in_english():
    directive = "MUST be in English"
    for ct in (CycleType.ASSESS_AUDIT, CycleType.CHALLENGE_AUDIT, CycleType.ADJUDICATE_AUDIT):
        prompt = get_system_prompt(ct)
        assert directive in prompt, f"{ct} system prompt missing English directive"


def test_all_audit_system_prompts_require_json():
    for ct in (CycleType.ASSESS_AUDIT, CycleType.CHALLENGE_AUDIT, CycleType.ADJUDICATE_AUDIT):
        prompt = get_system_prompt(ct)
        assert "JSON" in prompt, f"{ct} system prompt does not require JSON output"


# ===========================================================================
# CLAIM_TYPE_PENALTIES
# ===========================================================================


def test_claim_type_penalties_security_audit_exists():
    assert "security_audit" in CLAIM_TYPE_PENALTIES


def test_claim_type_penalties_security_audit_value():
    assert CLAIM_TYPE_PENALTIES["security_audit"] == 1.0
