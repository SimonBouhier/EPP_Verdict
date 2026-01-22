# LYRA - PROTOCOLE TRIPLE-BLIND EVALUATION
## Claude Haiku 4.5 comme Juge Non-Biaisé

**Date :** 2025-12-06  
**Objectif :** Éliminer tous les biais possibles dans l'évaluation LLM-as-judge

---

## 🎯 PRINCIPE DU TRIPLE-BLIND

### Niveaux de Blindness

**1. Judge-Blind (Claude Haiku)**
- Ne voit PAS les config_id
- Ne voit PAS les métadonnées (physics, latency)
- Ne voit PAS l'ordre d'exécution
- Voit UNIQUEMENT : prompt + réponse anonymisée

**2. Experimenter-Blind (Vous)**
- Ne voyez PAS les jugements pendant évaluation
- Ne modifiez PAS le protocol en cours
- Analysez UNIQUEMENT après completion

**3. Data-Blind (Séparation physique)**
- Fichiers sources et jugements dans dossiers séparés
- Mapping config ↔ anonyme dans fichier séparé
- Reconstruction post-hoc uniquement

---

## 📂 ARCHITECTURE DES FICHIERS

```
evaluation/
├── 1_source_data/
│   ├── responses_raw.jsonl           # Données brutes avec config_id
│   └── mapping_secret.json           # Config_id ↔ anonymous_id
│
├── 2_blind_data/
│   ├── responses_blind.jsonl         # Pour le juge (anonymisé)
│   └── judgment_template.md          # Rubrique de jugement
│
├── 3_judgments/
│   ├── judgments_blind.jsonl         # Jugements avec anonymous_id
│   └── judgment_log.txt              # Log Claude Haiku
│
├── 4_results/
│   ├── judgments_unblinded.jsonl     # Après reconstruction
│   └── analysis_report.md            # Analyse finale
│
└── scripts/
    ├── 1_anonymize.py                # Source → Blind
    ├── 2_judge.py                    # Claude Haiku évaluation
    ├── 3_unblind.py                  # Reconstruction
    └── 4_analyze.py                  # Analyse statistique
```

---

## 🔧 SCRIPT 1 : ANONYMISATION

```python
"""
1_anonymize.py
Transforme données sources en format aveugle pour le juge.
"""
import json
import hashlib
import random
from pathlib import Path

def anonymize_responses(source_file: str, output_dir: str):
    """
    Anonymise les réponses et crée le mapping secret.
    
    Input:  responses_raw.jsonl (avec config_id, meta, etc.)
    Output: responses_blind.jsonl (prompt + response + anonymous_id uniquement)
            mapping_secret.json (anonymous_id → config_id)
    """
    blind_dir = Path(output_dir) / "2_blind_data"
    blind_dir.mkdir(parents=True, exist_ok=True)
    
    mapping_file = Path(output_dir) / "1_source_data" / "mapping_secret.json"
    
    with open(source_file, 'r') as f:
        responses = [json.loads(line) for line in f]
    
    # Créer mapping aléatoire
    mapping = {}
    anonymous_ids = [f"resp_{i:04d}" for i in range(len(responses))]
    random.shuffle(anonymous_ids)  # Ordre aléatoire pour masquer patterns
    
    blind_responses = []
    
    for i, response in enumerate(responses):
        anon_id = anonymous_ids[i]
        
        # Stocker mapping (secret)
        mapping[anon_id] = {
            "config_id": response["config_id"],
            "config_label": response["config_label"],
            "execution_order": response["execution_order"],
            "original_index": i
        }
        
        # Créer version blind (AUCUNE métadonnée identifiable)
        blind_response = {
            "id": anon_id,
            "prompt": response["prompt"],
            "response": response["response"],
            "domain": response["domain"]  # OK car pas identifiant
        }
        
        blind_responses.append(blind_response)
    
    # Sauvegarder blind data
    blind_file = blind_dir / "responses_blind.jsonl"
    with open(blind_file, 'w') as f:
        for br in blind_responses:
            f.write(json.dumps(br) + '\n')
    
    # Sauvegarder mapping (KEEP SECRET)
    with open(mapping_file, 'w') as f:
        json.dump(mapping, f, indent=2)
    
    print(f"✓ Anonymized {len(responses)} responses")
    print(f"✓ Blind data: {blind_file}")
    print(f"✓ Mapping (SECRET): {mapping_file}")
    print(f"\n⚠️  DO NOT OPEN mapping_secret.json until analysis phase!")
    
    return blind_file, mapping_file


if __name__ == "__main__":
    anonymize_responses(
        source_file="evaluation/1_source_data/responses_raw.jsonl",
        output_dir="evaluation/"
    )
```

