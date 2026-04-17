"""
Scenario Jiang — EPP Prédictions géopolitiques Jiang Xueqin
============================================================

8 claims issues des prédictions de Jiang Xueqin (Yale, "Predictive History")
sur la géopolitique du Moyen-Orient 2024-2026.

Deux passes par claim :
1. VERIFY épistémique (ESMM multi-LLM)
2. DETERMINISTIC ACLED (ancrage sur données de conflit) — si ACLED_EMAIL défini

Usage :
    python demos/scenario_jiang.py
    ACLED_EMAIL=... ACLED_PASSWORD=... python demos/scenario_jiang.py
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

logger = logging.getLogger("scenario_jiang")

# ---------------------------------------------------------------------------
# Claims catalog
# ---------------------------------------------------------------------------

CLAIMS = [
    {
        "id": "JIANG-01",
        "category": "geopolitical_prediction",
        "claim": "Iran pursues a strategy of controlled proxy escalation in the Middle East, consistent with conflict patterns observed through 2025",
        "source_thesis": "Jiang Xueqin, Predictive History, May 2024",
        "frame": "geopolitical_forecast_v1.0",
        "acled_query": {"country": "Iran", "event_type": "Battles", "baseline": 300, "mode": "events"},
    },
    {
        "id": "JIANG-02",
        "category": "geopolitical_prediction",
        "claim": "Iranian proxy network attacks on Gulf state infrastructure have intensified through 2025",
        "source_thesis": "Jiang Xueqin, Predictive History, May 2024",
        "frame": "geopolitical_forecast_v1.0",
        "acled_query": {"region": "Middle East", "actor1": "IRGC", "baseline": 200, "mode": "events"},
    },
    {
        "id": "JIANG-03",
        "category": "geopolitical_prediction",
        "claim": "A sustained disruption of the Strait of Hormuz remains a viable coercive strategy for Iran based on 2025 regional dynamics",
        "source_thesis": "Jiang Xueqin, Predictive History, May 2024",
        "frame": "geopolitical_forecast_v1.0",
        "acled_query": {"country": "Yemen", "event_type": "Strategic developments", "baseline": 150, "mode": "events"},
    },
    {
        "id": "JIANG-RESOLVED-01",
        "category": "resolved_prediction",
        "claim": "Donald Trump won the 2024 US presidential election",
        "source_thesis": "Jiang Xueqin, Predictive History, May 2024",
        "frame": "general_knowledge_v1.0",
        "expected_verdict": "SUPPORTED",
        "acled_query": None,
        "wikidata_query": {
            "sparql": "SELECT ?winnerLabel WHERE { wd:Q101110072 wdt:P991 ?winner . SERVICE wikibase:label { bd:serviceParam wikibase:language \"en\" . } } LIMIT 5"
        },
    },
    {
        "id": "JIANG-RESOLVED-02",
        "category": "resolved_prediction",
        "claim": "The United States conducted direct military operations against Iranian-linked targets in 2025",
        "source_thesis": "Jiang Xueqin, Predictive History, May 2024",
        "frame": "geopolitical_forecast_v1.0",
        "expected_verdict": "SUPPORTED",
        "acled_query": {"country": "Iraq", "actor2": "United States", "baseline": 50, "mode": "events"},
        "wikidata_query": None,
    },
    {
        "id": "JIANG-CAST-01",
        "category": "forecast_delta",
        "claim": "Conflict intensity in the Middle East will escalate beyond historical baselines through 2025-2026",
        "source_thesis": "Jiang Xueqin, Predictive History, May 2024",
        "frame": "geopolitical_forecast_v1.0",
        "acled_query": {"country": "Iran", "baseline": 500, "mode": "forecast"},
    },
    {
        "id": "GEO-CONTROL-01",
        "category": "control_positive",
        "claim": "Yemen is experiencing active armed conflict in 2025 as documented in conflict event databases",
        "frame": "geopolitical_forecast_v1.0",
        "expected_verdict": "SUPPORTED",
        "acled_query": {"country": "Yemen", "baseline": 500, "mode": "events"},
    },
    {
        "id": "GEO-CONTROL-02",
        "category": "control_negative",
        "claim": "Switzerland is experiencing active armed conflict on its sovereign territory in 2025",
        "frame": "geopolitical_forecast_v1.0",
        "expected_verdict": "CONTESTED",
        "acled_query": {"country": "Switzerland", "baseline": 10, "mode": "events"},
    },
]


# ---------------------------------------------------------------------------
# Infra (pattern identique à scenario_6_1_edge_cases.py)
# ---------------------------------------------------------------------------

async def check_ollama() -> list[str]:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception as e:
        print(f"✗ Ollama non disponible: {e}")
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


async def run_claim(entry: dict, selected: list[str], idx: int, total: int) -> dict:
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

    fd, db_path = tempfile.mkstemp(suffix=f"_jiang_{cid}.db")
    os.close(fd)

    row = {
        "id": cid,
        "category": cat,
        "claim": claim,
        "source_thesis": entry.get("source_thesis"),
        "frame": entry.get("frame"),
        "verdict": None,
        "consensus_score": None,
        "dissent": None,
        "dissent_score": None,
        "vote_entropy": None,
        "claim_type": None,
        "decidability_penalty": None,
        "models_agreed": None,
        "models_total": len(selected),
        "triplets_extracted": 0,
        "duration_s": 0.0,
        "expected_verdict": entry.get("expected_verdict"),
        "verdict_ok": None,
        "errors": "",
        # Champs spécifiques Jiang
        "verify_verdict": None,
        "verify_score": None,
        "acled_status": None,
        "acled_score": None,
        "concordance": None,
        "acled_skipped": True,
        "wikidata_status": None,
        "wikidata_score": None,
    }

    try:
        db = ISpaceDB(db_path)
        await db.initialize()
        providers = build_providers(selected)

        # -------------------------------------------------------------------
        # Passe 1 — VERIFY épistémique (toujours exécutée)
        # -------------------------------------------------------------------
        print(f"           [PASSE 1] VERIFY epistemique...")
        config_verify = PipelineConfig(
            metrological_frame=entry["frame"],
            use_cache=False,
        )
        esmm_verify = ESMMRunConfig(
            models=selected,
            input_mode="verify",
            original_claim=claim,
        )

        start = time.time()
        result_verify = await run_pipeline(
            question=claim,
            db=db,
            config=config_verify,
            providers=providers,
            models=selected,
            esmm_config=esmm_verify,
        )
        elapsed = time.time() - start
        row["duration_s"] = round(elapsed, 1)
        row["triplets_extracted"] = result_verify.triplets_extracted

        if result_verify.errors:
            row["errors"] = "; ".join(result_verify.errors)

        # Extraire verdict VERIFY
        verdict_atts = sorted(
            [a for a in result_verify.attestations if a.predicate == "verdict"],
            key=lambda a: a.consensus_score, reverse=True
        )
        if verdict_atts:
            best = verdict_atts[0]
            row["verdict"] = best.object
            row["verify_verdict"] = best.object
            row["consensus_score"] = round(best.consensus_score, 4)
            row["verify_score"] = round(best.consensus_score, 4)
            row["models_agreed"] = best.models_agreeing
            if len(verdict_atts) > 1:
                row["dissent"] = verdict_atts[1].object
                row["dissent_score"] = round(verdict_atts[1].consensus_score, 4)

        # Extraire méta
        if result_verify.attestations:
            meta = getattr(result_verify.attestations[0], "consensus_meta", {}) or {}
            diag = meta.get("diagnostics", {})
            row["vote_entropy"] = diag.get("vote_entropy")
            verify = meta.get("verify", {})
            row["claim_type"] = verify.get("claim_type")
            pen = verify.get("decidability_penalty")
            if isinstance(pen, dict):
                row["decidability_penalty"] = pen.get("claim_type_penalty")
            elif pen:
                row["decidability_penalty"] = pen

        # Affichage passe 1
        v = row["verdict"] or "ERR"
        cs = row["consensus_score"] or 0.0
        ent = row["vote_entropy"] or 0.0
        ct = row["claim_type"] or "?"
        pen_val = row["decidability_penalty"] or 1.0
        print(
            f"           [V1] {v} ({cs:.0%})"
            f" | type={ct} pen={pen_val:.2f} entropy={ent:.2f} | {elapsed:.0f}s"
        )

        # -------------------------------------------------------------------
        # Passe 2 — DETERMINISTIC ACLED (si credentials + acled_query)
        # -------------------------------------------------------------------
        acled_available = bool(os.getenv("ACLED_EMAIL"))
        acled_q = entry.get("acled_query")

        if acled_available and acled_q:
            query_mode = acled_q.get("mode", "events")
            source_id = f"acled_{query_mode}"
            print(f"           [PASSE 2] DETERMINISTIC ACLED ({source_id})...")

            spec = SourceAnchorSpec(
                source_id=source_id,
                frame_id=entry["frame"],
                query=acled_q,
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
                config=PipelineConfig(use_cache=False),
                providers=providers,
                models=selected,
                esmm_config=esmm_det,
            )
            elapsed_det = time.time() - start_det
            row["duration_s"] = round(row["duration_s"] + elapsed_det, 1)
            row["acled_skipped"] = False

            # Extraire statut ACLED depuis l'attestation déterministe
            det_atts = result_det.attestations if result_det else []
            if det_atts:
                acled_att = det_atts[0]
                row["acled_status"] = acled_att.object
                acled_meta = getattr(acled_att, "consensus_meta", {}) or {}
                acled_verify = acled_meta.get("verify", {})
                row["acled_score"] = acled_verify.get("score")

            # Calcul concordance
            verify_verdict = row["verify_verdict"]
            acled_status = row["acled_status"]
            if verify_verdict and acled_status:
                concordance = (
                    (verify_verdict == "SUPPORTED" and acled_status in ("escalation", "stable"))
                    or (verify_verdict == "CONTESTED" and acled_status == "de-escalation")
                    or (verify_verdict == "INSUFFICIENT_EVIDENCE")
                )
                row["concordance"] = concordance

            conc_icon = "✓" if row["concordance"] else ("✗" if row["concordance"] is False else "?")
            print(
                f"           [V2] ACLED status={acled_status or 'n/a'}"
                f" score={row['acled_score'] or 'n/a'}"
                f" | concordance={conc_icon} | {elapsed_det:.0f}s"
            )
        else:
            row["acled_skipped"] = True
            if not acled_available:
                print("           [ACLED] ACLED_EMAIL absent -- passe deterministe ignoree")
            else:
                print("           [ACLED] acled_query=None -- passe deterministe ignoree")

        # -------------------------------------------------------------------
        # Passe 3 — Wikidata (si wikidata_query défini, pas de credentials)
        # -------------------------------------------------------------------
        wiki_q = entry.get("wikidata_query")
        if wiki_q:
            print(f"           [PASSE 3] DETERMINISTIC Wikidata...")
            try:
                spec_wiki = SourceAnchorSpec(
                    source_id="wikidata",
                    frame_id=entry["frame"],
                    query=wiki_q,
                )
                esmm_wiki = ESMMRunConfig(
                    models=[],
                    claim_nature=ClaimNature.DETERMINISTIC,
                    source_anchor_spec=spec_wiki,
                )
                start_wiki = time.time()
                result_wiki = await run_pipeline(
                    question=claim,
                    db=db,
                    config=PipelineConfig(use_cache=False),
                    providers=providers,
                    models=selected,
                    esmm_config=esmm_wiki,
                )
                elapsed_wiki = time.time() - start_wiki
                row["duration_s"] = round(row["duration_s"] + elapsed_wiki, 1)

                # Debug temporaire
                if result_wiki:
                    print(f"           [WIKI] pipeline errors={result_wiki.errors}")
                    print(f"           [WIKI] attestations count={len(result_wiki.attestations)}")

                if result_wiki and result_wiki.attestations:
                    row["wikidata_status"] = "found"
                    row["wikidata_score"] = 0.85  # plafonné MAX_CONFIDENCE
                else:
                    row["wikidata_status"] = "not_found"
                    row["wikidata_score"] = 0.0

                print(f"           [WIKI] status={row['wikidata_status']}"
                      f" score={row['wikidata_score']} | {elapsed_wiki:.0f}s")
            except Exception as e:
                row["wikidata_status"] = f"error: {e}"
                row["wikidata_score"] = None
                print(f"           [WIKI] Error: {str(e)[:60]}")

        # Valider verdict attendu
        if row["expected_verdict"] and row["verdict"]:
            row["verdict_ok"] = row["verdict"] == row["expected_verdict"]

        # Affichage récap
        v_icon = ""
        if row["verdict_ok"] is True:
            v_icon = " ✓"
        elif row["verdict_ok"] is False:
            v_icon = " ✗"
        print(f"           → {v or 'ERR'}{v_icon} ({cs:.0%}) | {row['duration_s']:.0f}s total")

        for p in providers.values():
            if hasattr(p, "close"):
                await p.close()

    except Exception as e:
        row["errors"] = str(e)
        print(f"           → ERROR: {str(e)[:80]}")
    finally:
        try:
            await close_pool()
        except Exception:
            pass
        if os.path.exists(db_path):
            os.unlink(db_path)

    return row


async def main():
    print("=" * 65)
    print("EPP SCENARIO JIANG — Prédictions géopolitiques Jiang Xueqin")
    print("VERIFY epistemique + ancrage ACLED (si credentials)")
    print("=" * 65)

    acled_active = bool(os.getenv("ACLED_EMAIL"))
    print(f"\nACLED credentials: {'OUI' if acled_active else 'NON (passe deterministe ignoree)'}")

    available = await check_ollama()
    selected = select_models(available, max_models=3)

    if len(selected) < 2:
        print(f"✗ Minimum 2 modèles requis. Disponibles: {available}")
        sys.exit(1)

    print(f"Models ({len(selected)}): {', '.join(selected)}")
    print(f"Claims  ({len(CLAIMS)}): {', '.join(c['id'] for c in CLAIMS)}")
    print()

    results = []
    for i, entry in enumerate(CLAIMS, 1):
        row = await run_claim(entry, selected, i, len(CLAIMS))
        results.append(row)

    # --- Summary ---
    total_s = sum(r["duration_s"] for r in results)
    print("\n" + "=" * 65)
    print("SUMMARY")
    print("=" * 65)

    categories = {}
    for r in results:
        cat = r["category"]
        categories.setdefault(cat, []).append(r)

    for cat, rows in categories.items():
        print(f"\n  [{cat}]")
        for r in rows:
            v = r["verdict"] or "ERR"
            cs = r["consensus_score"] or 0.0
            ct = r["claim_type"] or "?"
            ent = r["vote_entropy"] or 0.0
            acled_s = r["acled_status"] or ("skip" if r["acled_skipped"] else "n/a")

            v_icon = "✓" if r["verdict_ok"] is True else ("✗" if r["verdict_ok"] is False else " ")
            conc = r["concordance"]
            conc_icon = ("✓" if conc else ("✗" if conc is False else " ")) if not r["acled_skipped"] else "-"

            print(
                f"    {v_icon} {r['id']} → {v} ({cs:.0%})"
                f" type={ct} entropy={ent:.2f}"
                f" | ACLED={acled_s} conc={conc_icon}"
            )
            if r["dissent"]:
                print(f"         dissent: {r['dissent']} ({r['dissent_score']:.0%})")
            if r["errors"]:
                print(f"         error: {r['errors'][:60]}")

    # Concordance globale
    acled_run = [r for r in results if not r["acled_skipped"]]
    if acled_run:
        concordant = sum(1 for r in acled_run if r["concordance"] is True)
        print(f"\n  Concordance VERIFY↔ACLED : {concordant}/{len(acled_run)}")

    mins = int(total_s // 60)
    secs = int(total_s % 60)
    print(f"\n  Durée totale: {mins}m {secs}s")
    print("=" * 65)

    # JSON output
    out_dir = Path(__file__).parent / "benchmark_runs"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"jiang_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "scenario": "scenario_jiang",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "models": selected,
            "acled_enabled": acled_active,
            "claims": results,
        }, f, indent=2, default=str, ensure_ascii=False)

    print(f"\n  Report: {json_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
