# PHASE 3 - VALIDATION BRIEF
## Mission : Identifier la source réelle du gain de performance Lyra

**Date :** 2025-12-04  
**Durée estimée :** 2-3 heures  
**Priorité :** CRITIQUE (bloque communication résultats)

---

## 📊 CONTEXTE

### Résultats Initiaux (matrix_results.jsonl)

Benchmark Phase 3 montre des gains de performance surprenants :

```
Configuration          | Latency (ms) | Std Dev | Delta vs Raw | Coherence
-----------------------|--------------|---------|--------------|----------
Raw Ollama (baseline)  | 4678         | 1771    | —            | 0.7250
Lyra Balanced          | 4132         | 993     | -11.7%       | 0.7238
Lyra Creative          | 4074         | 1324    | -12.9%       | 0.7224
Lyra Memory            | 4093         | 1131    | -12.5%       | 0.7147
```

**Résultat contre-intuitif** : Lyra (avec overhead FastAPI + context extraction) est **12% plus rapide** que Raw Ollama direct.

**Qualité sémantique préservée** : Coherence identique (~0.72).

### Problèmes Identifiés

#### Problème 1 : Pas de modulation temporelle
```json
// TOUS les prompts Lyra ont t=0.0
"physics": {"t": 0.0, "tau_c": 1.0, "rho": 0.0, "delta_r": 0.0, "kappa": 0.5}
```

**Cause** : Pas de `session_id` persistant → chaque prompt = nouvelle session → t reste à 0.

**Impact** : Trajectoire Bezier non exploitée (on reste sur point initial).

#### Problème 2 : Context injection désactivé
```json
"context_used": {
    "neighbor_concepts": [],  // Toujours vide
    "total_weight": 0,        // Toujours 0
}
```

**Cause** : Graphe sémantique vide ou keywords ne matchent rien.

**Impact** : Lyra Memory = Lyra Balanced en pratique.

#### Problème 3 : Paramètres non comparables
```python
# Raw Ollama (via curl)
{
  "model": "gpt-oss:20b",
  "messages": [...],
  "stream": false
  # Pas d'options → defaults Ollama
}

# Lyra (via llm_client.py)
{
  "model": "gpt-oss:20b",
  "messages": [...],
  "options": {
    "temperature": 0.8 / tau_c,  # Modulé
    "num_predict": 4096,
    "top_k": 40,
    "top_p": 0.9,
    "repeat_penalty": 1.0 + penalties
  }
}
```

**Différences possibles** :
- `num_predict` : 4096 vs illimité ?
- `temperature` : 0.8 vs default Ollama (0.8 aussi ?)
- Autres params implicites différents ?

#### Problème 4 : Ordre d'exécution fixe
```
Benchmark exécute : Raw → Balanced → Creative → Memory
```

**Biais possible** : Ollama "warm-up" progressif ? Creative/Memory bénéficient de cache ?

---

## 🎯 OBJECTIFS

### Objectif Principal
**Déterminer si le gain de 12% est réel ou artefact de mesure.**

### Objectifs Secondaires
1. Identifier la source exacte du gain (température, paramètres, warm-up, longueur réponse)
2. Valider ou invalider chaque hypothèse avec données quantitatives
3. Corriger les bugs identifiés (t=0, context vide)
4. Produire un benchmark "propre" avec biais éliminés
5. Documenter méthodologie pour communication résultats

---

## 🧪 HYPOTHÈSES À TESTER

### Hypothèse 1 : Température différente
**Affirmation** : Lyra Creative utilise temperature=0.615 (via tau_c=1.3) vs Raw=0.8 default.

**Test** : Comparer Raw avec temperature=0.615 explicite vs Raw default.

**Prédiction** : Si H1 vraie → raw_temp_0.615 ≈ lyra_creative en latence.

### Hypothèse 2 : Paramètres Ollama différents
**Affirmation** : `num_predict=4096`, `top_k=40`, etc. affectent performance.

**Test** : Raw avec TOUS les paramètres identiques à Lyra.

**Prédiction** : Si H2 vraie → raw_explicit ≈ lyra_balanced.

### Hypothèse 3 : Warm-up progressif Ollama
**Affirmation** : Ollama devient plus rapide après plusieurs requêtes (cache, GPU warm).

**Test** : Inverser ordre exécution (Lyra first, Raw last).

