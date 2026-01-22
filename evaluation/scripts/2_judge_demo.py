"""
2_judge_demo.py
Demo version of judging script with mock Claude Haiku responses.

This shows what the pipeline looks like without needing Anthropic API key.
For real execution, set $env:ANTHROPIC_API_KEY='sk-ant-...' and run 2_judge.py

Usage:
    python evaluation/scripts/2_judge_demo.py
    
Output:
    evaluation/3_judgments/judgments_blind.jsonl (with demo scores)
"""

import json
import random
from pathlib import Path
from typing import Dict, List

# Mock judgment rubric (same as real version)
MOCK_JUDGMENTS = [
    {
        "accuracy": 5,
        "completeness": 4,
        "clarity": 5,
        "coherence": 5,
        "appropriateness": 4,
        "overall": 4,
        "reasoning": "Accurate definition with good structure."
    },
    {
        "accuracy": 5,
        "completeness": 5,
        "clarity": 4,
        "coherence": 5,
        "appropriateness": 5,
        "overall": 5,
        "reasoning": "Comprehensive, clear, and well-adapted."
    },
    {
        "accuracy": 4,
        "completeness": 4,
        "clarity": 4,
        "coherence": 4,
        "appropriateness": 4,
        "overall": 4,
        "reasoning": "Solid response, minor clarity issues."
    },
    {
        "accuracy": 4,
        "completeness": 3,
        "clarity": 5,
        "coherence": 4,
        "appropriateness": 4,
        "overall": 4,
        "reasoning": "Clear but could be more comprehensive."
    },
    {
        "accuracy": 5,
        "completeness": 4,
        "clarity": 5,
        "coherence": 5,
        "appropriateness": 5,
        "overall": 5,
        "reasoning": "Excellent response, highly appropriate."
    },
    {
        "accuracy": 3,
        "completeness": 3,
        "clarity": 4,
        "coherence": 3,
        "appropriateness": 3,
        "overall": 3,
        "reasoning": "Acceptable but lacks depth and nuance."
    },
]

def judge_responses_demo(
    blind_file: str = "evaluation/2_blind_data/responses_blind.jsonl",
    output_file: str = "evaluation/3_judgments/judgments_blind.jsonl"
) -> List[Dict]:
    """
    Demo judge with mock scores.
    
    In real version, uses Claude Haiku 4.5 via Anthropic API.
    """
    
    # Create output directory
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    # Load blind responses
    blind_responses = []
    try:
        with open(blind_file, 'r') as f:
            blind_responses = [json.loads(line) for line in f]
    except FileNotFoundError:
        print(f"❌ Blind file not found: {blind_file}")
        return []
    
    if not blind_responses:
        print(f"❌ No responses found in {blind_file}")
        return []
    
    print("=" * 80)
    print("JUDGING WITH MOCK CLAUDE HAIKU 4.5 (DEMO MODE)")
    print("=" * 80)
    print(f"Evaluating {len(blind_responses)} responses...")
    print(f"⚠️  Using mock scores (for demonstration only)")
    print()
    
    judgments = []
    
    for i, response in enumerate(blind_responses, 1):
        resp_id = response['id']
        
        # Randomly select from mock judgments (or cycle through them)
        mock_judgment = MOCK_JUDGMENTS[i % len(MOCK_JUDGMENTS)]
        
        judgment_record = {
            "id": resp_id,
            "domain": response['domain'],
            "accuracy": mock_judgment["accuracy"],
            "completeness": mock_judgment["completeness"],
            "clarity": mock_judgment["clarity"],
            "coherence": mock_judgment["coherence"],
            "appropriateness": mock_judgment["appropriateness"],
            "overall": mock_judgment["overall"],
            "reasoning": mock_judgment["reasoning"],
            "timestamp": f"demo_id_{i}",
            "demo_mode": True
        }
        
        judgments.append(judgment_record)
        
        print(f"[{i}/{len(blind_responses)}] {resp_id:10} → Overall: {judgment_record['overall']}/5 ✓")
        
        # Save incrementally
        with open(output_file, 'a') as f:
            f.write(json.dumps(judgment_record) + '\n')
    
    print()
    print("=" * 80)
    print(f"✅ DEMO JUDGING COMPLETE")
    print("=" * 80)
    print(f"  Successful: {len(judgments)}/{len(blind_responses)}")
    print(f"  Output: {output_file}")
    print()
    print("⚠️  NOTE: This is DEMO data with mock scores")
    print("   For real evaluation, set ANTHROPIC_API_KEY and run:")
    print("   python evaluation/scripts/2_judge.py")
    print()
    print(f"Next step: python evaluation/scripts/3_unblind.py")
    print("=" * 80)
    
    return judgments


if __name__ == "__main__":
    judge_responses_demo()
