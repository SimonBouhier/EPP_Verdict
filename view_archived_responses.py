#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Afficheur des reponses archivees Phase 2
Recupère et affiche les vraies reponses du benchmark archivé
"""

import sys
import json
from pathlib import Path

# Ajouter project root au path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from tests.benchmarks.archive import BenchmarkArchive

def display_archived_responses():
    """Affiche les reponses completes du benchmark archive precedent"""
    
    print("\n" + "=" * 80)
    print("AFFICHAGE DES REPONSES ARCHIVEES - PHASE 2")
    print("=" * 80)
    print()
    
    # Trouver le dernier run archive
    benchmark_dir = Path("benchmark_results")
    jsonl_files = list(benchmark_dir.glob("*_export.jsonl"))
    
    if not jsonl_files:
        print("[ERREUR] Aucun fichier JSONL trouve dans benchmark_results/")
        return
    
    # Prendre le plus recent
    jsonl_file = sorted(jsonl_files)[-1]
    print(f"Fichier archivé: {jsonl_file}")
    print()
    
    # Lire et afficher
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        records = [json.loads(line) for line in f]
    
    print(f"Total messages archivés: {len(records)}")
    print()
    
    # Grouper par niveau
    levels = {}
    for record in records:
        level = record.get('level', 0)
        if level not in levels:
            levels[level] = []
        levels[level].append(record)
    
    # Afficher par niveau
    for level in sorted(levels.keys()):
        records_at_level = levels[level]
        print("=" * 80)
        print(f"LEVEL {level}: {len(records_at_level)} messages")
        print("=" * 80)
        
        for i, record in enumerate(records_at_level[:3], 1):  # Afficher les 3 premiers
            print(f"\n[Message {i}]")
            print(f"  Turn: {record.get('turn_number', 'N/A')}")
            print(f"  Query: {record.get('query_text', 'N/A')}")
            print(f"  Response: {record.get('response_text', 'N/A')[:300]}...")
            print(f"  Tokens: {record.get('tokens_prompt', 0)} prompt + {record.get('tokens_response', 0)} response")
            print(f"  Coherence: {record.get('coherence', 0):.3f}")
            print(f"  Stability: {record.get('stability', 0):.3f}")
        
        if len(records_at_level) > 3:
            print(f"\n  ... et {len(records_at_level) - 3} autres messages")
    
    print()
    print("=" * 80)
    print("EXPORT JSONL COMPLET")
    print("=" * 80)
    print(f"Fichier: {jsonl_file}")
    print(f"Taille: {jsonl_file.stat().st_size / 1024:.1f} KB")
    print()
    print("Pour analyser les donnees:")
    print(f"  import json")
    print(f"  with open('{jsonl_file}', 'r') as f:")
    print(f"      records = [json.loads(line) for line in f]")
    print()
    
    return records


if __name__ == '__main__':
    try:
        records = display_archived_responses()
        print("[OK] Benchmark complet - reponses archivees disponibles pour evaluation")
    except Exception as e:
        print(f"\n[ERREUR] {e}")
        import traceback
        traceback.print_exc()
