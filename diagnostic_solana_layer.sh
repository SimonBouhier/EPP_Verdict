#!/usr/bin/env bash
# ============================================================================
# DIAGNOSTIC SOLANA LAYER v2 -- EPP_Verdict
# ============================================================================
# PURPOSE : Verify Solana architecture state + flag known discrepancies
#            between CHANGELOG claims and actual file state.
#
# VERSION 2 CHANGES vs v1:
#   - Removed set -euo pipefail (grep returns exit 1 on no match -> killed script)
#   - Fixed Rust paths (programs/epp/src/ after 24/02 restructuring)
#   - Added D3: CONFIDENCE_TIER_MAP bijection (known bug post-24/02)
#   - Added D8: Deserialize integrity (last_revalidated + size assertion)
#   - Added D11: use_legacy_relation_groups flag + actual active path
#   - Added D12: VERIFY mode components existence
#   - Added D13: Bijection test existence
#   - Fixed skip grep pattern (was too restrictive)
#   - ASCII-only output (avoids encoding issues on Windows/PowerShell)
#
# Usage:
#   bash diagnostic_solana_layer.sh 2>&1 | tee solana_diagnostic.log
# ============================================================================

RUST_SRC="programs/epp/src"
BRIDGE="services/solana/bridge.py"
CLIENT="services/solana/client.py"
CONFIG_PY="services/solana/config.py"
CONFIG_YAML="config.yaml"

echo "=============================================="
echo "  DIAGNOSTIC SOLANA LAYER v2 -- $(date '+%Y-%m-%dT%H:%M:%S')"
echo "=============================================="
echo ""

# ----------------------------------------------------------
# PRE-CHECK: Rust source location
# ----------------------------------------------------------
echo "=== PRE-CHECK -- Rust source location ==="
echo ""
RUST_LIB=$(find . -name "lib.rs" -path "*/epp/*" -not -path "*target/*" 2>/dev/null | head -1)
RUST_STATE=$(find . -name "state.rs" -path "*/epp/*" -not -path "*target/*" 2>/dev/null | head -1)
RUST_CONST=$(find . -name "constants.rs" -path "*/epp/*" -not -path "*target/*" 2>/dev/null | head -1)

if [ -z "$RUST_LIB" ]; then
  echo "  CRITICAL: lib.rs not found under any */epp/* path"
  echo "  Expected: $RUST_SRC/lib.rs"
  echo "  Run from project root. Anchor restructuring (24/02) moved files."
else
  echo "  lib.rs       -> $RUST_LIB"
  echo "  state.rs     -> $RUST_STATE"
  echo "  constants.rs -> $RUST_CONST"
fi
echo ""

# ----------------------------------------------------------
# D1 -- NotImplementedError (mock stubs)
# ----------------------------------------------------------
echo "=== D1 -- NotImplementedError in $CLIENT ==="
echo ""
COUNT=$(grep -c "NotImplementedError" "$CLIENT" 2>/dev/null)
COUNT=${COUNT:-0}
echo "  Found: $COUNT occurrence(s)"
if [ "$COUNT" = "0" ]; then
  echo "  OK: All methods implemented (no stubs remaining)"
else
  echo "  REVIEW REQUIRED:"
  grep -n "NotImplementedError" "$CLIENT"
fi
echo ""

# ----------------------------------------------------------
# D2 -- AUDIT marker inventory (REQUIRED vs CLEARED)
# ----------------------------------------------------------
echo "=== D2 -- AUDIT marker inventory ==="
echo ""
echo "  CHANGELOG 24/02 claims AUDIT_CLEARED on 3 specific markers:"
echo "    client.py:474  (CLAIM_HASH_OFFSET memcmp)"
echo "    client.py:511  (SUBJECT_OFFSET memcmp)"
echo "    lib.rs:113     (PDA seeds)"
echo ""
echo "--- AUDIT_REQUIRED in Solana Python files ---"
grep -n "AUDIT_REQUIRED" "$BRIDGE" "$CLIENT" 2>/dev/null || echo "  (none)"
echo ""
echo "--- AUDIT_CLEARED in Solana Python files ---"
grep -n "AUDIT_CLEARED" "$BRIDGE" "$CLIENT" 2>/dev/null || echo "  (none)"
echo ""
echo "--- AUDIT_REQUIRED in Rust files ---"
if [ -n "$RUST_LIB" ]; then
  grep -n "AUDIT_REQUIRED" "$RUST_LIB" "$RUST_STATE" "$RUST_CONST" 2>/dev/null || echo "  (none)"
