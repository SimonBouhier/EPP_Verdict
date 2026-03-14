"""
Scenario Flywheel — ADR-018 Epistemic Flywheel Demonstration
=============================================================

Demonstrates the Epistemic Flywheel: deterministic source attestations
(Wikidata, ACLED) stored in the local graph are automatically injected
into the LLM system prompt during subsequent VERIFY passes.

The flywheel effect: same models, same claim, smarter graph → better verdict.

Structure per claim:
  Pass 1 — DETERMINISTIC (stores anchor in DB with question=question)
  Pass 2 — VERIFY with flywheel enabled (finds anchor, injects into LLM context)

Control claims (no deterministic source) verify flywheel does NOT activate.

Usage:
    python demos/scenario_flywheel.py
    ACLED_EMAIL=... ACLED_PASSWORD=... python demos/scenario_flywheel.py

Depends on: ADR-018 (flywheel), ADR-012 (deterministic path), ADR-013 (cache)
Preserves: scenario_jiang.py and all existing benchmark_runs/ data untouched.
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

logger = logging.getLogger("scenario_flywheel")

# ---------------------------------------------------------------------------
# Claims catalog — subset chosen to demonstrate flywheel delta
# ---------------------------------------------------------------------------

CLAIMS = [
    {
        "id": "FLYWHEEL-01",
        "origin": "JIANG-RESOLVED-01",
        "category": "flywheel_wikidata",
        "claim": "Donald Trump won the 2024 US presidential election",
        "frame": "general_knowledge_v1.0",
        "expected_verdict": "SUPPORTED",
        "baseline_verify_score": 0.43,
        "baseline_verify_verdict": "CONTESTED",
        "deterministic_source": "wikidata",
        "deterministic_query": {
            "sparql": 'SELECT ?winnerLabel WHERE { wd:Q101110072 wdt:P991 ?winner . SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . } } LIMIT 5'
        },
        "acled_query": None,
    },
    {
        "id": "FLYWHEEL-02",
        "origin": "GEO-CONTROL-01",
        "category": "flywheel_acled",
        "claim": "Yemen is experiencing active armed conflict in 2025 as documented in conflict event databases",
        "frame": "geopolitical_forecast_v1.0",
        "expected_verdict": "SUPPORTED",
        "baseline_verify_score": 0.97,
        "baseline_verify_verdict": "SUPPORTED",
        "deterministic_source": "acled",
        "deterministic_query": None,
        "acled_query": {"country": "Yemen", "baseline": 500, "mode": "events"},
    },
    {
        "id": "FLYWHEEL-CONTROL-01",
        "origin": "GEO-CONTROL-02",
        "category": "control_no_flywheel",
        "claim": "Switzerland is experiencing active armed conflict on its sovereign territory in 2025",
        "frame": "geopolitical_forecast_v1.0",
        "expected_verdict": "CONTESTED",
        "baseline_verify_score": 0.61,
        "baseline_verify_verdict": "CONTESTED",
        "deterministic_source": None,
        "deterministic_query": None,
        "acled_query": None,
    },
]


# ---------------------------------------------------------------------------
# Infra (pattern from scenario_jiang.py — unchanged)
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
# Core: run a single claim through the flywheel protocol
# ---------------------------------------------------------------------------

async def run_flywheel_claim(entry: dict, selected: list[str], idx: int, total: int) -> dict:
    from database.engine import ISpaceDB
    from database.pool import close_pool
    from services.esmm.orchestrator import ESMMRunConfig, ClaimNature
    from services.esmm.pipeline import PipelineConfig, run_pipeline
    from services.esmm.source_anchor_builder import SourceAnchorSpec

    cid = entry["id"]
    claim = entry["claim"]
    short = claim[:52] + "..." if len(claim) > 52 else claim
    cat = entry.get("category", "")
    print(f"\n  [{idx:02d}/{total:02d}] {cid} [{cat}]")
    print(f"           \"{short}\"")

    fd, db_path = tempfile.mkstemp(suffix=f"_flywheel_{cid}.db")
    os.close(fd)

    row = {
        "id": cid,
        "origin": entry.get("origin"),
        "category": cat,
        "claim": claim,
        "frame": entry.get("frame"),
        # Deterministic pass
        "deterministic_source": entry.get("deterministic_source"),
        "deterministic_score": None,
        "deterministic_status": None,
        "deterministic_errors": "",
        "deterministic_duration_s": 0.0,
        # VERIFY pass (with flywheel)
        "verify_verdict": None,
        "verify_score": None,
        "vote_entropy": None,
        "claim_type": None,
        "verify_errors": "",
        "verify_duration_s": 0.0,
        # Flywheel metadata
        "flywheel_anchors_found": 0,
        "flywheel_sources_injected": [],
        "flywheel_enabled": False,
        # Delta
        "baseline_verify_score": entry.get("baseline_verify_score"),
        "baseline_verify_verdict": entry.get("baseline_verify_verdict"),
        "delta": None,
        "expected_verdict": entry.get("expected_verdict"),
        "verdict_ok": None,
        # Totals
        "models": selected,
        "duration_s": 0.0,
    }

    try:
        db = ISpaceDB(db_path)
        await db.initialize()
        providers = build_providers(selected)

        # ===============================================================
        # PASS 1 — DETERMINISTIC (store anchor in DB)
        # ===============================================================
        det_source = entry.get("deterministic_source")
        has_deterministic = False

        # --- Wikidata path ---
        wiki_q = entry.get("deterministic_query")
        if det_source == "wikidata" and wiki_q:
            print(f"           [PASS 1] DETERMINISTIC Wikidata...")
            try:
                spec_wiki = SourceAnchorSpec(
                    source_id="wikidata",
                    frame_id=entry["frame"],
                    query=wiki_q,
                )
                esmm_det = ESMMRunConfig(
                    models=[],
                    claim_nature=ClaimNature.DETERMINISTIC,
                    source_anchor_spec=spec_wiki,
                )
                start_det = time.time()
                result_det = await run_pipeline(
                    question=claim,
                    db=db,
                    config=PipelineConfig(use_cache=False),
                    providers=providers,
                    models=selected,
                    esmm_config=esmm_det,
                )
                elapsed_det = time.time() - start_det
                row["deterministic_duration_s"] = round(elapsed_det, 1)
                row["duration_s"] += elapsed_det

                if result_det and result_det.attestations:
                    row["deterministic_status"] = "found"
                    row["deterministic_score"] = result_det.attestations[0].consensus_score
                    has_deterministic = True
                    print(
                        f"           [PASS 1] OK: status=found"
                        f" score={row['deterministic_score']}"
                        f" | {elapsed_det:.0f}s"
                    )
                else:
                    row["deterministic_status"] = "not_found"
                    row["deterministic_score"] = 0.0
                    errs = result_det.errors if result_det else ["no result"]
                    row["deterministic_errors"] = "; ".join(str(e) for e in errs)
                    print(f"           [PASS 1] NOT FOUND | errors={row['deterministic_errors'][:60]}")

            except Exception as e:
                row["deterministic_errors"] = str(e)
                print(f"           [PASS 1] ERROR: {str(e)[:80]}")

        # --- ACLED path ---
        elif det_source == "acled" and entry.get("acled_query"):
            acled_available = bool(os.getenv("ACLED_EMAIL"))
            if acled_available:
                acled_q = entry["acled_query"]
                query_mode = acled_q.get("mode", "events")
                source_id = f"acled_{query_mode}"
                print(f"           [PASS 1] DETERMINISTIC ACLED ({source_id})...")
                try:
                    spec_acled = SourceAnchorSpec(
                        source_id=source_id,
                        frame_id=entry["frame"],
                        query=acled_q,
                    )
                    esmm_det = ESMMRunConfig(
                        models=[],
                        claim_nature=ClaimNature.DETERMINISTIC,
                        source_anchor_spec=spec_acled,
                    )
                    start_det = time.time()
                    result_det = await run_pipeline(
                        question=claim,
                        db=db,
                        config=PipelineConfig(use_cache=False),
                        providers=providers,
                        models=selected,
                        esmm_config=esmm_det,
                    )
                    elapsed_det = time.time() - start_det
                    row["deterministic_duration_s"] = round(elapsed_det, 1)
                    row["duration_s"] += elapsed_det

                    if result_det and result_det.attestations:
                        att = result_det.attestations[0]
                        row["deterministic_status"] = att.object
                        row["deterministic_score"] = att.consensus_score
                        has_deterministic = True
                        print(
                            f"           [PASS 1] OK: status={att.object}"
                            f" score={att.consensus_score}"
                            f" | {elapsed_det:.0f}s"
                        )
                    else:
                        row["deterministic_status"] = "no_attestation"
                        errs = result_det.errors if result_det else ["no result"]
                        row["deterministic_errors"] = "; ".join(str(e) for e in errs)
                        print(f"           [PASS 1] NO ATTESTATION | {row['deterministic_errors'][:60]}")

                except Exception as e:
                    row["deterministic_errors"] = str(e)
                    print(f"           [PASS 1] ERROR: {str(e)[:80]}")
            else:
                print("           [PASS 1] ACLED credentials absent -- skipped")
                row["deterministic_status"] = "skipped_no_credentials"

        # --- No deterministic source (control claim) ---
        elif det_source is None:
            print("           [PASS 1] No deterministic source (control claim)")
            row["deterministic_status"] = "control_no_source"

        else:
            print(f"           [PASS 1] Unknown source type: {det_source}")
            row["deterministic_status"] = f"unknown_{det_source}"

        # ===============================================================
        # PASS 2 — VERIFY with flywheel (finds anchor from Pass 1)
        # ===============================================================
        expected_anchors = 1 if has_deterministic else 0
        print(
            f"           [PASS 2] VERIFY epistemique"
            f" (flywheel expects {expected_anchors} anchor(s))..."
        )

        config_verify = PipelineConfig(
            metrological_frame=entry["frame"],
            use_cache=False,
        )
        esmm_verify = ESMMRunConfig(
            models=selected,
            input_mode="verify",
            original_claim=claim,
        )

        start_verify = time.time()
        result_verify = await run_pipeline(
            question=claim,
            db=db,
            config=config_verify,
            providers=providers,
            models=selected,
            esmm_config=esmm_verify,
        )
        elapsed_verify = time.time() - start_verify
        row["verify_duration_s"] = round(elapsed_verify, 1)
        row["duration_s"] = round(row["duration_s"] + elapsed_verify, 1)

        if result_verify.errors:
            row["verify_errors"] = "; ".join(result_verify.errors)

        # Extract VERIFY verdict
        verdict_atts = sorted(
            [a for a in result_verify.attestations if a.predicate == "verdict"],
            key=lambda a: a.consensus_score, reverse=True,
        )
        if verdict_atts:
            best = verdict_atts[0]
            row["verify_verdict"] = best.object
            row["verify_score"] = round(best.consensus_score, 4)

        # Extract flywheel metadata from consensus_meta
        if result_verify.attestations:
            meta = getattr(result_verify.attestations[0], "consensus_meta", {}) or {}
            diag = meta.get("diagnostics", {})
            row["vote_entropy"] = diag.get("vote_entropy")

            verify_meta = meta.get("verify", {})
            row["claim_type"] = verify_meta.get("claim_type")

            # Flywheel traceability (ADR-018)
            flywheel_meta = meta.get("methodology", {}).get("flywheel", {})
            row["flywheel_anchors_found"] = flywheel_meta.get("anchors_found", 0)
            row["flywheel_sources_injected"] = flywheel_meta.get("sources_injected", [])
            row["flywheel_enabled"] = flywheel_meta.get("enabled", False)

        # Compute delta vs baseline
        if row["verify_score"] is not None and row["baseline_verify_score"] is not None:
            delta = round(row["verify_score"] - row["baseline_verify_score"], 4)
            row["delta"] = delta

        # Validate expected verdict
        if row["expected_verdict"] and row["verify_verdict"]:
            row["verdict_ok"] = row["verify_verdict"] == row["expected_verdict"]

        # Display
        v = row["verify_verdict"] or "ERR"
        cs = row["verify_score"] or 0.0
        ent = row["vote_entropy"] or 0.0
        fw = row["flywheel_anchors_found"]
        delta_str = f"{row['delta']:+.4f}" if row["delta"] is not None else "n/a"
        baseline = row["baseline_verify_score"] or 0.0
        v_icon = ""
        if row["verdict_ok"] is True:
            v_icon = " OK"
        elif row["verdict_ok"] is False:
            v_icon = " MISS"

        print(
            f"           [PASS 2] {v}{v_icon} ({cs:.0%})"
            f" | entropy={ent:.2f}"
            f" | flywheel={fw} anchor(s)"
            f" | baseline={baseline:.0%} delta={delta_str}"
            f" | {elapsed_verify:.0f}s"
        )

        # Cleanup providers
        for p in providers.values():
            if hasattr(p, "close"):
                await p.close()

    except Exception as e:
        row["verify_errors"] = str(e)
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
    print("EPP SCENARIO FLYWHEEL — ADR-018 Epistemic Flywheel Demonstration")
    print("DETERMINISTIC first, then VERIFY with flywheel injection")
    print("=" * 70)

    acled_active = bool(os.getenv("ACLED_EMAIL"))
    print(f"\n  ACLED credentials: {'YES' if acled_active else 'NO (ACLED claims will skip Pass 1)'}")

    available = await check_ollama()
    selected = select_models(available, max_models=3)

    if len(selected) < 2:
        print(f"  x Minimum 2 models required. Available: {available}")
        sys.exit(1)

    print(f"  Models ({len(selected)}): {', '.join(selected)}")
    print(f"  Claims ({len(CLAIMS)}): {', '.join(c['id'] for c in CLAIMS)}")
    print(f"  Flywheel: enabled (ADR-018)")
    print()

    results = []
    for i, entry in enumerate(CLAIMS, 1):
        row = await run_flywheel_claim(entry, selected, i, len(CLAIMS))
        results.append(row)

    # --- Summary ---
    total_s = sum(r["duration_s"] for r in results)
    print("\n" + "=" * 70)
    print("FLYWHEEL RESULTS")
    print("=" * 70)

    for r in results:
        v = r["verify_verdict"] or "ERR"
        cs = r["verify_score"] or 0.0
        bl = r["baseline_verify_score"] or 0.0
        delta = r["delta"]
        delta_str = f"{delta:+.4f}" if delta is not None else "  n/a"
        fw = r["flywheel_anchors_found"]
        src = ", ".join(r["flywheel_sources_injected"]) or "none"
        det = r["deterministic_status"] or "n/a"

        v_icon = "OK  " if r["verdict_ok"] is True else ("MISS" if r["verdict_ok"] is False else "    ")

        print(
            f"  {v_icon} {r['id']}"
            f"  {v:>24s} ({cs:.0%})"
            f"  baseline={bl:.0%}"
            f"  delta={delta_str}"
            f"  flywheel={fw}({src})"
            f"  det={det}"
        )

    # Flywheel effectiveness
    fw_claims = [r for r in results if r["flywheel_anchors_found"] > 0]
    ctrl_claims = [r for r in results if r["flywheel_anchors_found"] == 0]

    if fw_claims:
        avg_delta = sum(r["delta"] for r in fw_claims if r["delta"] is not None) / len(fw_claims)
        print(f"\n  Flywheel claims ({len(fw_claims)}): avg delta = {avg_delta:+.4f}")
    if ctrl_claims:
        avg_delta_ctrl = sum(
            r["delta"] for r in ctrl_claims if r["delta"] is not None
        ) / max(len([r for r in ctrl_claims if r["delta"] is not None]), 1)
        print(f"  Control claims  ({len(ctrl_claims)}): avg delta = {avg_delta_ctrl:+.4f}")

    mins = int(total_s // 60)
    secs = int(total_s % 60)
    print(f"\n  Total duration: {mins}m {secs}s")
    print("=" * 70)

    # JSON output
    out_dir = Path(__file__).parent / "benchmark_runs"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"flywheel_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "scenario": "scenario_flywheel",
            "adr": "ADR-018",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "models": selected,
            "acled_enabled": acled_active,
            "flywheel_enabled": True,
            "claims": results,
        }, f, indent=2, default=str, ensure_ascii=False)

    print(f"\n  Report: {json_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
