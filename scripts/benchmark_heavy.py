"""
ADR-014 — Benchmark Heavy Models : phi4 / deepseek-r1 / gpt-oss:20b
====================================================================

Script avec logging temps réel et timeout par unité.
Chaque étape affiche : modèle, fonction, durée, statut.
Si un modèle timeout → skip + log, les autres continuent.

Usage:
    python scripts/benchmark_heavy.py                     # Run complet
    python scripts/benchmark_heavy.py --test-models       # Test connexion Ollama seulement
    python scripts/benchmark_heavy.py --single withdraw   # 1 seule fonction (validation rapide)
    python scripts/benchmark_heavy.py --timeout 300       # Timeout custom (défaut 240s)

Pré-requis:
    - Ollama running
    - DB purgée (le script refuse de tourner sur une DB non vide)
"""

import asyncio
import json
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================================
# CONFIGURATION
# ============================================================================

CONTRACT_PATH = str(PROJECT_ROOT / "tests" / "fixtures" / "benchmark" / "not_so_smart" / "reentrancy.sol")
AUDIT_DB_PATH = str(PROJECT_ROOT / "data" / "epp_audit_heavy.db")
FRAME = "smartcontract_audit_v1.0"

MODELS = [
    "phi4-reasoning:latest",
    "deepseek-r1:latest",
    "gpt-oss:20b",
    # "granite3.3:latest",   # 413GB — décommenter si VRAM suffisante
]

TIMEOUT_PER_UNIT = 900  # 15 minutes par fonction — les modèles reasoning peuvent dépasser 300s


# ============================================================================
# LOGGING TEMPS RÉEL
# ============================================================================

_start_time = time.time()


def log(msg: str, level: str = "INFO") -> None:
    """Log avec timestamp relatif depuis le début du script."""
    elapsed = time.time() - _start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    prefix = {"INFO": "[  ]", "OK": "[OK]", "WARN": "[!!]", "ERR": "[XX]", "TIME": "[TM]", "SKIP": "[--]"}
    icon = prefix.get(level, "  ")
    print(f"[{minutes:02d}:{seconds:02d}] {icon} {msg}", flush=True)


# ============================================================================
# TEST CONNEXION OLLAMA
# ============================================================================

async def test_models() -> dict:
    """Teste chaque modèle avec un prompt minimal. Retourne {model: ok/error}."""
    import httpx

    log("Testing Ollama connectivity...", "INFO")
    results = {}

    for model in MODELS:
        log(f"  Testing {model}...", "INFO")
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": model,
                        "prompt": "Say OK",
                        "stream": False,
                        "options": {"num_predict": 10},
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    response_text = data.get("response", "")[:50]
                    duration = time.time() - t0
                    log(f"  {model}: OK ({duration:.1f}s) — '{response_text}'", "OK")
                    results[model] = "ok"
                else:
                    log(f"  {model}: HTTP {resp.status_code}", "ERR")
                    results[model] = f"http_{resp.status_code}"
        except httpx.TimeoutException:
            log(f"  {model}: TIMEOUT (>60s on trivial prompt)", "ERR")
            results[model] = "timeout"
        except httpx.ConnectError:
            log(f"  {model}: Ollama not reachable", "ERR")
            results[model] = "connection_error"
        except Exception as exc:
            log(f"  {model}: {exc}", "ERR")
            results[model] = str(exc)

    log("", "INFO")
    working = [m for m, s in results.items() if s == "ok"]
    failed = [m for m, s in results.items() if s != "ok"]
    log(f"Working: {len(working)}/{len(MODELS)} — {working}", "OK" if working else "ERR")
    if failed:
        log(f"Failed: {failed}", "WARN")
    return results


# ============================================================================
# AUDIT AVEC TIMEOUT PAR UNITÉ
# ============================================================================