else
  echo "  (Rust files not found -- see PRE-CHECK)"
fi
echo ""
echo "--- AUDIT_CLEARED in Rust files ---"
if [ -n "$RUST_LIB" ]; then
  grep -n "AUDIT_CLEARED" "$RUST_LIB" "$RUST_STATE" "$RUST_CONST" 2>/dev/null || echo "  (none)"
else
  echo "  (Rust files not found -- see PRE-CHECK)"
fi
echo ""
echo "EXPECTED: client.py:474, client.py:511, lib.rs:113 should show AUDIT_CLEARED 2026-02-23"
echo "IF STILL AUDIT_REQUIRED: CHANGELOG 24/02 claims were not applied to these files -- BUG."
echo ""

# ----------------------------------------------------------
# D3 -- CONFIDENCE_TIER_MAP bijection
# ----------------------------------------------------------
echo "=== D3 -- CONFIDENCE_TIER_MAP bijection (CRITICAL) ==="
echo ""
echo "CHANGELOG 24/02: '3 legacy aliases removed (low/medium/high)'"
echo "Bijection requirement: exactly 4 keys (sandbox/proposition/validated/verified)"
echo ""
echo "--- CONFIDENCE_TIER_MAP in $BRIDGE ---"
grep -A15 "CONFIDENCE_TIER_MAP" "$BRIDGE" 2>/dev/null | head -20
echo ""
echo "--- Checking for legacy aliases ---"
LEGACY=$(grep -E '"low"|"medium"|"high"' "$BRIDGE" 2>/dev/null | grep -v "#" | grep -v "CONFIDENCE_TIER_REVERSE")
if [ -n "$LEGACY" ]; then
  echo "  BUG: Legacy aliases still present:"
  echo "$LEGACY"
  echo "  IMPACT: bridge.py accepts 7 keys but state.rs only has 4 arms."
  echo "          test_confidence_tier_map_bijection_with_rust will FAIL if it tests strict count."
else
  echo "  OK: No legacy aliases found -- bijection is strict (4 keys)"
fi
echo ""

# ----------------------------------------------------------
# D4 -- Constants bridge.py vs constants.rs
# ----------------------------------------------------------
echo "=== D4 -- Constants bridge.py vs constants.rs ==="
echo ""
echo "--- bridge.py ---"
grep -n "MAX_SUBJECT_LEN\|MAX_PREDICATE_LEN\|MAX_OBJECT_LEN\|SCORE_SCALE" \
  "$BRIDGE" 2>/dev/null | grep "^[0-9].*=" | head -10
echo ""
echo "--- constants.rs ---"
if [ -n "$RUST_CONST" ]; then
  grep -n "MAX_SUBJECT_LEN\|MAX_PREDICATE_LEN\|MAX_OBJECT_LEN\|SCORE_SCALE\|DISCRIMINATOR_SIZE" \
    "$RUST_CONST" 2>/dev/null | head -10
else
  echo "  (not found -- see PRE-CHECK)"
fi
echo ""
echo "EXPECTED (both sides identical):"
echo "  MAX_SUBJECT_LEN  = 64"
echo "  MAX_PREDICATE_LEN = 64"
echo "  MAX_OBJECT_LEN   = 128"
echo "  SCORE_SCALE      = 10000"
echo ""

