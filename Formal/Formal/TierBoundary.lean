import Formal.Basic

/-
  INV-4 — Tier Boundary Enforcement (ADR-005 + ADR-019)

  Le tier "verified" ne peut être accordé que si :
    - consensus_score ≥ 8500 (sur 10000)
    - ET (models_consulted ≥ 3 OU source_anchor est non-nul)

  Ce théorème prouve que la fonction d'assignation est correcte :
  elle ne retourne jamais "verified" sans satisfaire les conditions.
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

/-- INV-4 : Si le tier assigné est verified, alors le score est ≥ 8500
    ET soit 3+ modèles soit un source_anchor non-nul. -/
theorem tier_verified_implies_conditions
    (s : Score) (m : Nat) (a : Bool)
    (h : assignTier s m a = ConfidenceTier.verified) :
    s.val ≥ 8500 ∧ (m ≥ 3 ∨ a = true) := by
  unfold assignTier at h
  split at h
  · assumption
  · split at h
    · cases h
    · split at h
      · cases h
      · cases h