**Prédiction** : Si H3 vraie → Raw devient plus rapide quand exécuté après Lyra.

### Hypothèse 4 : Réponses plus courtes
**Affirmation** : Lyra génère moins de tokens → plus rapide.

**Test** : Compter tokens exacts (pas approximation caractères).

**Prédiction** : Si H4 vraie → correlation négative (tokens ↓ → latency ↓).

---

## 🛠️ IMPLÉMENTATION

### Tâche 1 : Créer `benchmark_phase3_validation.py`

**Objectif** : Script qui teste les 4 hypothèses en une seule exécution.

#### Structure du Script

```python
"""
PHASE 3 - VALIDATION BENCHMARK
==============================

Tests 4 hypotheses pour expliquer gain performance Lyra vs Raw:
1. Temperature difference
2. Ollama parameters difference
3. Warm-up order effect
4. Response length difference

Usage:
    python benchmark_phase3_validation.py --output validation_results.jsonl
"""

import requests
import json
import time
import uuid
from typing import List, Dict, Any
from datetime import datetime
import numpy as np

# URLs
OLLAMA_URL = "http://localhost:11434"
LYRA_URL = "http://localhost:8000"

# Prompts (subset for speed - 10 prompts = 10min)
VALIDATION_PROMPTS = [
    {"domain": "technical", "prompt": "What is machine learning? (20 words max)"},
    {"domain": "technical", "prompt": "Explain Python briefly (20 words max)"},
    {"domain": "technical", "prompt": "What is AI? (20 words max)"},
    {"domain": "creative", "prompt": "Write a haiku about code"},
    {"domain": "creative", "prompt": "Describe blue poetically (15 words max)"},
    {"domain": "analytical", "prompt": "Compare Linux and Windows (25 words max)"},
    {"domain": "analytical", "prompt": "Explain quantum computing (25 words max)"},
    {"domain": "philosophical", "prompt": "What is consciousness? (20 words)"},
    {"domain": "philosophical", "prompt": "Can machines think? (20 words)"},
    {"domain": "practical", "prompt": "How to debug code? (steps in 20 words)"},
]

# Configurations to test
VALIDATION_CONFIGS = {
    # BASELINE
    "raw_default": {
        "label": "Raw Default",
        "url": OLLAMA_URL,
        "endpoint": "/api/chat",
        "params": {
            "model": "gpt-oss:20b",
            "stream": False
            # No options → Ollama defaults
        }
    },
    
    # HYPOTHESIS 1: Temperature explicit
    "raw_temp_0.8": {
        "label": "Raw Temp 0.8",
        "url": OLLAMA_URL,
        "endpoint": "/api/chat",
        "params": {
            "model": "gpt-oss:20b",
            "stream": False,
            "options": {
                "temperature": 0.8
            }
        }
    },
    
    "raw_temp_0.615": {
        "label": "Raw Temp 0.615 (Creative equivalent)",
        "url": OLLAMA_URL,
        "endpoint": "/api/chat",
        "params": {
            "model": "gpt-oss:20b",
            "stream": False,
            "options": {
                "temperature": 0.615  # Same as Lyra Creative
            }
        }
    },
    
    # HYPOTHESIS 2: All params explicit
    "raw_explicit": {
        "label": "Raw Explicit (Lyra-equivalent params)",
        "url": OLLAMA_URL,
        "endpoint": "/api/chat",
        "params": {
            "model": "gpt-oss:20b",
            "stream": False,
            "options": {
                "temperature": 0.8,
                "num_predict": 4096,
                "top_k": 40,
                "top_p": 0.9,
                "repeat_penalty": 1.0
            }
        }
    },
    
    # REFERENCE: Lyra Balanced (for comparison)
    "lyra_balanced": {
        "label": "Lyra Balanced",
        "url": LYRA_URL,
        "endpoint": "/chat/message",
        "params": {
            "profile": "balanced",
            "enable_context": False,
            "consciousness_level": 0
        }
    },
    
    # REFERENCE: Lyra Creative (for comparison)
    "lyra_creative": {
        "label": "Lyra Creative",
        "url": LYRA_URL,
        "endpoint": "/chat/message",
        "params": {
            "profile": "creative",
            "enable_context": False,
            "consciousness_level": 0
        }
    },
}

def call_ollama_direct(config: Dict, prompt: str) -> Dict[str, Any]:
    """Call Ollama API directly"""
    start = time.time()
    
    payload = {**config["params"]}
    payload["messages"] = [{"role": "user", "content": prompt}]
    
    try:
        resp = requests.post(
            f"{config['url']}{config['endpoint']}",
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        
        latency_ms = (time.time() - start) * 1000
        
        # Extract response
        response_text = data.get("message", {}).get("content", "")
        
        return {
            "success": True,
            "response": response_text,
            "latency_ms": latency_ms,
            "meta": {"raw_response": data}
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "latency_ms": (time.time() - start) * 1000
        }

def call_lyra(config: Dict, prompt: str, session_id: str) -> Dict[str, Any]:
    """Call Lyra API"""
    start = time.time()
    
    payload = {
        "text": prompt,
        "session_id": session_id,  # IMPORTANT: persistent session
        **config["params"]
    }
    
    try:
        resp = requests.post(
            f"{config['url']}{config['endpoint']}",
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        
        latency_ms = (time.time() - start) * 1000
        
        return {
            "success": True,
            "response": data.get("text", ""),
            "latency_ms": latency_ms,
            "meta": {
                "physics": data.get("physics_state"),
                "context": data.get("context")
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "latency_ms": (time.time() - start) * 1000
        }

def compute_coherence(prompt: str, response: str) -> float:
    """Compute semantic coherence (placeholder - use embeddings in real impl)"""
    # TODO: Use mxbai-embed-large for real coherence
    # For now, simple heuristic
    prompt_words = set(prompt.lower().split())
    response_words = set(response.lower().split())
    overlap = len(prompt_words & response_words)
    return overlap / max(len(prompt_words), 1)

def count_tokens_approx(text: str) -> int:
    """Approximate token count (4 chars ≈ 1 token)"""
    return len(text) // 4

def run_validation_benchmark(output_file: str = "validation_results.jsonl"):
    """
    Run validation benchmark with 2 execution orders:
    1. Normal: Raw configs first, then Lyra
    2. Reversed: Lyra first, then Raw configs
    """
    
    results = []
    
    # ORDER 1: Normal (Raw → Lyra)
    print("\n" + "="*80)
    print("ORDER 1: Raw → Lyra (testing warm-up hypothesis)")
    print("="*80)
    
    order_1_configs = [
        "raw_default",
        "raw_temp_0.8",
        "raw_temp_0.615",
        "raw_explicit",
        "lyra_balanced",
        "lyra_creative"
    ]
    
    for config_id in order_1_configs:
        config = VALIDATION_CONFIGS[config_id]
        session_id = str(uuid.uuid4())  # One session per config
        
        print(f"\n[{config_id}] {config['label']}")
        print("-" * 60)
        
        for i, item in enumerate(VALIDATION_PROMPTS, 1):
            prompt = item["prompt"]
            domain = item["domain"]
            
            print(f"  [{i}/10] {prompt[:50]}...", end=" ", flush=True)
            
            # Call appropriate API
            if config_id.startswith("raw_"):
                result = call_ollama_direct(config, prompt)
            else:
                result = call_lyra(config, prompt, session_id)
            
            if result["success"]:
                print(f"✓ {result['latency_ms']:.0f}ms")
                
                # Compute metrics
                coherence = compute_coherence(prompt, result["response"])
                tokens = count_tokens_approx(result["response"])
                
                # Store result
                results.append({
                    "execution_order": "normal",
                    "config_id": config_id,
                    "config_label": config["label"],
                    "domain": domain,
                    "prompt": prompt,
                    "response": result["response"],
                    "latency_ms": result["latency_ms"],
                    "coherence": round(coherence, 4),
                    "tokens_approx": tokens,
                    "meta": result.get("meta", {}),
                    "timestamp": datetime.now().isoformat()
                })
                
                # Save incrementally
                with open(output_file, "a") as f:
                    f.write(json.dumps(results[-1]) + "\n")
                    
            else:
                print(f"✗ {result.get('error', 'Unknown error')}")
            
            # Small delay between requests
            time.sleep(0.5)
    
    # ORDER 2: Reversed (Lyra → Raw)
    print("\n\n" + "="*80)
    print("ORDER 2: Lyra → Raw (control for warm-up)")
    print("="*80)
    
    order_2_configs = list(reversed(order_1_configs))
    
    for config_id in order_2_configs:
        config = VALIDATION_CONFIGS[config_id]
        session_id = str(uuid.uuid4())
        
        print(f"\n[{config_id}] {config['label']}")
        print("-" * 60)
        
        for i, item in enumerate(VALIDATION_PROMPTS, 1):
            prompt = item["prompt"]
            domain = item["domain"]
            
            print(f"  [{i}/10] {prompt[:50]}...", end=" ", flush=True)
            
            if config_id.startswith("raw_"):
                result = call_ollama_direct(config, prompt)
            else:
                result = call_lyra(config, prompt, session_id)
            
            if result["success"]:
                print(f"✓ {result['latency_ms']:.0f}ms")
                
                coherence = compute_coherence(prompt, result["response"])
                tokens = count_tokens_approx(result["response"])
                
                results.append({
                    "execution_order": "reversed",
                    "config_id": config_id,
                    "config_label": config["label"],
                    "domain": domain,
                    "prompt": prompt,
                    "response": result["response"],
                    "latency_ms": result["latency_ms"],
                    "coherence": round(coherence, 4),
                    "tokens_approx": tokens,
                    "meta": result.get("meta", {}),
                    "timestamp": datetime.now().isoformat()
                })
                
                with open(output_file, "a") as f:
                    f.write(json.dumps(results[-1]) + "\n")
                    
            else:
                print(f"✗ {result.get('error', 'Unknown error')}")
            
            time.sleep(0.5)
    
    print("\n" + "="*80)
    print(f"✓ Validation benchmark complete: {len(results)} results")
    print(f"✓ Saved to: {output_file}")
    print("="*80)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Phase 3 Validation Benchmark")
    parser.add_argument("--output", default="validation_results.jsonl", help="Output file")
    args = parser.parse_args()
    
    run_validation_benchmark(args.output)
```

