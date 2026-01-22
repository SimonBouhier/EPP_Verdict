"""
PHASE 3 - VALIDATION BENCHMARK
==============================

Tests 4 hypotheses pour expliquer gain performance Lyra vs Raw:
1. Temperature difference
2. Ollama parameters difference
3. Warm-up order effect
4. Response length difference

Méthodologie:
- 10 prompts variés
- 6 configurations (raw_default, raw_temp_0.8, raw_temp_0.615, raw_explicit, lyra_balanced, lyra_creative)
- 2 ordres d'exécution (normal, reversed)
- Total: 120 requêtes

Usage:
    python benchmark_phase3_validation.py --output validation_results.jsonl
"""
import requests
import json
import time
import uuid
import logging
from typing import List, Dict, Any
from datetime import datetime
import argparse

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# URLs
OLLAMA_URL = "http://localhost:11434"
LYRA_URL = "http://localhost:8000"
MODEL = "gpt-oss:20b"

# Prompts validés (subset pour validation - 10 prompts = ~12 min)
VALIDATION_PROMPTS = [
    {"domain": "technical", "prompt": "What is machine learning? (answer in 20 words max)"},
    {"domain": "technical", "prompt": "Explain Python briefly (20 words max)"},
    {"domain": "technical", "prompt": "What is AI? (20 words max)"},
    {"domain": "creative", "prompt": "Write a haiku about code"},
    {"domain": "creative", "prompt": "Describe the color blue poetically (15 words max)"},
    {"domain": "analytical", "prompt": "Compare Linux and Windows (25 words max)"},
    {"domain": "analytical", "prompt": "Explain quantum computing basics (25 words max)"},
    {"domain": "philosophical", "prompt": "What is consciousness? (20 words max)"},
    {"domain": "philosophical", "prompt": "Can machines think? (20 words max)"},
    {"domain": "practical", "prompt": "How to debug code? (steps in 20 words)"},
]

# Configurations testées
VALIDATION_CONFIGS = {
    # BASELINE - Raw Default (Ollama defaults)
    "raw_default": {
        "label": "Raw Default",
        "url": OLLAMA_URL,
        "endpoint": "/api/chat",
        "params": {
            "model": MODEL,
            "stream": False
            # No options → Ollama defaults
        }
    },
    
    # HYPOTHESIS 1: Temperature explicit (same as creative)
    "raw_temp_0.8": {
        "label": "Raw Temp 0.8 (explicit)",
        "url": OLLAMA_URL,
        "endpoint": "/api/chat",
        "params": {
            "model": MODEL,
            "stream": False,
            "options": {
                "temperature": 0.8
            }
        }
    },
    
    "raw_temp_0.615": {
        "label": "Raw Temp 0.615 (Creative equiv)",
        "url": OLLAMA_URL,
        "endpoint": "/api/chat",
        "params": {
            "model": MODEL,
            "stream": False,
            "options": {
                "temperature": 0.615  # Same as Lyra Creative (tau_c=1.3)
            }
        }
    },
    
    # HYPOTHESIS 2: All params explicit (matching Lyra)
    "raw_explicit": {
        "label": "Raw Explicit (Lyra-equiv params)",
        "url": OLLAMA_URL,
        "endpoint": "/api/chat",
        "params": {
            "model": MODEL,
            "stream": False,
            "options": {
                "temperature": 0.8,
                "num_predict": 4096,
                "top_k": 40,
                "top_p": 0.9,
                "repeat_penalty": 1.0
            }
        }
    },
    
    # REFERENCE: Lyra Balanced
    "lyra_balanced": {
        "label": "Lyra Balanced",
        "url": LYRA_URL,
        "endpoint": "/chat/message",
        "params": {
            "profile": "balanced",
            "enable_context": False
        }
    },
    
    # REFERENCE: Lyra Creative
    "lyra_creative": {
        "label": "Lyra Creative",
        "url": LYRA_URL,
        "endpoint": "/chat/message",
        "params": {
            "profile": "creative",
            "enable_context": False
        }
    },
}


