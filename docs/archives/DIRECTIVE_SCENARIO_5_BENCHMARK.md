# DIRECTIVE SCENARIO 5 — Benchmark Multi-Claims

> **Destinataire :** Claude Code
> **Émetteur :** Audit Adversarial (Opus)
> **Statut :** Nouvelle feature
> **Objectif :** Script batch qui évalue 12 claims à travers le pipeline VERIFY,
>   collecte les résultats dans un CSV exploitable, et produit un résumé console
>   lisible pour le pitch hackathon.

---

## 1. CATALOGUE DES CLAIMS

12 claims réparties en 4 tiers d'ambiguïté. Chaque claim est conçue pour tester
un aspect spécifique du pipeline VERIFY.

### TIER 1 — Baseline empirique (attendu : SUPPORTED, consensus > 80%)
Faits établis. Le système doit les valider avec confiance haute.
Si un de ces 3 échoue, c'est un red flag sur les prompts ASSESS.

```python
TIER_1 = [
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
]
```

### TIER 2 — Mesurable avec nuance (attendu : SUPPORTED, consensus 55-75%)
Faits vérifiables mais dont la véracité dépend du timing, de la source,
ou de la métrique exacte. Les modèles devraient SUPPORTER avec caveats.

```python
TIER_2 = [
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
]
```

### TIER 3 — Ambiguïté définitionnelle (attendu : split SUPPORTED/CONTESTED)
Claims dont la réponse dépend de la définition des termes clés.
C'est ici que la valeur d'EPP se démontre — le split EST la bonne réponse.

```python
TIER_3 = [
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
        "test_target": "Scientific misconception — entanglement is real, FTL communication is not. Tests precision.",
        "frame": "quantum_physics_v1.0",
    },
]
```

### TIER 4 — Non-factuel / Infalsifiable (attendu : CONTESTED, consensus < 55%)
Claims philosophiques ou subjectives. Le système doit reconnaître les limites
de la vérification empirique. Si ces claims produisent SUPPORTED avec haute
confiance, les prompts sont trop permissifs.

```python
TIER_4 = [
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
        "test_target": "Pure opinion — no factual basis. If SUPPORTED or CONTESTED, system treats opinions as facts.",
        "frame": "culinary_v1.0",
    },
]
```

---

## 2. ARCHITECTURE DU SCRIPT

### Fichier : `demos/scenario_5_benchmark.py`

```
                                 ┌──────────────┐
                                 │  claims.json  │
                                 └──────┬───────┘
                                        │
                                        ▼
                              ┌─────────────────┐
                              │  Benchmark Loop  │
                              │                  │
                    ┌─────────┤  for each claim: │
                    │         │   fresh DB        │
                    │         │   run_pipeline()  │
                    │         │   collect metrics │
                    │         └─────────────────┘
                    │                    │
                    ▼                    ▼
            ┌──────────────┐   ┌────────────────────┐
            │  results.csv │   │  Console summary    │
            └──────────────┘   └────────────────────┘
```

### Principes

1. **DB fraîche par claim** — chaque claim obtient une DB temporaire neuve.
   Pas de contamination cross-claim dans le graphe.
2. **VERIFY forcé** — ne pas dépendre de `classify_input()` pour le benchmark.
   Passer `esmm_config` avec `input_mode="verify"` explicitement.
   MAIS aussi logger si `classify_input()` aurait auto-détecté (pour tester le classifier).
3. **Error recovery** — si un claim plante, logger l'erreur et passer au suivant.
   Un claim crashé ne doit pas tuer le benchmark.
4. **Pas de parallélisme** — les runs sont séquentiels. Ollama ne supporte
   qu'un modèle en VRAM à la fois, le parallélisme ne ferait que ralentir.

### CSV Output Format

Fichier : `demos/benchmark_results.csv`

```csv
id,claim,domain,expected_ambiguity,frame,verdict,dissent,consensus_score,dissent_score,vote_entropy,models_agreed,models_total,triplets_extracted,triplets_attested,evidence_count,duration_s,auto_detected_verify,errors
T1-01,"The speed of light...",physics,low,physics_constants_v1.0,SUPPORTED,,0.82,,0.12,4,4,25,3,18,148.2,True,
```

