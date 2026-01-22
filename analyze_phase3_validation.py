"""
PHASE 3 - VALIDATION ANALYSIS
=============================

Analyze validation benchmark results to test 4 hypotheses:
1. H1: Temperature affects latency
2. H2: Ollama parameters affect latency
3. H3: Execution order (warm-up) affects latency
4. H4: Response length correlates with latency

Usage:
    python analyze_phase3_validation.py validation_results.jsonl
"""

import json
import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List, Tuple
import sys


def load_results(jsonl_file: str) -> pd.DataFrame:
    """Load JSONL results into DataFrame"""
    with open(jsonl_file) as f:
        data = [json.loads(line) for line in f if line.strip()]
    
    df = pd.DataFrame(data)
    return df


def test_hypothesis_1_temperature(df: pd.DataFrame):
    """
    H1: Temperature affects latency
    
    Compare:
    - raw_default (temp unknown/default)
    - raw_temp_0.8 (temp explicit, same as baseline)
    - raw_temp_0.615 (lower temp, same as Lyra Creative)
    - lyra_creative (temp 0.615 via tau_c=1.3)
    """
    print("\n" + "="*80)
    print("HYPOTHESIS 1: Temperature Impact on Latency")
    print("="*80)
    
    configs = ["raw_default", "raw_temp_0.8", "raw_temp_0.615", "lyra_creative"]
    
    for order in ["normal", "reversed"]:
        print(f"\n--- Execution Order: {order.upper()} ---")
        
        subset = df[df["execution_order"] == order]
        
        for config in configs:
            data = subset[subset["config_id"] == config]
            if len(data) > 0:
                latency = data["latency_ms"].mean()
                std = data["latency_ms"].std()
                coherence_proxy = data["tokens_approx"].mean()  # More tokens = better coherence
                
                print(f"  {config:20} | latency={latency:7.1f}ms ± {std:5.1f} | tokens={coherence_proxy:5.1f}")
    
    # Statistical test: temp_0.615 vs temp_0.8
    print("\n--- T-Test: temp_0.615 vs temp_0.8 (normal order) ---")
    
    normal = df[df["execution_order"] == "normal"]
    
    temp_low = normal[normal["config_id"] == "raw_temp_0.615"]["latency_ms"]
    temp_high = normal[normal["config_id"] == "raw_temp_0.8"]["latency_ms"]
    
    if len(temp_low) > 1 and len(temp_high) > 1:
        t_stat, p_value = stats.ttest_ind(temp_low, temp_high)
        delta = temp_low.mean() - temp_high.mean()
        delta_pct = (delta / temp_high.mean()) * 100 if temp_high.mean() > 0 else 0
        
        print(f"\n  Raw Temp 0.615 latency: {temp_low.mean():.1f}ms")
        print(f"  Raw Temp 0.8 latency:   {temp_high.mean():.1f}ms")
        print(f"  Δ: {delta:+.1f}ms ({delta_pct:+.1f}%)")
        print(f"  T-statistic: {t_stat:.3f}")
        print(f"  P-value: {p_value:.4f}")
        print(f"  Significant: {'YES (p < 0.05)' if p_value < 0.05 else 'NO (p >= 0.05)'}")
        
        print(f"\nInterpretation:")
        if p_value < 0.05:
            print(f"  → Temperature DOES affect latency")
            print(f"  → Lower temperature (0.615) makes responses {'faster' if delta < 0 else 'slower'}")
        else:
            print(f"  → No statistically significant difference between temperatures")


