"""
Fix 1 — RED tests : subject_override pour attestations d'audit.

Le subject des attestations doit être "ContractName::unitName"
au lieu du prompt ASSESS_AUDIT brut (800+ chars).

Ces tests DOIVENT échouer avant l'implémentation.
"""


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
