import Formal.Basic

/-
  INV-2 — Claim Hash Purity (ADR-006 + ADR-017)

  L'identité d'un claim ne dépend QUE du noyau canonique
  (subject, predicate, object, frame).

  Cette propriété est la condition de possibilité du réseau de
  clusters (ADR-017) : deux opérateurs indépendants soumettant
  le même claim obtiennent le même claim_hash, donc peuvent être
  comparés par un indexer externe.

  Le modèle Lean abstrait SHA-256 en une concaténation canonique.
  La preuve porte sur la PROJECTION d'Attestation sur son noyau
  d'identité — pas sur les propriétés cryptographiques de SHA-256.
-/

/-- Noyau canonique d'un claim : les 4 champs qui forment son identité. -/
structure ClaimCore where
  subject   : String
  predicate : String
  object    : String
  frame     : String
  deriving Repr, DecidableEq

/-- Projection d'une attestation sur son noyau canonique.
    N'utilise QUE les 4 premiers champs d'Attestation. -/
def toClaimCore (a : Attestation) : ClaimCore :=
  { subject := a.subject
  , predicate := a.predicate
  , object := a.object
  , frame := a.frame }

/-- Modèle abstrait du claim_hash : concaténation canonique du noyau.
    Le vrai hash SHA-256 est implémenté côté Python/Rust ; ici on
    prouve que l'identité dépend uniquement du ClaimCore. -/
def claimHashCore (c : ClaimCore) : String :=
  c.subject ++ "|" ++ c.predicate ++ "|" ++ c.object ++ "|" ++ c.frame

/-- Le claim_hash d'une attestation dépend exclusivement de son noyau. -/
def claimHash (a : Attestation) : String :=
  claimHashCore (toClaimCore a)

/-- INV-2 — Claim Hash Purity.
    Deux attestations au noyau canonique identique ont le même hash,
    peu importe leur timestamp, submitter, ou décision épistémique. -/
theorem claim_hash_purity (a₁ a₂ : Attestation)
    (hs : a₁.subject = a₂.subject)
    (hp : a₁.predicate = a₂.predicate)
    (ho : a₁.object = a₂.object)
    (hf : a₁.frame = a₂.frame) :
    claimHash a₁ = claimHash a₂ := by
  unfold claimHash toClaimCore claimHashCore
  rw [hs, hp, ho, hf]

/-- Corollaire : deux attestations qui ne diffèrent QUE sur le timestamp
    ont le même hash. Cross-cluster : deux opérateurs émettant le même
    claim à des moments différents produisent des attestations
    comparables. -/
theorem claim_hash_timestamp_independent
    (a₁ a₂ : Attestation)
    (hcore : toClaimCore a₁ = toClaimCore a₂) :
    claimHash a₁ = claimHash a₂ := by
  unfold claimHash
  rw [hcore]

/-- Corollaire : deux attestations qui ne diffèrent QUE sur le submitter
    ont le même hash. Cross-cluster : deux clusters émettent le même
    claim_hash pour le même claim. -/
theorem claim_hash_submitter_independent
    (a₁ a₂ : Attestation)
    (hcore : toClaimCore a₁ = toClaimCore a₂) :
    claimHash a₁ = claimHash a₂ := by
  unfold claimHash
  rw [hcore]
