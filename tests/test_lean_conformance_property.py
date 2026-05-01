"""
Tests de conformité Python ↔ invariants Lean 4 — property-based (P4.1, ADR-020).

Complément du fichier `test_lean_conformance.py` (tests unitaires sur cas
spécifiques) : ce fichier exerce les fonctions Python sur des centaines à
milliers d'inputs aléatoires générés par `hypothesis`. Là où le fichier
unitaire fait *« avec ces inputs spécifiques, voilà le résultat attendu »*,
ce fichier fait *« pour tout input dans le domaine, la propriété tient »* —
sur N exemples (configurable).

C'est l'action qui ferme partiellement le décalage spec/code (B6 dans
`docs/research/RESEARCH_FORMAL_AUDIT.md`) : on ne *prouve* pas que Python
correspond à Lean (impossible sans extraction formelle), mais on
**falsifie** systématiquement la conformance sur un large échantillon.

Configuration `hypothesis` :
  - `max_examples = 100` par défaut (rapide, intégration CI standard).
  - Surcharge via env var `HYPOTHESIS_MAX_EXAMPLES` (par ex. 10000 pour
    validation profonde manuelle).
  - `deadline = 5000ms` pour absorber les pics Pydantic + SHA-256 répétés.
  - `derandomize = True` pour reproductibilité.

Écarts connus Python ↔ Lean (documentés dans chaque classe) :
  - INV-2 : Python applique `.lower().strip()` — propriété plus forte
    qu'INV-2 Lean. Pas de divergence de sécurité.
  - INV-4 : Python exige `architecture_families ≥ 2` ET
    `(source_anchor ≠ None ∨ validation_count ≥ 3)` en plus des conditions
    Lean. Python ⇒ Lean (Python plus strict, sûr).
  - INV-7 (Brier) : la fenêtre glissante 90 jours
    (`database/schema.sql:995`) introduit un biais temporel non modélisé
    en Lean. **Hors scope P4** — documenté ici comme écart connu non
    couvert par le property testing actuel.
"""
import os
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.esmm.attestation import (
    ModelVote,
    Signature5D,
    compute_claim_hash,
    crystallize,
    derive_confidence_tier,
)


# ═══════════════════════════════════════════════════════════════
# CONFIG hypothesis — surchargeable via env var
# ═══════════════════════════════════════════════════════════════

_MAX_EXAMPLES = int(os.environ.get("HYPOTHESIS_MAX_EXAMPLES", "100"))

# Profil partagé pour toutes les classes : déterministe, deadline large.
_HYP = settings(
    max_examples=_MAX_EXAMPLES,
    deadline=5000,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)


# ═══════════════════════════════════════════════════════════════
# STRATÉGIES — domaines bornés pour éviter les inputs pathologiques
# ═══════════════════════════════════════════════════════════════

# Texte ASCII printable, longueur 1-100. Couvre les cas réalistes sans
# exploser le coût de génération sur Unicode obscur.
text_field = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
    min_size=1,
    max_size=100,
)

# Frame optionnel (peut être None ou string).
frame_field = st.one_of(
    st.none(),
    text_field,
)

# Score consensus dans [0, 1] (validé par Pydantic ge=0, le=1).
score_field = st.floats(
    min_value=0.0,
    max_value=1.0,
    allow_nan=False,
    allow_infinity=False,
)

# Counts entiers raisonnables.
small_count = st.integers(min_value=0, max_value=20)

# Hash SHA-256 hexadécimal minuscule, longueur exacte 64 — aligné sur le
# pattern Pydantic `^[0-9a-f]{64}$` ajouté en P4.2 alignement (2026-05-01).
# Cette stratégie génère uniquement des chaînes conformes au contrat
# `SourceAnchor` Lean P4.2 (longueur 64, charset hex minuscule).
hash_field = st.text(
    alphabet="0123456789abcdef",
    min_size=64,
    max_size=64,
)


# ═══════════════════════════════════════════════════════════════
# HELPERS — construction d'attestations valides pour INV-6
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
# INV-2 — Claim Hash Purity (property-based)
# ═══════════════════════════════════════════════════════════════

