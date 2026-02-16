#!/bin/bash
# =============================================================================
# AUDIT ADR-010 + Phase 4.8 — Script de verification consolide
# Genere par Claude Opus pour recette adversariale
# Date : 2026-02-16
# Usage : bash tests/audit_adr010_phase48.sh
# =============================================================================
# Ce script NE CORRIGE RIEN. Il imprime des faits.
# Envoyer la sortie complete a Opus pour verdict.
# =============================================================================

echo "================================================================="
echo "  AUDIT CONSOLIDE — ADR-010 + Phase 4.8"
echo "  $(date)"
echo "================================================================="
echo ""

# -----------------------------------------------------------------
# 0. BASELINE
# -----------------------------------------------------------------
echo "=== [C0] BASELINE — pytest ==="
python -m pytest tests/ -q --tb=line 2>&1 | tail -5
echo ""

# -----------------------------------------------------------------
# C1 — SIGNATURES
# -----------------------------------------------------------------
echo "=== [C1a] Cascade compute_consensus ==="
grep -rn "compute_consensus" --include="*.py" database/ services/ cli/ app/ tests/ 2>/dev/null | grep -v __pycache__
echo ""
echo "--- .triplets (preuve ConsensusResult) ---"
grep -rn "\.triplets" --include="*.py" services/esmm/triplet_extractor.py services/esmm/cycle_manager.py services/esmm/orchestrator.py services/esmm/pipeline.py 2>/dev/null | grep -v __pycache__
echo ""

echo "=== [C1b] Cascade _extract_triplets_from_question ==="
grep -rn "_extract_triplets_from_question" --include="*.py" database/ services/ cli/ app/ tests/ 2>/dev/null | grep -v __pycache__
echo ""

echo "=== [C1c] Cascade crystallize() — consensus_meta ==="
grep -rn "crystallize(" --include="*.py" services/ tests/ 2>/dev/null | grep -v __pycache__ | grep -v "def crystallize"
echo ""

# -----------------------------------------------------------------
# C2 — SINGLETONS
# -----------------------------------------------------------------
echo "=== [C2] Singletons ==="
grep -rn "global _" --include="*.py" database/ services/ app/ 2>/dev/null | grep -v __pycache__ | grep -v test_
echo "--- Total: $(grep -rn 'global _' --include='*.py' database/ services/ app/ 2>/dev/null | grep -v __pycache__ | grep -v test_ | wc -l) ---"
echo ""

# -----------------------------------------------------------------
# C3 — SILENCE
# -----------------------------------------------------------------
echo "=== [C3] Exceptions silencieuses — fichiers ADR-010 ==="
for f in services/esmm/consensus_engine.py services/esmm/pipeline.py services/providers/ollama.py database/engine.py services/esmm/attestation.py; do
  hits=$(grep -n "except" "$f" 2>/dev/null | grep -v "logger\.\|logging\.\|raise\|AUDIT\|# OK:" | head -20)
  if [ -n "$hits" ]; then
    echo "--- $f ---"
    echo "$hits"
  fi
done
echo ""

# -----------------------------------------------------------------
# C4 — SCHEMA
# -----------------------------------------------------------------
echo "=== [C4a] consensus_meta dans schema.sql ==="
grep -n "consensus_meta" database/schema.sql 2>/dev/null
echo ""
echo "=== [C4b] consensus_meta dans engine.py ==="
grep -n "consensus_meta" database/engine.py 2>/dev/null
echo ""
echo "=== [C4c] Migration ALTER TABLE ==="
grep -n "ALTER TABLE.*consensus_meta\|ADD COLUMN.*consensus_meta" database/engine.py 2>/dev/null
echo ""
echo "=== [C4d] Backfill ==="
grep -n "backfill_consensus_meta\|pre-ADR-010" database/engine.py 2>/dev/null
echo ""

# -----------------------------------------------------------------
# C5 — SEMANTIQUE : resolve_model_version
# -----------------------------------------------------------------
echo "=== [C5] resolve_model_version ==="
grep -n -A 30 "def resolve_model_version" services/providers/ollama.py 2>/dev/null
echo ""

