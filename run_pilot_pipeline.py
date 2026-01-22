"""
run_pilot_pipeline.py
Execute complete pilot triple-blind evaluation in sequence.

Workflow:
1. Extract pilot data (9 ML responses)
2. Anonymize (remove config_id)
3. Judge with Claude Haiku (blind)
4. Unblind (reveal config_id)
5. Analyze (statistics + recommendation)

Usage:
    python run_pilot_pipeline.py
    
Or run individual steps:
    python evaluation/scripts/0_create_pilot_data.py
    python evaluation/scripts/1_anonymize.py
    python evaluation/scripts/2_judge.py
    python evaluation/scripts/3_unblind.py
    python evaluation/scripts/4_analyze_pilot.py
"""

import subprocess
import sys
import time
from pathlib import Path

def run_step(step_num: int, script: str, description: str) -> bool:
    """Run a single pipeline step."""
    print()
    print("=" * 80)
    print(f"STEP {step_num}: {description}")
    print("=" * 80)
    print(f"Running: {script}")
    print()
    
    try:
        result = subprocess.run(
            [sys.executable, script],
            cwd=Path.cwd(),
            capture_output=False,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        if result.returncode != 0:
            print(f"❌ STEP {step_num} FAILED")
            return False
        
        print(f"✅ STEP {step_num} COMPLETE")
        time.sleep(1)  # Brief pause between steps
        return True
    
    except subprocess.TimeoutExpired:
        print(f"❌ STEP {step_num} TIMEOUT (10 minutes)")
        return False
    except Exception as e:
        print(f"❌ STEP {step_num} ERROR: {e}")
        return False


def main():
    """Execute full pilot pipeline."""
    
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "LYRA TRIPLE-BLIND EVALUATION - PILOT PIPELINE".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("║" + "Option B-1: Pilot Ultra-Rapide".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")
    
    print()
    print("📋 WORKFLOW:")
    print("  [1] Extract pilot data (9 responses)")
    print("  [2] Anonymize (remove metadata)")
    print("  [3] Judge with Claude Haiku (blind)")
    print("  [4] Unblind (reconstruct config_id)")
    print("  [5] Analyze (statistics + recommendation)")
    print()
    
    steps = [
        (1, "evaluation/scripts/0_create_pilot_data.py", "Extract Pilot Data"),
        (2, "evaluation/scripts/1_anonymize.py", "Anonymization"),
        (3, "evaluation/scripts/2_judge.py", "Blind Judging (Claude Haiku)"),
        (4, "evaluation/scripts/3_unblind.py", "Unblinding"),
        (5, "evaluation/scripts/4_analyze_pilot.py", "Analysis & Recommendation"),
    ]
    
    start_time = time.time()
    failed_steps = []
    
    for step_num, script, description in steps:
        success = run_step(step_num, script, description)
        
        if not success:
            failed_steps.append((step_num, description))
            print()
            print(f"⚠️  Pipeline stopped at Step {step_num}")
            break
    
    # Summary
    elapsed = time.time() - start_time
    
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    
    if not failed_steps:
        print("║" + "✅ PIPELINE COMPLETE - ALL STEPS SUCCESSFUL".center(78) + "║")
    else:
        print("║" + "❌ PIPELINE FAILED".center(78) + "║")
    
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")
    
    print()
    print(f"⏱️  Total time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    print()
    
    if not failed_steps:
        print("📊 OUTPUT FILES:")
        print()
        print("  Blind Data (for Claude):")
        print("    → evaluation/2_blind_data/responses_blind.jsonl")
        print()
        print("  Judgments (from Claude):")
        print("    → evaluation/3_judgments/judgments_blind.jsonl")
        print()
        print("  Results:")
        print("    → evaluation/4_results/judgments_unblinded.jsonl")
        print("    → evaluation/4_results/pilot_scores_by_config.json")
        print("    → evaluation/4_results/pilot_analysis.md")
        print()
        print("🔐 SECRET FILES (DO NOT SHARE):")
        print("    → evaluation/1_source_data/mapping_secret.json")
        print()
    else:
        print(f"❌ Failed at: {', '.join([d for _, d in failed_steps])}")
        print()
    
    print("=" * 80)


if __name__ == "__main__":
    main()