# ----------------------------------------------------------
# D5 -- Enum mappings deep: EPISTEMIC_TYPE + CONFIDENCE_TIER
# ----------------------------------------------------------
echo "=== D5 -- Enum mappings: Python vs Rust ==="
echo ""
echo "--- EPISTEMIC_TYPE_MAP in $BRIDGE ---"
grep -A8 "^EPISTEMIC_TYPE_MAP" "$BRIDGE" 2>/dev/null
echo ""
echo "--- epistemic_type_to_u8 in state.rs ---"
if [ -n "$RUST_STATE" ]; then
  grep -A10 "fn epistemic_type_to_u8" "$RUST_STATE" 2>/dev/null
else
  echo "  (not found)"
fi
echo ""
echo "--- CONFIDENCE_TIER_REVERSE in $BRIDGE (used for deserialization) ---"
grep -A7 "^CONFIDENCE_TIER_REVERSE" "$BRIDGE" 2>/dev/null
echo ""
echo "--- confidence_tier_to_u8 in state.rs ---"
if [ -n "$RUST_STATE" ]; then
  grep -A8 "fn confidence_tier_to_u8" "$RUST_STATE" 2>/dev/null
else
  echo "  (not found)"
fi
echo ""
echo "EXPECTED: Both Python maps and Rust match arms use identical keys 0-4 / 0-3"
echo ""

# ----------------------------------------------------------
# D6 -- Programme ID consistency (4 sources)
# ----------------------------------------------------------
echo "=== D6 -- Programme ID consistency ==="
echo ""
echo "--- lib.rs ---"
if [ -n "$RUST_LIB" ]; then
  grep "declare_id" "$RUST_LIB" 2>/dev/null
else
  echo "  (not found)"
fi
echo ""
echo "--- Anchor.toml ---"
grep "epp\s*=" Anchor.toml 2>/dev/null || echo "  (not found)"
echo ""
echo "--- $CONFIG_PY ---"
grep "DEFAULT_PROGRAM_ID\|program_id" "$CONFIG_PY" 2>/dev/null | head -3
echo ""
echo "--- ARCHITECTURE.md ---"
grep "Programme ID\|98Fc" docs/ARCHITECTURE.md 2>/dev/null | head -3
echo ""
echo "EXPECTED: 98Fc2oL2cKsTDGYi3GifggzkQkEQSRn2oTgg8HsaVa3C in all 4 sources"
echo ""

# ----------------------------------------------------------
# D7 -- Offsets memcmp: dynamic calculation verification
# ----------------------------------------------------------
echo "=== D7 -- Offsets memcmp ==="
echo ""
echo "Expected layout (from state.rs field order):"
echo "  discriminator : 8 bytes   (not in deserialized data -- stripped before call)"
echo "  bump          : 1 byte    -> offset in raw account = 8"
echo "  submitter     : 32 bytes  -> offset 9"
echo "  claim_hash    : 32 bytes  -> offset 41  (= 8+1+32)"
echo "  subject       : 64 bytes  -> offset 73  (= 8+1+32+32)"
echo ""
echo "--- Offset formulas in $CLIENT ---"
grep -n "CLAIM_HASH_OFFSET\|SUBJECT_OFFSET" "$CLIENT" 2>/dev/null
echo ""
echo "EXPECTED:"
echo "  CLAIM_HASH_OFFSET = ACCOUNT_DISCRIMINATOR_SIZE + 1 + 32   -> 8+1+32 = 41"
echo "  SUBJECT_OFFSET    = ACCOUNT_DISCRIMINATOR_SIZE + 1 + 32 + 32 -> 8+1+32+32 = 73"
echo "  Both should be expressed as formulas (not hardcoded numbers)"
echo ""

