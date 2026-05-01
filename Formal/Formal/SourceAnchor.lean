import Formal.Basic

/-
  INV-6 — Deterministic Source Anchor (ADR-012 + ADR-019)

  Une attestation de type deterministic DOIT avoir un source_anchor
  présent (Option.isSome). Sans source autoritaire, une attestation ne
  peut pas prétendre être déterministe.

  Note (audit P3.A, 2026-04-30) : depuis le refactor B5 dans Basic.lean,
  le champ `source_anchor` est un `Option SourceAnchor` où le type
  `SourceAnchor` est non-construible avec un hash vide. La non-vacuité
  est donc garantie *par construction du type*. Les théorèmes ci-dessous
  restent tautologiques au sens preuve (la définition de `wellFormed`
  est exactement l'implication), mais l'invariant qu'ils expriment est
  désormais porté par le système de types Lean : aucune attestation
  deterministic ne peut être construite sans SourceAnchor (modulo le
  pont spec/code documenté en B6).
  Cf. tests/test_lean_conformance.py::TestInv6DeterministicAnchorStrict
  pour l'enforcement runtime côté Python.
-/

/-- Prédicat : une attestation est well-formed selon son type.
    Pour deterministic : un SourceAnchor doit être présent (Option.isSome).
    La non-vacuité du hash est garantie par construction du type SourceAnchor. -/
def wellFormed (a : Attestation) : Prop :=
  match a.epistemic_type with
  | EpistemicType.deterministic => a.source_anchor.isSome = true
  | _ => True  -- pas de contrainte supplémentaire pour empirical/assessed

/-- INV-6 : Si une attestation est well-formed ET de type deterministic,
    alors son source_anchor est présent (Option.isSome = true). -/
theorem deterministic_requires_anchor
    (a : Attestation)
    (hwf : wellFormed a)
    (htype : a.epistemic_type = EpistemicType.deterministic) :
    a.source_anchor.isSome = true := by
  unfold wellFormed at hwf
  rw [htype] at hwf
  exact hwf

/-- Corollaire : une attestation deterministic avec anchor à `none` n'est
    PAS well-formed. -/
theorem deterministic_without_anchor_not_wellformed
    (a : Attestation)
    (htype : a.epistemic_type = EpistemicType.deterministic)
    (hno : a.source_anchor = none) :
    ¬ wellFormed a := by
  unfold wellFormed
  rw [htype, hno]
  simp

