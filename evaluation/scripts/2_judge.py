"""
2_judge.py
Blind judging with Claude Haiku 4.5 using triple-blind protocol.

The judge (Claude) NEVER sees:
- config_id
- execution_order
- latency_ms
- any metadata

Claude only sees: prompt, response, domain

Usage:
    python evaluation/scripts/2_judge.py
    
Output:
    evaluation/3_judgments/judgments_blind.jsonl
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List
import anthropic

# Rubric for consistent judging
JUDGMENT_RUBRIC = """
You are evaluating AI-generated responses to prompts. Rate each response on a scale of 1-5 for the following criteria:

**ACCURACY** (1-5):
- 5: Completely accurate, no factual errors
- 4: Mostly accurate, minor imprecision
- 3: Partially accurate, some errors
- 2: Mostly inaccurate
- 1: Completely wrong or nonsensical

**COMPLETENESS** (1-5):
- 5: Fully addresses all aspects of prompt
- 4: Addresses most aspects
- 3: Addresses some aspects, missing important points
- 2: Barely addresses prompt
- 1: Does not address prompt

**CLARITY** (1-5):
- 5: Crystal clear, well-structured, easy to understand
- 4: Clear, minor awkwardness
- 3: Understandable but unclear in places
- 2: Confusing, hard to follow
- 1: Incomprehensible

**COHERENCE** (1-5):
- 5: Perfectly coherent, logical flow
- 4: Mostly coherent, minor issues
- 3: Somewhat coherent, some disconnects
- 2: Poorly coherent
- 1: Incoherent

**APPROPRIATENESS** (1-5):
- 5: Perfectly appropriate tone/style/length for prompt
- 4: Mostly appropriate
- 3: Somewhat appropriate
- 2: Inappropriate in several ways
- 1: Completely inappropriate

**OVERALL** (1-5):
- Holistic assessment considering all factors above

Return your judgment as JSON (ONLY valid JSON, no markdown):
{
  "accuracy": <1-5>,
  "completeness": <1-5>,
  "clarity": <1-5>,
  "coherence": <1-5>,
  "appropriateness": <1-5>,
  "overall": <1-5>,
  "reasoning": "<2-3 sentence brief explanation of overall score>"
}

IMPORTANT:
- Be consistent and objective
- Do NOT favor any response based on position or length
- Do NOT try to guess which system generated the response
- Judge ONLY on quality of response to the prompt
"""


def judge_responses(
    blind_file: str = "evaluation/2_blind_data/responses_blind.jsonl",
    output_file: str = "evaluation/3_judgments/judgments_blind.jsonl",
    batch_size: int = 3,
    pause_between_batches: int = 2
) -> List[Dict]:
    """
    Judge blind responses with Claude Haiku 4.5.
    
    Args:
        blind_file: Input blind responses
        output_file: Output judgments
        batch_size: Pause after N requests (rate limiting)
        pause_between_batches: Seconds to pause
    """
    
    # Get API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY environment variable not set")
        print("   Set it with: $env:ANTHROPIC_API_KEY='your-key-here'")
        return []
    
    # Create output directory
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    # Load blind responses
    blind_responses = []
    try:
        with open(blind_file, 'r') as f:
            blind_responses = [json.loads(line) for line in f]
    except FileNotFoundError:
        print(f"❌ Blind file not found: {blind_file}")
        print(f"   Run: python evaluation/scripts/1_anonymize.py")
        return []
    
    if not blind_responses:
        print(f"❌ No responses found in {blind_file}")
        return []
    
    # Initialize Claude client
    client = anthropic.Anthropic(api_key=api_key)
    
    # Judge responses
    judgments = []
    successful = 0
    failed = 0
    
    print("=" * 80)
    print("JUDGING WITH CLAUDE HAIKU 4.5 (TRIPLE-BLIND)")
    print("=" * 80)
    print(f"Evaluating {len(blind_responses)} responses...")
    print()
    
    for i, response in enumerate(blind_responses, 1):
        resp_id = response['id']
        print(f"[{i}/{len(blind_responses)}] Judging {resp_id}...", end=" ", flush=True)
        
        # Build judge prompt
        judge_prompt = f"""{JUDGMENT_RUBRIC}

---

**PROMPT:**
{response['prompt']}

**DOMAIN:**
{response['domain']}

**RESPONSE TO EVALUATE:**
{response['response']}

---

Provide your judgment as JSON only (no markdown, no explanation before JSON)."""
        
        try:
            # Call Claude Haiku
            message = client.messages.create(
                model="claude-haiku-4.5-20251022",
                max_tokens=300,
                temperature=0.3,  # Low temp for consistency
                messages=[{
                    "role": "user",
                    "content": judge_prompt
                }]
            )
            
            # Extract and parse response
            judgment_text = message.content[0].text.strip()
            
            # Handle markdown wrapping
            if "```json" in judgment_text:
                judgment_text = judgment_text.split("```json")[1].split("```")[0].strip()
            elif "```" in judgment_text:
                judgment_text = judgment_text.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            try:
                judgment = json.loads(judgment_text)
            except json.JSONDecodeError:
                print(f"⚠️  JSON parse error, trying to extract...")
                # Try to find JSON in response
                start = judgment_text.find('{')
                end = judgment_text.rfind('}') + 1
                if start >= 0 and end > start:
                    judgment = json.loads(judgment_text[start:end])
                else:
                    raise ValueError("Could not find valid JSON")
            
            # Ensure all required fields
            judgment_record = {
                "id": resp_id,
                "domain": response['domain'],
                "accuracy": judgment.get("accuracy", 3),
                "completeness": judgment.get("completeness", 3),
                "clarity": judgment.get("clarity", 3),
                "coherence": judgment.get("coherence", 3),
                "appropriateness": judgment.get("appropriateness", 3),
                "overall": judgment.get("overall", 3),
                "reasoning": judgment.get("reasoning", ""),
                "timestamp": message.id
            }
            
            judgments.append(judgment_record)
            successful += 1
            
            print(f"✓ Overall: {judgment_record['overall']}/5")
            
            # Save incrementally
            with open(output_file, 'a') as f:
                f.write(json.dumps(judgment_record) + '\n')
        
        except Exception as e:
            print(f"✗ Error: {str(e)[:60]}")
            failed += 1
            
            # Log error but continue
            error_record = {
                "id": resp_id,
                "domain": response['domain'],
                "error": str(e)[:200],
                "overall": None
            }
            judgments.append(error_record)
            
            with open(output_file, 'a') as f:
                f.write(json.dumps(error_record) + '\n')
        
        # Rate limiting pause
        if i % batch_size == 0 and i < len(blind_responses):
            print(f"   [Pausing {pause_between_batches}s to avoid rate limits...]")
            time.sleep(pause_between_batches)
    
    # Summary
    print()
    print("=" * 80)
    print(f"✅ JUDGING COMPLETE")
    print("=" * 80)
    print(f"  Successful: {successful}/{len(blind_responses)}")
    print(f"  Failed: {failed}/{len(blind_responses)}")
    print(f"  Output: {output_file}")
    print()
    print(f"Next step: python evaluation/scripts/3_unblind.py")
    print("=" * 80)
    
    return judgments


if __name__ == "__main__":
    judge_responses()