Colonnes :

| Colonne | Source | Description |
|:---|:---|:---|
| `id` | Catalogue | Identifiant unique T1-01..T4-03 |
| `claim` | Catalogue | Texte de la claim |
| `domain` | Catalogue | Domaine thématique |
| `expected_ambiguity` | Catalogue | low / medium / high / extreme |
| `frame` | Catalogue | Frame métrologique |
| `verdict` | `consensus_meta["verify"]["final_verdict"]` | SUPPORTED / CONTESTED / INSUFFICIENT_EVIDENCE / null |
| `dissent` | 2ème attestation verdict si présente | CONTESTED / SUPPORTED / null |
| `consensus_score` | Meilleure attestation `.consensus_score` | 0.0-1.0 |
| `dissent_score` | 2ème attestation `.consensus_score` | 0.0-1.0 / vide |
| `vote_entropy` | `consensus_meta["diagnostics"]["vote_entropy"]` | 0.0-1.0 |
| `models_agreed` | `attestation.models_agreeing` | int |
| `models_total` | `attestation.models_consulted` | int |
| `triplets_extracted` | `result.triplets_extracted` | int |
| `triplets_attested` | `result.triplets_attested` | int |
| `evidence_count` | `len(consensus_meta["verify"]["evidence_corpus"])` | int / 0 |
| `duration_s` | `elapsed` | float, secondes |
| `auto_detected_verify` | `classify_input(claim).name` | True/False |
| `errors` | `result.errors` ou exception msg | string / vide |

### JSON Output (complément)

Fichier : `demos/benchmark_results.json`

Contient les résultats complets (consensus_meta, evidence_corpus, model_verdicts)
pour analyse post-hoc. Le CSV est le résumé, le JSON est l'archive.

```python
{
    "benchmark_meta": {
        "timestamp": "2026-02-22T...",
        "models": ["mistral:latest", ...],
        "model_count": 4,
        "total_duration_s": 1842.3,
        "claims_total": 12,
        "claims_completed": 11,
        "claims_errored": 1,
    },
    "results": [
        {
            "id": "T1-01",
            "claim": "...",
            "verdict": "SUPPORTED",
            "consensus_meta": { ... },  # complet
            "attestations": [ ... ],     # to_portable_json() de chaque attestation
        },
        ...
    ]
}
```

---

## 3. CONSOLE OUTPUT

Le script doit produire un output console lisible en temps réel :

```
============================================================
EPP BENCHMARK — 12 Claims × 4 Models
============================================================
Models: mistral:latest, llama3.1:8b, gemma3:latest, granite3.3:latest

[01/12] T1-01 | physics | "The speed of light in vacuum exceeds 299000..."
        → SUPPORTED (82%) | entropy=0.12 | 148s
[02/12] T1-02 | astronomy | "Earth completes one orbit around the Sun..."
        → SUPPORTED (78%) | entropy=0.21 | 152s
...
[07/12] T3-01 | blockchain | "Ethereum is more decentralized than Solana"
        → SUPPORTED (58%) ↔ CONTESTED (55%) | entropy=0.89 | 161s
...
[12/12] T4-03 | culinary_opinion | "Pineapple is a valid pizza topping"
        → CONTESTED (52%) | entropy=0.95 | 139s

============================================================
BENCHMARK SUMMARY
============================================================
  Duration: 30m 42s total | avg 153.5s/claim

  ┌─────────────────────────────────────────────────────────┐
  │  TIER 1 (baseline):  3/3 SUPPORTED  avg consensus 79%  │
  │  TIER 2 (nuanced):   3/3 SUPPORTED  avg consensus 63%  │
  │  TIER 3 (ambiguous):  1 SUPPORTED / 2 split             │
  │  TIER 4 (opinion):   0 SUPPORTED / 3 CONTESTED          │
  └─────────────────────────────────────────────────────────┘

  Consensus vs Ambiguity:
    low:     ████████████████████  79%
    medium:  ████████████▒         63%
    high:    ████████▒▒▒           54%
    extreme: █████▒▒▒▒▒            41%

  Results saved:
    CSV: demos/benchmark_results.csv
    JSON: demos/benchmark_results.json

  Verdict: Consensus score inversely correlates with expected ambiguity.
           The system correctly calibrates epistemic confidence.
============================================================
```

