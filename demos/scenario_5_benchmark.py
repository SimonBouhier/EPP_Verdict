"""
Scenario 5 -- EPP Benchmark: Multi-claim evaluation across domains.

Evaluates 12 claims spanning 4 ambiguity tiers through the VERIFY pipeline.
Produces CSV + JSON results for analysis and pitch visualization.

Prerequisites:
    - Ollama running (ollama serve)
    - At least 2 models pulled
    - Scenario 4 working (VERIFY mode operational)

Expected duration: ~30 minutes (12 claims x ~2.5 min each)
"""

import asyncio
import csv
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger("benchmark")

# ---------------------------------------------------------------------------
# Claims catalog — 12 claims, 4 tiers of ambiguity
# ---------------------------------------------------------------------------

CLAIMS = [
    # TIER 1 — Baseline empirique (attendu: SUPPORTED, consensus > 80%)
    {
        "id": "T1-01",
        "claim": "The speed of light in vacuum exceeds 299000 kilometers per second",
        "domain": "physics",
        "expected_ambiguity": "low",
        "test_target": "Numeric comparative — auto-detection VERIFY + high consensus",
        "frame": "physics_constants_v1.0",
    },
    {
        "id": "T1-02",
        "claim": "Earth completes one orbit around the Sun in approximately 365 days",
        "domain": "astronomy",
        "expected_ambiguity": "low",
        "test_target": "Approximate numeric — tolerance handling ('approximately')",
        "frame": "astronomy_v1.0",
    },
    {
        "id": "T1-03",
        "claim": "Water boils at 100 degrees Celsius at standard atmospheric pressure",
        "domain": "chemistry",
        "expected_ambiguity": "low",
        "test_target": "Conditional fact — qualifier handling ('at standard pressure')",
        "frame": "chemistry_v1.0",
    },
    # TIER 2 — Mesurable avec nuance (attendu: SUPPORTED, consensus 55-75%)
    {
        "id": "T2-01",
        "claim": "Bitcoin annual energy consumption exceeds 100 terawatt-hours",
        "domain": "crypto_energy",
        "expected_ambiguity": "medium",
        "test_target": "Evolving metric — true in 2023, contested in 2025. Tests temporal awareness.",
        "frame": "energy_metrics_v1.0",
    },
    {
        "id": "T2-02",
        "claim": "More than 55 percent of the global population lives in urban areas",
        "domain": "demographics",
        "expected_ambiguity": "medium",
        "test_target": "Threshold claim — true per UN data, but depends on 'urban' definition.",
        "frame": "demographics_v1.0",
    },
    {
        "id": "T2-03",
        "claim": "Global average surface temperature has risen more than 1 degree Celsius since 1850",
        "domain": "climate",
        "expected_ambiguity": "medium",
        "test_target": "Scientific consensus with political controversy — tests source bias.",
        "frame": "climate_v1.0",
    },
    # TIER 3 — Ambiguïté définitionnelle (attendu: split SUPPORTED/CONTESTED)
    {
        "id": "T3-01",
        "claim": "Ethereum is more decentralized than Solana",
        "domain": "blockchain",
        "expected_ambiguity": "high",
        "test_target": "Crypto-native claim — subjective metric, audience-relevant pour Colosseum.",
        "frame": "blockchain_decentralization_v1.0",
    },
    {
        "id": "T3-02",
        "claim": "Large language models can understand natural language",
        "domain": "ai",
        "expected_ambiguity": "high",
        "test_target": "Definitional — 'understand' is the contested term. Meta-reflexive for an AI system.",
        "frame": "ai_capabilities_v1.0",
    },
    {
        "id": "T3-03",
        "claim": "Quantum entanglement enables faster than light communication",
        "domain": "quantum_physics",
        "expected_ambiguity": "high",
        "test_target": "Scientific misconception — entanglement is real, FTL communication is not.",
        "frame": "quantum_physics_v1.0",
    },
    # TIER 4 — Non-factuel / Infalsifiable (attendu: CONTESTED, consensus < 55%)
    {
        "id": "T4-01",
        "claim": "Free will is an illusion created by deterministic neural processes",
        "domain": "philosophy",
        "expected_ambiguity": "extreme",
        "test_target": "Unfalsifiable claim — tests if system defaults to CONTESTED or INSUFFICIENT_EVIDENCE.",
        "frame": "philosophy_v1.0",
    },
    {
        "id": "T4-02",
        "claim": "Democracy is the most effective form of government",
        "domain": "political_philosophy",
        "expected_ambiguity": "extreme",
        "test_target": "Normative claim — 'most effective' is undefined. Tests opinion vs fact boundary.",
        "frame": "political_science_v1.0",
    },
    {
        "id": "T4-03",
        "claim": "Pineapple is a valid pizza topping",
        "domain": "culinary_opinion",
        "expected_ambiguity": "extreme",
        "test_target": "Pure opinion — no factual basis.",
        "frame": "culinary_v1.0",
    },
]


