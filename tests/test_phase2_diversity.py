"""Tests Phase 2.4 — Diversité architecturale."""

from services.providers.base import infer_architecture_family, ARCHITECTURE_FAMILIES


class TestArchitectureFamilyInference:

    def test_mistral(self):
        assert infer_architecture_family("ollama::mistral:7b") == "transformer_dense"

    def test_mixtral(self):
        assert infer_architecture_family("ollama::mixtral:8x7b") == "transformer_moe"

    def test_llama(self):
        assert infer_architecture_family("ollama::llama3.1:8b") == "transformer_dense"

    def test_deepseek(self):
        assert infer_architecture_family("openai::deepseek-r1") == "transformer_moe"

    def test_gpt(self):
        assert infer_architecture_family("openai::gpt-4o-mini") == "openai_family"

    def test_claude(self):
        assert infer_architecture_family("anthropic::claude-3-haiku") == "anthropic_family"

    def test_unknown(self):
        assert infer_architecture_family("custom::novelmodel:3b") == "unknown"

    def test_diversity_count(self):
        """3 modèles de 2 familles = diversité 2."""
        models = ["mistral:7b", "llama3:8b", "mixtral:8x7b"]
        families = set(infer_architecture_family(m) for m in models)
        assert len(families) == 2  # dense + moe
