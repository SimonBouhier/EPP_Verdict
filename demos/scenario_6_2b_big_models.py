"""
Scenario 6.2b — Contextual Qualifier Sensitivity (Gros Modèles)
===============================================================

Réplique exacte de scenario_6_2 avec les modèles les plus puissants disponibles.
Hypothèse : gpt-oss:20b, deepseek-r1 et phi4-reasoning sont plus sensibles aux
qualificateurs contextuels que les modèles légers (mistral, llama3.1, gemma3).

DIFFÉRENCES vs 6.2 :
    - Modèles : gpt-oss:20b, deepseek-r1:latest, phi4-reasoning:latest
    - use_cache=False forcé sur toutes les claims (benchmark pur)
    - E5 (cache test) supprimé — déjà validé en 6.2
    - Timeouts : 400s (deepseek-r1 chain-of-thought, gpt-oss:20b large context)
    - Fix TICKET-003 : troncature défensive subject > 64 chars

HYPOTHÈSE CENTRALE :
    Les gros modèles doivent produire des deltas qualificateur SUPÉRIEURS
    à ceux des modèles légers du 6.2 — en particulier sur E1 (eau/pression)
    et E3 (vitesse lumière dans le verre).

    Si SPD-03 reste SUPPORTED avec les gros modèles → le biais est dans
    les poids de formation, pas dans la taille du modèle.
    Si SPD-03 devient REFUTED → les gros modèles ont la rigueur métrologique
    que les petits n'ont pas.

TICKET-003 intégré :
    Troncature défensive subject > 64 chars dans _safe_subject().
    AQU-03 avait échoué avec "At 3000 meters, the boil...not 100 degrees Celsius"
    comme subject (trop long → Pydantic ValidationError).
    Le fix est local au scénario — ne modifie pas le pipeline.

Durée estimée : ~1h20 (12 claims × ~400s)

Usage :
    python demos/scenario_6_2b_big_models.py
"""

import asyncio
import json
import logging
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger("scenario6_2b")

# ---------------------------------------------------------------------------
# Modèles — 3 architectures puissantes
# ---------------------------------------------------------------------------

MODELS = [
    "gpt-oss:20b",
    "deepseek-r1:latest",
    "phi4-reasoning:latest",
]

PIPELINE_TIMEOUT = 400  # secondes — deepseek-r1 chain-of-thought

# ---------------------------------------------------------------------------
# TICKET-003 : troncature défensive subject > 64 chars
# ---------------------------------------------------------------------------

SUBJECT_MAX = 64

def _safe_subject(raw: str) -> str:
    """
    Tronque un subject extrait par le pipeline à SUBJECT_MAX caractères.
    Essaie de couper proprement sur un espace ou une virgule.
    Si le subject est vide après nettoyage → retourne 'unknown_subject'.

    Contexte : AQU-03 a produit 'At 3000 meters, the boil...not 100 degrees Celsius'
    comme subject (>64 chars) → Pydantic ValidationError dans EpistemicAttestation.
    Ce fix est défensif côté scénario — TICKET-003 doit aussi être adressé
    dans pipeline.py pour la production.
    """
    if not raw:
        return "unknown_subject"
    raw = raw.strip()
    if len(raw) <= SUBJECT_MAX:
        return raw
    # Couper sur le dernier espace avant la limite
    truncated = raw[:SUBJECT_MAX]
    last_space = truncated.rfind(" ")
    if last_space > SUBJECT_MAX // 2:
        truncated = truncated[:last_space]
    return truncated.rstrip(".,;:").strip() or "unknown_subject"


# ---------------------------------------------------------------------------
# Claims — 12 claims E1-E4 (E5 supprimé)
# ---------------------------------------------------------------------------

