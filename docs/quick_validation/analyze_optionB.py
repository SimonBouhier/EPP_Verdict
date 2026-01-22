"""
Analyze Option B results with statistical tests and visualizations.

Usage:
    python analyze_optionB.py \
        --input evaluation/4_results/judgments_unblinded.jsonl \
        --output evaluation/5_analysis/
        
Outputs:
    - summary_stats.json
    - pairwise_tests.json
    - domain_breakdown.json
    - attribution_chart.png
    - report.md
"""

import json
import argparse
from pathlib import Path
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_style("whitegrid")

# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

def load_judgments(filepath):
    """Load unblinded judgments."""
    judgments = []
    with open(filepath) as f:
        for line in f:
            judgments.append(json.loads(line))
    return judgments


def compute_summary_stats(judgments):
    """Compute summary statistics by config."""
    
    stats_by_config = {}
    
    for config_id in ["baseline", "temp_only", "system_only", "full_lyra"]:
        config_data = [j for j in judgments if j["config_id"] == config_id]
        
        if not config_data:
            continue
        
        overall_scores = [j["scores"]["overall"] for j in config_data]
        
        stats_by_config[config_id] = {
            "n": len(config_data),
            "overall_mean": float(np.mean(overall_scores)),
            "overall_std": float(np.std(overall_scores, ddof=1)),
            "overall_median": float(np.median(overall_scores)),
            "overall_min": float(np.min(overall_scores)),
            "overall_max": float(np.max(overall_scores)),
            "accuracy_mean": float(np.mean([j["scores"]["accuracy"] for j in config_data])),
            "completeness_mean": float(np.mean([j["scores"]["completeness"] for j in config_data])),
            "clarity_mean": float(np.mean([j["scores"]["clarity"] for j in config_data])),
            "appropriateness_mean": float(np.mean([j["scores"]["appropriateness"] for j in config_data])),
            "creativity_mean": float(np.mean([j["scores"].get("creativity", 0) for j in config_data if j["scores"].get("creativity")]))
        }
    
    return stats_by_config


def pairwise_tests(judgments):
    """Perform pairwise t-tests between configs."""
    
    configs = ["baseline", "temp_only", "system_only", "full_lyra"]
    results = {}
    
    for i, config_a in enumerate(configs):
        for config_b in configs[i+1:]:
            
            scores_a = [j["scores"]["overall"] for j in judgments if j["config_id"] == config_a]
            scores_b = [j["scores"]["overall"] for j in judgments if j["config_id"] == config_b]
            
            if not scores_a or not scores_b:
                continue
            
            # T-test
            t_stat, p_value = stats.ttest_ind(scores_a, scores_b)
            
            # Cohen's d
            pooled_std = np.sqrt((np.var(scores_a, ddof=1) + np.var(scores_b, ddof=1)) / 2)
            cohens_d = (np.mean(scores_a) - np.mean(scores_b)) / pooled_std if pooled_std > 0 else 0
            
            results[f"{config_a}_vs_{config_b}"] = {
                "config_a": config_a,
                "config_b": config_b,
                "mean_a": float(np.mean(scores_a)),
                "mean_b": float(np.mean(scores_b)),
                "t_statistic": float(t_stat),
                "p_value": float(p_value),
                "cohens_d": float(cohens_d),
                "significant_005": bool(p_value < 0.05),
                "significant_001": bool(p_value < 0.01),
                "effect_size_interpretation": interpret_cohens_d(cohens_d)
            }
    
    return results


def interpret_cohens_d(d):
    """Interpret Cohen's d effect size."""
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    elif abs_d < 0.5:
        return "small"
    elif abs_d < 0.8:
        return "medium"
    else:
        return "large"


