"""
Verify that responses are properly saved with all fields.
"""
import json
from pathlib import Path

def verify_responses():
    """Verify response integrity."""
    raw_file = Path("evaluation/1_source_data/responses_raw.jsonl")
    
    if not raw_file.exists():
        print("File not yet created")
        return
    
    with open(raw_file, 'r', encoding='utf-8') as f:
        responses = [json.loads(line) for line in f if line.strip()]
    
    print(f"\nTotal responses: {len(responses)}")
    
    if responses:
        sample = responses[0]
        print("\nFirst response structure:")
        for key, value in sample.items():
            if key == "response":
                preview = value[:100] if isinstance(value, str) else value
                print(f"  {key}: {repr(preview)}..." if isinstance(value, str) and len(value) > 100 else f"  {key}: {repr(preview)}")
            else:
                print(f"  {key}: {repr(value)}")
        
        # Check for empty responses
        empty_responses = sum(1 for r in responses if not r.get("response"))
        print(f"\nEmpty responses: {empty_responses}")
        
        # Check by config
        configs = {}
        for r in responses:
            config = r.get("config_id")
            if config not in configs:
                configs[config] = 0
            configs[config] += 1
        
        print("\nResponses per config:")
        for config, count in sorted(configs.items()):
            print(f"  {config}: {count}")

if __name__ == "__main__":
    verify_responses()
