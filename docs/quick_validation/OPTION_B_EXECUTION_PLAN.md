# Option B : Quick Validation - Plan d'Exécution

**Durée :** 1-2 jours  
**Coût :** ~$0.50 USD  
**Effort :** 8-10 heures  
**Output :** Go/No-Go Decision pour Full Evaluation

---

## Objectifs

1. ✅ Valider protocole triple-blind fonctionne techniquement
2. ✅ Tester Claude Haiku 4.5 comme juge fiable
3. ✅ Proof of concept : différence détectable entre configs ?
4. ✅ Attribution causale rapide (temperature vs system vs full)
5. ✅ Économiser ressources si résultats négatifs

---

## Design Expérimental Simplifié

### 4 Configurations (au lieu de 6)

```python
CONFIGS = {
    "baseline": {
        "name": "Raw Default",
        "description": "Ollama defaults, no Lyra",
        "consciousness_level": 0,
        "profile": None,
        "expected_params": {
            "temperature": 0.80,
            "repeat_penalty": 1.00
        }
    },
    
    "temp_only": {
        "name": "Temperature Only",
        "description": "Lyra temperature mapping, no system prompt",
        "consciousness_level": 0,
        "profile": "balanced",  # tau_c ≈ 1.0 → temp ≈ 0.80
        "override_system": False,  # Use minimal system
        "expected_params": {
            "temperature": 0.80,  # balanced similar to baseline
            "repeat_penalty": 1.00
        }
    },
    
    "system_only": {
        "name": "System Prompt Only",
        "description": "Lyra style hints, default temperature",
        "consciousness_level": 0,
        "profile": "balanced",
        "override_system": True,  # Use Lyra system prompt
        "force_temperature": 0.80,
        "expected_params": {
            "temperature": 0.80,
            "repeat_penalty": 1.00
        }
    },
    
    "full_lyra": {
        "name": "Full Lyra Balanced",
        "description": "Complete Lyra orchestration",
        "consciousness_level": 1,
        "profile": "balanced",
        "expected_params": {
            "temperature": 0.80,
            "repeat_penalty": 1.00
        }
    }
}
```

**Rationale :** 
- Baseline = contrôle pur
- Temp Only = isoler effet tau_c → temperature
- System Only = isoler effet kappa → style hints
- Full Lyra = effet combiné

Si temp et system individuellement négligeables mais full_lyra significatif → effet synergique.

### 15 Prompts Stratifiés

**5 Technical (Factual Knowledge)**
```python
TECHNICAL_PROMPTS = [
    "Explain the difference between TCP and UDP protocols.",
    "What is the time complexity of quicksort in the worst case?",
    "Describe how photosynthesis works at the molecular level.",
    "What are the key differences between supervised and unsupervised learning?",
    "Explain the concept of virtual memory in operating systems."
]
```

**5 Creative (Open-Ended Imagination)**
```python
CREATIVE_PROMPTS = [
    "Write a short story about a robot learning to paint.",
    "Imagine a world where time flows backwards. Describe a typical day.",
    "Create a metaphor that explains quantum entanglement to a child.",
    "Design a new sport that could be played in zero gravity.",
    "Write a poem about the intersection of mathematics and nature."
]
```

**5 Analytical (Reasoning & Comparison)**
```python
ANALYTICAL_PROMPTS = [
    "Compare the advantages and disadvantages of functional vs object-oriented programming.",
    "Analyze the ethical implications of AI-generated art.",
    "What are the trade-offs between microservices and monolithic architectures?",
    "Evaluate the impact of social media on political discourse.",
    "Compare renewable energy sources: solar vs wind vs hydroelectric."
]
```

**Total :** 15 prompts × 4 configs = **60 responses**

---

## Timeline Détaillé

### Jour 1 : Génération + Jugement

#### Phase 1A : Génération Réponses (2-3h)

```bash
# Script : generate_responses_optionB.py
# Input : 15 prompts, 4 configs
# Output : evaluation/1_source_data/responses_raw.jsonl (60 lines)

python generate_responses_optionB.py
```

**Durée estimée :**
- 60 réponses × ~45s/réponse = **45 minutes** (LLM generation)
- + Setup + logging = **2-3 heures total**