Le résumé par tier et la barre de consensus sont les **deux slides de pitch**.

---

## 4. IMPLÉMENTATION

### Structure du script

```python
"""
Scenario 5 -- EPP Benchmark: Multi-claim evaluation across domains.

Evaluates 12 claims spanning 4 ambiguity tiers through the VERIFY pipeline.
Produces CSV + JSON results for analysis and pitch visualization.

Prerequisites:
    - Ollama running (ollama serve)
    - At least 2 models pulled
    - Scenario 4 working (VERIFY mode operational)

Expected duration: ~30 minutes (12 claims × ~2.5 min each)
"""

import asyncio
import csv
import json
import sys
import tempfile
import os
import time
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

# --- Claims catalog (defined inline, not external file) ---

CLAIMS = [
    # TIER 1 — Baseline
    {...},  # T1-01, T1-02, T1-03 from §1 above
    # TIER 2 — Nuanced
    {...},  # T2-01, T2-02, T2-03
    # TIER 3 — Ambiguous
    {...},  # T3-01, T3-02, T3-03
    # TIER 4 — Non-factual
    {...},  # T4-01, T4-02, T4-03
]


async def check_ollama() -> list[str]:
    """Réutiliser la même logique que scenario_4."""
    ...  # Copier depuis scenario_4_live_ollama.py


def build_providers(selected_models: list[str]) -> dict:
    """Construire les providers Ollama à partir des modèles sélectionnés."""
    from services.providers.ollama import OllamaProvider
    providers = {}
    for model_name in selected_models:
        pid = f"ollama-{model_name.replace(':', '_').replace('.', '_')}"
        providers[pid] = OllamaProvider(model=model_name)
    return providers


async def run_single_claim(
    claim_entry: dict,
    selected_models: list[str],
    claim_index: int,
    total_claims: int,
) -> dict:
    """
    Exécute le pipeline VERIFY pour une seule claim.
    Retourne un dict de résultats (une ligne CSV).
    DB fraîche à chaque appel.
    """
    from database.engine import ISpaceDB
    from database.pool import close_pool
    from services.esmm.pipeline import run_pipeline, PipelineConfig
    from services.esmm.orchestrator import ESMMRunConfig

    # Optionnel : tester l'auto-détection SANS forcer le mode
    try:
        from services.esmm.question_seeder import classify_input, InputType
        auto_detected = classify_input(claim_entry["claim"]) == InputType.VERIFY
    except Exception:
        auto_detected = None

    claim_id = claim_entry["id"]
    claim_text = claim_entry["claim"]
    domain = claim_entry["domain"]

    # Affichage temps réel
    short_claim = claim_text[:60] + "..." if len(claim_text) > 60 else claim_text
    print(f"[{claim_index:02d}/{total_claims:02d}] {claim_id} | {domain} | \"{short_claim}\"")

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

    # Données complètes pour le JSON
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

        # FORCER le mode VERIFY — ne pas dépendre de classify_input()
        esmm_config = ESMMRunConfig(
            models=selected_models,
            input_mode="verify",           # Force VERIFY
            original_claim=claim_text,      # Claim originale
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

        # Extraire verdict et dissent des attestations
        verdict_atts = [a for a in result.attestations if a.predicate == "verdict"]
        if verdict_atts:
            # Trier par consensus_score descending
            verdict_atts.sort(key=lambda a: a.consensus_score, reverse=True)
            best = verdict_atts[0]
            row["verdict"] = best.object
            row["consensus_score"] = round(best.consensus_score, 4)
            row["models_agreed"] = best.models_agreeing

            if len(verdict_atts) > 1:
                second = verdict_atts[1]
                row["dissent"] = second.object
                row["dissent_score"] = round(second.consensus_score, 4)

        # Extraire consensus_meta
        if result.attestations and hasattr(result.attestations[0], "consensus_meta"):
            meta = result.attestations[0].consensus_meta
            if meta:
                full_result["consensus_meta"] = meta
                row["vote_entropy"] = meta.get("diagnostics", {}).get("vote_entropy")

                verify_section = meta.get("verify", {})
                evidence = verify_section.get("evidence_corpus", [])
                row["evidence_count"] = len(evidence)

        # Attestations portables pour JSON
        for att in result.attestations:
            if hasattr(att, "to_portable_json"):
                full_result["attestations"].append(att.to_portable_json())

        # Cleanup providers
        for provider in providers.values():
            if hasattr(provider, "close"):
                await provider.close()

    except Exception as e:
        row["errors"] = str(e)
        row["duration_s"] = 0.0
        logging.getLogger("benchmark").error(f"Claim {claim_id} failed: {e}")

    finally:
        try:
            await close_pool()
        except Exception:
            pass
        if os.path.exists(db_path):
            os.unlink(db_path)

    # Affichage résultat
    v = row["verdict"] or "ERROR"
    cs = row["consensus_score"]
    ent = row["vote_entropy"]
    dur = row["duration_s"]
    if row["dissent"]:
        print(f"        → {v} ({cs:.0%}) ↔ {row['dissent']} ({row['dissent_score']:.0%}) "
              f"| entropy={ent:.2f} | {dur:.0f}s")
    elif cs is not None:
        print(f"        → {v} ({cs:.0%}) | entropy={ent or 0:.2f} | {dur:.0f}s")
    else:
        print(f"        → ERROR: {row['errors'][:80]}")

    return row, full_result


async def main():
    print("=" * 60)
    print("EPP BENCHMARK — 12 Claims × N Models")
    print("=" * 60)
    print()

    # Health check
    available = await check_ollama()
    # Filtrer les modèles d'embedding
    EMBEDDING_KEYWORDS = ["embed", "nomic", "mxbai"]
    selected = [
        m for m in available
        if not any(kw in m.lower() for kw in EMBEDDING_KEYWORDS)
    ]
    # Exclure aussi deepseek-r1 (trop lent) et gpt-oss (si instable)
    EXCLUDE = ["deepseek-r1", "gpt-oss"]
    selected = [
        m for m in selected
        if not any(ex in m.lower() for ex in EXCLUDE)
    ]

    if len(selected) < 2:
        print("Need at least 2 non-embedding models.")
        sys.exit(1)

    print(f"Models: {', '.join(selected)}")
    print()

    # Run benchmark
    csv_rows = []
    json_results = []
    total_start = time.time()

    for i, claim_entry in enumerate(CLAIMS, 1):
        row, full = await run_single_claim(claim_entry, selected, i, len(CLAIMS))
        csv_rows.append(row)
        json_results.append(full)

    total_elapsed = time.time() - total_start

    # --- Write CSV ---
    csv_path = Path(__file__).parent / "benchmark_results.csv"
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
    json_path = Path(__file__).parent / "benchmark_results.json"
    benchmark_json = {
        "benchmark_meta": {
            "timestamp": datetime.utcnow().isoformat(),
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
        json.dump(benchmark_json, f, indent=2, default=str)

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

    # Summary par tier
    tiers = {"T1": "baseline", "T2": "nuanced", "T3": "ambiguous", "T4": "opinion"}
    for prefix, label in tiers.items():
        tier_rows = [r for r in csv_rows if r["id"].startswith(prefix)]
        supported = sum(1 for r in tier_rows if r["verdict"] == "SUPPORTED")
        contested = sum(1 for r in tier_rows if r["verdict"] == "CONTESTED")
        splits = sum(1 for r in tier_rows if r["dissent"])
        scores = [r["consensus_score"] for r in tier_rows if r["consensus_score"]]
        avg_cs = sum(scores) / len(scores) if scores else 0
        total = len(tier_rows)
        print(f"  TIER {prefix[-1]} ({label:10s}): "
              f"{supported}S/{contested}C/{splits} split  "
              f"avg consensus {avg_cs:.0%}  "
              f"({total} claims)")

    # Barre de consensus par ambiguity
    print()
    print("  Consensus vs Ambiguity:")
    for level in ["low", "medium", "high", "extreme"]:
        level_rows = [r for r in csv_rows
                      if r["expected_ambiguity"] == level and r["consensus_score"]]
        if level_rows:
            avg = sum(r["consensus_score"] for r in level_rows) / len(level_rows)
            bar_len = int(avg * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"    {level:8s}: {bar}  {avg:.0%}")

    print()
    print(f"  Results saved:")
    print(f"    CSV:  {csv_path}")
    print(f"    JSON: {json_path}")
    print()
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
```