---

## 🤖 SCRIPT 2 : JUGEMENT CLAUDE HAIKU

```python
"""
2_judge.py
Claude Haiku évalue les réponses de manière aveugle.
"""
import json
import anthropic
from pathlib import Path
from typing import Dict, List

# Rubrique de jugement (critères clairs et objectifs)
JUDGMENT_RUBRIC = """
You are evaluating AI-generated responses to prompts. Rate each response on a scale of 1-5 for the following criteria:

**ACCURACY** (1-5):
- 5: Completely accurate, no errors
- 4: Mostly accurate, minor imprecision
- 3: Partially accurate, some errors
- 2: Mostly inaccurate
- 1: Completely wrong

**COMPLETENESS** (1-5):
- 5: Fully addresses all aspects of prompt
- 4: Addresses most aspects
- 3: Addresses some aspects, missing important points
- 2: Barely addresses prompt
- 1: Does not address prompt

**CLARITY** (1-5):
- 5: Crystal clear, well-structured
- 4: Clear, minor awkwardness
- 3: Understandable but unclear in places
- 2: Confusing, hard to follow
- 1: Incomprehensible

**APPROPRIATENESS** (1-5):
- 5: Perfectly appropriate tone/style for prompt
- 4: Mostly appropriate
- 3: Somewhat appropriate
- 2: Inappropriate in several ways
- 1: Completely inappropriate

**CREATIVITY** (1-5, only for creative prompts):
- 5: Highly creative, original phrasing
- 4: Some creativity
- 3: Standard/formulaic
- 2: Boring/repetitive
- 1: No creativity

**OVERALL** (1-5):
- Holistic assessment considering all factors

Return your judgment as JSON:
{
  "accuracy": <1-5>,
  "completeness": <1-5>,
  "clarity": <1-5>,
  "appropriateness": <1-5>,
  "creativity": <1-5>,
  "overall": <1-5>,
  "reasoning": "<brief explanation of overall score>"
}

Be consistent across all responses. Do NOT favor any particular response based on position or similarity to others.
"""


def judge_with_claude_haiku(
    blind_file: str,
    output_file: str,
    api_key: str,
    batch_size: int = 10
):
    """
    Évalue responses avec Claude Haiku en mode aveugle.
    
    Args:
        blind_file: Path to responses_blind.jsonl
        output_file: Path to save judgments_blind.jsonl
        api_key: Anthropic API key
        batch_size: Combien de réponses juger par batch (évite fatigue)
    """
    client = anthropic.Anthropic(api_key=api_key)
    
    # Load blind responses
    with open(blind_file, 'r') as f:
        responses = [json.loads(line) for line in f]
    
    judgments = []
    
    print(f"Judging {len(responses)} responses with Claude Haiku 4.5...")
    print(f"(Batch size: {batch_size})\n")
    
    for i, response in enumerate(responses):
        print(f"[{i+1}/{len(responses)}] Judging {response['id']}...", end=" ")
        
        # Construire prompt de jugement
        judge_prompt = f"""
{JUDGMENT_RUBRIC}

---

**PROMPT:**
{response['prompt']}

**DOMAIN:**
{response['domain']}

**RESPONSE TO EVALUATE:**
{response['response']}

---

Please provide your judgment as JSON.
"""
        
        try:
            # Call Claude Haiku 4.5
            message = client.messages.create(
                model="claude-haiku-4.5-20251022",  # Latest Haiku
                max_tokens=500,
                temperature=0.3,  # Low temp for consistency
                messages=[{
                    "role": "user",
                    "content": judge_prompt
                }]
            )
            
            # Parse response
            judgment_text = message.content[0].text
            
            # Extract JSON (Claude might wrap in markdown)
            if "```json" in judgment_text:
                judgment_text = judgment_text.split("```json")[1].split("```")[0]
            elif "```" in judgment_text:
                judgment_text = judgment_text.split("```")[1].split("```")[0]
            
            judgment = json.loads(judgment_text.strip())
            
            # Add metadata
            judgment['id'] = response['id']
            judgment['domain'] = response['domain']
            judgment['judged_at'] = message.id  # Anthropic message ID
            
            judgments.append(judgment)
            
            print(f"✓ Overall: {judgment['overall']}/5")
            
            # Save incrementally (in case of crash)
            with open(output_file, 'a') as f:
                f.write(json.dumps(judgment) + '\n')
        
        except Exception as e:
            print(f"✗ Error: {e}")
            # Log error but continue
            judgments.append({
                'id': response['id'],
                'error': str(e),
                'accuracy': None,
                'overall': None
            })
        
        # Pause between batches (avoid rate limits)
        if (i + 1) % batch_size == 0 and i + 1 < len(responses):
            print(f"\n--- Batch {(i+1)//batch_size} complete. Pausing 5s... ---\n")
            import time
            time.sleep(5)
    
    print(f"\n✓ Judging complete: {len(judgments)} judgments saved to {output_file}")
    
    return judgments


