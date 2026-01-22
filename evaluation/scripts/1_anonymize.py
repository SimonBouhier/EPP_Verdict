"""
1_anonymize.py
Anonymize responses for triple-blind protocol.

Transforms source data with config_id into blind data with only:
- id (anonymous_id)
- prompt
- response
- domain

Keeps secret mapping: anonymous_id -> config_id

Usage:
    python evaluation/scripts/1_anonymize.py
    
Output:
    evaluation/2_blind_data/responses_blind.jsonl
    evaluation/1_source_data/mapping_secret.json
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Tuple

def anonymize_responses(
    source_file: str = "evaluation/1_source_data/pilot_data.jsonl",
    blind_output: str = "evaluation/2_blind_data/responses_blind.jsonl",
    mapping_output: str = "evaluation/1_source_data/mapping_secret.json"
) -> Tuple[List[Dict], Dict]:
    """
    Anonymize responses for blind judging.
    
    Args:
        source_file: Input JSONL with config_id (visible)
        blind_output: Output JSONL with anonymous_id only
        mapping_output: Secret mapping file (anonymous_id -> config_id)
    
    Returns:
        Tuple of (blind_responses, mapping)
    """
    
    # Create output directories
    Path(blind_output).parent.mkdir(parents=True, exist_ok=True)
    Path(mapping_output).parent.mkdir(parents=True, exist_ok=True)
    
    # Read source data
    source_responses = []
    try:
        with open(source_file, 'r') as f:
            source_responses = [json.loads(line) for line in f]
    except FileNotFoundError:
        print(f"❌ Source file not found: {source_file}")
        print(f"   Run: python evaluation/scripts/0_create_pilot_data.py")
        return [], {}
    
    if not source_responses:
        print(f"❌ No responses found in {source_file}")
        return [], {}
    
    # Create anonymous IDs in random order (mask patterns)
    anonymous_ids = [f"resp_{i:04d}" for i in range(len(source_responses))]
    random.shuffle(anonymous_ids)
    
    # Build mapping and blind data
    mapping = {}
    blind_responses = []
    
    for i, response in enumerate(source_responses):
        anon_id = anonymous_ids[i]
        
        # Store mapping (SECRET - keep in safe place)
        mapping[anon_id] = {
            "config_id": response.get("config_id", "unknown"),
            "config_label": response.get("config_label", "unknown"),
            "execution_order": response.get("execution_order", "unknown"),
            "original_index": response.get("index", i),
            "latency_ms": response.get("latency_ms", 0)
        }
        
        # Create blind version (ONLY prompt, response, domain - nothing identifiable)
        blind_response = {
            "id": anon_id,
            "prompt": response.get("prompt", ""),
            "response": response.get("response", ""),
            "domain": response.get("domain", "technical")
        }
        
        blind_responses.append(blind_response)
    
    # Save blind data
    with open(blind_output, 'w') as f:
        for br in blind_responses:
            f.write(json.dumps(br) + '\n')
    
    # Save secret mapping
    with open(mapping_output, 'w') as f:
        json.dump(mapping, f, indent=2)
    
    # Report
    print("=" * 80)
    print("ANONYMIZATION COMPLETE")
    print("=" * 80)
    print(f"✅ Blind data: {blind_output}")
    print(f"   - {len(blind_responses)} responses")
    print(f"   - Fields: id, prompt, response, domain")
    print()
    print(f"🔐 Secret mapping: {mapping_output}")
    print(f"   - DO NOT SHARE THIS FILE!")
    print(f"   - Only open after judging is complete")
    print()
    print("⚠️  TRIPLE-BLIND PROTOCOL:")
    print("   1. Judge does NOT see mapping")
    print("   2. Experimenter does NOT see mapping during judging")
    print("   3. Data and metadata are physically separated")
    print()
    print(f"Next step: python evaluation/scripts/2_judge.py")
    print("=" * 80)
    
    return blind_responses, mapping


if __name__ == "__main__":
    anonymize_responses()
