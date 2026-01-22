"""
Mock judgment for demonstration - simulates Claude Haiku evaluation.

This creates realistic dummy judgments for testing the pipeline.
In production, replace with real Claude Haiku 4.5 API calls.
"""

import json
from pathlib import Path
import random

def generate_mock_judgments(
    blind_file: str = "evaluation/2_blind_data/responses_blind.jsonl",
    output_file: str = "evaluation/3_judgments/judgments_blind.jsonl"
):
    """
    Generate mock judgments for testing.
    """
    
    blind_path = Path(blind_file)
    if not blind_path.exists():
        print(f"ERROR: Blind data file not found: {blind_file}")
        return None
    
    # Load blind responses
    with open(blind_path, 'r', encoding='utf-8') as f:
        responses = [json.loads(line) for line in f if line.strip()]
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Clear if exists
    if output_path.exists():
        output_path.unlink()
    
    print("=" * 80)
    print("MOCK JUDGMENT GENERATION (for testing)")
    print("=" * 80)
    print(f"Responses to judge: {len(responses)}")
    print(f"Output: {output_path}")
    print()
    
    judgments = []
    
    # Config-specific score distributions (simulated)
    config_scores = {
        "baseline": {"mean": 3.2, "std": 0.6},
        "temp_only": {"mean": 3.3, "std": 0.6},
        "system_only": {"mean": 3.6, "std": 0.5},
        "full_lyra": {"mean": 3.8, "std": 0.5}
    }
    
    for i, response in enumerate(responses):
        anon_id = response.get('id')
        domain = response.get('domain')
        
        print(f"[{i+1:2d}/{len(responses)}] {anon_id} ({domain:10s})... ", end="", flush=True)
        
        # Map anon_id back to config (for scoring simulation only, not cheating)
        # In real scenario, judge is truly blind
        # This is just for demo to show config effect
        config_id = "baseline"  # Default
        for config in ["baseline", "temp_only", "system_only", "full_lyra"]:
            if config in anon_id or (i % 4) == list(config_scores.keys()).index(config):
                config_id = config
                break
        
        # Generate scores based on config
        config_dist = config_scores.get(config_id, {"mean": 3.5, "std": 0.6})
        
        # Overall score (normally distributed)
        overall = random.gauss(config_dist["mean"], config_dist["std"])
        overall = max(1, min(5, int(round(overall))))  # Clamp to 1-5
        
        # Component scores (correlated with overall)
        base_score = overall - random.uniform(-0.5, 0.5)
        
        judgment = {
            "id": anon_id,
            "domain": domain,
            "accuracy": max(1, min(5, int(round(base_score + random.uniform(-0.3, 0.3))))),
            "completeness": max(1, min(5, int(round(base_score + random.uniform(-0.3, 0.3))))),
            "clarity": max(1, min(5, int(round(base_score + random.uniform(-0.3, 0.3))))),
            "appropriateness": max(1, min(5, int(round(base_score + random.uniform(-0.3, 0.3))))),
            "relevance": max(1, min(5, int(round(base_score + random.uniform(-0.3, 0.3))))),
            "overall": overall,
            "reasoning": f"Mock judgment for {domain} response",
            "judged_at": f"mock-msg-{i}"
        }
        
        judgments.append(judgment)
        
        print(f"overall={judgment['overall']}/5")
        
        # Save incrementally
        with open(output_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(judgment) + '\n')
    
    print()
    print("=" * 80)
    print(f"Mock Judging Complete")
    print(f"  Total: {len(judgments)}")
    print(f"  Output: {output_path}")
    print(f"\nNOTE: For real evaluation, run 3_judge_blind.py with ANTHROPIC_API_KEY set")
    print("=" * 80)
    
    return output_path


if __name__ == "__main__":
    generate_mock_judgments()
