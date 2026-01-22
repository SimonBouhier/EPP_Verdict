"""
LYRA CLEAN - BENCHMARK END-TO-END
==================================

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
