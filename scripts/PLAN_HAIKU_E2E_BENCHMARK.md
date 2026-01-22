# PLAN D'IMPLÉMENTATION - BENCHMARK E2E LYRA CLEAN

**Destinataire :** Claude Haiku 4.5 (Copilot)  
**Projet :** Lyra Clean - Système de conscience pour LLM  
**Objectif :** Compléter l'intégration et créer un benchmark de bout en bout  
**Date :** 26 novembre 2025

---

## 📋 CONTEXTE

Lyra Clean est un framework de chat LLM avec 4 niveaux de conscience :
- **Level 0** : Baseline (pas de conscience)
- **Level 1** : Métriques passives (coherence, tension, fit, pressure)
- **Level 2** : Adaptation graduelle des profils Bezier
- **Level 3** : Mémoire sémantique avec embeddings + decay temporel

**État actuel :**
- ✅ Code conscience implémenté (`metrics.py`, `adaptation.py`, `memory.py`)
- ✅ Tests unitaires passent (37+ tests)
- ⚠️ Benchmarks existants = tests unitaires isolés (pas d'appels LLM)
- ❌ Pas de benchmark E2E avec appels LLM réels
- ❌ Intégration API Level 3 non validée en conditions réelles

---

## 🎯 MISSIONS À ACCOMPLIR

### MISSION 1 : Vérifier/Compléter le Schema SQL
### MISSION 2 : Valider l'intégration API Level 3
### MISSION 3 : Créer le Benchmark E2E
### MISSION 4 : Exécuter et Documenter les Résultats

---

## MISSION 1 : SCHEMA SQL

### 1.1 Vérifier l'existence de `database/schema.sql`

Si le fichier existe, vérifier qu'il contient ces tables :

```sql
-- Tables requises
- concepts (id, rho_static, degree, access_count, last_accessed)
- relations (source, target, weight, kappa)
- sessions (session_id, created_at, last_activity, profile, params_snapshot, message_count, total_tokens)
- events (event_id, session_id, event_type, role, content, injected_concepts, graph_weight, timestamp, latency_ms)
- trajectories (id, session_id, event_id, t_param, tau_c, rho, delta_r, kappa, timestamp)
- profiles (profile_name, description, tau_c_curve, rho_curve, delta_r_curve, kappa_curve, is_default)
- semantic_memory (id, session_id, turn, content, embeddings, timestamp, turn_number)  -- PHASE 3
- session_adjustments (id, session_id, adjustments, metrics, timestamp)  -- PHASE 2
```

### 1.2 Si table `semantic_memory` manquante, l'ajouter :

```sql
CREATE TABLE IF NOT EXISTS semantic_memory (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    content TEXT NOT NULL,
    embeddings BLOB,  -- JSON array of floats (1024D)
    timestamp REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_semantic_memory_session 
ON semantic_memory(session_id, turn_number DESC);
```

### 1.3 Si table `session_adjustments` manquante, l'ajouter :

```sql
CREATE TABLE IF NOT EXISTS session_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    adjustments TEXT NOT NULL,  -- JSON
    metrics TEXT NOT NULL,      -- JSON
    timestamp REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_session_adjustments_session 
ON session_adjustments(session_id, timestamp DESC);
```

---

## MISSION 2 : VALIDER INTÉGRATION API LEVEL 3

### 2.1 Vérifier `services/consciousness/__init__.py`

Le fichier doit exporter :

```python
from .metrics import ConsciousnessMetrics, ConsciousnessMonitor
from .adaptation import AdaptiveConsciousness
from .memory import SemanticMemory, MemoryEntry

__all__ = [
    'ConsciousnessMetrics',
    'ConsciousnessMonitor', 
    'AdaptiveConsciousness',
    'SemanticMemory',
    'MemoryEntry'
]
```

### 2.2 Vérifier l'intégration dans `app/api/chat.py`

Le endpoint `/chat/message` doit :

1. **Avant génération LLM** (si level >= 3) :
   - Charger mémoire session
   - Encoder query avec embeddings
   - Rappeler messages similaires
   - Injecter [MEMORY ECHO] dans prompt

2. **Après génération LLM** (si level >= 1) :
   - Calculer métriques conscience
   - Si level >= 2 : suggérer ajustements
   - Si level >= 3 : stocker message en mémoire

### 2.3 Template de code à vérifier/ajouter dans `chat.py`

```python
# Après import existants, ajouter :
from services.consciousness import SemanticMemory

# Dans endpoint chat_message(), AVANT appel LLM :
memory_echo = None
if request.consciousness_level >= 3:
    semantic_memory = SemanticMemory(level=3)
    
    # Recall similar messages
    recalled = semantic_memory.recall_memory(
        session_id=session_id,
        query_embeddings=await get_embeddings(request.text),  # À implémenter
        current_turn=message_count,
        top_k=3
    )
    
    # Format for injection
    memory_echo = semantic_memory.format_memory_echo(recalled)
    
    if memory_echo:
        # Injecter dans messages avant LLM
        enriched_prompt["messages"].insert(-1, {
            "role": "system",
            "content": memory_echo
        })

# APRÈS génération LLM, stocker en mémoire :
if request.consciousness_level >= 3:
    await semantic_memory.store_memory(
        session_id=session_id,
        content=request.text,
        embeddings=await get_embeddings(request.text),
        turn_number=message_count
    )
```

### 2.4 Fonction helper pour embeddings (si manquante)

Créer `app/embeddings.py` :

```python
"""
Embedding generation via Ollama mxbai-embed-large
"""
import httpx
from typing import List

OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "mxbai-embed-large"

async def get_embeddings(text: str) -> List[float]:
    """
    Génère embeddings 1024D via Ollama.
    
    Args:
        text: Texte à encoder
        
    Returns:
        Liste de 1024 floats
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={
                "model": EMBEDDING_MODEL,
                "prompt": text
            }
        )
        response.raise_for_status()
        data = response.json()
        return data.get("embedding", [])
```

---

## MISSION 3 : CRÉER LE BENCHMARK E2E

### 3.1 Créer `tests/benchmarks/benchmark_e2e.py`

```python
"""
LYRA CLEAN - BENCHMARK END-TO-END
=================================

Test complet avec appels LLM réels pour tous les niveaux de conscience.

Mesure :
- Latence totale par niveau (0, 1, 2, 3)
- Overhead conscience vs baseline
- Fonctionnalité mémoire (recalls)
- Stabilité sur conversation longue
"""

import asyncio
import httpx
import time
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import uuid

# Configuration
API_BASE = "http://localhost:8000"
RESULTS_DIR = Path("benchmark_results")
RESULTS_DIR.mkdir(exist_ok=True)

# Prompts de test (variés pour tester mémoire)
TEST_PROMPTS = [
    "What is entropy in physics?",
    "Explain the concept of disorder",
    "How does entropy relate to information theory?",
    "What is thermodynamic equilibrium?",
    "Describe the second law of thermodynamics",
    "How does entropy connect to chaos?",
    "What is the relationship between entropy and order?",
    "Explain heat death of the universe",
    "How does entropy apply to data compression?",
    "Summarize what we discussed about entropy"
]

class E2EBenchmark:
    """Benchmark de bout en bout avec appels LLM réels."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=180.0)  # 3 min timeout
        self.results: List[Dict] = []
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    async def close(self):
        await self.client.aclose()
    
    async def check_health(self) -> bool:
        """Vérifie que le serveur est opérationnel."""
        try:
            response = await self.client.get(f"{API_BASE}/health")
            data = response.json()
            print(f"[Health] Status: {data.get('status')}")
            print(f"[Health] Ollama: {data.get('ollama', {}).get('connected')}")
            print(f"[Health] Database: {data.get('database', {}).get('connected')}")
            return data.get('status') in ['healthy', 'degraded']
        except Exception as e:
            print(f"[Health] FAILED: {e}")
            return False
    
    async def send_message(
        self,
        text: str,
        session_id: str,
        consciousness_level: int,
        profile: str = "balanced"
    ) -> Dict[str, Any]:
        """Envoie un message et mesure la latence."""
        
        start_time = time.time()
        
        try:
            response = await self.client.post(
                f"{API_BASE}/chat/message",
                json={
                    "text": text,
                    "session_id": session_id,
                    "profile": profile,
                    "enable_context": True,
                    "consciousness_level": consciousness_level,
                    "max_history": 20
                }
            )
            
            total_latency = (time.time() - start_time) * 1000
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "latency_ms": total_latency
                }
            
            data = response.json()
            
            return {
                "success": True,
                "latency_ms": total_latency,
                "response_length": len(data.get("text", "")),
                "consciousness": data.get("consciousness"),
                "memory_echo": data.get("memory_echo"),
                "context_latency": data.get("latency", {}).get("context_extraction", 0),
                "llm_latency": data.get("latency", {}).get("llm_generation", 0),
                "tokens": data.get("tokens", {})
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000
            }
    
    async def benchmark_single_level(
        self,
        level: int,
        prompts: List[str],
        session_prefix: str = "e2e_test"
    ) -> List[Dict]:
        """Benchmark un niveau de conscience sur une conversation."""
        
        session_id = f"{session_prefix}_L{level}_{uuid.uuid4().hex[:8]}"
        results = []
        
        print(f"\n{'='*60}")
        print(f"  LEVEL {level} - Session: {session_id}")
        print(f"{'='*60}")
        
        for turn, prompt in enumerate(prompts, 1):
            print(f"  Turn {turn}/{len(prompts)}: {prompt[:40]}...")
            
            result = await self.send_message(
                text=prompt,
                session_id=session_id,
                consciousness_level=level
            )
            
            result.update({
                "level": level,
                "turn": turn,
                "prompt": prompt,
                "session_id": session_id
            })
            
            results.append(result)
            
            if result["success"]:
                latency = result["latency_ms"]
                has_consciousness = result.get("consciousness") is not None
                has_memory = result.get("memory_echo") is not None
                print(f"    ✓ {latency:.0f}ms | Consciousness: {has_consciousness} | Memory: {has_memory}")
            else:
                print(f"    ✗ ERROR: {result.get('error', 'Unknown')}")
            
            # Pause entre requêtes (éviter surcharge)
            await asyncio.sleep(0.5)
        
        return results
    
    async def run_full_benchmark(self):
        """Exécute le benchmark complet sur tous les niveaux."""
        
        print("\n" + "="*70)
        print("  LYRA CLEAN - BENCHMARK END-TO-END")
        print("  Testing all consciousness levels with real LLM calls")
        print("="*70)
        
        # Health check
        if not await self.check_health():
            print("\n❌ Server not healthy. Aborting benchmark.")
            return
        
        all_results = []
        
        # Test chaque niveau
        for level in [0, 1, 2, 3]:
            results = await self.benchmark_single_level(
                level=level,
                prompts=TEST_PROMPTS
            )
            all_results.extend(results)
            
            # Pause entre niveaux
            await asyncio.sleep(2)
        
        self.results = all_results
        
        # Sauvegarder et analyser
        self.save_results()
        self.print_summary()
    
    def save_results(self):
        """Sauvegarde les résultats en CSV et JSON."""
        
        # CSV
        csv_path = RESULTS_DIR / f"e2e_benchmark_{self.timestamp}.csv"
        
        fieldnames = [
            "level", "turn", "prompt", "success", "latency_ms",
            "response_length", "context_latency", "llm_latency",
            "has_consciousness", "has_memory", "error"
        ]
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for r in self.results:
                writer.writerow({
                    "level": r.get("level"),
                    "turn": r.get("turn"),
                    "prompt": r.get("prompt", "")[:50],
                    "success": r.get("success"),
                    "latency_ms": round(r.get("latency_ms", 0), 2),
                    "response_length": r.get("response_length", 0),
                    "context_latency": round(r.get("context_latency", 0), 2),
                    "llm_latency": round(r.get("llm_latency", 0), 2),
                    "has_consciousness": r.get("consciousness") is not None,
                    "has_memory": r.get("memory_echo") is not None,
                    "error": r.get("error", "")[:100] if r.get("error") else ""
                })
        
        print(f"\n📄 Results saved: {csv_path}")
        
        # JSON config
        config_path = RESULTS_DIR / f"e2e_benchmark_{self.timestamp}_config.json"
        
        config = {
            "timestamp": self.timestamp,
            "prompts_count": len(TEST_PROMPTS),
            "levels_tested": [0, 1, 2, 3],
            "total_requests": len(self.results),
            "successful_requests": sum(1 for r in self.results if r.get("success")),
            "api_base": API_BASE
        }
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"📄 Config saved: {config_path}")
    
    def print_summary(self):
        """Affiche un résumé des résultats."""
        
        print("\n" + "="*70)
        print("  RÉSUMÉ BENCHMARK E2E")
        print("="*70)
        
        # Grouper par niveau
        by_level = {}
        for r in self.results:
            level = r.get("level", -1)
            if level not in by_level:
                by_level[level] = []
            by_level[level].append(r)
        
        # Stats par niveau
        print("\n  Level | Requests | Success | Avg Latency | Consciousness | Memory")
        print("  " + "-"*65)
        
        baseline_latency = None
        
        for level in sorted(by_level.keys()):
            results = by_level[level]
            success_count = sum(1 for r in results if r.get("success"))
            success_rate = (success_count / len(results)) * 100 if results else 0
            
            latencies = [r["latency_ms"] for r in results if r.get("success")]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            
            if level == 0:
                baseline_latency = avg_latency
            
            has_consciousness = sum(1 for r in results if r.get("consciousness"))
            has_memory = sum(1 for r in results if r.get("memory_echo"))
            
            print(f"    {level}   |    {len(results):2d}    |  {success_rate:5.1f}% |  {avg_latency:8.0f}ms  |      {has_consciousness:2d}       |   {has_memory:2d}")
        
        # Overhead analysis
        if baseline_latency and len(by_level) > 1:
            print("\n  OVERHEAD ANALYSIS (vs Level 0 baseline)")
            print("  " + "-"*45)
            
            for level in sorted(by_level.keys()):
                if level == 0:
                    continue
                    
                results = by_level[level]
                latencies = [r["latency_ms"] for r in results if r.get("success")]
                avg_latency = sum(latencies) / len(latencies) if latencies else 0
                
                overhead_ms = avg_latency - baseline_latency
                overhead_pct = (overhead_ms / baseline_latency) * 100 if baseline_latency else 0
                
                status = "✓" if overhead_ms < 1000 else "⚠"  # Warn if > 1s overhead
                
                print(f"    Level {level}: {overhead_ms:+.0f}ms ({overhead_pct:+.1f}%) {status}")
        
        # Memory functionality check
        memory_results = [r for r in self.results if r.get("level") == 3]
        memory_echoes = sum(1 for r in memory_results if r.get("memory_echo"))
        
        print(f"\n  MEMORY FUNCTIONALITY (Level 3)")
        print(f"  " + "-"*35)
        print(f"    Total turns: {len(memory_results)}")
        print(f"    Memory echoes triggered: {memory_echoes}")
        print(f"    Echo rate: {(memory_echoes/len(memory_results)*100) if memory_results else 0:.1f}%")
        
        # Final verdict
        print("\n" + "="*70)
        total_success = sum(1 for r in self.results if r.get("success"))
        total = len(self.results)
        
        if total_success == total:
            print("  ✅ BENCHMARK PASSED - All requests successful")
        elif total_success >= total * 0.9:
            print(f"  ⚠️  BENCHMARK PARTIAL - {total_success}/{total} requests successful")
        else:
            print(f"  ❌ BENCHMARK FAILED - Only {total_success}/{total} requests successful")
        
        print("="*70 + "\n")


async def main():
    """Point d'entrée principal."""
    benchmark = E2EBenchmark()
    
    try:
        await benchmark.run_full_benchmark()
    finally:
        await benchmark.close()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## MISSION 4 : EXÉCUTION ET DOCUMENTATION

### 4.1 Commandes d'exécution

```bash
# 1. Vérifier que le serveur tourne
curl http://localhost:8000/health | jq .

# 2. Vérifier Ollama
curl http://localhost:11434/api/tags | jq .

# 3. Exécuter le benchmark E2E
cd /chemin/vers/lyra_clean
python tests/benchmarks/benchmark_e2e.py

# 4. Vérifier les résultats
ls -la benchmark_results/e2e_benchmark_*.csv
cat benchmark_results/e2e_benchmark_*_config.json
```

### 4.2 Résultats attendus

| Level | Latence Attendue | Consciousness | Memory |
|-------|------------------|---------------|--------|
| 0 | ~8-12s (baseline) | Non | Non |
| 1 | ~8-12s (+<100ms) | Oui | Non |
| 2 | ~8-12s (+<100ms) | Oui | Non |
| 3 | ~8-12s (+<500ms) | Oui | Oui (tours 2+) |

### 4.3 Créer le rapport final

Après exécution, créer `docs/phases/E2E_BENCHMARK_REPORT.md` avec :

1. **Configuration de test**
   - Modèle LLM utilisé
   - Nombre de prompts
   - Sessions testées

2. **Résultats par niveau**
   - Latence moyenne
   - Taux de succès
   - Overhead vs baseline

3. **Analyse mémoire (Level 3)**
   - Taux de recalls
   - Qualité des echoes
   - Performance embeddings

4. **Conclusions**
   - Overhead acceptable ?
   - Fonctionnalités validées ?
   - Recommandations

---

## 📁 STRUCTURE FINALE ATTENDUE

```
lyra_clean/
├── app/
│   ├── api/
│   │   ├── chat.py          # ✓ Intégration Level 3
│   │   └── sessions.py
│   ├── embeddings.py         # NOUVEAU - Helper embeddings
│   ├── main.py
│   ├── models.py
│   └── llm_client.py
├── services/
│   └── consciousness/
│       ├── __init__.py       # ✓ Exports complets
│       ├── metrics.py        # ✓ Level 1
│       ├── adaptation.py     # ✓ Level 2
│       └── memory.py         # ✓ Level 3
├── database/
│   ├── engine.py
│   └── schema.sql            # ✓ Tables semantic_memory + session_adjustments
├── tests/
│   └── benchmarks/
│       ├── benchmark_suite.py      # Phase 0
│       ├── test_phase_1.py
│       ├── benchmark_phase_1.py
│       ├── test_phase_2.py
│       ├── benchmark_phase_2.py
│       ├── test_phase_3.py
│       ├── benchmark_phase_3.py
│       └── benchmark_e2e.py        # NOUVEAU - E2E complet
├── benchmark_results/
│   ├── baseline_*.csv
│   ├── phase1_*.csv
│   ├── phase2_*.csv
│   ├── phase3_*.csv
│   └── e2e_benchmark_*.csv         # NOUVEAU
└── docs/
    └── phases/
        ├── PHASE_0_*.md
        ├── PHASE_1_*.md
        ├── PHASE_2_*.md
        ├── PHASE_3_*.md
        └── E2E_BENCHMARK_REPORT.md  # NOUVEAU
```

---

## ⚠️ POINTS DE VIGILANCE

1. **Timeout** : Les appels LLM peuvent prendre 8-15 secondes. Configurer timeout à 180s minimum.

2. **Embeddings** : S'assurer que `mxbai-embed-large` est installé dans Ollama :
   ```bash
   ollama pull mxbai-embed-large
   ```

3. **Mémoire Level 3** : Le premier tour d'une session n'aura jamais de `memory_echo` (rien à rappeler).

4. **Sessions uniques** : Chaque niveau utilise une session différente pour isolation.

5. **Base de données** : S'assurer que `ispace.db` contient les concepts/relations (1728+ concepts).

---

## ✅ CHECKLIST FINALE

- [ ] Schema SQL vérifié/complété
- [ ] `services/consciousness/__init__.py` exports OK
- [ ] `app/embeddings.py` créé (si manquant)
- [ ] Intégration `chat.py` Level 3 validée
- [ ] `benchmark_e2e.py` créé
- [ ] Benchmark exécuté avec succès
- [ ] Résultats CSV générés
- [ ] Rapport final créé
- [ ] Commit + tag version

---

**Fin du plan. Bonne exécution !** 🚀
