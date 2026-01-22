"""
Reconstruct judgments with config metadata (unblind).

Usage:
    python evaluation/scripts/4_unblind.py
    
Output:
    evaluation/4_results/judgments_unblinded.jsonl
"""

import json
from pathlib import Path

def unblind_judgments(
    judgments_file: str = "evaluation/3_judgments/judgments_blind.jsonl",
    mapping_file: str = "evaluation/1_source_data/mapping_secret.json",
    output_file: str = "evaluation/4_results/judgments_unblinded.jsonl"
):
    """
    Reconstruct judgments with config_id metadata.
    """
    
    judgments_path = Path(judgments_file)
    mapping_path = Path(mapping_file)
    output_path = Path(output_file)
    
    # Verify files exist
    if not judgments_path.exists():
        print(f"ERROR: Judgments file not found: {judgments_file}")
        return None
    
    if not mapping_path.exists():
        print(f"ERROR: Mapping file not found: {mapping_file}")
        return None
    
    print("=" * 80)
    print("UNBLINDING - RECONSTRUCTION")
    print("=" * 80)
    
    # Load judgments
    with open(judgments_path, 'r', encoding='utf-8') as f:
        judgments = [json.loads(line) for line in f if line.strip()]
    
    print(f"Loaded: {len(judgments)} judgments")
    
    # Load mapping
    with open(mapping_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f)
    
    print(f"Loaded: {len(mapping)} mapping entries")
    
    # Reconstruct
    unblinded = []
    errors = 0
    
    for judgment in judgments:
        anon_id = judgment.get('id')
        
        if anon_id not in mapping:
            print(f"WARNING: {anon_id} not in mapping")
            errors += 1
            continue
        
        # Get original metadata
        original = mapping[anon_id]
        
        # Merge
        unblinded_judgment = {
            **judgment,
            "config_id": original.get("config_id"),
            "config_label": original.get("config_label"),
            "domain": original.get("domain"),
            "original_index": original.get("original_index")
        }
        
        unblinded.append(unblinded_judgment)
    
    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save
    with open(output_path, 'w', encoding='utf-8') as f:
        for uj in unblinded:
            f.write(json.dumps(uj) + '\n')
    
    print()
    print("=" * 80)
    print(f"Unblinding Complete")
    print(f"  Reconstructed: {len(unblinded)}")
    print(f"  Errors: {errors}")
    print(f"  Output: {output_path}")
    print("=" * 80)
    
    return output_path


if __name__ == "__main__":
    unblind_judgments()
