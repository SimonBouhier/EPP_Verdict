"""
Generate 60 responses for Option B quick validation.

Usage:
    python generate_responses_optionB.py
    
Output:
    evaluation/1_source_data/responses_raw.jsonl (60 lines)
    
Configs:
    - baseline (raw default)
    - temp_only (temperature mapping only)
    - system_only (system prompt only)
    - full_lyra (complete orchestration)
    
Prompts:
    - 5 technical
    - 5 creative  
    - 5 analytical
    
Total: 4 configs × 15 prompts = 60 responses
"""

import asyncio
import json
import time
from pathlib import Path
from datetime import datetime
import httpx

# ============================================================================
# CONFIGURATION
# ============================================================================

API_URL = "http://localhost:8000/chat/message"
OUTPUT_DIR = Path("evaluation/1_source_data")
OUTPUT_FILE = OUTPUT_DIR / "responses_raw.jsonl"

CONFIGS = {
    "baseline": {
        "name": "Raw Default",
        "consciousness_level": 0,
        "enable_context": False,
        "profile": "balanced"  # Will be ignored at level 0
    },
    "temp_only": {
        "name": "Temperature Only",
        "consciousness_level": 0,
        "enable_context": False,
        "profile": "balanced"
    },
    "system_only": {
        "name": "System Prompt Only",
        "consciousness_level": 0,
        "enable_context": False,
        "profile": "balanced"
    },
    "full_lyra": {
        "name": "Full Lyra Balanced",
        "consciousness_level": 1,
        "enable_context": True,
        "profile": "balanced"
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

# ============================================================================
# GENERATION
# ============================================================================

async def generate_response(
    prompt: str,
    domain: str,
    config_id: str,
    config: dict,
    session: httpx.AsyncClient
) -> dict:
    """Generate single response via API."""
    
    payload = {
        "text": prompt,
        "session_id": f"optionB_{config_id}_{domain}",
        "consciousness_level": config["consciousness_level"],
        "profile": config["profile"],
        "enable_context": config["enable_context"]
    }
    
    start = time.time()
    
    try:
        response = await session.post(API_URL, json=payload, timeout=180.0)
        response.raise_for_status()
        data = response.json()
        
        latency_ms = (time.time() - start) * 1000
        
        return {
            "config_id": config_id,
            "config_name": config["name"],
            "prompt": prompt,
            "domain": domain,
            "response": data.get("text", ""),
            "physics_state": data.get("physics_state"),
            "latency_ms": latency_ms,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tokens": data.get("tokens"),
            "consciousness": data.get("consciousness")
        }
    
    except Exception as e:
        print(f"❌ ERROR [{config_id}] {prompt[:50]}: {e}")
        return None


async def generate_all():
    """Generate all 60 responses."""
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Build all tasks
    tasks = []
    for domain, prompts in PROMPTS.items():
        for prompt in prompts:
            for config_id, config in CONFIGS.items():
                tasks.append((prompt, domain, config_id, config))
    
    print(f"🚀 Starting generation: {len(tasks)} total responses")
    print(f"📁 Output: {OUTPUT_FILE}")
    print("-" * 80)
    
    # Execute sequentially with progress
    async with httpx.AsyncClient() as session:
        with open(OUTPUT_FILE, 'w') as f:
            for i, (prompt, domain, config_id, config) in enumerate(tasks):
                print(f"[{i+1:2d}/{len(tasks)}] {config_id:12s} | {domain:10s} | {prompt[:40]}...")
                
                result = await generate_response(prompt, domain, config_id, config, session)
                
                if result:
                    f.write(json.dumps(result) + '\n')
                    f.flush()
                else:
                    print(f"   ⚠️  Skipped (error)")
                
                # Small pause to avoid overwhelming server
                await asyncio.sleep(0.5)
    
    print("-" * 80)
    print(f"✅ Generation complete!")
    print(f"📊 {len(tasks)} responses saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(generate_all())
