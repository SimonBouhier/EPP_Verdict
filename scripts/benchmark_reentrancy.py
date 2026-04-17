"""
ADR-014 — Premier benchmark live : reentrancy.sol
==================================================

Script standalone pour le premier run live du moteur d'audit EPP.
Audite reentrancy.sol avec 3 modèles Ollama (mistral, deepseek-r1, gemma3).
Optionnellement lance Slither en parallèle pour comparaison.

Usage:
    python scripts/benchmark_reentrancy.py
    python scripts/benchmark_reentrancy.py --with-slither
    python scripts/benchmark_reentrancy.py --dry-run  (MockProvider, pas d'Ollama)

Pré-requis:
    - Ollama running avec mistral:latest, llama3.1:8b, gemma3:latest
    - solc-select use 0.4.25 (pour Slither)
    - Slither installé (optionnel, --with-slither)

Résultats:
    - Console : index structuré par fonction
    - data/epp_audit_devnet.db : attestations persistées
    - (optionnel) slither_reentrancy.json : sortie Slither brute
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Ajouter la racine du projet au path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================================
# CONFIGURATION
# ============================================================================

CONTRACT_PATH = str(PROJECT_ROOT / "tests" / "fixtures" / "benchmark" / "not_so_smart" / "reentrancy.sol")
AUDIT_DB_PATH = str(PROJECT_ROOT / "data" / "epp_audit_devnet.db")
FRAME = "smartcontract_audit_v1.0"

# 3 modèles, 3 familles architecturales (Mistral, DeepSeek, Google)
MODELS = [
    "mistral:latest",
    "llama3.1:8b",
    "gemma3:latest",
]

# Ground truth pour comparaison post-run
GROUND_TRUTH = {
    "withdrawBalance": {
        "swc_id": "SWC-107",
        "severity": "high",
        "description": "External call before state update — reentrancy",
    },
}


# ============================================================================
# HELPERS
# ============================================================================

def print_header(text: str) -> None:
    """Affiche un header formaté."""
    print()
    print("=" * 70)
    print(f"  {text}")
    print("=" * 70)
    print()


def print_unit_result(unit_name: str, severity: str, consensus: float,
                      external_calls: list, state_writes: list) -> None:
    """Affiche le résultat d'une unité auditée."""
    print(f"  [{severity.upper():15s}] {unit_name}()")
    print(f"     consensus: {consensus:.2f}")
    if external_calls:
        print(f"     external_calls: {external_calls}")
    if state_writes:
        print(f"     state_writes: {state_writes}")

    # Comparaison avec ground truth
    if unit_name in GROUND_TRUTH:
        gt = GROUND_TRUTH[unit_name]
        match = "MATCH" if severity == gt["severity"] else f"EXPECTED {gt['severity']}"
        print(f"     ground_truth: {gt['swc_id']} -- {match}")
    print()


# ============================================================================
# SLITHER (optionnel)
# ============================================================================

