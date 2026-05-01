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
    peu importe leur timestamp, submitter, ou décision épistémique.

    NOTE GATEKEEPER (2026-04-30) : ce théorème est un regression test sur
    la définition de `toClaimCore`. Si quelqu'un modifiait la projection
    canonique pour y inclure un champ supplémentaire (timestamp,
    submitter, etc.), les 4 hypothèses ne suffiraient plus à conclure
    et la preuve casserait. Sa valeur n'est pas une garantie universelle
    sur SHA-256 (le vrai hash est en Python/Rust) mais bien la
    protection contre une mutation accidentelle de la projection
    canonique côté Lean. -/
theorem claim_hash_purity (a₁ a₂ : Attestation)
    (hs : a₁.subject = a₂.subject)
    (hp : a₁.predicate = a₂.predicate)
    (ho : a₁.object = a₂.object)
    (hf : a₁.frame = a₂.frame) :
    claimHash a₁ = claimHash a₂ := by
  unfold claimHash toClaimCore claimHashCore
  rw [hs, hp, ho, hf]

-- ═══════════════════════════════════════════════════════════════
-- Théorèmes supprimés le 2026-04-30 (audit P1.2) :
--   - claim_hash_timestamp_independent
--   - claim_hash_submitter_independent
--
-- Justification : ces deux théorèmes avaient une hypothèse
-- `hcore : toClaimCore a₁ = toClaimCore a₂` qui les rendait strictement
-- équivalents l'un à l'autre (mêmes paramètres, même conclusion, même
-- preuve `unfold claimHash; rw [hcore]`) et redondants avec
-- `claim_hash_purity` (qui couvre déjà la propriété au bon niveau
-- d'abstraction via les 4 hypothèses canoniques). Les RedTests
-- `red_hash_1_timestamp_independence` et `red_hash_2_submitter_independence`
-- (RedTests.lean) sont les regression tests adéquats pour ces invariants
-- spécifiques.
-- ═══════════════════════════════════════════════════════════════