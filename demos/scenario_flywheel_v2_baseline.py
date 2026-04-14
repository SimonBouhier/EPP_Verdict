"""
Scenario Flywheel v2 Baseline — LLM-only scores without flywheel injection
============================================================================

Runs the same claims as scenario_flywheel_v2.py but in VERIFY-only mode:
no PASS 1 deterministic, no flywheel anchor injection. Measures raw LLM
scores so we can compute deltas against the flywheel-enhanced run.

Usage:
    python demos/scenario_flywheel_v2_baseline.py

Output: demos/benchmark_runs/flywheel_v2_baseline_{timestamp}.json
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger("scenario_flywheel_v2_baseline")

# ---------------------------------------------------------------------------
# Claims — flywheel targets only (no controls that already have baselines)
# ---------------------------------------------------------------------------

CLAIMS = [
    {
        "id": "FW2-01",
        "claim": "Donald Trump won the 2024 US presidential election",
        "frame": "general_knowledge_v1.0",
        "expected_verdict": "SUPPORTED",
    },
    {
        "id": "FW2-02",
        "claim": "Keir Starmer is the current Prime Minister of the United Kingdom",
        "frame": "general_knowledge_v1.0",
        "expected_verdict": "SUPPORTED",
    },
    {
        "id": "FW2-03",
        "claim": "Claudia Sheinbaum is the current President of Mexico",
        "frame": "general_knowledge_v1.0",
        "expected_verdict": "SUPPORTED",
    },
    {
        "id": "FW2-05",
        "claim": "The 2024 Nobel Prize in Physics was awarded to John Hopfield and Geoffrey Hinton",
        "frame": "general_knowledge_v1.0",
        "expected_verdict": "SUPPORTED",
    },
]


# ---------------------------------------------------------------------------
# Infra (reused from scenario_flywheel_v2.py)
# ---------------------------------------------------------------------------

async def check_ollama() -> list[str]:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception as e:
        print(f"  x Ollama unavailable: {e}")
        sys.exit(1)


def select_models(available: list[str], max_models: int = 3) -> list[str]:
    EMBEDDING = ["embed", "nomic", "mxbai"]
    EXCLUDE = ["gpt-oss", "deepseek-r1", "llama4", "phi4-reasoning"]
    selected = [
        m for m in available
        if not any(k in m.lower() for k in EMBEDDING)
        and not any(e in m.lower() for e in EXCLUDE)
    ]
    PREFERRED = ["mistral", "llama3.1:8b", "gemma3", "granite3.3"]
    ordered = sorted(selected, key=lambda m: next(
        (i for i, p in enumerate(PREFERRED) if p in m), 99
    ))
    return ordered[:max_models]


def build_providers(selected_models: list[str]) -> dict:
    from services.providers.ollama import OllamaProvider
    return {
        f"ollama-{m.replace(':', '_').replace('.', '_')}": OllamaProvider(model=m)
        for m in selected_models
    }


# ---------------------------------------------------------------------------
# Core: run a single claim in VERIFY-only mode (no flywheel)
# ---------------------------------------------------------------------------

async def run_baseline_claim(entry: dict, selected: list[str], idx: int, total: int) -> dict:
    from database.engine import ISpaceDB
    from database.pool import close_pool
    from services.esmm.orchestrator import ESMMRunConfig
    from services.esmm.pipeline import PipelineConfig, run_pipeline

    cid = entry["id"]
    claim = entry["claim"]
    short = claim[:60] + "..." if len(claim) > 60 else claim
    print(f"\n  [{idx:02d}/{total:02d}] {cid}")
    print(f'           "{short}"')

    fd, db_path = tempfile.mkstemp(suffix=f"_baseline_{cid}.db")
    os.close(fd)

    row = {
        "id": cid,
        "claim": claim,
        "verify_verdict": None,
        "verify_score": None,
        "vote_entropy": None,
        "claim_type": None,
        "errors": "",
        "duration_s": 0.0,
    }

    try:
        db = ISpaceDB(db_path=db_path)
        await db.initialize()
        providers = build_providers(selected)

        config = PipelineConfig(
            metrological_frame=entry.get("frame"),
            use_cache=False,
        )
        esmm_config = ESMMRunConfig(
            models=selected,
            input_mode="verify",
            original_claim=claim,
        )

        start = time.time()
        result = await run_pipeline(
            question=claim,
            db=db,
            config=config,
            providers=providers,
            models=selected,
            esmm_config=esmm_config,
        )
        elapsed = time.time() - start
        row["duration_s"] = round(elapsed, 1)

        if result.errors:
            row["errors"] = "; ".join(result.errors)

        # Extract verdict
        verdict_atts = sorted(
            [a for a in result.attestations if a.predicate == "verdict"],
            key=lambda a: a.consensus_score, reverse=True,
        )
        if verdict_atts:
            best = verdict_atts[0]
            row["verify_verdict"] = best.object
            row["verify_score"] = round(best.consensus_score, 4)

        # Extract metadata
        if result.attestations:
            meta = getattr(result.attestations[0], "consensus_meta", {}) or {}
            if isinstance(meta, str):
                import json as _json
                meta = _json.loads(meta)
            diag = meta.get("diagnostics", {})
            row["vote_entropy"] = diag.get("vote_entropy")
            verify_meta = meta.get("verify", {})
            row["claim_type"] = verify_meta.get("claim_type")

        v = row["verify_verdict"] or "ERR"
        cs = row["verify_score"] or 0.0
        ent = row["vote_entropy"] or 0.0
        ct = row["claim_type"] or "?"
        print(f"           {v} ({cs:.0%}) | entropy={ent:.2f} | type={ct} | {elapsed:.0f}s")

        for p in providers.values():
            if hasattr(p, "close"):
                await p.close()

    except Exception as e:
        row["errors"] = str(e)
        print(f"           -> ERROR: {str(e)[:80]}")
    finally:
        try:
            await close_pool()
        except Exception:
            pass
        if os.path.exists(db_path):
            os.unlink(db_path)

    return row


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print("=" * 70)
    print("EPP SCENARIO FLYWHEEL v2 BASELINE — LLM-only (no flywheel)")
    print("VERIFY-only, no DETERMINISTIC pass, no anchor injection")
    print("=" * 70)

    available = await check_ollama()
    selected = select_models(available, max_models=3)

    if len(selected) < 2:
        print(f"  x Minimum 2 models required. Available: {available}")
        sys.exit(1)

    print(f"\n  Models ({len(selected)}): {', '.join(selected)}")
    print(f"  Claims ({len(CLAIMS)}): {', '.join(c['id'] for c in CLAIMS)}")
    print(f"  Flywheel: DISABLED (baseline measurement)")
    print()

    results = []
    for i, entry in enumerate(CLAIMS, 1):
        row = await run_baseline_claim(entry, selected, i, len(CLAIMS))
        results.append(row)

    # --- Summary ---
    total_s = sum(r["duration_s"] for r in results)
    print("\n" + "=" * 70)
    print("BASELINE RESULTS")
    print("=" * 70)

    print(f"\n  {'ID':<16} {'Verdict':>12} {'Score':>7} {'Type':<16}")
    print(f"  {'-'*16} {'-'*12} {'-'*7} {'-'*16}")

    for r in results:
        v = r["verify_verdict"] or "ERR"
        cs = r["verify_score"] or 0.0
        ct = r["claim_type"] or "?"
        print(f"  {r['id']:<16} {v:>12} {cs:>6.0%} {ct:<16}")

    mins = int(total_s // 60)
    secs = int(total_s % 60)
    print(f"\n  Total duration: {mins}m {secs}s")
    print("=" * 70)

    # JSON output
    out_dir = Path(__file__).parent / "benchmark_runs"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"flywheel_v2_baseline_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "scenario": "flywheel_v2_baseline",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "models": selected,
            "flywheel_enabled": False,
            "claims": results,
        }, f, indent=2, default=str, ensure_ascii=False)

    print(f"\n  Report: {json_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
