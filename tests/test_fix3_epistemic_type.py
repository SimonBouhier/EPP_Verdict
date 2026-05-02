"""
Fix 3 — RED tests : epistemic_type="security_audit" pour les attestations d'audit.

Ces tests DOIVENT échouer avant l'implémentation.
"""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


import pytest
from pydantic import ValidationError


def _make_attestation_kwargs(epistemic_type: str) -> dict:
    """Minimal kwargs pour créer un EpistemicAttestation valide."""
    import time
    return dict(
        claim_hash="a" * 64,
        subject="TestContract::testFunc",
        predicate="contains",
        object="reentrancy vulnerability",
        consensus_score=0.7,
        models_consulted=2,
        models_agreeing=2,
        model_votes=[],
        epistemic_type=epistemic_type,
        confidence_tier="proposition",
        timestamp=time.time(),
        signature_5d={
            "agreement": 0.7,
            "semantic_consistency": 0.7,
            "centrality": 0.7,
            "stability": 0.7,
            "relation_diversity": 0.7,
        },
    )


def test_audit_pipeline_config_sets_security_audit():
    """
    EpistemicAttestation doit accepter epistemic_type="security_audit".
    Actuellement, field_validator rejette cette valeur — RED.
    """
    from services.esmm.attestation import EpistemicAttestation

    # Doit lever ValidationError avant le fix
    # Après le fix, doit créer l'attestation sans erreur
    attestation = EpistemicAttestation(**_make_attestation_kwargs("security_audit"))
    assert attestation.epistemic_type == "security_audit"


def test_foundational_is_not_used_for_audit():
    """
    'security_audit' != 'foundational' : les deux configs sont distinctes.
    """
    from services.esmm.pipeline import PipelineConfig

    config_default = PipelineConfig()
    config_audit = PipelineConfig(default_epistemic_type="security_audit")

    assert config_default.default_epistemic_type != "security_audit", (
        "Le PipelineConfig par défaut ne doit pas être 'security_audit'"
    )
    assert config_audit.default_epistemic_type == "security_audit"


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
