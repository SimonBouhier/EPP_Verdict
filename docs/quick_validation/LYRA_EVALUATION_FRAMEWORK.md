# LYRA - FRAMEWORK D'ÉVALUATION RIGOUREUX
## LLM-as-Judge avec Corrections de Bias

**Date :** 2025-12-04  
**Base théorique :** [arxiv:2511.21140] "How to Correctly Report LLM-as-a-Judge Evaluations"  
**Objectif :** Évaluer l'impact **qualitatif** des profils Bezier de Lyra

---

## 🎯 OBJECTIF DE L'ÉVALUATION

**Ce qu'on ÉVALUE** :
- ✅ Qualité des réponses (pas vitesse)
- ✅ Impact des profils Bezier (Creative vs Balanced vs Raw)
- ✅ Différentiation par type de tâche (technical, creative, analytical)

**Ce qu'on N'ÉVALUE PAS** :
- ❌ Performance/latence (déjà fait : overhead 5% acceptable)
- ❌ Context injection (graphe désactivé)
- ❌ Memory (Phase 3 pas prioritaire)

**Hypothèse centrale** :
> Les trajectoires Bezier modulent les paramètres (temperature, penalties) de manière à produire des réponses qualitativement différentes adaptées au contexte.

---

## ⚠️ PROBLÈMES DES LLM-AS-JUDGE (Article 2511.21140)

### 1. Bias Systématique

**Les LLM judges ont deux paramètres cachés** :
- **q₀ (specificity)** : P(juge rejette | réponse incorrecte)
- **q₁ (sensitivity)** : P(juge accepte | réponse correcte)

**Conséquence** : Le score brut p̂ (fraction jugée "correcte") est **biaisé** :

```
E[p̂] = (1 - q₀) + θ(q₀ + q₁ - 1)
```

**Direction du bias** :
- Si θ < (1-q₀)/(q₀+q₁-1) : **SURESTIMATION** (bias positif)
- Si θ > (1-q₀)/(q₀+q₁-1) : **SOUS-ESTIMATION** (bias négatif)

**Exemple** : Avec q₀=0.7, q₁=0.9
- Point de transition : θ = 0.75
- θ=0.5 → overestimate de ~5-10%
- θ=0.9 → underestimate de ~5-10%

### 2. Incertitude Non Quantifiée

**Deux sources d'incertitude** :
1. **Test dataset** : variance due au sample de prompts
2. **Calibration dataset** : variance sur l'estimation de q₀, q₁

**Problème** : Les études reportent typiquement **un seul nombre** (p̂) sans confidence interval → impossible de savoir si différence significative.

### 3. Comparaisons Invalides

**Sans correction** :
- Système A : p̂ₐ = 0.85
- Système B : p̂ᵦ = 0.82
- **Conclusion naïve** : A est meilleur (+3%)

**Avec correction** :
- Système A : θ̂ₐ = 0.78 ± 0.05
- Système B : θ̂ᵦ = 0.81 ± 0.04
- **Conclusion correcte** : B probablement meilleur (intervalles se chevauchent peu)

---

## ✅ SOLUTION : CALIBRATION + CORRECTION

### Étape 1 : Créer Calibration Dataset

**Définition** : Un ensemble de (prompt, réponse, ground_truth) où `ground_truth` est le jugement humain (ou oracle).

**Taille requise** : 
- Minimum : 30-50 exemples (estimation q₀, q₁)
- Optimal : 100-200 exemples (confidence intervals étroits)

**Structure** :
```json
{
  "prompt": "What is machine learning?",
  "response_raw": "ML is training algorithms on data...",
  "response_creative": "ML weaves patterns through digital neurons...",
  "ground_truth_raw": "correct",      // Human judgment
  "ground_truth_creative": "correct"   // Human judgment
}
```

**Comment obtenir ground_truth** :
1. **Option A (Gold Standard)** : Annotation humaine experte
   - 2-3 annotateurs par exemple
   - Accord inter-annotateur (Kappa > 0.7)
   - Coût : ~50-100€ pour 100 exemples

