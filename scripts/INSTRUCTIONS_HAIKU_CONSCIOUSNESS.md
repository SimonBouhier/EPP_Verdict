# 🧠 INSTRUCTIONS DÉTAILLÉES - Implémentation Conscience Modulaire Lyra Clean

**Destinataire :** Claude Haiku 4.5  
**Objectif :** Implémenter progressivement 4 niveaux de conscience avec benchmarking rigoureux  
**Approche :** Incrémentale, testée, documentée à chaque étape  
**Durée estimée :** 4-6 heures de développement

---

## 📋 CONTEXTE DU PROJET

### État actuel (Baseline - Lyra Clean v1.0)

```
LYRA CLEAN - Architecture Actuelle
├── FastAPI backend (app/main.py)
├── SQLite async database (database/engine.py)
├── Bezier physics engine (core/physics/bezier.py)
├── Context injector (services/injector.py)
├── API documentée : http://localhost:8000/docs
└── Tests passing : 6/6 ✅
```

**Forces :**
- ✅ Stable (déterministe)
- ✅ Rapide (< 10ms queries)
- ✅ Production-ready
- ✅ Bien documenté

**Limitations actuelles :**
- ❌ Pas de métriques internes (coherence, tension)
- ❌ Pas d'adaptation dynamique
- ❌ Pas de mémoire sophistiquée
- ❌ Comportement figé (profiles statiques)

### Objectif de la mission

Implémenter **4 niveaux de conscience progressifs** :