def test_hypothesis_2_parameters(df: pd.DataFrame):
    """
    H2: Ollama parameters affect latency
    
    Compare:
    - raw_default (implicit params)
    - raw_explicit (explicit params matching Lyra: temp, num_predict, top_k, top_p)
    - lyra_balanced (same params via framework)
    """
    print("\n" + "="*80)
    print("HYPOTHESIS 2: Ollama Parameters Impact")
    print("="*80)
    
    configs = ["raw_default", "raw_explicit", "lyra_balanced"]
    
    for order in ["normal", "reversed"]:
        print(f"\n--- Execution Order: {order.upper()} ---")
        
        subset = df[df["execution_order"] == order]
        
        for config in configs:
            data = subset[subset["config_id"] == config]
            if len(data) > 0:
                latency = data["latency_ms"].mean()
                std = data["latency_ms"].std()
                tokens = data["tokens_approx"].mean()
                
                print(f"  {config:20} | latency={latency:7.1f}ms ± {std:5.1f} | tokens={tokens:5.1f}")
    
    # Statistical test: explicit vs default
    print("\n--- T-Test: raw_explicit vs raw_default (normal order) ---")
    
    normal = df[df["execution_order"] == "normal"]
    
    raw_def = normal[normal["config_id"] == "raw_default"]["latency_ms"]
    raw_exp = normal[normal["config_id"] == "raw_explicit"]["latency_ms"]
    lyra_bal = normal[normal["config_id"] == "lyra_balanced"]["latency_ms"]
    
    if len(raw_def) > 1 and len(raw_exp) > 1:
        t_stat, p_value = stats.ttest_ind(raw_def, raw_exp)
        delta_explicit = raw_exp.mean() - raw_def.mean()
        delta_pct = (delta_explicit / raw_def.mean()) * 100 if raw_def.mean() > 0 else 0
        
        print(f"\n  Raw Default latency:   {raw_def.mean():.1f}ms")
        print(f"  Raw Explicit latency:  {raw_exp.mean():.1f}ms")
        print(f"  Δ: {delta_explicit:+.1f}ms ({delta_pct:+.1f}%)")
        print(f"  P-value: {p_value:.4f}")
        print(f"  Significant: {'YES' if p_value < 0.05 else 'NO'}")
    
    # Compare raw_explicit to lyra_balanced
    if len(raw_exp) > 1 and len(lyra_bal) > 1:
        print(f"\n--- T-Test: lyra_balanced vs raw_explicit (normal order) ---")
        
        t_stat, p_value = stats.ttest_ind(lyra_bal, raw_exp)
        delta_lyra = lyra_bal.mean() - raw_exp.mean()
        delta_pct = (delta_lyra / raw_exp.mean()) * 100 if raw_exp.mean() > 0 else 0
        
        print(f"\n  Raw Explicit latency:  {raw_exp.mean():.1f}ms")
        print(f"  Lyra Balanced latency: {lyra_bal.mean():.1f}ms")
        print(f"  Δ: {delta_lyra:+.1f}ms ({delta_pct:+.1f}%)")
        print(f"  P-value: {p_value:.4f}")
        print(f"  Significant: {'YES' if p_value < 0.05 else 'NO'}")
        
        print(f"\nInterpretation:")
        if p_value < 0.05 and delta_lyra < 0:
            print(f"  → Lyra framework overhead DOES NOT negate parameter optimization")
            print(f"  → Lyra is actually FASTER than raw with same parameters")
        elif p_value < 0.05 and delta_lyra > 0:
            print(f"  → Lyra framework adds {delta_lyra:.1f}ms overhead vs raw")
        else:
            print(f"  → No significant difference between Lyra and Raw with same parameters")


def test_hypothesis_3_warmup(df: pd.DataFrame):
    """
    H3: Execution order affects latency (warm-up hypothesis)
    
    If Ollama gets faster with multiple requests (GPU warm-up, caching),
    then reversing order should change latencies.
    """
    print("\n" + "="*80)
    print("HYPOTHESIS 3: Warm-up / Execution Order Effect")
    print("="*80)
    
    configs_to_compare = ["raw_default", "lyra_balanced", "lyra_creative"]
    
    print("\n--- Comparing same config across execution orders ---\n")
    
    significant_count = 0
    
    for config in configs_to_compare:
        normal = df[(df["config_id"] == config) & (df["execution_order"] == "normal")]
        reversed_data = df[(df["config_id"] == config) & (df["execution_order"] == "reversed")]
        
        if len(normal) > 1 and len(reversed_data) > 1:
            lat_normal = normal["latency_ms"].mean()
            lat_reversed = reversed_data["latency_ms"].mean()
            delta = lat_reversed - lat_normal
            delta_pct = (delta / lat_normal) * 100 if lat_normal > 0 else 0
            
            # T-test
            t_stat, p_value = stats.ttest_ind(
                normal["latency_ms"],
                reversed_data["latency_ms"]
            )
            
            is_sig = "***" if p_value < 0.05 else "   "
            print(f"{config:20} {is_sig}")
            print(f"  Normal order:   {lat_normal:7.1f}ms")
            print(f"  Reversed order: {lat_reversed:7.1f}ms")
            print(f"  Δ: {delta:+.1f}ms ({delta_pct:+.1f}%)")
            print(f"  p-value: {p_value:.4f}\n")
            
            if p_value < 0.05:
                significant_count += 1
    
    print(f"--- Summary ---")
    print(f"Configs with significant order effect: {significant_count}/{len(configs_to_compare)}")
    
    if significant_count >= 2:
        print(f"\nInterpretation:")
        print(f"  → Strong evidence of WARM-UP effect")
        print(f"  → Ollama gets significantly faster with repeated requests")
        print(f"  → This could explain part of Lyra's gain (Lyra is cached, Raw is not)")
    else:
        print(f"\nInterpretation:")
        print(f"  → Warm-up effect is MINIMAL or NON-EXISTENT")
        print(f"  → Performance differences are likely NOT due to execution order")