def domain_breakdown(judgments):
    """Breakdown by domain."""
    
    breakdown = {}
    
    for domain in ["technical", "creative", "analytical"]:
        domain_data = [j for j in judgments if j.get("domain") == domain]
        
        breakdown[domain] = {}
        
        for config_id in ["baseline", "temp_only", "system_only", "full_lyra"]:
            config_domain = [j for j in domain_data if j["config_id"] == config_id]
            
            if config_domain:
                breakdown[domain][config_id] = {
                    "overall_mean": float(np.mean([j["scores"]["overall"] for j in config_domain])),
                    "overall_std": float(np.std([j["scores"]["overall"] for j in config_domain], ddof=1)),
                    "n": len(config_domain)
                }
    
    return breakdown


def plot_attribution_chart(stats, pairwise, output_dir):
    """Plot effect sizes for attribution."""
    
    # Extract effect sizes relative to baseline
    effect_sizes = {
        "Temperature Only": pairwise.get("baseline_vs_temp_only", {}).get("cohens_d", 0),
        "System Prompt Only": pairwise.get("baseline_vs_system_only", {}).get("cohens_d", 0),
        "Full Lyra": pairwise.get("baseline_vs_full_lyra", {}).get("cohens_d", 0)
    }
    
    # Sort by absolute value
    items = sorted(effect_sizes.items(), key=lambda x: abs(x[1]), reverse=True)
    components = [item[0] for item in items]
    values = [item[1] for item in items]
    
    # Colors based on effect size magnitude
    colors = []
    for v in values:
        abs_v = abs(v)
        if abs_v < 0.2:
            colors.append('#FF6B6B')  # Red = negligible
        elif abs_v < 0.5:
            colors.append('#FFB347')  # Orange = small
        elif abs_v < 0.8:
            colors.append('#4ECDC4')  # Teal = medium
        else:
            colors.append('#45B7D1')  # Blue = large
    
    # Plot
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.barh(components, values, color=colors, edgecolor='black', linewidth=1.2)
    ax.axvline(0, color='black', linewidth=1.5)
    ax.axvline(0.2, color='gray', linestyle='--', alpha=0.5)
    ax.axvline(0.5, color='gray', linestyle='--', alpha=0.5)
    ax.axvline(0.8, color='gray', linestyle='--', alpha=0.5)
    ax.axvline(-0.2, color='gray', linestyle='--', alpha=0.5)
    ax.axvline(-0.5, color='gray', linestyle='--', alpha=0.5)
    ax.axvline(-0.8, color='gray', linestyle='--', alpha=0.5)
    
    ax.set_xlabel("Cohen's d (Effect Size vs Baseline)", fontsize=12, fontweight='bold')
    ax.set_title("Attribution Analysis: Component Effect Sizes", fontsize=14, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)
    
    # Add value labels
    for i, (comp, val) in enumerate(zip(components, values)):
        ax.text(val + 0.02 if val > 0 else val - 0.02, i, f"{val:.3f}", 
                va='center', ha='left' if val > 0 else 'right', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_dir / "attribution_chart.png", dpi=300, bbox_inches='tight')
    print(f"📊 Saved attribution chart")


