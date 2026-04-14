"""
Scenario Flywheel v2 — Expanded Epistemic Flywheel Demonstration
=================================================================

Extends scenario_flywheel.py with additional post-training-cutoff claims
verifiable via Wikidata SPARQL. Demonstrates cumulative flywheel effect
across multiple domains: elections, Nobel prizes, geopolitics.

The core insight: 7-8B Ollama models (training cutoff ~mid-2024) cannot
know about events from late 2024 onwards. Wikidata does. The flywheel
injects verified facts into the LLM context, correcting their blindness.

Structure per claim:
  Pass 1 — DETERMINISTIC (Wikidata SPARQL → stores anchor in DB)
  Pass 2 — VERIFY with flywheel enabled (finds anchor, injects into LLM)

Control claims (well-known facts) verify baseline behavior.

Usage:
    python demos/scenario_flywheel_v2.py

Depends on: ADR-018 (flywheel), ADR-012 (deterministic path), ADR-013 (cache)
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

logger = logging.getLogger("scenario_flywheel_v2")

# ---------------------------------------------------------------------------
# Claims catalog — post-training-cutoff events + controls
# ---------------------------------------------------------------------------
# SPARQL VALIDATION REQUIRED: before running, test each query manually at
# https://query.wikidata.org/ — QIDs and properties may need adjustment.
#
# Baseline scores are estimated from the Trump baseline pattern (0.43 for
# unknown-to-model facts). First run will establish actual baselines.
# ---------------------------------------------------------------------------

CLAIMS = [
    # =======================================================================
    # TIER 1 — Post-cutoff elections (strong delta expected, ~0.3-0.5)
    # =======================================================================
    {
        "id": "FW2-01",
        "origin": "FLYWHEEL-01",
        "category": "flywheel_wikidata",
        "claim": "Donald Trump won the 2024 US presidential election",
        "frame": "general_knowledge_v1.0",
        "expected_verdict": "SUPPORTED",
        "baseline_verify_score": 0.43,
        "baseline_verify_verdict": "CONTESTED",
        "deterministic_source": "wikidata",
        "deterministic_query": {
            "sparql": (
                'SELECT ?winnerLabel WHERE { '
                'wd:Q101110072 wdt:P991 ?winner . '
                'SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . } '
                '} LIMIT 5'
            ),
        },
        "acled_query": None,
    },
    {
        "id": "FW2-02",
        "origin": "new",
        "category": "flywheel_wikidata",
        "claim": "Keir Starmer is the current Prime Minister of the United Kingdom",
        "frame": "general_knowledge_v1.0",
        "expected_verdict": "SUPPORTED",
        # Baseline 2026-04-11: models still think Sunak is PM (cutoff pre-July 2024)
        "baseline_verify_score": 0.481,
        "baseline_verify_verdict": "CONTESTED",
        "deterministic_source": "wikidata",
        "deterministic_query": {
            # Q264766 = Keir Starmer, P39 = position held
            # Should return "Prime Minister of the United Kingdom"
            "sparql": (
                'SELECT ?posLabel ?startDate WHERE { '
                'wd:Q264766 p:P39 ?stmt . '
                '?stmt ps:P39 ?pos . '
                'OPTIONAL { ?stmt pq:P580 ?startDate . } '
                'SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . } '
                '} LIMIT 10'
            ),
        },
        "acled_query": None,
    },
    {
        "id": "FW2-03",
        "origin": "new",
        "category": "flywheel_wikidata",
        "claim": "Claudia Sheinbaum is the current President of Mexico",
        "frame": "general_knowledge_v1.0",
        "expected_verdict": "SUPPORTED",
        # Baseline 2026-04-11: models still think AMLO is president (cutoff pre-Oct 2024)
        "baseline_verify_score": 0.78,
        "baseline_verify_verdict": "SUPPORTED",
        "deterministic_source": "wikidata",
        "deterministic_query": {
            # Q862580 = Claudia Sheinbaum, P39 = position held
            "sparql": (
                'SELECT ?posLabel ?startDate WHERE { '
                'wd:Q862580 p:P39 ?stmt . '
                '?stmt ps:P39 ?pos . '
                'OPTIONAL { ?stmt pq:P580 ?startDate . } '
                'SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . } '
                '} LIMIT 10'
            ),
        },
        "acled_query": None,
    },
    {
        "id": "FW2-04",
        "origin": "new",
        "category": "flywheel_wikidata",
        "claim": "Prabowo Subianto is the current President of Indonesia",
        "frame": "general_knowledge_v1.0",
        "expected_verdict": "SUPPORTED",
        # Models likely still think Jokowi is president (cutoff pre-Oct 2024)
        "baseline_verify_score": None,
        "baseline_verify_verdict": None,
        "deterministic_source": "wikidata",
        "deterministic_query": {
            # Q313868 = Prabowo Subianto, P39 = position held
            "sparql": (
                'SELECT ?posLabel ?startDate WHERE { '
                'wd:Q313868 p:P39 ?stmt . '
                '?stmt ps:P39 ?pos . '
                'OPTIONAL { ?stmt pq:P580 ?startDate . } '
                'SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . } '
                '} LIMIT 10'
            ),
        },
        "acled_query": None,
    },

    # =======================================================================
    # TIER 2 — Post-cutoff science/events (moderate delta expected, ~0.2-0.4)
    # =======================================================================
    {
        "id": "FW2-05",
        "origin": "new",
        "category": "flywheel_wikidata",
        "claim": "The 2024 Nobel Prize in Physics was awarded to John Hopfield and Geoffrey Hinton",
        "frame": "general_knowledge_v1.0",
        "expected_verdict": "SUPPORTED",
        "baseline_verify_score": 0.77,
        "baseline_verify_verdict": "SUPPORTED",
        "deterministic_source": "wikidata",
        "deterministic_query": {
            # Q5765 = Nobel Prize in Physics, look for 2024 laureates
            # P166 = award received, qualify by P585 = point in time
            "sparql": (
                'SELECT ?laureateLabel WHERE { '
                '?laureate wdt:P166 wd:Q38104 . '  # Q38104 = Nobel Prize in Physics
                '?laureate p:P166 ?stmt . '
                '?stmt ps:P166 wd:Q38104 . '
                '?stmt pq:P585 ?date . '
                'FILTER(YEAR(?date) = 2024) '
                'SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . } '
                '} LIMIT 10'
            ),
        },
        "acled_query": None,
    },
    {
        "id": "FW2-06",
        "origin": "new",
        "category": "flywheel_wikidata",
        "claim": "South Korea declared martial law in December 2024",
        "frame": "general_knowledge_v1.0",
        "expected_verdict": "SUPPORTED",
        "baseline_verify_score": None,
        "baseline_verify_verdict": None,
        "deterministic_source": "wikidata",
        "deterministic_query": {
            # Q131454927 = 2024 South Korean martial law crisis (if it exists)
            # Fallback: search by label
            "sparql": (
                'SELECT ?item ?itemLabel ?date WHERE { '
                '?item rdfs:label "2024 South Korean martial law"@en . '
                'OPTIONAL { ?item wdt:P585 ?date . } '
                'SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . } '
                '} LIMIT 5'
            ),
        },
        "acled_query": None,
    },

    # =======================================================================
    # TIER 3 — Controls (no flywheel effect expected, models already know)
    # =======================================================================
    {
        "id": "FW2-CTRL-01",
        "origin": "control",
        "category": "control_known_fact",
        "claim": "Joe Biden served as the 46th President of the United States",
        "frame": "general_knowledge_v1.0",
        "expected_verdict": "SUPPORTED",
        "baseline_verify_score": 0.90,  # models know this well
        "baseline_verify_verdict": "SUPPORTED",
        "deterministic_source": "wikidata",
        "deterministic_query": {
            # Q6279 = Joe Biden, P39 = position held
            "sparql": (
                'SELECT ?posLabel ?ordinal WHERE { '
                'wd:Q6279 p:P39 ?stmt . '
                '?stmt ps:P39 ?pos . '
                'OPTIONAL { ?stmt pq:P1545 ?ordinal . } '
                'SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . } '
                '} LIMIT 10'
            ),
        },
        "acled_query": None,
    },
]


# ---------------------------------------------------------------------------
# Infra (identical to scenario_flywheel.py)
# ---------------------------------------------------------------------------

async def check_ollama() -> list[str]:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception as e:
        print(f"  ✗ Ollama unavailable: {e}")
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
    short = claim[:60] + "..." if len(claim) > 60 else claim
    cat = entry.get("category", "")
    print(f"\n  [{idx:02d}/{total:02d}] {cid} [{cat}]")
    print(f'           "{short}"')

    fd, db_path = tempfile.mkstemp(suffix=f"_fw2_{cid}.db")
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
        # === Initialize DB ===
        db = ISpaceDB(db_path=db_path)
        await db.initialize()
        providers = build_providers(selected)

        # =================================================================
        # PASS 1 — DETERMINISTIC (store anchor in DB for flywheel)
        # =================================================================
        det_source = entry.get("deterministic_source")
        det_query = entry.get("deterministic_query")
        acled_query = entry.get("acled_query")

        if det_source and (det_query or acled_query):
            source_key = det_source
            query_dict = det_query or acled_query

            if det_source == "acled":
                source_key = f"acled_{acled_query.get('mode', 'events')}"
                query_dict = acled_query
                print(f"           [PASS 1] DETERMINISTIC ACLED ({source_key})...")
            else:
                print(f"           [PASS 1] DETERMINISTIC Wikidata...")

            spec = SourceAnchorSpec(
                source_id=source_key,
                frame_id=entry.get("frame", "general_knowledge_v1.0"),
                query=query_dict,
            )
            config_det = PipelineConfig(
                metrological_frame=entry.get("frame"),
                use_cache=False,
            )
            esmm_det = ESMMRunConfig(
                models=[],
                claim_nature=ClaimNature.DETERMINISTIC,
                source_anchor_spec=spec,
            )

            start_det = time.time()
            result_det = await run_pipeline(
                question=claim,
                db=db,
                config=config_det,
                providers=providers,
                models=selected,
                esmm_config=esmm_det,
            )
            elapsed_det = time.time() - start_det
            row["deterministic_duration_s"] = round(elapsed_det, 1)
            row["duration_s"] += elapsed_det

            if result_det.errors:
                row["deterministic_errors"] = "; ".join(result_det.errors)

            if result_det.attestations:
                att = result_det.attestations[0]
                meta = getattr(att, "consensus_meta", {}) or {}
                if isinstance(meta, str):
                    import json as _json
                    meta = _json.loads(meta)
                diag = meta.get("diagnostics", {})
                # diagnostics.result is a string status (e.g. "found"), not a dict
                row["deterministic_status"] = diag.get("result", "found")
                row["deterministic_score"] = att.consensus_score
                print(
                    f"           [PASS 1] OK: status={row['deterministic_status']}"
                    f" score={row['deterministic_score']}"
                    f" | {elapsed_det:.0f}s"
                )
            else:
                status = "no_attestation"
                if result_det.errors:
                    status = result_det.errors[0][:60]
                row["deterministic_status"] = status
                print(f"           [PASS 1] NO ATTESTATION | {status}")
        else:
            row["deterministic_status"] = "control_no_source"
            print(f"           [PASS 1] SKIPPED (control — no deterministic source)")

        # =================================================================
        # PASS 2 — VERIFY with flywheel
        # =================================================================
        expected_anchors = 1 if (det_source and row.get("deterministic_score")) else 0
        print(f"           [PASS 2] VERIFY epistemique (flywheel expects {expected_anchors} anchor(s))...")

        config_verify = PipelineConfig(
            metrological_frame=entry.get("frame"),
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
            if isinstance(meta, str):
                import json as _json
                meta = _json.loads(meta)
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
    print("EPP SCENARIO FLYWHEEL v2 — Expanded Post-Cutoff Demonstration")
    print("DETERMINISTIC first, then VERIFY with flywheel injection")
    print("=" * 70)

    # --- Pre-validate SPARQL queries ---
    print("\n  [PRE-CHECK] Validating Wikidata SPARQL queries...")
    import httpx
    sparql_ok = 0
    sparql_fail = 0
    claims_to_run = []
    for c in CLAIMS:
        dq = c.get("deterministic_query")
        if dq and dq.get("sparql") and c.get("deterministic_source") == "wikidata":
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        "https://query.wikidata.org/sparql",
                        params={"query": dq["sparql"], "format": "json"},
                        headers={
                            "Accept": "application/sparql-results+json",
                            "User-Agent": "EPP_Verdict/1.0 (https://github.com/SimonBouhier/EPP_Verdict) httpx",
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    bindings = data.get("results", {}).get("bindings", [])
                    if bindings:
                        label = next(
                            (v.get("value", "?") for v in bindings[0].values()),
                            "?"
                        )
                        print(f"    OK  {c['id']}: {len(bindings)} result(s) — e.g. {label[:50]}")
                        sparql_ok += 1
                        claims_to_run.append(c)
                    else:
                        print(f"    SKIP {c['id']}: SPARQL returned 0 results — removing from run")
                        sparql_fail += 1
            except Exception as e:
                print(f"    SKIP {c['id']}: SPARQL error ({str(e)[:60]}) — removing from run")
                sparql_fail += 1
        else:
            claims_to_run.append(c)

    print(f"    SPARQL: {sparql_ok} OK, {sparql_fail} skipped")
    if sparql_fail:
        print(f"    (skipped claims won't block the run — controls and valid claims proceed)")
    print()

    available = await check_ollama()
    selected = select_models(available, max_models=3)

    if len(selected) < 2:
        print(f"  ✗ Minimum 2 models required. Available: {available}")
        sys.exit(1)

    print(f"\n  Models ({len(selected)}): {', '.join(selected)}")
    print(f"  Claims ({len(claims_to_run)}): {', '.join(c['id'] for c in claims_to_run)}")

    # Categorize claims for summary
    flywheel_ids = [c["id"] for c in claims_to_run if c.get("deterministic_source")]
    control_ids = [c["id"] for c in claims_to_run if not c.get("deterministic_source")]
    print(f"  Flywheel claims: {len(flywheel_ids)} | Controls: {len(control_ids)}")
    print(f"  Flywheel: enabled (ADR-018)")
    print()

    results = []
    for i, entry in enumerate(claims_to_run, 1):
        row = await run_flywheel_claim(entry, selected, i, len(claims_to_run))
        results.append(row)

    # --- Summary ---
    total_s = sum(r["duration_s"] for r in results)
    print("\n" + "=" * 70)
    print("FLYWHEEL v2 RESULTS")
    print("=" * 70)

    # Header
    print(f"\n  {'ID':<16} {'Verdict':>12} {'Score':>7} {'Base':>7} {'Delta':>8} {'FW':>3} {'Source':<12} {'':>4}")
    print(f"  {'-'*16} {'-'*12} {'-'*7} {'-'*7} {'-'*8} {'-'*3} {'-'*12} {'-'*4}")

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
            f"  {v_icon} {r['id']:<12}"
            f" {v:>12s}"
            f" {cs:>6.0%}"
            f" {bl:>6.0%}"
            f" {delta_str:>8}"
            f" {fw:>3}"
            f" {src:<12}"
        )

    # Flywheel effectiveness
    fw_claims = [r for r in results if r["flywheel_anchors_found"] > 0]
    ctrl_claims = [r for r in results if r["flywheel_anchors_found"] == 0]
    no_baseline = [r for r in fw_claims if r["baseline_verify_score"] is None]

    if fw_claims:
        deltas = [r["delta"] for r in fw_claims if r["delta"] is not None]
        if deltas:
            avg_delta = sum(deltas) / len(deltas)
            print(f"\n  Flywheel claims with delta ({len(deltas)}): avg delta = {avg_delta:+.4f}")
        if no_baseline:
            print(f"  Flywheel claims, first run ({len(no_baseline)}): "
                  f"{', '.join(r['id'] for r in no_baseline)} — scores are now the baseline")

    if ctrl_claims:
        ctrl_deltas = [r["delta"] for r in ctrl_claims if r["delta"] is not None]
        if ctrl_deltas:
            avg_ctrl = sum(ctrl_deltas) / len(ctrl_deltas)
            print(f"  Control claims  ({len(ctrl_deltas)}): avg delta = {avg_ctrl:+.4f}")

    mins = int(total_s // 60)
    secs = int(total_s % 60)
    print(f"\n  Total duration: {mins}m {secs}s")
    print("=" * 70)

    # JSON output
    out_dir = Path(__file__).parent / "benchmark_runs"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"flywheel_v2_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "scenario": "scenario_flywheel_v2",
            "adr": "ADR-018",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "models": selected,
            "flywheel_enabled": True,
            "claims_total": len(claims_to_run),
            "claims_flywheel": len(flywheel_ids),
            "claims_control": len(control_ids),
            "claims": results,
        }, f, indent=2, default=str, ensure_ascii=False)

    print(f"\n  Report: {json_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
