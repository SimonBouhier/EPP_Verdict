import Formal.Basic

/-
  INV-4 — Tier Boundary Enforcement (ADR-005 + ADR-019)

  Le tier "verified" ne peut être accordé que si :
    - consensus_score ≥ 8500 (sur 10000)
    - ET models_consulted ≥ 3   (cumulativité — partagé avec validated)
    - ET (source_anchor non-nul OU validation_count ≥ 3)

  Notes (audit P3.B + P1 cumulativity, 2026-04-30 → 2026-05-01) :
  - L'extension `iff` (P3.B) ferme le biais B4 (asymétrie soundness/
    complétude) — cf. `Formal_Review_EPP.md` §2.
  - La correction P1 cumulativity (2026-05-01) ferme un bug de design
    repéré par revue critique externe : la version pré-P1 permettait
    `assignTier 8500 1 true = verified` (1 seul modèle + anchor),
    alors que `validated` exigeait models ≥ 3. Les tiers étaient
    présentés comme une stratification cumulative (sandbox <
    proposition < validated < verified) sans l'être réellement.
    Le fix : `verified` exige désormais TOUTES les conditions de
    `validated` plus le couplet anchor∨vc≥3. Cumulativité prouvée
    par les théorèmes `tier_*_implies_*_conditions` ci-dessous.
  - Le 4ème paramètre `validationCount` aligne le modèle Lean sur
    Python `derive_confidence_tier`, qui accepte deux chemins pour
    `verified` : source_anchor non-nul OU validation_count ≥ 3
    (cf. attestation.py:259-264). Sans ce paramètre, Lean serait
    strictement plus restrictif que Python, créant une nouvelle
    divergence spec/code (ce que P4.2 a justement fermé sur
    SourceAnchor).
-/

/-- Règle d'assignation du tier — miroir de
    services/esmm/attestation.py::derive_confidence_tier (modulo
    architecture_families ≥ 2 que Python exige en plus, cf. ADR-020 §5.2). -/
def assignTier
    (score : Score) (models : Nat) (hasAnchor : Bool) (validationCount : Nat) :
    ConfidenceTier :=
  if score.val ≥ 8500 ∧ models ≥ 3 ∧ (hasAnchor = true ∨ validationCount ≥ 3) then
    ConfidenceTier.verified
  else if score.val ≥ 7000 ∧ models ≥ 3 then
    ConfidenceTier.validated
  else if score.val ≥ 4000 ∧ models ≥ 2 then
    ConfidenceTier.proposition
  else
    ConfidenceTier.sandbox

-- ═══════════════════════════════════════════════════════════════
-- Caractérisation `iff` complète des 4 tiers (P3.B + P1 cumulativity)
-- ═══════════════════════════════════════════════════════════════

/-- INV-4.verified — Caractérisation `iff` du tier `verified`. -/
theorem tier_verified_iff_conditions
    (s : Score) (m : Nat) (a : Bool) (vc : Nat) :
    assignTier s m a vc = ConfidenceTier.verified ↔
    (s.val ≥ 8500 ∧ m ≥ 3 ∧ (a = true ∨ vc ≥ 3)) := by
  unfold assignTier
  constructor
  · intro h
    split at h
    · assumption
    · split at h
      · cases h
      · split at h
        · cases h
        · cases h
  · intro hA
    rw [if_pos hA]

/-- INV-4.validated — Caractérisation `iff` du tier `validated`. -/
theorem tier_validated_iff_conditions
    (s : Score) (m : Nat) (a : Bool) (vc : Nat) :
    assignTier s m a vc = ConfidenceTier.validated ↔
    (¬ (s.val ≥ 8500 ∧ m ≥ 3 ∧ (a = true ∨ vc ≥ 3))
     ∧ s.val ≥ 7000 ∧ m ≥ 3) := by
  unfold assignTier
  constructor
  · intro h
    split at h
    · cases h
    · next hnA =>
      split at h
      · next hB =>
        exact ⟨hnA, hB.1, hB.2⟩
      · split at h
        · cases h
        · cases h
  · intro ⟨hnA, h7, h3⟩
    rw [if_neg hnA, if_pos ⟨h7, h3⟩]

