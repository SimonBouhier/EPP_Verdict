"""
Fix 1 — RED tests : subject_override pour attestations d'audit.

Le subject des attestations doit être "ContractName::unitName"
au lieu du prompt ASSESS_AUDIT brut (800+ chars).

Ces tests DOIVENT échouer avant l'implémentation.
"""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib



def test_esmm_run_config_accepts_subject_override():
    """
    ESMMRunConfig doit avoir un champ subject_override Optional[str] = None.
    RED avant Fix 1.
    """
    from services.esmm.orchestrator import ESMMRunConfig

    # Doit accepter subject_override sans erreur
    cfg = ESMMRunConfig(
        models=["model_a"],
        subject_override="Reentrance::withdrawBalance",
    )
    assert cfg.subject_override == "Reentrance::withdrawBalance", (
        f"subject_override attendu 'Reentrance::withdrawBalance', obtenu {cfg.subject_override!r}"
    )


def test_esmm_run_config_subject_override_default_none():
    """
    ESMMRunConfig sans subject_override → None par défaut.
    """
    from services.esmm.orchestrator import ESMMRunConfig

    cfg = ESMMRunConfig(models=["model_a"])
    assert cfg.subject_override is None, (
        f"subject_override doit être None par défaut, obtenu {cfg.subject_override!r}"
    )


def test_pipeline_uses_subject_override_in_crystallization():
    """
    Quand ESMMRunConfig.subject_override est défini, le pipeline doit utiliser
    cette valeur comme subject dans crystallize() et compute_claim_hash().

    Vérifie via inspection du source que effective_subject est calculé.
    RED avant Fix 1.
    """
    import inspect
    from services.esmm import pipeline as pipeline_module

    source = inspect.getsource(pipeline_module)

    assert "effective_subject" in source, (
        "pipeline.py doit définir 'effective_subject' pour l'override subject (Fix 1 Lot A)"
    )
    assert "subject_override" in source, (
        "pipeline.py doit référencer 'subject_override' (Fix 1 Lot A)"
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
