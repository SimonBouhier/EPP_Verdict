"""
Scenario 6.2 — Contextual Qualifier Sensitivity
================================================

Teste la sensibilité épistémique aux qualificateurs contextuels.

HYPOTHÈSE CENTRALE :
    Une claim sans qualificateur de contexte doit produire un consensus
    INFÉRIEUR à la même claim avec qualificateur explicite.
    Le delta mesure la rigueur épistémique du pipeline.

EXPÉRIENCES :
    E1 — Eau / pression atmosphérique
         AQU-01 : sans qualificateur       → consensus bas attendu (ambiguïté altitude)
         AQU-02 : avec qualificateur 1013 hPa → consensus élevé attendu
         AQU-03 : contexte altitude 3000m  → REFUTED ou CONTESTED attendu

    E2 — Température / échelle implicite
         TMP-01 : "Water freezes at 32 degrees"  → dépend de l'échelle (F vs C)
         TMP-02 : "Water freezes at 32 degrees Fahrenheit" → non ambigu
         TMP-03 : "Water freezes at 0 degrees Celsius"     → non ambigu, différent

    E3 — Vitesse / référentiel implicite
         SPD-01 : "Light travels at 300,000 km/s"  → approximation (299,792)
         SPD-02 : "Light travels at 299,792 km/s in vacuum" → précis + qualifié
         SPD-03 : "Light travels at 300,000 km/s in glass" → REFUTED (ralentit)

    E4 — Claims juridiques / territoire implicite
         LAW-01 : "Cannabis is illegal"          → dépend du pays
         LAW-02 : "Cannabis is illegal in France" → factuel précis
         LAW-03 : "Cannabis is legal in Canada"  → factuel précis, inverso

    E5 — Cache poisoning naturel (ADR-013)
         CACHE-01 : "Water boils at 100 degrees Celsius" (sans qualiticateur)
                    → délibère normalement
         CACHE-02 : même question → doit matcher le cache de CACHE-01
                    → vérifier que le cache NE SERT PAS la réponse qualifiée
         CACHE-03 : "Water boils at 100 degrees Celsius at 1013 hPa"
                    → NE doit PAS matcher le cache de CACHE-01 (question différente)
                    → doit délibérer indépendamment

MÉTRIQUES CLÉS :
    - Δconsensus entre version sans/avec qualificateur (par paire)
    - Δ>15% : le système détecte la nuance ✓
    - Δ<5%  : le système est insensible au contexte ✗
    - CACHE-02 doit avoir from_cache=True et même hash que CACHE-01
    - CACHE-03 doit avoir from_cache=False (question différente)

Models recommandés : mistral, llama3.1:8b, gemma3 (3 modèles, ~90s/claim)
Durée estimée : ~22 min (15 claims × ~90s)

Usage :
    python demos/scenario_6_2_qualifier_sensitivity.py
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

logger = logging.getLogger("scenario6_2")

# ---------------------------------------------------------------------------
# Claims catalog
# ---------------------------------------------------------------------------

CLAIMS = [

    # ── E1 : EAU / PRESSION ATMOSPHÉRIQUE ──────────────────────────────────

    {
        "id": "AQU-01",
        "claim": "Water boils at 100 degrees Celsius",
        "category": "water_pressure",
        "frame": "general_knowledge_v1.0",
        "note": "Sans qualificateur — altitude, pression implicites. Consensus bas attendu.",
        "pair_with": "AQU-02",
        "expected_delta": "low",       # consensus doit être INFÉRIEUR à AQU-02
        "use_cache": False,            # benchmark — pas de cache
    },
    {
        "id": "AQU-02",
        "claim": "Water boils at 100 degrees Celsius at standard atmospheric pressure (1013 hPa)",
        "category": "water_pressure",
        "frame": "general_knowledge_v1.0",
        "note": "Avec qualificateur précis — consensus élevé attendu (98%+).",
        "pair_with": "AQU-01",
        "expected_verdict": "SUPPORTED",
        "use_cache": False,
    },
    {
        "id": "AQU-03",
        "claim": "Water boils at 100 degrees Celsius at an altitude of 3000 meters",
        "category": "water_pressure",
        "frame": "general_knowledge_v1.0",
        "note": "Contexte altitude — faux (eau bout ~90°C à 3000m). REFUTED attendu.",
        "expected_verdict": "REFUTED",
        "use_cache": False,
    },

    # ── E2 : TEMPÉRATURE / ÉCHELLE IMPLICITE ───────────────────────────────

    {
        "id": "TMP-01",
        "claim": "Water freezes at 32 degrees",
        "category": "temperature_scale",
        "frame": "general_knowledge_v1.0",
        "note": "Sans unité — 32°F (vrai) vs 32°C (faux). Ambiguïté maximale attendue.",
        "pair_with": "TMP-02",
        "expected_delta": "low",
        "use_cache": False,
    },
    {
        "id": "TMP-02",
        "claim": "Water freezes at 32 degrees Fahrenheit",
        "category": "temperature_scale",
        "frame": "general_knowledge_v1.0",
        "note": "Avec unité explicite — factuel, consensus élevé attendu.",
        "expected_verdict": "SUPPORTED",
        "pair_with": "TMP-01",
        "use_cache": False,
    },
    {
        "id": "TMP-03",
        "claim": "Water freezes at 0 degrees Celsius",
        "category": "temperature_scale",
        "frame": "general_knowledge_v1.0",
        "note": "Vérité alternative — même fait, unité différente. Consensus élevé attendu.",
        "expected_verdict": "SUPPORTED",
        "use_cache": False,
    },

    # ── E3 : VITESSE DE LA LUMIÈRE / RÉFÉRENTIEL ───────────────────────────

    {
        "id": "SPD-01",
        "claim": "Light travels at 300,000 kilometers per second",
        "category": "light_speed",
        "frame": "general_knowledge_v1.0",
        "note": "Approximation courante — valeur exacte 299,792. phi4 doit nuancer.",
        "pair_with": "SPD-02",
        "expected_delta": "medium",
        "use_cache": False,
    },
    {
        "id": "SPD-02",
        "claim": "Light travels at exactly 299,792 kilometers per second in a vacuum",
        "category": "light_speed",
        "frame": "general_knowledge_v1.0",
        "note": "Valeur exacte + référentiel vide. Consensus élevé attendu.",
        "expected_verdict": "SUPPORTED",
        "pair_with": "SPD-01",
        "use_cache": False,
    },
    {
        "id": "SPD-03",
        "claim": "Light travels at 300,000 kilometers per second through glass",
        "category": "light_speed",
        "frame": "general_knowledge_v1.0",
        "note": "Faux — dans le verre n~1.5, vitesse ~200,000 km/s. REFUTED attendu.",
        "expected_verdict": "REFUTED",
        "use_cache": False,
    },

    # ── E4 : CLAIMS JURIDIQUES / TERRITOIRE ────────────────────────────────

    {
        "id": "LAW-01",
        "claim": "Cannabis is illegal",
        "category": "legal_jurisdiction",
        "frame": "general_knowledge_v1.0",
        "note": "Sans territoire — vrai dans certains pays, faux dans d'autres. CONTESTED attendu.",
        "pair_with": "LAW-02",
        "expected_delta": "high",
        "use_cache": False,
    },
    {
        "id": "LAW-02",
        "claim": "Cannabis is illegal for recreational use in France",
        "category": "legal_jurisdiction",
        "frame": "general_knowledge_v1.0",
        "note": "Avec territoire précis — factuel vérifiable. Consensus élevé attendu.",
        "expected_verdict": "SUPPORTED",
        "pair_with": "LAW-01",
        "use_cache": False,
    },
    {
        "id": "LAW-03",
        "claim": "Cannabis is legal for recreational use in Canada",
        "category": "legal_jurisdiction",
        "frame": "general_knowledge_v1.0",
        "note": "Inverse mais également précis — SUPPORTED attendu (légalisé 2018).",
        "expected_verdict": "SUPPORTED",
        "use_cache": False,
    },

    # ── E5 : CACHE POISONING NATUREL (ADR-013) ─────────────────────────────

    {
        "id": "CACHE-01",
        "claim": "Water boils at 100 degrees Celsius",
        "category": "cache_test",
        "frame": "general_knowledge_v1.0",
        "note": "Run initial sans qualificateur — délibère et stocke en cache.",
        "use_cache": True,             # cache ACTIVÉ — stocke le résultat
        "cache_test": "first_run",
    },
    {
        "id": "CACHE-02",
        "claim": "Water boils at 100 degrees Celsius",
        "category": "cache_test",
        "frame": "general_knowledge_v1.0",
        "note": "Même question — DOIT retourner cache-hit (from_cache=True, hash identique).",
        "use_cache": True,
        "cache_test": "expect_hit",    # from_cache=True attendu
        "expected_from_cache": True,
    },
    {
        "id": "CACHE-03",
        "claim": "Water boils at 100 degrees Celsius at standard atmospheric pressure (1013 hPa)",
        "category": "cache_test",
        "frame": "general_knowledge_v1.0",
        "note": "Question différente — NE DOIT PAS matcher le cache de CACHE-01.",
        "use_cache": True,
        "cache_test": "expect_miss",   # from_cache=False attendu (nouvelle délibération)
        "expected_from_cache": False,
    },
]

# ---------------------------------------------------------------------------
# Infrastructure (pattern identique scenario 6.1)
# ---------------------------------------------------------------------------

async def check_ollama() -> list[str]:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception as e:
        print(f"Ollama non disponible: {e}")
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


async def run_claim(entry: dict, selected: list[str], idx: int, total: int,
                    persistent_db_path: str) -> dict:
    from database.engine import ISpaceDB
    from database.pool import close_pool
    from services.esmm.orchestrator import ESMMRunConfig
    from services.esmm.pipeline import PipelineConfig, run_pipeline

    cid = entry["id"]
    claim = entry["claim"]
    short = claim[:55] + "..." if len(claim) > 55 else claim
    cat = entry.get("category", "")
    use_cache = entry.get("use_cache", False)
    cache_test = entry.get("cache_test")

    print(f"\n  [{idx:02d}/{total:02d}] {cid} [{cat}]")
    print(f"           \"{short}\"")
    if entry.get("note"):
        print(f"           i {entry['note']}")

    # Choix DB : persistante pour les tests cache, tempfile pour les benchmarks
    if use_cache:
        db_path = persistent_db_path
        cleanup = False
    else:
        fd, db_path = tempfile.mkstemp(suffix=f"_s62_{cid}.db")
        os.close(fd)
        cleanup = True

    row = {
        "id": cid,
        "category": cat,
        "claim": claim,
        "note": entry.get("note", ""),
        "pair_with": entry.get("pair_with"),
        "cache_test": cache_test,
        "use_cache": use_cache,
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
        "from_cache": False,
        "cache_hit_hash": None,
        "duration_s": 0.0,
        "expected_verdict": entry.get("expected_verdict"),
        "expected_from_cache": entry.get("expected_from_cache"),
        "verdict_ok": None,
        "cache_test_ok": None,
        "errors": "",
    }

    try:
        db = ISpaceDB(db_path)
        await db.initialize()
        providers = build_providers(selected)

        config = PipelineConfig(
            metrological_frame=entry.get("frame", "general_knowledge_v1.0"),
            use_cache=use_cache,
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
        row["triplets_extracted"] = result.triplets_extracted
        row["from_cache"] = getattr(result, "from_cache", False)
        row["cache_hit_hash"] = getattr(result, "cache_hit_hash", None)

        if result.errors:
            row["errors"] = "; ".join(result.errors)

        # Extract verdict
        verdict_atts = sorted(
            [a for a in result.attestations if a.predicate == "verdict"],
            key=lambda a: a.consensus_score, reverse=True
        )
        if verdict_atts:
            best = verdict_atts[0]
            row["verdict"] = best.object
            row["consensus_score"] = round(best.consensus_score, 4)
            row["models_agreed"] = best.models_agreeing
            if len(verdict_atts) > 1:
                row["dissent"] = verdict_atts[1].object
                row["dissent_score"] = round(verdict_atts[1].consensus_score, 4)

        # Extract meta
        if result.attestations:
            meta = getattr(result.attestations[0], "consensus_meta", {}) or {}
            diag = meta.get("diagnostics", {})
            row["vote_entropy"] = diag.get("vote_entropy")
            verify = meta.get("verify", {})
            row["claim_type"] = verify.get("claim_type")
            pen = verify.get("decidability_penalty")
            if isinstance(pen, dict):
                row["decidability_penalty"] = pen.get("claim_type_penalty")
            elif pen:
                row["decidability_penalty"] = pen

        # Validate expected verdict
        if entry.get("expected_verdict") and row["verdict"]:
            row["verdict_ok"] = row["verdict"] == entry["expected_verdict"]

        # Validate cache behavior
        if entry.get("expected_from_cache") is not None:
            row["cache_test_ok"] = row["from_cache"] == entry["expected_from_cache"]

        # Display
        v = row["verdict"] or "ERR"
        cs = row["consensus_score"] or 0.0
        ent = row["vote_entropy"] or 0.0
        ct = row["claim_type"] or "?"

        cache_tag = " *CACHE" if row["from_cache"] else ""
        verdict_icon = ""
        if row["verdict_ok"] is True:
            verdict_icon = " ok"
        elif row["verdict_ok"] is False:
            verdict_icon = " FAIL"

        cache_icon = ""
        if row["cache_test_ok"] is True:
            cache_icon = " [cache ok]"
        elif row["cache_test_ok"] is False:
            cache_icon = " [cache FAIL]"

        if row["dissent"]:
            print(
                f"           -> {v}{verdict_icon} ({cs:.0%}) <-> {row['dissent']} ({row['dissent_score']:.0%})"
                f" | type={ct} entropy={ent:.2f} | {elapsed:.0f}s{cache_tag}{cache_icon}"
            )
        else:
            print(
                f"           -> {v}{verdict_icon} ({cs:.0%})"
                f" | type={ct} entropy={ent:.2f} | {elapsed:.0f}s{cache_tag}{cache_icon}"
            )

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
        if cleanup and os.path.exists(db_path):
            os.unlink(db_path)

    return row


async def main():
    print("=" * 68)
    print("EPP SCENARIO 6.2 — Contextual Qualifier Sensitivity")
    print("Eau/Pression · Temperature · Vitesse Lumiere · Juridique · Cache")
    print("=" * 68)

    available = await check_ollama()
    selected = select_models(available, max_models=3)

    if len(selected) < 2:
        print(f"Minimum 2 modeles requis. Disponibles: {available}")
        sys.exit(1)

    print(f"\nModels ({len(selected)}): {', '.join(selected)}")
    print(f"Claims ({len(CLAIMS)}): {', '.join(c['id'] for c in CLAIMS)}")
    print()
    print("NOTE: Claims cache_test utilisent la DB persistante (epp_devnet.db)")
    print("      Claims benchmark utilisent des DBs temporaires isolees")
    print()

    # DB persistante pour les tests cache uniquement
    from services.config_loader import get_section
    db_cfg = get_section("database", {})
    persistent_db_path = db_cfg.get("path", "data/epp_devnet.db")
    print(f"DB persistante: {persistent_db_path}")
    print()

    results = []
    for i, entry in enumerate(CLAIMS, 1):
        row = await run_claim(entry, selected, i, len(CLAIMS), persistent_db_path)
        results.append(row)

    # ── SUMMARY ──────────────────────────────────────────────────────────────
    total_s = sum(r["duration_s"] for r in results)
    print("\n" + "=" * 68)
    print("SUMMARY")
    print("=" * 68)

    # Par expérience
    experiments = {
        "water_pressure": ("E1", "Eau / Pression atmospherique"),
        "temperature_scale": ("E2", "Temperature / Echelle implicite"),
        "light_speed": ("E3", "Vitesse lumiere / Referentiel"),
        "legal_jurisdiction": ("E4", "Claims juridiques / Territoire"),
        "cache_test": ("E5", "Cache poisoning naturel (ADR-013)"),
    }

    for cat, (code, label) in experiments.items():
        rows = [r for r in results if r["category"] == cat]
        if not rows:
            continue
        print(f"\n  [{code}] {label}")
        for r in rows:
            v = r["verdict"] or "ERR"
            cs = r["consensus_score"] or 0.0
            ent = r["vote_entropy"] or 0.0
            ct = r["claim_type"] or "?"
            cache_tag = " *" if r["from_cache"] else ""
            v_icon = "ok" if r["verdict_ok"] is True else ("FAIL" if r["verdict_ok"] is False else " ")
            c_icon = "[C-ok]" if r["cache_test_ok"] is True else ("[C-FAIL]" if r["cache_test_ok"] is False else "")
            print(f"    {v_icon} {r['id']} -> {v} ({cs:.0%}) type={ct} entropy={ent:.2f}{cache_tag} {c_icon}")
            if r.get("errors"):
                print(f"         ERR: {r['errors'][:70]}")

    # Deltas entre paires
    print("\n  [QUALIFIER DELTA — sensibilite au contexte]")
    print("  (delta > 15% = le systeme detecte la nuance)")
    pairs_seen = set()
    for r in results:
        if not r.get("pair_with"):
            continue
        pair_id = r["pair_with"]
        key = tuple(sorted([r["id"], pair_id]))
        if key in pairs_seen:
            continue
        pairs_seen.add(key)
        partner = next((x for x in results if x["id"] == pair_id), None)
        if not partner:
            continue
        cs_a = r["consensus_score"]
        cs_b = partner["consensus_score"]
        if cs_a is None or cs_b is None:
            print(f"    ? {r['id']} vs {pair_id}: données manquantes")
            continue
        delta = abs(cs_a - cs_b)
        detected = delta >= 0.15
        icon = "ok" if detected else "FAIL"
        print(
            f"    {icon} {r['id']} ({cs_a:.0%}) vs {pair_id} ({cs_b:.0%})"
            f" -> delta={delta:.0%} ({'nuance detectee' if detected else 'insensible'})"
        )

    # Cache test résumé
    cache_rows = [r for r in results if r["category"] == "cache_test"]
    if cache_rows:
        print("\n  [CACHE ADR-013 — comportement attendu]")
        all_ok = True
        for r in cache_rows:
            ok = r.get("cache_test_ok")
            icon = "ok" if ok is True else ("FAIL" if ok is False else "?")
            fc = "from_cache=True" if r["from_cache"] else "from_cache=False"
            h = r.get("cache_hit_hash", "")[:16] + "..." if r.get("cache_hit_hash") else ""
            print(f"    {icon} {r['id']} -> {fc} {h}")
            if ok is False:
                all_ok = False
        print(f"\n    Cache behavior: {'OK' if all_ok else 'ANOMALIE DETECTEE'}")

    mins = int(total_s // 60)
    secs = int(total_s % 60)
    print(f"\n  Duree totale: {mins}m {secs}s")
    print("=" * 68)

    # JSON report
    out_dir = Path(__file__).parent / "benchmark_runs"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"scenario6_2_{ts}.json"

    # Compute deltas for report
    deltas = []
    pairs_seen = set()
    for r in results:
        if not r.get("pair_with"):
            continue
        key = tuple(sorted([r["id"], r["pair_with"]]))
        if key in pairs_seen:
            continue
        pairs_seen.add(key)
        partner = next((x for x in results if x["id"] == r["pair_with"]), None)
        if partner and r["consensus_score"] and partner["consensus_score"]:
            deltas.append({
                "pair": [r["id"], r["pair_with"]],
                "delta": round(abs(r["consensus_score"] - partner["consensus_score"]), 4),
                "nuance_detected": abs(r["consensus_score"] - partner["consensus_score"]) >= 0.15,
            })

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "scenario": "scenario_6_2_qualifier_sensitivity",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "models": selected,
            "total_claims": len(CLAIMS),
            "qualifier_deltas": deltas,
            "claims": results,
        }, f, indent=2, default=str, ensure_ascii=False)

    print(f"\n  Report: {json_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
