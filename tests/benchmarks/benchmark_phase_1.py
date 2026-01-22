"""
Benchmark Phase 1 : Impact metriques passives
Compare overhead level 0 vs level 1
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

# Ajouter chemin projet
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.benchmarks.benchmark_suite import LyraBenchmark


async def benchmark_consciousness_overhead():
    """Compare overhead level 0 vs level 1"""
    
    async with LyraBenchmark() as benchmark:
        print("\n" + "="*60)
        print("PHASE 1 BENCHMARK: Consciousness Overhead")
        print("="*60)
        
        prompts = [
            "What is entropy?",
            "Explain quantum mechanics",
            "How does photosynthesis work?",
            "What is machine learning?",
            "Describe the water cycle"
        ]
        
        results = []
        
        for idx, prompt in enumerate(prompts):
            print(f"\n[{idx+1}/{len(prompts)}] Testing: {prompt[:40]}...")
            
            # Level 0 (baseline)
            try:
                response_0 = await benchmark.client.post(
                    f"{benchmark.base_url}/chat/message",
                    json={
                        "text": prompt,
                        "consciousness_level": 0
                    }
                )
                data_0 = response_0.json()
                latency_0 = data_0["latency"]["total"]
            except Exception as e:
                print(f"  [ERROR] Level 0 failed: {e}")
                continue
            
            # Level 1 (passive metrics)
            try:
                response_1 = await benchmark.client.post(
                    f"{benchmark.base_url}/chat/message",
                    json={
                        "text": prompt,
                        "consciousness_level": 1
                    }
                )
                data_1 = response_1.json()
                latency_1 = data_1["latency"]["total"]
            except Exception as e:
                print(f"  [ERROR] Level 1 failed: {e}")
                continue
            
            overhead_ms = latency_1 - latency_0
            overhead_pct = (overhead_ms / latency_0) * 100 if latency_0 > 0 else 0
            
            result = {
                "prompt": prompt[:30],
                "level_0_latency_ms": latency_0,
                "level_1_latency_ms": latency_1,
                "overhead_ms": overhead_ms,
                "overhead_percent": overhead_pct,
                "coherence": data_1.get("consciousness", {}).get("coherence"),
                "tension": data_1.get("consciousness", {}).get("tension"),
                "fit": data_1.get("consciousness", {}).get("fit"),
                "pressure": data_1.get("consciousness", {}).get("pressure")
            }
            
            results.append(result)
            
            print(f"  Level 0: {latency_0:.2f}ms")
            print(f"  Level 1: {latency_1:.2f}ms")
            print(f"  Overhead: +{overhead_ms:.2f}ms ({overhead_pct:.2f}%)")
            if result["coherence"] is not None:
                print(f"  Metrics: coh={result['coherence']:.2f}, ten={result['tension']:.2f}, fit={result['fit']:.2f}, pre={result['pressure']:.2f}")
        
        if not results:
            print("\n[ERROR] No successful results!")
            return None
        
        df = pd.DataFrame(results)
        
        print(f"\n{'='*60}")
        print(f"SUMMARY:")
        print(f"{'='*60}")
        print(f"Requests completed: {len(df)}/{len(prompts)}")
        print(f"Average overhead: {df['overhead_ms'].mean():.2f}ms ({df['overhead_percent'].mean():.2f}%)")
        print(f"Max overhead: {df['overhead_ms'].max():.2f}ms")
        print(f"Std dev: {df['overhead_ms'].std():.2f}ms")
        print(f"\nTarget: < 5ms")
        
        if df['overhead_ms'].mean() < 5.0:
            print(f"RESULT: PASS - Overhead acceptable [avg={df['overhead_ms'].mean():.2f}ms]")
        else:
            print(f"RESULT: FAIL - Overhead too high [avg={df['overhead_ms'].mean():.2f}ms > 5ms]")
        
        benchmark.save_results(df, "phase1_consciousness_overhead", {
            "phase": 1,
            "test": "consciousness_overhead",
            "prompts": prompts,
            "target_overhead_ms": 5.0
        })
        
        return df


async def main():
    await benchmark_consciousness_overhead()


if __name__ == "__main__":
    asyncio.run(main())