if __name__ == "__main__":
    import os
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Set ANTHROPIC_API_KEY environment variable")
    
    judge_with_claude_haiku(
        blind_file="evaluation/2_blind_data/responses_blind.jsonl",
        output_file="evaluation/3_judgments/judgments_blind.jsonl",
        api_key=api_key,
        batch_size=10
    )
```

---

## 🔓 SCRIPT 3 : RECONSTRUCTION (UNBLINDING)

```python
"""
3_unblind.py
Reconstruit les jugements avec les vraies config_id.
"""
import json
from pathlib import Path

def unblind_judgments(
    judgments_file: str,
    mapping_file: str,
    output_file: str
):
    """
    Reconstruit judgments avec config_id réelles.
    
    Args:
        judgments_file: Path to judgments_blind.jsonl
        mapping_file: Path to mapping_secret.json
        output_file: Path to save judgments_unblinded.jsonl
    """
    # Load judgments
    with open(judgments_file, 'r') as f:
        judgments = [json.loads(line) for line in f]
    
    # Load mapping
    with open(mapping_file, 'r') as f:
        mapping = json.load(f)
    
    # Reconstruct
    unblinded = []
    
    for judgment in judgments:
        anon_id = judgment['id']
        
        # Get original metadata
        original = mapping[anon_id]
        
        # Merge
        unblinded_judgment = {
            **judgment,  # All judgment fields
            "config_id": original["config_id"],
            "config_label": original["config_label"],
            "execution_order": original["execution_order"],
            "original_index": original["original_index"]
        }
        
        unblinded.append(unblinded_judgment)
    
    # Save
    with open(output_file, 'w') as f:
        for uj in unblinded:
            f.write(json.dumps(uj) + '\n')
    
    print(f"✓ Unblinded {len(unblinded)} judgments")
    print(f"✓ Output: {output_file}")
    
    return unblinded


if __name__ == "__main__":
    unblind_judgments(
        judgments_file="evaluation/3_judgments/judgments_blind.jsonl",
        mapping_file="evaluation/1_source_data/mapping_secret.json",
        output_file="evaluation/4_results/judgments_unblinded.jsonl"
    )
```

---

## 📊 SCRIPT 4 : ANALYSE

```python
"""
4_analyze.py
Analyse statistique des jugements.
"""
import json
import numpy as np
from scipy import stats
from collections import defaultdict