---

## 5. CONTRAINTES

### Non-négociable

- **Zéro modification** de fichiers existants. Scenario 5 est un NEW FILE uniquement.
- **DB fraîche par claim** — `tempfile.mkstemp()` + cleanup en `finally`.
- **Error recovery** — un claim qui crashe ne tue PAS le benchmark.
  Le `try/except` dans `run_single_claim()` capture l'erreur, l'écrit dans le CSV,
  et le script continue.
- **VERIFY forcé** — passer `esmm_config=ESMMRunConfig(input_mode="verify", ...)`
  directement, ne PAS dépendre de `classify_input()` pour le benchmark.
  L'auto-détection est LOGGÉE dans la colonne `auto_detected_verify` mais pas utilisée.

### Important mais flexible

- **Exclure deepseek-r1** du benchmark — trop lent (30s+ par réponse vs 4-9s).
  Si on veut le tester, faire un run séparé.
- **Les frames sont décoratives** pour l'instant — le pipeline ne les utilise pas
  pour filtrer les réponses. Mais elles apparaissent dans les attestations
  et donnent du contexte au jury.
- **Le résumé console est le minimum** — si Claude Code veut ajouter des visualisations
  plus riches (barres horizontales, tableaux box-drawing), c'est bienvenu mais optionnel.

