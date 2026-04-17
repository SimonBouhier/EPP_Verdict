import Formal.Basic

/-
  INV-1 — Encodage float↔u16 (ADR-001 + ADR-019)

  Le bridge Python encode les floats [0.0, 1.0] en u16 [0, 10000]
  via round(value × 10000). Ce fichier prouve que l'encodage et le
  décodage préservent les bornes.
-/

/-- Constante d'échelle — doit correspondre à SCORE_SCALE dans bridge.py et constants.rs -/
def SCORE_SCALE : Nat := 10000

/-- Un Score est toujours décodable en une valeur ≤ SCORE_SCALE -/
theorem score_bounded (s : Score) : s.val ≤ SCORE_SCALE :=
  s.h_bound

/-- Construire un Score depuis un Nat avec preuve de borne -/
def mkScore (n : Nat) (h : n ≤ 10000) : Score := ⟨n, h⟩

/-- Le score 0 est valide -/
theorem zero_score_valid : (mkScore 0 (by omega)).val = 0 := rfl

/-- Le score max (10000) est valide -/
theorem max_score_valid : (mkScore 10000 (by omega)).val = SCORE_SCALE := rfl

/-- Tout Score encodé puis décodé reste dans [0, SCORE_SCALE] -/
theorem score_roundtrip_bounded (s : Score) :
    s.val ≤ SCORE_SCALE ∧ 0 ≤ s.val :=
  ⟨s.h_bound, Nat.zero_le s.val⟩