# ----------------------------------------------------------
# D8 -- Deserialize integrity: last_revalidated + size assertion
# ----------------------------------------------------------
echo "=== D8 -- Deserialize integrity ==="
echo ""
echo "Regression check for Phase 1.2 fix (17/02): last_revalidated field"
echo "and offset mismatch assertion."
echo ""
echo "--- last_revalidated in _deserialize_attestation_account ---"
grep -n "last_revalidated" "$CLIENT" 2>/dev/null | grep -v "#"
echo ""
echo "--- Size assertion at end of deserialize ---"
grep -n "offset != len(data)\|offset mismatch\|Deserialization offset" "$CLIENT" 2>/dev/null
echo ""
echo "EXPECTED: last_revalidated present, read as '<q' (8 bytes i64)"
echo "EXPECTED: 'if offset != len(data): raise ValueError' present"
echo ""

# ----------------------------------------------------------
# D9 -- PDA seeds: Python vs Rust
# ----------------------------------------------------------
echo "=== D9 -- PDA seeds ==="
echo ""
echo "--- ATTESTATION_SEED in $CLIENT ---"
grep -n "ATTESTATION_SEED\|seeds" "$CLIENT" 2>/dev/null | grep -v "#" | head -6
echo ""
echo "--- seeds in lib.rs ---"
if [ -n "$RUST_LIB" ]; then
  grep -n "seeds\|ATTESTATION_SEED" "$RUST_LIB" 2>/dev/null
else
  echo "  (not found)"
fi
echo ""
echo "EXPECTED: [b'attestation', submitter_pubkey, claim_hash] -- both sides"
echo ""

# ----------------------------------------------------------
# D10 -- Account SIZE: 462 bytes
# ----------------------------------------------------------
echo "=== D10 -- Account SIZE ==="
echo ""
if [ -n "$RUST_STATE" ]; then
  grep -A25 "pub const SIZE" "$RUST_STATE" 2>/dev/null
else
  echo "  (state.rs not found)"
fi
echo ""
echo "EXPECTED: 462 bytes total"
echo ""

# ----------------------------------------------------------
# D11 -- relation_vocabulary: flag + actual active path
# ----------------------------------------------------------
echo "=== D11 -- relation_vocabulary: active path ==="
echo ""
echo "--- use_legacy_relation_groups in $CONFIG_YAML ---"
grep "use_legacy_relation_groups" "$CONFIG_YAML" 2>/dev/null
echo ""
echo "IMPACT: When 'true', consensus_engine uses frozen _LEGACY_RELATION_SYNONYMS"
echo "        (10 groups, defined locally). relation_vocabulary.py is NOT active."
echo "        When 'false', consensus_engine calls build_synonym_map() from"
echo "        relation_vocabulary.py (11 groups, updated). fingerprint_match.py"
echo "        always reads the flag per-call."
echo ""
echo "--- Import from relation_vocabulary in consensus_engine.py ---"
grep -n "from.*relation_vocabulary\|import.*relation_vocabulary" \
  services/esmm/consensus_engine.py 2>/dev/null || \
  grep -n "from.*relation_vocabulary\|import.*relation_vocabulary" \
  consensus_engine.py 2>/dev/null || echo "  (not found -- check path)"
echo ""
echo "--- Import from relation_vocabulary in fingerprint_match.py ---"
grep -n "from.*relation_vocabulary\|import.*relation_vocabulary" \
  services/esmm/fingerprint_match.py 2>/dev/null || \
  grep -n "from.*relation_vocabulary\|import.*relation_vocabulary" \
  fingerprint_match.py 2>/dev/null || echo "  (not found -- check path)"
echo ""
echo "EXPECTED: Both import from relation_vocabulary."
echo "          flag=true is safe (legacy frozen). Set to false to activate new groups."
echo ""

# ----------------------------------------------------------
# D12 -- VERIFY mode components
# ----------------------------------------------------------
echo "=== D12 -- VERIFY mode components (added 20/02) ==="
echo ""
echo "--- verdict_encoder.py ---"
find . -name "verdict_encoder.py" -not -path "*__pycache__*" 2>/dev/null || \
  echo "  ABSENT"
echo ""
echo "--- classify_input + InputType in question_seeder.py ---"
find . -name "question_seeder.py" -not -path "*__pycache__*" 2>/dev/null | \
  xargs grep -l "classify_input\|InputType" 2>/dev/null || echo "  ABSENT"
