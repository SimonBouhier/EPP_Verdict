"""
"""LYRA BENCHMARK PHASE 3 - COMPARATIVE MATRIX
===========================================
Comparative study: Raw GPT vs Lyra Balanced vs Lyra Creative vs Lyra Memory.
Integrates safe embedding generation to avoid timeouts.

FIXES (Phase 3 Validation):
- Added session_id persistence for Lyra configs (fixes t=0 issue)
- Added graph initialization check
- Better error handling and logging
"""
import time
import json
import requests
import httpx
import numpy as np
import uuid
import sqlite3
import os
from datetime import datetime
from pathlib import Path

# --- CONFIGURATION ---
OLLAMA_URL = "http://localhost:11434"
LYRA_URL = "http://localhost:8000"
MODEL_GEN = "gpt-oss:20b"
MODEL_EMBED = "mxbai-embed-large"

# Timeout massivement large pour la sécurité
TIMEOUT = httpx.Timeout(600.0, connect=60.0)

# Les 15 Prompts validés de la Phase 2
PROMPTS = [
    # Technical
    ("What is machine learning? (answer in 20 words max)", "technical"),
    ("Explain Python briefly (20 words max)", "technical"),
    ("What is AI? (20 words max)", "technical"),
    ("Define cloud computing (20 words max)", "technical"),
    ("What is blockchain? (20 words max)", "technical"),
    # Creative
    ("Write a haiku about code", "creative"),
    ("Describe the color blue poetically (15 words max)", "creative"),
    ("What makes a good story? (20 words max)", "creative"),
    # Analytical
    ("Compare Linux and Windows (25 words max)", "analytical"),
    ("Explain quantum computing basics (25 words max)", "analytical"),
    ("What are the benefits of open source? (25 words max)", "analytical"),
    # Philosophical
    ("What is consciousness? (20 words max)", "philosophical"),
    ("Can machines think? (20 words max)", "philosophical"),
    ("Define intelligence (20 words max)", "philosophical"),
    # Practical
    ("How to debug code? (steps in 20 words)", "practical")
]

# La Matrice de Test
CONFIGS = [
    {"id": "raw_gpt",       "type": "ollama", "label": "Baseline (Raw)"},
    {"id": "lyra_balanced", "type": "lyra",   "profile": "balanced", "context": False, "label": "Lyra (Balanced)"},
    {"id": "lyra_creative", "type": "lyra",   "profile": "creative", "context": False, "label": "Lyra (Creative)"},
    {"id": "lyra_memory",   "type": "lyra",   "profile": "balanced", "context": True,  "label": "Lyra (Memory)"}
]

def get_embedding(text):
    """Safe embedding fetching with pause."""
    time.sleep(0.5)
    try:
        resp = requests.post(f"{OLLAMA_URL}/api/embeddings", json={
            "model": MODEL_EMBED,
            "prompt": text
        }, timeout=120)
        if resp.status_code == 200:
            return resp.json()["embedding"]
    except Exception as e:
        pass
    return None

def calculate_metrics(q_vec, r_vec):
    """Compute coherence/tension."""
    if not q_vec or not r_vec: return 0.0, 0.0
    v1, v2 = np.array(q_vec), np.array(r_vec)
    norm1, norm2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0: return 0.0, 0.0
    
    coherence = np.dot(v1, v2) / (norm1 * norm2)
    tension = max(0.0, 1.0 - coherence)
    return float(coherence), float(tension)

def run_ollama_raw(prompt):
    """Call Ollama directly (Baseline)."""
    start = time.time()
    try:
        resp = requests.post(f"{OLLAMA_URL}/api/generate", json={
            "model": MODEL_GEN,
            "prompt": prompt,
            "stream": False
        }, timeout=120)
        resp.raise_for_status()
        lat = (time.time() - start) * 1000
        return resp.json()["response"], lat
    except Exception as e:
        return None, None

def run_lyra(prompt, conf, session_id=None):
    """Call Lyra API with persistent session_id and retry logic."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            start = time.time()
            payload = {
                "text": prompt,
                "profile": conf["profile"],
                "enable_context": conf["context"]
            }
            # Add session_id for persistent context across prompts
            if session_id:
                payload["session_id"] = session_id
            
            resp = requests.post(f"{LYRA_URL}/chat/message", json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            lat = (time.time() - start) * 1000 
            return data["text"], lat, data
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return None, None, None

def check_graph_initialized(db_path="data/ispace.db"):
    """Verify semantic graph is populated"""
    if not os.path.exists(db_path):
        return {"initialized": False, "error": "DB file not found", "concepts": 0, "relations": 0}
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM concepts")
        n_concepts = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM relations")
        n_relations = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "initialized": n_concepts > 0,
            "concepts": n_concepts,
            "relations": n_relations
        }
    except Exception as e:
        return {"initialized": False, "error": str(e), "concepts": 0, "relations": 0}

def run_benchmark():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("benchmark_results") / f"phase3_matrix_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "matrix_results.jsonl"

    print(f"[START] PHASE 3 MATRIX BENCHMARK")
    print(f"[OUTPUT] {out_file}")
    print(f"[MATRIX] {len(CONFIGS)} configs x {len(PROMPTS)} prompts = {len(CONFIGS)*len(PROMPTS)} requests")
    
    # Check graph status
    graph_status = check_graph_initialized()
    print(f"[GRAPH] Concepts: {graph_status['concepts']}, Relations: {graph_status['relations']}")
    if not graph_status['initialized']:
        print(f"[WARNING] Semantic graph is empty - context injection will not work")

    results = []
    
    with open(out_file, "w", encoding="utf-8") as f:
        for conf in CONFIGS:
            print(f"\n[CONFIG] {conf['label']}")
            
            # Create session_id for Lyra (persistent across all prompts in this config)
            session_id = str(uuid.uuid4()) if conf["type"] == "lyra" else None
            
            for i, (prompt, domain) in enumerate(PROMPTS):
                print(f"   [{i+1}/{len(PROMPTS)}] {prompt[:40]}...", end="", flush=True)
                
                # 1. GENERATION
                meta = {}
                try:
                    if conf["type"] == "ollama":
                        response_text, latency = run_ollama_raw(prompt)
                        meta = {"physics": "N/A", "profile": "raw"}
                    else:
                        response_text, latency, api_data = run_lyra(prompt, conf, session_id)
                        meta = {
                            "physics": api_data.get("physics_state") if api_data else None,
                            "context_used": api_data.get("context") if api_data else None
                        }
                    
                    # Skip if generation failed
                    if response_text is None or latency is None:
                        print(f" SKIP (gen failed)")
                        continue
                    
                    print(f" OK ({latency:.0f}ms) -> Embed...", end="", flush=True)

                    # 2. EMBEDDINGS (Immediate & Safe)
                    q_emb = get_embedding(prompt)
                    r_emb = get_embedding(response_text)
                    
                    # 3. METRICS
                    coh, tens = calculate_metrics(q_emb, r_emb)
                    
                    record = {
                        "config_id": conf["id"],
                        "config_label": conf["label"],
                        "domain": domain,
                        "prompt": prompt,
                        "response": response_text,
                        "latency_ms": round(latency, 2),
                        "coherence": round(coh, 4),
                        "tension": round(tens, 4),
                        "meta": meta,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    f.write(json.dumps(record) + "\n")
                    f.flush()
                    print(f" OK (Coh: {coh:.3f})")
                    
                except Exception as e:
                    print(f" ERROR: {e}")

    print("\n[COMPLETE] BENCHMARK DONE.")

if __name__ == "__main__":
    run_benchmark()
