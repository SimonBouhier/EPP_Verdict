"""
Tests de conformité Python ↔ invariants Lean 4 (ADR-020).

Cette suite vérifie que le code runtime Python respecte les règles
formellement prouvées dans Formal/. Les preuves Lean spécifient le
protocole ; ces tests vérifient que l'implémentation s'y conforme.

Invariants couverts (tests unitaires sur cas spécifiques) :
  - U16 round-trip : encodage float↔u16 (bridge.py) — voir TestPyU16RoundTrip
  - INV-2 : claim hash purity (attestation.py::compute_claim_hash)
  - INV-4 : tier boundary (attestation.py::derive_confidence_tier)
  - INV-6 : deterministic ⇒ source_anchor non-nul (guards crystallize)

Le complément property-based (10 000+ inputs aléatoires) vit dans
`tests/test_lean_conformance_property.py` (P4.1, 2026-04-30).

Notes de conformité (voir ADR-020 §5) :
  - U16 round-trip : conformité stricte côté Python. Pas d'homologue
    Lean actuel — `Encoding.lean` a été supprimé en P2 (4 tautologies
    sans modélisation de Float). Les tests Python restent utiles comme
    garde-fou runtime sur les conversions de score.
  - INV-2 : Python applique `.lower().strip()` — propriété plus FORTE
            qu'INV-2 Lean. Les tests vérifient la propriété Lean + la
            normalisation Python. Pas de divergence de sécurité.
  - INV-4 : Python exige `architecture_families ≥ 2` en plus des
            conditions Lean. Python ⇒ Lean (implication sûre).
  - INV-6 : strictement enforced par un `model_validator` Pydantic
            dans `EpistemicAttestation` (ajouté 2026-04-18 suite au
            diagnostic de conformité). Deux niveaux testés : le guard
            de `crystallize()` sur `consensus_method` (pré-existant)
            et le guard Pydantic sur `epistemic_type × source_anchor`
            (aligné sur INV-6 Lean).

Voir ADR-020 §4 pour le protocole de double falsification.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.solana.bridge import float_to_u16, u16_to_float, SCORE_SCALE
from services.esmm.attestation import (
    ModelVote,
    Signature5D,
    compute_claim_hash,
    crystallize,
    derive_confidence_tier,
)


# ═══════════════════════════════════════════════════════════════
# HELPERS — construction de ModelVote/Signature5D minimaux
# ═══════════════════════════════════════════════════════════════

def _make_votes(n_agree: int, n_total: int):
    return [
        ModelVote(
            model_id=f"m_{i}",
            provider_id="mock",
            agreed=(i < n_agree),
            confidence=0.8 if i < n_agree else 0.3,
        )
        for i in range(n_total)
    ]


def _make_sig():
    return Signature5D(
        agreement=0.8,
        semantic_consistency=0.8,
        centrality=0.8,
        stability=0.8,
        relation_diversity=0.8,
    )


# ═══════════════════════════════════════════════════════════════
# U16 round-trip — conversion float ↔ u16 (bridge.py)
#
# Note (P4.1, 2026-04-30) : cette classe testait précédemment INV-1
# Lean ; mais `Formal/Formal/Encoding.lean` a été supprimé en P2 (4
# tautologies sans modélisation de Float). La classe est conservée
# pour sa valeur de garde-fou runtime sur les conversions de score
# utilisées partout (consensus_score, signature 5D), mais ne prétend
# plus tester un invariant Lean — d'où le renommage de TestInv1Encoding
# en TestPyU16RoundTrip. Le fichier n'a pas d'homologue Lean actuel.
# ═══════════════════════════════════════════════════════════════

class TestPyU16RoundTrip:
    """Round-trip Python u16 ↔ float : préserve les bornes [0, 1]
    avec tolérance 1e-4. Pas d'homologue Lean (cf. note P4.1)."""

    def test_float_to_u16_bounds_lower(self):
        assert float_to_u16(0.0) == 0

    def test_float_to_u16_bounds_upper(self):
        assert float_to_u16(1.0) == SCORE_SCALE

    def test_float_to_u16_rejects_above_one(self):
        with pytest.raises(ValueError):
            float_to_u16(1.5)

    def test_float_to_u16_rejects_below_zero(self):
        with pytest.raises(ValueError):
            float_to_u16(-0.1)

    def test_u16_to_float_bounds(self):
        assert u16_to_float(0) == 0.0
        assert u16_to_float(SCORE_SCALE) == 1.0

    def test_u16_to_float_rejects_negative(self):
        with pytest.raises(ValueError):
            u16_to_float(-1)

    def test_u16_to_float_rejects_above_scale(self):
        with pytest.raises(ValueError):
            u16_to_float(SCORE_SCALE + 1)

    def test_roundtrip_preserves_within_precision(self):
        """ADR-001 : tolérance 1e-4 sur le round-trip."""
        for val in [0.0, 0.25, 0.5, 0.85, 1.0]:
            assert abs(u16_to_float(float_to_u16(val)) - val) < 1e-4


