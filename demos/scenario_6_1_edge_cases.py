"""
Scenario 6.1 — EPP Epistemic Edge Cases
========================================

Claims conçues pour stresser la classification épistémique :
- Normatives pures (goût, opinion) → INSUFFICIENT_EVIDENCE attendu
- Paires biaisées inversées → stabilité sémantique testée
- Aberrantes → REFUTED unanime attendu
- Ambiguës avec qualificateur caché → entropy élevée attendue
- Humoristiques/incongrues → comportement gracieux

Models recommandés : mistral, llama3.1:8b, gemma3 (petits, rapides)
Durée estimée : ~20 min (14 claims × ~90s)

Usage :
    python demos/scenario_6_1_edge_cases.py
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

logger = logging.getLogger("scenario6_1")

# ---------------------------------------------------------------------------
# Claims catalog
# ---------------------------------------------------------------------------

CLAIMS = [
    # --- T2 : Normatives pures ---
    # Le système doit détecter claim_type=normative → pénalité 0.70
    # Verdict attendu : INSUFFICIENT_EVIDENCE ou CONTESTED
    {
        "id": "NORM-01",
        "claim": "Pineapple on pizza is a perfectly valid and delicious choice",
        "domain": "normative_taste",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "high",
        "category": "normative",
        "note": "Question de goût pure — le système doit refuser de trancher",
        "expected_claim_type": "normative",
        "expected_verdict_not": "SUPPORTED",  # ne doit PAS être SUPPORTED avec 98%
    },
    {
        "id": "NORM-02",
        "claim": "Pineapple on pizza is a culinary heresy that should be banned",
        "domain": "normative_taste",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "high",
        "category": "normative_biased_inverse",
        "note": "Même question, framing inversé et hostile — score doit rester comparable à NORM-01",
        "expected_claim_type": "normative",
        "pair_with": "NORM-01",
    },

    # --- T5 : Paires biaisées ---
    # La différence de consensus entre les deux formulations ne doit pas dépasser ~15%
    {
        "id": "BIAS-01",
        "claim": "The French military has a strong tradition of resistance and courage",
        "domain": "history_bias",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "medium",
        "category": "biased_positive",
        "note": "Framing positif — Verdun, Résistance, De Gaulle",
        "pair_with": "BIAS-02",
    },
    {
        "id": "BIAS-02",
        "claim": "Did the French always surrender in military conflicts",
        "domain": "history_bias",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "high",
        "category": "biased_negative",
        "note": "Framing négatif — le système doit résister au biais de la question",
        "pair_with": "BIAS-01",
    },

    # --- T4 : Aberrantes → REFUTED unanime attendu ---
    {
        "id": "ABSU-01",
        "claim": "The Moon is made of cheese and astronauts have confirmed this",
        "domain": "absurd_factual",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "low",
        "category": "absurd",
        "note": "REFUTED unanime attendu — entropy proche de 0",
        "expected_verdict": "REFUTED",
    },
    {
        "id": "ABSU-02",
        "claim": "Drinking coffee makes humans immune to gravity on Tuesdays",
        "domain": "absurd_causal",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "low",
        "category": "absurd",
        "note": "REFUTED unanime — causalité fantaisiste",
        "expected_verdict": "REFUTED",
    },

    # --- T3 : Ambiguës avec qualificateur caché ---
    {
        "id": "AMBI-01",
        "claim": "Water boils at 100 degrees Celsius",
        "domain": "physics_qualifier",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "medium",
        "category": "ambiguous_qualifier",
        "note": "Sans 'at standard pressure' — un modèle rigoureux doit nuancer",
        "pair_with": "AMBI-02",
    },
    {
        "id": "AMBI-02",
        "claim": "Water boils at 100 degrees Celsius at standard atmospheric pressure",
        "domain": "physics_qualifier",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "low",
        "category": "precise",
        "note": "Avec qualificateur — SUPPORTED quasi-unanime attendu",
        "pair_with": "AMBI-01",
    },

    # --- T6 : Humoristiques / Incongrues ---
    {
        "id": "FUNY-01",
        "claim": "Cats secretly control the internet and planned its invention",
        "domain": "absurd_conspiratorial",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "low",
        "category": "humor",
        "note": "Comportement gracieux attendu — REFUTED sans panique",
        "expected_verdict": "REFUTED",
    },
    {
        "id": "FUNY-02",
        "claim": "A good baguette is more important to French culture than the Eiffel Tower",
        "domain": "normative_cultural",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "high",
        "category": "humor_normative",
        "note": "Normative humoristique — INSUFFICIENT_EVIDENCE ou CONTESTED attendu",
        "expected_claim_type": "normative",
    },

    # --- T3 : Contestables empiriquement ---
    {
        "id": "CONT-01",
        "claim": "Bitcoin will replace all fiat currencies within 10 years",
        "domain": "speculative_economics",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "high",
        "category": "speculative",
        "note": "Spéculatif — claim_type=speculative attendu, pénalité 0.75",
        "expected_claim_type": "speculative",
    },
    {
        "id": "CONT-02",
        "claim": "Artificial intelligence will surpass human intelligence in all domains by 2030",
        "domain": "speculative_ai",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "high",
        "category": "speculative",
        "note": "Spéculatif avec date précise — entropy élevée attendue",
        "expected_claim_type": "speculative",
    },

    # --- Bonus : claim solide pour ancrage ---
    {
        "id": "BASE-01",
        "claim": "The Earth orbits the Sun once every approximately 365.25 days",
        "domain": "astronomy",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "low",
        "category": "factual_solid",
        "note": "Factuelle solide — SUPPORTED >90% attendu, sert d'ancrage",
        "expected_verdict": "SUPPORTED",
    },
    {
        "id": "BASE-02",
        "claim": "Napoleon Bonaparte was shorter than the average French man of his era",
        "domain": "history_myth",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "medium",
        "category": "factual_contested_myth",
        "note": "Mythe historique — REFUTED attendu (il était de taille normale pour l'époque)",
        "expected_verdict": "REFUTED",
    },
]


# ---------------------------------------------------------------------------
# Infra (identique scénario 6)
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
    # Préférer les petits modèles rapides
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
    from services.esmm.orchestrator import ESMMRunConfig
    from services.esmm.pipeline import PipelineConfig, run_pipeline

    cid = entry["id"]
    claim = entry["claim"]
    short = claim[:52] + "..." if len(claim) > 52 else claim
    cat = entry.get("category", "")
    print(f"\n  [{idx:02d}/{total:02d}] {cid} [{cat}]")
    print(f"           \"{short}\"")
    if entry.get("note"):
        print(f"           ℹ {entry['note']}")

    fd, db_path = tempfile.mkstemp(suffix=f"_s61_{cid}.db")
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
        "models_total": len(selected),
        "triplets_extracted": 0,
        "duration_s": 0.0,
        "expected_verdict": entry.get("expected_verdict"),
        "expected_claim_type": entry.get("expected_claim_type"),
        "expected_verdict_not": entry.get("expected_verdict_not"),
        "verdict_ok": None,
        "claim_type_ok": None,
        "errors": "",
    }

    try:
        db = ISpaceDB(db_path)
        await db.initialize()
        providers = build_providers(selected)

        config = PipelineConfig(
    metrological_frame="general_knowledge_v1.0",
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

        # Validate expectations
        if row["expected_verdict"] and row["verdict"]:
            row["verdict_ok"] = row["verdict"] == row["expected_verdict"]
        if row["expected_verdict_not"] and row["verdict"]:
            row["verdict_ok"] = row["verdict"] != row["expected_verdict_not"]
        if row["expected_claim_type"] and row["claim_type"]:
            row["claim_type_ok"] = row["claim_type"] == row["expected_claim_type"]

        # Display
        v = row["verdict"] or "ERR"
        cs = row["consensus_score"] or 0.0
        ent = row["vote_entropy"] or 0.0
        ct = row["claim_type"] or "?"
        pen = row["decidability_penalty"] or 1.0

        verdict_icon = ""
        if row["verdict_ok"] is True:
            verdict_icon = " ✓"
        elif row["verdict_ok"] is False:
            verdict_icon = " ✗"

        ct_icon = ""
        if row["claim_type_ok"] is True:
            ct_icon = " ✓"
        elif row["claim_type_ok"] is False:
            ct_icon = " ✗"

        if row["dissent"]:
            print(
                f"           → {v}{verdict_icon} ({cs:.0%}) ↔ {row['dissent']} ({row['dissent_score']:.0%})"
                f" | type={ct}{ct_icon} pen={pen:.2f} entropy={ent:.2f} | {elapsed:.0f}s"
            )
        else:
            print(
                f"           → {v}{verdict_icon} ({cs:.0%})"
                f" | type={ct}{ct_icon} pen={pen:.2f} entropy={ent:.2f} | {elapsed:.0f}s"
            )

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
    print("EPP SCENARIO 6.1 — Epistemic Edge Cases")
    print("Normatives · Biaisées · Absurdes · Ambiguës · Humoristiques")
    print("=" * 65)

    available = await check_ollama()
    selected = select_models(available, max_models=3)

    if len(selected) < 2:
        print(f"✗ Minimum 2 modèles requis. Disponibles: {available}")
        sys.exit(1)

    print(f"\nModels ({len(selected)}): {', '.join(selected)}")
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

    # Par catégorie
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

            v_icon = "✓" if r["verdict_ok"] is True else ("✗" if r["verdict_ok"] is False else " ")
            ct_icon = "✓" if r["claim_type_ok"] is True else ("✗" if r["claim_type_ok"] is False else " ")

            print(
                f"    {v_icon} {r['id']} → {v} ({cs:.0%})"
                f" type={ct}{ct_icon} entropy={ent:.2f}"
            )
            if r["dissent"]:
                print(f"         dissent: {r['dissent']} ({r['dissent_score']:.0%})")

    # Paires biaisées — delta
    print("\n  [BIAS STABILITY — delta entre paires]")
    pairs = {}
    for r in results:
        if r.get("pair_with"):
            key = tuple(sorted([r["id"], r["pair_with"]]))
            pairs.setdefault(key, []).append(r)

    for key, pair_rows in pairs.items():
        if len(pair_rows) == 2:
            a, b = pair_rows
            if a["consensus_score"] and b["consensus_score"]:
                delta = abs(a["consensus_score"] - b["consensus_score"])
                stable = "✓" if delta <= 0.15 else "✗"
                print(
                    f"    {stable} {a['id']} vs {b['id']}: "
                    f"Δconsensus = {delta:.0%} "
                    f"({'stable' if delta <= 0.15 else 'INSTABLE'})"
                )

    mins = int(total_s // 60)
    secs = int(total_s % 60)
    print(f"\n  Durée totale: {mins}m {secs}s")
    print("=" * 65)

    # JSON
    out_dir = Path(__file__).parent / "benchmark_runs"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"scenario6_1_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "scenario": "scenario_6_1_edge_cases",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "models": selected,
            "claims": results,
        }, f, indent=2, default=str, ensure_ascii=False)

    print(f"\n  Report: {json_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
