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

/-- Modèle simplifié d'une attestation on-chain.
    Les 4 premiers champs (subject, predicate, object, frame) forment
    le noyau canonique d'identité : claim_hash en dépend exclusivement
    (cf. INV-2 dans ClaimHash.lean). Les champs suivants caractérisent
    le contexte d'émission mais n'entrent PAS dans l'identité. -/
structure Attestation where
  -- Noyau canonique d'identité (INV-2)
  subject         : String
  predicate       : String
  object          : String
  frame           : String
  -- Contexte d'émission (ne doit PAS entrer dans claim_hash)
  timestamp       : Nat
  submitter       : String
  -- Décision épistémique (cf. TierBoundary.lean, SourceAnchor.lean)
  epistemic_type  : EpistemicType
  confidence_tier : ConfidenceTier
  consensus_score : Score
  models_consulted : Nat
  source_anchor_nonzero : Bool