class TestInv2ClaimHashProperty:
    """INV-2 (`Formal/Formal/ClaimHash.lean::claim_hash_purity`).

    Propriétés vérifiées sur N=100 (par défaut) inputs aléatoires :
      - **Déterminisme** : `f(x) == f(x)` pour tout x.
      - **Pureté de signature** : `compute_claim_hash` ne prend que
        (subject, predicate, object_, frame) — pas de timestamp ni
        submitter dans la signature. Toute régression de signature
        casserait au compile time.
      - **Sensibilité aux 4 champs** : changer un seul champ canonique
        produit (presque toujours) un hash différent. Note : pour des
        inputs identiques modulo `.lower().strip()`, Python produit le
        même hash — c'est l'écart connu §docstring du module.
      - **Format** : sortie SHA-256 hex (64 chars `[0-9a-f]`).

    Écart connu Python > Lean : `.lower().strip()` appliqué avant le hash
    (voir `compute_claim_hash` `attestation.py:222-225`). Lean modélise
    la concaténation littérale. Python est plus permissif : strictement
    plus d'égalités de hash. Pas de divergence de sécurité.
    """

    @_HYP
    @given(s=text_field, p=text_field, o=text_field, f=frame_field)
    def test_determinism(self, s, p, o, f):
        """Pour tout (s, p, o, f), deux appels successifs produisent
        le même hash."""
        h1 = compute_claim_hash(s, p, o, f)
        h2 = compute_claim_hash(s, p, o, f)
        assert h1 == h2

    @_HYP
    @given(s=text_field, p=text_field, o=text_field, f=frame_field)
    def test_output_is_64_hex_chars(self, s, p, o, f):
        """SHA-256 hex : 64 caractères, charset [0-9a-f]."""
        h = compute_claim_hash(s, p, o, f)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    @_HYP
    @given(s1=text_field, s2=text_field, p=text_field, o=text_field, f=frame_field)
    def test_subject_change_changes_hash(self, s1, s2, p, o, f):
        """Si les subjects normalisés diffèrent, les hashes diffèrent.
        L'écart `.lower().strip()` est explicitement préfiltré."""
        if s1.lower().strip() == s2.lower().strip():
            return  # cas où Python > Lean produit la même valeur
        h1 = compute_claim_hash(s1, p, o, f)
        h2 = compute_claim_hash(s2, p, o, f)
        assert h1 != h2

    @_HYP
    @given(s=text_field, p1=text_field, p2=text_field, o=text_field, f=frame_field)
    def test_predicate_change_changes_hash(self, s, p1, p2, o, f):
        """Idem sur predicate."""
        if p1.lower().strip() == p2.lower().strip():
            return
        h1 = compute_claim_hash(s, p1, o, f)
        h2 = compute_claim_hash(s, p2, o, f)
        assert h1 != h2

    @_HYP
    @given(s=text_field, p=text_field, o=text_field, f=frame_field)
    def test_normalization_python_stronger_than_lean(self, s, p, o, f):
        """Écart Python > Lean : `.lower().strip()` rend le hash insensible
        à la casse et aux espaces de bordure. Ce test vérifie cette
        propriété PYTHON SPÉCIFIQUE — elle n'est pas modélisée en Lean."""
        h_normal = compute_claim_hash(s, p, o, f)
        h_upper = compute_claim_hash(s.upper(), p.upper(), o.upper(),
                                     f.upper() if f else f)
        h_padded = compute_claim_hash(f"  {s}  ", p, o, f)
        assert h_normal == h_upper
        assert h_normal == h_padded


# ═══════════════════════════════════════════════════════════════
# INV-4 — Tier Boundary (property-based)
# ═══════════════════════════════════════════════════════════════

