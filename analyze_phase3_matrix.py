"""
PHASE 3 MATRIX ANALYSIS
=======================
Compare: Raw Ollama vs Lyra (Balanced, Creative, Memory)

Metrics:
- Latency (ms): Response time per config
- Coherence: Semantic alignment between query and response
- Domain performance: Which domains benefit most from Lyra?
- Profile effectiveness: Balanced vs Creative vs Memory
"""
import json
import numpy as np
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Find the latest benchmark results
benchmark_dir = Path("benchmark_results")
matrix_dirs = sorted(benchmark_dir.glob("phase3_matrix_*"))
if not matrix_dirs:
    print("❌ No Phase 3 matrix results found!")
    exit(1)

latest_dir = matrix_dirs[-1]
results_file = latest_dir / "matrix_results.jsonl"

if not results_file.exists():
    print(f"❌ Results file not found: {results_file}")
    exit(1)

print(f"📊 Analyzing: {results_file}")
print("=" * 80)

# Parse results
results = []
with open(results_file, "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            results.append(json.loads(line))

# Organize by config and domain
by_config = defaultdict(list)
by_domain = defaultdict(lambda: defaultdict(list))

for r in results:
    config_id = r["config_id"]
    domain = r["domain"]
    by_config[config_id].append(r)
    by_domain[domain][config_id].append(r)

# ============================================================================
# ANALYSIS 1: Latency Comparison
# ============================================================================
print("\n📈 LATENCY ANALYSIS (ms)")
print("-" * 80)

latencies = {}
for config_id in sorted(by_config.keys()):
    lats = [r["latency_ms"] for r in by_config[config_id]]
    latencies[config_id] = {
        "mean": np.mean(lats),
        "median": np.median(lats),
        "std": np.std(lats),
        "min": np.min(lats),
        "max": np.max(lats)
    }

baseline_latency = latencies["raw_gpt"]["mean"]
print(f"\n{'Config':<20} {'Mean (ms)':>12} {'Median':>10} {'Std':>10} {'Delta vs Baseline':>20}")
print("-" * 80)

for config_id in sorted(by_config.keys()):
    stats = latencies[config_id]
    config_name = {"raw_gpt": "Baseline (Raw)", "lyra_balanced": "Lyra (Balanced)", 
                   "lyra_creative": "Lyra (Creative)", "lyra_memory": "Lyra (Memory)"}.get(config_id, config_id)
    delta = stats["mean"] - baseline_latency
    delta_pct = (delta / baseline_latency) * 100
    delta_str = f"{delta:+.0f}ms ({delta_pct:+.1f}%)"
    print(f"{config_name:<20} {stats['mean']:>12.0f} {stats['median']:>10.0f} {stats['std']:>10.1f} {delta_str:>20}")

# ============================================================================
# ANALYSIS 2: Coherence Comparison (Semantic Quality)
# ============================================================================
print("\n\n🎯 COHERENCE ANALYSIS (Semantic Alignment)")
print("-" * 80)

coherences = {}
for config_id in sorted(by_config.keys()):
    cohs = [r["coherence"] for r in by_config[config_id]]
    coherences[config_id] = {
        "mean": np.mean(cohs),
        "median": np.median(cohs),
        "std": np.std(cohs),
        "min": np.min(cohs),
        "max": np.max(cohs)
    }

baseline_coherence = coherences["raw_gpt"]["mean"]
print(f"\n{'Config':<20} {'Mean':>8} {'Median':>8} {'Std':>8} {'Min':>8} {'Max':>8} {'Delta vs Baseline':>15}")
print("-" * 80)

for config_id in sorted(by_config.keys()):
    stats = coherences[config_id]
    config_name = {"raw_gpt": "Baseline (Raw)", "lyra_balanced": "Lyra (Balanced)", 
                   "lyra_creative": "Lyra (Creative)", "lyra_memory": "Lyra (Memory)"}.get(config_id, config_id)
    delta = stats["mean"] - baseline_coherence
    print(f"{config_name:<20} {stats['mean']:>8.3f} {stats['median']:>8.3f} {stats['std']:>8.3f} {stats['min']:>8.3f} {stats['max']:>8.3f} {delta:+.4f}")

# ============================================================================
# ANALYSIS 3: Domain Performance
# ============================================================================
print("\n\n🎨 DOMAIN-SPECIFIC PERFORMANCE")
print("-" * 80)

for domain in sorted(by_domain.keys()):
    print(f"\n{domain.upper()}")
    print("  " + "-" * 76)
    domain_data = by_domain[domain]
    
    for config_id in sorted(domain_data.keys()):
        config_name = {"raw_gpt": "Baseline", "lyra_balanced": "Balanced", 
                       "lyra_creative": "Creative", "lyra_memory": "Memory"}.get(config_id, config_id)
        coh_list = [r["coherence"] for r in domain_data[config_id]]
        lat_list = [r["latency_ms"] for r in domain_data[config_id]]
        
        coh_mean = np.mean(coh_list)
        lat_mean = np.mean(lat_list)
        
        print(f"  {config_name:<15} Coherence: {coh_mean:.3f}  |  Latency: {lat_mean:.0f}ms")

# ============================================================================
# ANALYSIS 4: Profile Effectiveness (Lyra vs Baseline)
# ============================================================================
print("\n\n⚡ PROFILE EFFECTIVENESS (vs Baseline)")
print("-" * 80)

lyra_configs = {
    "lyra_balanced": "Balanced",
    "lyra_creative": "Creative",
    "lyra_memory": "Memory"
}

print(f"\n{'Profile':<15} {'Latency Delta':>20} {'Coherence Delta':>20} {'Summary':>20}")
print("-" * 80)

for config_id, profile_name in lyra_configs.items():
    lat_delta = latencies[config_id]["mean"] - baseline_latency
    lat_delta_pct = (lat_delta / baseline_latency) * 100
    coh_delta = coherences[config_id]["mean"] - baseline_coherence
    
    # Determine if it's an improvement
    lat_status = "✓ FASTER" if lat_delta < 0 else f"✗ SLOWER +{lat_delta:.0f}ms"
    coh_status = "✓ BETTER" if coh_delta > 0 else f"✗ WORSE {coh_delta:.4f}"
    
    summary = "🚀 Optimal" if (lat_delta < 500 and coh_delta > 0) else "⚠️ Tradeoff"
    
    print(f"{profile_name:<15} {lat_status:>20} {coh_status:>20} {summary:>20}")

# ============================================================================
# ANALYSIS 5: Response Quality Rankings
# ============================================================================
print("\n\n🏆 TOP 5 HIGHEST COHERENCE RESPONSES")
print("-" * 80)

sorted_results = sorted(results, key=lambda x: x["coherence"], reverse=True)
for i, r in enumerate(sorted_results[:5], 1):
    config_name = {"raw_gpt": "Baseline", "lyra_balanced": "Balanced", 
                   "lyra_creative": "Creative", "lyra_memory": "Memory"}.get(r["config_id"], r["config_id"])
    print(f"{i}. [{config_name:>15}] {r['domain']:>12} | Coh: {r['coherence']:.4f} | {r['prompt'][:50]}")

print("\n\n🔻 TOP 5 LOWEST COHERENCE RESPONSES")
print("-" * 80)

sorted_results = sorted(results, key=lambda x: x["coherence"])
for i, r in enumerate(sorted_results[:5], 1):
    config_name = {"raw_gpt": "Baseline", "lyra_balanced": "Balanced", 
                   "lyra_creative": "Creative", "lyra_memory": "Memory"}.get(r["config_id"], r["config_id"])
    print(f"{i}. [{config_name:>15}] {r['domain']:>12} | Coh: {r['coherence']:.4f} | {r['prompt'][:50]}")

# ============================================================================
# SUMMARY STATISTICS
# ============================================================================
print("\n\n📋 SUMMARY STATISTICS")
print("=" * 80)

print(f"\nTotal Requests: {len(results)}")
print(f"Configurations: {len(by_config)}")
print(f"Domains: {len(by_domain)}")
print(f"Prompts per Config: {len(by_config['raw_gpt'])}")

print(f"\nLatency Range:")
print(f"  Baseline: {latencies['raw_gpt']['mean']:.0f}ms (σ={latencies['raw_gpt']['std']:.1f})")
print(f"  Lyra Balanced: {latencies['lyra_balanced']['mean']:.0f}ms (σ={latencies['lyra_balanced']['std']:.1f})")
print(f"  Lyra Creative: {latencies['lyra_creative']['mean']:.0f}ms (σ={latencies['lyra_creative']['std']:.1f})")
print(f"  Lyra Memory: {latencies['lyra_memory']['mean']:.0f}ms (σ={latencies['lyra_memory']['std']:.1f})")

print(f"\nCoherence Range:")
print(f"  Baseline: {coherences['raw_gpt']['mean']:.4f} ± {coherences['raw_gpt']['std']:.4f}")
print(f"  Lyra Balanced: {coherences['lyra_balanced']['mean']:.4f} ± {coherences['lyra_balanced']['std']:.4f}")
print(f"  Lyra Creative: {coherences['lyra_creative']['mean']:.4f} ± {coherences['lyra_creative']['std']:.4f}")
print(f"  Lyra Memory: {coherences['lyra_memory']['mean']:.4f} ± {coherences['lyra_memory']['std']:.4f}")

print("\n" + "=" * 80)
print("✅ Analysis complete!")
print("=" * 80)