**Format `responses_raw.jsonl` :**
```json
{
  "config_id": "baseline",
  "prompt": "Explain TCP vs UDP",
  "domain": "technical",
  "response": "TCP (Transmission Control Protocol)...",
  "physics_state": null,
  "latency_ms": 8234.5,
  "timestamp": "2025-12-06T15:23:45Z"
}
```

#### Phase 1B : Anonymisation (10 min)

```bash
python scripts/1_anonymize.py \
  --input evaluation/1_source_data/responses_raw.jsonl \
  --output evaluation/2_blind_data/responses_blind.jsonl \
  --mapping evaluation/1_source_data/mapping_secret.json
```

**Output :**
- `responses_blind.jsonl` : anonymous_id, prompt, response, domain
- `mapping_secret.json` : {anonymous_id → config_id}

#### Phase 1C : Blind Judging (2-3h)

```bash
python scripts/2_judge.py \
  --input evaluation/2_blind_data/responses_blind.jsonl \
  --output evaluation/3_judgments/judgments_blind.jsonl \
  --model claude-haiku-4.5 \
  --temperature 0.3 \
  --batch-size 10 \
  --pause 30
```

**Durée estimée :**
- 60 réponses × 30s/judgment = **30 minutes** (API calls)
- + Pauses + retry = **1-2 heures**

**Coût Claude Haiku 4.5 :**
- Input : ~500 tokens/response × 60 = 30k tokens → $0.03
- Output : ~150 tokens/judgment × 60 = 9k tokens → $0.045
- **Total : ~$0.08**

#### Phase 1D : Unblinding (5 min)

```bash
python scripts/3_unblind.py \
  --judgments evaluation/3_judgments/judgments_blind.jsonl \
  --mapping evaluation/1_source_data/mapping_secret.json \
  --output evaluation/4_results/judgments_unblinded.jsonl
```

---

### Jour 2 : Analyse + Go/No-Go

#### Phase 2A : Analyse Statistique (1h)

```bash
python scripts/4_analyze_optionB.py \
  --input evaluation/4_results/judgments_unblinded.jsonl \
  --output evaluation/5_analysis/
```

**Outputs :**
- `summary_stats.json` : Moyennes par config
- `pairwise_tests.json` : T-tests entre configs
- `domain_breakdown.json` : Performance par domaine
- `attribution_chart.png` : Effect sizes
- `report.md` : Interprétation

**Métriques Clés :**
```json
{
  "baseline": {
    "overall_mean": 3.45,
    "overall_std": 0.67,
    "n": 15
  },
  "temp_only": {
    "overall_mean": 3.52,
    "overall_std": 0.71,
    "n": 15
  },
  "system_only": {
    "overall_mean": 3.78,
    "overall_std": 0.59,
    "n": 15
  },
  "full_lyra": {
    "overall_mean": 3.91,
    "overall_std": 0.54,
    "n": 15
  }
}
```