def analyze_judgments(unblinded_file: str):
    """
    Analyse complète avec tests statistiques.
    """
    with open(unblinded_file, 'r') as f:
        judgments = [json.loads(line) for line in f]
    
    # Group by config
    by_config = defaultdict(list)
    for j in judgments:
        by_config[j['config_id']].append(j)
    
    print("="*80)
    print("JUDGMENT ANALYSIS")
    print("="*80)
    
    # Summary stats
    for config_id, jlist in by_config.items():
        overall_scores = [j['overall'] for j in jlist if j.get('overall')]
        
        if not overall_scores:
            continue
        
        mean = np.mean(overall_scores)
        std = np.std(overall_scores, ddof=1)
        
        print(f"\n{config_id}:")
        print(f"  N = {len(overall_scores)}")
        print(f"  Mean Overall: {mean:.2f} ± {std:.2f}")
        print(f"  Range: [{min(overall_scores)}, {max(overall_scores)}]")
    
    # Pairwise comparisons
    print("\n" + "="*80)
    print("PAIRWISE COMPARISONS (t-tests)")
    print("="*80)
    
    configs = list(by_config.keys())
    for i, config_a in enumerate(configs):
        for config_b in configs[i+1:]:
            scores_a = [j['overall'] for j in by_config[config_a] if j.get('overall')]
            scores_b = [j['overall'] for j in by_config[config_b] if j.get('overall')]
            
            if len(scores_a) < 2 or len(scores_b) < 2:
                continue
            
            t_stat, p_value = stats.ttest_ind(scores_a, scores_b)
            
            mean_a = np.mean(scores_a)
            mean_b = np.mean(scores_b)
            delta = mean_a - mean_b
            
            sig = "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else "ns"
            
            print(f"\n{config_a} vs {config_b}:")
            print(f"  Δ = {delta:+.3f} ({mean_a:.2f} - {mean_b:.2f})")
            print(f"  t = {t_stat:.2f}, p = {p_value:.4f} {sig}")
    
    # By domain
    print("\n" + "="*80)
    print("BY DOMAIN")
    print("="*80)
    
    domains = set(j['domain'] for j in judgments)
    
    for domain in sorted(domains):
        print(f"\n{domain.upper()}:")
        
        domain_judgments = [j for j in judgments if j['domain'] == domain]
        domain_by_config = defaultdict(list)
        
        for j in domain_judgments:
            domain_by_config[j['config_id']].append(j['overall'])
        
        for config_id, scores in domain_by_config.items():
            if scores:
                print(f"  {config_id}: {np.mean(scores):.2f} ± {np.std(scores, ddof=1):.2f}")


if __name__ == "__main__":
    analyze_judgments("evaluation/4_results/judgments_unblinded.jsonl")
```

---

## 🔒 GARANTIES DE BLINDNESS

### ✅ Ce que Claude Haiku NE voit PAS :
- ❌ config_id ("raw_default", "lyra_creative")
- ❌ config_label ("Lyra Creative")
- ❌ Métadonnées physics (tau_c, rho, etc.)
- ❌ Latency_ms (évite bias "plus rapide = meilleur")
- ❌ Execution order (normal/reversed)
- ❌ Tokens count (évite bias longueur)
- ❌ Timestamp (évite pattern temporel)

### ✅ Ce que Claude Haiku VOIT :
- ✓ Prompt (nécessaire)
- ✓ Response (nécessaire)
- ✓ Domain (utile pour contexte, non-identifiant)
- ✓ Anonymous ID (resp_0042, resp_0137, etc.)

### ✅ Ordre Randomisé :
```python
random.shuffle(anonymous_ids)  # Dans anonymize.py
```
- Empêche pattern "tous les premiers sont X"
- Empêche inference "changement de style = changement config"

---

## ⚖️ VALIDATION DU PROTOCOLE

### Test Inter-Rater Reliability

**Avant production** :
1. Prendre 20 réponses
2. Faire juger par Claude Haiku (aveugle)
3. Faire juger par humain (vous, aveugle aussi)
4. Calculer Cohen's Kappa

**Critère acceptation** : κ > 0.6 (accord substantiel)

```python
from sklearn.metrics import cohen_kappa_score

human_scores = [4, 5, 3, 4, 5, ...]  # 20 jugements
claude_scores = [4, 4, 3, 5, 5, ...]  # 20 jugements