# ---------------------------------------------------------------------------
# Ollama health check (reused pattern from scenario_4)
# ---------------------------------------------------------------------------


async def check_ollama() -> list[str]:
    """
    Health check Ollama. Returns list of available model names.
    Raises SystemExit with clear message if Ollama is unreachable.
    """
    import httpx

    base_url = "http://localhost:11434"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            return models
    except httpx.ConnectError:
        print("Ollama not running. Start with `ollama serve` then retry.")
        sys.exit(1)
    except Exception as e:
        print(f"Ollama health check failed: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Provider builder
# ---------------------------------------------------------------------------


def build_providers(selected_models: list[str]) -> dict:
    """Construct Ollama providers from selected model names."""
    from services.providers.ollama import OllamaProvider

    providers = {}
    for model_name in selected_models:
        pid = f"ollama-{model_name.replace(':', '_').replace('.', '_')}"
        providers[pid] = OllamaProvider(model=model_name)
    return providers


# ---------------------------------------------------------------------------
# Single claim runner
# ---------------------------------------------------------------------------


async def run_single_claim(
    claim_entry: dict,
    selected_models: list[str],
    claim_index: int,
    total_claims: int,
) -> tuple[dict, dict]:
    """
    Run the VERIFY pipeline for a single claim.
    Returns (csv_row, full_json_result).
    Fresh DB per call. Errors are caught, not propagated.
    """
    from database.engine import ISpaceDB
    from database.pool import close_pool
    from services.esmm.orchestrator import ESMMRunConfig
    from services.esmm.pipeline import PipelineConfig, run_pipeline

    # Test auto-detection without relying on it
    try:
        from services.esmm.question_seeder import InputType, classify_input
        auto_detected = classify_input(claim_entry["claim"]) == InputType.VERIFY
    except Exception:
        auto_detected = None

    claim_id = claim_entry["id"]
    claim_text = claim_entry["claim"]
    domain = claim_entry["domain"]

    # Real-time progress
    short_claim = claim_text[:60] + "..." if len(claim_text) > 60 else claim_text
    print(f'[{claim_index:02d}/{total_claims:02d}] {claim_id} | {domain} | "{short_claim}"')

    fd, db_path = tempfile.mkstemp(suffix=f"_bench_{claim_id}.db")
    os.close(fd)

    row = {
        "id": claim_id,
        "claim": claim_text,
        "domain": domain,
        "expected_ambiguity": claim_entry["expected_ambiguity"],
        "frame": claim_entry["frame"],
        "verdict": None,
        "dissent": None,
        "consensus_score": None,
        "dissent_score": None,
        "vote_entropy": None,
        "models_agreed": None,
        "models_total": len(selected_models),
        "triplets_extracted": 0,
        "triplets_attested": 0,
        "evidence_count": 0,
        "duration_s": 0.0,
        "auto_detected_verify": auto_detected,
        "errors": "",
    }

    full_result = {
        "id": claim_id,
        "claim": claim_text,
        "domain": domain,
        "expected_ambiguity": claim_entry["expected_ambiguity"],
        "consensus_meta": None,
        "attestations": [],
    }

    try:
        db = ISpaceDB(db_path)
        await db.initialize()

        providers = build_providers(selected_models)

        config = PipelineConfig(metrological_frame=claim_entry["frame"])

        # Force VERIFY mode — don't depend on classify_input()
        esmm_config = ESMMRunConfig(
            models=selected_models,
            input_mode="verify",
            original_claim=claim_text,
        )

        start = time.time()
        result = await run_pipeline(
            question=claim_text,
            db=db,
            config=config,
            providers=providers,
            models=selected_models,
            esmm_config=esmm_config,
        )
        elapsed = time.time() - start

        row["duration_s"] = round(elapsed, 1)
        row["triplets_extracted"] = result.triplets_extracted
        row["triplets_attested"] = result.triplets_attested

        if result.errors:
            row["errors"] = "; ".join(result.errors)

        # Extract verdict and dissent from attestations
        verdict_atts = [a for a in result.attestations if a.predicate == "verdict"]
        if verdict_atts:
            verdict_atts.sort(key=lambda a: a.consensus_score, reverse=True)
            best = verdict_atts[0]
            row["verdict"] = best.object
            row["consensus_score"] = round(best.consensus_score, 4)
            row["models_agreed"] = best.models_agreeing

            if len(verdict_atts) > 1:
                second = verdict_atts[1]
                row["dissent"] = second.object
                row["dissent_score"] = round(second.consensus_score, 4)

        # Extract consensus_meta
        if result.attestations and hasattr(result.attestations[0], "consensus_meta"):
            meta = result.attestations[0].consensus_meta
            if meta:
                full_result["consensus_meta"] = meta
                row["vote_entropy"] = meta.get("diagnostics", {}).get("vote_entropy")

                verify_section = meta.get("verify", {})
                if verify_section:
                    evidence = verify_section.get("evidence_corpus", [])
                    row["evidence_count"] = len(evidence)

        # Portable attestations for JSON archive
        for att in result.attestations:
            if hasattr(att, "to_portable_json"):
                full_result["attestations"].append(
                    json.loads(att.to_portable_json())
                )

        # Cleanup providers
        for provider in providers.values():
            if hasattr(provider, "close"):
                await provider.close()

    except Exception as e:
        row["errors"] = str(e)
        row["duration_s"] = 0.0
        logger.error("Claim %s failed: %s", claim_id, e)

    finally:
        try:
            await close_pool()
        except Exception:
            pass
        if os.path.exists(db_path):
            os.unlink(db_path)

    # Real-time result display
    v = row["verdict"] or "ERROR"
    cs = row["consensus_score"]
    ent = row["vote_entropy"]
    dur = row["duration_s"]
    if row["dissent"] and row["dissent_score"] is not None:
        print(
            f"        -> {v} ({cs:.0%}) <-> {row['dissent']} ({row['dissent_score']:.0%}) "
            f"| entropy={ent or 0:.2f} | {dur:.0f}s"
        )
    elif cs is not None:
        print(f"        -> {v} ({cs:.0%}) | entropy={ent or 0:.2f} | {dur:.0f}s")
    else:
        print(f"        -> ERROR: {row['errors'][:80]}")

    return row, full_result


# ---------------------------------------------------------------------------
# Main benchmark loop
# ---------------------------------------------------------------------------


async def main():
    print("=" * 60)
    print("EPP BENCHMARK -- 12 Claims x N Models")
    print("=" * 60)
    print()

    # Health check
    available = await check_ollama()

    # Filter out embedding models
    EMBEDDING_KEYWORDS = ["embed", "nomic", "mxbai"]
    selected = [
        m for m in available
        if not any(kw in m.lower() for kw in EMBEDDING_KEYWORDS)
    ]
    # Exclude slow/unstable models
    EXCLUDE = ["deepseek-r1", "gpt-oss"]
    selected = [
        m for m in selected
        if not any(ex in m.lower() for ex in EXCLUDE)
    ]

    if len(selected) < 2:
        print(f"Need at least 2 non-embedding models. Found: {available}")
        sys.exit(1)

    print(f"Models ({len(selected)}): {', '.join(selected)}")
    print()

    # Run identity
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).parent / "benchmark_runs"
    output_dir.mkdir(exist_ok=True)

    # Sequential benchmark
    csv_rows = []
    json_results = []
    total_start = time.time()

    for i, claim_entry in enumerate(CLAIMS, 1):
        row, full = await run_single_claim(claim_entry, selected, i, len(CLAIMS))
        csv_rows.append(row)
        json_results.append(full)

    total_elapsed = time.time() - total_start

    # --- Write CSV ---
    csv_path = output_dir / f"benchmark_results_{timestamp_str}.csv"
    fieldnames = [
        "id", "claim", "domain", "expected_ambiguity", "frame",
        "verdict", "dissent", "consensus_score", "dissent_score",
        "vote_entropy", "models_agreed", "models_total",
        "triplets_extracted", "triplets_attested", "evidence_count",
        "duration_s", "auto_detected_verify", "errors",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    # --- Write JSON ---
    json_path = output_dir / f"benchmark_results_{timestamp_str}.json"
    benchmark_json = {
        "benchmark_meta": {
            "run_id": timestamp_str,
            "run_label": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "models": selected,
            "model_count": len(selected),
            "total_duration_s": round(total_elapsed, 1),
            "claims_total": len(CLAIMS),
            "claims_completed": sum(1 for r in csv_rows if r["verdict"]),
            "claims_errored": sum(1 for r in csv_rows if r["errors"]),
        },
        "results": json_results,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_json, f, indent=2, default=str, ensure_ascii=False)

    # --- Console Summary ---
    print()
    print("=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    mins = int(total_elapsed // 60)
    secs = int(total_elapsed % 60)
    durations = [r["duration_s"] for r in csv_rows if r["duration_s"] > 0]
    avg_dur = sum(durations) / len(durations) if durations else 0
    print(f"  Duration: {mins}m {secs}s total | avg {avg_dur:.1f}s/claim")
    print()

    # Summary by tier
    tiers = {"T1": "baseline", "T2": "nuanced", "T3": "ambiguous", "T4": "opinion"}
    print("  +-----------------------------------------------------------+")
    for prefix, label in tiers.items():
        tier_rows = [r for r in csv_rows if r["id"].startswith(prefix)]
        supported = sum(1 for r in tier_rows if r["verdict"] == "SUPPORTED")
        contested = sum(1 for r in tier_rows if r["verdict"] in ("CONTESTED", "REFUTED"))
        splits = sum(1 for r in tier_rows if r["dissent"])
        scores = [r["consensus_score"] for r in tier_rows if r["consensus_score"]]
        avg_cs = sum(scores) / len(scores) if scores else 0
        total = len(tier_rows)
        print(
            f"  |  TIER {prefix[-1]} ({label:10s}): "
            f"{supported}S/{contested}C/{splits} split  "
            f"avg consensus {avg_cs:4.0%}  "
            f"({total} claims) |"
        )
    print("  +-----------------------------------------------------------+")

    # Consensus vs Ambiguity bar chart
    print()
    print("  Consensus vs Ambiguity:")
    for level in ["low", "medium", "high", "extreme"]:
        level_rows = [
            r for r in csv_rows
            if r["expected_ambiguity"] == level and r["consensus_score"]
        ]
        if level_rows:
            avg = sum(r["consensus_score"] for r in level_rows) / len(level_rows)
            bar_len = int(avg * 20)
            bar = "\u2588" * bar_len + "\u2591" * (20 - bar_len)
            print(f"    {level:8s}: {bar}  {avg:.0%}")

    # --- Write latest.txt pointer ---
    latest_path = output_dir / "latest.txt"
    latest_path.write_text(timestamp_str, encoding="utf-8")

    print()
    print("  Results saved:")
    print(f"    CSV:  {csv_path}")
    print(f"    JSON: {json_path}")
    print(f"    Latest: {latest_path} -> {timestamp_str}")
    print()
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