def run_slither(contract_path: str) -> dict:
    """Lance Slither et retourne les findings."""
    import subprocess

    print("[Slither] Running static analysis...")
    try:
        result = subprocess.run(
            ["slither", contract_path, "--json", "-"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.stdout.strip():
            data = json.loads(result.stdout)
            detectors = data.get("results", {}).get("detectors", [])
            print(f"[Slither] {len(detectors)} findings detected")
            return data
        else:
            print(f"[Slither] No JSON output. stderr: {result.stderr[:200]}")
            return {}
    except FileNotFoundError:
        print("[Slither] Not installed — skipping")
        return {}
    except Exception as exc:
        print(f"[Slither] Error: {exc}")
        return {}


def print_slither_summary(slither_data: dict) -> None:
    """Affiche un résumé des findings Slither."""
    detectors = slither_data.get("results", {}).get("detectors", [])
    if not detectors:
        return

    print_header("SLITHER STATIC ANALYSIS")

    by_severity = {"High": [], "Medium": [], "Low": [], "Informational": []}
    for d in detectors:
        sev = d.get("impact", "Informational")
        check = d.get("check", "unknown")
        by_severity.setdefault(sev, []).append(check)

    for sev in ["High", "Medium", "Low", "Informational"]:
        findings = by_severity.get(sev, [])
        if findings:
            print(f"  [{sev}] {len(findings)} finding(s): {', '.join(set(findings))}")

    # Concordance avec ground truth
    reentrancy_found = any(
        d.get("check") == "reentrancy-eth" for d in detectors
    )
    print()
    if reentrancy_found:
        print("  [OK] Slither confirms SWC-107 (reentrancy-eth) on withdrawBalance")
    else:
        print("  [!!] Slither did NOT detect reentrancy-eth")
    print()


# ============================================================================
# AUDIT EPP (principal)
# ============================================================================

async def run_epp_audit(contract_path: str, dry_run: bool = False) -> dict:
    """
    Lance l'audit EPP complet sur un contrat.

    Returns: dict avec les résultats structurés.
    """
    from database.engine import ISpaceDB
    from database.pool import close_pool
    from services.audit.audit_runner import run_audit
    from services.audit.contract_slicer import slice_contract

    # Afficher le découpage d'abord
    print_header("CONTRACT SLICING")
    slice_result = slice_contract(contract_path)
    print(f"  Contract: {slice_result.units[0].contract_name if slice_result.units else 'unknown'}")
    print(f"  Language: {slice_result.language}")
    print(f"  Hash: {slice_result.contract_hash[:16]}...")
    print(f"  Total lines: {slice_result.total_lines}")
    print(f"  Units extracted: {len(slice_result.units)}")
    print(f"  Units skipped: {len(slice_result.skipped_units)} {slice_result.skipped_units}")
    print(f"  Strategy: {slice_result.slice_strategy}")
    print()

    for unit in slice_result.units:
        priority = "HIGH" if unit.external_calls else ("MED" if unit.state_writes else "LOW")
        print(f"  [{priority:4s}] {unit.unit_name}() -- ext:{unit.external_calls} sw:{unit.state_writes}")

    # Initialiser la DB d'audit isolée
    print_header("EPP EPISTEMIC AUDIT")

    db = ISpaceDB(AUDIT_DB_PATH)
    await db.initialize()

    models = MODELS
    if dry_run:
        print("  [!!] DRY-RUN MODE -- MockProvider (no Ollama)")
        models = ["mock:1", "mock:2", "mock:3"]
    else:
        print(f"  Models: {', '.join(models)}")

    print(f"  Frame: {FRAME}")
    print(f"  DB: {AUDIT_DB_PATH}")
    print(f"  Cache: disabled (benchmark mode)")
    print()
    print("  Starting audit... (this may take several minutes)")
    print()

    t_start = time.time()

    result = await run_audit(
        contract_path=contract_path,
        db=db,
        models=models,
        frame=FRAME,
        use_slither=False,  # Slither géré séparément dans ce script
        use_cache=False,    # Pas de cache pour le benchmark
    )

    duration = time.time() - t_start

    # Afficher les résultats
    print_header("AUDIT RESULTS — PER UNIT")

    for ur in result.unit_results:
        unit = ur["unit"]
        severity = ur["severity"]

        # Extraire consensus_score depuis le pipeline result
        pr = ur["pipeline_result"]
        consensus = 0.0
        if pr.attestations:
            consensus = pr.attestations[0].consensus_score

        print_unit_result(
            unit_name=unit.unit_name,
            severity=severity,
            consensus=consensus,
            external_calls=unit.external_calls,
            state_writes=unit.state_writes,
        )

    # Résumé agrégé
    print_header("AGGREGATE SUMMARY")
    print(f"  Contract: {result.contract_name}")
    print(f"  Aggregate severity: {result.aggregate_severity}")
    print(f"  Aggregate consensus: {result.aggregate_consensus:.2f}")
    print(f"  Vulnerabilities found: {result.total_vulnerabilities}")
    print(f"  Units audited: {result.total_units_audited}")
    print(f"  Units skipped: {result.total_units_skipped}")
    print(f"  Duration: {duration:.1f}s ({result.duration_ms:.0f}ms pipeline)")
    print(f"  Errors: {len(result.errors)}")

    if result.errors:
        print()
        print("  Errors:")
        for err in result.errors:
            print(f"    - {err}")

    await close_pool()

    return {
        "contract": result.contract_name,
        "aggregate_severity": result.aggregate_severity,
        "aggregate_consensus": result.aggregate_consensus,
        "total_vulnerabilities": result.total_vulnerabilities,
        "units_audited": result.total_units_audited,
        "duration_s": duration,
        "errors": result.errors,
    }


# ============================================================================
# MAIN
# ============================================================================

async def main():
    args = sys.argv[1:]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = PROJECT_ROOT / "data" / f"benchmark_light_{timestamp}.json"
    with_slither = "--with-slither" in args
    dry_run = "--dry-run" in args

    print_header("EPP VERDICT — SMART CONTRACT AUDIT BENCHMARK")
    print(f"  Contract: {CONTRACT_PATH}")
    print(f"  Models: {', '.join(MODELS)}")
    print(f"  Slither: {'enabled' if with_slither else 'disabled'}")
    print(f"  Mode: {'DRY-RUN (MockProvider)' if dry_run else 'LIVE (Ollama)'}")

    # Phase 1 : Slither (optionnel)
    slither_data = {}
    if with_slither:
        slither_data = run_slither(CONTRACT_PATH)
        if slither_data:
            print_slither_summary(slither_data)

    # Phase 2 : EPP Audit
    epp_results = await run_epp_audit(CONTRACT_PATH, dry_run=dry_run)

    # Phase 3 : Concordance Slither ↔ EPP (si les deux ont tourné)
    if slither_data and epp_results:
        print_header("CONCORDANCE SLITHER <-> EPP")

        slither_detectors = slither_data.get("results", {}).get("detectors", [])
        slither_has_reentrancy = any(
            d.get("check") == "reentrancy-eth" for d in slither_detectors
        )
        epp_severity = epp_results.get("aggregate_severity", "informational")

        if slither_has_reentrancy and epp_severity in ("high", "medium"):
            print("  [OK] CONCORDANT -- Both Slither and EPP flag high-severity reentrancy")
        elif slither_has_reentrancy and epp_severity == "informational":
            print("  [!!] DISCORDANT -- Slither flags reentrancy, EPP says informational")
        elif not slither_has_reentrancy and epp_severity in ("high", "medium"):
            print("  [!!] DISCORDANT -- EPP flags vulnerability, Slither missed it")
        else:
            print("  [--] BOTH CLEAR -- Neither tool flagged high-severity issues")
        print()

    # Résumé final
    print_header("BENCHMARK COMPLETE")
    print(f"  Ground truth: SWC-107 (reentrancy) in withdrawBalance -- severity HIGH")
    print(f"  EPP verdict: {epp_results.get('aggregate_severity', 'N/A')}")
    print(f"  Duration: {epp_results.get('duration_s', 0):.1f}s")

    # Save JSON summary
    summary = {
        "timestamp": timestamp,
        "contract": CONTRACT_PATH,
        "db_path": AUDIT_DB_PATH,
        "models": MODELS,
        "slither_enabled": with_slither,
        **epp_results,
    }
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"  Output: {output_path.resolve()}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