# -----------------------------------------------------------------
# C6 — COUVERTURE
# -----------------------------------------------------------------
echo "=== [C6a] Tests ADR-010 ==="
grep -n "def test_" tests/test_adr010_consensus_meta.py 2>/dev/null
echo ""
ASSERTS=$(grep -c "assert " tests/test_adr010_consensus_meta.py 2>/dev/null || echo 0)
MOCKS=$(grep -c "assert_called\|assert_awaited" tests/test_adr010_consensus_meta.py 2>/dev/null || echo 0)
TESTS=$(grep -c "def test_" tests/test_adr010_consensus_meta.py 2>/dev/null || echo 0)
echo "=== [C6b] Ratio: $TESTS tests, $ASSERTS val-asserts, $MOCKS mock-asserts ==="
echo ""
echo "=== [C6c] Tests Phase 4.8 ==="
grep -rn "def test_.*english\|def test_.*semantic_merge\|def test_.*ambiguity\|def test_.*prompts_are" --include="*.py" tests/ 2>/dev/null | grep -v __pycache__
echo ""

# -----------------------------------------------------------------
# C7 — POLLUTION
# -----------------------------------------------------------------
echo "=== [C7] conftest resets ==="
echo "$(grep -c 'reset\|close\|_instance.*None\|clear' tests/conftest.py 2>/dev/null) lignes reset/close/clear"
echo ""

# -----------------------------------------------------------------
# C8 — MOCKS
# -----------------------------------------------------------------
echo "=== [C8a] Backward-compat 2/3-tuple ==="
grep -n "len(extract_result)" services/esmm/pipeline.py 2>/dev/null
echo ""
echo "=== [C8b] Mocks de _extract_triplets dans tests ==="
grep -rn "_extract_triplets_from_question\|extract_result" --include="*.py" tests/ 2>/dev/null | grep -v __pycache__ | head -20
echo ""

# -----------------------------------------------------------------
# C9 — DOCUMENTATION
# -----------------------------------------------------------------
echo "=== [C9a] README baseline ==="
grep -i "passed\|failed\|skipped" README.md 2>/dev/null | head -5
echo ""
echo "=== [C9b] CHANGELOG top ==="
head -20 docs/fr/CHANGELOG.md 2>/dev/null || head -20 CHANGELOG.md 2>/dev/null
echo ""
echo "=== [C9c] ADR-010 dans ARCHITECTURE ==="
grep -n "ADR-010\|consensus_meta\|ConsensusResult" docs/ARCHITECTURE.md 2>/dev/null || grep -n "ADR-010\|consensus_meta\|ConsensusResult" ARCHITECTURE.md 2>/dev/null
echo ""
echo "=== [C9d] Date ARCHITECTURE ==="
head -5 docs/ARCHITECTURE.md 2>/dev/null || head -5 ARCHITECTURE.md 2>/dev/null
echo ""

# -----------------------------------------------------------------
# ADR-006 : claim_hash etanche
# -----------------------------------------------------------------
echo "=== [ADR-006] compute_claim_hash ==="
grep -n -A 20 "def compute_claim_hash" services/esmm/attestation.py 2>/dev/null
echo ""

# -----------------------------------------------------------------
# ADR-010 specifique
# -----------------------------------------------------------------
echo "=== [ADR-010a] ConsensusResult dataclass ==="
grep -n -A 15 "class ConsensusResult" services/esmm/consensus_engine.py 2>/dev/null
echo ""

echo "=== [ADR-010b] _compute_vote_entropy ==="
grep -n -A 20 "def _compute_vote_entropy" services/esmm/consensus_engine.py 2>/dev/null
echo ""

echo "=== [ADR-010c] _build_consensus_meta ==="
grep -n -A 40 "def _build_consensus_meta" services/esmm/pipeline.py 2>/dev/null
echo ""

# -----------------------------------------------------------------
# ADR-009 : COMMUNITY_DECISION_REQUIRED
# -----------------------------------------------------------------
echo "=== [ADR-009] COMMUNITY_DECISION_REQUIRED ==="
grep -rn "COMMUNITY_DECISION_REQUIRED" --include="*.py" services/ 2>/dev/null | grep -v __pycache__
echo ""

# -----------------------------------------------------------------
# Phase 4.8 : Residus francais
# -----------------------------------------------------------------
echo "=== [4.8] Marqueurs francais residuels ==="
grep -n -E "Tu es|Quelles sont|Décris|Identifie|Réponds|Liste les|Quels concepts|À partir de|En analysant|Y a-t-il" services/esmm/cycle_prompts.py services/esmm/prompts.py 2>/dev/null || echo "  (aucun marqueur francais)"
echo ""

echo "================================================================="
echo "  FIN — Envoyer cette sortie complete a Opus"
echo "================================================================="
