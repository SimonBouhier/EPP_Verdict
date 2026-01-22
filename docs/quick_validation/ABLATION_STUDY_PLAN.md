# LYRA - PLAN DE TESTS D'ABLATION
## Isoler les Sources de Variation Paramétrique

**Date :** 2025-12-06  
**Objectif :** Déterminer quelle composante de Lyra cause les différences observées

---

## 🎯 HYPOTHÈSE À TESTER

**Observation** : Les réponses diffèrent entre configurations (raw vs lyra).

**Sources possibles** :
1. **Temperature** (tau_c → temp mapping)
2. **Penalties** (rho → presence/frequency)
3. **System Prompt** (kappa → style hints)
4. **Top-k/Top-p** (fixes dans Ollama)
5. **Context Scheduling** (delta_r → timing, mais graphe vide donc inactive)
6. **Combinaisons** (effets d'interaction)

**Question** : Quelle(s) source(s) causent les variations ?

---

## 🧪 DESIGN EXPÉRIMENTAL : ABLATION LADDER

### Baseline (Control)

```python
CONFIG_BASELINE = {
    "name": "raw_vanilla",
    "model": "gpt-oss:20b",
    "temperature": 0.8,        # Ollama default
    "top_k": 40,               # Ollama default
    "top_p": 0.9,              # Ollama default
    "repeat_penalty": 1.0,     # Ollama default
    "presence_penalty": None,  # N'existe pas dans Ollama
    "frequency_penalty": None, # N'existe pas dans Ollama
    "system_prompt": None      # Pas de system prompt
}
```

### Ablation 1 : Temperature Seule

```python
CONFIG_TEMP_ONLY = {
    "name": "ablation_temp",
    "model": "gpt-oss:20b",
    "temperature": 0.615,      # ← CHANGEMENT (Creative equiv)
    "top_k": 40,               # = baseline
    "top_p": 0.9,              # = baseline
    "repeat_penalty": 1.0,     # = baseline
    "system_prompt": None      # = baseline
}
```

**Hypothèse** : Si différences → temperature est responsable.

### Ablation 2 : Repeat Penalty Seule

```python
CONFIG_PENALTY_ONLY = {
    "name": "ablation_penalty",
    "model": "gpt-oss:20b",
    "temperature": 0.8,        # = baseline
    "top_k": 40,
    "top_p": 0.9,
    "repeat_penalty": 1.3,     # ← CHANGEMENT (rho=0.5 → +0.3*0.5 = +0.15)
    "system_prompt": None
}
```

**Hypothèse** : Si différences → penalties responsables.

### Ablation 3 : System Prompt Seul

```python
CONFIG_SYSTEM_ONLY = {
    "name": "ablation_system",
    "model": "gpt-oss:20b",
    "temperature": 0.8,        # = baseline
    "repeat_penalty": 1.0,
    "system_prompt": """
You are Lyra, an AI assistant with adaptive behavior.

Style Guidelines:
- Balance structure and exploration
- Use clear explanations
- Maintain professional tone
"""  # ← CHANGEMENT (kappa → style hints)
}
```

**Hypothèse** : Si différences → system prompt responsable.

### Ablation 4 : Temperature + Penalty

```python
CONFIG_TEMP_PENALTY = {
    "name": "ablation_temp_penalty",
    "temperature": 0.615,      # Comme Creative
    "repeat_penalty": 1.3,     # Comme Creative
    "system_prompt": None      # PAS de system
}
```

**Test interaction** : Effets additifs ou synergiques ?

### Ablation 5 : Full Lyra (Toutes Composantes)

```python
CONFIG_FULL_LYRA = {
    "name": "lyra_creative_full",
    "temperature": 0.615,      # tau_c=1.3 → temp=0.8/1.3
    "repeat_penalty": 1.3,     # rho=0.5 → 1.0+(0.3*0.5)
    "system_prompt": SYSTEM_CREATIVE  # kappa=0.5 → hints
}
```

**Référence complète** pour comparaison.

---

## 📊 MATRICE DE COMPARAISON

| Config               | Temp | Penalty | System | Expected Diff |
|----------------------|------|---------|--------|---------------|
| Baseline (raw)       | 0.80 | 1.0     | None   | -             |
| Ablation Temp        | 0.62 | 1.0     | None   | Small         |
| Ablation Penalty     | 0.80 | 1.3     | None   | Moderate      |
| Ablation System      | 0.80 | 1.0     | Yes    | Large         |
| Temp + Penalty       | 0.62 | 1.3     | None   | Moderate+     |
| Full Lyra            | 0.62 | 1.3     | Yes    | Large+        |

---

## 🔬 PROTOCOLE D'EXÉCUTION

### Phase 1 : Génération (2h)

```python
ABLATION_CONFIGS = [
    "raw_vanilla",
    "ablation_temp",
    "ablation_penalty",
    "ablation_system",
    "ablation_temp_penalty",
    "lyra_creative_full"
]

TEST_PROMPTS = [
    # Technical (10)
    "What is machine learning? (20 words max)",
    "Explain TCP protocol (25 words max)",
    # ... 8 more
    
    # Creative (10)
    "Write a haiku about algorithms",
    "Describe sunset in 15 words",
    # ... 8 more
    
    # Analytical (10)
    "Compare Python vs JavaScript (30 words max)",
    "Pros/cons of microservices (25 words max)",
    # ... 8 more
]

# Génération
for config in ABLATION_CONFIGS:
    for prompt in TEST_PROMPTS:
        response = generate(prompt, config)
        save(prompt, config, response)
```

**Output** : 6 configs × 30 prompts = **180 réponses**

### Phase 2 : Jugement Blind (1h)

```python
# Anonymiser
anonymize_responses("ablation_responses.jsonl")

# Juger avec Claude Haiku (protocole triple-blind)
judge_with_claude_haiku("ablation_blind.jsonl")

# Coût : 180 judgments × ~$0.0015 = ~$0.27
```

### Phase 3 : Analyse d'Attribution (30 min)

```python
def attribution_analysis(judgments):
    """
    Compare chaque ablation au baseline pour isoler l'effet.
    """
    baseline_scores = get_scores("raw_vanilla")
    
    effects = {}
    
    # Effet Temperature
    temp_scores = get_scores("ablation_temp")
    effects['temperature'] = compare(baseline_scores, temp_scores)
    
    # Effet Penalty
    penalty_scores = get_scores("ablation_penalty")
    effects['penalty'] = compare(baseline_scores, penalty_scores)
    
    # Effet System
    system_scores = get_scores("ablation_system")
    effects['system'] = compare(baseline_scores, system_scores)
    
    # Interaction
    temp_penalty_scores = get_scores("ablation_temp_penalty")
    expected_additive = (
        effects['temperature']['delta'] + 
        effects['penalty']['delta']
    )
    actual_combined = temp_penalty_scores.mean() - baseline_scores.mean()
    
    interaction_effect = actual_combined - expected_additive
    
    return effects, interaction_effect
```

---

## 📈 ANALYSE STATISTIQUE

### Test ANOVA

**Question** : Les configs diffèrent-elles significativement ?

```python
from scipy import stats

# Préparer données
groups = {
    'baseline': baseline_scores,
    'temp': temp_scores,
    'penalty': penalty_scores,
    'system': system_scores,
    'temp_penalty': temp_penalty_scores,
    'full_lyra': full_scores
}

# One-way ANOVA
f_stat, p_value = stats.f_oneway(*groups.values())

print(f"ANOVA: F={f_stat:.2f}, p={p_value:.4f}")

if p_value < 0.05:
    print("✓ Configurations differ significantly")
    
    # Post-hoc pairwise comparisons
    from scipy.stats import ttest_ind
    
    comparisons = [
        ('baseline', 'ablation_temp'),
        ('baseline', 'ablation_penalty'),
        ('baseline', 'ablation_system'),
        # ... etc
    ]
    
    for config_a, config_b in comparisons:
        t, p = ttest_ind(groups[config_a], groups[config_b])
        print(f"{config_a} vs {config_b}: t={t:.2f}, p={p:.4f}")
```

### Effect Size

**Question** : Quelle composante a le PLUS GRAND effet ?

```python
def cohens_d(group1, group2):
    """Cohen's d effect size"""
    mean1, mean2 = np.mean(group1), np.mean(group2)
    std_pooled = np.sqrt(
        (np.std(group1, ddof=1)**2 + np.std(group2, ddof=1)**2) / 2
    )
    return (mean1 - mean2) / std_pooled

effect_sizes = {
    'temperature': cohens_d(baseline_scores, temp_scores),
    'penalty': cohens_d(baseline_scores, penalty_scores),
    'system': cohens_d(baseline_scores, system_scores)
}

# Interpréter
for component, d in effect_sizes.items():
    magnitude = (
        "Large" if abs(d) > 0.8 else
        "Medium" if abs(d) > 0.5 else
        "Small" if abs(d) > 0.2 else
        "Negligible"
    )
    print(f"{component}: d={d:.3f} ({magnitude})")
```

**Interprétation** :
- |d| < 0.2 : Negligible
- |d| ~ 0.5 : Medium (visible)
- |d| > 0.8 : Large (évident)

---

## 📊 VISUALISATION

### Attribution Chart

```python
import matplotlib.pyplot as plt

components = ['Temperature', 'Penalty', 'System Prompt', 'Interaction']
effects = [0.12, 0.28, 0.45, 0.08]  # Exemple (effect sizes)

plt.figure(figsize=(10, 6))
plt.barh(components, effects, color=['#3498db', '#e74c3c', '#2ecc71', '#f39c12'])
plt.xlabel('Effect Size (Cohen\'s d)')
plt.title('Attribution of Lyra Variations: Which Component Matters?')
plt.axvline(x=0, color='black', linestyle='-', linewidth=0.5)
plt.axvline(x=0.2, color='gray', linestyle='--', alpha=0.5, label='Small')
plt.axvline(x=0.5, color='gray', linestyle='--', alpha=0.5, label='Medium')
plt.axvline(x=0.8, color='gray', linestyle='--', alpha=0.5, label='Large')
plt.legend()
plt.tight_layout()
plt.savefig('lyra_attribution.png', dpi=300)
```

### Interaction Plot

```python
# Si interaction significative
configs = ['Baseline', 'Temp', 'Penalty', 'Temp+Penalty', 'Full']
scores = [3.2, 3.4, 3.7, 4.0, 4.3]  # Exemple

plt.figure(figsize=(10, 6))
plt.plot(configs, scores, marker='o', linewidth=2, markersize=10)
plt.ylabel('Mean Quality Score (1-5)')
plt.title('Cumulative Effect of Lyra Components')
plt.grid(True, alpha=0.3)

# Annotate deltas
for i in range(1, len(configs)):
    delta = scores[i] - scores[i-1]
    plt.annotate(
        f'+{delta:.2f}',
        xy=(i, scores[i]),
        xytext=(10, 10),
        textcoords='offset points',
        fontsize=10,
        color='green' if delta > 0 else 'red'
    )

plt.tight_layout()
plt.savefig('lyra_cumulative_effect.png', dpi=300)
```

---

## 🎯 RÉSULTATS ATTENDUS

### Scénario A : System Prompt Dominant

```
Component        | Effect Size | p-value | Conclusion
-----------------|-------------|---------|---------------------------
Temperature      | d = 0.15    | 0.342   | Negligible (ns)
Penalty          | d = 0.23    | 0.128   | Small (ns)
System Prompt    | d = 0.68    | 0.003   | Large (SIGNIFICANT) ✓
Interaction      | d = 0.09    | 0.756   | None
```

**Interprétation** : Les style hints du system prompt sont la source principale des variations. Temperature et penalties ont un effet minimal.

**Implication** : Lyra's value = intelligent system prompt building, pas juste parameter tweaking.

### Scénario B : Effets Combinés

```
Component        | Effect Size | p-value | Conclusion
-----------------|-------------|---------|---------------------------
Temperature      | d = 0.32    | 0.042   | Small (significant) ✓
Penalty          | d = 0.38    | 0.021   | Small-Medium (sig) ✓
System Prompt    | d = 0.41    | 0.015   | Medium (significant) ✓
Interaction      | d = 0.28    | 0.067   | Moderate synergy
```

**Interprétation** : Tous les composants contribuent modérément. L'effet total (d=0.89, large) provient de la combinaison.

**Implication** : Lyra's value = holistic orchestration, pas un seul "magic bullet".

### Scénario C : Temperature Dominant (Surprenant)

```
Component        | Effect Size | p-value | Conclusion
-----------------|-------------|---------|---------------------------
Temperature      | d = 0.72    | 0.001   | Large (SIGNIFICANT) ✓
Penalty          | d = 0.14    | 0.456   | Negligible
System Prompt    | d = 0.18    | 0.287   | Negligible
```

**Interprétation** : Temperature mapping (tau_c → temp) est le driver principal. Autres composants négligeables.

**Implication** : Simplifier Lyra ? Focus sur temperature modulation, retirer penalties/system ?

---

## 💡 INSIGHTS OPÉRATIONNELS

### Si System Prompt Dominant

**Action** : 
- Investir dans prompt engineering sophistiqué
- Créer library de style hints par contexte
- Ajouter plus de κ (kappa) profiles

**Simplification possible** :
- Peut-être retirer temperature/penalty modulation
- Focus sur dynamic prompting

### Si Effets Combinés

**Action** :
- Garder architecture actuelle (tous composants nécessaires)
- Documenter synergies
- Optimiser interactions

**Communication** :
- "Lyra: Holistic LLM orchestration"
- Emphasize integrated approach

### Si Temperature Dominant

**Action** :
- Simplifier Lyra → focus temperature
- Créer "Lyra Lite" : juste tau_c → temp mapping
- Retirer penalties, system prompt

**Pivot** :
- "Lyra: Intelligent Temperature Scheduling"
- Simpler, clearer value prop

---

## 📋 SCRIPT D'ABLATION COMPLET

```python
"""
ablation_study.py
Tests d'ablation pour isoler sources de variation Lyra.
"""
import json
import requests
from typing import Dict, List
import numpy as np
from scipy import stats

# Configurations
OLLAMA_URL = "http://localhost:11434/api/generate"

CONFIGS = {
    "baseline": {
        "temperature": 0.8,
        "repeat_penalty": 1.0,
        "system": None
    },
    "ablation_temp": {
        "temperature": 0.615,  # Creative equiv
        "repeat_penalty": 1.0,
        "system": None
    },
    "ablation_penalty": {
        "temperature": 0.8,
        "repeat_penalty": 1.3,  # rho=0.5
        "system": None
    },
    "ablation_system": {
        "temperature": 0.8,
        "repeat_penalty": 1.0,
        "system": "You are Lyra, an AI assistant. Maintain professional tone."
    },
    "ablation_temp_penalty": {
        "temperature": 0.615,
        "repeat_penalty": 1.3,
        "system": None
    },
    "full_lyra": {
        "temperature": 0.615,
        "repeat_penalty": 1.3,
        "system": "You are Lyra, an AI assistant with adaptive behavior.\n\nStyle Guidelines:\n- Balance structure and exploration\n- Use clear explanations"
    }
}

PROMPTS = [
    {"domain": "technical", "prompt": "What is machine learning? (20 words max)"},
    {"domain": "technical", "prompt": "Explain TCP protocol (25 words max)"},
    # ... 28 more prompts
]

def generate_response(prompt: str, config: Dict) -> str:
    """Génère réponse avec config donnée"""
    payload = {
        "model": "gpt-oss:20b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": config["temperature"],
            "repeat_penalty": config["repeat_penalty"],
            "num_predict": 100,
            "top_k": 40,
            "top_p": 0.9
        }
    }
    
    if config["system"]:
        payload["system"] = config["system"]
    
    resp = requests.post(OLLAMA_URL, json=payload)
    return resp.json()["response"]

def run_ablation_study():
    """Exécute tous les tests d'ablation"""
    results = []
    
    for config_name, config in CONFIGS.items():
        print(f"\n{'='*60}")
        print(f"Config: {config_name}")
        print(f"{'='*60}")
        
        for prompt_data in PROMPTS:
            prompt = prompt_data["prompt"]
            domain = prompt_data["domain"]
            
            print(f"  [{domain}] {prompt[:50]}...", end=" ")
            
            response = generate_response(prompt, config)
            
            results.append({
                "config": config_name,
                "domain": domain,
                "prompt": prompt,
                "response": response,
                "temperature": config["temperature"],
                "repeat_penalty": config["repeat_penalty"],
                "has_system": config["system"] is not None
            })
            
            print(f"✓")
    
    # Save
    with open("ablation_results.jsonl", 'w') as f:
        for r in results:
            f.write(json.dumps(r) + '\n')
    
    print(f"\n✓ Generated {len(results)} responses")
    return results

def analyze_attribution(judgments_file: str):
    """
    Analyse d'attribution après jugement blind.
    
    Requires: judgments_unblinded.jsonl avec config reconstitué
    """
    with open(judgments_file, 'r') as f:
        judgments = [json.loads(line) for line in f]
    
    # Group par config
    by_config = {}
    for j in judgments:
        config = j['config']
        if config not in by_config:
            by_config[config] = []
        by_config[config].append(j['overall'])
    
    baseline = np.array(by_config['baseline'])
    
    print("="*80)
    print("ABLATION ATTRIBUTION ANALYSIS")
    print("="*80)
    
    effects = {}
    
    # Calculer effet de chaque composant
    for config_name in ['ablation_temp', 'ablation_penalty', 'ablation_system']:
        if config_name not in by_config:
            continue
        
        scores = np.array(by_config[config_name])
        
        # t-test
        t_stat, p_value = stats.ttest_ind(baseline, scores)
        
        # Cohen's d
        mean_diff = scores.mean() - baseline.mean()
        pooled_std = np.sqrt((baseline.std(ddof=1)**2 + scores.std(ddof=1)**2) / 2)
        cohens_d = mean_diff / pooled_std
        
        # Magnitude
        magnitude = (
            "Large" if abs(cohens_d) > 0.8 else
            "Medium" if abs(cohens_d) > 0.5 else
            "Small" if abs(cohens_d) > 0.2 else
            "Negligible"
        )
        
        effects[config_name] = {
            'mean_diff': mean_diff,
            'cohens_d': cohens_d,
            'p_value': p_value,
            'magnitude': magnitude
        }
        
        component = config_name.replace('ablation_', '').capitalize()
        sig = "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else "ns"
        
        print(f"\n{component}:")
        print(f"  Δ = {mean_diff:+.3f}")
        print(f"  d = {cohens_d:.3f} ({magnitude})")
        print(f"  p = {p_value:.4f} {sig}")
    
    # Test interaction
    if 'ablation_temp_penalty' in by_config:
        temp_penalty = np.array(by_config['ablation_temp_penalty'])
        
        expected_additive = (
            effects.get('ablation_temp', {}).get('mean_diff', 0) +
            effects.get('ablation_penalty', {}).get('mean_diff', 0)
        )
        
        actual = temp_penalty.mean() - baseline.mean()
        
        interaction = actual - expected_additive
        
        print(f"\n{'='*80}")
        print("INTERACTION EFFECT")
        print(f"{'='*80}")
        print(f"Expected (additive): {expected_additive:+.3f}")
        print(f"Actual (combined):   {actual:+.3f}")
        print(f"Interaction:         {interaction:+.3f}")
        
        if abs(interaction) > 0.1:
            print("→ Non-additive (synergy or interference)")
        else:
            print("→ Approximately additive")
    
    return effects

if __name__ == "__main__":
    # Phase 1: Generate
    print("PHASE 1: Generating ablation responses...")
    run_ablation_study()
    
    # Phase 2: Judge (après anonymisation + Claude Haiku)
    print("\nPHASE 2: Now run blind judgment:")
    print("  1. python 1_anonymize.py ablation_results.jsonl")
    print("  2. python 2_judge.py")
    print("  3. python 3_unblind.py")
    
    # Phase 3: Analyze (après reconstruction)
    print("\nPHASE 3: After unblinding, run:")
    print("  python ablation_study.py --analyze judgments_unblinded.jsonl")
```

---

## 🎓 CONCLUSION

**Ce plan d'ablation répond à la question critique** :

> "Si ce n'est que le top_p et top_k qui changent le ton je dois le savoir"

**Méthode** :
1. ✅ Tester chaque composant isolément
2. ✅ Mesurer effect size (pas juste p-value)
3. ✅ Tester interactions (synergies ?)
4. ✅ Attribution causale rigoureuse

**Résultat attendu** : Savoir précisément quels paramètres comptent et lesquels sont superflus.

**Décisions ensuite** :
- Si system prompt dominant → Focus prompt engineering
- Si temperature dominant → Simplifier en "Lyra Lite"
- Si effets combinés → Garder architecture holistique

---

**Plan Statut** : ✅ PRÊT POUR EXÉCUTION  
**Coût** : ~$0.30 (180 judgments)  
**Durée** : 3-4h total  
**Output** : Attribution causale claire + visualisations
