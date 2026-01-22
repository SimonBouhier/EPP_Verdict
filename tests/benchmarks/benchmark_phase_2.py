"""
Benchmark Phase 2 - Adaptive Consciousness Overhead

Mesure l'overhead de l'adaptation progressive vs métriques passives (Phase 1).
Teste une conversation de 30 messages pour observer adjustments triggérés.
"""

import time
import json
import csv
from datetime import datetime
from pathlib import Path
from services.consciousness.metrics import ConsciousnessMetrics, ConsciousnessMonitor
from services.consciousness.adaptation import AdaptiveConsciousness


def benchmark_adaptive_consciousness():
    """
    Benchmark conversation 30 messages avec adaptation vs sans.
    
    Teste 2 profils :
    - Level 1 (Passif) : métriques seulement
    - Level 2 (Adaptatif) : métriques + suggestions
    
    Mesure latence par tour et nombre d'adjustments.
    """
    
    # Prompts variés pour stimuler différentes métriques
    prompts = [
        "Hello, how are you?",
        "Explain quantum mechanics briefly",
        "What is your favorite color?",
        "Describe the water cycle in detail",
        "Tell a short joke",
        "What time is it?",
        "Explain machine learning to a 5-year-old",
        "List 5 benefits of exercise",
        "What is your name?",
        "How does photosynthesis work?"
    ]
    
    results_level1 = []
    results_level2 = []
    config = {
        'timestamp': datetime.now().isoformat(),
        'prompts': len(prompts),
        'rounds': 3,  # 30 messages total = 3 rounds × 10 prompts
        'level1': 'ConsciousnessMonitor (Passif)',
        'level2': 'AdaptiveConsciousness (Adaptatif)'
    }
    
    print("\n" + "=" * 70)
    print("PHASE 2 BENCHMARK: Adaptive Consciousness Overhead")
    print("=" * 70)
    print(f"Conversation: {len(prompts)} × {config['rounds']} = 30 messages")
    print(f"Measuring: Level 1 (Passif) vs Level 2 (Adaptatif)")
    print()
    
    # Profil de test constant
    profile = {'tau_c': 1.0, 'rho': 0.2, 'delta_r': 0.0}
    
    # Scenarios de contexte variés pour stimuler différentes métriques
    context_scenarios = [
        {'weight': 2.0, 'concepts': 3, 'response_len': 100},
        {'weight': 4.0, 'concepts': 5, 'response_len': 130},
        {'weight': 6.0, 'concepts': 7, 'response_len': 160},
        {'weight': 8.0, 'concepts': 9, 'response_len': 190},
        {'weight': 10.0, 'concepts': 11, 'response_len': 220},
        {'weight': 7.0, 'concepts': 8, 'response_len': 175},
        {'weight': 3.0, 'concepts': 4, 'response_len': 120},
        {'weight': 9.0, 'concepts': 10, 'response_len': 200},
        {'weight': 5.0, 'concepts': 6, 'response_len': 150},
        {'weight': 1.5, 'concepts': 2, 'response_len': 90},
    ]
    
    adjustments_triggered = 0
    
    for round_idx in range(config['rounds']):
        for prompt_idx, prompt in enumerate(prompts):
            turn = round_idx * len(prompts) + prompt_idx + 1
            
            # Sélectionner scénario contexte pour ce tour
            context_data = context_scenarios[prompt_idx % len(context_scenarios)]
            
            # ============= LEVEL 1 (PASSIF) =============
            monitor_l1 = ConsciousnessMonitor(level=1)
            start_l1 = time.perf_counter()
            result_l1 = monitor_l1.compute_metrics(
                context_weight=context_data['weight'],
                num_concepts=context_data['concepts'],
                physics_state=profile,
                response_length=context_data['response_len']
            )
            elapsed_l1 = (time.perf_counter() - start_l1) * 1000  # ms
            
            results_level1.append({
                'turn': turn,
                'level': 1,
                'prompt': prompt[:30],
                'latency_ms': round(elapsed_l1, 3),
                'coherence': result_l1.coherence if result_l1 else 0,
                'tension': result_l1.tension if result_l1 else 0,
                'fit': result_l1.fit if result_l1 else 0,
                'pressure': result_l1.pressure if result_l1 else 0,
                'stability': result_l1.stability_score if result_l1 else 0,
                'adjustments': None
            })
            
            # ============= LEVEL 2 (ADAPTATIF) =============
            adaptive = AdaptiveConsciousness(level=2, adaptation_rate=0.05)
            start_l2 = time.perf_counter()
            
            # Compute metrics
            result_l2 = adaptive.compute_metrics(
                context_weight=context_data['weight'],
                num_concepts=context_data['concepts'],
                physics_state=profile,
                response_length=context_data['response_len']
            )
            
            # Suggest adjustments
            adjustments = None
            if result_l2:
                adjustments = adaptive.suggest_adjustments(
                    result_l2,
                    profile,
                    session_length=turn
                )
                if adjustments:
                    adjustments_triggered += 1
            
            elapsed_l2 = (time.perf_counter() - start_l2) * 1000  # ms
            
            results_level2.append({
                'turn': turn,
                'level': 2,
                'prompt': prompt[:30],
                'latency_ms': round(elapsed_l2, 3),
                'coherence': result_l2.coherence if result_l2 else 0,
                'tension': result_l2.tension if result_l2 else 0,
                'fit': result_l2.fit if result_l2 else 0,
                'pressure': result_l2.pressure if result_l2 else 0,
                'stability': result_l2.stability_score if result_l2 else 0,
                'adjustments': 'YES' if adjustments else 'NO'
            })
            
            # Print progress
            if turn % 5 == 0:
                overhead = results_level2[-1]['latency_ms'] - results_level1[-1]['latency_ms']
                print(f"Turn {turn}/30: L1={results_level1[-1]['latency_ms']:.2f}ms, "
                      f"L2={results_level2[-1]['latency_ms']:.2f}ms, "
                      f"Overhead={overhead:.2f}ms")
    
    # Calculer statistiques
    l1_latencies = [r['latency_ms'] for r in results_level1]
    l2_latencies = [r['latency_ms'] for r in results_level2]
    overheads = [l2 - l1 for l1, l2 in zip(l1_latencies, l2_latencies)]
    
    avg_overhead = sum(overheads) / len(overheads)
    max_overhead = max(overheads)
    min_overhead = min(overheads)
    
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Level 1 (Passif) - Avg latency: {sum(l1_latencies)/len(l1_latencies):.2f}ms")
    print(f"Level 2 (Adaptatif) - Avg latency: {sum(l2_latencies)/len(l2_latencies):.2f}ms")
    print(f"Average overhead: {avg_overhead:.2f}ms")
    print(f"Max overhead: {max_overhead:.2f}ms")
    print(f"Min overhead: {min_overhead:.2f}ms")
    print(f"Adjustments triggered: {adjustments_triggered}/30 turns")
    print()
    print(f"Target overhead: < 5ms")
    print(f"Status: {'PASS' if avg_overhead < 5.0 else 'FAIL'}")
    print("=" * 70)
    
    # Sauvegarder résultats
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path("benchmark_results")
    results_dir.mkdir(exist_ok=True)
    
    # Combiner et sauvegarder
    all_results = results_level1 + results_level2
    csv_path = results_dir / f"phase2_adaptive_overhead_{timestamp}.csv"
    
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
        writer.writeheader()
        writer.writerows(all_results)
    
    config['avg_overhead_ms'] = avg_overhead
    config['max_overhead_ms'] = max_overhead
    config['adjustments_triggered'] = adjustments_triggered
    config['target_overhead_ms'] = 5.0
    config['result'] = 'PASS' if avg_overhead < 5.0 else 'FAIL'
    
    config_path = results_dir / f"phase2_adaptive_overhead_{timestamp}_config.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\nResults saved to: {csv_path}")
    print(f"Config saved to: {config_path}")
    
    return avg_overhead < 5.0


if __name__ == '__main__':
    success = benchmark_adaptive_consciousness()
    exit(0 if success else 1)
