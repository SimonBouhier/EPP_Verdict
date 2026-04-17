import Formal.Basic

/-
  INV-6 — Deterministic Source Anchor (ADR-012 + ADR-019)

  Une attestation de type deterministic DOIT avoir un source_anchor
  non-nul. Sans source autoritaire, une attestation ne peut pas
  prétendre être déterministe.
-/

/-- Prédicat : une attestation est well-formed selon son type -/
def wellFormed (a : Attestation) : Prop :=
  match a.epistemic_type with
  | EpistemicType.deterministic => a.source_anchor_nonzero = true
  | _ => True  -- pas de contrainte supplémentaire pour empirical/assessed

/-- INV-6 : Si une attestation est well-formed ET de type deterministic,
    alors son source_anchor est non-nul. -/
theorem deterministic_requires_anchor
    (a : Attestation)
    (hwf : wellFormed a)
    (htype : a.epistemic_type = EpistemicType.deterministic) :
    a.source_anchor_nonzero = true := by
  unfold wellFormed at hwf
  rw [htype] at hwf
  exact hwf

/-- Corollaire : une attestation deterministic avec anchor nul n'est
    PAS well-formed. -/
theorem deterministic_without_anchor_not_wellformed
    (a : Attestation)
    (htype : a.epistemic_type = EpistemicType.deterministic)
    (hno : a.source_anchor_nonzero = false) :
    ¬ wellFormed a := by
  unfold wellFormed
  rw [htype]
  simp [hno]