/-- INV-4.proposition — Caractérisation `iff` du tier `proposition`. -/
theorem tier_proposition_iff_conditions
    (s : Score) (m : Nat) (a : Bool) (vc : Nat) :
    assignTier s m a vc = ConfidenceTier.proposition ↔
    (¬ (s.val ≥ 8500 ∧ m ≥ 3 ∧ (a = true ∨ vc ≥ 3))
     ∧ ¬ (s.val ≥ 7000 ∧ m ≥ 3)
     ∧ s.val ≥ 4000 ∧ m ≥ 2) := by
  unfold assignTier
  constructor
  · intro h
    split at h
    · cases h
    · next hnA =>
      split at h
      · cases h
      · next hnB =>
        split at h
        · next hC =>
          exact ⟨hnA, hnB, hC.1, hC.2⟩
        · cases h
  · intro ⟨hnA, hnB, h4, h2⟩
    rw [if_neg hnA, if_neg hnB, if_pos ⟨h4, h2⟩]

/-- INV-4.sandbox — Caractérisation `iff` du tier `sandbox`. -/
theorem tier_sandbox_iff_conditions
    (s : Score) (m : Nat) (a : Bool) (vc : Nat) :
    assignTier s m a vc = ConfidenceTier.sandbox ↔
    (¬ (s.val ≥ 8500 ∧ m ≥ 3 ∧ (a = true ∨ vc ≥ 3))
     ∧ ¬ (s.val ≥ 7000 ∧ m ≥ 3)
     ∧ ¬ (s.val ≥ 4000 ∧ m ≥ 2)) := by
  unfold assignTier
  constructor
  · intro h
    split at h
    · cases h
    · next hnA =>
      split at h
      · cases h
      · next hnB =>
        split at h
        · cases h
        · next hnC =>
          exact ⟨hnA, hnB, hnC⟩
  · intro ⟨hnA, hnB, hnC⟩
    rw [if_neg hnA, if_neg hnB, if_neg hnC]

-- ═══════════════════════════════════════════════════════════════
-- Cumulativité des tiers (P1, 2026-05-01)
--
-- Théorèmes substantifs : si l'attestation atteint un tier supérieur,
-- elle satisfait nécessairement les conditions de tous les tiers
-- inférieurs. C'est la propriété de stratification que la nomenclature
-- (sandbox < proposition < validated < verified) suggère et que la
-- définition pré-P1 d'`assignTier` ne respectait pas (verified
-- pouvait s'obtenir avec models = 1 si anchor = true, alors que
-- validated exigeait models ≥ 3 — bug de design rendu visible par la
-- caractérisation `iff` de P3.B).
-- ═══════════════════════════════════════════════════════════════

/-- INV-4.cumul1 — Cumulativité verified ⇒ validated.
    Si l'attestation atteint le tier `verified`, alors elle satisfait
    aussi les conditions de `validated` : score ≥ 7000 ∧ models ≥ 3.
    C'est la propriété cumulative qui était violée pré-P1. -/
theorem tier_verified_implies_validated_conditions
    (s : Score) (m : Nat) (a : Bool) (vc : Nat)
    (h : assignTier s m a vc = ConfidenceTier.verified) :
    s.val ≥ 7000 ∧ m ≥ 3 := by
  rw [tier_verified_iff_conditions] at h
  exact ⟨by omega, h.2.1⟩

/-- INV-4.cumul2 — Cumulativité validated ⇒ proposition.
    Si l'attestation atteint le tier `validated`, alors elle satisfait
    aussi les conditions de `proposition` : score ≥ 4000 ∧ models ≥ 2. -/
theorem tier_validated_implies_proposition_conditions
    (s : Score) (m : Nat) (a : Bool) (vc : Nat)
    (h : assignTier s m a vc = ConfidenceTier.validated) :
    s.val ≥ 4000 ∧ m ≥ 2 := by
  rw [tier_validated_iff_conditions] at h
  exact ⟨by omega, by omega⟩

-- ═══════════════════════════════════════════════════════════════
-- Corollaire conservé pour traçabilité historique (P3.B, 2026-04-30)
-- ═══════════════════════════════════════════════════════════════

/-- Conservé pour traçabilité historique : version directionnelle prouvée
    avant l'extension `iff` (P3.B, 2026-04-30) et avant la correction
    cumulativity (P1, 2026-05-01). Découle directement de
    `tier_verified_iff_conditions` via `Iff.mp`. -/
theorem tier_verified_implies_conditions
    (s : Score) (m : Nat) (a : Bool) (vc : Nat)
    (h : assignTier s m a vc = ConfidenceTier.verified) :
    s.val ≥ 8500 ∧ m ≥ 3 ∧ (a = true ∨ vc ≥ 3) :=
  (tier_verified_iff_conditions s m a vc).mp h
