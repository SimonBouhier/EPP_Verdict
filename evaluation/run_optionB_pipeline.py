"""
Orchestrate the entire Option B pipeline.

Usage:
    python evaluation/run_optionB_pipeline.py
"""

import subprocess
import sys
from pathlib import Path
import time

def run_command(cmd, description):
    """Run a command and report results."""
    print()
    print("=" * 80)
    print(f"STEP: {description}")
    print("=" * 80)
    print(f"Command: {' '.join(cmd)}")
    print()
    
    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent.parent.parent)
        if result.returncode != 0:
            print()
            print(f"ERROR: {description} failed with return code {result.returncode}")
            return False
        return True
    except KeyboardInterrupt:
        print()
        print("Interrupted by user")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def main():
    print()
    print("*" * 80)
    print("OPTION B - QUICK VALIDATION PIPELINE")
    print("*" * 80)
    print()
    
    steps = [
        (
            ["python", "evaluation/scripts/1_generate_responses_optionB.py"],
            "1/5 Generate 60 responses (4 configs x 15 prompts)"
        ),
        (
            ["python", "evaluation/scripts/2_anonymize.py"],
            "2/5 Anonymize responses for blind judging"
        ),
        (
            ["python", "evaluation/scripts/3_judge_blind.py"],
            "3/5 Judge with Claude Haiku 4.5"
        ),
        (
            ["python", "evaluation/scripts/4_unblind.py"],
            "4/5 Unblind and reconstruct results"
        ),
        (
            ["python", "evaluation/scripts/5_analyze_optionB.py"],
            "5/5 Analyze results and generate recommendation"
        )
    ]
    
    completed = 0
    for cmd, description in steps:
        if run_command(cmd, description):
            completed += 1
        else:
            print()
            print(f"Pipeline stopped at step {completed + 1}/5")
            return False
        
        time.sleep(1)
    
    print()
    print("=" * 80)
    print(f"PIPELINE COMPLETE: {completed}/{len(steps)} steps successful")
    print("=" * 80)
    print()
    print("Next steps:")
    print("  1. Review: evaluation/4_results/analysis_report.md")
    print("  2. Check recommendation: GO or INCONCLUSIVE")
    print("  3. If GO: Proceed to full Option A evaluation")
    print("  4. If INCONCLUSIVE: Refine and retry")
    print()
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
