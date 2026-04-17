import Formal.Basic
import Formal.TierBoundary

/- RED TEST 1 : score 5000 ne doit PAS donner verified -/
theorem red1_low_score_gets_verified :
    assignTier (⟨5000, by omega⟩ : Score) 5 true = ConfidenceTier.verified := by
  unfold assignTier
  simp
