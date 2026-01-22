#!/usr/bin/env python3
"""Display comprehensive benchmark statistics"""

import json
import statistics
from pathlib import Path

# Try to find the repaired version first, fall back to original
target_dir = Path('benchmark_results/phase2_comprehensive_20251203_223951')
repaired_file = target_dir / 'phase2_comprehensive_20251203_223951_export_REPAIRED.jsonl'
original_file = target_dir / 'phase2_comprehensive_20251203_223951_export.jsonl'

file_path = repaired_file if repaired_file.exists() else original_file

# Parse all messages
messages = []
with open(file_path, 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            messages.append(json.loads(line))

print('✅ COMPREHENSIVE BENCHMARK ARCHIVE - FINAL STATS')
print('=' * 80)
print(f'\nTotal messages archived: {len(messages)}')
domains_set = set(m['domain'] for m in messages)
print(f'Domains covered: {len(domains_set)} - {", ".join(sorted(domains_set))}')

# Stats by domain
domains = {}
for msg in messages:
    d = msg['domain']
    if d not in domains:
        domains[d] = []
    domains[d].append(msg)

print('\nBREAKDOWN BY DOMAIN:')
print('-' * 80)
for domain in sorted(domains.keys()):
    msgs = domains[domain]
    latencies = [m['latency_ms'] for m in msgs]
    coherences = [m['coherence'] for m in msgs]
    stabilities = [m['stability'] for m in msgs]
    
    print(f'\n  {domain.upper()}: {len(msgs)} messages')
    avg_lat = statistics.mean(latencies)
    std_lat = statistics.stdev(latencies) if len(latencies) > 1 else 0
    print(f'    Latency: {avg_lat:.0f}ms ± {std_lat:.0f}ms')
    print(f'    Coherence: {statistics.mean(coherences):.3f} (avg)')
    print(f'    Stability: {statistics.mean(stabilities):.3f} (avg)')
    
    response_lens = [len(m['response_text']) for m in msgs]
    print(f'    Response length: {statistics.mean(response_lens):.0f} chars (avg)')

# Overall
all_latencies = [m['latency_ms'] for m in messages]
all_coherences = [m['coherence'] for m in messages]
all_stabilities = [m['stability'] for m in messages]

print('\n\nOVERALL STATISTICS:')
print('-' * 80)
total_latency = sum(all_latencies)
print(f'  Total latency: {total_latency:.0f}ms')
print(f'  Avg latency per message: {statistics.mean(all_latencies):.0f}ms')
print(f'  Latency range: {min(all_latencies):.0f}ms - {max(all_latencies):.0f}ms')
print(f'  Avg coherence: {statistics.mean(all_coherences):.3f}')
print(f'  Avg stability: {statistics.mean(all_stabilities):.3f}')

total_prompt_tokens = sum(m['tokens_prompt'] for m in messages)
total_response_tokens = sum(m['tokens_response'] for m in messages)
print(f'  Total prompt tokens: {total_prompt_tokens}')
print(f'  Total response tokens: {total_response_tokens}')

print('\n✅ Archive ready for analysis!')
print(f'📁 Location: benchmark_results/phase2_comprehensive_20251203_223951/')
print(f'📄 Export: phase2_comprehensive_20251203_223951_export.jsonl')
print('=' * 80)