class TestInv4TierBoundaryProperty:
    """INV-4 (`Formal/Formal/TierBoundary.lean::tier_*_iff_conditions`).

    La spec Lean caractérise `assignTier` par 4 théorèmes `iff` (P3.B).
    Python (`derive_confidence_tier`) est strictement plus restrictif :
    il exige en plus `architecture_families ≥ 2` (pour validated et
    verified) et `(source_anchor ≠ None ∨ validation_count ≥ 3)`
    (pour verified). Donc Python ⇒ Lean (tout ce que Python tier
    `verified` satisfait, Lean tier `verified` satisfait aussi).

    Tests property-based :
      - Le tier retourné est toujours dans CONFIDENCE_TIERS.
      - Si Python retourne `verified`, alors les conditions Lean sont
        nécessairement remplies (Python ⇒ Lean).
      - Les bornes de score sont respectées.
    """

    @_HYP
    @given(
        score=score_field,
        models=small_count,
        archs=small_count,
        anchor=st.one_of(st.none(), text_field),
        vc=small_count,
    )
    def test_tier_in_known_set(self, score, models, archs, anchor, vc):
        """Le tier retourné est toujours l'un des 4 tiers documentés."""
        tier = derive_confidence_tier(
            score, models_consulted=models, architecture_families=archs,
            source_anchor=anchor, validation_count=vc,
        )
        assert tier in {"sandbox", "proposition", "validated", "verified"}

    @_HYP
    @given(
        score=score_field,
        models=small_count,
        archs=small_count,
        anchor=st.one_of(st.none(), text_field),
        vc=small_count,
    )
    def test_python_verified_implies_lean_conditions(
        self, score, models, archs, anchor, vc,
    ):
        """Si Python retourne `verified`, les conditions Lean
        (`tier_verified_iff_conditions`) sont nécessairement remplies :
        score ≥ 0.85 ET (models ≥ 3 OR anchor non-nul). Python est strict
        sur archs ≥ 2 et (anchor OR vc ≥ 3) en plus, donc Python ⇒ Lean."""
        tier = derive_confidence_tier(
            score, models_consulted=models, architecture_families=archs,
            source_anchor=anchor, validation_count=vc,
        )
        if tier == "verified":
            assert score >= 0.85
            # Conditions Lean : models ≥ 3 OR anchor non-nul
            assert models >= 3 or (anchor is not None)

    @_HYP
    @given(
        score=score_field.filter(lambda s: s < 0.40),
        models=small_count,
        archs=small_count,
        anchor=st.one_of(st.none(), text_field),
        vc=small_count,
    )
    def test_low_score_implies_sandbox(self, score, models, archs, anchor, vc):
        """Si score < 0.40, Python retourne sandbox (cf.
        `attestation.py::derive_confidence_tier` ligne 296). C'est aussi
        cohérent avec `tier_sandbox_iff_conditions` Lean (la borne basse
        est ¬(score ≥ 4000) parmi d'autres)."""
        tier = derive_confidence_tier(
            score, models_consulted=models, architecture_families=archs,
            source_anchor=anchor, validation_count=vc,
        )
        assert tier == "sandbox"


# ═══════════════════════════════════════════════════════════════
# INV-6 — Deterministic Source Anchor (property-based)
# ═══════════════════════════════════════════════════════════════

class TestInv6DeterministicProperty:
    """INV-6 (`Formal/Formal/SourceAnchor.lean::deterministic_requires_anchor`).

    Côté Python : un `model_validator` Pydantic dans `EpistemicAttestation`
    rejette toute construction avec `epistemic_type='deterministic'` et
    `source_anchor=None`. Cette règle est exercée à travers `crystallize()`
    qui construit l'attestation finale.

    Tests property-based :
      - Pour tout `epistemic_type='deterministic'` + source_anchor=None,
        la cristallisation lève une exception.
      - Pour tout `epistemic_type='deterministic'` + source_anchor non-nul,
        la cristallisation réussit.
      - Pour `epistemic_type` ≠ 'deterministic', la règle ne s'applique
        pas — la construction réussit avec ou sans anchor.

    NB : ce test exerce **l'invariant logique INV-6 standard** (déterministique
    ⇒ anchor non-nul). Le **renforcement contractuel P4.2** sur le format
    SHA-256 hex 64 chars du SourceAnchor existe au niveau du type *Lean*,
    pas au niveau Pydantic actuellement (cf. SESSION_AUDIT_FORMAL_P4.md
    §écart connu — divergence remontée à Sim).
    """

    # epistemic_types non-deterministic : règle INV-6 ne s'applique pas
    NON_DETERMINISTIC = st.sampled_from([
        "foundational", "bridge", "specialized",
        "generalist", "hybrid", "verdict", "security_audit",
    ])

    @_HYP
    @given(et=NON_DETERMINISTIC, anchor=st.one_of(st.none(), hash_field))
    def test_non_deterministic_accepts_any_anchor(self, et, anchor):
        """Pour epistemic_type ≠ 'deterministic', la cristallisation
        réussit avec ou sans source_anchor (INV-6 ne contraint que le
        cas deterministic).

        Note (P4.2 alignement, 2026-05-01) : `anchor` est désormais tiré
        de `hash_field` (SHA-256 hex 64 chars conforme au pattern Pydantic).
        Le contrat de format vit au niveau du type `source_anchor`,
        indépendamment d'`epistemic_type`."""
        att = crystallize(
            subject="s", predicate="p", object_="o",
            consensus_score=0.5,
            model_votes=_make_votes(2, 3),
            signature_5d=_make_sig(),
            epistemic_type=et,
            source_anchor=anchor,
            consensus_meta=None,
        )
        assert att.epistemic_type == et

    @_HYP
    @given(anchor=hash_field)
    def test_deterministic_with_anchor_accepted(self, anchor):
        """epistemic_type='deterministic' + source_anchor non-nul →
        cristallisation réussit (cas passant INV-6).

        Le `consensus_meta` doit contenir `source_anchor_meta` (guard
        de `crystallize` sur consensus_method=deterministic_source_v1)."""
        att = crystallize(
            subject="s", predicate="p", object_="o",
            consensus_score=0.9,
            model_votes=_make_votes(3, 3),
            signature_5d=_make_sig(),
            epistemic_type="deterministic",
            source_anchor=anchor,
            consensus_meta={
                "methodology": {"consensus_method": "deterministic_source_v1"},
                "source_anchor_meta": {"source_id": "wikidata", "query": "Q1"},
            },
        )
        assert att.epistemic_type == "deterministic"
        assert att.source_anchor == anchor

    def test_deterministic_without_anchor_rejected(self):
        """epistemic_type='deterministic' + source_anchor=None → exception
        (`model_validator` Pydantic). Test unitaire (pas property-based) :
        pas besoin d'aléa pour démontrer le rejet du None."""
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


