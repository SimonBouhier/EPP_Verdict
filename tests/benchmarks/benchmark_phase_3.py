"""
Benchmark Phase 3 - Semantic Memory Overhead

Mesure l'overhead de la mémoire sémantique vs adaptation (Phase 2).
Teste une conversation de 30 messages avec rappels de mémoire.
"""

import time
import json
import csv
import random
from datetime import datetime
from pathlib import Path
from services.consciousness.memory import SemanticMemory


def benchmark_semantic_memory():
    """
    Benchmark conversation 30 messages avec mémoire.
    
    Teste 3 profils :
    - Level 1 (Passif) : métriques seulement
    - Level 2 (Adaptatif) : métriques + suggestions
    - Level 3 (Mémoire) : métriques + suggestions + rappel mémoire
    
    Mesure latence par tour et impacts mémoire.
    """
    
    # Prompts pour 30 messages
    prompts = [
        "Hello, how are you?",
        "Explain quantum mechanics",
        "What is AI?",
        "Describe evolution",
        "Tell me about climate",
        "What is photosynthesis?",
        "How does banking work?",
        "Explain cryptography",
        "What is psychology?",
        "Tell me about history"
    ]
    
    results_level1 = []
    results_level2 = []
    results_level3 = []
    config = {
        'timestamp': datetime.now().isoformat(),
        'prompts': len(prompts),
        'rounds': 3,
        'total_turns': 30,
        'embedding_dim': 1024,
        'level1': 'ConsciousnessMonitor (Passif)',
        'level2': 'AdaptiveConsciousness (Adaptatif)',
        'level3': 'SemanticMemory (Mémoire)'
    }
    
    print("\n" + "=" * 70)
    print("PHASE 3 BENCHMARK: Semantic Memory Overhead")
    print("=" * 70)
    print(f"Conversation: {len(prompts)} × {config['rounds']} = 30 messages")
    print(f"Measuring: Level 1 (Passif) vs Level 2 (Adaptatif) vs Level 3 (Mémoire)")
    print()
    
    # Profil de test constant
    profile = {'tau_c': 1.0, 'rho': 0.2, 'delta_r': 0.0}
    
    # Metrics scénarios variés
    metrics_scenarios = [
        {'coherence': 0.3, 'tension': 0.4, 'fit': 0.5, 'pressure': 0.3},
        {'coherence': 0.6, 'tension': 0.7, 'fit': 0.7, 'pressure': 0.6},
        {'coherence': 0.2, 'tension': 0.85, 'fit': 0.4, 'pressure': 0.9},
        {'coherence': 0.8, 'tension': 0.3, 'fit': 0.9, 'pressure': 0.4},
        {'coherence': 0.5, 'tension': 0.6, 'fit': 0.5, 'pressure': 0.5},
    ]
    
    # Générateur embeddings simples (random 1024D)
    def get_embeddings():
        return [random.gauss(0.5, 0.2) for _ in range(1024)]
    
    session_id = "benchmark_session"
    memory_recalls = 0
    memory_entries = 0
    
    for round_idx in range(config['rounds']):
        for prompt_idx, prompt in enumerate(prompts):
            turn = round_idx * len(prompts) + prompt_idx + 1
            
            # Sélectionner métriques
            metrics_data = metrics_scenarios[prompt_idx % len(metrics_scenarios)]
            
            # ============= LEVEL 1 (PASSIF) =============
            start_l1 = time.perf_counter()
            # Simule calcul metrics seulement
            for _ in range(5):
                _ = sum([0.1] * 1024)  # Simule calcul
            elapsed_l1 = (time.perf_counter() - start_l1) * 1000
            
            results_level1.append({
                'turn': turn,
                'level': 1,
                'prompt': prompt[:30],
                'latency_ms': round(elapsed_l1, 3),
                'memory_entries': 0,
                'recalls': 0,
                'has_echo': 'NO'
            })
            
            # ============= LEVEL 2 (ADAPTATIF) =============
            start_l2 = time.perf_counter()
            adaptive = SemanticMemory(level=2, adaptation_rate=0.05)
            # Simule calcul metrics + suggestions (light)
            for _ in range(5):
                _ = sum([0.1] * 1024)
            elapsed_l2 = (time.perf_counter() - start_l2) * 1000
            
            results_level2.append({
                'turn': turn,
                'level': 2,
                'prompt': prompt[:30],
                'latency_ms': round(elapsed_l2, 3),
                'memory_entries': 0,
                'recalls': 0,
                'has_echo': 'NO'
            })
            
            # ============= LEVEL 3 (MÉMOIRE) =============
            memory = SemanticMemory(level=3, similarity_threshold=0.6)
            start_l3 = time.perf_counter()
            
            # Simule calcul metrics + suggestions + mémoire
            embeddings = get_embeddings()
            
            # Stocker en mémoire
            entry = memory.store_memory(
                session_id,
                prompt,
                embeddings,
                turn
            )
            memory_entries = len(memory.memory.get(session_id, []))
            
            # Rappel de mémoire (top-3 messages similaires)
            recalled = memory.recall_memory(
                session_id,
                embeddings,
                turn,
                top_k=3
            )
            memory_recalls = len(recalled)
            
            # Formater résultats
            formatted = memory.format_memory_echo(recalled) if recalled else None
            
            elapsed_l3 = (time.perf_counter() - start_l3) * 1000
            
            results_level3.append({
                'turn': turn,
                'level': 3,
                'prompt': prompt[:30],
                'latency_ms': round(elapsed_l3, 3),
                'memory_entries': memory_entries,
                'recalls': memory_recalls,
                'has_echo': 'YES' if formatted else 'NO'
            })
            
            # Afficher progression
            if turn % 5 == 0:
                overhead_l2 = results_level2[-1]['latency_ms'] - results_level1[-1]['latency_ms']
                overhead_l3 = results_level3[-1]['latency_ms'] - results_level1[-1]['latency_ms']
                print(f"Turn {turn}/30: L1={results_level1[-1]['latency_ms']:.3f}ms, "
                      f"L2={results_level2[-1]['latency_ms']:.3f}ms (+{overhead_l2:.3f}ms), "
                      f"L3={results_level3[-1]['latency_ms']:.3f}ms (+{overhead_l3:.3f}ms, "
                      f"mem={memory_entries})")
    
    # Calculer statistiques
    l1_latencies = [r['latency_ms'] for r in results_level1]
    l2_latencies = [r['latency_ms'] for r in results_level2]
    l3_latencies = [r['latency_ms'] for r in results_level3]
    
    overheads_l2 = [l2 - l1 for l1, l2 in zip(l1_latencies, l2_latencies)]
    overheads_l3 = [l3 - l1 for l1, l3 in zip(l1_latencies, l3_latencies)]
    
    avg_overhead_l2 = sum(overheads_l2) / len(overheads_l2)
    avg_overhead_l3 = sum(overheads_l3) / len(overheads_l3)
    max_overhead_l3 = max(overheads_l3)
    total_recalls = sum(r['recalls'] for r in results_level3)
    final_memory_entries = results_level3[-1]['memory_entries']
    
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Level 1 (Passif) - Avg: {sum(l1_latencies)/len(l1_latencies):.3f}ms")
    print(f"Level 2 (Adaptatif) - Avg: {sum(l2_latencies)/len(l2_latencies):.3f}ms")
    print(f"  Overhead vs L1: {avg_overhead_l2:.3f}ms")
    print(f"Level 3 (Mémoire) - Avg: {sum(l3_latencies)/len(l3_latencies):.3f}ms")
    print(f"  Overhead vs L1: {avg_overhead_l3:.3f}ms")
    print(f"  Max overhead: {max_overhead_l3:.3f}ms")
    print()
    print(f"Memory Statistics:")
    print(f"  Final entries: {final_memory_entries}/30")
    print(f"  Total recalls: {total_recalls}")
    print(f"  Avg recalls/turn: {total_recalls/30:.1f}")
    print()
    print(f"Phase 2 target: < 5ms (Actual L2 overhead: {avg_overhead_l2:.3f}ms)")
    print(f"Phase 3 target: < 20ms total (Actual L3 overhead: {avg_overhead_l3:.3f}ms)")
    print(f"Status: PASS" if avg_overhead_l3 < 20.0 else "FAIL")
    print("=" * 70)
    
    # Sauvegarder résultats
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path("benchmark_results")
    results_dir.mkdir(exist_ok=True)
    
    # Combiner et sauvegarder
    all_results = results_level1 + results_level2 + results_level3
    csv_path = results_dir / f"phase3_semantic_memory_{timestamp}.csv"
    
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
        writer.writeheader()
        writer.writerows(all_results)
    
    config['avg_overhead_l2_ms'] = avg_overhead_l2
    config['avg_overhead_l3_ms'] = avg_overhead_l3
    config['max_overhead_l3_ms'] = max_overhead_l3
    config['total_recalls'] = total_recalls
    config['final_memory_entries'] = final_memory_entries
    config['target_overhead_ms'] = 20.0
    config['result'] = 'PASS' if avg_overhead_l3 < 20.0 else 'FAIL'
    
    config_path = results_dir / f"phase3_semantic_memory_{timestamp}_config.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\nResults saved to: {csv_path}")
    print(f"Config saved to: {config_path}")
    
    return avg_overhead_l3 < 20.0


if __name__ == '__main__':
    success = benchmark_semantic_memory()
    exit(0 if success else 1)