# ═══════════════════════════════════════════════════════════════
# INV-2 — Claim Hash Purity (Formal/ClaimHash.lean)
# ═══════════════════════════════════════════════════════════════

class TestInv2ClaimHashPurity:
    """INV-2 : claim_hash ne dépend QUE de (subject, predicate, object, frame).

    Implication directe : deux attestations au noyau canonique identique
    produisent le même claim_hash (ADR-017 cross-cluster condition).
    """

    def test_same_canonical_fields_same_hash(self):
        h1 = compute_claim_hash("Iran", "has_strategy", "proxy", "geo_v1")
        h2 = compute_claim_hash("Iran", "has_strategy", "proxy", "geo_v1")
        assert h1 == h2

    def test_different_subject_different_hash(self):
        h1 = compute_claim_hash("Iran", "has_strategy", "X", "frame")
        h2 = compute_claim_hash("USA", "has_strategy", "X", "frame")
        assert h1 != h2

    def test_different_predicate_different_hash(self):
        h1 = compute_claim_hash("s", "rel_A", "o", "f")
        h2 = compute_claim_hash("s", "rel_B", "o", "f")
        assert h1 != h2

    def test_different_object_different_hash(self):
        h1 = compute_claim_hash("s", "p", "obj_A", "f")
        h2 = compute_claim_hash("s", "p", "obj_B", "f")
        assert h1 != h2

    def test_different_frame_different_hash(self):
        h1 = compute_claim_hash("Iran", "has_strategy", "X", "frame_A")
        h2 = compute_claim_hash("Iran", "has_strategy", "X", "frame_B")
        assert h1 != h2

    def test_normalization_case_insensitive(self):
        """Python > Lean (`.lower()` avant hash). ADR-020 §5.3."""
        h1 = compute_claim_hash("Iran", "has_strategy", "X", "frame")
        h2 = compute_claim_hash("IRAN", "has_strategy", "X", "frame")
        assert h1 == h2

    def test_normalization_whitespace_insensitive(self):
        """Python > Lean (`.strip()` avant hash). ADR-020 §5.3."""
        h1 = compute_claim_hash("Iran", "has_strategy", "X", "frame")
        h2 = compute_claim_hash("  Iran  ", "has_strategy", "X", "frame")
        assert h1 == h2

    def test_hash_is_64_hex_chars(self):
        """SHA-256 produit 64 caractères hex."""
        h = compute_claim_hash("s", "p", "o", "f")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ═══════════════════════════════════════════════════════════════
# INV-4 — Tier Boundary (Formal/TierBoundary.lean)
# ═══════════════════════════════════════════════════════════════

class TestInv4TierBoundary:
    """INV-4 Lean : verified ⇒ score ≥ 0.85 ∧ (models ≥ 3 ∨ anchor).

    Python exige en plus `architecture_families ≥ 2` et
    `(source_anchor ≠ None ∨ validation_count ≥ 3)`.
    Python verified ⇒ Lean verified (implication sûre, Python plus strict).
    """

    def test_low_score_never_verified(self):
        """Miroir RED-TIER-1 Lean : score < 0.85 ne donne pas verified."""
        assert derive_confidence_tier(
            0.5, models_consulted=5, architecture_families=3, source_anchor="any"
        ) != "verified"

    def test_score_just_below_threshold_not_verified(self):
        """score = 0.849 < 0.85 → pas verified (bord strict)."""
        assert derive_confidence_tier(
            0.849, models_consulted=5, architecture_families=3, source_anchor="any"
        ) != "verified"

    def test_one_model_cannot_be_verified(self):
        """Miroir RED-TIER-2 Lean : moins de 3 modèles ne donne pas verified."""
        assert derive_confidence_tier(
            0.9, models_consulted=1, architecture_families=1, source_anchor="any"
        ) != "verified"

    def test_verified_with_anchor_and_three_models(self):
        """Miroir GREEN Lean : conditions suffisantes Python → verified."""
        assert derive_confidence_tier(
            0.9, models_consulted=3, architecture_families=2, source_anchor="anchor_hex"
        ) == "verified"

    def test_verified_with_validation_count_three(self):
        """Alternative Python : validation_count ≥ 3 remplace source_anchor."""
        assert derive_confidence_tier(
            0.9, models_consulted=3, architecture_families=2, validation_count=3
        ) == "verified"

    def test_python_requires_two_architecture_families(self):
        """Python exige architecture_families ≥ 2 — plus strict qu'INV-4 Lean.
        Avec 1 seule famille, même conditions sinon remplies, Python refuse verified."""
        assert derive_confidence_tier(
            0.9, models_consulted=3, architecture_families=1, source_anchor="anchor"
        ) != "verified"

    def test_verified_requires_anchor_or_validation_count(self):
        """Python exige (anchor OU validation_count ≥ 3) pour verified."""
        assert derive_confidence_tier(
            0.9, models_consulted=3, architecture_families=2,
            source_anchor=None, validation_count=1
        ) != "verified"


