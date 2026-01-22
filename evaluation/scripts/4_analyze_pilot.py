"""
4_analyze_pilot.py
Analyze pilot results - test if protocol works and if differences are detectable.

Inputs:
- Unblinded judgments with scores per response
- Grouped by config_id

Outputs:
- Summary statistics per config
- Visualization of differences
- Go/No-Go recommendation

Usage:
    python evaluation/scripts/4_analyze_pilot.py
    
Output:
    evaluation/4_results/pilot_analysis.md
    evaluation/4_results/pilot_scores_by_config.json
"""

import json
from pathlib import Path
from typing import Dict, List
from collections import defaultdict
import statistics

def load_unblinded_judgments(
    judgments_file: str = "evaluation/4_results/judgments_unblinded.jsonl"
) -> List[Dict]:
    """Load unblinded judgments."""
    judgments = []
    try:
        with open(judgments_file, 'r') as f:
            judgments = [json.loads(line) for line in f]
    except FileNotFoundError:
        print(f"❌ Judgments file not found: {judgments_file}")
        return []
    
    return [j for j in judgments if j.get('overall') is not None]


def analyze_pilot(
    judgments_file: str = "evaluation/4_results/judgments_unblinded.jsonl",
    output_md: str = "evaluation/4_results/pilot_analysis.md",
    output_json: str = "evaluation/4_results/pilot_scores_by_config.json"
) -> Dict:
    """Analyze pilot results."""
    
    # Load judgments
    judgments = load_unblinded_judgments(judgments_file)
    
    if not judgments:
        print(f"❌ No judgments to analyze")
        return {}
    
    # Group by config
    by_config = defaultdict(list)
    
    for j in judgments:
        config_id = j.get("config_id", "unknown")
        by_config[config_id].append({
            "accuracy": j.get("accuracy", 0),
            "completeness": j.get("completeness", 0),
            "clarity": j.get("clarity", 0),
            "coherence": j.get("coherence", 0),
            "appropriateness": j.get("appropriateness", 0),
            "overall": j.get("overall", 0),
            "reasoning": j.get("reasoning", "")
        })
    
    # Calculate statistics
    stats = {}
    for config_id, scores in by_config.items():
        overall_scores = [s["overall"] for s in scores]
        
        stats[config_id] = {
            "n": len(scores),
            "overall_mean": round(statistics.mean(overall_scores), 2),
            "overall_std": round(statistics.stdev(overall_scores), 2) if len(overall_scores) > 1 else 0,
            "overall_min": min(overall_scores),
            "overall_max": max(overall_scores),
            "accuracy_mean": round(statistics.mean([s["accuracy"] for s in scores]), 2),
            "completeness_mean": round(statistics.mean([s["completeness"] for s in scores]), 2),
            "clarity_mean": round(statistics.mean([s["clarity"] for s in scores]), 2),
            "coherence_mean": round(statistics.mean([s["coherence"] for s in scores]), 2),
            "appropriateness_mean": round(statistics.mean([s["appropriateness"] for s in scores]), 2),
            "sample_reasoning": scores[0]["reasoning"][:100] if scores[0]["reasoning"] else ""
        }
    
    # Save JSON
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    # Generate markdown report
    md_report = generate_markdown_report(stats, judgments)
    
    Path(output_md).parent.mkdir(parents=True, exist_ok=True)
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write(md_report)
    
    print("=" * 80)
    print("PILOT ANALYSIS COMPLETE")
    print("=" * 80)
    print(md_report)
    print()
    print(f"✅ Full report: {output_md}")
    print(f"✅ JSON stats: {output_json}")
    print("=" * 80)
    
    return stats


def generate_markdown_report(stats: Dict, judgments: List[Dict]) -> str:
    """Generate markdown analysis report."""
    
    report = []
    report.append("# PILOT EVALUATION REPORT")
    report.append("")
    report.append(f"**Date:** {Path('evaluation/4_results').stat().st_mtime}")
    report.append(f"**Total Responses Judged:** {len(judgments)}")
    report.append(f"**Configurations:** {len(stats)}")
    report.append("")
    
    report.append("---")
    report.append("## Summary Statistics by Configuration")
    report.append("")
    
    # Sort by overall score
    sorted_configs = sorted(stats.items(), key=lambda x: x[1]["overall_mean"], reverse=True)
    
    for config_id, s in sorted_configs:
        report.append(f"### {config_id}")
        report.append("")
        report.append(f"| Metric | Score |")
        report.append(f"|--------|-------|")
        report.append(f"| Overall | {s['overall_mean']} ± {s['overall_std']} |")
        report.append(f"| Accuracy | {s['accuracy_mean']} |")
        report.append(f"| Completeness | {s['completeness_mean']} |")
        report.append(f"| Clarity | {s['clarity_mean']} |")
        report.append(f"| Coherence | {s['coherence_mean']} |")
        report.append(f"| Appropriateness | {s['appropriateness_mean']} |")
        report.append(f"| n | {s['n']} |")
        report.append("")
        if s['sample_reasoning']:
            report.append(f"**Sample Judgment:** _{s['sample_reasoning']}_")
            report.append("")
    
    report.append("---")
    report.append("## Interpretation")
    report.append("")
    
    if len(sorted_configs) > 1:
        best = sorted_configs[0]
        worst = sorted_configs[-1]
        delta = best[1]['overall_mean'] - worst[1]['overall_mean']
        
        report.append(f"**Best Performer:** {best[0]} ({best[1]['overall_mean']}/5)")
        report.append(f"**Worst Performer:** {worst[0]} ({worst[1]['overall_mean']}/5)")
        report.append(f"**Difference:** {delta:.2f} points")
        report.append("")
        
        if delta > 0.5:
            report.append("✅ **DETECTABLE DIFFERENCE**: Configs show meaningful variation")
            report.append("   → Protocol successfully identifies quality differences")
        elif delta > 0.2:
            report.append("⚠️  **MARGINAL DIFFERENCE**: Configs show small variation")
            report.append("   → Differences exist but are subtle")
        else:
            report.append("❌ **NO SIGNIFICANT DIFFERENCE**: Configs score similarly")
            report.append("   → May need larger sample or different prompts")
    
    report.append("")
    report.append("---")
    report.append("## Next Steps")
    report.append("")
    report.append("If GO → Proceed to full 60-response evaluation:")
    report.append("```bash")
    report.append("python evaluation/scripts/0_create_pilot_data.py  # Full 60 responses")
    report.append("python evaluation/scripts/1_anonymize.py")
    report.append("python evaluation/scripts/2_judge.py")
    report.append("python evaluation/scripts/3_unblind.py")
    report.append("python evaluation/scripts/4_analyze_full.py")
    report.append("```")
    report.append("")
    
    return "\n".join(report)


if __name__ == "__main__":
    analyze_pilot()
