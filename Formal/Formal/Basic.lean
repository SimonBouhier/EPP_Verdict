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

/-- Vérifie qu'un caractère est un chiffre hexadécimal minuscule
    (`'0'`-`'9'` ou `'a'`-`'f'`). Retourne un `Bool` pour permettre
    `decide` / `native_decide` sur des chaînes constantes. -/
def isHexLowerChar (c : Char) : Bool :=
  c.isDigit || (Nat.ble 'a'.toNat c.toNat && Nat.ble c.toNat 'f'.toNat)

/-- Vérifie qu'une chaîne ne contient que des chiffres hex minuscules. -/
def isHexLower (s : String) : Bool :=
  s.toList.all isHexLowerChar

/-- Un SourceAnchor est un hash SHA-256 hexadécimal minuscule de longueur
    exactement 64 caractères. Trois contraintes sont portées au niveau du
    type :
    - non-vacuité (`h_nonempty`, héritée de P3.A),
    - longueur exacte 64 (`h_length`, P4.2),
    - charset hex minuscule (`h_hex`, P4.2).

    Le constructeur exige les preuves correspondantes — il est donc
    impossible de produire un `SourceAnchor` qui ne respecte pas ces
    trois contraintes. C'est le renforcement formel du contrat B5
    (cf. P3.A puis P4.2) avec la couche Python/Rust où Pydantic
    valide la même règle via regex `^[0-9a-f]{64}$`.

    Note (audit P4.2, 2026-04-30) : la non-vacuité est désormais un
    corollaire de la longueur exacte 64 (`h_length` implique trivialement
    `h_nonempty`), mais on la conserve explicitement pour clarté du
    contrat — elle documente l'intention dans la signature du type, et
    permet à un consommateur (preuve future ou inspection visuelle) de
    voir tous les contrats sans avoir à inspecter le code de `decide`. -/
structure SourceAnchor where
  hash : String
  h_nonempty : hash ≠ ""
  h_length   : hash.length = 64
  h_hex      : isHexLower hash = true

/-- Modèle simplifié d'une attestation on-chain.
    Les 4 premiers champs (subject, predicate, object, frame) forment
    le noyau canonique d'identité : claim_hash en dépend exclusivement
    (cf. INV-2 dans ClaimHash.lean). Les champs suivants caractérisent
    le contexte d'émission mais n'entrent PAS dans l'identité.

    Note (audit P3.A, 2026-04-30) : le champ `source_anchor` était
    précédemment un `Bool` (`source_anchor_nonzero`) qui pouvait mentir
    (la couche Python pouvait mettre `true` sans vrai hash en base). Il
    est désormais un `Option SourceAnchor` : la non-vacuité du hash est
    garantie *par construction du type* `SourceAnchor` (cf. ci-dessus).
    Conséquence : INV-6 (`SourceAnchor.lean`) reste tautologique en
    preuve, mais l'invariant qu'il exprime est maintenant porté par le
    système de types, pas par un drapeau externe. -/
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
  source_anchor   : Option SourceAnchor  -- ← refactor B5 (P3.A, 2026-04-30)

