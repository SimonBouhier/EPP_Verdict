import Formal.Basic

/-
  INV-4 — Tier Boundary Enforcement (ADR-005 + ADR-019)

  Le tier "verified" ne peut être accordé que si :
    - consensus_score ≥ 8500 (sur 10000)
    - ET (models_consulted ≥ 3 OU source_anchor est non-nul)

  Note (audit P3.B, 2026-04-30) : extension du théorème directionnel
  initial vers une caractérisation `iff` complète sur les 4 tiers.
  L'ancien théorème `tier_verified_implies_conditions` est conservé
  comme corollaire pour traçabilité historique. La version `iff` ferme
  le biais B4 (asymétrie soundness/complétude) identifié dans
  `Formal_Review_EPP.md` §2 : une implémentation triviale qui ne
  retournerait jamais `verified` ne passe plus la spécification — elle
  doit *aussi* retourner `verified` quand les conditions sont remplies.
-/

/-- Règle d'assignation du tier — miroir de attestation.py -/
def assignTier (score : Score) (models : Nat) (hasAnchor : Bool) : ConfidenceTier :=
  if score.val ≥ 8500 ∧ (models ≥ 3 ∨ hasAnchor = true) then
    ConfidenceTier.verified
  else if score.val ≥ 7000 ∧ models ≥ 3 then
    ConfidenceTier.validated
  else if score.val ≥ 4000 ∧ models ≥ 2 then
    ConfidenceTier.proposition
  else
    ConfidenceTier.sandbox

-- ═══════════════════════════════════════════════════════════════
-- Caractérisation `iff` complète des 4 tiers (P3.B)
--
-- Chaque théorème prouve l'équivalence stricte entre le résultat de
-- `assignTier` et les conditions logiques cumulatives qui le définissent.
-- L'ensemble des 4 théorèmes caractérise EXHAUSTIVEMENT le comportement
-- de la fonction : pour tous (s, m, a), `assignTier s m a` retourne
-- exactement le tier dont les conditions sont vraies.
-- ═══════════════════════════════════════════════════════════════

/-- INV-4.verified — Caractérisation `iff` du tier `verified`.
    `assignTier` retourne `verified` SI ET SEULEMENT SI le score est
    ≥ 8500 et (au moins 3 modèles consultés OU source_anchor présent). -/
theorem tier_verified_iff_conditions (s : Score) (m : Nat) (a : Bool) :
    assignTier s m a = ConfidenceTier.verified ↔
    (s.val ≥ 8500 ∧ (m ≥ 3 ∨ a = true)) := by
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

/-- INV-4.validated — Caractérisation `iff` du tier `validated`.
    `assignTier` retourne `validated` SI ET SEULEMENT SI les conditions
    de `verified` ne sont pas remplies, ET le score est ≥ 7000 avec ≥ 3
    modèles consultés. -/
theorem tier_validated_iff_conditions (s : Score) (m : Nat) (a : Bool) :
    assignTier s m a = ConfidenceTier.validated ↔
    (¬ (s.val ≥ 8500 ∧ (m ≥ 3 ∨ a = true))
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

/-- INV-4.proposition — Caractérisation `iff` du tier `proposition`.
    `assignTier` retourne `proposition` SI ET SEULEMENT SI les conditions
    de `verified` et `validated` ne sont pas remplies, ET le score est
    ≥ 4000 avec ≥ 2 modèles consultés. -/
theorem tier_proposition_iff_conditions (s : Score) (m : Nat) (a : Bool) :
    assignTier s m a = ConfidenceTier.proposition ↔
    (¬ (s.val ≥ 8500 ∧ (m ≥ 3 ∨ a = true))
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

/-- INV-4.sandbox — Caractérisation `iff` du tier `sandbox`.
    `assignTier` retourne `sandbox` SI ET SEULEMENT SI aucune des
    conditions des 3 tiers supérieurs n'est remplie. -/
theorem tier_sandbox_iff_conditions (s : Score) (m : Nat) (a : Bool) :
    assignTier s m a = ConfidenceTier.sandbox ↔
    (¬ (s.val ≥ 8500 ∧ (m ≥ 3 ∨ a = true))
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
-- Corollaire conservé pour traçabilité historique (P3.B, 2026-04-30)
-- ═══════════════════════════════════════════════════════════════

/-- Conservé pour traçabilité historique : version directionnelle prouvée
    avant l'extension `iff` (P3.B, 2026-04-30). Découle directement de
    `tier_verified_iff_conditions` via `Iff.mp`.

    Le théorème originel ne couvrait qu'une seule direction et était
    *vacuusement* satisfait par toute fonction qui ne retourne jamais
    `verified` (cf. `_RedTestVacuity.lean` pour la preuve observable).
    L'extension `iff` ci-dessus ferme ce gap en exigeant aussi la
    direction inverse. -/
theorem tier_verified_implies_conditions
    (s : Score) (m : Nat) (a : Bool)
    (h : assignTier s m a = ConfidenceTier.verified) :
    s.val ≥ 8500 ∧ (m ≥ 3 ∨ a = true) :=
  (tier_verified_iff_conditions s m a).mp h
