/-
  EPP_Verdict — Formal Specification
  Types de base du protocole épistémique (ADR-019)
-/

/-- Catégories on-chain V2 (3 valeurs, Lean 4-ready) -/
inductive EpistemicType where
  | empirical     -- 0 : consensus multi-LLM
  | deterministic -- 1 : source autoritaire (ADR-012)
  | assessed      -- 2 : audit dirigé (ADR-014)
  deriving Repr, DecidableEq

/-- Tiers de confiance (ADR-005), ordre strict -/
inductive ConfidenceTier where
  | sandbox
  | proposition
  | validated
  | verified
  deriving Repr, DecidableEq

/-- Score encodé comme u16 [0, 10000] -/
structure Score where
  val : Nat
  h_bound : val ≤ 10000

/-- Modèle simplifié d'une attestation on-chain -/
structure Attestation where
  epistemic_type : EpistemicType
  confidence_tier : ConfidenceTier
  consensus_score : Score
  models_consulted : Nat
  source_anchor_nonzero : Bool

