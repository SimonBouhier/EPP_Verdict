"""
Statistical analysis for Option B quick validation.

Usage:
    python evaluation/scripts/5_analyze_optionB.py
    
Output:
    evaluation/4_results/analysis_summary.json
    evaluation/4_results/analysis_report.md
"""

import json
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy import stats

def analyze_results(
    unblinded_file: str = "evaluation/4_results/judgments_unblinded.jsonl",
    output_dir: str = "evaluation/4_results"
):
    """
    Analyze judgments and generate go/no-go recommendation.
    """
    
    unblinded_path = Path(unblinded_file)
    if not unblinded_path.exists():
        print(f"ERROR: Unblinded judgments file not found: {unblinded_file}")
        return None
    
    # Load judgments
    with open(unblinded_path, 'r', encoding='utf-8') as f:
        judgments = [json.loads(line) for line in f if line.strip()]
    
    if not judgments:
        print(f"ERROR: No judgments found in {unblinded_file}")
        return None
    
    print("=" * 80)
    print("STATISTICAL ANALYSIS - OPTION B")
    print("=" * 80)
    print(f"Total judgments: {len(judgments)}")
    print()
    
    # Group by config
    configs_data = defaultdict(list)
    domains_data = defaultdict(lambda: defaultdict(list))
    
    for judgment in judgments:
        config_id = judgment.get('config_id')
        config_label = judgment.get('config_label')
        domain = judgment.get('domain')
        overall = judgment.get('overall')
        
        if overall is None:
            continue
        
        if isinstance(overall, str):
            try:
                overall = int(overall)
            except:
                continue
        
        configs_data[config_id].append({
            'label': config_label,
            'overall': overall,
            'accuracy': judgment.get('accuracy'),
            'completeness': judgment.get('completeness'),
            'clarity': judgment.get('clarity'),
            'appropriateness': judgment.get('appropriateness'),
            'relevance': judgment.get('relevance')
        })
        
        if domain:
            domains_data[domain][config_id].append(overall)
    
    # Compute summary statistics
    summary = {}
    
    print("PERFORMANCE BY CONFIG:")
    print("-" * 80)
    
    for config_id in sorted(configs_data.keys()):
        scores = [s['overall'] for s in configs_data[config_id] if s['overall'] is not None]
        
        if not scores:
            continue
        
        mean_score = np.mean(scores)
        std_score = np.std(scores)
        n = len(scores)
        
        summary[config_id] = {
            'label': configs_data[config_id][0]['label'],
            'n': n,
            'mean': float(mean_score),
            'std': float(std_score),
            'min': float(min(scores)),
            'max': float(max(scores))
        }
        
        print(f"{config_id:15s} | mean={mean_score:.2f} +/- {std_score:.2f} | n={n}")
    
    print()
    print("PAIRWISE COMPARISONS (T-tests, Bonferroni corrected):")
    print("-" * 80)
    
    config_ids = sorted(configs_data.keys())
    comparisons = []
    
    for i, config_a in enumerate(config_ids):
        scores_a = np.array([s['overall'] for s in configs_data[config_a] if s['overall'] is not None])
        
        for config_b in config_ids[i+1:]:
            scores_b = np.array([s['overall'] for s in configs_data[config_b] if s['overall'] is not None])
            
            if len(scores_a) < 2 or len(scores_b) < 2:
                continue
            
            t_stat, p_value = stats.ttest_ind(scores_a, scores_b)
            
            # Cohen's d effect size
            pooled_std = np.sqrt((np.std(scores_a, ddof=1)**2 + np.std(scores_b, ddof=1)**2) / 2)
            cohens_d = (np.mean(scores_a) - np.mean(scores_b)) / pooled_std if pooled_std > 0 else 0
            
            # Bonferroni correction
            n_comparisons = len(config_ids) * (len(config_ids) - 1) / 2
            alpha_corrected = 0.05 / n_comparisons
            significant = p_value < alpha_corrected
            
            comparison = {
                'config_a': config_a,
                'config_b': config_b,
                'mean_a': float(np.mean(scores_a)),
                'mean_b': float(np.mean(scores_b)),
                'delta': float(np.mean(scores_a) - np.mean(scores_b)),
                't_statistic': float(t_stat),
                'p_value': float(p_value),
                'p_value_corrected': float(min(p_value * n_comparisons, 1.0)),
                'cohens_d': float(cohens_d),
                'significant': significant
            }
            
            comparisons.append(comparison)
            
            sig_marker = "***" if significant else ""
            print(f"{config_a:15s} vs {config_b:15s}: delta={comparison['delta']:+.2f}, d={cohens_d:+.2f}, p={p_value:.4f} {sig_marker}")
    
    print()
    print("DOMAIN BREAKDOWN:")
    print("-" * 80)
    
    domain_summary = {}
    for domain in sorted(domains_data.keys()):
        print(f"\n{domain.upper()}:")
        domain_summary[domain] = {}
        
        for config_id in sorted(domains_data[domain].keys()):
            scores = domains_data[domain][config_id]
            if not scores:
                continue
            
            mean = np.mean(scores)
            std = np.std(scores)
            
            domain_summary[domain][config_id] = {
                'mean': float(mean),
                'std': float(std),
                'n': len(scores)
            }
            
            print(f"  {config_id:15s}: mean={mean:.2f} +/- {std:.2f} (n={len(scores)})")
    
    # GO/NO-GO DECISION
    print()
    print("=" * 80)
    print("GO / NO-GO DECISION")
    print("=" * 80)
    
    # Criteria
    has_significant_difference = any(c['significant'] for c in comparisons)
    has_medium_effect = any(abs(c['cohens_d']) > 0.3 for c in comparisons)
    has_large_effect = any(abs(c['cohens_d']) > 0.5 for c in comparisons)
    
    print(f"\nGO Criteria:")
    print(f"  [{'X' if has_significant_difference else ' '}] At least one significant difference (p < 0.05)")
    print(f"  [{'X' if has_medium_effect else ' '}] At least one medium effect (|d| > 0.3)")
    
    if has_significant_difference or has_large_effect:
        recommendation = "GO"
        recommendation_text = "Proceed to FULL EVALUATION (Option A)"
    else:
        recommendation = "INCONCLUSIVE"
        recommendation_text = "Collect more data or refine hypothesis"
    
    print()
    print(f"RECOMMENDATION: {recommendation}")
    print(f"ACTION: {recommendation_text}")
    
    # Save summary
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    results = {
        'timestamp': str(Path(unblinded_file).stat().st_mtime),
        'summary_statistics': summary,
        'pairwise_comparisons': comparisons,
        'domain_summary': domain_summary,
        'criteria': {
            'has_significant_difference': has_significant_difference,
            'has_medium_effect': has_medium_effect,
            'has_large_effect': has_large_effect
        },
        'recommendation': recommendation,
        'action': recommendation_text
    }
    
    # Save JSON
    summary_file = output_path / "analysis_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    # Save markdown report
    report_file = output_path / "analysis_report.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# OPTION B - QUICK VALIDATION ANALYSIS\n\n")
        
        f.write("## Summary Statistics\n\n")
        f.write("| Config | N | Mean | Std | Min | Max |\n")
        f.write("|--------|---|------|-----|-----|-----|\n")
        for config_id, stats_dict in summary.items():
            f.write(f"| {stats_dict['label']:<30s} | {stats_dict['n']:2d} | {stats_dict['mean']:.2f} | {stats_dict['std']:.2f} | {stats_dict['min']:.2f} | {stats_dict['max']:.2f} |\n")
        
        f.write("\n## Pairwise Comparisons\n\n")
        f.write("| Config A | Config B | Delta | d (Cohen's) | p-value | Significant |\n")
        f.write("|----------|----------|-------|-------------|---------|-------------|\n")
        for comp in comparisons:
            sig = "YES" if comp['significant'] else "NO"
            f.write(f"| {comp['config_a']:15s} | {comp['config_b']:15s} | {comp['delta']:+.2f} | {comp['cohens_d']:+.2f} | {comp['p_value']:.4f} | {sig} |\n")
        
        f.write(f"\n## Recommendation\n\n**{recommendation}**: {recommendation_text}\n")
    
    print()
    print("=" * 80)
    print(f"Analysis complete")
    print(f"  Summary: {summary_file}")
    print(f"  Report: {report_file}")
    print("=" * 80)
    
    return results


if __name__ == "__main__":
    analyze_results()