# ═══════════════════════════════════════════════════════════════
# INV-6 — Deterministic Source Anchor (Formal/SourceAnchor.lean)
# ═══════════════════════════════════════════════════════════════

class TestInv6DeterministicAnchorCrystallizeGuard:
    """Règle Python enforced (partielle) : crystallize() avec
    `consensus_method=deterministic_source_v1` requiert
    `consensus_meta['source_anchor_meta']`. Ce n'est pas exactement INV-6
    Lean (qui porte sur `epistemic_type`, pas sur `consensus_method`),
    mais c'est la règle qu'implémente actuellement le code."""

    def test_crystallize_rejects_deterministic_method_without_meta(self):
        """Guard existant : consensus_method=deterministic_source_v1
        sans source_anchor_meta → ValueError."""
        with pytest.raises(ValueError, match="source_anchor_meta"):
            crystallize(
                subject="s", predicate="p", object_="o",
                consensus_score=0.9,
                model_votes=_make_votes(3, 3),
                signature_5d=_make_sig(),
                epistemic_type="deterministic",
                consensus_meta={
                    "methodology": {"consensus_method": "deterministic_source_v1"}
                },
            )

    def test_crystallize_accepts_deterministic_method_with_meta(self):
        """Côté passant : source_anchor_meta fourni → attestation cristallisée.

        Note (P4.2 alignement, 2026-05-01) : `source_anchor` doit désormais
        être un SHA-256 hex 64 chars (pattern Pydantic aligné sur Lean P4.2).
        Hash de test : `sha256(b"P4.2 alignment fixture").hexdigest()`."""
        valid_hash = "a" * 64  # 64 chars hex minuscules — conforme au pattern Lean P4.2
        att = crystallize(
            subject="s", predicate="p", object_="o",
            consensus_score=0.9,
            model_votes=_make_votes(3, 3),
            signature_5d=_make_sig(),
            epistemic_type="deterministic",
            source_anchor=valid_hash,
            consensus_meta={
                "methodology": {"consensus_method": "deterministic_source_v1"},
                "source_anchor_meta": {"source_id": "wikidata", "query": "Q1"},
            },
        )
        assert att.epistemic_type == "deterministic"
        assert att.source_anchor == valid_hash


class TestInv6DeterministicAnchorStrict:
    """INV-6 strict Lean : epistemic_type=deterministic ⇒ source_anchor non-nul.

    Depuis 2026-04-18, enforced par un `model_validator` Pydantic dans
    `EpistemicAttestation` (voir `services/esmm/attestation.py::
    validate_deterministic_requires_anchor`). Le runtime Python rejette
    désormais strictement toute construction d'attestation déterministe
    sans source_anchor, en cohérence avec INV-6 Lean et ADR-012.
    """

    def test_deterministic_without_anchor_is_rejected(self):
        """INV-6 Lean strict : epistemic_type=deterministic + source_anchor=None
        est rejeté par Pydantic (ValidationError lors du build de
        l'EpistemicAttestation dans crystallize())."""
        with pytest.raises(Exception):
            crystallize(
                subject="s", predicate="p", object_="o",
                consensus_score=0.9,
                model_votes=_make_votes(3, 3),
                signature_5d=_make_sig(),
                epistemic_type="deterministic",
                source_anchor=None,
                consensus_meta=None,
            )