#### Spécifications Techniques

**Nombre de requêtes** :
```
10 prompts × 6 configs × 2 orders = 120 requêtes totales
Durée estimée : ~15-20 minutes
```

**Ordre d'exécution** :
```
Order 1 (Normal):
  1. raw_default
  2. raw_temp_0.8
  3. raw_temp_0.615
  4. raw_explicit
  5. lyra_balanced
  6. lyra_creative

Order 2 (Reversed):
  6. lyra_creative
  5. lyra_balanced
  4. raw_explicit
  3. raw_temp_0.615
  2. raw_temp_0.8
  1. raw_default
```

**Format de sortie** (JSONL) :
```json
{
  "execution_order": "normal",
  "config_id": "raw_temp_0.615",
  "config_label": "Raw Temp 0.615",
  "domain": "technical",
  "prompt": "What is AI?",
  "response": "AI is...",
  "latency_ms": 3542.1,
  "coherence": 0.7234,
  "tokens_approx": 42,
  "meta": {...},
  "timestamp": "2025-12-04T12:00:00"
}
```

---

### Tâche 2 : Créer `analyze_phase3_validation.py`

**Objectif** : Analyser validation_results.jsonl et répondre aux 4 hypothèses.

```python
"""
PHASE 3 - VALIDATION ANALYSIS
=============================

Analyze validation benchmark results to test 4 hypotheses.

Usage:
    python analyze_phase3_validation.py validation_results.jsonl
"""

import json
import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List

def load_results(jsonl_file: str) -> pd.DataFrame:
    """Load JSONL into DataFrame"""
    with open(jsonl_file) as f:
        data = [json.loads(line) for line in f if line.strip()]
    return pd.DataFrame(data)

def test_hypothesis_1_temperature(df: pd.DataFrame):
    """
    H1: Temperature affects latency
    
    Compare:
    - raw_default (temp unknown)
    - raw_temp_0.8 (temp explicit)
    - raw_temp_0.615 (lower temp)
    - lyra_creative (temp 0.615 via tau_c)
    """
    print("\n" + "="*80)
    print("HYPOTHESIS 1: Temperature Impact")
    print("="*80)
    
    configs = ["raw_default", "raw_temp_0.8", "raw_temp_0.615", "lyra_creative"]
    
    for order in ["normal", "reversed"]:
        print(f"\n--- Execution Order: {order} ---")
        
        subset = df[df["execution_order"] == order]
        
        for config in configs:
            data = subset[subset["config_id"] == config]
            if len(data) > 0:
                latency = data["latency_ms"].mean()
                std = data["latency_ms"].std()
                coherence = data["coherence"].mean()
                tokens = data["tokens_approx"].mean()
                
                print(f"{config:20} | {latency:7.1f}ms ± {std:5.1f} | "
                      f"coherence={coherence:.3f} | tokens={tokens:.1f}")
    
    # Statistical test: temp_0.615 vs temp_0.8
    normal = df[df["execution_order"] == "normal"]
    
    temp_low = normal[normal["config_id"] == "raw_temp_0.615"]["latency_ms"]
    temp_high = normal[normal["config_id"] == "raw_temp_0.8"]["latency_ms"]
    
    if len(temp_low) > 0 and len(temp_high) > 0:
        t_stat, p_value = stats.ttest_ind(temp_low, temp_high)
        delta = temp_low.mean() - temp_high.mean()
        delta_pct = (delta / temp_high.mean()) * 100
        
        print(f"\nT-test (temp_0.615 vs temp_0.8):")
        print(f"  Δ latency: {delta:+.1f}ms ({delta_pct:+.1f}%)")
        print(f"  t-statistic: {t_stat:.3f}")
        print(f"  p-value: {p_value:.4f}")
        print(f"  Significant: {'YES' if p_value < 0.05 else 'NO'}")

def test_hypothesis_2_parameters(df: pd.DataFrame):
    """
    H2: Ollama parameters affect latency
    
    Compare:
    - raw_default (implicit params)
    - raw_explicit (explicit params matching Lyra)
    - lyra_balanced (same params via framework)
    """
    print("\n" + "="*80)
    print("HYPOTHESIS 2: Parameters Impact")
    print("="*80)
    
    configs = ["raw_default", "raw_explicit", "lyra_balanced"]
    
    for order in ["normal", "reversed"]:
        print(f"\n--- Execution Order: {order} ---")
        
        subset = df[df["execution_order"] == order]
        
        for config in configs:
            data = subset[subset["config_id"] == config]
            if len(data) > 0:
                latency = data["latency_ms"].mean()
                std = data["latency_ms"].std()
                coherence = data["coherence"].mean()
                
                print(f"{config:20} | {latency:7.1f}ms ± {std:5.1f} | coherence={coherence:.3f}")
    
    # Statistical test
    normal = df[df["execution_order"] == "normal"]
    
    raw_def = normal[normal["config_id"] == "raw_default"]["latency_ms"]
    raw_exp = normal[normal["config_id"] == "raw_explicit"]["latency_ms"]
    lyra_bal = normal[normal["config_id"] == "lyra_balanced"]["latency_ms"]
    
    if len(raw_def) > 0 and len(raw_exp) > 0:
        delta_explicit = raw_exp.mean() - raw_def.mean()
        delta_pct = (delta_explicit / raw_def.mean()) * 100
        
        print(f"\nΔ (explicit - default): {delta_explicit:+.1f}ms ({delta_pct:+.1f}%)")
    
    if len(raw_exp) > 0 and len(lyra_bal) > 0:
        delta_lyra = lyra_bal.mean() - raw_exp.mean()
        delta_pct = (delta_lyra / raw_exp.mean()) * 100
        
        print(f"Δ (lyra - raw_explicit): {delta_lyra:+.1f}ms ({delta_pct:+.1f}%)")

def test_hypothesis_3_warmup(df: pd.DataFrame):
    """
    H3: Execution order affects latency (warm-up)
    
    Compare same config in normal vs reversed order.
    """
    print("\n" + "="*80)
    print("HYPOTHESIS 3: Warm-up / Order Effect")
    print("="*80)
    
    configs = ["raw_default", "lyra_balanced", "lyra_creative"]
    
    for config in configs:
        normal = df[(df["config_id"] == config) & (df["execution_order"] == "normal")]
        reversed_data = df[(df["config_id"] == config) & (df["execution_order"] == "reversed")]
        
        if len(normal) > 0 and len(reversed_data) > 0:
            lat_normal = normal["latency_ms"].mean()
            lat_reversed = reversed_data["latency_ms"].mean()
            delta = lat_reversed - lat_normal
            delta_pct = (delta / lat_normal) * 100
            
            print(f"\n{config}:")
            print(f"  Normal order:   {lat_normal:7.1f}ms")
            print(f"  Reversed order: {lat_reversed:7.1f}ms")
            print(f"  Δ (reversed - normal): {delta:+.1f}ms ({delta_pct:+.1f}%)")
            
            # T-test
            t_stat, p_value = stats.ttest_ind(
                normal["latency_ms"],
                reversed_data["latency_ms"]
            )
            print(f"  p-value: {p_value:.4f} {'(significant)' if p_value < 0.05 else ''}")

def test_hypothesis_4_length(df: pd.DataFrame):
    """
    H4: Response length correlates with latency
    """
    print("\n" + "="*80)
    print("HYPOTHESIS 4: Response Length Correlation")
    print("="*80)
    
    # Overall correlation
    corr, p_value = stats.pearsonr(df["tokens_approx"], df["latency_ms"])
    
    print(f"\nOverall correlation (tokens vs latency):")
    print(f"  Pearson r: {corr:.3f}")
    print(f"  p-value: {p_value:.4f}")
    print(f"  Interpretation: {'Significant correlation' if abs(corr) > 0.3 and p_value < 0.05 else 'No strong correlation'}")
    
    # Per config
    print("\n--- Average tokens per config ---")
    
    for config in df["config_id"].unique():
        subset = df[df["config_id"] == config]
        tokens_mean = subset["tokens_approx"].mean()
        latency_mean = subset["latency_ms"].mean()
        
        print(f"{config:20} | tokens={tokens_mean:5.1f} | latency={latency_mean:7.1f}ms")

def generate_summary(df: pd.DataFrame):
    """Generate executive summary"""
    print("\n\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    
    # Compare key configs (normal order only)
    normal = df[df["execution_order"] == "normal"]
    
    raw_default = normal[normal["config_id"] == "raw_default"]["latency_ms"].mean()
    lyra_balanced = normal[normal["config_id"] == "lyra_balanced"]["latency_ms"].mean()
    
    delta = lyra_balanced - raw_default
    delta_pct = (delta / raw_default) * 100
    
    print(f"\nCore Result:")
    print(f"  Raw Default:    {raw_default:.1f}ms")
    print(f"  Lyra Balanced:  {lyra_balanced:.1f}ms")
    print(f"  Δ (Lyra - Raw): {delta:+.1f}ms ({delta_pct:+.1f}%)")
    
    print("\nHypotheses Status:")
    print("  H1 (Temperature):  [ANALYZE OUTPUT ABOVE]")
    print("  H2 (Parameters):   [ANALYZE OUTPUT ABOVE]")
    print("  H3 (Warm-up):      [ANALYZE OUTPUT ABOVE]")
    print("  H4 (Length):       [ANALYZE OUTPUT ABOVE]")
    
    print("\nRecommendation:")
    if abs(delta_pct) < 5:
        print("  → Difference < 5% : NOT SIGNIFICANT")
    elif abs(delta_pct) < 10:
        print("  → Difference 5-10% : MARGINALLY SIGNIFICANT")
    else:
        print("  → Difference > 10% : SIGNIFICANT")
        print("  → Identify primary factor from H1-H4 analysis")

def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python analyze_phase3_validation.py validation_results.jsonl")
        sys.exit(1)
    
    jsonl_file = sys.argv[1]
    
    print("="*80)
    print("PHASE 3 - VALIDATION ANALYSIS")
    print("="*80)
    print(f"Loading: {jsonl_file}")
    
    df = load_results(jsonl_file)
    
    print(f"\nDataset: {len(df)} results")
    print(f"Configs: {df['config_id'].nunique()}")
    print(f"Orders: {df['execution_order'].unique().tolist()}")
    
    # Run all tests
    test_hypothesis_1_temperature(df)
    test_hypothesis_2_parameters(df)
    test_hypothesis_3_warmup(df)
    test_hypothesis_4_length(df)
    generate_summary(df)
    
    print("\n" + "="*80)
    print("✓ Analysis complete")
    print("="*80)

if __name__ == "__main__":
    main()
```