def count_tokens_approx(text: str) -> int:
    """Approximate token count (4 chars ≈ 1 token)"""
    return max(1, len(text) // 4)


def call_ollama_direct(config: Dict, prompt: str) -> Dict[str, Any]:
    """Call Ollama API directly"""
    start = time.time()
    
    payload = {**config["params"]}
    payload["messages"] = [{"role": "user", "content": prompt}]
    
    try:
        resp = requests.post(
            f"{config['url']}{config['endpoint']}",
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        
        latency_ms = (time.time() - start) * 1000
        
        # Extract response
        response_text = data.get("message", {}).get("content", "")
        
        return {
            "success": True,
            "response": response_text,
            "latency_ms": latency_ms,
        }
        
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        logger.warning(f"Ollama error: {e}")
        return {
            "success": False,
            "error": str(e),
            "latency_ms": latency_ms
        }


def call_lyra(config: Dict, prompt: str, session_id: str) -> Dict[str, Any]:
    """Call Lyra API with persistent session"""
    start = time.time()
    
    payload = {
        "text": prompt,
        "session_id": session_id,  # IMPORTANT: persistent session
        **config["params"]
    }
    
    try:
        resp = requests.post(
            f"{config['url']}{config['endpoint']}",
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        
        # Check if data is None or invalid
        if not data:
            return {
                "success": False,
                "error": "Empty response from server",
                "latency_ms": (time.time() - start) * 1000
            }
        
        latency_ms = (time.time() - start) * 1000
        
        return {
            "success": True,
            "response": data.get("text", ""),
            "latency_ms": latency_ms,
            "meta": {
                "physics": data.get("physics_state"),
                "context_weight": data.get("context", {}).get("total_weight", 0) if data.get("context") else 0
            }
        }
        
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        logger.warning(f"Lyra error: {e}")
        return {
            "success": False,
            "error": str(e),
            "latency_ms": latency_ms
        }


def run_validation_benchmark(output_file: str = "validation_results.jsonl"):
    """
    Run validation benchmark with 2 execution orders:
    1. Normal: Raw configs first, then Lyra
    2. Reversed: Lyra first, then Raw configs
    """
    
    results = []
    
    # Clear output file
    with open(output_file, "w") as f:
        pass
    
    # ORDER 1: Normal (Raw → Lyra)
    print("\n" + "="*80)
    print("ORDER 1: Raw → Lyra (normal execution order)")
    print("="*80)
    
    order_1_configs = [
        "raw_default",
        "raw_temp_0.8",
        "raw_temp_0.615",
        "raw_explicit",
        "lyra_balanced",
        "lyra_creative"
    ]
    
    for config_id in order_1_configs:
        config = VALIDATION_CONFIGS[config_id]
        session_id = str(uuid.uuid4())  # One session per config
        
        print(f"\n[{config_id}] {config['label']}")
        print("-" * 60)
        
        for i, item in enumerate(VALIDATION_PROMPTS, 1):
            prompt = item["prompt"]
            domain = item["domain"]
            
            print(f"  [{i:2d}/10] {prompt[:45]}...", end=" ", flush=True)
            
            # Call appropriate API
            if config_id.startswith("raw_"):
                result = call_ollama_direct(config, prompt)
            else:
                result = call_lyra(config, prompt, session_id)
            
            if result["success"]:
                print(f"✓ {result['latency_ms']:6.0f}ms")
                
                # Compute metrics
                tokens = count_tokens_approx(result["response"])
                
                # Store result
                record = {
                    "execution_order": "normal",
                    "config_id": config_id,
                    "config_label": config["label"],
                    "domain": domain,
                    "prompt": prompt,
                    "response": result["response"],
                    "latency_ms": round(result["latency_ms"], 1),
                    "tokens_approx": tokens,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Add meta if present
                if "meta" in result:
                    record["meta"] = result["meta"]
                
                results.append(record)
                
                # Save incrementally
                with open(output_file, "a") as f:
                    f.write(json.dumps(record) + "\n")
                    
            else:
                print(f"✗ ERROR: {result.get('error', 'Unknown')[:30]}")
            
            # Small delay between requests
            time.sleep(0.5)
    
    # ORDER 2: Reversed (Lyra → Raw)
    print("\n\n" + "="*80)
    print("ORDER 2: Lyra → Raw (reversed execution order - test warm-up)")
    print("="*80)
    
    order_2_configs = list(reversed(order_1_configs))
    
    for config_id in order_2_configs:
        config = VALIDATION_CONFIGS[config_id]
        session_id = str(uuid.uuid4())
        
        print(f"\n[{config_id}] {config['label']}")
        print("-" * 60)
        
        for i, item in enumerate(VALIDATION_PROMPTS, 1):
            prompt = item["prompt"]
            domain = item["domain"]
            
            print(f"  [{i:2d}/10] {prompt[:45]}...", end=" ", flush=True)
            
            if config_id.startswith("raw_"):
                result = call_ollama_direct(config, prompt)
            else:
                result = call_lyra(config, prompt, session_id)
            
            if result["success"]:
                print(f"✓ {result['latency_ms']:6.0f}ms")
                
                tokens = count_tokens_approx(result["response"])
                
                record = {
                    "execution_order": "reversed",
                    "config_id": config_id,
                    "config_label": config["label"],
                    "domain": domain,
                    "prompt": prompt,
                    "response": result["response"],
                    "latency_ms": round(result["latency_ms"], 1),
                    "tokens_approx": tokens,
                    "timestamp": datetime.now().isoformat()
                }
                
                if "meta" in result:
                    record["meta"] = result["meta"]
                
                results.append(record)
                
                with open(output_file, "a") as f:
                    f.write(json.dumps(record) + "\n")
                    
            else:
                print(f"✗ ERROR: {result.get('error', 'Unknown')[:30]}")
            
            time.sleep(0.5)
    
    print("\n" + "="*80)
    print(f"✓ Validation benchmark COMPLETE")
    print(f"✓ Total results: {len(results)}")
    print(f"✓ Output file: {output_file}")
    print("="*80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 3 Validation Benchmark")
    parser.add_argument("--output", default="validation_results.jsonl", help="Output file (JSONL)")
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("PHASE 3 - VALIDATION BENCHMARK")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  Ollama URL: {OLLAMA_URL}")
    print(f"  Lyra URL: {LYRA_URL}")
    print(f"  Model: {MODEL}")
    print(f"  Prompts: {len(VALIDATION_PROMPTS)}")
    print(f"  Configs: {len(VALIDATION_CONFIGS)}")
    print(f"  Orders: 2 (normal, reversed)")
    print(f"  Total requests: {len(VALIDATION_PROMPTS) * len(VALIDATION_CONFIGS) * 2}")
    print(f"  Estimated duration: 15-20 minutes\n")
    
    run_validation_benchmark(args.output)
