"""
LEGACY TOOL — Not part of the main pipeline.
============================================

Uses direct HTTP calls to Ollama (not EmbeddingProvider).
For production embedding migration, use tools/migrate_embeddings.py instead.

Original purpose: Repair corrupted benchmark archives (simulated embeddings).
Re-reads generated texts and recalculates real vectors via Ollama.

Author: Lyra Architect
"""
import json
import time
import httpx
import numpy as np
import shutil
from pathlib import Path
from datetime import datetime

# --- CONFIGURATION ---
# Le dossier où se trouve ton benchmark raté
TARGET_DIR = Path("benchmark_results") 
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_EMBEDDING = "nomic-embed-text"

# Timeout très large pour éviter les crashs (10 minutes)
TIMEOUT_CONFIG = httpx.Timeout(600.0, connect=60.0)

def get_real_embedding(text):
    """Récupère le vrai vecteur depuis Ollama avec retry."""
    payload = {
        "model": MODEL_EMBEDDING,
        "prompt": text
    }
    
    for attempt in range(3):
        try:
            with httpx.Client(timeout=TIMEOUT_CONFIG) as client:
                response = client.post(OLLAMA_URL, json=payload)
                if response.status_code == 200:
                    return response.json()["embedding"]
                else:
                    print(f"⚠️ Erreur API ({response.status_code}). Retry {attempt+1}...")
                    time.sleep(2)
        except Exception as e:
            print(f"⚠️ Exception ({e}). Retry {attempt+1}...")
            time.sleep(2)
    
    return None # Echec total

def calculate_physics(vec_query, vec_response):
    """Recalcule les métriques de conscience basées sur les vecteurs."""
    v1 = np.array(vec_query)
    v2 = np.array(vec_response)
    
    # 1. Cohérence (Cosine Similarity)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    
    if norm1 == 0 or norm2 == 0:
        coherence = 0.0
    else:
        coherence = np.dot(v1, v2) / (norm1 * norm2)
        
    # 2. Tension (Dérivée simple de la cohérence pour le bench)
    # Dans Lyra, Tension monte quand Cohérence baisse
    tension = max(0.0, 1.0 - coherence)
    
    return coherence, tension

def find_latest_archive():
    """Trouve le dossier de benchmark le plus récent."""
    if not TARGET_DIR.exists(): return None
    dirs = sorted([d for d in TARGET_DIR.iterdir() if d.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
    return dirs[0] if dirs else None

def hydrate_archive():
    print("💧 Démarrage de l'Hydratation des Données...")
    
    # 1. Trouver le fichier
    latest_run = find_latest_archive()
    if not latest_run:
        print("❌ Aucun dossier de benchmark trouvé.")
        return

    jsonl_files = list(latest_run.glob("*_export.jsonl"))
    if not jsonl_files:
        print("❌ Pas de fichier .jsonl trouvé dans le dernier run.")
        return
        
    input_file = jsonl_files[0]
    output_file = input_file.parent / f"{input_file.stem}_REPAIRED.jsonl"
    
    print(f"📂 Cible : {input_file.name}")
    print(f"💾 Sortie : {output_file.name}")
    
    # 2. Traitement ligne par ligne
    success_count = 0
    lines = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    print(f"📊 {len(lines)} entrées à réparer.")
    
    with open(output_file, 'w', encoding='utf-8') as f_out:
        for i, line in enumerate(lines):
            data = json.loads(line)
            prompt = data.get("query_text", "")
            response = data.get("response_text", "")
            
            print(f"   [{i+1}/{len(lines)}] Hydratation: '{prompt[:30]}...'")
            
            # A. Récupérer Query Embedding
            emb_q = get_real_embedding(prompt)
            time.sleep(0.5) # Pause respiration
            
            # B. Récupérer Response Embedding
            emb_r = get_real_embedding(response)
            time.sleep(0.5) # Pause respiration
            
            if emb_q and emb_r:
                # C. Recalculer Métriques
                coh, tens = calculate_physics(emb_q, emb_r)
                
                # D. Mise à jour des données
                data["query_embeddings"] = emb_q
                data["response_embeddings"] = emb_r
                data["coherence"] = round(float(coh), 4)
                data["tension"] = round(float(tens), 4)
                data["stability"] = round(float(coh * 0.9), 4) # Proxy simple
                
                # Marqueur de réparation
                data["meta_repaired"] = True
                data["meta_repair_date"] = datetime.now().isoformat()
                
                print(f"      ✅ Succès -> Cohérence: {coh:.4f} | Tension: {tens:.4f}")
                success_count += 1
            else:
                print("      ❌ Echec vectorisation. Données originales conservées.")
                data["meta_repaired"] = False
            
            # Ecriture immédiate
            f_out.write(json.dumps(data) + "\n")
            f_out.flush()
            
    print("-" * 60)
    print(f"✨ Terminé. {success_count}/{len(lines)} messages réparés.")
    print(f"👉 Nouveau fichier prêt pour analyse : {output_file}")

if __name__ == "__main__":
    hydrate_archive()