---

### Tâche 3 : Corriger `benchmark_phase3_matrix.py`

**Fixes critiques** :

#### Fix 1 : Session persistante
```python
# AVANT (INCORRECT)
for prompt in prompts:
    resp = requests.post(f"{LYRA_URL}/chat/message", json={
        "text": prompt,
        "profile": config["profile"],
        # ← PAS DE session_id
    })

# APRÈS (CORRECT)
SESSION_ID = str(uuid.uuid4())  # Une session par config

for prompt in prompts:
    resp = requests.post(f"{LYRA_URL}/chat/message", json={
        "text": prompt,
        "session_id": SESSION_ID,  # ← CRUCIAL
        "profile": config["profile"],
    })
```

#### Fix 2 : Vérifier le graphe existe
```python
import sqlite3
import os

def check_graph_initialized(db_path="data/ispace.db") -> Dict:
    """Verify semantic graph is populated"""
    if not os.path.exists(db_path):
        return {"initialized": False, "error": "DB file not found"}
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM concepts")
    n_concepts = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM relations")
    n_relations = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "initialized": n_concepts > 0,
        "concepts": n_concepts,
        "relations": n_relations
    }

# Au début du benchmark
graph_status = check_graph_initialized()
if not graph_status["initialized"]:
    print("⚠️  WARNING: Semantic graph is empty!")
    print("   Context injection will not work.")
    print("   Run: python weaver.py data/topics.txt")
```

