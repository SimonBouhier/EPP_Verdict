"""
Anonymize responses for blind judging.

Usage:
    python evaluation/scripts/2_anonymize.py
    
Output:
    evaluation/2_blind_data/responses_blind.jsonl
    evaluation/1_source_data/mapping_secret.json
"""

import json
import hashlib
import random
from pathlib import Path

def anonymize_responses(
    source_file: str = "evaluation/1_source_data/responses_raw.jsonl",
    output_dir: str = "evaluation"
):
    """
    Anonymises les réponses et crée le mapping secret.
    
    Input:  responses_raw.jsonl (avec config_id, metadata, etc.)
    Output: responses_blind.jsonl (prompt + response + anonymous_id uniquement)
            mapping_secret.json (anonymous_id → config_id)
    """
    
    source_path = Path(source_file)
    blind_dir = Path(output_dir) / "2_blind_data"
    blind_dir.mkdir(parents=True, exist_ok=True)
    
    mapping_file = Path(output_dir) / "1_source_data" / "mapping_secret.json"
    
    # Load responses
    if not source_path.exists():
        print(f"✗ Source file not found: {source_file}")
        return None, None
    
    with open(source_path, 'r', encoding='utf-8') as f:
        responses = [json.loads(line) for line in f if line.strip()]
    
    if not responses:
        print(f"✗ No responses found in {source_file}")
        return None, None
    
    print("=" * 80)
    print("ANONYMIZATION")
    print("=" * 80)
    print(f"Input: {len(responses)} responses")
    
    # Create mapping with random order
    mapping = {}
    anonymous_ids = [f"resp_{i:04d}" for i in range(len(responses))]
    random.shuffle(anonymous_ids)
    
    blind_responses = []
    
    for i, response in enumerate(responses):
        anon_id = anonymous_ids[i]
        
        # Store mapping (SECRET)
        mapping[anon_id] = {
            "config_id": response.get("config_id"),
            "config_label": response.get("config_label"),
            "domain": response.get("domain"),
            "original_index": i
        }
        
        # Create blind version (NO identifiable metadata)
        blind_response = {
            "id": anon_id,
            "prompt": response.get("prompt"),
            "response": response.get("response"),
            "domain": response.get("domain")  # OK: helps stratification but not identifiable
        }
        
        blind_responses.append(blind_response)
    
    # Save blind data
    blind_file = blind_dir / "responses_blind.jsonl"
    with open(blind_file, 'w', encoding='utf-8') as f:
        for br in blind_responses:
            f.write(json.dumps(br) + '\n')
    
    # Save mapping (KEEP SECRET - store separately)
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=2)
    
    print(f"Output:")
    print(f"  Blind data: {blind_file}")
    print(f"  Mapping (SECRET): {mapping_file}")
    print()
    print("WARNING: Do NOT open mapping_secret.json until analysis phase!")
    print("=" * 80)
    
    return blind_file, mapping_file


if __name__ == "__main__":
    blind_file, mapping_file = anonymize_responses()
    
    if blind_file and mapping_file:
        # Verify
        with open(blind_file, 'r', encoding='utf-8') as f:
            blind_count = sum(1 for _ in f)
        with open(mapping_file, 'r', encoding='utf-8') as f:
            mapping = json.load(f)
            mapping_count = len(mapping)
        
        print(f"\nVerification:")
        print(f"  Blind responses: {blind_count}")
        print(f"  Mapping entries: {mapping_count}")
        print(f"  Match: {'✓' if blind_count == mapping_count else '✗'}")
