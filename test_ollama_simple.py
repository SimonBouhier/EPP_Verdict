#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test simple Ollama avec gpt-oss:20b
Diagnostic du probleme de timeout
"""

import requests
import time
import json

def test_ollama_simple():
    """Test ultra-simple pour voir ce qui se passe"""
    
    url = "http://localhost:11434/api/generate"
    
    print("\n" + "=" * 80)
    print("TEST OLLAMA AVEC GPT-OSS:20B")
    print("=" * 80)
    print()
    
    # Test 1: Juste un ping
    print("[1] Test de connectivite...")
    try:
        tags_response = requests.get("http://localhost:11434/api/tags", timeout=5)
        print(f"    [OK] Ollama repond (status: {tags_response.status_code})")
        models = tags_response.json().get('models', [])
        print(f"    Modeles disponibles: {len(models)}")
        for m in models:
            print(f"      - {m.get('name', 'Unknown')}")
    except Exception as e:
        print(f"    [ERREUR] {e}")
        return
    
    print()
    
    # Test 2: Essayer une generation ultra-courte
    print("[2] Test generation ultra-courte avec gpt-oss:20b...")
    payload = {
        "model": "gpt-oss:20b",
        "prompt": "Respond in ONE word: yes or no?",
        "stream": False,
        "num_predict": 5,  # Ultra court: 5 tokens max
        "temperature": 0.1  # Deterministe
    }
    
    print(f"    Payload: {json.dumps(payload, indent=2)}")
    print()
    
    try:
        print("    [ENVOI] POST a http://localhost:11434/api/generate")
        print("    [ATTENTE] Timeout: 60 secondes...")
        start = time.time()
        
        response = requests.post(url, json=payload, timeout=60)
        elapsed = time.time() - start
        
        print(f"    [RECU] Status {response.status_code} apres {elapsed:.1f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"    [OK] Response recu!")
            print(f"        Tokens prompt: {data.get('prompt_eval_count', 0)}")
            print(f"        Tokens completion: {data.get('eval_count', 0)}")
            print(f"        Response: '{data.get('response', '').strip()}'")
            return True
        else:
            print(f"    [ERREUR] Status {response.status_code}")
            print(f"    Body: {response.text[:200]}...")
            return False
            
    except requests.exceptions.Timeout as e:
        print(f"    [TIMEOUT] Apres 60s: {e}")
        return False
    except Exception as e:
        print(f"    [ERREUR] {type(e).__name__}: {e}")
        return False


if __name__ == '__main__':
    success = test_ollama_simple()
    print()
    print("=" * 80)
    if success:
        print("[OK] Ollama fonctionne! Le probleme est dans le code benchmark")
    else:
        print("[ERREUR] Ollama ne repond pas correctement")
    print("=" * 80)