#### Fix 3 : Logger paramètres effectifs
```python
# Dans llm_client.py, ajouter logging
import logging

logger = logging.getLogger(__name__)

async def chat(self, messages, physics_state, ...):
    # Map physics parameters
    temperature = map_tau_to_temperature(physics_state.tau_c)
    penalties = map_rho_to_penalties(physics_state.rho)
    
    # Build payload
    payload = {
        "model": self.model,
        "messages": messages,
        "options": {
            "temperature": temperature,
            "num_predict": 4096,
            "top_k": 40,
            "top_p": 0.9,
            "repeat_penalty": 1.0 + penalties["frequency_penalty"],
        }
    }
    
    # LOG EFFECTIVE PARAMETERS
    logger.info(f"Ollama request with: temperature={temperature:.3f}, "
                f"tau_c={physics_state.tau_c:.3f}, rho={physics_state.rho:.3f}")
    
    # ... rest of function
```

---

## ✅ CRITÈRES DE SUCCÈS

### Critères Techniques

- [ ] `benchmark_phase3_validation.py` exécute sans erreur
- [ ] 120 requêtes complétées (10 prompts × 6 configs × 2 orders)
- [ ] `validation_results.jsonl` créé avec toutes les données
- [ ] `analyze_phase3_validation.py` génère rapport complet
- [ ] Toutes les 4 hypothèses testées avec statistiques