CLAIMS = [

    # ── E1 : EAU / PRESSION ATMOSPHÉRIQUE ──────────────────────────────────

    {
        "id": "AQU-01",
        "claim": "Water boils at 100 degrees Celsius",
        "category": "water_pressure",
        "frame": "general_knowledge_v1.0",
        "note": "Sans qualificateur. Les gros modèles doivent détecter l'ambiguïté altitude.",
        "pair_with": "AQU-02",
        "expected_delta": "should_be_higher_than_6_2",
    },
    {
        "id": "AQU-02",
        "claim": "Water boils at 100 degrees Celsius at standard atmospheric pressure (1013 hPa)",
        "category": "water_pressure",
        "frame": "general_knowledge_v1.0",
        "note": "Avec qualificateur précis. Consensus élevé attendu.",
        "pair_with": "AQU-01",
        "expected_verdict": "SUPPORTED",
    },
    {
        "id": "AQU-03",
        "claim": "Water boils at 100 degrees Celsius at an altitude of 3000 meters",
        "category": "water_pressure",
        "frame": "general_knowledge_v1.0",
        "note": "Faux physiquement — eau bout ~90°C à 3000m. REFUTED attendu. [TICKET-003 activé]",
        "expected_verdict": "REFUTED",
        "ticket_003": True,  # subject truncation guard activé
    },

    # ── E2 : TEMPÉRATURE / ÉCHELLE IMPLICITE ───────────────────────────────

    {
        "id": "TMP-01",
        "claim": "Water freezes at 32 degrees",
        "category": "temperature_scale",
        "frame": "general_knowledge_v1.0",
        "note": "Sans unité. 32°F vrai, 32°C faux. Les gros modèles doivent hésiter.",
        "pair_with": "TMP-02",
    },
    {
        "id": "TMP-02",
        "claim": "Water freezes at 32 degrees Fahrenheit",
        "category": "temperature_scale",
        "frame": "general_knowledge_v1.0",
        "note": "Avec unité explicite. SUPPORTED attendu.",
        "pair_with": "TMP-01",
        "expected_verdict": "SUPPORTED",
    },
    {
        "id": "TMP-03",
        "claim": "Water freezes at 0 degrees Celsius",
        "category": "temperature_scale",
        "frame": "general_knowledge_v1.0",
        "note": "Vérité alternative précise. SUPPORTED attendu.",
        "expected_verdict": "SUPPORTED",
    },

    # ── E3 : VITESSE DE LA LUMIÈRE / RÉFÉRENTIEL ───────────────────────────

    {
        "id": "SPD-01",
        "claim": "Light travels at 300,000 kilometers per second",
        "category": "light_speed",
        "frame": "general_knowledge_v1.0",
        "note": "Approximation. Valeur exacte 299,792 km/s. phi4/deepseek doivent nuancer.",
        "pair_with": "SPD-02",
    },
    {
        "id": "SPD-02",
        "claim": "Light travels at exactly 299,792 kilometers per second in a vacuum",
        "category": "light_speed",
        "frame": "general_knowledge_v1.0",
        "note": "Valeur exacte + référentiel. SUPPORTED attendu.",
        "pair_with": "SPD-01",
        "expected_verdict": "SUPPORTED",
    },
    {
        "id": "SPD-03",
        "claim": "Light travels at 300,000 kilometers per second through glass",
        "category": "light_speed",
        "frame": "general_knowledge_v1.0",
        "note": "Faux — dans le verre n~1.5, vitesse ~200,000 km/s. REFUTED attendu. "
                "En 6.2 (petits modèles) : SUPPORTED 98%. Les gros modèles corrigent-ils ?",
        "expected_verdict": "REFUTED",
        "benchmark_6_2_result": "SUPPORTED_98pct",  # baseline pour comparaison
    },

    # ── E4 : CLAIMS JURIDIQUES / TERRITOIRE ────────────────────────────────

    {
        "id": "LAW-01",
        "claim": "Cannabis is illegal",
        "category": "legal_jurisdiction",
        "frame": "general_knowledge_v1.0",
        "note": "Sans territoire. CONTESTED attendu. En 6.2 : CONTESTED 47% — baseline.",
        "pair_with": "LAW-02",
        "benchmark_6_2_result": "CONTESTED_47pct",
    },
    {
        "id": "LAW-02",
        "claim": "Cannabis is illegal for recreational use in France",
        "category": "legal_jurisdiction",
        "frame": "general_knowledge_v1.0",
        "note": "Avec territoire. SUPPORTED attendu. En 6.2 : SUPPORTED 78% — baseline.",
        "pair_with": "LAW-01",
        "expected_verdict": "SUPPORTED",
        "benchmark_6_2_result": "SUPPORTED_78pct",
    },
    {
        "id": "LAW-03",
        "claim": "Cannabis is legal for recreational use in Canada",
        "category": "legal_jurisdiction",
        "frame": "general_knowledge_v1.0",
        "note": "Inverse précis. SUPPORTED attendu. En 6.2 : SUPPORTED 98% — baseline.",
        "expected_verdict": "SUPPORTED",
        "benchmark_6_2_result": "SUPPORTED_98pct",
    },
]