2. **Option B (Proxy)** : Utiliser un LLM **très supérieur** comme proxy humain
   - GPT-4o ou Claude Opus 3.5
   - Prompt soigneusement calibré
   - Validation sur subset humain (≥20 exemples)

3. **Option C (Heuristique)** : Pour certaines tâches objectives
   - Code : compile/test pass = correct
   - Math : résultat exact = correct
   - Factuel : vérifiable par source externe

### Étape 2 : Estimer q₀ et q₁

**Sur le calibration dataset** :

```python
# Exemples incorrects (ground_truth = incorrect)
incorrect_samples = [s for s in calibration if s['ground_truth'] == 'incorrect']
m0 = len(incorrect_samples)

# Combien le juge a rejeté correctement
rejected_incorrect = [s for s in incorrect_samples if s['llm_judge'] == 'incorrect']
q0_hat = len(rejected_incorrect) / m0

# Exemples corrects (ground_truth = correct)
correct_samples = [s for s in calibration if s['ground_truth'] == 'correct']
m1 = len(correct_samples)

# Combien le juge a accepté correctement
accepted_correct = [s for s in correct_samples if s['llm_judge'] == 'correct']
q1_hat = len(accepted_correct) / m1

print(f"Estimated specificity (q₀): {q0_hat:.3f}")
print(f"Estimated sensitivity (q₁): {q1_hat:.3f}")
```

### Étape 3 : Correction du Bias

**Sur le test dataset** (réponses Lyra à évaluer) :

```python
# Score brut (naive estimator)
p_hat = count_correct / total_samples

# Correction de bias (formule de Rogan & Gladen, 1978)
theta_hat = (p_hat - (1 - q0_hat)) / (q0_hat + q1_hat - 1)

# Clamping (si hors [0, 1])
theta_hat = max(0.0, min(1.0, theta_hat))

print(f"Naive accuracy: {p_hat:.3f}")
print(f"Bias-corrected accuracy: {theta_hat:.3f}")
print(f"Correction: {(theta_hat - p_hat):.3f} ({(theta_hat - p_hat)/p_hat*100:+.1f}%)")
```

### Étape 4 : Confidence Interval

**Formule (simplifiée)** :

```python
import numpy as np
from scipy import stats

# Test dataset size
n = total_samples

# Calibration sizes
m0 = len(incorrect_calibration)
m1 = len(correct_calibration)

# Variance components
var_test = (theta_hat * (1 - theta_hat)) / n
var_calib = (
    ((1 - theta_hat) / (q0_hat + q1_hat - 1))**2 * q0_hat * (1 - q0_hat) / m0 +
    (theta_hat / (q0_hat + q1_hat - 1))**2 * q1_hat * (1 - q1_hat) / m1
)

# Total variance
var_total = var_test + var_calib
se = np.sqrt(var_total)

# 95% confidence interval (approximation normale)
z = stats.norm.ppf(0.975)  # z = 1.96
ci_lower = theta_hat - z * se
ci_upper = theta_hat + z * se

print(f"Accuracy: {theta_hat:.3f} ± {z*se:.3f}")
print(f"95% CI: [{ci_lower:.3f}, {ci_upper:.3f}]")
```

### Étape 5 : Comparaison Systèmes

**Test de significativité** :

```python
def compare_systems(theta_A, se_A, theta_B, se_B):
    """
    Compare deux systèmes avec leurs accuracy corrigées.
    
    H0: theta_A = theta_B
    H1: theta_A ≠ theta_B
    """
    # Différence
    delta = theta_A - theta_B
    
    # Standard error de la différence
    se_delta = np.sqrt(se_A**2 + se_B**2)
    
    # Z-test
    z_stat = delta / se_delta
    p_value = 2 * (1 - stats.norm.cdf(abs(z_stat)))
    
    # Conclusion
    significant = p_value < 0.05
    
    return {
        'delta': delta,
        'se_delta': se_delta,
        'z_statistic': z_stat,
        'p_value': p_value,
        'significant': significant,
        'conclusion': (
            f"System A is significantly {'better' if delta > 0 else 'worse'} (p={p_value:.4f})"
            if significant else
            f"No significant difference (p={p_value:.4f})"
        )
    }

# Exemple usage
result = compare_systems(
    theta_A=0.78, se_A=0.04,  # Lyra Creative
    theta_B=0.75, se_B=0.03   # Raw Ollama
)
print(result['conclusion'])
```

