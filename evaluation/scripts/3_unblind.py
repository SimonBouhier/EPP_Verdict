"""
3_unblind.py
Reconstruct judgments with real config_id after judging is complete.

Only after all blind judging done, merge:
- Blind judgments (with anonymous_id)
- Secret mapping (anonymous_id -> config_id)

Output: Fully reconstructed results

Usage:
    python evaluation/scripts/3_unblind.py
    
Output:
    evaluation/4_results/judgments_unblinded.jsonl
"""

import json
from pathlib import Path
from typing import Dict, List

def unblind_judgments(
    judgments_file: str = "evaluation/3_judgments/judgments_blind.jsonl",
    mapping_file: str = "evaluation/1_source_data/mapping_secret.json",
    output_file: str = "evaluation/4_results/judgments_unblinded.jsonl"
) -> List[Dict]:
    """
    Reconstruct judgments with real config_id.
    
    Args:
        judgments_file: Blind judgments from Claude
        mapping_file: Secret mapping (anonymous_id -> config_id)
        output_file: Output unblinded judgments
    
    Returns:
        List of unblinded judgment records
    """
    
    # Create output directory
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    # Load blind judgments
    judgments = []
    try:
        with open(judgments_file, 'r') as f:
            judgments = [json.loads(line) for line in f]
    except FileNotFoundError:
        print(f"❌ Judgments file not found: {judgments_file}")
        print(f"   Run: python evaluation/scripts/2_judge.py")
        return []
    
    if not judgments:
        print(f"❌ No judgments found in {judgments_file}")
        return []
    
    # Load mapping
    mapping = {}
    try:
        with open(mapping_file, 'r') as f:
            mapping = json.load(f)
    except FileNotFoundError:
        print(f"❌ Mapping file not found: {mapping_file}")
        print(f"   Run: python evaluation/scripts/1_anonymize.py")
        return []
    
    if not mapping:
        print(f"❌ Empty mapping in {mapping_file}")
        return []
    
    # Reconstruct
    unblinded = []
    
    for judgment in judgments:
        anon_id = judgment.get('id')
        
        if anon_id not in mapping:
            print(f"⚠️  Warning: No mapping found for {anon_id}")
            continue
        
        # Get original config info
        original = mapping[anon_id]
        
        # Merge
        unblinded_record = {
            **judgment,  # All judgment fields
            "config_id": original["config_id"],
            "config_label": original["config_label"],
            "execution_order": original["execution_order"],
            "original_index": original["original_index"],
            "latency_ms": original["latency_ms"]
        }
        
        unblinded.append(unblinded_record)
    
    # Save
    with open(output_file, 'w') as f:
        for record in unblinded:
            f.write(json.dumps(record) + '\n')
    
    # Report
    print("=" * 80)
    print("UNBLINDING COMPLETE")
    print("=" * 80)
    print(f"✅ Unblinded {len(unblinded)} judgments")
    print(f"   Output: {output_file}")
    print()
    print("Data now contains:")
    print("  - Judgment scores (accuracy, completeness, clarity, etc.)")
    print("  - Real config_id (decoded from mapping)")
    print("  - Original metadata (execution_order, latency_ms)")
    print()
    print(f"Next step: python evaluation/scripts/4_analyze.py")
    print("=" * 80)
    
    return unblinded


if __name__ == "__main__":
    unblind_judgments()