def generate_report(stats, pairwise, domain_data, output_dir):
    """Generate markdown report."""
    
    report = []
    report.append("# Option B : Quick Validation Results\n")
    report.append(f"**Generated :** {Path.cwd()}\n")
    report.append("---\n\n")
    
    # Summary stats
    report.append("## Summary Statistics\n\n")
    report.append("| Config | N | Overall Mean ± SD | Accuracy | Completeness | Clarity |\n")
    report.append("|--------|---|-------------------|----------|--------------|----------|\n")
    
    for config_id in ["baseline", "temp_only", "system_only", "full_lyra"]:
        if config_id not in stats:
            continue
        s = stats[config_id]
        report.append(f"| {config_id} | {s['n']} | {s['overall_mean']:.2f} ± {s['overall_std']:.2f} | "
                     f"{s['accuracy_mean']:.2f} | {s['completeness_mean']:.2f} | {s['clarity_mean']:.2f} |\n")
    
    report.append("\n")
    
    # Pairwise tests
    report.append("## Pairwise Comparisons\n\n")
    
    for comparison, result in pairwise.items():
        report.append(f"### {comparison.replace('_', ' ').title()}\n\n")
        report.append(f"- **Cohen's d :** {result['cohens_d']:.3f} ({result['effect_size_interpretation']})\n")
        report.append(f"- **p-value :** {result['p_value']:.4f}\n")
        report.append(f"- **Significant (α=0.05) :** {'✅ Yes' if result['significant_005'] else '❌ No'}\n")
        report.append(f"- **Mean Difference :** {result['mean_b']-result['mean_a']:.3f}\n\n")
    
    # Go/No-Go
    report.append("---\n\n")
    report.append("## Go/No-Go Decision\n\n")
    
    any_significant = any(r['significant_005'] for r in pairwise.values())
    any_medium_effect = any(abs(r['cohens_d']) >= 0.3 for r in pairwise.values())
    
    if any_significant and any_medium_effect:
        report.append("### ✅ **GO** : Proceed to Full Evaluation (Option A)\n\n")
        report.append("**Rationale:**\n")
        report.append("- At least one significant difference detected (p < 0.05)\n")
        report.append("- Medium or larger effect size observed (|d| ≥ 0.3)\n")
        report.append("- Evidence suggests Lyra components have measurable impact\n\n")
        report.append("**Next Steps:**\n")
        report.append("1. Expand to 6 configs (add Creative, Analytical profiles)\n")
        report.append("2. Expand to 50 prompts (300 total responses)\n")
        report.append("3. Implement calibration dataset (50 examples)\n")
        report.append("4. Run full bias-corrected evaluation\n")
        report.append("5. Budget: ~$15-20, 1 week\n\n")
    else:
        report.append("### ❌ **NO-GO** : Pivot Strategy Recommended\n\n")
        report.append("**Rationale:**\n")
        report.append("- No significant differences detected (all p > 0.05)\n")
        report.append("- All effect sizes negligible (|d| < 0.3)\n")
        report.append("- LLM-as-judge may not detect quality differences\n\n")
        report.append("**Alternative Approaches:**\n")
        report.append("1. **Human Evaluation :** Mechanical Turk with expert raters\n")
        report.append("2. **Domain-Specific Focus :** Test on narrow use cases where Lyra excels\n")
        report.append("3. **Qualitative Analysis :** Case studies with detailed examination\n")
        report.append("4. **Repositioning :** Emphasize 'orchestration framework' over quality gains\n\n")
    
    # Save report
    with open(output_dir / "report.md", 'w') as f:
        f.write(''.join(report))
    
    print(f"📝 Saved report")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Analyze Option B results')
    parser.add_argument('--input', required=True, help='Path to judgments_unblinded.jsonl')
    parser.add_argument('--output', required=True, help='Output directory')
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load
    print(f"📂 Loading judgments from {args.input}")
    judgments = load_judgments(args.input)
    print(f"✅ Loaded {len(judgments)} judgments")
    
    # Analyze
    print("\n📊 Computing summary stats...")
    stats = compute_summary_stats(judgments)
    
    print("📊 Running pairwise tests...")
    pairwise = pairwise_tests(judgments)
    
    print("📊 Computing domain breakdown...")
    domain = domain_breakdown(judgments)
    
    # Save JSON
    print("\n💾 Saving results...")
    with open(output_dir / "summary_stats.json", 'w') as f:
        json.dump(stats, f, indent=2)
    
    with open(output_dir / "pairwise_tests.json", 'w') as f:
        json.dump(pairwise, f, indent=2)
    
    with open(output_dir / "domain_breakdown.json", 'w') as f:
        json.dump(domain, f, indent=2)
    
    # Visualize
    print("\n📈 Generating visualizations...")
    plot_attribution_chart(stats, pairwise, output_dir)
    
    # Report
    print("📝 Generating report...")
    generate_report(stats, pairwise, domain, output_dir)
    
    print(f"\n{'='*80}")
    print(f"✅ Analysis complete!")
    print(f"📁 Results saved to {output_dir}/")
    print(f"📄 Read report: {output_dir / 'report.md'}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