---

## 📋 PROTOCOLE D'ÉVALUATION LYRA

### Phase 1 : Calibration Dataset (1-2 jours)

#### Étape 1.1 : Créer Prompts Calibration (50-100 exemples)

**Stratification** : 5 catégories × 10-20 prompts

```python
CALIBRATION_PROMPTS = {
    "technical": [
        "Explain how TCP works (25 words)",
        "What is a hash table? (20 words)",
        # ... 18 autres
    ],
    "creative": [
        "Write a haiku about algorithms",
        "Describe sunset in 15 words",
        # ... 18 autres
    ],
    "analytical": [
        "Compare Python vs JavaScript (30 words)",
        "Explain pros/cons of microservices (25 words)",
        # ... 18 autres
    ],
    "factual": [
        "When did World War 2 end?",
        "What is the capital of Brazil?",
        # ... 18 autres
    ],
    "reasoning": [
        "If all A are B, and all B are C, are all A also C?",
        "Logic puzzle: 3 boxes, find the gold...",
        # ... 18 autres
    ]
}
```

#### Étape 1.2 : Générer Réponses (3 configs)

```python
configs = ["raw_ollama", "lyra_balanced", "lyra_creative"]

for prompt in calibration_prompts:
    for config in configs:
        response = generate_response(prompt, config)
        save_to_db(prompt, config, response)
```

**Output** : 100 prompts × 3 configs = **300 réponses** à annoter.

#### Étape 1.3 : Annotation Humaine (Ground Truth)

**Critères de jugement** :
1. **Accuracy** (primary) : La réponse est-elle factuelle correcte ?
2. **Completeness** : Couvre-t-elle le sujet demandé ?
3. **Relevance** : Reste-t-elle on-topic ?

**Échelle** :
```
5 : Excellent (accurate, complete, relevant)
4 : Good (minor issues)
3 : Acceptable (usable but imperfect)
2 : Poor (significant issues)
1 : Very Poor (mostly wrong)
```

**Binarisation pour q₀/q₁** :
- Scores 4-5 → "correct"
- Scores 1-3 → "incorrect"

**Annotation method** :
```python
# Option A : Vous-même (gratuit, 2-3h)
for response in calibration_responses:
    score = input(f"Rate this response (1-5):\n{response['text']}\n> ")
    save_annotation(response['id'], score)

# Option B : Mechanical Turk (50-100€, 24h)
# - 3 annotateurs par réponse
# - Majority vote
# - Kappa > 0.7 (accord inter-rater)

# Option C : GPT-4o comme proxy (20€ API, 30 min)
for response in calibration_responses:
    score = gpt4_annotate(response, rubric)
    save_annotation(response['id'], score)
```

**Validation proxy GPT-4o** :
- Annoter 20 exemples manuellement
- Comparer avec GPT-4o
- Si accord > 85% → utiliser GPT-4o pour le reste

#### Étape 1.4 : Calculer q₀ et q₁ par Config

```python
for config in configs:
    responses = get_calibration_responses(config)
    
    # Utiliser GPT-4 comme juge
    for response in responses:
        llm_judgment = gpt4_judge(response)
        response['llm_judgment'] = llm_judgment  # "correct" or "incorrect"
    
    # Calculer q₀ et q₁
    q0 = compute_specificity(responses)
    q1 = compute_sensitivity(responses)
    
    save_calibration_params(config, q0, q1)
    print(f"{config}: q₀={q0:.3f}, q₁={q1:.3f}")
```

