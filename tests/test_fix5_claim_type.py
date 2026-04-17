"""
Fix 5 — RED tests : claim_type="security_audit" override dans pipeline.py

Ces tests DOIVENT échouer/passer selon l'état d'implémentation.
"""


def test_security_audit_claim_type_penalty_exists():
    """
    CLAIM_TYPE_PENALTIES["security_audit"] doit exister avec valeur 1.0.
    Ce test doit déjà passer (la pénalité existe mais n'est jamais activée).
    """
    from services.esmm.pipeline import CLAIM_TYPE_PENALTIES

    assert "security_audit" in CLAIM_TYPE_PENALTIES, (
        "CLAIM_TYPE_PENALTIES manque la clé 'security_audit'"
    )
    assert CLAIM_TYPE_PENALTIES["security_audit"] == 1.0, (
        f"Pénalité attendue 1.0, obtenu {CLAIM_TYPE_PENALTIES['security_audit']}"
    )


def test_security_audit_claim_type_forces_override():
    """
    Quand default_epistemic_type='security_audit', verify_claim_type doit être 'security_audit'
    indépendamment de ce que les LLMs retournent.

    Ce test vérifie l'override via PipelineConfig — RED avant Fix 5.
    """
    from services.esmm.pipeline import PipelineConfig

    # Vérifier que default_epistemic_type est correctement stocké
    config = PipelineConfig(default_epistemic_type="security_audit")
    assert config.default_epistemic_type == "security_audit"

    # Vérifier que CLAIM_TYPE_PENALTIES contient la clé "security_audit" (pénalité neutre)
    from services.esmm.pipeline import CLAIM_TYPE_PENALTIES
    assert CLAIM_TYPE_PENALTIES.get("security_audit") == 1.0, (
        "La pénalité pour 'security_audit' doit être 1.0 (neutre = pas de pénalité)"
    )

    # Vérifier que le code pipeline applique l'override (inspection du source)
    import inspect
    from services.esmm import pipeline as pipeline_module
    source = inspect.getsource(pipeline_module)

    assert 'config.default_epistemic_type == "security_audit"' in source, (
        "pipeline.py doit contenir l'override claim_type pour security_audit (Fix 5 Lot A)"
    )
    assert 'verify_claim_type = "security_audit"' in source, (
        "pipeline.py doit forcer verify_claim_type='security_audit' pour les audits (Fix 5 Lot A)"
    )
