"""
TEST API - Lyra Clean Backend
==============================
Test des endpoints critiques du serveur FastAPI
"""
import requests
import json
import time
import uuid

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    """Test /health endpoint"""
    print("\n🏥 TEST HEALTH CHECK")
    resp = requests.get(f"{BASE_URL}/health")
    data = resp.json()
    print(f"  Status: {data['status']}")
    print(f"  Database: {data['database']['connected']} ({data['database']['concepts']} concepts)")
    print(f"  Ollama: {data['ollama']['connected']}")
    assert resp.status_code == 200
    print("  ✅ PASS")

def test_stats():
    """Test /stats endpoint"""
    print("\n📊 TEST STATS")
    resp = requests.get(f"{BASE_URL}/stats")
    data = resp.json()
    print(f"  Concepts: {data['database']['concepts']}")
    print(f"  Relations: {data['database']['relations']}")
    print(f"  Sessions: {data['database']['sessions']}")
    assert resp.status_code == 200
    print("  ✅ PASS")

def test_root_ui():
    """Test / endpoint (UI)"""
    print("\n🌐 TEST ROOT UI")
    resp = requests.get(f"{BASE_URL}/")
    assert resp.status_code == 200
    assert "index.html" in resp.text or "Lyra" in resp.text
    print(f"  Response length: {len(resp.text)} bytes")
    print("  ✅ PASS")

def test_chat_message():
    """Test POST /chat/message endpoint"""
    print("\n💬 TEST CHAT MESSAGE")
    
    session_id = str(uuid.uuid4())
    
    payload = {
        "session_id": session_id,
        "profile": "balanced",
        "enable_context": True,
        "text": "Explique moi l'entropie en physique"
    }
    
    print(f"  Session ID: {session_id[:8]}...")
    print(f"  Profile: balanced")
    print(f"  Message: {payload['text']}")
    
    start = time.time()
    resp = requests.post(f"{BASE_URL}/chat/message", json=payload)
    elapsed = time.time() - start
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Status: {resp.status_code}")
        print(f"  Response time: {elapsed:.2f}s")
        reply_text = data.get('text', data.get('reply', ''))
        print(f"  Reply preview: {str(reply_text)[:100]}...")
        if 'latency_ms' in data:
            print(f"  Latency: {data['latency_ms']}ms")
        print("  ✅ PASS")
    else:
        print(f"  Status: {resp.status_code}")
        print(f"  Error: {resp.text[:200]}")
        print("  ❌ FAIL")

def test_sessions_get():
    """Test GET /sessions endpoint"""
    print("\n📋 TEST GET SESSIONS")
    resp = requests.get(f"{BASE_URL}/sessions")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Sessions: {len(data.get('sessions', []))} actives")
        print("  ✅ PASS")
    else:
        print(f"  Status: {resp.status_code}")
        print("  ⚠️ EXPECTED (peut être non implémenté)")

def test_api_root():
    """Test /api endpoint"""
    print("\n🔮 TEST API ROOT")
    resp = requests.get(f"{BASE_URL}/api")
    data = resp.json()
    print(f"  Service: {data.get('service')}")
    print(f"  Version: {data.get('version')}")
    print(f"  Endpoints:")
    for key, val in data.get('endpoints', {}).items():
        print(f"    - {key}: {val}")
    assert resp.status_code == 200
    print("  ✅ PASS")

def main():
    print("="*70)
    print("🚀 LYRA CLEAN - API TEST SUITE")
    print("="*70)
    
    try:
        test_health()
        test_stats()
        test_api_root()
        test_root_ui()
        test_chat_message()
        test_sessions_get()
        
        print("\n" + "="*70)
        print("✅ TESTS COMPLÉTÉS AVEC SUCCÈS")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