echo ""
echo "--- CycleType enum (ASSESS/CHALLENGE/ADJUDICATE) ---"
find . -name "cycle_manager.py" -not -path "*__pycache__*" 2>/dev/null | \
  xargs grep -l "ASSESS\|ADJUDICATE" 2>/dev/null || echo "  ABSENT"
echo ""
echo "--- ESMMRunConfig dataclass ---"
find . -name "orchestrator.py" -not -path "*__pycache__*" 2>/dev/null | \
  xargs grep -l "ESMMRunConfig" 2>/dev/null || echo "  ABSENT"
echo ""
echo "EXPECTED: All 4 components present"
echo ""

# ----------------------------------------------------------
# D13 -- Test coverage: skip patterns + bijection test
# ----------------------------------------------------------
echo "=== D13 -- Test coverage: solana-related ==="
echo ""
echo "--- Skip patterns (actual pattern used) ---"
grep -rn "skipif.*SOLANA_AVAILABLE\|skip.*solana_available\|pytest.mark.skip" \
  tests/ --include="*.py" 2>/dev/null | grep -v "__pycache__" | head -10 || \
  echo "  (none found with these patterns)"
echo ""
echo "--- Test files touching Solana ---"
grep -rl "solana\|bridge\|client\|Anchor\|pda\|memcmp" tests/ \
  --include="*.py" 2>/dev/null | grep -v "__pycache__"
echo ""
echo "--- test_confidence_tier_map_bijection_with_rust (CHANGELOG 24/02) ---"
grep -rn "test_confidence_tier_map_bijection_with_rust\|bijection_with_rust" \
  tests/ --include="*.py" 2>/dev/null | grep -v "__pycache__" || \
  echo "  NOT FOUND -- CHANGELOG 24/02 claims this test was added"
echo ""
echo "--- test_legacy_tiers_backward_compat (should be REMOVED per 24/02) ---"
grep -rn "test_legacy_tiers_backward_compat" \
  tests/ --include="*.py" 2>/dev/null | grep -v "__pycache__" || \
  echo "  Not found (expected -- should have been deleted per CHANGELOG 24/02)"
echo ""

# ----------------------------------------------------------
# SUMMARY
# ----------------------------------------------------------
echo "=============================================="
echo "  SUMMARY"
echo "=============================================="
echo ""
echo "  D1  NotImplementedError    : see above"
echo "  D2  AUDIT markers          : check REQUIRED vs CLEARED count"
echo "  D3  CONFIDENCE_TIER_MAP    : CHECK for low/medium/high aliases (known bug)"
echo "  D4  Constants Py/Rust      : values should be identical"
echo "  D5  Enum mappings          : 5-key epistemic + 4-key confidence tier"
echo "  D6  Programme ID           : 98Fc... in 4 sources"
echo "  D7  Offsets memcmp         : dynamic formulas = 41/73"
echo "  D8  Deserialize integrity  : last_revalidated + size assertion"
echo "  D9  PDA seeds              : [attestation, submitter, claim_hash]"
echo "  D10 Account SIZE           : 462 bytes"
echo "  D11 relation_vocabulary    : flag=true means legacy active"
echo "  D12 VERIFY components      : verdict_encoder, classify_input, CycleType"
echo "  D13 Bijection test         : test_confidence_tier_map_bijection_with_rust"
echo ""
echo "  KNOWN DISCREPANCIES (CHANGELOG 24/02 vs actual files):"
echo "  - D2/D3: AUDIT_CLEARED markers NOT applied (still AUDIT_REQUIRED)"
echo "  - D3:    CONFIDENCE_TIER_MAP legacy aliases NOT removed"
echo "  => Claude Code must fix these 3 items with RED-GREEN-FIX protocol"
echo ""
echo "  This diagnostic does NOT replace a devnet test."
echo "  It confirms architecture readiness for a Solana dev."
echo "=============================================="
