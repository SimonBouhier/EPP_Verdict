#!/usr/bin/env bash
# ============================================================================
# DIAGNOSTIC SOLANA LAYER — EPP_Verdict
# ============================================================================
# BUT : Vérifier que l'architecture Solana est correcte et prête à être
#        branchée sur un validator réel par un dev Solana.
#
# CE SCRIPT NE TESTE PAS LE DEVNET. Il vérifie les prérequis.
#
# Usage : bash diagnostic_solana_layer.sh > solana_diagnostic.log 2>&1
# ============================================================================

set -euo pipefail

echo "=============================================="
echo "  DIAGNOSTIC SOLANA LAYER — $(date -Iseconds)"
echo "=============================================="
echo ""

# ----------------------------------------------------------
# D1 — Inventaire des NotImplementedError (le vrai état)
# ----------------------------------------------------------
echo "=== D1 — NotImplementedError dans client.py ==="
echo "Chaque occurrence = une méthode qui n'existe qu'en mock."
echo ""
grep -n "NotImplementedError" services/solana/client.py || echo "  (aucun trouvé — vérifier manuellement)"
echo ""
echo "ATTENDU : 3 occurrences (submit_attestation, get_attestation, query_by_claim/subject)"
echo "SI 0 : Soit implémenté, soit supprimé silencieusement — VÉRIFIER."
echo ""

# ----------------------------------------------------------
# D2 — Méthode _deserialize_attestation_account (fantôme CHANGELOG)
# ----------------------------------------------------------
echo "=== D2 — _deserialize_attestation_account (mentionnée CHANGELOG, existe-t-elle ?) ==="
echo ""
grep -rn "_deserialize_attestation_account\|deserialize_attestation" \
  services/solana/ tests/ || echo "  ABSENT — confirmé fantôme CHANGELOG"
echo ""

# ----------------------------------------------------------
# D3 — Cohérence offsets memcmp vs state.rs layout
# ----------------------------------------------------------
echo "=== D3 — Vérification offsets memcmp ==="
echo ""
echo "--- Layout state.rs (tailles déclarées) ---"
echo "  discriminator:    8 bytes"
echo "  bump:             1 byte   -> offset 8"
echo "  submitter:       32 bytes  -> offset 9"
echo "  claim_hash:      32 bytes  -> offset 41"
echo "  subject:         64 bytes  -> offset 73"
echo "  predicate:       64 bytes  -> offset 137"
echo "  object:         128 bytes  -> offset 201"
echo ""
echo "--- Offsets dans client.py ---"
grep -n "OFFSET\|offset" services/solana/client.py || echo "  (aucune constante OFFSET trouvée)"
echo ""
echo "--- Vérification croisée ---"
echo "  CLAIM_HASH attendu à offset 8+1+32 = 41"
CLAIM_OFFSET=$(grep -oP 'CLAIM_HASH_OFFSET\s*=\s*\K\d+' services/solana/client.py 2>/dev/null || echo "")
if [ -z "$CLAIM_OFFSET" ]; then
  # Essayer avec l'expression calculée
  CLAIM_EXPR=$(grep "CLAIM_HASH_OFFSET" services/solana/client.py 2>/dev/null || echo "NON TROUVÉ")
  echo "  client.py : $CLAIM_EXPR"
else
  echo "  client.py : CLAIM_HASH_OFFSET = $CLAIM_OFFSET"
  if [ "$CLAIM_OFFSET" = "41" ]; then
    echo "  ✅ MATCH"
  else
    echo "  ❌ MISMATCH — attendu 41, trouvé $CLAIM_OFFSET"
  fi
fi
echo ""
echo "  SUBJECT attendu à offset 8+1+32+32 = 73"
SUBJECT_EXPR=$(grep "SUBJECT_OFFSET" services/solana/client.py 2>/dev/null || echo "NON TROUVÉ")
echo "  client.py : $SUBJECT_EXPR"
echo ""

# ----------------------------------------------------------
# D4 — Cohérence constantes bridge.py vs constants.rs
# ----------------------------------------------------------
echo "=== D4 — Constantes bridge.py vs constants.rs ==="
echo ""
echo "--- bridge.py ---"
grep -n "MAX_SUBJECT_LEN\|MAX_PREDICATE_LEN\|MAX_OBJECT_LEN\|SCORE_SCALE" \
  services/solana/bridge.py | head -10
echo ""
echo "--- constants.rs ---"
grep -n "MAX_SUBJECT_LEN\|MAX_PREDICATE_LEN\|MAX_OBJECT_LEN\|SCORE_SCALE\|DISCRIMINATOR" \
  programs/epp/src/constants.rs 2>/dev/null || \
  grep -n "MAX_SUBJECT_LEN\|MAX_PREDICATE_LEN\|MAX_OBJECT_LEN\|SCORE_SCALE\|DISCRIMINATOR" \
  constants.rs 2>/dev/null || echo "  (fichier constants.rs non trouvé au chemin attendu)"
echo ""
echo "ATTENDU : Valeurs identiques des deux côtés."
echo ""

# ----------------------------------------------------------
# D5 — Enum mappings bridge.py vs state.rs
# ----------------------------------------------------------
echo "=== D5 — Enum mappings bridge.py vs state.rs ==="
echo ""
echo "--- bridge.py epistemic_type ---"
grep -A5 "EPISTEMIC_TYPE_MAP" services/solana/bridge.py | head -8
echo ""
echo "--- state.rs epistemic_type_to_u8 ---"
grep -A7 "fn epistemic_type_to_u8" programs/epp/src/state.rs 2>/dev/null || \
  grep -A7 "fn epistemic_type_to_u8" state.rs 2>/dev/null || echo "  (fichier state.rs non trouvé)"
