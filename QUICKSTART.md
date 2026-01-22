# ⚡ QUICKSTART - Lyra Clean (5 Minutes)

## Option 1: Local Development

```bash
# 1. Install (1 min)
cd lyra_clean
pip install -r requirements.txt

# 2. Migrate data (2 min)
python scripts/migrate_data.py \
  --edges ../data/graphs/edges.csv \
  --nodes ../data/graphs/nodes.csv \
  --output data/ispace.db

# 3. Verify (30 sec)
python verify_setup.py

# 4. Start server (30 sec)
python app/main.py
# → Server: http://localhost:8000
# → Docs:   http://localhost:8000/docs
```

**Test:**
```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello!", "profile": "creative"}'
```

---

## Option 2: Docker (Production)

```bash
# 1. Build & start (2 min)
cd lyra_clean
docker-compose up -d

# 2. Pull LLM model (3 min)
docker exec lyra-ollama ollama pull gpt-oss:20b

# 3. Check health
curl http://localhost:8000/health
```

**View logs:**
```bash
docker-compose logs -f lyra-api
```

**Stop:**
```bash
docker-compose down
```

---

## Quick Test Script

```python
import httpx
import asyncio

async def test_lyra():
    async with httpx.AsyncClient() as client:
        # Health check
        health = await client.get("http://localhost:8000/health")
        print(f"Health: {health.json()['status']}")

        # Send message
        response = await client.post(
            "http://localhost:8000/chat/message",
            json={
                "text": "What is entropy?",
                "profile": "creative",
                "enable_context": True
            }
        )
        result = response.json()
        print(f"\nResponse: {result['text'][:100]}...")
        print(f"Latency: {result['latency']['total']:.1f}ms")

asyncio.run(test_lyra())
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| Database not found | Run migration script first |
| Ollama not connected | Check `docker logs lyra-ollama` |
| Port 8000 in use | Change port in `config.yaml` |

---

## Next Steps

- 📖 **Full Guide:** [GETTING_STARTED.md](GETTING_STARTED.md)
- 📚 **API Docs:** [API_GUIDE.md](API_GUIDE.md)
- 🏗️ **Architecture:** [README.md](README.md)
- ✅ **Completion Report:** [PROJECT_COMPLETION.md](PROJECT_COMPLETION.md)

---

**Ready in 5 minutes!** 🚀