### Critères Scientifiques

- [ ] H1: Δ latency entre temp_0.615 et temp_0.8 quantifié (p-value < 0.05)
- [ ] H2: Δ latency entre raw_explicit et raw_default quantifié
- [ ] H3: Effet ordre quantifié (normal vs reversed)
- [ ] H4: Corrélation tokens-latency calculée (Pearson r)
- [ ] Identification de la source principale du gain 12%

### Critères de Communication

- [ ] Résultats reproductibles (script + données)
- [ ] Méthodologie documentée
- [ ] Biais identifiés et contrôlés
- [ ] Recommandations claires (communiquer ou non)

---

## 📦 LIVRABLES

### Fichiers à Créer

1. **benchmark_phase3_validation.py** (400 lignes)
   - Script benchmark complet
   - 6 configurations
   - 2 ordres d'exécution
   - Sauvegarde JSONL incrémentale

2. **analyze_phase3_validation.py** (300 lignes)
   - Tests statistiques H1-H4
   - Visualisations (optionnel)
   - Rapport texte

3. **validation_results.jsonl** (120 lignes)
   - Résultats bruts

4. **validation_report.md** (généré automatiquement)
   - Executive summary
   - Réponses aux 4 hypothèses
   - Recommandations

### Fichiers à Modifier

