"""Tests Phase 2.4 — Diversité architecturale."""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


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
