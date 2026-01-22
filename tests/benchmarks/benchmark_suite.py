"""
Suite de benchmarking pour Lyra Clean
Permet de comparer differentes configurations
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
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
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
        """Verifie que le serveur est accessible"""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.json()["status"] == "healthy"
        except Exception as e:
            print(f"[ERROR] Server not accessible: {e}")
            return False
    
    async def benchmark_latency_basic(
        self,
        n_requests: int = 50,
        prompt: str = "What is entropy?"
    ) -> pd.DataFrame:
        """
        Benchmark 1 : Latence de base (sans complexite)
        
        Mesure :
        - Latence totale
        - Breakdown par composant
        - Stabilite (variance)
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
                print(f"  [ERROR] Request {i} failed: {e}")
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
        print(f"\n[RESULTS]:")
        print(f"  Total latency: {df['total_latency_ms'].mean():.2f} +/- {df['total_latency_ms'].std():.2f} ms")
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
        - Nombre de concepts injectes
        - Impact sur qualite (subjectif)
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
                print(f"    [ERROR] Without context failed: {e}")
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
                print(f"    [ERROR] With context failed: {e}")
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
        print(f"\n[RESULTS]:")
        print(f"  Average overhead: {df['overhead_ms'].mean():.2f} ms ({df['overhead_percent'].mean():.1f}%)")
        print(f"  Average concepts injected: {df['concepts_injected'].mean():.1f}")
        
        return df
    
    async def benchmark_profiles(
        self,
        prompts: List[str] = None
    ) -> pd.DataFrame:
        """
        Benchmark 3 : Comparaison des profils Bezier
        
        Compare tous les profils sur memes prompts
        
        Mesure :
        - Latence
        - Longueur reponse
        - Parametres physiques (tau_c, rho)
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
        print(f"{len(profiles)} profiles x {len(prompts)} prompts = {len(profiles)*len(prompts)} tests")
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
                    print(f"    [ERROR] Failed: {e}")
        
        df = pd.DataFrame(results)
        
        # Statistiques par profil
        print(f"\n[RESULTS] by profile:")
        for profile in profiles:
            profile_df = df[df["profile"] == profile]
            if len(profile_df) > 0:
                print(f"\n  {profile}:")
                print(f"    Avg latency: {profile_df['latency_ms'].mean():.2f} ms")
                print(f"    Avg response length: {profile_df['response_length'].mean():.0f} words")
                print(f"    Avg tau_c: {profile_df['tau_c'].mean():.2f}")
        
        return df
    
    def save_results(self, df: pd.DataFrame, name: str, config: dict = None):
        """Sauvegarde resultats avec metadonnees"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Sauvegarder CSV
        csv_path = self.results_dir / f"{name}_{timestamp}.csv"
        df.to_csv(csv_path, index=False)
        print(f"\n[SAVE] Results: {csv_path}")
        
        # Sauvegarder config
        if config:
            config_path = self.results_dir / f"{name}_{timestamp}_config.json"
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"[SAVE] Config: {config_path}")
    
    async def run_baseline_suite(self):
        """Execute suite complete baseline"""
        print("\n" + "="*60)
        print("LYRA BASELINE BENCHMARK SUITE")
        print("="*60)
        
        # Verifier serveur
        if not await self.check_server_health():
            print("[ERROR] Server not healthy, aborting")
            return
        
        print("[OK] Server healthy, starting benchmarks...\n")
        
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
        print("BASELINE SUITE COMPLETE")
        print("="*60)
        print(f"\nResults saved in: {self.results_dir}/")


async def main():
    """Point d'entree principal"""
    async with LyraBenchmark() as benchmark:
        await benchmark.run_baseline_suite()


if __name__ == "__main__":
    asyncio.run(main())