### Adaptation ESMMRunConfig

⚠️ **ATTENTION** — Le code actuel de `ESMMRunConfig` dans `orchestrator.py` n'a peut-être
pas encore `input_mode` et `original_claim` comme champs du dataclass (ils ont été ajoutés
par les corrections A1-A3 sur la machine locale, pas dans le code source du projet).

Si `ESMMRunConfig` ne reconnaît pas `input_mode` :
- Option A : ajouter les champs au dataclass (préféré, 2 lignes)
- Option B : passer `esmm_config=None` et laisser `_extract_triplets_from_question()`
  auto-détecter — mais alors la claim "Pineapple is a valid pizza topping" sera en mode
  EXPLORE, pas VERIFY.

Claude Code doit vérifier l'état actuel de `ESMMRunConfig` et s'adapter.

---

## 6. VÉRIFICATION

```bash
# 1. Le script tourne sans crash
python demos/scenario_5_benchmark.py

# 2. Les fichiers de sortie existent
ls -la demos/benchmark_results.csv demos/benchmark_results.json

# 3. Le CSV a 13 lignes (header + 12 claims)
wc -l demos/benchmark_results.csv
# Attendu : 13

# 4. Pas de régression (scenario 5 ne touche rien)
pytest tests/ --tb=short -q
# Attendu : 663+ passed, 0 failed

# 5. Le JSON est parseable
python -c "import json; d=json.load(open('demos/benchmark_results.json')); print(f'{d[\"benchmark_meta\"][\"claims_completed\"]}/{d[\"benchmark_meta\"][\"claims_total\"]} completed')"
```

---

## 7. CE QUE CETTE DONNÉE DONNE POUR LE PITCH

### Slide 1 : "EPP calibrates epistemic confidence"
Le graphique Consensus vs Ambiguity — 4 barres descendantes de ~80% à ~40%.
C'est visuel, immédiat, convaincant.

### Slide 2 : "EPP doesn't manufacture consensus"
Le split SUPPORTED/CONTESTED sur les claims Tier 3 et 4.
Montrer que le système REFUSE de trancher quand la question est indécidable.

### Slide 3 : "12 domains, 4 models, consistent behavior"
Le tableau complet CSV. Montre la robustesse cross-domaine.

### Donnée bonus pour les évaluateurs techniques
Le JSON complet avec `evidence_corpus` et `model_verdicts` —
la transparence méthodologique que les oracles existants ne fournissent pas.

---

*Fin de directive. ~30 minutes de compute, un dataset de pitch.*