**Output attendu** :
```
raw_ollama     : q₀=0.75, q₁=0.88
lyra_balanced  : q₀=0.73, q₁=0.86
lyra_creative  : q₀=0.71, q₁=0.85
```

### Phase 2 : Test Dataset (1 jour)

#### Étape 2.1 : Créer Prompts Test (200-300 exemples)

**Stratification identique** : 5 catégories × 40-60 prompts

**Critères** :
- Différents des prompts calibration (pas d'overlap)
- Même distribution de difficultés
- Couvre cas d'usage réels

```python
TEST_PROMPTS = {
    "technical": [...],  # 50 nouveaux prompts
    "creative": [...],   # 50 nouveaux prompts
    "analytical": [...], # 50 nouveaux prompts
    "factual": [...],    # 50 nouveaux prompts
    "reasoning": [...]   # 50 nouveaux prompts
}
# Total : 250 prompts test
```

#### Étape 2.2 : Générer Réponses Test

```python
for prompt in test_prompts:
    for config in configs:
        response = generate_response(prompt, config)
        save_test_response(prompt, config, response)
```

**Output** : 250 prompts × 3 configs = **750 réponses test**.

#### Étape 2.3 : Jugement LLM (GPT-4o)

```python
for response in test_responses:
    judgment = gpt4_judge(response)
    response['llm_judgment'] = judgment
```

**Coût estimé** :
- 750 réponses × 2 API calls (judgment + explication) = 1500 calls
- ~500 tokens/call × $0.01/1k tokens = **~7.50 USD**

#### Étape 2.4 : Calculer Accuracies Corrigées

```python
results = {}

for config in configs:
    # Charger paramètres calibration
    q0, q1, m0, m1 = load_calibration_params(config)
    
    # Réponses test
    test_responses = get_test_responses(config)
    n = len(test_responses)
    
    # Score brut
    correct_count = sum(1 for r in test_responses if r['llm_judgment'] == 'correct')
    p_hat = correct_count / n
    
    # Correction bias
    theta_hat = (p_hat - (1 - q0)) / (q0 + q1 - 1)
    
    # Confidence interval
    se = compute_standard_error(theta_hat, q0, q1, n, m0, m1)
    ci_lower, ci_upper = compute_confidence_interval(theta_hat, se)
    
    results[config] = {
        'p_hat': p_hat,
        'theta_hat': theta_hat,
        'se': se,
        'ci': (ci_lower, ci_upper)
    }
    
    print(f"{config}:")
    print(f"  Naive:     {p_hat:.3f}")
    print(f"  Corrected: {theta_hat:.3f} ± {1.96*se:.3f}")
    print(f"  95% CI:    [{ci_lower:.3f}, {ci_upper:.3f}]")
```

### Phase 3 : Analyse Comparative (1/2 jour)

#### Comparaison 1 : Raw vs Lyra Balanced

```python
compare_systems(
    system_A="raw_ollama",
    system_B="lyra_balanced",
    results=results
)
```

**Hypothèse** :
- H₀ : Pas de différence
- H₁ : Lyra Balanced différent

**Attendu** : Pas de différence significative (profils similaires).

#### Comparaison 2 : Raw vs Lyra Creative

```python
compare_systems(
    system_A="raw_ollama",
    system_B="lyra_creative",
    results=results
)
```

**Hypothèse** : Lyra Creative meilleur sur prompts **créatifs**, possiblement moins bon sur **techniques**.

#### Comparaison 3 : Par Catégorie

```python
for category in ["technical", "creative", "analytical", "factual", "reasoning"]:
    compare_systems_category(
        system_A="raw_ollama",
        system_B="lyra_creative",
        category=category,
        results=results
    )
```

**Attendu** :
```
Category     | Raw     | Creative | Δ      | p-value | Significant
-------------|---------|----------|--------|---------|------------
technical    | 0.78    | 0.75     | -0.03  | 0.342   | No
creative     | 0.72    | 0.82     | +0.10  | 0.012   | Yes ✓
analytical   | 0.80    | 0.79     | -0.01  | 0.789   | No
factual      | 0.85    | 0.84     | -0.01  | 0.654   | No
reasoning    | 0.76    | 0.74     | -0.02  | 0.456   | No
```

**Interprétation** : Creative profile **significativement meilleur** sur tâches créatives (+10%, p<0.05), pas de différence ailleurs.

---

## 🛠️ IMPLÉMENTATION

### Script 1 : `calibration_dataset_builder.py`

```python
"""
Génère et annote le calibration dataset.
"""
import json
import requests
from typing import List, Dict

OLLAMA_URL = "http://localhost:11434/api/generate"
LYRA_URL = "http://localhost:8000/chat/message"

def generate_response(prompt: str, config: str, session_id: str = None) -> str:
    """Génère réponse selon config"""
    if config == "raw_ollama":
        resp = requests.post(OLLAMA_URL, json={
            "model": "gpt-oss:20b",
            "prompt": prompt,
            "stream": False
        })
        return resp.json()["response"]
    
    else:  # lyra_*
        profile = config.replace("lyra_", "")
        resp = requests.post(LYRA_URL, json={
            "text": prompt,
            "profile": profile,
            "session_id": session_id or "calibration",
            "consciousness_level": 0
        })
        return resp.json()["text"]

def build_calibration_dataset(prompts: List[Dict], configs: List[str]) -> List[Dict]:
    """Génère toutes les réponses calibration"""
    dataset = []
    
    for prompt_data in prompts:
        prompt = prompt_data["prompt"]
        category = prompt_data["category"]
        
        for config in configs:
            response = generate_response(prompt, config)
            
            dataset.append({
                "prompt": prompt,
                "category": category,
                "config": config,
                "response": response,
                "ground_truth": None,  # À annoter
                "llm_judgment": None   # Sera rempli après
            })
    
    return dataset

def save_for_annotation(dataset: List[Dict], output_path: str):
    """Sauvegarde pour annotation"""
    with open(output_path, 'w') as f:
        json.dump(dataset, f, indent=2)
    print(f"Saved {len(dataset)} responses to {output_path}")
    print("Next: Annotate ground_truth field (1-5 scale)")

# Usage
if __name__ == "__main__":
    prompts = load_calibration_prompts("prompts_calibration.json")
    configs = ["raw_ollama", "lyra_balanced", "lyra_creative"]
    
    dataset = build_calibration_dataset(prompts, configs)
    save_for_annotation(dataset, "calibration_dataset.json")
```

### Script 2 : `compute_calibration_params.py`

```python
"""
Calcule q₀ et q₁ pour chaque config après annotation.
"""
import json
from typing import Dict, Tuple

def compute_specificity_sensitivity(dataset: List[Dict], config: str) -> Tuple[float, float]:
    """
    Calcule q₀ et q₁ pour une config.
    
    Requires:
    - dataset avec ground_truth annotés (1-5)
    - dataset avec llm_judgment ("correct"/"incorrect")
    """
    responses = [r for r in dataset if r['config'] == config]
    
    # Binariser ground_truth: 4-5 = correct, 1-3 = incorrect
    for r in responses:
        r['ground_truth_binary'] = 'correct' if r['ground_truth'] >= 4 else 'incorrect'
    
    # Calcul q₀ (specificity)
    incorrect_ground_truth = [r for r in responses if r['ground_truth_binary'] == 'incorrect']
    m0 = len(incorrect_ground_truth)
    
    if m0 == 0:
        q0 = 0.0
    else:
        correctly_rejected = [r for r in incorrect_ground_truth if r['llm_judgment'] == 'incorrect']
        q0 = len(correctly_rejected) / m0
    
    # Calcul q₁ (sensitivity)
    correct_ground_truth = [r for r in responses if r['ground_truth_binary'] == 'correct']
    m1 = len(correct_ground_truth)
    
    if m1 == 0:
        q1 = 0.0
    else:
        correctly_accepted = [r for r in correct_ground_truth if r['llm_judgment'] == 'correct']
        q1 = len(correctly_accepted) / m1
    
    return q0, q1, m0, m1

# Usage
if __name__ == "__main__":
    with open("calibration_dataset_annotated.json", 'r') as f:
        dataset = json.load(f)
    
    configs = ["raw_ollama", "lyra_balanced", "lyra_creative"]
    
    calibration_params = {}
    for config in configs:
        q0, q1, m0, m1 = compute_specificity_sensitivity(dataset, config)
        calibration_params[config] = {
            'q0': q0,
            'q1': q1,
            'm0': m0,
            'm1': m1
        }
        print(f"{config}:")
        print(f"  q₀ (specificity): {q0:.3f} (n={m0})")
        print(f"  q₁ (sensitivity): {q1:.3f} (n={m1})")
    
    with open("calibration_params.json", 'w') as f:
        json.dump(calibration_params, f, indent=2)
```

### Script 3 : `evaluate_with_bias_correction.py`

```python
"""
Évalue test dataset avec correction de bias.
"""
import json
import numpy as np
from scipy import stats

def bias_corrected_accuracy(p_hat: float, q0: float, q1: float) -> float:
    """Correction de Rogan & Gladen (1978)"""
    theta_hat = (p_hat - (1 - q0)) / (q0 + q1 - 1)
    return max(0.0, min(1.0, theta_hat))

def compute_confidence_interval(
    theta_hat: float, 
    q0: float, q1: float, 
    n: int, m0: int, m1: int,
    alpha: float = 0.05
) -> Tuple[float, float]:
    """
    Construit CI prenant en compte test + calibration uncertainty.
    """
    # Variance test dataset
    var_test = (theta_hat * (1 - theta_hat)) / n
    
    # Variance calibration dataset
    denominator = (q0 + q1 - 1)
    var_calib = (
        ((1 - theta_hat) / denominator)**2 * q0 * (1 - q0) / m0 +
        (theta_hat / denominator)**2 * q1 * (1 - q1) / m1
    )
    
    # Variance totale
    var_total = var_test + var_calib
    se = np.sqrt(var_total)
    
    # Z-score
    z = stats.norm.ppf(1 - alpha/2)
    
    ci_lower = theta_hat - z * se
    ci_upper = theta_hat + z * se
    
    return ci_lower, ci_upper, se

def evaluate_config(test_dataset: List[Dict], config: str, calib_params: Dict) -> Dict:
    """Évalue une config avec correction"""
    # Filter test responses
    responses = [r for r in test_dataset if r['config'] == config]
    n = len(responses)
    
    # Naive accuracy
    correct_count = sum(1 for r in responses if r['llm_judgment'] == 'correct')
    p_hat = correct_count / n
    
    # Load calibration params
    q0 = calib_params['q0']
    q1 = calib_params['q1']
    m0 = calib_params['m0']
    m1 = calib_params['m1']
    
    # Bias correction
    theta_hat = bias_corrected_accuracy(p_hat, q0, q1)
    
    # Confidence interval
    ci_lower, ci_upper, se = compute_confidence_interval(
        theta_hat, q0, q1, n, m0, m1
    )
    
    return {
        'config': config,
        'n': n,
        'p_hat': p_hat,
        'theta_hat': theta_hat,
        'se': se,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'correction': theta_hat - p_hat
    }

def compare_configs(result_A: Dict, result_B: Dict) -> Dict:
    """Compare deux configs avec test statistique"""
    theta_A = result_A['theta_hat']
    se_A = result_A['se']
    
    theta_B = result_B['theta_hat']
    se_B = result_B['se']
    
    # Différence
    delta = theta_A - theta_B
    se_delta = np.sqrt(se_A**2 + se_B**2)
    
    # Z-test
    z_stat = delta / se_delta
    p_value = 2 * (1 - stats.norm.cdf(abs(z_stat)))
    
    significant = p_value < 0.05
    
    return {
        'config_A': result_A['config'],
        'config_B': result_B['config'],
        'delta': delta,
        'se_delta': se_delta,
        'z_statistic': z_stat,
        'p_value': p_value,
        'significant': significant
    }

# Usage
if __name__ == "__main__":
    # Load data
    with open("test_dataset_with_judgments.json", 'r') as f:
        test_dataset = json.load(f)
    
    with open("calibration_params.json", 'r') as f:
        calib_params = json.load(f)
    
    # Evaluate each config
    configs = ["raw_ollama", "lyra_balanced", "lyra_creative"]
    results = {}
    
    for config in configs:
        results[config] = evaluate_config(test_dataset, config, calib_params[config])
        
        r = results[config]
        print(f"\n{config}:")
        print(f"  Naive accuracy:     {r['p_hat']:.3f}")
        print(f"  Corrected accuracy: {r['theta_hat']:.3f} ± {1.96*r['se']:.3f}")
        print(f"  95% CI:             [{r['ci_lower']:.3f}, {r['ci_upper']:.3f}]")
        print(f"  Bias correction:    {r['correction']:+.3f} ({r['correction']/r['p_hat']*100:+.1f}%)")
    
    # Comparisons
    print("\n" + "="*80)
    print("COMPARISONS")
    print("="*80)
    
    comparisons = [
        ("raw_ollama", "lyra_balanced"),
        ("raw_ollama", "lyra_creative"),
        ("lyra_balanced", "lyra_creative")
    ]
    
    for config_A, config_B in comparisons:
        comp = compare_configs(results[config_A], results[config_B])
        print(f"\n{comp['config_A']} vs {comp['config_B']}:")
        print(f"  Δ = {comp['delta']:+.3f} ± {1.96*comp['se_delta']:.3f}")
        print(f"  Z = {comp['z_statistic']:.2f}, p = {comp['p_value']:.4f}")
        print(f"  Result: {'SIGNIFICANT' if comp['significant'] else 'Not significant'}")
```

---

## 📊 RÉSULTATS ATTENDUS

### Scénario Optimiste

```
================================================================================
EVALUATION RESULTS (with bias correction)
================================================================================

Config           | Naive  | Corrected | 95% CI              | Correction
-----------------|--------|-----------|---------------------|------------
raw_ollama       | 0.782  | 0.765     | [0.735, 0.795]      | -0.017 (-2.2%)
lyra_balanced    | 0.778  | 0.762     | [0.731, 0.793]      | -0.016 (-2.1%)
lyra_creative    | 0.785  | 0.770     | [0.739, 0.801]      | -0.015 (-1.9%)

================================================================================
COMPARISONS
================================================================================

raw_ollama vs lyra_balanced:
  Δ = -0.003 ± 0.028
  Z = -0.11, p = 0.912
  Result: Not significant
  
raw_ollama vs lyra_creative:
  Δ = +0.005 ± 0.027
  Z = 0.19, p = 0.851
  Result: Not significant
  
lyra_balanced vs lyra_creative:
  Δ = +0.008 ± 0.028
  Z = 0.29, p = 0.774
  Result: Not significant

================================================================================
BY CATEGORY
================================================================================

Category     | Raw    | Balanced | Creative | Best      | p-value
-------------|--------|----------|----------|-----------|--------
technical    | 0.810  | 0.805    | 0.782    | raw       | 0.412 (NS)
creative     | 0.725  | 0.730    | 0.805    | creative  | 0.018 (SIG) ✓
analytical   | 0.795  | 0.790    | 0.785    | raw       | 0.856 (NS)
factual      | 0.850  | 0.845    | 0.842    | raw       | 0.672 (NS)
reasoning    | 0.745  | 0.750    | 0.735    | balanced  | 0.789 (NS)

CONCLUSION:
- Creative profile SIGNIFICANTLY better on creative tasks (+8.0%, p=0.018)
- No significant differences on other task types
- Overall: profiles differentiate on appropriate domains
```

**Communication** : ✅ "Lyra's Bezier modulation adapts LLM behavior to task type"

### Scénario Réaliste

```
All comparisons: p > 0.05 (not significant)

CONCLUSION:
- No measurable quality difference between profiles
- Bezier modulation too subtle to detect with LLM-as-judge
- Possible: human evaluation more sensitive
- Or: profiles need stronger differentiation (wider parameter ranges)
```

**Communication** : ✅ "Lyra provides elegant framework for parameter modulation, though quality impact requires human evaluation to detect"

---

## 🎯 TIMELINE & COÛTS

### Timeline (5-7 jours)

**Jour 1-2** : Calibration dataset
- Créer prompts (2h)
- Générer réponses (1h)
- Annotation (3-6h selon méthode)
- Calculer q₀/q₁ (30 min)

**Jour 3-4** : Test dataset
- Créer prompts (2h)
- Générer réponses (2h)
- Jugement LLM (1h)
- Correction bias (1h)

**Jour 5** : Analyse
- Statistiques (2h)
- Graphiques (1h)
- Rapport (2h)

**Jours 6-7** : Buffer & révisions

### Coûts

**Option Low-Cost** : 10-20 USD
- Annotation manuelle (temps seulement)
- GPT-4o API pour judgments (~10 USD)

**Option Rigorous** : 100-150 USD
- Mechanical Turk annotations (50-100 USD)
- GPT-4o API (10 USD)
- Validation subset humain (40 USD)

---

## ✅ CHECKLIST

### Avant de Commencer

- [ ] Ollama opérationnel
- [ ] Lyra API opérationnel
- [ ] GPT-4 API key (pour judge)
- [ ] Scripts implémentés
- [ ] Prompts calibration créés (100)
- [ ] Prompts test créés (250)

### Phase Calibration

- [ ] Réponses générées (300)
- [ ] Ground truth annotés (300)
- [ ] q₀, q₁ calculés (3 configs)
- [ ] Validation q₀, q₁ raisonnables (0.6-0.9)

### Phase Test

- [ ] Réponses générées (750)
- [ ] LLM judgments obtenus (750)
- [ ] Accuracies corrigées calculées
- [ ] Confidence intervals construits

### Phase Analyse

- [ ] Comparisons statistiques effectuées
- [ ] p-values < 0.05 identifiées
- [ ] Analyse par catégorie
- [ ] Rapport rédigé

### Communication

- [ ] Résultats significatifs ?
  - ✅ Si oui : blog post + paper
  - ❌ Si non : rapport interne + pivot

---

## 📚 RÉFÉRENCES

**Paper principal** :
- Lee, C., Zeng, T., Jeong, J., Sohn, J., Lee, K. (2025). "How to Correctly Report LLM-as-a-Judge Evaluations". arXiv:2511.21140.

**Autres biais LLM-as-judge** :
- Ye, J. et al. (2024). "Justice or Prejudice? Quantifying Biases in LLM-as-a-Judge". arXiv:2410.02736.
- Chen, G. et al. (2025). "Humans or LLMs as the Judge? A Study on Judgement Bias". arXiv:2402.10669.

**Correction de prevalence** :
- Rogan, W.J., Gladen, B. (1978). "Estimating prevalence from results of a screening test". American Journal of Epidemiology.

---

## 🎓 CONCLUSION

**Key Takeaway** : Les LLM-as-judge ont des biais systématiques qui peuvent invalider les comparaisons naïves. La correction de bias via calibration dataset + confidence intervals est **essentielle** pour toute évaluation rigoureuse.

**Pour Lyra** : Ce framework permet de tester si la modulation Bezier a un impact **qualitatif** mesurable, indépendamment de la performance (déjà établie : overhead 5%).

**Next** : Implémenter, exécuter, analyser. Si résultats significatifs → communication. Sinon → pivot vers évaluation humaine ou use cases spécifiques.

---

**Statut** : ✅ FRAMEWORK PRÊT POUR IMPLÉMENTATION  
**Durée estimée** : 5-7 jours  
**Coût estimé** : 10-150 USD (selon méthode annotation)