| Niveau | Nom | Description | Overhead attendu |
|--------|-----|-------------|------------------|
| 0 | Baseline | État actuel (aucune conscience) | 0 ms |
| 1 | Passive Metrics | Calcul métriques épistémiques (pas d'action) | < 5 ms |
| 2 | Adaptive | Ajustements graduels du profil | < 10 ms |
| 3 | Full Memory | Rappel mémoire + adaptation | < 20 ms |

**Chaque niveau doit :**
1. Être **activable/désactivable** via API
2. Être **benchmarké** rigoureusement
3. Être **documenté** avec exemples
4. Préserver la **compatibilité** avec niveau inférieur

---

## 🎯 INSTRUCTIONS GÉNÉRALES

### Principes de travail

1. **Développement incrémental**
   - Une phase à la fois
   - Tests après chaque phase
   - Commit après validation

2. **Documentation continue**
   - Commenter le code
   - Créer exemples d'utilisation
   - Mettre à jour API_GUIDE.md

3. **Benchmarking systématique**
   - Baseline avant changement
   - Mesure après changement
   - Comparaison rigoureuse

4. **Compatibilité ascendante**
   - Ne jamais casser l'API existante
   - Ajouter des champs optionnels
   - Garder comportement par défaut

### Structure des livrables

Pour chaque phase, produire :

```
phase_N/
├── code/
│   └── [fichiers modifiés/créés]
├── tests/
│   ├── test_phase_N.py
│   └── benchmark_phase_N.py
├── docs/
│   ├── PHASE_N_IMPLEMENTATION.md
│   └── PHASE_N_BENCHMARK_RESULTS.md
└── PHASE_N_CHECKLIST.md (✅/❌ pour chaque item)
```

---

## 📦 PHASE 0 : PRÉPARATION & BASELINE

### Objectifs
1. Créer structure de dossiers
2. Établir benchmark baseline
3. Documenter état initial

### Tâches

#### 0.1 : Créer structure projet
```bash
# À exécuter dans lyra_clean/

mkdir -p tests/benchmarks
mkdir -p services/consciousness
mkdir -p docs/phases

# Créer fichiers vides
touch services/consciousness/__init__.py
touch services/consciousness/metrics.py
touch services/consciousness/adaptation.py
touch services/consciousness/memory.py
touch tests/benchmarks/__init__.py
touch tests/benchmarks/benchmark_suite.py
touch tests/benchmarks/benchmark_runner.py
```

#### 0.2 : Créer suite de benchmarking baseline

**Fichier :** `tests/benchmarks/benchmark_suite.py`

```python
"""
Suite de benchmarking pour Lyra Clean
Permet de comparer différentes configurations
"""
import asyncio
import time
import json
from typing import List, Dict, Optional
from pathlib import Path
import httpx
import pandas as pd
from datetime import datetime


class LyraBenchmark:
    """Suite de benchmarks pour Lyra Clean"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = None
        self.results_dir = Path("benchmark_results")
        self.results_dir.mkdir(exist_ok=True)
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=60.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def check_server_health(self) -> bool:
        """Vérifie que le serveur est accessible"""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.json()["status"] == "healthy"
        except Exception as e:
            print(f"❌ Server not accessible: {e}")
            return False
    
    async def benchmark_latency_basic(
        self,
        n_requests: int = 100,
        prompt: str = "What is entropy?"
    ) -> pd.DataFrame:
        """
        Benchmark 1 : Latence de base (sans complexité)
        
        Mesure :
        - Latence totale
        - Breakdown par composant
        - Stabilité (variance)
        """
        print(f"\n{'='*60}")
        print(f"BENCHMARK 1: Basic Latency ({n_requests} requests)")
        print(f"{'='*60}")
        
        results = []
        
        for i in range(n_requests):
            start = time.time()
            
            try:
                response = await self.client.post(
                    f"{self.base_url}/chat/message",
                    json={
                        "text": prompt,
                        "enable_context": True
                    }
                )
                
                total_latency = (time.time() - start) * 1000  # ms
                data = response.json()
                
                results.append({
                    "request_id": i,
                    "total_latency_ms": total_latency,
                    "context_latency_ms": data["latency"]["context_extraction"],
                    "llm_latency_ms": data["latency"]["llm_generation"],
                    "api_overhead_ms": total_latency - data["latency"]["total"]
                })
                
                if (i + 1) % 10 == 0:
                    print(f"  Progress: {i+1}/{n_requests} requests")
            
            except Exception as e:
                print(f"  ❌ Request {i} failed: {e}")
                results.append({
                    "request_id": i,
                    "total_latency_ms": None,
                    "context_latency_ms": None,
                    "llm_latency_ms": None,
                    "api_overhead_ms": None,
                    "error": str(e)
                })
        
        df = pd.DataFrame(results)
        
        # Statistiques
        print(f"\n📊 Results:")
        print(f"  Total latency: {df['total_latency_ms'].mean():.2f} ± {df['total_latency_ms'].std():.2f} ms")
        print(f"  Context extraction: {df['context_latency_ms'].mean():.2f} ms")
        print(f"  LLM generation: {df['llm_latency_ms'].mean():.2f} ms")
        print(f"  API overhead: {df['api_overhead_ms'].mean():.2f} ms")
        
        return df
    
    async def benchmark_context_impact(
        self,
        prompts: List[str] = None
    ) -> pd.DataFrame:
        """
        Benchmark 2 : Impact de l'injection de contexte
        
        Compare :
        - enable_context=False
        - enable_context=True
        
        Mesure :
        - Overhead d'extraction
        - Nombre de concepts injectés
        - Impact sur qualité (subjectif)
        """
        if prompts is None:
            prompts = [
                "What is entropy?",
                "Explain quantum mechanics",
                "How does photosynthesis work?",
                "What is machine learning?",
                "Describe the water cycle"
            ]
        
        print(f"\n{'='*60}")
        print(f"BENCHMARK 2: Context Injection Impact ({len(prompts)} prompts)")
        print(f"{'='*60}")
        
        results = []
        
        for idx, prompt in enumerate(prompts):
            print(f"\n  Testing prompt {idx+1}/{len(prompts)}: {prompt[:50]}...")
            
            # Sans contexte
            try:
                start_without = time.time()
                response_without = await self.client.post(
                    f"{self.base_url}/chat/message",
                    json={"text": prompt, "enable_context": False}
                )
                latency_without = (time.time() - start_without) * 1000
                data_without = response_without.json()
            except Exception as e:
                print(f"    ❌ Without context failed: {e}")
                continue
            
            # Avec contexte
            try:
                start_with = time.time()
                response_with = await self.client.post(
                    f"{self.base_url}/chat/message",
                    json={"text": prompt, "enable_context": True}
                )
                latency_with = (time.time() - start_with) * 1000
                data_with = response_with.json()
            except Exception as e:
                print(f"    ❌ With context failed: {e}")
                continue
            
            result = {
                "prompt": prompt[:50],
                "latency_without_ms": latency_without,
                "latency_with_ms": latency_with,
                "overhead_ms": latency_with - latency_without,
                "overhead_percent": ((latency_with - latency_without) / latency_without) * 100,
                "concepts_injected": len(data_with.get("context", {}).get("neighbor_concepts", [])),
                "response_length_without": len(data_without["text"].split()),
                "response_length_with": len(data_with["text"].split())
            }
            
            results.append(result)
            
            print(f"    Overhead: +{result['overhead_ms']:.1f}ms ({result['overhead_percent']:.1f}%)")
            print(f"    Concepts: {result['concepts_injected']}")
        
        df = pd.DataFrame(results)
        
        # Statistiques
        print(f"\n📊 Results:")
        print(f"  Average overhead: {df['overhead_ms'].mean():.2f} ms ({df['overhead_percent'].mean():.1f}%)")
        print(f"  Average concepts injected: {df['concepts_injected'].mean():.1f}")
        
        return df
    
    async def benchmark_profiles(
        self,
        prompts: List[str] = None
    ) -> pd.DataFrame:
        """
        Benchmark 3 : Comparaison des profils Bezier
        
        Compare tous les profils sur mêmes prompts
        
        Mesure :
        - Latence
        - Longueur réponse
        - Paramètres physiques (tau_c, rho)
        """
        if prompts is None:
            prompts = [
                "Explain entropy",
                "What is consciousness?",
                "Describe evolution"
            ]
        
        profiles = ["balanced", "creative", "safe", "analytical", "concise"]
        
        print(f"\n{'='*60}")
        print(f"BENCHMARK 3: Profile Comparison")
        print(f"{len(profiles)} profiles × {len(prompts)} prompts = {len(profiles)*len(prompts)} tests")
        print(f"{'='*60}")
        
        results = []
        
        for profile in profiles:
            print(f"\n  Testing profile: {profile}")
            
            for prompt in prompts:
                try:
                    response = await self.client.post(
                        f"{self.base_url}/chat/message",
                        json={
                            "text": prompt,
                            "profile": profile
                        }
                    )
                    
                    data = response.json()
                    
                    results.append({
                        "profile": profile,
                        "prompt": prompt[:30],
                        "latency_ms": data["latency"]["total"],
                        "response_length": len(data["text"].split()),
                        "tau_c": data["physics_state"]["tau_c"],
                        "rho": data["physics_state"]["rho"],
                        "delta_r": data["physics_state"]["delta_r"]
                    })
                    
                except Exception as e:
                    print(f"    ❌ Failed: {e}")
        
        df = pd.DataFrame(results)
        
        # Statistiques par profil
        print(f"\n📊 Results by profile:")
        for profile in profiles:
            profile_df = df[df["profile"] == profile]
            print(f"\n  {profile}:")
            print(f"    Avg latency: {profile_df['latency_ms'].mean():.2f} ms")
            print(f"    Avg response length: {profile_df['response_length'].mean():.0f} words")
            print(f"    Avg tau_c: {profile_df['tau_c'].mean():.2f}")
        
        return df
    
    def save_results(self, df: pd.DataFrame, name: str, config: dict = None):
        """Sauvegarde résultats avec métadonnées"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Sauvegarder CSV
        csv_path = self.results_dir / f"{name}_{timestamp}.csv"
        df.to_csv(csv_path, index=False)
        print(f"\n💾 Results saved: {csv_path}")
        
        # Sauvegarder config
        if config:
            config_path = self.results_dir / f"{name}_{timestamp}_config.json"
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"💾 Config saved: {config_path}")
    
    async def run_baseline_suite(self):
        """Exécute suite complète baseline"""
        print("\n" + "="*60)
        print("LYRA BASELINE BENCHMARK SUITE")
        print("="*60)
        
        # Vérifier serveur
        if not await self.check_server_health():
            print("❌ Server not healthy, aborting")
            return
        
        print("✅ Server healthy, starting benchmarks...\n")
        
        # Benchmark 1: Latence
        df_latency = await self.benchmark_latency_basic(n_requests=50)
        self.save_results(df_latency, "baseline_latency", {
            "benchmark": "latency_basic",
            "n_requests": 50
        })
        
        # Benchmark 2: Context impact
        df_context = await self.benchmark_context_impact()
        self.save_results(df_context, "baseline_context")
        
        # Benchmark 3: Profiles
        df_profiles = await self.benchmark_profiles()
        self.save_results(df_profiles, "baseline_profiles")
        
        print("\n" + "="*60)
        print("✅ BASELINE SUITE COMPLETE")
        print("="*60)
        print(f"\nResults saved in: {self.results_dir}/")


async def main():
    """Point d'entrée principal"""
    async with LyraBenchmark() as benchmark:
        await benchmark.run_baseline_suite()


if __name__ == "__main__":
    asyncio.run(main())
```

#### 0.3 : Exécuter benchmark baseline

```bash
# 1. S'assurer que le serveur tourne
python app/main.py  # Dans un terminal séparé

# 2. Lancer benchmark baseline
python tests/benchmarks/benchmark_suite.py
```

**Résultats attendus :**
```
LYRA BASELINE BENCHMARK SUITE
============================================================
✅ Server healthy, starting benchmarks...

BENCHMARK 1: Basic Latency (50 requests)
============================================================
  Progress: 10/50 requests
  Progress: 20/50 requests
  ...
📊 Results:
  Total latency: 1250.32 ± 45.67 ms
  Context extraction: 8.23 ms
  LLM generation: 1230.45 ms
  API overhead: 11.64 ms

💾 Results saved: benchmark_results/baseline_latency_20250116_143022.csv

BENCHMARK 2: Context Injection Impact (5 prompts)
============================================================
  Testing prompt 1/5: What is entropy?...
    Overhead: +8.5ms (0.7%)
    Concepts: 7
  ...
📊 Results:
  Average overhead: 8.12 ms (0.65%)
  Average concepts injected: 6.4

💾 Results saved: benchmark_results/baseline_context_20250116_143145.csv

BENCHMARK 3: Profile Comparison
============================================================
  Testing profile: balanced
  Testing profile: creative
  ...
📊 Results by profile:
  balanced:
    Avg latency: 1242.34 ms
    Avg response length: 156 words
    Avg tau_c: 1.00
  ...

💾 Results saved: benchmark_results/baseline_profiles_20250116_143312.csv

============================================================
✅ BASELINE SUITE COMPLETE
============================================================
```

#### 0.4 : Documenter baseline

**Fichier :** `docs/phases/PHASE_0_BASELINE.md`

```markdown
# Phase 0 : Baseline Établie

**Date :** [DATE]  
**Version Lyra :** 1.0.0  
**Conscience Level :** 0 (aucune)

## Résultats

### Benchmark 1 : Latence de base
- **Total moyen :** [X] ms ± [Y] ms
- **Context extraction :** [X] ms
- **LLM generation :** [X] ms
- **API overhead :** [X] ms

### Benchmark 2 : Impact contexte
- **Overhead moyen :** +[X] ms ([Y]%)
- **Concepts injectés :** [X] concepts

### Benchmark 3 : Profils
| Profile | Latency | Response Length | tau_c |
|---------|---------|-----------------|-------|
| balanced | [X] ms | [Y] words | [Z] |
| creative | [X] ms | [Y] words | [Z] |
| ... | ... | ... | ... |

## Fichiers générés
- `benchmark_results/baseline_latency_*.csv`
- `benchmark_results/baseline_context_*.csv`
- `benchmark_results/baseline_profiles_*.csv`

## Conclusion
✅ Baseline établie avec succès
✅ Performances acceptables
✅ Prêt pour Phase 1
```

#### 0.5 : Checklist Phase 0

**Fichier :** `docs/phases/PHASE_0_CHECKLIST.md`

```markdown
# Phase 0 : Checklist

- [ ] Structure dossiers créée
- [ ] `benchmark_suite.py` implémenté
- [ ] Serveur démarré et healthy
- [ ] Benchmark baseline exécuté
- [ ] 3 fichiers CSV générés
- [ ] Documentation baseline créée
- [ ] Résultats archivés
- [ ] Commit effectué

## Commandes de validation

```bash
# Vérifier structure
ls tests/benchmarks/
ls services/consciousness/
ls docs/phases/

# Vérifier résultats
ls benchmark_results/*.csv
cat docs/phases/PHASE_0_BASELINE.md

# Commit
git add .
git commit -m "Phase 0: Baseline established"
```
```

---

## 🧠 PHASE 1 : MÉTRIQUES PASSIVES (Conscience Niveau 1)

### Objectifs
1. Implémenter calcul métriques épistémiques
2. Ajouter champ `consciousness_level` à l'API
3. Benchmarker overhead
4. Documenter

### Tâches

#### 1.1 : Implémenter module de métriques

**Fichier :** `services/consciousness/metrics.py`

```python
"""
Consciousness Metrics - Niveau 1 (Passif)

Calcule métriques épistémiques sans modifier comportement :
- Coherence : densité sémantique du contexte
- Tension : charge ressentie
- Fit : alignement avec attentes
- Pressure : exploration vs exploitation
"""
from dataclasses import dataclass
from typing import Optional
import math


@dataclass
class ConsciousnessMetrics:
    """Métriques épistémiques calculées"""
    coherence: float      # [0,1] : Densité sémantique
    tension: float        # [0,1] : Charge système
    fit: float           # [0,1] : Alignement
    pressure: float      # [0,1] : Exploration
    
    @property
    def stability_score(self) -> float:
        """Score composite de stabilité"""
        return (self.coherence + self.fit) / 2 - self.tension * 0.5
    
    def dict(self):
        """Conversion dict pour JSON"""
        return {
            "coherence": round(self.coherence, 3),
            "tension": round(self.tension, 3),
            "fit": round(self.fit, 3),
            "pressure": round(self.pressure, 3),
            "stability_score": round(self.stability_score, 3)
        }


class ConsciousnessMonitor:
    """
    Moniteur de conscience (Niveau 1 : Passif)
    
    Calcule métriques épistémiques sans modifier comportement.
    L'overhead doit rester < 5ms.
    """
    
    def __init__(self, level: int = 0):
        """
        Args:
            level: Niveau de conscience (0=off, 1=passive, 2=adaptive, 3=full)
        """
        self.level = level
    
    def compute_metrics(
        self,
        context_weight: float,
        num_concepts: int,
        physics_state: dict,
        response_length: int
    ) -> Optional[ConsciousnessMetrics]:
        """
        Calcule métriques épistémiques
        
        Args:
            context_weight: Poids total du contexte graphe
            num_concepts: Nombre de concepts injectés
            physics_state: État physique {tau_c, rho, delta_r}
            response_length: Longueur réponse (en mots)
        
        Returns:
            ConsciousnessMetrics si level >= 1, sinon None
        """
        if self.level < 1:
            return None
        
        # 1. COHERENCE : basé sur densité graphe
        # Plus de concepts avec poids élevé = haute cohérence
        coherence = self._compute_coherence(context_weight, num_concepts)
        
        # 2. PRESSURE : basé sur tau_c et delta_r
        # Tau_c élevé + delta_r élevé = haute pression
        pressure = self._compute_pressure(
            physics_state.get("tau_c", 1.0),
            physics_state.get("delta_r", 0.0)
        )
        
        # 3. FIT : basé sur rho et longueur réponse
        # Alignement entre attentes (rho) et production
        fit = self._compute_fit(
            physics_state.get("rho", 0.0),
            response_length
        )
        
        # 4. TENSION : combinaison coherence, pressure
        # Haute si structure faible OU charge forte
        tension = self._compute_tension(coherence, pressure)
        
        return ConsciousnessMetrics(
            coherence=coherence,
            tension=tension,
            fit=fit,
            pressure=pressure
        )
    
    def _compute_coherence(self, weight: float, n_concepts: int) -> float:
        """
        Coherence = densité sémantique
        
        Formule : min(1.0, weight / (n_concepts * 0.8))
        
        Rationale :
        - Poids moyen de 0.8 par concept = bonne cohérence
        - Saturé à 1.0
        """
        if n_concepts == 0:
            return 0.0
        
        avg_weight = weight / n_concepts
        coherence = avg_weight / 0.8  # Normalisation
        return min(1.0, max(0.0, coherence))
    
    def _compute_pressure(self, tau_c: float, delta_r: float) -> float:
        """
        Pressure = charge exploration/exploitation
        
        Formule : 0.3 * |delta_r| + 0.7 * (tau_c / (tau_c + 1.0))
        
        Rationale :
        - Delta_r élevé = exploration temporelle
        - Tau_c élevé = contrainte forte
        """
        normalized_tau = tau_c / (tau_c + 1.0)
        pressure = 0.3 * abs(delta_r) + 0.7 * normalized_tau
        return min(1.0, max(0.0, pressure))
    
    def _compute_fit(self, rho: float, response_length: int) -> float:
        """
        Fit = alignement production vs attentes
        
        Formule : 1.0 - |actual - expected| / expected
        
        Rationale :
        - Rho > 0 : attendu expansif (200+ mots)
        - Rho < 0 : attendu concis (100- mots)
        """
        # Longueur attendue selon rho
        if rho > 0:
            expected_length = 200 + rho * 100  # 200-300 mots
        elif rho < 0:
            expected_length = 150 + rho * 50   # 100-150 mots
        else:
            expected_length = 150
        
        # Écart normalisé
        deviation = abs(response_length - expected_length) / expected_length
        fit = 1.0 - min(1.0, deviation)
        
        return max(0.0, min(1.0, fit))
    
    def _compute_tension(self, coherence: float, pressure: float) -> float:
        """
        Tension = stress système
        
        Formule : 0.4 * (1 - coherence) + 0.6 * pressure
        
        Rationale :
        - Structure faible (low coherence) = tension
        - Charge forte (high pressure) = tension
        """
        tension = 0.4 * (1.0 - coherence) + 0.6 * pressure
        return min(1.0, max(0.0, tension))
```

#### 1.2 : Intégrer dans API

**Fichier à modifier :** `app/models.py`

Ajouter champ `consciousness_level` :

```python
# app/models.py

class ChatRequest(BaseModel):
    text: str
    session_id: Optional[str] = None
    profile: str = "balanced"
    enable_context: bool = True
    max_history: int = 20
    consciousness_level: int = 0  # NOUVEAU : 0=off, 1=passive, 2=adaptive, 3=full
    
    @validator('consciousness_level')
    def validate_consciousness_level(cls, v):
        if v not in [0, 1, 2, 3]:
            raise ValueError("consciousness_level must be 0, 1, 2, or 3")
        return v


class ChatResponse(BaseModel):
    text: str
    session_id: str
    physics_state: dict
    context: Optional[dict] = None
    latency: dict
    tokens: Optional[dict] = None
    consciousness: Optional[dict] = None  # NOUVEAU : métriques si level >= 1
```

**Fichier à modifier :** `app/api/chat.py`

Intégrer calcul métriques :

```python
# app/api/chat.py (MODIFICATIONS)

from services.consciousness.metrics import ConsciousnessMonitor

@router.post("/message")
async def chat_message(request: ChatRequest):
    """
    ... docstring existante ...
    """
    # ... code existant jusqu'à génération réponse ...
    
    # NOUVEAU : Initialiser moniteur de conscience
    consciousness_monitor = ConsciousnessMonitor(level=request.consciousness_level)
    
    # ... générer réponse (code existant) ...
    
    # NOUVEAU : Calculer métriques si activé
    consciousness_metrics = None
    if request.consciousness_level >= 1:
        consciousness_metrics = consciousness_monitor.compute_metrics(
            context_weight=context.total_weight if context else 0.0,
            num_concepts=len(context.neighbor_concepts) if context else 0,
            physics_state={
                "tau_c": state.tau_c,
                "rho": state.rho,
                "delta_r": state.delta_r
            },
            response_length=len(result["text"].split())
        )
    
    return ChatResponse(
        text=result["text"],
        session_id=session_id,
        physics_state=state.dict(),
        context=context.dict() if context else None,
        latency=latency,
        tokens=tokens,
        consciousness=consciousness_metrics.dict() if consciousness_metrics else None  # NOUVEAU
    )
```

#### 1.3 : Tests unitaires

**Fichier :** `tests/benchmarks/test_phase_1.py`

```python
"""
Tests unitaires Phase 1 : Métriques passives
"""
import pytest
from services.consciousness.metrics import ConsciousnessMonitor, ConsciousnessMetrics


class TestConsciousnessMetrics:
    """Tests métriques épistémiques"""
    
    def test_monitor_level_0_returns_none(self):
        """Level 0 ne calcule pas de métriques"""
        monitor = ConsciousnessMonitor(level=0)
        metrics = monitor.compute_metrics(
            context_weight=5.0,
            num_concepts=7,
            physics_state={"tau_c": 1.0, "rho": 0.2, "delta_r": 0.0},
            response_length=150
        )
        assert metrics is None
    
    def test_monitor_level_1_returns_metrics(self):
        """Level 1 calcule métriques"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=5.6,
            num_concepts=7,
            physics_state={"tau_c": 1.0, "rho": 0.2, "delta_r": 0.0},
            response_length=150
        )
        assert metrics is not None
        assert isinstance(metrics, ConsciousnessMetrics)
        assert 0.0 <= metrics.coherence <= 1.0
        assert 0.0 <= metrics.tension <= 1.0
        assert 0.0 <= metrics.fit <= 1.0
        assert 0.0 <= metrics.pressure <= 1.0
    
    def test_high_coherence_scenario(self):
        """Contexte fort → haute cohérence"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=8.0,  # Fort
            num_concepts=10,
            physics_state={"tau_c": 1.0, "rho": 0.0, "delta_r": 0.0},
            response_length=150
        )
        assert metrics.coherence > 0.7  # Attendu haute
    
    def test_high_pressure_scenario(self):
        """Tau_c élevé → haute pression"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=5.0,
            num_concepts=7,
            physics_state={"tau_c": 1.8, "rho": 0.0, "delta_r": 0.5},  # Élevés
            response_length=150
        )
        assert metrics.pressure > 0.7  # Attendu haute
    
    def test_high_tension_scenario(self):
        """Coherence basse + pressure haute → haute tension"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=1.0,  # Faible
            num_concepts=5,
            physics_state={"tau_c": 1.8, "rho": 0.0, "delta_r": 0.5},  # Haute pression
            response_length=150
        )
        assert metrics.tension > 0.6  # Attendu haute
    
    def test_metrics_dict_serialization(self):
        """Métriques sérialisables en JSON"""
        monitor = ConsciousnessMonitor(level=1)
        metrics = monitor.compute_metrics(
            context_weight=5.0,
            num_concepts=7,
            physics_state={"tau_c": 1.0, "rho": 0.2, "delta_r": 0.0},
            response_length=150
        )
        metrics_dict = metrics.dict()
        assert "coherence" in metrics_dict
        assert "tension" in metrics_dict
        assert "fit" in metrics_dict
        assert "pressure" in metrics_dict
        assert "stability_score" in metrics_dict


def test_api_consciousness_level_0():
    """Test API avec consciousness_level=0"""
    # TODO: Test intégration API
    pass


def test_api_consciousness_level_1():
    """Test API avec consciousness_level=1"""
    # TODO: Test intégration API
    pass
```

Exécuter tests :
```bash
pytest tests/benchmarks/test_phase_1.py -v
```

#### 1.4 : Benchmark Phase 1

**Fichier :** `tests/benchmarks/benchmark_phase_1.py`

```python
"""
Benchmark Phase 1 : Impact métriques passives
"""
import asyncio
from benchmark_suite import LyraBenchmark
import pandas as pd


async def benchmark_consciousness_overhead():
    """Compare overhead level 0 vs level 1"""
    
    async with LyraBenchmark() as benchmark:
        print("\n" + "="*60)
        print("PHASE 1 BENCHMARK: Consciousness Overhead")
        print("="*60)
        
        prompts = [
            "What is entropy?",
            "Explain quantum mechanics",
            "How does photosynthesis work?"
        ]
        
        results = []
        
        for prompt in prompts:
            print(f"\nTesting: {prompt[:40]}...")
            
            # Level 0 (baseline)
            response_0 = await benchmark.client.post(
                f"{benchmark.base_url}/chat/message",
                json={
                    "text": prompt,
                    "consciousness_level": 0
                }
            )
            data_0 = response_0.json()
            
            # Level 1 (passive metrics)
            response_1 = await benchmark.client.post(
                f"{benchmark.base_url}/chat/message",
                json={
                    "text": prompt,
                    "consciousness_level": 1
                }
            )
            data_1 = response_1.json()
            
            overhead_ms = data_1["latency"]["total"] - data_0["latency"]["total"]
            
            result = {
                "prompt": prompt[:30],
                "level_0_latency_ms": data_0["latency"]["total"],
                "level_1_latency_ms": data_1["latency"]["total"],
                "overhead_ms": overhead_ms,
                "overhead_percent": (overhead_ms / data_0["latency"]["total"]) * 100,
                "coherence": data_1.get("consciousness", {}).get("coherence"),
                "tension": data_1.get("consciousness", {}).get("tension"),
                "fit": data_1.get("consciousness", {}).get("fit")
            }
            
            results.append(result)
            
            print(f"  Level 0: {result['level_0_latency_ms']:.2f}ms")
            print(f"  Level 1: {result['level_1_latency_ms']:.2f}ms")
            print(f"  Overhead: +{result['overhead_ms']:.2f}ms ({result['overhead_percent']:.2f}%)")
            print(f"  Metrics: coherence={result['coherence']:.2f}, tension={result['tension']:.2f}")
        
        df = pd.DataFrame(results)
        
        print(f"\n📊 Results:")
        print(f"  Average overhead: {df['overhead_ms'].mean():.2f}ms ({df['overhead_percent'].mean():.2f}%)")
        print(f"  Max overhead: {df['overhead_ms'].max():.2f}ms")
        print(f"  Target: < 5ms")
        
        if df['overhead_ms'].mean() < 5.0:
            print(f"  ✅ PASS: Overhead acceptable")
        else:
            print(f"  ❌ FAIL: Overhead too high")
        
        benchmark.save_results(df, "phase1_consciousness_overhead")
        
        return df


async def main():
    await benchmark_consciousness_overhead()


if __name__ == "__main__":
    asyncio.run(main())
```

Exécuter :
```bash
python tests/benchmarks/benchmark_phase_1.py
```

**Résultats attendus :**
```
PHASE 1 BENCHMARK: Consciousness Overhead
============================================================

Testing: What is entropy?...
  Level 0: 1245.32ms
  Level 1: 1248.15ms
  Overhead: +2.83ms (0.23%)
  Metrics: coherence=0.78, tension=0.42

Testing: Explain quantum mechanics...
  Level 0: 1312.45ms
  Level 1: 1316.23ms
  Overhead: +3.78ms (0.29%)
  Metrics: coherence=0.82, tension=0.38

...

📊 Results:
  Average overhead: 3.21ms (0.26%)
  Max overhead: 4.12ms
  Target: < 5ms
  ✅ PASS: Overhead acceptable

💾 Results saved: benchmark_results/phase1_consciousness_overhead_*.csv
```

#### 1.5 : Documentation Phase 1

**Fichier :** `docs/phases/PHASE_1_IMPLEMENTATION.md`

```markdown
# Phase 1 : Métriques Passives (Conscience Niveau 1)

**Date :** [DATE]  
**Version :** 1.1.0  
**Consciousness Level :** 1 (passive)

## Implémentation

### Fichiers créés
- `services/consciousness/metrics.py` : Module calcul métriques
- `tests/benchmarks/test_phase_1.py` : Tests unitaires
- `tests/benchmarks/benchmark_phase_1.py` : Benchmark overhead

### Fichiers modifiés
- `app/models.py` : Ajout champ `consciousness_level`
- `app/api/chat.py` : Intégration calcul métriques

### API Changes

#### Nouveau champ request
```json
{
  "text": "...",
  "consciousness_level": 1
}
```

#### Nouveau champ response
```json
{
  "consciousness": {
    "coherence": 0.78,
    "tension": 0.42,
    "fit": 0.85,
    "pressure": 0.51,
    "stability_score": 0.60
  }
}
```

## Métriques Épistémiques

### Coherence (0-1)
Densité sémantique du contexte.  
**Formule :** `min(1.0, avg_weight / 0.8)`

**Interprétation :**
- > 0.7 : Contexte fort, concepts bien connectés
- 0.4-0.7 : Contexte moyen
- < 0.4 : Contexte faible, concepts épars

### Tension (0-1)
Stress système = structure faible OU charge forte.  
**Formule :** `0.4 * (1 - coherence) + 0.6 * pressure`

**Interprétation :**
- > 0.8 : Haute tension → risque instabilité
- 0.5-0.8 : Tension modérée
- < 0.5 : Basse tension, système stable

### Fit (0-1)
Alignement production vs attentes (basé sur rho).  
**Formule :** `1.0 - |actual_length - expected_length| / expected_length`

### Pressure (0-1)
Charge exploration/exploitation.  
**Formule :** `0.3 * |delta_r| + 0.7 * (tau_c / (tau_c + 1.0))`

### Stability Score (composite)
Score de stabilité globale.  
**Formule :** `(coherence + fit) / 2 - tension * 0.5`

## Benchmark Results

### Overhead Latence
- **Moyen :** [X] ms ([Y]%)
- **Max :** [X] ms
- **Target :** < 5ms
- **Status :** ✅ PASS / ❌ FAIL

### Tests Unitaires
- **Total tests :** [X]
- **Passed :** [X]
- **Failed :** [X]

## Exemples d'utilisation

### cURL
```bash
curl -X POST "http://localhost:8000/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Explain entropy",
    "consciousness_level": 1
  }'
```

### Python
```python
import httpx

response = httpx.post(
    "http://localhost:8000/chat/message",
    json={
        "text": "Explain entropy",
        "consciousness_level": 1
    }
)

data = response.json()
print(data["consciousness"])
# {'coherence': 0.78, 'tension': 0.42, ...}
```

## Validation Checklist
- [ ] Tests unitaires passent
- [ ] Benchmark overhead < 5ms
- [ ] API fonctionne avec level 0 et 1
- [ ] Documentation complète
- [ ] Exemples testés
```

#### 1.6 : Checklist Phase 1

**Fichier :** `docs/phases/PHASE_1_CHECKLIST.md`

```markdown
# Phase 1 : Checklist

## Implémentation
- [ ] `services/consciousness/metrics.py` créé
- [ ] `ConsciousnessMonitor` implémenté
- [ ] `ConsciousnessMetrics` implémenté
- [ ] Tests unitaires créés (`test_phase_1.py`)
- [ ] Tests unitaires passent (pytest)
- [ ] API modifiée (`models.py`, `chat.py`)
- [ ] `consciousness_level` field ajouté
- [ ] `consciousness` response field ajouté

## Benchmarking
- [ ] Benchmark overhead créé (`benchmark_phase_1.py`)
- [ ] Benchmark exécuté avec succès
- [ ] Overhead < 5ms validé
- [ ] Résultats sauvegardés (CSV)
- [ ] Comparaison avec baseline

## Documentation
- [ ] `PHASE_1_IMPLEMENTATION.md` créé
- [ ] Métriques expliquées
- [ ] Exemples cURL fournis
- [ ] Exemples Python fournis
- [ ] Screenshots/logs inclus

## Validation
- [ ] Serveur redémarre sans erreur
- [ ] API docs mises à jour (`/docs`)
- [ ] Test manuel avec consciousness_level=0
- [ ] Test manuel avec consciousness_level=1
- [ ] Métriques cohérentes (pas de NaN/Inf)

## Git
- [ ] Commit avec message clair
- [ ] Tag `v1.1.0-phase1`

## Commandes de validation

```bash
# Tests unitaires
pytest tests/benchmarks/test_phase_1.py -v

# Benchmark
python tests/benchmarks/benchmark_phase_1.py

# Test API manuel
curl -X POST "http://localhost:8000/chat/message" \
  -H "Content-Type: application/json" \
  -d '{"text": "Test", "consciousness_level": 1}' | jq '.consciousness'

# Vérifier docs
open http://localhost:8000/docs

# Commit
git add .
git commit -m "Phase 1: Passive consciousness metrics implemented"
git tag v1.1.0-phase1
```
```

---

## 🔄 PHASE 2 : ADAPTATION DOUCE (Conscience Niveau 2)

### Objectifs
1. Implémenter adaptation graduelle des profils
2. Persistence ajustements en session
3. Benchmarker sur conversations longues
4. Documenter

### Tâches

#### 2.1 : Implémenter module d'adaptation

**Fichier :** `services/consciousness/adaptation.py`

```python
"""
Consciousness Adaptation - Niveau 2 (Adaptatif)

Ajuste graduellement le profil Bezier basé sur métriques.
Adaptation progressive (5% par interaction) pour stabilité.
"""
from typing import Optional, Dict
from .metrics import ConsciousnessMonitor, ConsciousnessMetrics


class AdaptiveConsciousness(ConsciousnessMonitor):
    """
    Adaptation progressive basée sur métriques épistémiques
    
    Niveau 2 : Ajustements graduels du profil (5% par interaction)
    """
    
    def __init__(self, level: int = 2, adaptation_rate: float = 0.05):
        """
        Args:
            level: Niveau conscience (doit être >= 2)
            adaptation_rate: Taux d'adaptation (default 5%)
        """
        super().__init__(level)
        self.adaptation_rate = adaptation_rate
    
    def suggest_adjustments(
        self,
        metrics: ConsciousnessMetrics,
        current_profile: dict,
        session_length: int
    ) -> Optional[Dict[str, float]]:
        """
        Suggère ajustements basés sur métriques
        
        Règles d'adaptation :
        1. Tension haute (> 0.75) → réduire tau_c (plus créativité)
        2. Coherence basse (< 0.3) → augmenter |rho| (plus focus)
        3. Fit excellent (> 0.8) + stabilité → augmenter delta_r (exploration)
        4. Pressure très haute (> 0.85) → réduire tau_c et delta_r
        
        Args:
            metrics: Métriques épistémiques actuelles
            current_profile: Profil Bezier actuel
            session_length: Nombre d'interactions session
        
        Returns:
            Dict avec multiplicateurs, ou None si pas d'ajustement
        """
        if self.level < 2:
            return None
        
        adjustments = {}
        reason = []
        
        # RÈGLE 1 : Tension haute → réduire contrainte
        if metrics.tension > 0.75:
            adjustments["tau_c_multiplier"] = 1.0 - self.adaptation_rate
            reason.append(f"High tension ({metrics.tension:.2f}) - reducing tau_c")
        
        # RÈGLE 2 : Coherence basse → augmenter focus
        if metrics.coherence < 0.3:
            # Augmenter rho (si positif) ou le rendre plus négatif
            adjustments["rho_shift"] = -self.adaptation_rate if current_profile.get("avg_rho", 0) > 0 else self.adaptation_rate
            reason.append(f"Low coherence ({metrics.coherence:.2f}) - adjusting focus")
        
        # RÈGLE 3 : Fit excellent + stabilité → exploration
        if metrics.fit > 0.8 and metrics.stability_score > 0.7:
            adjustments["delta_r_multiplier"] = 1.0 + self.adaptation_rate * 0.5  # Plus prudent
            reason.append(f"High fit & stability - encouraging exploration")
        
        # RÈGLE 4 : Pressure très haute → réduire charge
        if metrics.pressure > 0.85:
            adjustments["tau_c_multiplier"] = 1.0 - self.adaptation_rate * 1.5
            adjustments["delta_r_multiplier"] = 1.0 - self.adaptation_rate
            reason.append(f"Very high pressure ({metrics.pressure:.2f}) - reducing load")
        
        # RÈGLE 5 : Session longue (> 30) + tension stable → aucun changement
        if session_length > 30 and 0.4 < metrics.tension < 0.6:
            return None  # Système stable, ne pas perturber
        
        if adjustments:
            adjustments["reason"] = "; ".join(reason)
            adjustments["triggered_by"] = {
                "coherence": metrics.coherence,
                "tension": metrics.tension,
                "fit": metrics.fit,
                "pressure": metrics.pressure
            }
            return adjustments
        
        return None
    
    def apply_adjustments(
        self,
        current_params: dict,
        adjustments: dict
    ) -> dict:
        """
        Applique ajustements aux paramètres actuels
        
        Args:
            current_params: Paramètres actuels {tau_c, rho, delta_r, kappa}
            adjustments: Multiplicateurs {tau_c_multiplier, rho_shift, ...}
        
        Returns:
            Nouveaux paramètres ajustés
        """
        adjusted = current_params.copy()
        
        # Appliquer multiplicateurs
        if "tau_c_multiplier" in adjustments:
            adjusted["tau_c"] *= adjustments["tau_c_multiplier"]
            adjusted["tau_c"] = max(0.5, min(2.0, adjusted["tau_c"]))  # Bornes
        
        if "rho_shift" in adjustments:
            adjusted["rho"] += adjustments["rho_shift"]
            adjusted["rho"] = max(-1.0, min(1.0, adjusted["rho"]))  # Bornes
        
        if "delta_r_multiplier" in adjustments:
            adjusted["delta_r"] *= adjustments["delta_r_multiplier"]
            adjusted["delta_r"] = max(-1.0, min(1.0, adjusted["delta_r"]))  # Bornes
        
        return adjusted
```

#### 2.2 : Modifier système de sessions

**Fichier à modifier :** `database/engine.py`

Ajouter stockage ajustements :

```python
# database/engine.py (AJOUTS)

async def store_session_adjustments(
    self,
    session_id: str,
    adjustments: dict,
    metrics: dict
):
    """Stocke ajustements de profil pour une session"""
    async with self._connect() as db:
        await db.execute(
            """
            INSERT INTO session_adjustments 
            (session_id, adjustments, metrics, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (
                session_id,
                json.dumps(adjustments),
                json.dumps(metrics),
                time.time()
            )
        )
        await db.commit()


async def get_session_adjustments(
    self,
    session_id: str,
    limit: int = 10
) -> list:
    """Récupère historique ajustements d'une session"""
    async with self._connect() as db:
        async with db.execute(
            """
            SELECT adjustments, metrics, timestamp
            FROM session_adjustments
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (session_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "adjustments": json.loads(row[0]),
                    "metrics": json.loads(row[1]),
                    "timestamp": row[2]
                }
                for row in rows
            ]
```

**Fichier à modifier :** `database/schema.sql`

Ajouter table :

```sql
-- database/schema.sql (AJOUT)

CREATE TABLE IF NOT EXISTS session_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    adjustments TEXT NOT NULL, -- JSON
    metrics TEXT NOT NULL,     -- JSON
    timestamp REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX idx_session_adjustments_session 
ON session_adjustments(session_id, timestamp DESC);
```

#### 2.3 : Intégrer dans API

**Fichier à modifier :** `app/api/chat.py`

```python
# app/api/chat.py (MODIFICATIONS PHASE 2)

from services.consciousness.adaptation import AdaptiveConsciousness

@router.post("/message")
async def chat_message(request: ChatRequest):
    # ... code existant ...
    
    # NOUVEAU : Utiliser AdaptiveConsciousness si level >= 2
    if request.consciousness_level >= 2:
        consciousness_monitor = AdaptiveConsciousness(
            level=request.consciousness_level,
            adaptation_rate=0.05
        )
    else:
        consciousness_monitor = ConsciousnessMonitor(
            level=request.consciousness_level
        )
    
    # ... génération réponse ...
    
    # NOUVEAU : Suggérer ajustements si level >= 2
    profile_adjustments = None
    if request.consciousness_level >= 2 and consciousness_metrics:
        # Récupérer historique session
        history = await db.get_session_history(session_id, limit=50)
        session_length = len(history)
        
        # Suggérer ajustements
        profile_adjustments = consciousness_monitor.suggest_adjustments(
            metrics=consciousness_metrics,
            current_profile={
                "avg_tau_c": state.tau_c,
                "avg_rho": state.rho,
                "avg_delta_r": state.delta_r
            },
            session_length=session_length
        )
        
        # Stocker ajustements si présents
        if profile_adjustments:
            await db.store_session_adjustments(
                session_id=session_id,
                adjustments=profile_adjustments,
                metrics=consciousness_metrics.dict()
            )
    
    return ChatResponse(
        # ... champs existants ...
        consciousness=consciousness_metrics.dict() if consciousness_metrics else None,
        profile_adjustments=profile_adjustments  # NOUVEAU
    )
```

**Modèle response à modifier :**

```python
# app/models.py

class ChatResponse(BaseModel):
    text: str
    session_id: str
    physics_state: dict
    context: Optional[dict] = None
    latency: dict
    tokens: Optional[dict] = None
    consciousness: Optional[dict] = None
    profile_adjustments: Optional[dict] = None  # NOUVEAU : si level >= 2
```

#### 2.4 : Benchmark Phase 2

**Fichier :** `tests/benchmarks/benchmark_phase_2.py`

```python
"""
Benchmark Phase 2 : Adaptation progressive
Compare profils statiques (level 1) vs adaptatifs (level 2)
"""
import asyncio
from benchmark_suite import LyraBenchmark
import pandas as pd


async def benchmark_adaptive_conversation():
    """
    Test conversation longue avec adaptation
    
    Scénario :
    - 30 messages alternés
    - Prompts variés (simples → complexes)
    - Mesure évolution métriques
    """
    async with LyraBenchmark() as benchmark:
        print("\n" + "="*60)
        print("PHASE 2 BENCHMARK: Adaptive Conversation (30 turns)")
        print("="*60)
        
        prompts = [
            "Hello",
            "What is entropy?",
            "Explain it simply",
            "Go deeper into thermodynamics",
            "How does this relate to information theory?",
            "Give me equations",
            "Explain like I'm 5",
            "Now explain like I'm a physicist",
            # ... 22 autres prompts variés
        ] * 4  # Répéter pour avoir 30
        
        prompts = prompts[:30]
        
        results_static = []
        results_adaptive = []
        
        # Test 1 : Statique (level 1)
        print("\n[Test 1] Static profile (consciousness_level=1)")
        session_id_static = "benchmark_static"
        
        for turn, prompt in enumerate(prompts):
            response = await benchmark.client.post(
                f"{benchmark.base_url}/chat/message",
                json={
                    "text": prompt,
                    "session_id": session_id_static,
                    "consciousness_level": 1,
                    "profile": "balanced"
                }
            )
            data = response.json()
            
            results_static.append({
                "turn": turn,
                "level": 1,
                "prompt": prompt[:30],
                "latency_ms": data["latency"]["total"],
                "coherence": data["consciousness"]["coherence"],
                "tension": data["consciousness"]["tension"],
                "fit": data["consciousness"]["fit"],
                "stability": data["consciousness"]["stability_score"],
                "adjustments": None
            })
            
            if (turn + 1) % 5 == 0:
                print(f"  Turn {turn+1}/30: tension={results_static[-1]['tension']:.2f}")
        
        # Test 2 : Adaptatif (level 2)
        print("\n[Test 2] Adaptive profile (consciousness_level=2)")
        session_id_adaptive = "benchmark_adaptive"
        
        for turn, prompt in enumerate(prompts):
            response = await benchmark.client.post(
                f"{benchmark.base_url}/chat/message",
                json={
                    "text": prompt,
                    "session_id": session_id_adaptive,
                    "consciousness_level": 2,
                    "profile": "balanced"
                }
            )
            data = response.json()
            
            results_adaptive.append({
                "turn": turn,
                "level": 2,
                "prompt": prompt[:30],
                "latency_ms": data["latency"]["total"],
                "coherence": data["consciousness"]["coherence"],
                "tension": data["consciousness"]["tension"],
                "fit": data["consciousness"]["fit"],
                "stability": data["consciousness"]["stability_score"],
                "adjustments": data.get("profile_adjustments")
            })
            
            if (turn + 1) % 5 == 0:
                adj = "YES" if results_adaptive[-1]['adjustments'] else "NO"
                print(f"  Turn {turn+1}/30: tension={results_adaptive[-1]['tension']:.2f}, adjusted={adj}")
        
        # Analyse comparative
        df_static = pd.DataFrame(results_static)
        df_adaptive = pd.DataFrame(results_adaptive)
        
        print(f"\n📊 Comparative Analysis:")
        print(f"\nStatic (Level 1):")
        print(f"  Avg tension: {df_static['tension'].mean():.3f} ± {df_static['tension'].std():.3f}")
        print(f"  Avg stability: {df_static['stability'].mean():.3f}")
        print(f"  Tension spikes (> 0.75): {(df_static['tension'] > 0.75).sum()}")
        
        print(f"\nAdaptive (Level 2):")
        print(f"  Avg tension: {df_adaptive['tension'].mean():.3f} ± {df_adaptive['tension'].std():.3f}")
        print(f"  Avg stability: {df_adaptive['stability'].mean():.3f}")
        print(f"  Tension spikes (> 0.75): {(df_adaptive['tension'] > 0.75).sum()}")
        print(f"  Adjustments triggered: {df_adaptive['adjustments'].notna().sum()}")
        
        # Sauvegarder
        df_combined = pd.concat([df_static, df_adaptive], ignore_index=True)
        benchmark.save_results(df_combined, "phase2_adaptive_conversation")
        
        return df_combined


async def main():
    await benchmark_adaptive_conversation()


if __name__ == "__main__":
    asyncio.run(main())
```

#### 2.5 : Documentation Phase 2

**Fichier :** `docs/phases/PHASE_2_IMPLEMENTATION.md`

[Contenu similaire à Phase 1, adapté pour Phase 2]

#### 2.6 : Checklist Phase 2

**Fichier :** `docs/phases/PHASE_2_CHECKLIST.md`

[Contenu similaire à Phase 1]

---

## 🧠 PHASE 3 : MÉMOIRE SOPHISTIQUÉE (Conscience Niveau 3)

[Instructions détaillées similaires aux phases précédentes]

**Fichiers à créer :**
- `services/consciousness/memory.py`
- `tests/benchmarks/test_phase_3.py`
- `tests/benchmarks/benchmark_phase_3.py`
- `docs/phases/PHASE_3_IMPLEMENTATION.md`
- `docs/phases/PHASE_3_CHECKLIST.md`

**Fonctionnalités :**
- Rappel mémoire avec décroissance temporelle
- Similarité Jaccard
- Injection [MEMORY ECHO]
- Overhead < 20ms

---

## ✅ VALIDATION FINALE

### Checklist globale

Après Phase 3 complétée :

- [ ] 4 niveaux conscience implémentés (0, 1, 2, 3)
- [ ] Tests unitaires passent (toutes phases)
- [ ] Benchmarks exécutés (toutes phases)
- [ ] Overhead acceptable :
  - Level 1 : < 5ms
  - Level 2 : < 10ms
  - Level 3 : < 20ms
- [ ] Documentation complète (3 phases)
- [ ] API fonctionnelle (tous niveaux)
- [ ] Comparaison baseline effectuée

### Rapport final

**Fichier à créer :** `docs/CONSCIOUSNESS_IMPLEMENTATION_REPORT.md`

```markdown
# Rapport d'Implémentation - Conscience Modulaire

## Résumé Exécutif

- **Durée totale :** [X] heures
- **Phases complétées :** 3/3
- **Tests :** [X]/[X] passent
- **Overhead :**
  - Level 1 : [X]ms ✅/❌
  - Level 2 : [X]ms ✅/❌
  - Level 3 : [X]ms ✅/❌

## Métriques Clés

### Performance
[Tableaux comparatifs baseline vs level 3]

### Qualité
[Analyse subjective conversations]

### Stabilité
[Variance métriques sur 50 turns]

## Recommandations

1. Niveau par défaut recommandé : [X]
2. Use cases par niveau
3. Optimisations possibles

## Prochaines Étapes

- [ ] Déploiement production
- [ ] Tests A/B utilisateurs
- [ ] Fine-tuning seuils
```

---

## 📝 NOTES IMPORTANTES POUR HAIKU

### Principes de développement

1. **Incrémentalité stricte**
   - Une phase à la fois
   - Ne pas passer à la suivante avant validation complète

2. **Tests systématiques**
   - Tests unitaires AVANT intégration
   - Benchmarks APRÈS intégration
   - Validation manuelle également

3. **Documentation continue**
   - Documenter AU FUR ET À MESURE
   - Pas de "on documentera plus tard"

4. **Communication**
   - Rapporter progrès régulièrement
   - Signaler blocages immédiatement
   - Proposer alternatives si nécessaire

### En cas de problème

**Si overhead trop élevé** :
- Profiler le code
- Identifier bottleneck
- Optimiser (cache, pré-calcul, etc.)

**Si tests échouent** :
- Debugging systématique
- Ne pas ignorer failures
- Corriger avant de continuer

**Si API casse** :
- Rollback immédiat
- Analyser cause
- Implémenter autrement

### Questions fréquentes

**Q : Puis-je modifier l'ordre des phases ?**  
R : Non. L'ordre est conçu pour minimiser risques.

**Q : Puis-je sauter benchmarks ?**  
R : Non. Benchmarks sont essentiels pour validation scientifique.

**Q : Puis-je fusionner phases ?**  
R : Non. Séparation permet isolation problèmes.

---

## 🎯 OBJECTIF FINAL

À la fin de cette mission, Lyra Clean aura :

✅ **4 niveaux de conscience** activables via API  
✅ **Benchmarks rigoureux** prouvant performance  
✅ **Documentation exhaustive** pour chaque niveau  
✅ **Architecture modulaire** permettant extensions  
✅ **Base scientifique** pour publications/comparaisons  

**Bonne chance, Claude Haiku ! 🚀**

---

**Version :** 1.0  
**Date :** 2025-01-16  
**Auteur :** Claude Sonnet 4.5  
**Destinataire :** Claude Haiku 4.5