1. **benchmark_phase3_matrix.py**
   - Ajouter session_id persistant
   - Ajouter check graphe
   - Améliorer logging

2. **llm_client.py** (optionnel)
   - Logger paramètres effectifs

---

## 🚨 POINTS D'ATTENTION

### Pièges à Éviter

1. **Ne pas randomiser l'ordre** des prompts dans un même config (pour comparabilité)
2. **Ne pas oublier** les petits délais (0.5s) entre requêtes (éviter rate limiting)
3. **Ne pas ignorer** les erreurs (logger et continuer)
4. **Ne pas mélanger** execution_order dans l'analyse

### Cas Limites

1. **Ollama down** → Retry avec exponential backoff
2. **Timeout** → Logger et skip ce prompt
3. **DB vide** → Warning mais continuer (teste quand même)
4. **Graphe vide** → Context injection = no-op (attendu)

### Performance

- Durée estimée : 15-20 min (120 requêtes × ~8s par requête)
- Si > 30 min → Vérifier Ollama perf ou réduire à 5 prompts

---

## 📊 TEMPLATE RAPPORT FINAL

```markdown
# PHASE 3 - VALIDATION REPORT

**Date:** 2025-12-04
**Benchmark:** benchmark_phase3_validation.py
**Résultats:** validation_results.jsonl

## Executive Summary

[À REMPLIR PAR ANALYSE]

Lyra montre un gain de **X%** vs Raw Ollama.

**Source principale identifiée:** [H1/H2/H3/H4]

**Recommandation:** [COMMUNIQUER / NE PAS COMMUNIQUER / REFAIRE]

## Méthodologie

- 10 prompts variés (technical, creative, analytical, philosophical, practical)
- 6 configurations testées
- 2 ordres d'exécution (normal, reversed)
- Total: 120 requêtes

## Résultats par Hypothèse

### H1: Temperature Impact
[RÉSULTATS T-TEST]

### H2: Parameters Impact
[COMPARAISON RAW_EXPLICIT VS LYRA]

### H3: Warm-up Effect
[COMPARAISON NORMAL VS REVERSED]

### H4: Length Correlation
[PEARSON R]

## Conclusion

[SYNTHÈSE]

## Recommandations

[PROCHAINES ÉTAPES]
```

