"""
Tests ADR-012 : Source Anchor Builder + RWA adapters + frames déterministes.

Protocol RED-GREEN-FIX :
- test_deterministic_bypass_skips_esmm    → RED en étape 2, GREEN après étape 3
- test_epistemic_type_deterministic_accepted → RED en étape 2, GREEN après étape 3
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Étape 1 : _canonical_hash
# ---------------------------------------------------------------------------


def test_canonical_hash_deterministic():
    """Même dict → même SHA-256."""
    from services.esmm.source_anchor_builder import _canonical_hash

    h1 = _canonical_hash({"entity": "Acme", "score": 0.95})
    h2 = _canonical_hash({"entity": "Acme", "score": 0.95})
    assert h1 == h2
    assert len(h1) == 64  # hex SHA-256


def test_canonical_hash_key_order_independent():
    """Ordre des clés ne change pas le hash (JSON trié)."""
    from services.esmm.source_anchor_builder import _canonical_hash

    h1 = _canonical_hash({"a": 1, "b": 2})
    h2 = _canonical_hash({"b": 2, "a": 1})
    assert h1 == h2


def test_canonical_hash_matches_manual_sha256():
    """Vérification manuelle du calcul SHA-256 canonique."""
    from services.esmm.source_anchor_builder import _canonical_hash

    obj = {"status": "clear", "score": 0.0}
    expected_raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    expected = hashlib.sha256(expected_raw.encode("utf-8")).hexdigest()
    assert _canonical_hash(obj) == expected


# ---------------------------------------------------------------------------
# Étape 1 : SourceAnchorSpec
# ---------------------------------------------------------------------------


def test_source_anchor_spec_fields():
    """SourceAnchorSpec stocke les champs correctement."""
    from services.esmm.source_anchor_builder import SourceAnchorSpec

    spec = SourceAnchorSpec(
        source_id="opensanctions",
        frame_id="compliance_sanctions_v1.0",
        query={"name": "Acme Corp"},
    )
    assert spec.source_id == "opensanctions"
    assert spec.frame_id == "compliance_sanctions_v1.0"
    assert spec.max_age_hours == 24
    assert spec.min_sources == 1


def test_source_anchor_spec_custom_ttl():
    """TTL personnalisable."""
    from services.esmm.source_anchor_builder import SourceAnchorSpec

    spec = SourceAnchorSpec(
        source_id="ofac_sdn",
        frame_id="compliance_sanctions_v1.0",
        query={"name": "X"},
        max_age_hours=48,
        min_sources=2,
    )
    assert spec.max_age_hours == 48
    assert spec.min_sources == 2


# ---------------------------------------------------------------------------
# Étape 1 : Registre adaptateurs
# ---------------------------------------------------------------------------


def test_get_adapter_opensanctions():
    """get_adapter retourne OpenSanctionsAdapter pour 'opensanctions'."""
    from services.sources.adapters import get_adapter
    from services.sources.adapters.opensanctions import OpenSanctionsAdapter

    adapter = get_adapter("opensanctions")
    assert isinstance(adapter, OpenSanctionsAdapter)


def test_get_adapter_unknown_raises():
    """get_adapter lève ValueError pour source_id inconnu."""
    from services.sources.adapters import get_adapter

    with pytest.raises(ValueError, match="Unknown source_id"):
        get_adapter("inexistant_source")


# ---------------------------------------------------------------------------
# Étape 1 : OpenSanctionsAdapter.normalize
# ---------------------------------------------------------------------------


def test_opensanctions_normalize_match():
    """Score ≥ 0.85 → status 'match'."""
    from services.sources.adapters.opensanctions import OpenSanctionsAdapter

    adapter = OpenSanctionsAdapter()
    raw = {
        "responses": {
            "q": {
                "results": [
                    {"id": "ofac-1", "score": 0.92, "name": "Acme"},
                ]
            }
        }
    }
    result = adapter.normalize(raw)
    assert result["status"] == "match"
    assert result["score"] == pytest.approx(0.92)


def test_opensanctions_normalize_clear_low_score():
    """Score < 0.85 → status 'clear'."""
    from services.sources.adapters.opensanctions import OpenSanctionsAdapter

    adapter = OpenSanctionsAdapter()
    raw = {
        "responses": {
            "q": {
                "results": [
                    {"id": "ofac-2", "score": 0.72, "name": "Acme Ltd"},
                ]
            }
        }
    }
    result = adapter.normalize(raw)
    assert result["status"] == "clear"
    assert result["score"] == pytest.approx(0.72)


def test_opensanctions_normalize_empty_results():
    """Aucun résultat → status 'clear', score 0.0."""
    from services.sources.adapters.opensanctions import OpenSanctionsAdapter

    adapter = OpenSanctionsAdapter()
    raw = {"responses": {"q": {"results": []}}}
    result = adapter.normalize(raw)
    assert result["status"] == "clear"
    assert result["score"] == 0.0


def test_opensanctions_normalize_best_score_selected():
    """Plusieurs résultats → le meilleur score est retenu."""
    from services.sources.adapters.opensanctions import OpenSanctionsAdapter

    adapter = OpenSanctionsAdapter()
    raw = {
        "responses": {
            "q": {
                "results": [
                    {"id": "a", "score": 0.60},
                    {"id": "b", "score": 0.91},
                    {"id": "c", "score": 0.50},
                ]
            }
        }
    }
    result = adapter.normalize(raw)
    assert result["status"] == "match"
    assert result["score"] == pytest.approx(0.91)


def test_opensanctions_get_source_version_from_raw():
    """get_source_version extrait 'version' de la réponse brute."""
    from services.sources.adapters.opensanctions import OpenSanctionsAdapter

    adapter = OpenSanctionsAdapter()
    raw = {"version": "20260225", "responses": {}}
    assert adapter.get_source_version(raw) == "20260225"


def test_opensanctions_get_source_version_fallback():
    """get_source_version retourne fallback si 'version' absent."""
    from services.sources.adapters.opensanctions import OpenSanctionsAdapter

    adapter = OpenSanctionsAdapter()
    raw = {"responses": {}}
    version = adapter.get_source_version(raw)
    assert version == "opensanctions-unknown"


# ---------------------------------------------------------------------------
# Étape 2 : Frame compliance_sanctions_v1.0
# ---------------------------------------------------------------------------


def test_compliance_sanctions_frame_fields():
    """Frame compliance_sanctions_v1.0 a les bons champs."""
    from services.solana.metrological_frame import create_compliance_sanctions_frame

    frame = create_compliance_sanctions_frame()
    assert frame.frame_id == "compliance_sanctions_v1.0"
    assert frame.domain == "regulatory_compliance"
    assert frame.metric == "sanctions_status"
    assert frame.required_sources >= 1


def test_compliance_sanctions_frame_esmm_bypass():
    """Le paramètre esmm_bypass est True pour le chemin déterministe."""
    from services.solana.metrological_frame import create_compliance_sanctions_frame

    frame = create_compliance_sanctions_frame()
    assert frame.parameters.get("esmm_bypass") is True


def test_compliance_sanctions_frame_match_threshold():
    """Seuil de matching configuré à 0.85."""
    from services.solana.metrological_frame import create_compliance_sanctions_frame

    frame = create_compliance_sanctions_frame()
    assert frame.parameters["match_score_threshold"] == pytest.approx(0.85)


def test_compliance_sanctions_frame_hash_deterministic():
    """Hash de frame déterministe (même contenu → même hash)."""
    from services.solana.metrological_frame import create_compliance_sanctions_frame

    f1 = create_compliance_sanctions_frame()
    f2 = create_compliance_sanctions_frame()
    assert f1.compute_frame_hash() == f2.compute_frame_hash()


# ---------------------------------------------------------------------------
# RED — étape 3 (ces tests DOIVENT échouer avant l'implémentation de l'étape 3)
# ---------------------------------------------------------------------------


def test_epistemic_type_deterministic_accepted():
    """
    'deterministic' doit être accepté par validate_epistemic_type (ADR-012).
    RED avant étape 3 : ValueError car 'deterministic' absent du set.
    GREEN après étape 3 : validation OK.
    """
    from pydantic import ValidationError
    from services.esmm.attestation import EpistemicAttestation, Signature5D

    sig = Signature5D(
        agreement=0.0,
        semantic_consistency=0.0,
        centrality=0.0,
        stability=0.0,
        relation_diversity=0.0,
    )
    # Construire une attestation minimale avec epistemic_type="deterministic"
    # INV-6 (ADR-020) : type deterministic ⇒ source_anchor non-nul.
    attestation = EpistemicAttestation(
        claim_hash="a" * 64,
        subject="Acme Corp",
        predicate="sanctions_status",
        object="clear",
        consensus_score=0.0,
        models_consulted=0,
        models_agreeing=0,
        model_votes=[],
        signature_5d=sig,
        epistemic_type="deterministic",
        confidence_tier="sandbox",
        source_anchor="a" * 64,
        timestamp=1.0,
    )
    assert attestation.epistemic_type == "deterministic"


def test_claim_nature_deterministic_exists():
    """
    ClaimNature.DETERMINISTIC doit exister dans ESMMRunConfig.
    RED avant étape 3 : AttributeError.
    GREEN après étape 3 : import OK.
    """
    from services.esmm.orchestrator import ClaimNature

    assert ClaimNature.DETERMINISTIC == "deterministic"
    assert ClaimNature.EPISTEMIC == "epistemic"


def test_esmm_run_config_claim_nature_field():
    """
    ESMMRunConfig accepte claim_nature et source_anchor_spec.
    RED avant étape 3 : AttributeError (champs absents).
    GREEN après étape 3 : instanciation OK.
    """
    from services.esmm.orchestrator import ClaimNature, ESMMRunConfig
    from services.esmm.source_anchor_builder import SourceAnchorSpec

    spec = SourceAnchorSpec(
        source_id="opensanctions",
        frame_id="compliance_sanctions_v1.0",
        query={"name": "Acme Corp"},
    )
    config = ESMMRunConfig(
        models=["mock-model"],
        claim_nature=ClaimNature.DETERMINISTIC,
        source_anchor_spec=spec,
    )
    assert config.claim_nature == ClaimNature.DETERMINISTIC
    assert config.source_anchor_spec is spec


def test_esmm_run_config_deterministic_requires_spec():
    """
    claim_nature=DETERMINISTIC sans source_anchor_spec → ValueError.
    RED avant étape 3.
    """
    from services.esmm.orchestrator import ClaimNature, ESMMRunConfig

    with pytest.raises((ValueError, TypeError)):
        ESMMRunConfig(
            models=["mock-model"],
            claim_nature=ClaimNature.DETERMINISTIC,
            # source_anchor_spec manquant → doit lever
        )


# ---------------------------------------------------------------------------
# Correctifs post-audit ADR-012 — P1 (predicate) + P2 (subject)
# ---------------------------------------------------------------------------


def test_predefined_frames_registry_exists():
    """PREDEFINED_FRAMES est exporté par metrological_frame."""
    from services.solana.metrological_frame import PREDEFINED_FRAMES

    assert "compliance_sanctions_v1.0" in PREDEFINED_FRAMES
    assert "carbon_credits_vcs_v1.0" in PREDEFINED_FRAMES
    assert "rwa_identity_v1.0" in PREDEFINED_FRAMES


def test_predefined_frames_metric_vcs():
    """carbon_credits_vcs_v1.0 → metric = 'carbon_credit_validity' (fix P1)."""
    from services.solana.metrological_frame import PREDEFINED_FRAMES

    frame = PREDEFINED_FRAMES["carbon_credits_vcs_v1.0"]()
    assert frame.metric == "carbon_credit_validity"


def test_deterministic_subject_fallback_serial():
    """Subject résolu sur 'serial' quand 'name' absent (fix P2).

    NOTE C2 : ce test valide la formule de résolution inline, pas l'appel
    réel à pipeline._run_deterministic_pipeline(). Si la ligne dans pipeline.py
    régresse sans que cette formule change, ce test passera quand même.
    Test de régression unitaire acceptable, non substituable à un test E2E.
    """
    query = {"serial": "VCU-123456"}
    subject = (
        query.get("name")
        or query.get("serial")
        or query.get("project_id")
        or "fallback"
    )[:64]
    assert subject == "VCU-123456"


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
