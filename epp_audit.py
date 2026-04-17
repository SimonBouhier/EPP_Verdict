"""
EPP_VERDICT — UNIFIED AUDIT
============================
Single script combining all audit passes:

  Phase 1: STATIC ANALYSIS (C1-C8 controls)
  Phase 2: ORPHAN DETECTION (dead files)
  Phase 3: FULL REGRESSION (pytest)
  Phase 4: MUTATION TESTING (21 targeted mutations)

Usage:
    python epp_audit.py                  # Full audit (all phases)
    python epp_audit.py --static         # Phase 1 only
    python epp_audit.py --orphans        # Phase 2 only
    python epp_audit.py --regression     # Phase 3 only
    python epp_audit.py --mutations      # Phase 4 only
    python epp_audit.py --no-mutations   # Phases 1-3 (skip slow mutations)

Output:
    EPP_AUDIT_REPORT.md — Full report with verdicts and evidence

Author: Claude Opus (auditor)
Date: 2026-02-22
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ============================================================================
# CONFIGURATION
# ============================================================================

ROOT = Path(__file__).parent
REPORT_PATH = ROOT / "tests" / "audits" / "EPP_AUDIT_REPORT.md"
CHECKSUMS_PATH = ROOT / "tests" / "audits" / "audit_checksums.txt"
TIMEOUT_SECONDS = 30

# Directories to scan (relative to ROOT)
CODE_DIRS = ["services/", "database/"]
TEST_DIR = "tests/"
EXCLUDE_PATTERNS = ["__pycache__", ".venv", "node_modules", ".git"]


# ============================================================================
# UTILITIES
# ============================================================================

def p(msg: str):
    """Print with UTF-8 encoding (Windows compat)."""
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_cmd(cmd: str, cwd: str = None) -> Tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        cwd=cwd or str(ROOT), timeout=120,
    )
    return result.returncode, result.stdout, result.stderr


def find_py_files(*dirs: str, exclude_tests: bool = False) -> List[Path]:
    """Find all .py files in given directories, excluding patterns."""
    files = []
    for d in dirs:
        base = ROOT / d
        if not base.exists():
            continue
        for f in base.rglob("*.py"):
            rel = str(f.relative_to(ROOT))
            if any(pat in rel for pat in EXCLUDE_PATTERNS):
                continue
            if exclude_tests and "/tests/" in rel:
                continue
            if f.name == "__init__.py":
                continue
            files.append(f)
    return sorted(files)


# ============================================================================
# PHASE 1: STATIC ANALYSIS
# ============================================================================

class StaticAnalyzer:
    """C1-C8 control checks via grep and file analysis."""

    def __init__(self):
        self.findings: Dict[str, List[str]] = {}

    def run_all(self) -> Dict[str, List[str]]:
        p("=" * 70)
        p("  PHASE 1: STATIC ANALYSIS (C1-C8)")
        p("=" * 70)

        self._check_singletons()
        self._check_silent_except()
        self._check_schema_drift()
        self._check_config_drift()
        self._check_weak_assertions()
        self._check_verify_coverage()
        self._check_dead_imports()
        self._check_todo_fixme()

        return self.findings

    def _check_singletons(self):
        """C2: Global singletons that could cause state pollution."""
        p("\n  [C2] Singletons...")
        _, out, _ = run_cmd(
            'grep -rn "global _" --include="*.py" database/ services/ '
            '| grep -v __pycache__ | grep -v test_'
        )
        hits = [l.strip() for l in out.strip().splitlines() if l.strip()]
        self.findings["C2_singletons"] = hits
        p(f"       {len(hits)} global singletons found")

    def _check_silent_except(self):
        """C3: except blocks that silently swallow errors."""
        p("  [C3] Silent except...")
        _, out, _ = run_cmd(
            'grep -rn "except" --include="*.py" -A2 database/ services/ '
            '| grep -B1 "pass$" '
            '| grep -v "logger\\." | grep -v "logging\\." '
            '| grep -v "raise" | grep -v "AUDIT" | grep -v "# OK:" '
            '| grep -v __pycache__ | grep -v test_'
        )
        hits = [l.strip() for l in out.strip().splitlines() if l.strip() and ".py" in l]
        self.findings["C3_silent_except"] = hits
        p(f"       {len(hits)} silent except blocks found")

    def _check_schema_drift(self):
        """C4: Tables/views in schema.sql vs tables referenced in engine.py."""
        p("  [C4] Schema drift...")
        schema_file = ROOT / "database" / "schema.sql"
        engine_file = ROOT / "database" / "engine.py"
        drift = []

        if schema_file.exists() and engine_file.exists():
            schema_text = schema_file.read_text(errors="replace")
            engine_text = engine_file.read_text(errors="replace")

            # Capture both CREATE TABLE and CREATE VIEW
            schema_tables = set(
                re.findall(r"CREATE\s+(?:TABLE|VIEW)\s+(?:IF NOT EXISTS\s+)?(\w+)",
                           schema_text, re.I)
            )

            # Extract table refs from SQL in Python code (only from string literals)
            engine_tables = set(
                re.findall(r"(?:FROM|INTO|UPDATE|JOIN)\s+(\w+)", engine_text)
            )

            # Filter noise: SQL keywords, short words (<4 chars = likely false positives)
            sql_keywords = {"SELECT", "WHERE", "SET", "VALUES", "AND", "OR", "NOT",
                            "NULL", "AS", "ON", "IN", "IS", "BY", "ORDER", "GROUP",
                            "LIMIT", "OFFSET", "HAVING", "UNION", "CASE", "WHEN",
                            "THEN", "ELSE", "END", "EXISTS", "BETWEEN", "LIKE",
                            "DESC", "ASC", "DISTINCT", "COUNT", "SUM", "AVG",
                            "MAX", "MIN", "INNER", "LEFT", "RIGHT", "OUTER",
                            "CREATE", "DROP", "ALTER", "INDEX", "TABLE", "VIEW"}
            engine_tables = {t for t in engine_tables
                            if t.upper() not in sql_keywords and len(t) >= 4}

            in_schema_not_code = schema_tables - engine_tables
            in_code_not_schema = engine_tables - schema_tables

            if in_schema_not_code:
                drift.append(f"Tables/views in schema.sql but not in engine.py: {in_schema_not_code}")
            if in_code_not_schema:
                drift.append(f"Tables in engine.py but not in schema.sql: {in_code_not_schema}")
        else:
            drift.append("schema.sql or engine.py not found")

        self.findings["C4_schema_drift"] = drift
        p(f"       {len(drift)} drift issues found")

    def _check_config_drift(self):
        """C5: Keys in config.yaml vs keys read in code."""
        p("  [C5] Config drift...")
        config_file = ROOT / "config.yaml"
        drift = []

        if config_file.exists():
            config_text = config_file.read_text(errors="replace")
            # Top-level keys (no leading whitespace)
            top_keys = set(re.findall(r"^(\w+):", config_text, re.M))

            # Scan all Python files for references to these section names
            py_files = find_py_files("services/", "database/")
            all_code = []
            for f in py_files:
                try:
                    all_code.append(f.read_text(errors="replace"))
                except Exception:
                    continue
            combined_code = "\n".join(all_code)

            referenced_keys = set()
            for key in top_keys:
                # Match: config["key"], config['key'], config.get("key"),
                # ["key"], .key, or bare string in config_loader context
                if key in combined_code:
                    referenced_keys.add(key)

            unused_keys = top_keys - referenced_keys
            if unused_keys:
                drift.append(f"Config top-level keys never referenced in code: {unused_keys}")
        else:
            drift.append("config.yaml not found")

        self.findings["C5_config_drift"] = drift
        p(f"       {len(drift)} config issues found")

    def _check_weak_assertions(self):
        """C6: Tautological or weak test assertions."""
        p("  [C6] Weak assertions...")
        _, out, _ = run_cmd(
            'grep -rn "assert.*is not None$\\|assert True$\\|assert.*is True$" '
            f'--include="*.py" {TEST_DIR}'
        )
        hits = [l.strip() for l in out.strip().splitlines() if l.strip()]
        self.findings["C6_weak_assertions"] = hits
        p(f"       {len(hits)} weak assertions found")

    def _check_verify_coverage(self):
        """C8: Test coverage of VERIFY mode features."""
        p("  [C8] VERIFY mode test coverage...")

        test_dir = ROOT / TEST_DIR
        verify_keywords = ["verify", "claim_type", "decidability", "VERDICT_PENALTIES"]
        consensus_keywords = ["consensus_engine", "ConsensusEngine"]

        verify_files = []
        consensus_files = []

        if test_dir.exists():
            for tf in test_dir.rglob("*.py"):
                if "__pycache__" in str(tf):
                    continue
                try:
                    content = tf.read_text(errors="replace")
                except Exception:
                    continue
                rel = str(tf.relative_to(ROOT))
                if any(kw in content for kw in verify_keywords):
                    verify_files.append(rel)
                if any(kw in content for kw in consensus_keywords):
                    consensus_files.append(rel)

        self.findings["C8_verify_coverage"] = [
            f"Test files covering VERIFY mode: {len(verify_files)} — {verify_files[:5]}",
            f"Test files covering consensus_engine: {len(consensus_files)} — {consensus_files[:5]}",
        ]
        p(f"       {len(verify_files)} VERIFY test files, {len(consensus_files)} consensus test files")

    def _check_dead_imports(self):
        """Check for imports of modules that may not exist."""
        p("  [--] Dead imports...")
        _, out, _ = run_cmd(
            'grep -rn "from services\\|from database" --include="*.py" services/ database/ '
            '| grep -v __pycache__'
        )
        # Just collect for the report — manual review needed
        lines = [l.strip() for l in out.strip().splitlines() if l.strip()]
        self.findings["dead_imports_candidates"] = [f"{len(lines)} import statements to review"]
        p(f"       {len(lines)} import statements cataloged")

    def _check_todo_fixme(self):
        """Find TODO/FIXME/HACK markers in production code."""
        p("  [--] TODO/FIXME/HACK markers...")
        _, out, _ = run_cmd(
            'grep -rn "TODO\\|FIXME\\|HACK\\|XXX\\|AUDIT_REQUIRED" '
            '--include="*.py" services/ database/'
            '| grep -v __pycache__'
        )
        hits = [l.strip() for l in out.strip().splitlines() if l.strip()]
        self.findings["todo_fixme"] = hits
        p(f"       {len(hits)} markers found")


# ============================================================================
# PHASE 2: ORPHAN DETECTION
# ============================================================================

class OrphanDetector:
    """Find Python files that are never imported anywhere."""

    def run(self) -> List[str]:
        p("")
        p("=" * 70)
        p("  PHASE 2: ORPHAN DETECTION")
        p("=" * 70)

        # Collect all .py files in services/ and database/ (excluding tests, __init__)
        target_files = find_py_files("services/", "database/", exclude_tests=True)

        # Collect ALL .py files for scanning (including tests, configs, etc.)
        all_py_files = []
        for pattern_dir in ["services/", "database/", "tests/", "demos/"]:
            all_py_files.extend(find_py_files(pattern_dir))
        # Also include root-level .py files
        for f in ROOT.glob("*.py"):
            if f.name != "__init__.py":
                all_py_files.append(f)
        # Include __init__.py files (they wire up imports)
        for d in ["services/", "database/"]:
            base = ROOT / d
            if base.exists():
                for init in base.rglob("__init__.py"):
                    all_py_files.append(init)

        # Read all file contents once
        file_contents: Dict[Path, str] = {}
        for f in all_py_files:
            try:
                file_contents[f] = f.read_text(errors="replace")
            except Exception:
                continue

        orphans = []
        for target in target_files:
            basename = target.stem  # e.g., "consensus_engine"
            found = False

            for scanner, content in file_contents.items():
                if scanner == target:
                    continue  # Don't count self-references

                # Check for import patterns:
                #   from services.esmm.consensus_engine import ...
                #   import consensus_engine
                #   "consensus_engine" in string refs
                if basename in content:
                    found = True
                    break

            if not found:
                rel = str(target.relative_to(ROOT)).replace("\\", "/")
                orphans.append(rel)
                p(f"  ORPHAN: {rel}")

        if not orphans:
            p("  No orphans found.")
        else:
            p(f"\n  {len(orphans)} orphan file(s) found")

        return orphans


# ============================================================================
# PHASE 3: FULL REGRESSION
# ============================================================================

class RegressionRunner:
    """Run full pytest suite and parse results."""

    def run(self) -> Dict:
        p("")
        p("=" * 70)
        p("  PHASE 3: FULL REGRESSION (pytest)")
        p("=" * 70)

        cmd = [
            sys.executable, "-m", "pytest",
            TEST_DIR, "--tb=short", "-q",
            "--continue-on-collection-errors",
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=300, cwd=str(ROOT),
            )
        except subprocess.TimeoutExpired:
            p("  TIMEOUT — pytest exceeded 5 minutes")
            return {"passed": 0, "failed": 0, "skipped": 0, "errors": 0,
                    "output": "TIMEOUT", "returncode": -1}

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        combined = stdout + "\n" + stderr

        # Parse pytest summary line — multiple formats:
        #   "697 passed, 11 skipped"
        #   "697 passed, 2 failed, 11 skipped"
        #   "no tests ran"
        summary = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}

        # Try the standard summary line patterns individually
        for key, pattern in [
            ("passed",  r"(\d+) passed"),
            ("failed",  r"(\d+) failed"),
            ("skipped", r"(\d+) skipped"),
            ("errors",  r"(\d+) error"),
        ]:
            match = re.search(pattern, combined)
            if match:
                summary[key] = int(match.group(1))

        # Detect collection errors specifically (import failures etc.)
        collection_errors = re.findall(
            r"ERROR collecting (tests/\S+)", combined
        )
        summary["collection_errors"] = collection_errors

        summary["returncode"] = result.returncode
        summary["output"] = combined[-3000:]

        # Display results
        if result.returncode == 0 and not collection_errors:
            p(f"\n  PASS: {summary['passed']} passed, "
              f"{summary['failed']} failed, {summary['skipped']} skipped")
        else:
            p(f"\n  RESULT (rc={result.returncode}): "
              f"{summary['passed']} passed, {summary['failed']} failed, "
              f"{summary['skipped']} skipped, {summary['errors']} errors")
            if collection_errors:
                p(f"  Collection errors ({len(collection_errors)}):")
                for ce in collection_errors:
                    p(f"    - {ce}")
            # Show last lines of output for diagnosis
            tail = combined.strip().splitlines()[-15:]
            for line in tail:
                p(f"    | {line}")

        return summary


# ============================================================================
# PHASE 4: MUTATION TESTING
# ============================================================================

@dataclass
class Mutation:
    id: str
    file: str
    description: str
    original: str
    mutant: str
    test_files: str  # space-separated pytest paths
    first_only: bool = False  # Replace only first occurrence


MUTATIONS = [
    # ── GROUP 1: CONSENSUS ENGINE ──
    Mutation(
        id="M1.1",
        file="services/esmm/consensus_engine.py",
        description="Filtre inverse (rejette les bons, garde les mauvais)",
        original="if agreement_ratio < self.min_agreement:",
        mutant="if agreement_ratio > self.min_agreement:",
        test_files="tests/test_r2_weighted_consensus.py",
    ),
    Mutation(
        id="M1.2",
        file="services/esmm/consensus_engine.py",
        description="Poids inverses (agreement<>confidence)",
        original="agreement_ratio * self.agreement_weight",
        mutant="agreement_ratio * self.confidence_weight",
        test_files="tests/test_r2_weighted_consensus.py",
    ),
    Mutation(
        id="M1.3",
        file="services/esmm/consensus_engine.py",
        description="Normalisation desactivee (bypass normalize_triplet)",
        original="subject, relation, obj = normalize_triplet(raw_subject, raw_relation, raw_obj)",
        mutant="subject, relation, obj = raw_subject, raw_relation, raw_obj",
        test_files="tests/test_semantic_merge.py tests/test_r2_normalize_triplet.py",
    ),
    Mutation(
        id="M1.4",
        file="services/esmm/consensus_engine.py",
        description="Tri inverse (le pire resultat en premier)",
        original="consensus_results.sort(key=lambda x: x.consensus_score, reverse=True)",
        mutant="consensus_results.sort(key=lambda x: x.consensus_score, reverse=False)",
        test_files="tests/test_r2_weighted_consensus.py",
    ),
    Mutation(
        id="M1.5",
        file="services/esmm/consensus_engine.py",
        description="Ecart-type force a zero (controverses invisibles)",
        original="std_confidence = statistics.stdev(confidences)",
        mutant="std_confidence = 0.0",
        test_files="tests/test_r2_weighted_consensus.py",
    ),

    # ── GROUP 2: BRIDGE & SERIALIZATION ──
    Mutation(
        id="M2.1",
        file="services/solana/bridge.py",
        description="Perte de precision float (round supprime)",
        original="return min(int(round(value * SCORE_SCALE)), SCORE_SCALE)",
        mutant="return min(int(value * SCORE_SCALE), SCORE_SCALE)",
        test_files="tests/test_phase1_bridge.py",
    ),
    Mutation(
        id="M2.2",
        file="services/solana/bridge.py",
        description="Echelle incorrecte (10000 -> 1000)",
        original="SCORE_SCALE = 10000",
        mutant="SCORE_SCALE = 1000",
        test_files="tests/test_phase1_bridge.py tests/test_solana_deserialize.py",
    ),
    Mutation(
        id="M2.3",
        file="services/solana/bridge.py",
        description="Padding inverse (ljust -> rjust)",
        original="return encoded.ljust(max_len, b'\\x00')",
        mutant="return encoded.rjust(max_len, b'\\x00')",
        test_files="tests/test_phase1_bridge.py",
    ),
    Mutation(
        id="M2.4",
        file="services/solana/bridge.py",
        description="Validation taille supprimee (accepte tout)",
        original="if len(raw) != 32:",
        mutant="if False:",
        test_files="tests/test_phase1_bridge.py",
    ),

    # ── GROUP 3: ATTESTATION ──
    Mutation(
        id="M3.1",
        file="services/esmm/attestation.py",
        description="Seuil verified degrade (0.85 -> 0.50)",
        original="if (consensus_score >= 0.85",
        mutant="if (consensus_score >= 0.50",
        test_files="tests/test_phase03_attestation.py",
    ),
    Mutation(
        id="M3.2",
        file="services/esmm/attestation.py",
        description="Hash canonique corrompu (subject object inverses)",
        original=(
            "        subject.lower().strip(),\n"
            "        predicate.lower().strip(),\n"
            "        object_.lower().strip(),"
        ),
        mutant=(
            "        object_.lower().strip(),\n"
            "        predicate.lower().strip(),\n"
            "        subject.lower().strip(),"
        ),
        test_files="tests/test_phase03_attestation.py",
    ),
    Mutation(
        id="M3.3",
        file="services/esmm/attestation.py",
        description="Votes negatifs comptes comme positifs",
        original="models_agreeing = sum(1 for v in model_votes if v.agreed)",
        mutant="models_agreeing = len(model_votes)",
        test_files="tests/test_phase03_attestation.py",
    ),

    # ── GROUP 4: PIPELINE ──
    Mutation(
        id="M4.1",
        file="services/esmm/pipeline.py",
        description="Injection forcee (filtre de confiance desactive)",
        original='if triplet["consensus_score"] >= config.min_confidence_for_injection:',
        mutant="if True:",
        test_files="tests/test_phase3_pipeline.py",
    ),
    Mutation(
        id="M4.2",
        file="services/esmm/pipeline.py",
        description="Type de retour None vs liste (adapted -> None)",
        original="return adapted, result.run_id, result",
        mutant="return None, result.run_id, result",
        test_files="tests/test_phase3_pipeline.py",
    ),

    # ── GROUP 5: CYCLE MANAGER ──
    Mutation(
        id="M5.1",
        file="services/esmm/cycle_manager.py",
        description="Amnesie du LLM (reponses videes)",
        original="responses = await self._query_models(question, cycle_type, timeout)",
        mutant="responses = []",
        test_files="tests/test_phase3_orchestrator.py",
    ),

    # ── GROUP 6: SOLANA DESERIALIZER ──
    Mutation(
        id="M6.1",
        file="services/solana/client.py",
        description="Champ last_revalidated hardcode (bypass lecture)",
        original='last_revalidated = struct.unpack("<q", read(8))[0]',
        mutant="last_revalidated = 0; read(8)",
        test_files="tests/test_solana_deserialize.py",
        first_only=True,
    ),
    Mutation(
        id="M6.2",
        file="services/solana/client.py",
        description="Assertion taille supprimee",
        original="if offset != len(data):",
        mutant="if False:",
        test_files="tests/test_solana_deserialize.py",
    ),
    Mutation(
        id="M6.3",
        file="services/solana/client.py",
        description="Endianness inversee (little -> big)",
        original='last_revalidated = struct.unpack("<q", read(8))[0]',
        mutant='last_revalidated = struct.unpack(">q", read(8))[0]',
        test_files="tests/test_solana_deserialize.py",
        first_only=True,
    ),

    # ── GROUP 7: EPISTEMIC CALIBRATION (new) ──
    Mutation(
        id="M7.1",
        file="services/esmm/pipeline.py",
        description="Decidability penalty bypassee (score brut utilise)",
        original="actual_score = round(actual_score * v_penalty * t_penalty, 4)",
        mutant="actual_score = actual_score  # penalty disabled",
        test_files="tests/test_claim_verify.py",
    ),
    Mutation(
        id="M7.2",
        file="services/esmm/pipeline.py",
        description="claim_type toujours empirical (classification ignoree)",
        original='verify_claim_type = t["object"]',
        mutant='verify_claim_type = "empirical"  # forced',
        test_files="tests/test_claim_verify.py",
    ),
    Mutation(
        id="M7.3",
        file="services/esmm/cycle_prompts.py",
        description="ASSESS prompt sans STEP 1 classification",
        original="STEP 1 — CLASSIFY the claim type before evaluating:",
        mutant="STEP 1 — EVALUATE the claim directly:",
        test_files="tests/test_claim_verify.py",
    ),
]


class MutationRunner:
    """Execute mutation testing with integrity checks."""

    def __init__(self):
        self.results: List[Dict] = []

    def run(self) -> List[Dict]:
        p("")
        p("=" * 70)
        p("  PHASE 4: MUTATION TESTING (21 mutations)")
        p("=" * 70)

        # Load checksums if available
        checksums = {}
        if CHECKSUMS_PATH.exists():
            try:
                for line in CHECKSUMS_PATH.read_text().strip().splitlines():
                    h, f = line.split("  ", 1)
                    checksums[f] = h
                p(f"  Loaded {len(checksums)} file checksums")

                # Verify integrity before starting
                for fpath, expected in checksums.items():
                    fp = ROOT / fpath
                    if fp.exists():
                        actual = sha256_file(fp)
                        if actual != expected:
                            p(f"  [WARN] {fpath} modified since baseline — "
                              f"checksums will be regenerated")
                            checksums = {}
                            break
            except Exception:
                checksums = {}

        if not checksums:
            p("  No valid checksums — generating from current state...")
            for m in MUTATIONS:
                fp = ROOT / m.file
                if fp.exists():
                    checksums[m.file] = sha256_file(fp)
            # Save new checksums
            lines = [f"{h}  {f}" for f, h in sorted(checksums.items())]
            CHECKSUMS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
            p(f"  Generated {len(checksums)} checksums -> {CHECKSUMS_PATH.name}")

        p("")

        for i, m in enumerate(MUTATIONS, 1):
            p(f"  [{i:2d}/{len(MUTATIONS)}] {m.id} — {m.description}")
            r = self._run_one(m, checksums)
            self.results.append(r)

            symbols = {
                "KILLED": "KILLED", "SURVIVED": "SURVIVED", "CRASH": "CRASH",
                "SKIP": "SKIP", "ERROR": "ERROR", "ABORT": "ABORT",
            }
            p(f"           -> [{symbols.get(r['verdict'], '?')}] {r['detail']}")

        # Final integrity check
        p("")
        p("  INTEGRITY CHECK:")
        all_ok = True
        for fpath, expected in checksums.items():
            fp = ROOT / fpath
            if fp.exists():
                actual = sha256_file(fp)
                if actual != expected:
                    p(f"    [FAIL] {fpath}")
                    all_ok = False

        if all_ok:
            p("    [OK] All files restored to baseline")
        else:
            p("    [FAIL] CORRUPTION — some files not restored!")

        return self.results

    def _run_one(self, m: Mutation, checksums: dict) -> dict:
        """Execute single mutation cycle: backup -> inject -> test -> classify -> restore."""
        filepath = ROOT / m.file
        if not filepath.exists():
            return {"id": m.id, "verdict": "SKIP",
                    "detail": f"File not found: {m.file}"}

        original_content = filepath.read_bytes()
        original_hash = sha256_bytes(original_content)

        # Verify file integrity
        expected_hash = checksums.get(m.file)
        if expected_hash and original_hash != expected_hash:
            return {"id": m.id, "verdict": "ABORT",
                    "detail": f"File modified before mutation"}

        # Normalize CRLF -> LF for consistent string matching
        has_crlf = b"\r\n" in original_content
        text = original_content.decode("utf-8").replace("\r\n", "\n")

        # Check original string exists
        count = text.count(m.original)
        if count == 0:
            return {"id": m.id, "verdict": "SKIP",
                    "detail": f"Original string not found in {m.file}"}
        if count > 1 and not m.first_only:
            return {"id": m.id, "verdict": "SKIP",
                    "detail": f"Original string found {count} times (expected 1)"}

        try:
            # Inject mutation
            if m.first_only:
                mutated_text = text.replace(m.original, m.mutant, 1)
            else:
                mutated_text = text.replace(m.original, m.mutant)

            # Verify mutation applied
            if m.mutant not in mutated_text:
                return {"id": m.id, "verdict": "SKIP",
                        "detail": "Mutant string not found after replacement"}
            if m.original in mutated_text and not m.first_only:
                return {"id": m.id, "verdict": "SKIP",
                        "detail": "Original string still present"}

            # Write mutated file
            if has_crlf:
                mutated_text = mutated_text.replace("\n", "\r\n")
            filepath.write_bytes(mutated_text.encode("utf-8"))

            # Run targeted tests
            test_args = m.test_files.split()
            cmd = [
                sys.executable, "-m", "pytest", *test_args,
                f"--timeout={TIMEOUT_SECONDS}",
                "-x", "-q", "--tb=short", "--no-header",
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=TIMEOUT_SECONDS + 10, cwd=str(ROOT),
            )

            combined = (result.stdout or "") + (result.stderr or "")

            if result.returncode == 0:
                return {"id": m.id, "verdict": "SURVIVED",
                        "detail": "Tests passed despite mutation",
                        "output": combined[-500:]}

            # Classify failure type
            crash_indicators = ["NameError", "SyntaxError", "ImportError",
                                "TypeError", "ModuleNotFoundError", "AttributeError"]
            for indicator in crash_indicators:
                if indicator in combined and "FAILED" not in combined:
                    return {"id": m.id, "verdict": "CRASH",
                            "detail": f"Python crash: {indicator}",
                            "output": combined[-500:]}

            return {"id": m.id, "verdict": "KILLED",
                    "detail": "Tests detected the mutation",
                    "output": (result.stdout or "")[-500:]}

        except subprocess.TimeoutExpired:
            return {"id": m.id, "verdict": "KILLED",
                    "detail": "Timeout (potential infinite loop)"}
        except Exception as e:
            return {"id": m.id, "verdict": "ERROR",
                    "detail": f"Unexpected error: {e}"}
        finally:
            # ALWAYS restore
            filepath.write_bytes(original_content)
            restored_hash = sha256_file(filepath)
            if restored_hash != original_hash:
                p(f"    CORRUPTION DETECTED for {m.file}!")
                sys.exit(1)


# ============================================================================
# REPORT GENERATION
# ============================================================================

def generate_report(
    static: Dict[str, List[str]],
    orphans: List[str],
    regression: Dict,
    mutations: List[Dict],
) -> str:
    """Generate unified EPP_AUDIT_REPORT.md."""

    now = time.strftime("%Y-%m-%d %H:%M")
    killed = sum(1 for r in mutations if r["verdict"] == "KILLED")
    survived = sum(1 for r in mutations if r["verdict"] == "SURVIVED")
    crashed = sum(1 for r in mutations if r["verdict"] == "CRASH")
    skipped = sum(1 for r in mutations if r["verdict"] in ("SKIP", "ERROR", "ABORT"))

    # Overall verdict
    test_failures = regression.get("failed", 0) + regression.get("errors", 0)
    # Collection errors are warnings (missing deps), not critical failures
    has_collection_errors = bool(regression.get("collection_errors"))
    # rc!=0 with 0 passed and no collection errors = something is very wrong
    pytest_broken = (regression.get("returncode", 0) not in (0, -1)
                     and regression.get("passed", 0) == 0
                     and not has_collection_errors)
    critical_issues = survived + test_failures + (1 if pytest_broken else 0)
    if critical_issues == 0 and not has_collection_errors:
        overall = "VERT"
        overall_icon = "🟢"
    elif critical_issues <= 3 or (critical_issues == 0 and has_collection_errors):
        overall = "ORANGE"
        overall_icon = "🟠"
    else:
        overall = "ROUGE"
        overall_icon = "🔴"

    lines = [
        f"# EPP_VERDICT — UNIFIED AUDIT REPORT",
        "",
        f"> **Date** : {now}",
        f"> **Verdict** : {overall_icon} **{overall}**",
        f"> **Tests** : {regression.get('passed', '?')} passed, "
        f"{regression.get('failed', '?')} failed, "
        f"{regression.get('skipped', '?')} skipped",
        f"> **Mutations** : {killed} killed, {survived} survived, "
        f"{crashed} crash, {skipped} skipped",
        f"> **Orphans** : {len(orphans)}",
        "",
        "---",
        "",

        # ── PHASE 1 ──
        "## Phase 1 — Static Analysis",
        "",
    ]

    for control, findings in static.items():
        label = control.upper().replace("_", " ")
        icon = "🟢" if len(findings) == 0 else "🟡" if len(findings) <= 3 else "🟠"
        lines.append(f"### {icon} {label} ({len(findings)} findings)")
        lines.append("")
        if findings:
            for f in findings[:15]:  # Cap at 15 per section
                lines.append(f"- `{f}`")
            if len(findings) > 15:
                lines.append(f"- ... and {len(findings) - 15} more")
        else:
            lines.append("- No issues found")
        lines.append("")

    # ── PHASE 2 ──
    lines.extend([
        "---",
        "",
        "## Phase 2 — Orphan Detection",
        "",
    ])
    if orphans:
        for o in orphans:
            lines.append(f"- `{o}`")
    else:
        lines.append("- No orphan files detected")
    lines.append("")

    # ── PHASE 3 ──
    lines.extend([
        "---",
        "",
        "## Phase 3 — Full Regression",
        "",
        f"| Metric | Value |",
        f"|:---|:---|",
        f"| Passed | {regression.get('passed', '?')} |",
        f"| Failed | {regression.get('failed', '?')} |",
        f"| Skipped | {regression.get('skipped', '?')} |",
        f"| Return code | {regression.get('returncode', '?')} |",
        "",
    ])

    if regression.get("returncode", 0) != 0:
        lines.extend([
            f"**pytest output (rc={regression.get('returncode')}):**",
            "```",
            regression.get("output", "")[-1500:].strip(),
            "```",
            "",
        ])
        if regression.get("collection_errors"):
            lines.append("**Collection errors (missing dependencies):**")
            for ce in regression["collection_errors"]:
                lines.append(f"- `{ce}`")
            lines.append("")

    # ── PHASE 4 ──
    lines.extend([
        "---",
        "",
        "## Phase 4 — Mutation Testing",
        "",
        f"| # | File | Mutation | Verdict |",
        f"|:---|:---|:---|:---|",
    ])

    symbols = {
        "KILLED": "🟢 KILLED", "SURVIVED": "🔴 SURVIVED",
        "CRASH": "⚠️ CRASH", "SKIP": "⏭️ SKIP",
        "ERROR": "❌ ERROR", "ABORT": "🛑 ABORT",
    }

    for r in mutations:
        mid = r["id"]
        mut = next((m for m in MUTATIONS if m.id == mid), None)
        fname = mut.file.split("/")[-1] if mut else "?"
        desc = mut.description if mut else "?"
        verdict = symbols.get(r["verdict"], r["verdict"])
        lines.append(f"| {mid} | `{fname}` | {desc} | {verdict} |")

    lines.append("")

    # Detail for SURVIVED and CRASH
    for r in mutations:
        if r["verdict"] in ("SURVIVED", "CRASH"):
            lines.extend([
                f"### {r['id']} — {symbols[r['verdict']]}",
                "",
                f"**Detail** : {r['detail']}",
            ])
            if r.get("output"):
                lines.extend(["", "```", r["output"].strip(), "```"])
            lines.append("")

    # ── FOOTER ──
    lines.extend([
        "---",
        "",
        f"*Generated by epp_audit.py — {now}*",
    ])

    return "\n".join(lines)


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="EPP_Verdict — Unified Audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--static", action="store_true", help="Phase 1 only: static analysis")
    parser.add_argument("--orphans", action="store_true", help="Phase 2 only: orphan detection")
    parser.add_argument("--regression", action="store_true", help="Phase 3 only: pytest regression")
    parser.add_argument("--mutations", action="store_true", help="Phase 4 only: mutation testing")
    parser.add_argument("--no-mutations", action="store_true", help="Phases 1-3 (skip mutations)")

    args = parser.parse_args()

    # If no specific phase requested, run all
    run_all = not (args.static or args.orphans or args.regression or args.mutations)

    p("")
    p("=" * 70)
    p("  EPP_VERDICT — UNIFIED AUDIT")
    p(f"  {time.strftime('%Y-%m-%d %H:%M')}")
    p("=" * 70)

    static_results: Dict[str, List[str]] = {}
    orphan_results: List[str] = []
    regression_results: Dict = {"passed": 0, "failed": 0, "skipped": 0, "returncode": -1}
    mutation_results: List[Dict] = []

    # Phase 1
    if run_all or args.static or args.no_mutations:
        static_results = StaticAnalyzer().run_all()

    # Phase 2
    if run_all or args.orphans or args.no_mutations:
        orphan_results = OrphanDetector().run()

    # Phase 3
    if run_all or args.regression or args.no_mutations:
        regression_results = RegressionRunner().run()

    # Phase 4
    if (run_all or args.mutations) and not args.no_mutations:
        mutation_results = MutationRunner().run()

    # Generate report
    report = generate_report(
        static_results, orphan_results,
        regression_results, mutation_results,
    )
    REPORT_PATH.write_text(report, encoding="utf-8")

    # Final summary
    killed = sum(1 for r in mutation_results if r["verdict"] == "KILLED")
    survived = sum(1 for r in mutation_results if r["verdict"] == "SURVIVED")

    p("")
    p("=" * 70)
    p("  SUMMARY")
    p("=" * 70)
    if static_results:
        total_findings = sum(len(v) for v in static_results.values())
        p(f"  Static:     {total_findings} findings across {len(static_results)} controls")
    if orphan_results is not None:
        p(f"  Orphans:    {len(orphan_results)} dead files")
    if regression_results.get("returncode") != -1:
        p(f"  Regression: {regression_results['passed']} passed, "
          f"{regression_results['failed']} failed, "
          f"{regression_results['skipped']} skipped")
    if mutation_results:
        p(f"  Mutations:  {killed} killed / {survived} survived")

    p(f"\n  Report: {REPORT_PATH}")
    p("=" * 70)

    # Exit code: 0 = clean, 1 = issues found, 2 = critical
    if survived > 0 or regression_results.get("failed", 0) > 0:
        sys.exit(2)
    elif sum(len(v) for v in static_results.values()) > 10:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