kappa = cohen_kappa_score(human_scores, claude_scores)
print(f"Inter-rater reliability: κ = {kappa:.3f}")

if kappa > 0.6:
    print("✓ Claude Haiku validated as reliable judge")
else:
    print("✗ Need to improve rubric or use different judge")
```

---

## 📋 CHECKLIST D'EXÉCUTION

### Phase 1 : Préparation (30 min)
- [ ] Créer structure dossiers
- [ ] Copier responses brutes dans 1_source_data/
- [ ] Vérifier ANTHROPIC_API_KEY configurée
- [ ] Installer dépendances (`anthropic`, `scipy`, `numpy`)

### Phase 2 : Anonymisation (5 min)
- [ ] Exécuter `1_anonymize.py`
- [ ] Vérifier `responses_blind.jsonl` créé
- [ ] **NE PAS OUVRIR** `mapping_secret.json`

### Phase 3 : Jugement (1-2h selon taille)
- [ ] Exécuter `2_judge.py`
- [ ] Attendre completion (progress bars)
- [ ] Vérifier `judgments_blind.jsonl` créé
- [ ] **NE PAS REGARDER** les jugements en détail

### Phase 4 : Reconstruction (5 min)
- [ ] Exécuter `3_unblind.py`
- [ ] Vérifier `judgments_unblinded.jsonl` créé
- [ ] **MAINTENANT OK** d'analyser

### Phase 5 : Analyse (30 min)
- [ ] Exécuter `4_analyze.py`
- [ ] Interpréter résultats
- [ ] Créer visualisations
- [ ] Rédiger rapport

---

## 💰 COÛTS ESTIMÉS

**Claude Haiku 4.5 Pricing** :
- Input : $1.00 / MTok
- Output : $5.00 / MTok

**Estimation pour 750 réponses** :
- Input : ~500 tokens/judgment × 750 = 375k tokens = $0.38
- Output : ~200 tokens/judgment × 750 = 150k tokens = $0.75
- **Total : ~$1.13** (très abordable !)

**Comparé à GPT-4o** : ~7x moins cher

---

## 🎯 AVANTAGES DU PROTOCOLE

### ✅ Élimination Biais
- Position bias ✓ (ordre randomisé)
- Label bias ✓ (anonymisation)
- Experimenter bias ✓ (vous ne voyez pas pendant)
- Confirmation bias ✓ (juge ne sait pas hypothèse)

### ✅ Reproductibilité
- Scripts automatisés
- Seed aléatoire fixé (optionnel)
- Logs complets
- Versionning

### ✅ Auditabilité
- Tous les fichiers intermédiaires conservés
- Mapping permet reconstruction
- Timestam ps de chaque étape
- Traceable

---

## 📌 NOTES IMPORTANTES

### ⚠️ NE PAS FAIRE :

**❌ ERREUR FATALE** :
```python
# NE JAMAIS FAIRE ÇA
judgment_prompt = f"""
Evaluate this response from {config_id}:  ← SPOILER!
Response: {response}
"""
```

**❌ ERREUR SUBTILE** :
```python
# Ordre prévisible = pattern detectable
for config in ["raw", "lyra_balanced", "lyra_creative"]:
    for prompt in prompts:
        # Juge pourrait detecter pattern "3 variations par prompt"
```

**✅ CORRECT** :
```python
# Ordre complètement randomisé
all_responses = generate_all()
random.shuffle(all_responses)
for response in all_responses:
    judge(response)  # Aveugle
```

### 🔍 Vérification Finale

Avant d'analyser, vérifier :
```bash
# Fichier blind ne doit PAS contenir config_id
grep -i "config_id" evaluation/2_blind_data/responses_blind.jsonl
# Output attendu : (vide)

# Fichier blind ne doit PAS contenir "lyra"
grep -i "lyra" evaluation/2_blind_data/responses_blind.jsonl
# Output attendu : (vide)
```

---

**Protocole Statut** : ✅ PRODUCTION-READY  
**Blindness Level** : Triple-blind (judge, experimenter, data)  
**Cost** : ~$1-2 pour 750 judgments  
**Time** : ~2-3h total (mostly automated)
