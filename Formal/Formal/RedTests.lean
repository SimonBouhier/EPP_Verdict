import Formal.Basic
import Formal.TierBoundary

/-
  RED TESTS — Preuves de non-tautologie des invariants.

  Objectif : chaque red test est un théorème qui TOMBE si l'invariant
  correspondant est cassé (par exemple si quelqu'un abaisse un seuil
  dans assignTier). Les tests vivent dans lake build, pas dans un
  fichier orphelin.

  Pattern : pour démontrer qu'une condition NE DOIT PAS mener à un
  résultat donné, on prouve la négation (≠) directement. Pour
  démontrer qu'une condition DOIT mener à un résultat, on prouve
  l'égalité.
-/

/-- RED-TIER-1 : score 5000, 5 modèles, anchor=true → PAS verified
    (seuil score ≥ 8500 non atteint). -/
theorem red_tier_1_low_score_not_verified :
    assignTier (⟨5000, by omega⟩ : Score) 5 true ≠ ConfidenceTier.verified := by
  unfold assignTier
  simp

/-- RED-TIER-2 : score 8500, 1 modèle, anchor=false → PAS verified
    (ni 3 modèles ni anchor). -/
theorem red_tier_2_no_anchor_few_models_not_verified :
    assignTier (⟨8500, by omega⟩ : Score) 1 false ≠ ConfidenceTier.verified := by
  unfold assignTier
  simp

/-- GREEN-TIER-1 : score 8500, 3 modèles, anchor=false → verified
    (condition OR satisfaite par models ≥ 3). Preuve que la règle
    n'est pas trop restrictive. -/
theorem green_tier_1_high_score_many_models_verified :
    assignTier (⟨8500, by omega⟩ : Score) 3 false = ConfidenceTier.verified := by
  unfold assignTier
  simp

/-- GREEN-TIER-2 : score 8500, 1 modèle, anchor=true → verified
    (condition OR satisfaite par hasAnchor). -/
theorem green_tier_2_high_score_with_anchor_verified :
    assignTier (⟨8500, by omega⟩ : Score) 1 true = ConfidenceTier.verified := by
  unfold assignTier
  simp
