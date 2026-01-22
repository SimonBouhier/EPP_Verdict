#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Launcher pour benchmark phase 2 avec vraies reponses
Ajoute le project root au path sys
"""

import sys
import os
from pathlib import Path

# Force UTF-8 output encoding
if sys.stdout:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr:
    import io
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Ajouter le project root au path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Maintenant on peut importer
from tests.benchmarks.benchmark_phase_2_real_responses import benchmark_phase2_real_responses

if __name__ == '__main__':
    try:
        result = benchmark_phase2_real_responses()
        print("\n[OK] Benchmark termine!")
        print(f"  Run ID: {result['run_id']}")
        print(f"  Messages archives: {result['archived_count']}")
        print(f"  Export JSONL: {result['export_path']}")
    except Exception as e:
        print(f"\n[ERREUR] {e}")
        import traceback
        traceback.print_exc()