**Tests Statistiques :**
- Pairwise t-tests (Bonferroni corrected)
- Effect sizes (Cohen's d)
- Domain-specific breakdowns

#### Phase 2B : Inter-Rater Validation (Optionnel, 2h)

Annoter manuellement 10 exemples aléatoires :
- Comparer avec jugements Claude Haiku
- Calculer Cohen's Kappa
- Accepter si κ > 0.6

#### Phase 2C : Go/No-Go Decision (30 min)

**Critères GO (Proceed to Full Evaluation) :**

✅ **Détectabilité :** Au moins une différence p < 0.05 entre configs
✅ **Effect Size :** Cohen's d > 0.3 pour au moins une composante
✅ **Consistency :** Résultats cohérents entre domaines
✅ **Judge Reliability :** κ > 0.6 (si validation manuelle faite)

**Critères NO-GO (Pivot Strategy) :**

❌ Aucune différence significative (tous p > 0.2)
❌ Effect sizes négligeables (tous d < 0.2)
❌ Résultats incohérents (inversions entre domaines)
❌ Judge unreliable (κ < 0.4)

**Actions si GO :**
→ Proceed to Option A (Full Evaluation)
→ Expand to 6 configs × 50 prompts = 300 responses
→ Implement calibration + bias correction
→ Budget : ~$15-20 USD, 1 semaine

**Actions si NO-GO :**
→ Pivot to human evaluation (Mechanical Turk)
→ Focus on specific use cases (domain-specific prompts)
→ Alternative : Position Lyra as "orchestration framework" (not quality improvement)

---

## Scripts Python Complets

### Script 1 : `generate_responses_optionB.py`

```python
"""
Generate 60 responses for Option B quick validation.

Usage:
    python generate_responses_optionB.py
    
Output:
    evaluation/1_source_data/responses_raw.jsonl
"""

import asyncio
import json
import time
from pathlib import Path
from datetime import datetime
import httpx

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIGS = {
    "baseline": {
        "name": "Raw Default",
        "consciousness_level": 0,
        "profile": None,
        "api_payload_override": {
            "enable_context": False
        }
    },
    "temp_only": {
        "name": "Temperature Only",
        "consciousness_level": 0,
        "profile": "balanced",
        "api_payload_override": {
            "enable_context": False
        }
    },
    "system_only": {
        "name": "System Prompt Only",
        "consciousness_level": 0,
        "profile": "balanced",
        "api_payload_override": {
            "enable_context": False,
            "force_system_prompt": True
        }
    },
    "full_lyra": {
        "name": "Full Lyra Balanced",
        "consciousness_level": 1,
        "profile": "balanced",
        "api_payload_override": {
            "enable_context": True
        }
    }
}

PROMPTS = {
    "technical": [
        "Explain the difference between TCP and UDP protocols.",
        "What is the time complexity of quicksort in the worst case?",
        "Describe how photosynthesis works at the molecular level.",
        "What are the key differences between supervised and unsupervised learning?",
        "Explain the concept of virtual memory in operating systems."
    ],
    "creative": [
        "Write a short story about a robot learning to paint.",
        "Imagine a world where time flows backwards. Describe a typical day.",
        "Create a metaphor that explains quantum entanglement to a child.",
        "Design a new sport that could be played in zero gravity.",
        "Write a poem about the intersection of mathematics and nature."
    ],
    "analytical": [
        "Compare the advantages and disadvantages of functional vs object-oriented programming.",
        "Analyze the ethical implications of AI-generated art.",
        "What are the trade-offs between microservices and monolithic architectures?",
        "Evaluate the impact of social media on political discourse.",
        "Compare renewable energy sources: solar vs wind vs hydroelectric."
    ]
}

API_URL = "http://localhost:8000/chat/message"
OUTPUT_DIR = Path("evaluation/1_source_data")
OUTPUT_FILE = OUTPUT_DIR / "responses_raw.jsonl"

# ============================================================================
# GENERATION
# ============================================================================

async def generate_response(
    prompt: str,
    domain: str,
    config_id: str,
    config: dict,
    session: httpx.AsyncClient
) -> dict:
    """Generate single response."""
    
    payload = {
        "text": prompt,
        "session_id": f"optionB_{config_id}_{domain}",
        "consciousness_level": config["consciousness_level"],
        "profile": config.get("profile", "balanced"),
        **config.get("api_payload_override", {})
    }
    
    start = time.time()
    
    try:
        response = await session.post(API_URL, json=payload, timeout=180.0)
        response.raise_for_status()
        data = response.json()
        
        latency_ms = (time.time() - start) * 1000
        
        return {
            "config_id": config_id,
            "config_name": config["name"],
            "prompt": prompt,
            "domain": domain,
            "response": data.get("text", ""),
            "physics_state": data.get("physics_state"),
            "latency_ms": latency_ms,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tokens": data.get("tokens"),
            "consciousness": data.get("consciousness")
        }
    
    except Exception as e:
        print(f"ERROR [{config_id}] {prompt[:50]}: {e}")
        return None


async def generate_all():
    """Generate all 60 responses."""
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    tasks = []
    
    async with httpx.AsyncClient() as session:
        
        # Build all tasks
        for domain, prompts in PROMPTS.items():
            for prompt in prompts:
                for config_id, config in CONFIGS.items():
                    tasks.append((prompt, domain, config_id, config, session))
        
        print(f"Total tasks: {len(tasks)}")
        
        # Execute with progress
        with open(OUTPUT_FILE, 'w') as f:
            for i, (prompt, domain, config_id, config, session) in enumerate(tasks):
                print(f"[{i+1}/{len(tasks)}] {config_id} | {domain} | {prompt[:40]}...")
                
                result = await generate_response(prompt, domain, config_id, config, session)
                
                if result:
                    f.write(json.dumps(result) + '\n')
                    f.flush()
                
                # Small pause to avoid overwhelming server
                await asyncio.sleep(0.5)
        
        print(f"\n✅ Generated {len(tasks)} responses")
        print(f"📁 Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(generate_all())
```

### Script 2 : `scripts/4_analyze_optionB.py`

```python
"""
Analyze Option B results with statistical tests and visualizations.

Usage:
    python scripts/4_analyze_optionB.py \
        --input evaluation/4_results/judgments_unblinded.jsonl \
        --output evaluation/5_analysis/
"""

import json
import argparse
from pathlib import Path
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns

# ============================================================================
# ANALYSIS
# ============================================================================

def load_judgments(filepath):
    """Load unblinded judgments."""
    judgments = []
    with open(filepath) as f:
        for line in f:
            judgments.append(json.loads(line))
    return judgments


def compute_summary_stats(judgments):
    """Compute summary statistics by config."""
    
    stats_by_config = {}
    
    for config_id in ["baseline", "temp_only", "system_only", "full_lyra"]:
        config_data = [j for j in judgments if j["config_id"] == config_id]
        
        overall_scores = [j["scores"]["overall"] for j in config_data]
        
        stats_by_config[config_id] = {
            "n": len(config_data),
            "overall_mean": np.mean(overall_scores),
            "overall_std": np.std(overall_scores, ddof=1),
            "overall_median": np.median(overall_scores),
            "accuracy_mean": np.mean([j["scores"]["accuracy"] for j in config_data]),
            "completeness_mean": np.mean([j["scores"]["completeness"] for j in config_data]),
            "clarity_mean": np.mean([j["scores"]["clarity"] for j in config_data]),
            "appropriateness_mean": np.mean([j["scores"]["appropriateness"] for j in config_data]),
            "creativity_mean": np.mean([j["scores"].get("creativity", 0) for j in config_data])
        }
    
    return stats_by_config


def pairwise_tests(judgments):
    """Perform pairwise t-tests between configs."""
    
    configs = ["baseline", "temp_only", "system_only", "full_lyra"]
    results = {}
    
    for i, config_a in enumerate(configs):
        for config_b in configs[i+1:]:
            
            scores_a = [j["scores"]["overall"] for j in judgments if j["config_id"] == config_a]
            scores_b = [j["scores"]["overall"] for j in judgments if j["config_id"] == config_b]
            
            t_stat, p_value = stats.ttest_ind(scores_a, scores_b)
            
            # Cohen's d
            pooled_std = np.sqrt((np.var(scores_a, ddof=1) + np.var(scores_b, ddof=1)) / 2)
            cohens_d = (np.mean(scores_a) - np.mean(scores_b)) / pooled_std if pooled_std > 0 else 0
            
            results[f"{config_a}_vs_{config_b}"] = {
                "t_statistic": float(t_stat),
                "p_value": float(p_value),
                "cohens_d": float(cohens_d),
                "significant_005": p_value < 0.05,
                "significant_001": p_value < 0.01,
                "effect_size_interpretation": interpret_cohens_d(cohens_d)
            }
    
    return results


def interpret_cohens_d(d):
    """Interpret Cohen's d effect size."""
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    elif abs_d < 0.5:
        return "small"
    elif abs_d < 0.8:
        return "medium"
    else:
        return "large"


def domain_breakdown(judgments):
    """Breakdown by domain."""
    
    breakdown = {}
    
    for domain in ["technical", "creative", "analytical"]:
        domain_data = [j for j in judgments if j["domain"] == domain]
        
        breakdown[domain] = {}
        
        for config_id in ["baseline", "temp_only", "system_only", "full_lyra"]:
            config_domain = [j for j in domain_data if j["config_id"] == config_id]
            
            if config_domain:
                breakdown[domain][config_id] = {
                    "overall_mean": np.mean([j["scores"]["overall"] for j in config_domain]),
                    "n": len(config_domain)
                }
    
    return breakdown


def plot_attribution_chart(stats, pairwise, output_dir):
    """Plot effect sizes for attribution."""
    
    # Extract effect sizes relative to baseline
    effect_sizes = {
        "Temperature Only": pairwise.get("baseline_vs_temp_only", {}).get("cohens_d", 0),
        "System Prompt Only": pairwise.get("baseline_vs_system_only", {}).get("cohens_d", 0),
        "Full Lyra": pairwise.get("baseline_vs_full_lyra", {}).get("cohens_d", 0)
    }
    
    # Plot
    fig, ax = plt.subplots(figsize=(10, 6))
    
    components = list(effect_sizes.keys())
    values = list(effect_sizes.values())
    colors = ['#FF6B6B' if abs(v) < 0.2 else '#4ECDC4' if abs(v) < 0.5 else '#45B7D1' for v in values]
    
    ax.barh(components, values, color=colors)
    ax.axvline(0, color='black', linewidth=0.8)
    ax.axvline(0.2, color='gray', linestyle='--', alpha=0.5, label='Small effect')
    ax.axvline(0.5, color='gray', linestyle='--', alpha=0.5, label='Medium effect')
    ax.axvline(0.8, color='gray', linestyle='--', alpha=0.5, label='Large effect')
    
    ax.set_xlabel("Cohen's d (Effect Size)", fontsize=12)
    ax.set_title("Attribution Analysis: Component Effect Sizes vs Baseline", fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(axis='x', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / "attribution_chart.png", dpi=300)
    print(f"📊 Saved attribution chart")


def generate_report(stats, pairwise, domain, output_dir):
    """Generate markdown report."""
    
    report = []
    report.append("# Option B : Quick Validation Results\n")
    report.append(f"**Date :** {Path.cwd()}\n")
    report.append("---\n")
    
    # Summary stats
    report.append("## Summary Statistics\n")
    for config_id, config_stats in stats.items():
        report.append(f"### {config_id}\n")
        report.append(f"- **Overall Mean :** {config_stats['overall_mean']:.2f} ± {config_stats['overall_std']:.2f}\n")
        report.append(f"- **N :** {config_stats['n']}\n")
        report.append(f"- **Accuracy :** {config_stats['accuracy_mean']:.2f}\n")
        report.append(f"- **Completeness :** {config_stats['completeness_mean']:.2f}\n")
        report.append(f"- **Clarity :** {config_stats['clarity_mean']:.2f}\n\n")
    
    # Pairwise tests
    report.append("## Pairwise Comparisons\n")
    for comparison, result in pairwise.items():
        report.append(f"### {comparison}\n")
        report.append(f"- **Cohen's d :** {result['cohens_d']:.3f} ({result['effect_size_interpretation']})\n")
        report.append(f"- **p-value :** {result['p_value']:.4f} {'✅ significant' if result['significant_005'] else '❌ not significant'}\n\n")
    
    # Go/No-Go
    report.append("## Go/No-Go Decision\n")
    
    any_significant = any(r['significant_005'] for r in pairwise.values())
    any_medium_effect = any(abs(r['cohens_d']) > 0.3 for r in pairwise.values())
    
    if any_significant and any_medium_effect:
        report.append("✅ **GO** : Proceed to Full Evaluation (Option A)\n")
        report.append("- At least one significant difference detected\n")
        report.append("- Medium+ effect size observed\n")
    else:
        report.append("❌ **NO-GO** : Pivot Strategy Recommended\n")
        report.append("- No significant differences or negligible effect sizes\n")
        report.append("- Consider human evaluation or domain-specific focus\n")
    
    # Save report
    with open(output_dir / "report.md", 'w') as f:
        f.write('\n'.join(report))
    
    print(f"📝 Saved report")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='Path to judgments_unblinded.jsonl')
    parser.add_argument('--output', required=True, help='Output directory')
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load
    print(f"Loading judgments from {args.input}")
    judgments = load_judgments(args.input)
    print(f"Loaded {len(judgments)} judgments")
    
    # Analyze
    print("Computing summary stats...")
    stats = compute_summary_stats(judgments)
    
    print("Running pairwise tests...")
    pairwise = pairwise_tests(judgments)
    
    print("Computing domain breakdown...")
    domain = domain_breakdown(judgments)
    
    # Save JSON
    with open(output_dir / "summary_stats.json", 'w') as f:
        json.dump(stats, f, indent=2)
    
    with open(output_dir / "pairwise_tests.json", 'w') as f:
        json.dump(pairwise, f, indent=2)
    
    with open(output_dir / "domain_breakdown.json", 'w') as f:
        json.dump(domain, f, indent=2)
    
    # Visualize
    print("Generating visualizations...")
    plot_attribution_chart(stats, pairwise, output_dir)
    
    # Report
    print("Generating report...")
    generate_report(stats, pairwise, domain, output_dir)
    
    print(f"\n✅ Analysis complete. Results in {output_dir}/")


if __name__ == "__main__":
    main()
```

---

## Coûts Finaux

### API Calls
- **Génération réponses :** Gratuit (local Ollama)
- **Claude Haiku judging :** ~$0.08
- **Total :** < $0.10

### Temps Humain
- Génération : 2-3h (mostly automated)
- Judging : 1-2h (automated)
- Analyse : 1-2h
- **Total :** 5-7 heures

---

## Checklist Exécution

### Préparation
- [ ] Serveur Lyra running (`http://localhost:8000/health` OK)
- [ ] Ollama running avec gpt-oss:20b
- [ ] Claude API key configurée
- [ ] Scripts téléchargés dans `/mnt/project/`
- [ ] Structure dossiers créée (`evaluation/`)

### Jour 1
- [ ] Générer 60 réponses (`generate_responses_optionB.py`)
- [ ] Vérifier `responses_raw.jsonl` (60 lignes)
- [ ] Anonymiser (`1_anonymize.py`)
- [ ] Judge avec Claude Haiku (`2_judge.py`)
- [ ] Unblind (`3_unblind.py`)

### Jour 2
- [ ] Analyser statistiques (`4_analyze_optionB.py`)
- [ ] Examiner visualisations (attribution_chart.png)
- [ ] Lire rapport (report.md)
- [ ] **Go/No-Go Decision**

---

## Scénarios Attendus

### Scénario A : System Prompt Dominant (Medium Effect)

```json
{
  "baseline_vs_temp_only": {"cohens_d": 0.12, "p_value": 0.45},
  "baseline_vs_system_only": {"cohens_d": 0.54, "p_value": 0.02},
  "baseline_vs_full_lyra": {"cohens_d": 0.61, "p_value": 0.008}
}
```

**Interprétation :** 
- Temperature négligeable
- System prompt effet moyen (d=0.54)
- Full Lyra légèrement supérieur (synergie faible)

**Action :** GO to Full Evaluation, focus system prompt engineering

### Scénario B : No Detectable Difference

```json
{
  "baseline_vs_temp_only": {"cohens_d": 0.08, "p_value": 0.72},
  "baseline_vs_system_only": {"cohens_d": 0.14, "p_value": 0.51},
  "baseline_vs_full_lyra": {"cohens_d": 0.19, "p_value": 0.38}
}
```

**Interprétation :**
- Tous effets négligeables (d < 0.2)
- Aucune différence significative

**Action :** NO-GO. Pivot to :
1. Human evaluation (Mechanical Turk)
2. Domain-specific evaluation (narrow use case)
3. Position as "orchestration framework" (not quality)

### Scénario C : Full Lyra Strong Effect

```json
{
  "baseline_vs_temp_only": {"cohens_d": 0.23, "p_value": 0.28},
  "baseline_vs_system_only": {"cohens_d": 0.31, "p_value": 0.15},
  "baseline_vs_full_lyra": {"cohens_d": 0.78, "p_value": 0.001}
}
```

**Interprétation :**
- Composantes individuelles faibles
- Full Lyra effet large (d=0.78)
- Synergie forte (orchestration > somme parties)

**Action :** GO to Full Evaluation, emphasize "holistic orchestration"

---

## Next Steps After Go/No-Go

### If GO ✅
1. Expand to 6 configs (add Creative, Analytical profiles)
2. Expand to 50 prompts (10 per domain × 5 domains)
3. Implement calibration dataset (50 examples)
4. Run full bias-corrected evaluation
5. Budget : $15-20, 1 semaine

### If NO-GO ❌
1. Design Mechanical Turk study (human judges)
2. Focus on specific domains where Lyra shines
3. Alternative positioning : framework (not quality)
4. Consider qualitative case studies
5. Budget : $50-100, 2 semaines

---

**Ready to execute ?** Tous les scripts sont prêts. Commande pour démarrer :

```bash
python generate_responses_optionB.py
```
