"""
Judge responses with Claude Haiku 4.5 in blind mode.

Usage:
    export ANTHROPIC_API_KEY="sk-..."
    python evaluation/scripts/3_judge_blind.py
    
Output:
    evaluation/3_judgments/judgments_blind.jsonl
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, Optional

# Try to import anthropic
try:
    from anthropic import Anthropic
except ImportError:
    print("Error: anthropic module not installed")
    print("Install with: pip install anthropic")
    exit(1)

# ============================================================================
# JUDGMENT RUBRIC
# ============================================================================

JUDGMENT_RUBRIC = """
You are evaluating AI-generated responses to prompts. Rate each response on a scale of 1-5 for the following criteria:

ACCURACY (1-5):
- 5: Completely accurate, no errors
- 4: Mostly accurate, minor imprecision
- 3: Partially accurate, some errors
- 2: Mostly inaccurate
- 1: Completely wrong

COMPLETENESS (1-5):
- 5: Fully addresses all aspects of prompt
- 4: Addresses most aspects
- 3: Addresses some aspects, missing important points
- 2: Barely addresses prompt
- 1: Does not address prompt

CLARITY (1-5):
- 5: Crystal clear, well-structured
- 4: Clear, minor awkwardness
- 3: Understandable but unclear in places
- 2: Confusing, hard to follow
- 1: Incomprehensible

APPROPRIATENESS (1-5):
- 5: Perfectly appropriate tone/style for prompt
- 4: Mostly appropriate
- 3: Somewhat appropriate
- 2: Inappropriate in several ways
- 1: Completely inappropriate

RELEVANCE (1-5):
- 5: Entirely on-topic
- 4: Mostly on-topic
- 3: Partially on-topic
- 2: Mostly off-topic
- 1: Completely off-topic

OVERALL (1-5):
- Holistic assessment considering all factors

Return ONLY a JSON object with no markdown, no code blocks:
{"accuracy": <1-5>, "completeness": <1-5>, "clarity": <1-5>, "appropriateness": <1-5>, "relevance": <1-5>, "overall": <1-5>, "reasoning": "<brief 1-2 sentence summary>"}

Be consistent and objective across all responses.
"""


def judge_with_claude_haiku(
    blind_file: str = "evaluation/2_blind_data/responses_blind.jsonl",
    output_file: str = "evaluation/3_judgments/judgments_blind.jsonl",
    batch_size: int = 5
):
    """
    Evaluate responses with Claude Haiku in blind mode.
    """
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        print("Set it with: export ANTHROPIC_API_KEY='sk-...'")
        return None
    
    blind_path = Path(blind_file)
    if not blind_path.exists():
        print(f"ERROR: Blind data file not found: {blind_file}")
        return None
    
    client = Anthropic(api_key=api_key)
    
    # Load blind responses
    with open(blind_path, 'r', encoding='utf-8') as f:
        responses = [json.loads(line) for line in f if line.strip()]
    
    if not responses:
        print(f"ERROR: No responses found in {blind_file}")
        return None
    
    # Create output directory
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Clear if exists
    if output_path.exists():
        output_path.unlink()
    
    print("=" * 80)
    print("BLIND JUDGING WITH CLAUDE HAIKU 4.5")
    print("=" * 80)
    print(f"Responses to judge: {len(responses)}")
    print(f"Batch size: {batch_size} (pause between batches to avoid rate limits)")
    print(f"Output: {output_path}")
    print("=" * 80)
    print()
    
    judgments = []
    errors = 0
    
    for i, response in enumerate(responses):
        anon_id = response.get('id')
        prompt = response.get('prompt')
        text = response.get('response')
        domain = response.get('domain')
        
        print(f"[{i+1:2d}/{len(responses)}] {anon_id} ({domain:10s}) | {prompt[:40]:40s}... ", end="", flush=True)
        
        try:
            # Build judgment prompt
            judge_prompt = f"""{JUDGMENT_RUBRIC}

---

PROMPT:
{prompt}

DOMAIN:
{domain}

RESPONSE TO EVALUATE:
{text}

---

Return ONLY valid JSON with no markdown:"""
            
            # Call Claude Haiku 4.5
            message = client.messages.create(
                model="claude-haiku-4.5-20251022",
                max_tokens=300,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": judge_prompt
                }]
            )
            
            # Parse response
            judgment_text = message.content[0].text.strip()
            
            # Extract JSON
            if "```json" in judgment_text:
                judgment_text = judgment_text.split("```json")[1].split("```")[0]
            elif "```" in judgment_text:
                judgment_text = judgment_text.split("```")[1].split("```")[0]
            
            # Clean JSON
            judgment_text = judgment_text.strip()
            if judgment_text.startswith('{'):
                pass  # Already JSON
            elif judgment_text.startswith('```'):
                judgment_text = judgment_text[3:]
            
            judgment = json.loads(judgment_text)
            
            # Add metadata
            judgment['id'] = anon_id
            judgment['domain'] = domain
            judgment['judged_at'] = message.id
            
            judgments.append(judgment)
            
            print(f"OK (overall: {judgment.get('overall', '?')}/5)")
            
            # Save incrementally
            with open(output_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(judgment) + '\n')
        
        except json.JSONDecodeError as e:
            errors += 1
            print(f"JSON ERROR: {str(e)[:40]}")
            judgments.append({
                'id': anon_id,
                'domain': domain,
                'error': f"JSON parse failed: {str(e)[:50]}",
                'overall': None
            })
            with open(output_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(judgments[-1]) + '\n')
        
        except Exception as e:
            errors += 1
            print(f"ERROR: {str(e)[:40]}")
            judgments.append({
                'id': anon_id,
                'domain': domain,
                'error': str(e)[:50],
                'overall': None
            })
            with open(output_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(judgments[-1]) + '\n')
        
        # Pause between batches
        if (i + 1) % batch_size == 0 and i + 1 < len(responses):
            wait_time = 3
            print(f"\n--- Batch {(i+1)//batch_size} complete. Pausing {wait_time}s to avoid rate limits ---\n")
            time.sleep(wait_time)
    
    print()
    print("=" * 80)
    print(f"Judging Complete")
    print(f"  Total: {len(judgments)}")
    print(f"  Success: {len(judgments) - errors}")
    print(f"  Errors: {errors}")
    print(f"  Output: {output_path}")
    print("=" * 80)
    
    return output_path


if __name__ == "__main__":
    judge_with_claude_haiku()
