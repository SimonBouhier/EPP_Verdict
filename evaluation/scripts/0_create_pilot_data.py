"""
0_create_pilot_data.py
Extract 9 responses for "What is machine learning?" from existing validation_results.jsonl
to create a minimal pilot dataset for testing the triple-blind protocol.

Usage:
    python evaluation/scripts/0_create_pilot_data.py

Output:
    evaluation/1_source_data/pilot_data.jsonl (9 lines)
"""

import json
from pathlib import Path
from typing import List, Dict

def extract_pilot_data(
    source_file: str = "validation_results.jsonl",
    output_file: str = "evaluation/1_source_data/pilot_data.jsonl"
) -> List[Dict]:
    """
    Extract ML responses from validation_results.jsonl
    
    Looks for: "What is machine learning?" across different configs
    """
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    ml_responses = []
    
    try:
        with open(source_file, 'r') as f:
            for line in f:
                record = json.loads(line)
                # Filter for ML question
                if "machine learning" in record.get("prompt", "").lower():
                    ml_responses.append(record)
    except FileNotFoundError:
        print(f"❌ Source file not found: {source_file}")
        return []
    
    # Format for pilot (keep essential fields only)
    pilot_data = []
    
    for i, resp in enumerate(ml_responses, 1):
        # Create unique config label combining config_id and order
        config_label = f"{resp.get('config_label', 'Unknown')} ({resp.get('execution_order', 'unknown')})"
        
        pilot_record = {
            "index": i,
            "config_id": resp.get("config_id", "unknown"),
            "config_label": config_label,
            "execution_order": resp.get("execution_order", "unknown"),
            "domain": resp.get("domain", "technical"),
            "prompt": resp.get("prompt", ""),
            "response": resp.get("response", ""),
            "latency_ms": resp.get("latency_ms", 0),
            "tokens_approx": resp.get("tokens_approx", 0),
            "timestamp": resp.get("timestamp", "")
        }
        
        pilot_data.append(pilot_record)
    
    # Save pilot data
    with open(output_file, 'w') as f:
        for record in pilot_data:
            f.write(json.dumps(record) + '\n')
    
    print(f"✅ Pilot data created: {output_file}")
    print(f"   Total responses: {len(pilot_data)}")
    print()
    
    # Display summary
    print("Configurations in pilot:")
    for record in pilot_data:
        print(f"  [{record['index']}] {record['config_label']:40} | {record['latency_ms']:7.1f}ms")
    
    print()
    print(f"Sample response:")
    if pilot_data:
        print(f"  Prompt: {pilot_data[0]['prompt'][:60]}...")
        print(f"  Response: {pilot_data[0]['response'][:80]}...")
    
    return pilot_data


if __name__ == "__main__":
    data = extract_pilot_data()
    print(f"\n✅ Ready for anonymization step!")