def test_hypothesis_4_length(df: pd.DataFrame):
    """
    H4: Response length correlates with latency
    
    If Lyra generates shorter responses, latency will be lower
    regardless of other factors.
    """
    print("\n" + "="*80)
    print("HYPOTHESIS 4: Response Length Correlation with Latency")
    print("="*80)
    
    # Overall correlation
    corr, p_value = stats.pearsonr(df["tokens_approx"], df["latency_ms"])
    
    print(f"\nOverall Correlation (tokens vs latency):")
    print(f"  Pearson r: {corr:.4f}")
    print(f"  P-value: {p_value:.4f}")
    print(f"  Significance: {'YES (p < 0.05)' if p_value < 0.05 else 'NO (p >= 0.05)'}")
    
    if abs(corr) > 0.3 and p_value < 0.05:
        print(f"  Interpretation: STRONG correlation (response length affects latency)")
    elif abs(corr) > 0.1 and p_value < 0.05:
        print(f"  Interpretation: WEAK correlation (response length has some effect)")
    else:
        print(f"  Interpretation: NO significant correlation (length is NOT a factor)")
    
    # Per-config average tokens
    print(f"\n--- Average Response Length per Config (normal order only) ---\n")
    
    normal = df[df["execution_order"] == "normal"]
    
    for config in sorted(normal["config_id"].unique()):
        subset = normal[normal["config_id"] == config]
        tokens_mean = subset["tokens_approx"].mean()
        latency_mean = subset["latency_ms"].mean()
        
        config_label = subset["config_label"].iloc[0] if len(subset) > 0 else config
        
        print(f"{config:20} | tokens={tokens_mean:6.1f} | latency={latency_mean:7.1f}ms")
    
    # Analyze if Lyra generates shorter responses
    print(f"\n--- Do Lyra configs generate shorter responses? ---")
    
    raw_avg = df[(df["execution_order"] == "normal") & (df["config_id"].str.startswith("raw_"))]["tokens_approx"].mean()
    lyra_avg = df[(df["execution_order"] == "normal") & (df["config_id"].str.startswith("lyra_"))]["tokens_approx"].mean()
    
    print(f"\n  Raw configs avg:   {raw_avg:.1f} tokens")
    print(f"  Lyra configs avg:  {lyra_avg:.1f} tokens")
    print(f"  Δ: {lyra_avg - raw_avg:+.1f} tokens ({((lyra_avg - raw_avg) / raw_avg * 100):+.1f}%)")


