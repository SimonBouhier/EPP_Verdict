"""
Benchmark Phase 2 AVEC ARCHIVAGE COMPLET
=========================================

Version améliorée qui archive :
- Réponses brutes du modèle (simulées ici, réelles en production)
- Embeddings query/response
- Toutes les métriques
- Contexte d'exécution
"""

import time
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
import uuid

from services.consciousness.metrics import ConsciousnessMonitor
from services.consciousness.adaptation import AdaptiveConsciousness
from tests.benchmarks.archive import BenchmarkArchive


def simulate_llm_response(prompt: str, response_length: int = 150) -> Dict[str, str]:
    """
    Simule une réponse LLM.
    En production, ce serait un vrai appel Ollama.
    """
    base_response = f"Response to '{prompt[:30]}...': " + \
                   "This is a comprehensive answer that addresses the key points. " * 5
    
    return {
        'text': base_response[:response_length],
        'model': 'gpt-oss:20b',
        'tokens_prompt': len(prompt.split()),
        'tokens_response': len(base_response.split()[:response_length // 5])
    }


def simulate_embeddings(text: str, dim: int = 1024) -> List[float]:
    """
    Simule des embeddings 1024D.
    En production, ce serait un appel mxbai-embed-large via Ollama.
    """
    import hashlib
    import math
    
    # Hash déterministe du texte
    hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
    
    # Générer embeddings pseudo-aléatoires mais déterministes
    embeddings = []
    for i in range(dim):
        val = math.sin((hash_val + i) / 1000.0) * math.cos((hash_val + i) / 500.0)
        embeddings.append(val)
    
    # Normalisation L2
    norm = sum(e*e for e in embeddings) ** 0.5
    return [e / (norm + 1e-8) for e in embeddings]


def benchmark_phase2_archived():
    """
    Benchmark Phase 2 avec archivage complet.
    
    Scenarios variés de contexte pour tester différentes métriques.
    Chaque message est archivé avec :
    - Query + Response textes
    - Embeddings 1024D
    - Métriques calculées
    - Contexte d'exécution
    """
    
    # Initialiser archive
    archive = BenchmarkArchive()
    run_id = f"phase2_archived_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Configuration du run
    config = {
        'type': 'phase2_adaptive_archived',
        'prompts': 10,
        'rounds': 3,
        'total_messages': 30,
        'archive_enabled': True,
        'embeddings_dim': 1024
    }
    
    archive.create_run(run_id, 'phase2_adaptive', config)
    
    # Prompts
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
    
    # Scenarios contexte variés
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
    
    profile = {'tau_c': 1.0, 'rho': 0.2, 'delta_r': 0.0}
    results_l1 = []
    results_l2 = []
    
    print("\n" + "=" * 70)
    print("PHASE 2 BENCHMARK WITH COMPLETE ARCHIVING")
    print("=" * 70)
    print(f"Run ID: {run_id}")
    print(f"Total messages: 30 (3 rounds × 10 prompts)")
    print(f"Archiving: Query + Response + Embeddings (1024D) + Metrics + Context")
    print()
    
    archived_count = 0
    
    for round_idx in range(config['rounds']):
        for prompt_idx, prompt in enumerate(prompts):
            turn = round_idx * len(prompts) + prompt_idx + 1
            context_data = context_scenarios[prompt_idx % len(context_scenarios)]
            
            # ============= GENERATE LLM RESPONSE =============
            llm_response = simulate_llm_response(prompt, context_data['response_len'])
            response_text = llm_response['text']
            
            # ============= GENERATE EMBEDDINGS =============
            query_emb = simulate_embeddings(prompt, dim=1024)
            response_emb = simulate_embeddings(response_text, dim=1024)
            
            # ============= LEVEL 1 (PASSIF) =============
            monitor_l1 = ConsciousnessMonitor(level=1)
            start_l1 = time.perf_counter()
            result_l1 = monitor_l1.compute_metrics(
                context_weight=context_data['weight'],
                num_concepts=context_data['concepts'],
                physics_state=profile,
                response_length=context_data['response_len']
            )
            elapsed_l1 = (time.perf_counter() - start_l1) * 1000
            
            # Archive Level 1 message
            msg_id_l1 = archive.archive_message(
                run_id=run_id,
                turn_number=turn,
                level=1,
                query_text=prompt,
                query_embeddings=query_emb,
                response_text=response_text,
                response_embeddings=response_emb,
                latency_ms=elapsed_l1,
                tokens={
                    'prompt': llm_response['tokens_prompt'],
                    'response': llm_response['tokens_response'],
                    'total': llm_response['tokens_prompt'] + llm_response['tokens_response']
                }
            )
            
            # Archive Level 1 metrics
            archive.archive_metrics(
                msg_id=msg_id_l1,
                coherence=result_l1.coherence if result_l1 else 0,
                tension=result_l1.tension if result_l1 else 0,
                fit=result_l1.fit if result_l1 else 0,
                pressure=result_l1.pressure if result_l1 else 0,
                stability=result_l1.stability_score if result_l1 else 0
            )
            
            # Archive Level 1 context
            archive.archive_context(
                msg_id=msg_id_l1,
                concepts_injected=[f"concept_{i}" for i in range(context_data['concepts'])],
                graph_weight=context_data['weight'],
                session_length=turn,
                profile_used='balanced',
                llm_model='gpt-oss:20b'
            )
            
            results_l1.append({
                'turn': turn,
                'level': 1,
                'prompt': prompt[:30],
                'latency_ms': round(elapsed_l1, 3),
                'msg_id': msg_id_l1,
                'coherence': result_l1.coherence if result_l1 else 0,
                'tension': result_l1.tension if result_l1 else 0,
                'fit': result_l1.fit if result_l1 else 0,
                'pressure': result_l1.pressure if result_l1 else 0,
                'stability': result_l1.stability_score if result_l1 else 0,
            })
            
            # ============= LEVEL 2 (ADAPTATIF) =============
            adaptive = AdaptiveConsciousness(level=2, adaptation_rate=0.05)
            start_l2 = time.perf_counter()
            result_l2 = adaptive.compute_metrics(
                context_weight=context_data['weight'],
                num_concepts=context_data['concepts'],
                physics_state=profile,
                response_length=context_data['response_len']
            )
            
            adjustments = None
            if result_l2:
                adjustments = adaptive.suggest_adjustments(
                    result_l2,
                    profile,
                    session_length=turn
                )
            
            elapsed_l2 = (time.perf_counter() - start_l2) * 1000
            
            # Archive Level 2 message
            msg_id_l2 = archive.archive_message(
                run_id=run_id,
                turn_number=turn,
                level=2,
                query_text=prompt,
                query_embeddings=query_emb,
                response_text=response_text,
                response_embeddings=response_emb,
                latency_ms=elapsed_l2,
                tokens={
                    'prompt': llm_response['tokens_prompt'],
                    'response': llm_response['tokens_response'],
                    'total': llm_response['tokens_prompt'] + llm_response['tokens_response']
                }
            )
            
            # Archive Level 2 metrics
            archive.archive_metrics(
                msg_id=msg_id_l2,
                coherence=result_l2.coherence if result_l2 else 0,
                tension=result_l2.tension if result_l2 else 0,
                fit=result_l2.fit if result_l2 else 0,
                pressure=result_l2.pressure if result_l2 else 0,
                stability=result_l2.stability_score if result_l2 else 0,
                adjustments_triggered=adjustments is not None
            )
            
            # Archive Level 2 context
            archive.archive_context(
                msg_id=msg_id_l2,
                concepts_injected=[f"concept_{i}" for i in range(context_data['concepts'])],
                graph_weight=context_data['weight'],
                session_length=turn,
                profile_used='balanced',
                llm_model='gpt-oss:20b'
            )
            
            results_l2.append({
                'turn': turn,
                'level': 2,
                'prompt': prompt[:30],
                'latency_ms': round(elapsed_l2, 3),
                'msg_id': msg_id_l2,
                'coherence': result_l2.coherence if result_l2 else 0,
                'tension': result_l2.tension if result_l2 else 0,
                'fit': result_l2.fit if result_l2 else 0,
                'pressure': result_l2.pressure if result_l2 else 0,
                'stability': result_l2.stability_score if result_l2 else 0,
                'adjustments': 'YES' if adjustments else 'NO'
            })
            
            archived_count += 2
            
            # Progress
            if turn % 5 == 0:
                overhead = results_l2[-1]['latency_ms'] - results_l1[-1]['latency_ms']
                print(f"Turn {turn:2d}/30: L1={results_l1[-1]['latency_ms']:6.2f}ms, "
                      f"L2={results_l2[-1]['latency_ms']:6.2f}ms, "
                      f"Overhead={overhead:6.2f}ms, Archived: {archived_count} messages")
    
    # ============= FINALIZE =============
    archive.finalize_run(run_id, 'completed')
    
    print("\n" + "=" * 70)
    print("ARCHIVING RESULTS")
    print("=" * 70)
    
    # Export complet en JSONL
    export_path = archive.export_run(run_id)
    print(f"Exported JSONL: {export_path}")
    
    # Summary
    summary = archive.query_run_summary(run_id)
    
    print(f"\nRun Summary:")
    print(f"  Run ID: {run_id}")
    print(f"  Status: {summary['run'].get('status', 'N/A')}")
    print(f"  Total messages archived: {archived_count}")
    
    for msg_stat in summary.get('messages_stats', []):
        print(f"  Level {msg_stat.get('level')}: {msg_stat.get('count')} messages, "
              f"Avg latency: {msg_stat.get('avg_latency', 0):.2f}ms")
    
    metrics = summary.get('metrics_stats', {})
    print(f"\nMetrics Average:")
    print(f"  Coherence: {metrics.get('avg_coherence', 0):.3f}")
    print(f"  Tension:   {metrics.get('avg_tension', 0):.3f}")
    print(f"  Fit:       {metrics.get('avg_fit', 0):.3f}")
    print(f"  Pressure:  {metrics.get('avg_pressure', 0):.3f}")
    print(f"  Stability: {metrics.get('avg_stability', 0):.3f}")
    
    # Test retrieve
    sample_msg = results_l1[0]
    print(f"\nSample message retrieval test:")
    msg_data = archive.retrieve_message_data(sample_msg['msg_id'])
    if msg_data:
        print(f"  Retrieved message ID: {msg_data.get('msg_id')}")
        print(f"  Query: {msg_data.get('query_text', '')[:50]}...")
        print(f"  Response: {msg_data.get('response_text', '')[:50]}...")
    
    print("\n" + "=" * 70)
    print(f"BENCHMARK COMPLETE - Data archived to: {archive.archive_dir}/")
    print("=" * 70 + "\n")
    
    return run_id, archive


if __name__ == "__main__":
    run_id, archive = benchmark_phase2_archived()
