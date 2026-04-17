"""
Tests Phase 4.8 — Neutralité linguistique : prompts en anglais.

RED-GREEN-FIX : ces tests DOIVENT échouer avant traduction.

Vérifie que :
1. Tous les SYSTEM_PROMPTS sont en anglais (pas de marqueurs français).
2. Tous les CYCLE_TEMPLATES sont en anglais.
3. TRIPLET_EXTRACTION_PROMPT, TRIPLET_VALIDATION_PROMPT,
   RELATION_GENERATION_PROMPT, CONCEPT_EXTRACTION_PROMPT sont en anglais.
4. La directive JSON English-only est présente dans chaque system prompt
   et dans TRIPLET_EXTRACTION_PROMPT.
"""
import pytest

from services.esmm.cycle_prompts import SYSTEM_PROMPTS, CYCLE_TEMPLATES, CycleType
from services.esmm.prompts import (
    TRIPLET_EXTRACTION_PROMPT,
    TRIPLET_VALIDATION_PROMPT,
    RELATION_GENERATION_PROMPT,
    CONCEPT_EXTRACTION_PROMPT,
)


FRENCH_MARKERS = [
    "Tu es", "Quelles sont", "Décris", "Identifie", "Réponds",
    "Liste les", "Comment", "Quels concepts", "À partir de",
    "En analysant", "Y a-t-il", "Explore", "Propose",
]


class TestPromptsAreEnglish:
    """Phase 4.8 RED — all ESMM prompts must be in English."""

    def test_system_prompts_no_french(self):
        """SYSTEM_PROMPTS must not contain French markers."""
        violations = []
        for cycle_type, prompt in SYSTEM_PROMPTS.items():
            for marker in FRENCH_MARKERS:
                if marker in prompt:
                    violations.append(
                        f"SYSTEM_PROMPTS[{cycle_type.value}] contains '{marker}'"
                    )
                    break
        assert not violations, (
            "French found in SYSTEM_PROMPTS:\n" + "\n".join(violations)
        )

    def test_cycle_templates_no_french(self):
        """CYCLE_TEMPLATES must not contain French markers."""
        violations = []
        for cycle_type, templates in CYCLE_TEMPLATES.items():
            for i, template in enumerate(templates):
                for marker in FRENCH_MARKERS:
                    if marker in template:
                        violations.append(
                            f"CYCLE_TEMPLATES[{cycle_type.value}][{i}] contains '{marker}'"
                        )
                        break
        assert not violations, (
            "French found in CYCLE_TEMPLATES:\n" + "\n".join(violations)
        )

    def test_extraction_prompts_no_french(self):
        """Extraction/validation/generation/concept prompts must be English."""
        violations = []
        for name, prompt in [
            ("TRIPLET_EXTRACTION_PROMPT", TRIPLET_EXTRACTION_PROMPT),
            ("TRIPLET_VALIDATION_PROMPT", TRIPLET_VALIDATION_PROMPT),
            ("RELATION_GENERATION_PROMPT", RELATION_GENERATION_PROMPT),
            ("CONCEPT_EXTRACTION_PROMPT", CONCEPT_EXTRACTION_PROMPT),
        ]:
            for marker in FRENCH_MARKERS:
                if marker in prompt:
                    violations.append(f"{name} contains '{marker}'")
                    break
        assert not violations, (
            "French found in prompts:\n" + "\n".join(violations)
        )

    def test_json_english_directive_in_system_prompts(self):
        """Each SYSTEM_PROMPT must contain the English-only JSON directive."""
        directive_fragment = "MUST be in English"
        missing = []
        for cycle_type, prompt in SYSTEM_PROMPTS.items():
            if directive_fragment not in prompt:
                missing.append(f"SYSTEM_PROMPTS[{cycle_type.value}]")
        assert not missing, (
            f"Missing English-only directive in: {', '.join(missing)}"
        )

    def test_json_english_directive_in_extraction_prompt(self):
        """TRIPLET_EXTRACTION_PROMPT must contain the English-only directive."""
        assert "MUST be in English" in TRIPLET_EXTRACTION_PROMPT, (
            "TRIPLET_EXTRACTION_PROMPT lacks English-only JSON directive"
        )
