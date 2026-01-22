"""
Generate 60 responses for Option B quick validation.

Usage:
    python evaluation/scripts/1_generate_responses_optionB.py
    
Output:
    evaluation/1_source_data/responses_raw.jsonl
"""

import asyncio
import json
import time
from pathlib import Path
from datetime import datetime
import httpx
import sys

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIGS = {
    "baseline": {
        "name": "Raw Default",
        "consciousness_level": 0,
        "profile": "balanced",
        "enable_context": False
    },
    "temp_only": {
        "name": "Temperature Only",
        "consciousness_level": 0,
        "profile": "balanced",
        "enable_context": False
    },
    "system_only": {
        "name": "System Prompt Only",
        "consciousness_level": 0,
        "profile": "balanced",
        "enable_context": False
    },
    "full_lyra": {
        "name": "Full Lyra Balanced",
        "consciousness_level": 1,
        "profile": "balanced",
        "enable_context": True
    }
}

PROMPTS = {
    "technical": [
        "Explain the difference between TCP and UDP protocols.",
        "What is the time complexity of quicksort in the worst case?",
        "Describe how photosynthesis works at the molecular level.",
        "What are the key differences between supervised and unsupervised learning?",
        "Explain the concept of virtual memory in operating systems."
    ],
    "creative": [
        "Write a short story about a robot learning to paint.",
        "Imagine a world where time flows backwards. Describe a typical day.",
        "Create a metaphor that explains quantum entanglement to a child.",
        "Design a new sport that could be played in zero gravity.",
        "Write a poem about the intersection of mathematics and nature."
    ],
    "analytical": [
        "Compare the advantages and disadvantages of functional vs object-oriented programming.",
        "Analyze the ethical implications of AI-generated art.",
        "What are the trade-offs between microservices and monolithic architectures?",
        "Evaluate the impact of social media on political discourse.",
        "Compare renewable energy sources: solar vs wind vs hydroelectric."
    ]
}

API_URL = "http://localhost:8000/chat/message"
OUTPUT_DIR = Path("evaluation/1_source_data")
OUTPUT_FILE = OUTPUT_DIR / "responses_raw.jsonl"

# ============================================================================
# GENERATION
# ============================================================================

async def generate_response(
    prompt: str,
    domain: str,
    config_id: str,
    config: dict,
    session: httpx.AsyncClient,
    attempt: int = 1
) -> dict:
    """Generate single response."""
    
    payload = {
        "text": prompt,
        "session_id": f"optionB_{config_id}",
        "profile": config["profile"],
        "consciousness_level": config["consciousness_level"],
        "enable_context": config.get("enable_context", False)
    }
    
    start = time.time()
    
    try:
        response = await session.post(API_URL, json=payload, timeout=300.0)
        response.raise_for_status()
        data = response.json()
        
        latency_ms = (time.time() - start) * 1000
        
        return {
            "config_id": config_id,
            "config_label": config["name"],
            "prompt": prompt,
            "domain": domain,
            "response": data.get("text", ""),
            "latency_ms": latency_ms,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "execution_order": "normal"
        }
    
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        
        if attempt < 3:
            print(f"  ⚠ Retry {attempt}/2 after {latency_ms:.0f}ms...")
            await asyncio.sleep(2)
            return await generate_response(prompt, domain, config_id, config, session, attempt + 1)
        
        print(f"  ✗ Failed: {str(e)[:60]}")
        return {
            "config_id": config_id,
            "config_label": config["name"],
            "prompt": prompt,
            "domain": domain,
            "response": f"ERROR: {str(e)[:100]}",
            "latency_ms": latency_ms,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "execution_order": "normal",
            "error": True
        }


async def generate_all_responses():
    """Generate all 60 responses."""
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    total_prompts = sum(len(p) for p in PROMPTS.values())
    total_responses = total_prompts * len(CONFIGS)
    
    print("=" * 80)
    print("OPTION B - RESPONSE GENERATION")
    print("=" * 80)
    print(f"Configurations: {len(CONFIGS)}")
    print(f"Prompts per domain: {total_prompts // 3} × 3 domains = {total_prompts}")
    print(f"Total responses: {total_prompts} prompts × {len(CONFIGS)} configs = {total_responses}")
    print(f"Output: {OUTPUT_FILE}")
    print("=" * 80)
    print()
    
    async with httpx.AsyncClient(timeout=300.0) as session:
        
        count = 0
        errors = 0
        
        # Flatten prompts with domains
        prompt_list = []
        for domain, prompts in PROMPTS.items():
            for prompt in prompts:
                prompt_list.append((domain, prompt))
        
        # Generate for each config
        for config_id, config in CONFIGS.items():
            print(f"\n[{config['name']}]")
            
            for domain, prompt in prompt_list:
                count += 1
                print(f"  [{count:2d}/{total_responses}] {domain:10s} | {prompt[:50]:50s}... ", end="", flush=True)
                
                try:
                    result = await generate_response(prompt, domain, config_id, config, session)
                    
                    if result.get("error"):
                        errors += 1
                        print(f"ERR")
                    else:
                        print(f"OK ({result['latency_ms']:.0f}ms)")
                    
                    # Save incrementally
                    with open(OUTPUT_FILE, 'a') as f:
                        f.write(json.dumps(result) + '\n')
                    
                    await asyncio.sleep(0.5)  # Rate limit
                
                except Exception as e:
                    errors += 1
                    print(f"FAIL: {str(e)[:40]}")
        
        print()
        print("=" * 80)
        print(f"Generation Complete")
        print(f"  Total: {total_responses}")
        print(f"  Success: {total_responses - errors}")
        print(f"  Errors: {errors}")
        print(f"  Output: {OUTPUT_FILE}")
        print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(generate_all_responses())
    except KeyboardInterrupt:
        print("\n\n✗ Generation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        sys.exit(1)