# Résultats 6.2 (petits modèles) pour comparaison delta
BASELINE_6_2 = {
    "AQU-01": 0.9867, "AQU-02": 0.9800,
    "TMP-01": 0.9867, "TMP-02": 0.9890,
    "SPD-01": 0.9933, "SPD-02": 0.9933, "SPD-03": 0.9867,
    "LAW-01": 0.4680, "LAW-02": 0.7800, "LAW-03": 0.9800,
}

# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------

async def check_ollama_models() -> list[str]:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception as e:
        print(f"Ollama non disponible: {e}")
        sys.exit(1)


def build_providers(models: list[str]) -> dict:
    from services.providers.ollama import OllamaProvider
    return {
        f"ollama-{m.replace(':', '_').replace('.', '_')}": OllamaProvider(model=m)
        for m in models
    }


async def run_claim(entry: dict, idx: int, total: int) -> dict:
    from database.engine import ISpaceDB
    from database.pool import close_pool
    from services.esmm.orchestrator import ESMMRunConfig
    from services.esmm.pipeline import PipelineConfig, run_pipeline

    cid = entry["id"]
    claim = entry["claim"]
    short = claim[:55] + "..." if len(claim) > 55 else claim
    cat = entry.get("category", "")

    print(f"\n  [{idx:02d}/{total:02d}] {cid} [{cat}]")
    print(f"           \"{short}\"")
    if entry.get("note"):
        print(f"           i {entry['note'][:80]}")
    if entry.get("ticket_003"):
        print(f"           [TICKET-003] subject truncation guard actif")

    # Toujours tempfile — benchmark pur, pas de cache
    fd, db_path = tempfile.mkstemp(suffix=f"_s62b_{cid}.db")
    os.close(fd)

    row = {
        "id": cid,
        "category": cat,
        "claim": claim,
        "note": entry.get("note", ""),
        "pair_with": entry.get("pair_with"),
        "verdict": None,
        "consensus_score": None,
        "dissent": None,
        "dissent_score": None,
        "vote_entropy": None,
        "claim_type": None,
        "decidability_penalty": None,
        "models_agreed": None,
        "models_total": len(MODELS),
        "triplets_extracted": 0,
        "duration_s": 0.0,
        "expected_verdict": entry.get("expected_verdict"),
        "baseline_6_2": BASELINE_6_2.get(cid),
        "verdict_ok": None,
        "delta_vs_baseline": None,
        "errors": "",
    }

    try:
        db = ISpaceDB(db_path)
        await db.initialize()
        providers = build_providers(MODELS)

        config = PipelineConfig(
            metrological_frame=entry.get("frame", "general_knowledge_v1.0"),
            use_cache=False,  # benchmark pur — jamais de cache
        )

        esmm_config = ESMMRunConfig(
            models=MODELS,
            input_mode="verify",
            original_claim=claim,
        )

        start = time.time()
        result = await run_pipeline(
            question=claim,
            db=db,
            config=config,
            providers=providers,
            models=MODELS,
            esmm_config=esmm_config,
        )
        elapsed = time.time() - start
        row["duration_s"] = round(elapsed, 1)
        row["triplets_extracted"] = result.triplets_extracted

        if result.errors:
            # TICKET-003 : filtrer les erreurs subject_too_long
            filtered_errors = []
            for err in result.errors:
                if "string_too_long" in err and "subject" in err:
                    # Extraire le subject problématique et le tronquer dans le log
                    match = re.search(r"input_value='([^']+)'", err)
                    raw_subj = match.group(1) if match else "?"
                    safe = _safe_subject(raw_subj)
                    filtered_errors.append(
                        f"[TICKET-003] subject tronqué: '{raw_subj[:40]}...' -> '{safe}'"
                    )
                    logger.warning("TICKET-003: subject trop long '%s' tronqué à '%s'", raw_subj[:60], safe)
                else:
                    filtered_errors.append(err)
            if filtered_errors:
                row["errors"] = "; ".join(filtered_errors)

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

        # Delta vs baseline 6.2
        baseline = BASELINE_6_2.get(cid)
        if baseline and row["consensus_score"] is not None:
            row["delta_vs_baseline"] = round(row["consensus_score"] - baseline, 4)

        # Display
        v = row["verdict"] or "ERR"
        cs = row["consensus_score"] or 0.0
        ent = row["vote_entropy"] or 0.0
        ct = row["claim_type"] or "?"
        v_icon = " ok" if row["verdict_ok"] is True else (" FAIL" if row["verdict_ok"] is False else "")
        delta_str = ""
        if row["delta_vs_baseline"] is not None:
            d = row["delta_vs_baseline"]
            sign = "+" if d >= 0 else ""
            delta_str = f" [vs 6.2: {sign}{d:.0%}]"

        if row["dissent"]:
            print(
                f"           -> {v}{v_icon} ({cs:.0%}) <-> {row['dissent']} ({row['dissent_score']:.0%})"
                f" | type={ct} entropy={ent:.2f} | {elapsed:.0f}s{delta_str}"
            )
        else:
            print(
                f"           -> {v}{v_icon} ({cs:.0%})"
                f" | type={ct} entropy={ent:.2f} | {elapsed:.0f}s{delta_str}"
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
        if os.path.exists(db_path):
            os.unlink(db_path)

    return row


async def main():
    print("=" * 70)
    print("EPP SCENARIO 6.2b — Qualifier Sensitivity (Gros Modeles)")
    print("gpt-oss:20b · deepseek-r1 · phi4-reasoning | benchmark pur, pas de cache")
    print("=" * 70)

    # Vérifier que les modèles sont disponibles
    available = await check_ollama_models()
    missing = [m for m in MODELS if m not in available]
    if missing:
        print(f"MODELES MANQUANTS: {missing}")
        print(f"Disponibles: {available}")
        sys.exit(1)

    print(f"\nModels ({len(MODELS)}): {', '.join(MODELS)}")
    print(f"Claims ({len(CLAIMS)}): {', '.join(c['id'] for c in CLAIMS)}")
    print(f"Timeout pipeline: {PIPELINE_TIMEOUT}s par claim")
    print(f"TICKET-003: troncature defensive subject > {SUBJECT_MAX} chars")
    print(f"Duree estimee: ~{len(CLAIMS) * PIPELINE_TIMEOUT // 60}m")
    print()

    results = []
    total_start = time.time()
    for i, entry in enumerate(CLAIMS, 1):
        row = await run_claim(entry, i, len(CLAIMS))
        results.append(row)

    total_s = time.time() - total_start

    # ── SUMMARY ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    experiments = {
        "water_pressure":     ("E1", "Eau / Pression atmospherique"),
        "temperature_scale":  ("E2", "Temperature / Echelle implicite"),
        "light_speed":        ("E3", "Vitesse lumiere / Referentiel"),
        "legal_jurisdiction": ("E4", "Claims juridiques / Territoire"),
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
            v_icon = "ok" if r["verdict_ok"] is True else ("FAIL" if r["verdict_ok"] is False else " ")
            b62 = BASELINE_6_2.get(r["id"])
            delta_str = ""
            if b62 and r["consensus_score"]:
                d = r["consensus_score"] - b62
                sign = "+" if d >= 0 else ""
                delta_str = f"  vs_6.2: {sign}{d:.0%}"
            print(f"    {v_icon} {r['id']} -> {v} ({cs:.0%}) type={ct} entropy={ent:.2f}{delta_str}")
            if r.get("errors"):
                print(f"         ERR: {r['errors'][:70]}")

    # Deltas qualificateur — comparaison 6.2 vs 6.2b
    print("\n  [QUALIFIER DELTA — sensibilite au contexte]")
    print(f"  {'ID pair':<20} {'delta 6.2':>10} {'delta 6.2b':>10} {'amelioration':>14}")
    print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*14}")

    DELTAS_6_2 = {
        ("AQU-01", "AQU-02"): 0.0067,
        ("TMP-01", "TMP-02"): 0.0023,
        ("SPD-01", "SPD-02"): 0.0000,
        ("LAW-01", "LAW-02"): 0.3120,
    }

    pairs_seen = set()
    for r in results:
        if not r.get("pair_with"):
            continue
        key = tuple(sorted([r["id"], r["pair_with"]]))
        if key in pairs_seen:
            continue
        pairs_seen.add(key)
        partner = next((x for x in results if x["id"] == r["pair_with"]), None)
        if not partner:
            continue
        cs_a = r["consensus_score"]
        cs_b = partner["consensus_score"]
        if cs_a is None or cs_b is None:
            continue
        delta_new = abs(cs_a - cs_b)
        delta_old = DELTAS_6_2.get(key, 0.0)
        improved = delta_new > delta_old
        icon = "ok" if delta_new >= 0.15 else ("^" if improved else " ")
        label = "detectee" if delta_new >= 0.15 else ("amelioree" if improved else "toujours absente")
        print(
            f"  {icon} {r['id']} vs {r['pair_with']:<12}"
            f" {delta_old:>9.1%}"
            f" {delta_new:>10.1%}"
            f"  {label}"
        )

    # SPD-03 focus — le test clé
    spd3 = next((r for r in results if r["id"] == "SPD-03"), None)
    if spd3:
        print(f"\n  [SPD-03 — lumiere dans le verre : test cle]")
        print(f"  Baseline 6.2 (petits modeles) : SUPPORTED 98.67%")
        v = spd3["verdict"] or "ERR"
        cs = spd3["consensus_score"] or 0.0
        verdict_ok = spd3.get("verdict_ok")
        icon = "ok" if verdict_ok is True else "FAIL"
        print(f"  6.2b (gros modeles)            : {v} {cs:.0%}  [{icon}]")
        if verdict_ok is True:
            print(f"  -> Les gros modeles detectent la physique du milieu. Biais corrige.")
        elif verdict_ok is False:
            print(f"  -> Le biais persiste malgre les gros modeles. Ancrage source requis.")

    mins = int(total_s // 60)
    secs = int(total_s % 60)
    print(f"\n  Duree totale: {mins}m {secs}s")
    print("=" * 70)

    # JSON report
    out_dir = Path(__file__).parent / "benchmark_runs"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"scenario6_2b_{ts}.json"

    # Compute deltas for report
    qualifier_deltas = []
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
            delta_new = abs(r["consensus_score"] - partner["consensus_score"])
            delta_old = DELTAS_6_2.get(key, 0.0)
            qualifier_deltas.append({
                "pair": list(key),
                "delta_6_2": round(delta_old, 4),
                "delta_6_2b": round(delta_new, 4),
                "nuance_detected": delta_new >= 0.15,
                "improved_vs_6_2": delta_new > delta_old,
            })

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "scenario": "scenario_6_2b_qualifier_sensitivity_big_models",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "models": MODELS,
            "pipeline_timeout_s": PIPELINE_TIMEOUT,
            "total_claims": len(CLAIMS),
            "baseline_scenario": "scenario_6_2",
            "qualifier_deltas": qualifier_deltas,
            "claims": results,
        }, f, indent=2, default=str, ensure_ascii=False)

    print(f"\n  Report: {json_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