async def audit_single_unit(unit, db, models: list, unit_index: int, total_units: int) -> dict:
    """
    Audite une seule ContractUnit avec timeout.
    Retourne un dict avec le résultat ou l'erreur.
    """
    from services.audit.audit_runner import format_unit_for_audit_prompt, _safe_format, _ASSESS_AUDIT_TEMPLATE
    from services.esmm.pipeline import PipelineConfig, run_pipeline
    from services.esmm.orchestrator import ESMMRunConfig

    func_name = unit.unit_name
    log(f"[{unit_index}/{total_units}] Auditing {func_name}()...", "INFO")
    log(f"  external_calls: {unit.external_calls}", "INFO")
    log(f"  state_writes: {unit.state_writes}", "INFO")
    log(f"  models: {', '.join(models)}", "INFO")

    t0 = time.time()

    try:
        placeholders = format_unit_for_audit_prompt(unit)
        claim = _safe_format(_ASSESS_AUDIT_TEMPLATE, **placeholders)

        pipeline_config = PipelineConfig(
            use_cache=False,
            metrological_frame=FRAME,
            default_epistemic_type="security_audit",  # Fix 3 (Lot A)
        )
        esmm_cfg = ESMMRunConfig(
            models=models,
            input_mode="verify",
            original_claim=claim,
            subject_override=f"{unit.contract_name}::{unit.unit_name}",  # Fix 1 (Lot A)
        )

        # Timeout wrapper (TIMEOUT_PER_UNIT=0 → pas de limite)
        if TIMEOUT_PER_UNIT > 0:
            pipeline_result = await asyncio.wait_for(
                run_pipeline(
                    question=claim,
                    db=db,
                    config=pipeline_config,
                    esmm_config=esmm_cfg,
                ),
                timeout=TIMEOUT_PER_UNIT,
            )
        else:
            pipeline_result = await run_pipeline(
                question=claim,
                db=db,
                config=pipeline_config,
                esmm_config=esmm_cfg,
            )

        duration = time.time() - t0

        # Extract verdict
        if not pipeline_result.attestations:
            log(f"  → {func_name}(): no attestation produced ({duration:.0f}s)", "WARN")
            return {
                "unit_name": func_name,
                "status": "no_attestation",
                "verdict": None,
                "score": 0.0,
                "tier": None,
                "duration_s": duration,
                "errors": pipeline_result.errors or ["no attestation produced"],
            }

        att = pipeline_result.attestations[0]
        score = att.consensus_score
        tier = att.confidence_tier
        meta = att.consensus_meta
        if isinstance(meta, str):
            meta = json.loads(meta)
        if isinstance(meta, dict):
            verdict = meta.get("verify", {}).get("final_verdict", att.object)
        else:
            verdict = att.object

        log(f"  → {func_name}(): verdict={verdict} score={score:.2f} tier={tier} ({duration:.0f}s)", "OK")
        return {
            "unit_name": func_name,
            "status": "ok",
            "verdict": verdict,
            "score": score,
            "tier": tier,
            "duration_s": duration,
            "errors": pipeline_result.errors,
        }

    except asyncio.TimeoutError:
        duration = time.time() - t0
        log(f"  → {func_name}(): TIMEOUT after {duration:.0f}s (limit={TIMEOUT_PER_UNIT}s)", "ERR")
        return {
            "unit_name": func_name,
            "status": "timeout",
            "verdict": None,
            "score": 0,
            "tier": None,
            "duration_s": duration,
            "errors": [f"Timeout after {duration:.0f}s"],
        }

    except Exception as exc:
        duration = time.time() - t0
        log(f"  → {func_name}(): ERROR after {duration:.0f}s — {exc}", "ERR")
        return {
            "unit_name": func_name,
            "status": "error",
            "verdict": None,
            "score": 0,
            "tier": None,
            "duration_s": duration,
            "errors": [str(exc)],
        }


# ============================================================================
# MAIN
# ============================================================================