# ═══════════════════════════════════════════════════════════════
# Renforcement contractuel SourceAnchor (P4.2 + écart documenté)
# ═══════════════════════════════════════════════════════════════

class TestInv6SourceAnchorContractEnforced:
    """Renforcement contractuel SourceAnchor — alignement Python ↔ Lean P4.2.

    P4.2 a renforcé le contrat Lean `SourceAnchor` (`Formal/Formal/Basic.lean`) :
    un `SourceAnchor` ne peut être construit qu'avec un hash de longueur
    exacte 64 caractères dans le charset `[0-9a-f]`. Ces trois contraintes
    (non-vacuité, longueur 64, charset hex minuscule) sont garanties **par
    construction du type Lean**.

    **Alignement Python ↔ Lean (P4.2 alignement, 2026-05-01)** : côté
    Python, `EpistemicAttestation.source_anchor` est désormais typé avec
    `pattern=r"^[0-9a-f]{64}$"` (cf. `services/esmm/attestation.py:89-100`).
    Pydantic rejette donc toute valeur non conforme — alignement strict
    avec le contrat Lean P4.2.

    Cette classe **vérifie l'enforcement Pydantic** sur 5 angles :
      1. Hash valide accepté (cas passant — sanity).
      2. Hash trop court rejeté.
      3. Hash trop long rejeté.
      4. Hash en majuscules rejeté (charset hex minuscule).
      5. Hash de bonne longueur mais hors charset hex rejeté.

    Historique : avant l'alignement (P4.2 stricto sensu, 2026-04-30), cette
    classe s'appelait `TestInv6SourceAnchorContract` et contenait deux
    tests `xfail strict` qui matérialisaient l'écart entre la prescription
    du briefing P4 §4.3 et le code Pydantic réel. Sim a tranché en faveur
    de l'option 1 (alignement Python sur Lean) le 2026-05-01 ; la classe
    a été renommée et les xfail retirés.
    """

    @staticmethod
    def _build_attestation(source_anchor_value: str):
        """Construit une attestation deterministic avec un source_anchor
        donné. Utilise EpistemicAttestation directement pour bypasser
        les guards de crystallize() et exercer uniquement la validation
        Pydantic du champ."""
        from services.esmm.attestation import EpistemicAttestation
        return EpistemicAttestation(
            claim_hash="x" * 64,
            subject="s", predicate="p", object="o",
            consensus_score=0.9,
            models_consulted=3, models_agreeing=3,
            model_votes=[],
            signature_5d=_make_sig(),
            epistemic_type="deterministic",
            confidence_tier="verified",
            source_anchor=source_anchor_value,
            timestamp=0.0,
        )

    def test_valid_hash_accepted(self):
        """Cas passant : un hash de 64 chars hex minuscules est accepté."""
        valid = "a" * 64
        att = self._build_attestation(valid)
        assert att.source_anchor == valid

    def test_short_hash_rejected(self):
        """`source_anchor='ABC'` (3 chars, non-hex) → ValidationError.
        Aligne Python sur le contrat Lean P4.2 (`h_length` + `h_hex`)."""
        with pytest.raises(Exception):
            self._build_attestation("ABC")

    def test_long_hash_rejected(self):
        """65 chars hex minuscules → rejeté (longueur exacte = 64)."""
        with pytest.raises(Exception):
            self._build_attestation("a" * 65)

    def test_uppercase_hex_rejected(self):
        """64 chars hex majuscules → rejeté (charset minuscule strict)."""
        with pytest.raises(Exception):
            self._build_attestation("A" * 64)

    def test_non_hex_charset_rejected(self):
        """64 chars dont 1 hors charset hex → rejeté."""
        with pytest.raises(Exception):
            # 63 chars 'a' + 'g' (hors [0-9a-f])
            self._build_attestation("a" * 63 + "g")