---

## 🎯 CHECKLIST D'EXÉCUTION

### Avant de Lancer

- [ ] Ollama est démarré (`ollama serve`)
- [ ] Lyra API est démarrée (`python -m uvicorn app.main:app --port 8000`)
- [ ] Modèle gpt-oss:20b est chargé (`ollama list`)
- [ ] Espace disque suffisant (validation_results.jsonl ~500KB)

### Pendant l'Exécution

- [ ] Surveiller console pour erreurs
- [ ] Vérifier validation_results.jsonl se remplit
- [ ] Attendre 15-20 min (ne pas interrompre)

### Après l'Exécution

- [ ] Vérifier 120 lignes dans validation_results.jsonl
- [ ] Lancer `python analyze_phase3_validation.py validation_results.jsonl`
- [ ] Lire rapport complet
- [ ] Décider communication (OUI/NON)

---

## 💡 QUESTIONS CLÉS À RÉSOUDRE

À la fin de cette validation, tu DOIS pouvoir répondre à :

1. **Le gain de 12% est-il réel ou artefact ?**
   → Si H3 (warm-up) significatif → artefact
   → Sinon → réel

2. **Quelle est la source principale ?**
   → Si H1 (temperature) significatif → c'est la température
   → Si H2 (parameters) significatif → c'est num_predict ou autre
   → Si H4 (length) forte corrélation → Lyra génère plus court

3. **Lyra apporte-t-elle une vraie valeur ?**
   → Si gain vient juste de temperature=0.615 → valeur = interface élégante
   → Si gain vient de multiple facteurs → valeur = orchestration complète

4. **Dois-je communiquer les résultats ?**
   → Si méthodologie propre + gain validé → OUI
   → Si biais non résolus → NON (ou avec disclaimers)

---

## 🚀 PROCHAINES ÉTAPES APRÈS VALIDATION

### Si Gain Validé

1. **Communication Twitter** (thread)
2. **Post Reddit** (r/LocalLLaMA)
3. **HuggingFace Space** (démo interactive)
4. **Arxiv paper** (si résultats robustes)

### Si Gain Invalidé

1. **Documentation** du processus (méthodologie = aussi valuable)
2. **Blog post** sur "How NOT to benchmark LLMs"
3. **Amélioration** Lyra basée sur learnings

### Dans Tous les Cas

1. **Corriger** benchmark_phase3_matrix.py (session_id, graphe)
2. **Re-run** benchmark propre
3. **Archiver** résultats pour référence future

---

## 📞 SUPPORT

Si blocage pendant implémentation :

1. Vérifier Ollama logs : `journalctl -u ollama -f`
2. Vérifier Lyra logs : console FastAPI
3. Tester manuellement un endpoint :
   ```bash
   curl -X POST http://localhost:11434/api/chat \
     -d '{"model":"gpt-oss:20b","messages":[{"role":"user","content":"test"}]}'
   ```

---

**Bonne chance ! 🎯**

**Temps estimé total : 2-3 heures**

**Priorité : CRITIQUE** (bloque toute communication externe)