async def main():
    global TIMEOUT_PER_UNIT
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    args = sys.argv[1:]

    # Parse args
    test_only = "--test-models" in args
    single_func = None
    timeout = TIMEOUT_PER_UNIT
    
    if "--single" in args:
        idx = args.index("--single")
        if idx + 1 < len(args):
            single_func = args[idx + 1]

    if "--timeout" in args:
        idx = args.index("--timeout")
        if idx + 1 < len(args):
            timeout = int(args[idx + 1])

    TIMEOUT_PER_UNIT = timeout

    log("=" * 60, "INFO")
    log("EPP VERDICT — HEAVY MODELS BENCHMARK", "INFO")
    log("=" * 60, "INFO")
    log(f"Contract: {Path(CONTRACT_PATH).name}", "INFO")
    log(f"Models: {', '.join(MODELS)}", "INFO")
    log(f"Timeout per unit: {TIMEOUT_PER_UNIT}s", "INFO")
    log(f"DB: {AUDIT_DB_PATH}", "INFO")
    if single_func:
        log(f"Single function mode: {single_func}", "INFO")
    log("", "INFO")

    # Step 1: Test models
    model_status = await test_models()
    working_models = [m for m, s in model_status.items() if s == "ok"]

    if not working_models:
        log("No working models — aborting.", "ERR")
        return

    if len(working_models) < len(MODELS):
        log(f"Continuing with {len(working_models)} models: {working_models}", "WARN")
        log("Failed models will not be used.", "WARN")

    if test_only:
        log("--test-models flag: stopping here.", "INFO")
        return

    # Step 2: Check DB is clean
    db_path = Path(AUDIT_DB_PATH)
    if db_path.exists():
        log(f"DB already exists at {AUDIT_DB_PATH}", "WARN")
        log("Delete it first: Remove-Item data/epp_audit_heavy.db*", "WARN")
        log("Continuing anyway (results will accumulate)...", "WARN")

    # Step 3: Slice contract
    log("", "INFO")
    log("--- SLICING CONTRACT ---", "INFO")
    from services.audit.contract_slicer import slice_contract
    from services.audit.audit_runner import _sort_units_by_priority

    slice_result = slice_contract(CONTRACT_PATH)
    sorted_units = _sort_units_by_priority(slice_result.units)

    log(f"Contract: {slice_result.units[0].contract_name if slice_result.units else '?'}", "INFO")
    log(f"Units: {len(sorted_units)} auditable, {len(slice_result.skipped_units)} skipped", "INFO")
    log("", "INFO")

    for i, u in enumerate(sorted_units):
        priority = "HIGH" if u.external_calls else ("MED" if u.state_writes else "LOW")
        log(f"  [{priority:4s}] {u.unit_name}()", "INFO")

    # Filter if single function mode
    if single_func:
        sorted_units = [u for u in sorted_units if single_func.lower() in u.unit_name.lower()]
        if not sorted_units:
            log(f"No unit matching '{single_func}' — aborting.", "ERR")
            return
        log(f"Filtered to {len(sorted_units)} unit(s) matching '{single_func}'", "INFO")

    # Step 4: Initialize DB
    log("", "INFO")
    log("--- INITIALIZING AUDIT DB ---", "INFO")
    from database.engine import ISpaceDB

    db = ISpaceDB(AUDIT_DB_PATH)
    await db.initialize()
    log(f"DB ready: {AUDIT_DB_PATH}", "OK")

    # Step 5: Audit each unit
    log("", "INFO")
    log("--- STARTING AUDIT ---", "TIME")
    if TIMEOUT_PER_UNIT > 0:
        log(f"Estimated time: {len(sorted_units) * TIMEOUT_PER_UNIT // 60} min max "
            f"({len(sorted_units)} units x {TIMEOUT_PER_UNIT}s timeout)", "INFO")
    else:
        log(f"No timeout -- {len(sorted_units)} units will run until completion", "INFO")
    log("", "INFO")

    results = []
    for i, unit in enumerate(sorted_units, 1):
        result = await audit_single_unit(unit, db, working_models, i, len(sorted_units))
        results.append(result)
        log("", "INFO")

    from database.pool import close_pool
    await close_pool()

    # Step 6: Summary
    log("=" * 60, "INFO")
    log("BENCHMARK SUMMARY", "INFO")
    log("=" * 60, "INFO")
    log("", "INFO")

    total_time = time.time() - _start_time
    ok_count = sum(1 for r in results if r["status"] == "ok")
    timeout_count = sum(1 for r in results if r["status"] == "timeout")
    error_count = sum(1 for r in results if r["status"] == "error")

    log(f"Units audited: {ok_count}/{len(results)}", "OK" if ok_count == len(results) else "WARN")
    if timeout_count:
        log(f"Timeouts: {timeout_count}", "WARN")
    if error_count:
        log(f"Errors: {error_count}", "ERR")

    log("", "INFO")
    log(f"{'Function':<28s} {'Status':<10s} {'Verdict':<12s} {'Score':<7s} {'Time':<8s}", "INFO")
    log("-" * 65, "INFO")

    for r in results:
        status_icon = {"ok": "[OK]", "timeout": "[TM]", "error": "[XX]", "no_attestation": "[NA]"}.get(r["status"], "[??]")
        verdict = r["verdict"] or "N/A"
        score = f"{r['score']:.2f}" if r["score"] else "N/A"
        dur = f"{r['duration_s']:.0f}s"
        log(f"{r['unit_name']+'()':<28s} {status_icon:<10s} {verdict:<12s} {score:<7s} {dur:<8s}", "INFO")

    log("", "INFO")
    log(f"Total duration: {total_time:.0f}s ({total_time/60:.1f} min)", "TIME")
    log(f"DB: {AUDIT_DB_PATH}", "INFO")

    # Save summary JSON
    summary_path = PROJECT_ROOT / "data" / f"benchmark_heavy_{timestamp}.json"
    summary = {
        "timestamp": timestamp,
        "models": working_models,
        "contract": CONTRACT_PATH,
        "db_path": AUDIT_DB_PATH,
        "timeout_per_unit": TIMEOUT_PER_UNIT,
        "total_duration_s": total_time,
        "results": results,
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    log(f"Summary saved: {summary_path.name}", "OK")
    log(f"Full path: {summary_path.resolve()}", "OK")


if __name__ == "__main__":
    asyncio.run(main())