echo ""
echo "--- bridge.py confidence_tier ---"
grep -A5 "CONFIDENCE_TIER_MAP" services/solana/bridge.py | head -7
echo ""
echo "--- state.rs confidence_tier_to_u8 ---"
grep -A6 "fn confidence_tier_to_u8" programs/epp/src/state.rs 2>/dev/null || \
  grep -A6 "fn confidence_tier_to_u8" state.rs 2>/dev/null || echo "  (fichier state.rs non trouvé)"
echo ""

# ----------------------------------------------------------
# D6 — Programme ID cohérence
# ----------------------------------------------------------
echo "=== D6 — Programme ID ==="
echo ""
echo "--- lib.rs ---"
grep "declare_id" programs/epp/src/lib.rs 2>/dev/null || \
  grep "declare_id" lib.rs 2>/dev/null || echo "  (non trouvé)"
echo ""
echo "--- config.py ---"
grep "DEFAULT_PROGRAM_ID\|program_id" services/solana/config.py | head -5
echo ""
echo "--- ARCHITECTURE.md ---"
grep "Programme ID\|98Fc" ARCHITECTURE.md 2>/dev/null || echo "  (non trouvé)"
echo ""
echo "ATTENTION : Si lib.rs a un placeholder (EPPxxx...) et config.py a 98Fc...,"
echo "  c'est normal en dev — le deploy génère l'ID réel."
echo ""

# ----------------------------------------------------------
# D7 — Tests existants Solana (ce qui est RÉELLEMENT testé)
# ----------------------------------------------------------
echo "=== D7 — Tests Solana existants ==="
echo ""
echo "--- Fichiers test Solana ---"
find tests/ -name "*.py" -exec grep -l "solana\|bridge\|client\|pda\|memcmp\|anchor" {} \; 2>/dev/null || \
  echo "  (aucun fichier test Solana trouvé dans tests/)"
echo ""
echo "--- Tests qui utilisent mock vs tests réels ---"
grep -rn "MOCK\|mock_mode\|NotImplementedError\|_SOLANA_AVAILABLE" tests/ --include="*.py" 2>/dev/null | head -20
echo ""
echo "--- Nombre de tests 'skip' liés Solana ---"
grep -rn "skip.*solana\|skip.*validator\|skipIf.*SOLANA" tests/ --include="*.py" 2>/dev/null || \
  echo "  (aucun skip explicite trouvé)"
echo ""

# ----------------------------------------------------------
# D8 — PDA derivation Python vs Anchor (seeds cohérents)
# ----------------------------------------------------------
echo "=== D8 — PDA seeds cohérence ==="
echo ""
echo "--- client.py ---"
grep -A3 "seeds\|ATTESTATION_SEED" services/solana/client.py | head -10
echo ""
echo "--- lib.rs ---"
grep -B1 -A2 "seeds\|ATTESTATION_SEED" programs/epp/src/lib.rs 2>/dev/null || \
  grep -B1 -A2 "seeds\|ATTESTATION_SEED" lib.rs 2>/dev/null
echo ""
echo "ATTENDU : seeds = [b'attestation', submitter_pubkey, claim_hash] des deux côtés."
echo ""

# ----------------------------------------------------------
# D9 — SIZE total account vs rent calculation
# ----------------------------------------------------------
echo "=== D9 — Taille account ==="
echo ""
echo "--- state.rs SIZE ---"
grep -A20 "pub const SIZE" programs/epp/src/state.rs 2>/dev/null || \
  grep -A20 "pub const SIZE" state.rs 2>/dev/null
echo ""
echo "--- Calcul attendu ---"
echo "  8 (disc) + 1 (bump) + 32 (sub) + 32 (hash) + 64 (subj) + 64 (pred)"
echo "  + 128 (obj) + 2 (score) + 1 (m_cons) + 1 (m_agree) + 10 (sig5d)"
echo "  + 1 (type) + 1 (tier) + 32 (frame) + 32 (source) + 8 (ts)"
echo "  + 8 (revalid) + 2 (val_count) + 2 (proto_ver) + 1 (is_chall) + 32 (chall_pk)"
echo "  = 462 bytes"
echo ""

# ----------------------------------------------------------
# RÉSUMÉ
# ----------------------------------------------------------
echo "=============================================="
echo "  RÉSUMÉ DIAGNOSTIC"
echo "=============================================="
echo ""
echo "  D1  NotImplementedError    : à vérifier manuellement"
echo "  D2  _deserialize fantôme   : à confirmer absent"
echo "  D3  Offsets memcmp         : à vérifier vs layout"
echo "  D4  Constantes Py/Rust     : à comparer"
echo "  D5  Enums Py/Rust          : à comparer"
echo "  D6  Programme ID           : placeholder vs déployé"
echo "  D7  Tests mock vs réel     : ratio à évaluer"
echo "  D8  PDA seeds              : cohérence à vérifier"
echo "  D9  Account SIZE           : 462 bytes attendu"
echo ""
echo "  Ce diagnostic NE REMPLACE PAS un test devnet."
echo "  Il confirme que l'architecture est prête pour"
echo "  qu'un dev Solana implémente les 3-4 méthodes réelles."
echo "=============================================="
