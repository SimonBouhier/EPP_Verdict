#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Benchmark Phase 2 - Version SIMPLIFIEE et FONCTIONNELLE
Basee sur le test qui marche!
"""

import sys
import os
from pathlib import Path

# Ajouter project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
import requests
import json
from datetime import datetime

from services.consciousness.metrics import ConsciousnessMonitor
from services.consciousness.adaptation import AdaptiveConsciousness
from tests.benchmarks.archive import BenchmarkArchive


def benchmark_simple():
    """Benchmark ultra-simple qui fonctionne"""
    
    print("\n" + "=" * 80)
    print("BENCHMARK PHASE 2 - VERSION SIMPLIFIEE")
    print("=" * 80)
    print("Vraies reponses de gpt-oss:20b")
    print()
    
    # Initialiser archive
    archive = BenchmarkArchive()
    run_id = f"phase2_simple_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    config = {
        'type': 'phase2_simple',
        'prompts': 3,
        'archive_enabled': True,
        'generation_model': 'gpt-oss:20b'
    }
    
    archive.create_run(run_id, 'phase2_simple', config)
    
    # Prompts simples
    prompts = [
        "What is machine learning? (answer in 20 words max)",
        "Explain Python briefly (20 words max)",
        "What is AI? (20 words max)"
    ]
    
    print(f"Run ID: {run_id}")
    print(f"Total prompts: {len(prompts)}")
    print()
    
    url = "http://localhost:11434/api/generate"
    archived_count = 0
    
    for turn, prompt in enumerate(prompts, 1):
        print(f"[Turn {turn}/{len(prompts)}] Prompt: {prompt[:40]}...")
        
        try:
            # Appel Ollama ultra-simple
            payload = {
                "model": "gpt-oss:20b",
                "prompt": prompt,
                "stream": False,
                "num_predict": 100,  # Limiter les tokens
                "temperature": 0.7
            }
            
            print(f"  Calling Ollama... ", end='', flush=True)
            start_time = time.perf_counter()
            
            # SIMPLE: juste requests.post avec timeout
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            data = response.json()
            response_text = data.get('response', '')
            
            print(f"OK ({elapsed_ms:.0f}ms)")
            print(f"  Response: {response_text[:60]}...")
            print()
            
            # Calculer metriques
            monitor = ConsciousnessMonitor(level=1)
            metrics = monitor.compute_metrics(
                context_weight=5.0,
                num_concepts=5,
                physics_state={'tau_c': 1.0, 'rho': 0.2, 'delta_r': 0.0},
                response_length=len(response_text)
            )
            
            # Simuler embeddings (deterministes)
            import hashlib
            import math
            
            def fake_embeddings(text):
                hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
                emb = [math.sin((hash_val + i) / 1000.0) for i in range(1024)]
                norm = sum(e*e for e in emb) ** 0.5
                return [e / (norm + 1e-8) for e in emb]
            
            query_emb = fake_embeddings(prompt)
            response_emb = fake_embeddings(response_text)
            
            # Archiver
            msg_id = archive.archive_message(
                run_id=run_id,
                turn_number=turn,
                level=1,
                query_text=prompt,
                query_embeddings=query_emb,
                response_text=response_text,
                response_embeddings=response_emb,
                latency_ms=elapsed_ms,
                tokens={
                    'prompt': data.get('prompt_eval_count', 0),
                    'completion': data.get('eval_count', 0),
                    'total': data.get('prompt_eval_count', 0) + data.get('eval_count', 0)
                }
            )
            
            archive.archive_metrics(
                msg_id=msg_id,
                coherence=metrics.coherence if metrics else 0,
                tension=metrics.tension if metrics else 0,
                fit=metrics.fit if metrics else 0,
                pressure=metrics.pressure if metrics else 0,
                stability=metrics.stability_score if metrics else 0
            )
            
            archive.archive_context(
                msg_id=msg_id,
                concepts_injected=[f"concept_{i}" for i in range(5)],
                graph_weight=5.0,
                session_length=turn,
                profile_used='balanced',
                llm_model='gpt-oss:20b'
            )
            
            archived_count += 1
            
        except Exception as e:
            print(f"[ERREUR] {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Exporter
    print()
    print("=" * 80)
    print("RESULTATS")
    print("=" * 80)
    
    export_path = archive.export_run(run_id)
    
    print(f"Messages archives: {archived_count}/{len(prompts)}")
    print(f"Export JSONL: {export_path}")
    print(f"Database: benchmark_archive.db")
    print()
    print("[OK] Benchmark complete!")
    print()
    
    return {
        'run_id': run_id,
        'archived_count': archived_count,
        'export_path': str(export_path)
    }


if __name__ == '__main__':
    result = benchmark_simple()