def generate_summary(df: pd.DataFrame):
    """Generate executive summary"""
    print("\n\n" + "="*80)
    print("VALIDATION SUMMARY & CONCLUSIONS")
    print("="*80)
    
    # Core result: Lyra vs Raw Default (normal order only)
    normal = df[df["execution_order"] == "normal"]
    
    raw_default = normal[normal["config_id"] == "raw_default"]["latency_ms"].mean()
    lyra_balanced = normal[normal["config_id"] == "lyra_balanced"]["latency_ms"].mean()
    raw_explicit = normal[normal["config_id"] == "raw_explicit"]["latency_ms"].mean()
    
    delta_vs_default = lyra_balanced - raw_default
    delta_pct_default = (delta_vs_default / raw_default) * 100 if raw_default > 0 else 0
    
    delta_vs_explicit = lyra_balanced - raw_explicit
    delta_pct_explicit = (delta_vs_explicit / raw_explicit) * 100 if raw_explicit > 0 else 0
    
    print(f"\nPERFORMANCE (Normal Execution Order, 10 prompts each):")
    print(f"  Raw Default:    {raw_default:7.1f}ms")
    print(f"  Raw Explicit:   {raw_explicit:7.1f}ms")
    print(f"  Lyra Balanced:  {lyra_balanced:7.1f}ms")
    print(f"\nLyra vs Raw Default: {delta_vs_default:+.1f}ms ({delta_pct_default:+.1f}%) [ORIGINAL FINDING]")
    print(f"Lyra vs Raw Explicit: {delta_vs_explicit:+.1f}ms ({delta_pct_explicit:+.1f}%)")
    
    # Interpret
    print(f"\n--- INTERPRETATION ---")
    
    if delta_vs_default > 200:
        print(f"\n⚠️  FINDING IS INVALIDATED")
        print(f"Lyra is SLOWER than Raw by {abs(delta_vs_default):.0f}ms")
        print(f"This contradicts the original Phase 3 results.")
        
    elif -200 <= delta_vs_default <= 200:
        print(f"\n⚠️  FINDING IS SUSPICIOUS")
        print(f"Lyra latency difference is within noise margin (±200ms)")
        print(f"Original 12% gain may be due to:")
        if delta_vs_explicit < -100:
            print(f"  - Parameter differences (raw_explicit slower than raw_default)")
        else:
            print(f"  - Execution order/warm-up effects")
        
    elif delta_vs_default < -200:
        print(f"\n✓ FINDING IS VALIDATED")
        print(f"Lyra is FASTER than Raw by {abs(delta_vs_default):.0f}ms ({abs(delta_pct_default):.1f}%)")
        
        if delta_vs_explicit > 50:
            print(f"Lyra also faster than explicit parameters ({delta_vs_explicit:.0f}ms)")
            print(f"This suggests Lyra framework adds value beyond parameter tuning")
        else:
            print(f"But Raw with explicit params nearly matches Lyra")
            print(f"Suggests parameters are main factor, not framework")
    
    # Recommendation
    print(f"\n--- RECOMMENDATION ---")
    
    n_results = len(df)
    if n_results < 120:
        print(f"\n⚠️  INCOMPLETE DATA ({n_results}/120 results)")
        print(f"Need to rerun benchmark completely")
        recommendation = "RERUN_INCOMPLETE"
    elif delta_vs_default < -100:
        print(f"\n✓ PROCEED WITH COMMUNICATION")
        print(f"Lyra shows measurable performance gain")
        print(f"Report clearly documents methodology and sources")
        recommendation = "COMMUNICATE"
    elif delta_vs_explicit < -50:
        print(f"\n✓ PARTIAL COMMUNICATION OK")
        print(f"Gain exists but is parameter-dependent")
        print(f"Frame as: 'Lyra's intelligent parameter selection'")
        recommendation = "COMMUNICATE_PARTIAL"
    else:
        print(f"\n✗ DO NOT COMMUNICATE")
        print(f"No validated performance gain found")
        print(f"Use for internal process documentation instead")
        recommendation = "DO_NOT_COMMUNICATE"
    
    return recommendation


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_phase3_validation.py validation_results.jsonl")
        sys.exit(1)
    
    jsonl_file = sys.argv[1]
    
    print("="*80)
    print("PHASE 3 - VALIDATION ANALYSIS")
    print("="*80)
    print(f"\nLoading: {jsonl_file}")
    
    try:
        df = load_results(jsonl_file)
    except FileNotFoundError:
        print(f"ERROR: File not found: {jsonl_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in file: {e}")
        sys.exit(1)
    
    print(f"\nDataset Statistics:")
    print(f"  Total results: {len(df)}")
    print(f"  Configurations: {df['config_id'].nunique()}")
    print(f"  Execution orders: {df['execution_order'].unique().tolist()}")
    print(f"  Domains: {df['domain'].unique().tolist()}")
    
    # Run all hypothesis tests
    test_hypothesis_1_temperature(df)
    test_hypothesis_2_parameters(df)
    test_hypothesis_3_warmup(df)
    test_hypothesis_4_length(df)
    
    # Generate summary
    recommendation = generate_summary(df)
    
    print("\n" + "="*80)
    print("✓ Analysis complete")
    print("="*80)
    
    return recommendation


if __name__ == "__main__":
    main()
