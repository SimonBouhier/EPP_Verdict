# 🚀 LYRA CLEAN - API GUIDE

Complete API reference with cURL examples.

---

## 📡 Quick Start

### 1. Start Server (Development)

```bash
cd lyra_clean
python app/main.py
```

Server will start at: `http://localhost:8000`

API Documentation: `http://localhost:8000/docs`

### 2. Start with Docker

```bash
docker-compose up -d

# Pull Ollama model (first time)
docker exec lyra-ollama ollama pull gpt-oss:20b

# Check health
curl http://localhost:8000/health
```

---

## 🔥 Core Endpoints

### Chat Message

Send a message and get LLM response with physics-driven generation.

**Endpoint:** `POST /chat/message`

**Request:**
```json
{
    "text": "What is entropy in information theory?",
    "session_id": "my-session-123",
    "profile": "creative",
    "enable_context": true,
    "max_history": 20
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What is entropy in information theory?",
    "profile": "creative",
    "enable_context": true
  }'
```

**Response:**
```json
{
    "text": "Entropy in information theory is a measure of uncertainty...",
    "session_id": "abc-123",
    "physics_state": {
        "t": 0.46,
        "tau_c": 1.25,
        "rho": 0.35,
        "delta_r": 0.12,
        "kappa": 0.5
    },
    "context": {
        "query_keywords": ["entropy", "information", "theory"],
        "neighbor_concepts": [
            {"target": "chaos", "weight": 0.85, "kappa": 0.62},
            {"target": "order", "weight": 0.72, "kappa": 0.58}
        ],
        "total_weight": 3.42,
        "latency_ms": 15.3
    },
    "latency": {
        "context_extraction": 15.3,
        "llm_generation": 1245.7,
        "total": 1287.2
    },
    "tokens": {
        "prompt": 250,
        "completion": 180,
        "total": 430
    }
}
```

**Key Features:**
- ✅ Auto-creates session if `session_id` not provided
- ✅ Semantic context injection from graph (if `enable_context=true`)
- ✅ Physics parameters computed from Bezier trajectory
- ✅ Conversation history included (last N messages)
- ✅ Full latency breakdown for monitoring

---

## 📋 Session Management

### Create Session

Create a new conversation session with specific profile.

**Endpoint:** `POST /sessions`

```bash
curl -X POST "http://localhost:8000/sessions" \
  -H "Content-Type: application/json" \
  -d '{
    "profile": "analytical"
  }'
```

**Response:**
```json
{
    "session_id": "abc-123",
    "profile": "analytical",
    "created_at": "2025-01-01T12:00:00Z",
    "last_activity": "2025-01-01T12:00:00Z",
    "message_count": 0,
    "total_tokens": 0
}
```

---

### Get Session Info

**Endpoint:** `GET /sessions/{session_id}`

```bash
curl "http://localhost:8000/sessions/abc-123"
```

**Response:**
```json
{
    "session_id": "abc-123",
    "profile": "creative",
    "created_at": "2025-01-01T12:00:00Z",
    "last_activity": "2025-01-01T12:15:30Z",
    "message_count": 15,
    "total_tokens": 4523
}
```

---

### Get Conversation History

**Endpoint:** `GET /sessions/{session_id}/history?limit=50`

```bash
curl "http://localhost:8000/sessions/abc-123/history?limit=20"
```

**Response:**
```json
{
    "session_id": "abc-123",
    "messages": [
        {
            "event_id": 1,
            "role": "user",
            "content": "Hello",
            "timestamp": "2025-01-01T12:00:10Z",
            "latency_ms": null
        },
        {
            "event_id": 2,
            "role": "assistant",
            "content": "Hi! How can I help?",
            "timestamp": "2025-01-01T12:00:12Z",
            "latency_ms": 1250.3
        }
    ],
    "total_messages": 2
}
```

---

### Delete Session

**Endpoint:** `DELETE /sessions/{session_id}`

```bash
curl -X DELETE "http://localhost:8000/sessions/abc-123"
```

**Response:**
```json
{
    "status": "deleted",
    "session_id": "abc-123"
}
```

---

## 🎨 Bezier Profiles

### List Profiles

**Endpoint:** `GET /profiles`

```bash
curl "http://localhost:8000/profiles"
```

**Response:**
```json
{
    "profiles": [
        {
            "name": "balanced",
            "description": "Balanced exploration-exploitation",
            "is_default": true
        },
        {
            "name": "creative",
            "description": "High exploration, loose constraints",
            "is_default": false
        },
        {
            "name": "safe",
            "description": "Conservative, structured responses",
            "is_default": false
        },
        {
            "name": "analytical",
            "description": "High precision, low temperature",
            "is_default": false
        }
    ]
}
```

---

### Get Profile Details

**Endpoint:** `GET /profiles/{profile_name}?include_preview=true`

```bash
curl "http://localhost:8000/profiles/creative?include_preview=true&preview_samples=5"
```

**Response:**
```json
{
    "profile_name": "creative",
    "description": "High exploration, loose constraints",
    "tau_c_curve": [[0, 1.3], [0.2, 1.5], [0.6, 1.2], [1, 1.0]],
    "rho_curve": [[0, 0.5], [0.3, 0.7], [0.7, 0.4], [1, 0.2]],
    "delta_r_curve": [[0, 0.2], [0.4, 0.3], [0.8, 0.1], [1, 0.0]],
    "kappa_curve": null,
    "is_default": false,
    "preview": [
        {"t": 0.0, "tau_c": 1.30, "rho": 0.50, "delta_r": 0.20, "kappa": 0.5},
        {"t": 0.25, "tau_c": 1.45, "rho": 0.65, "delta_r": 0.28, "kappa": 0.5},
        {"t": 0.5, "tau_c": 1.38, "rho": 0.58, "delta_r": 0.23, "kappa": 0.5},
        {"t": 0.75, "tau_c": 1.18, "rho": 0.35, "delta_r": 0.12, "kappa": 0.5},
        {"t": 1.0, "tau_c": 1.00, "rho": 0.20, "delta_r": 0.00, "kappa": 0.5}
    ]
}
```

**Use Cases:**
- Visualize trajectory before using profile
- Debug Bezier curve behavior
- Compare profiles side-by-side

---

## 🏥 System Health

### Health Check

**Endpoint:** `GET /health`

```bash
curl "http://localhost:8000/health"
```

**Response:**
```json
{
    "status": "healthy",
    "database": {
        "connected": true,
        "concepts": 15234,
        "relations": 245678,
        "sessions": 42,
        "db_size_mb": 42.3
    },
    "ollama": {
        "connected": true,
        "models": ["gpt-oss:20b", "llama3:latest"],
        "model": "gpt-oss:20b",
        "available": true
    },
    "version": "1.0.0",
    "uptime_seconds": 3600.5
}
```

**Status Values:**
- `healthy`: All systems operational
- `degraded`: Partial functionality (e.g., Ollama down but DB up)
- `unhealthy`: Critical failure (both DB and Ollama down)

---

### System Stats

**Endpoint:** `GET /stats`

```bash
curl "http://localhost:8000/stats"
```

**Response:**
```json
{
    "database": {
        "concepts": 15234,
        "relations": 245678,
        "sessions": 42,
        "events": 1523,
        "trajectories": 856,
        "profiles": 4,
        "db_size_mb": 42.3
    },
    "performance": {
        "uptime_seconds": 3600.5
    }
}
```

---

## 🔬 Complete Workflow Example

### 1. Create Session

```bash
SESSION_ID=$(curl -s -X POST "http://localhost:8000/sessions" \
  -H "Content-Type: application/json" \
  -d '{"profile": "creative"}' | jq -r '.session_id')

echo "Created session: $SESSION_ID"
```

### 2. First Message

```bash
curl -X POST "http://localhost:8000/chat/message" \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"Explain quantum entanglement\",
    \"session_id\": \"$SESSION_ID\",
    \"enable_context\": true
  }" | jq '.'
```

### 3. Follow-up Message

```bash
curl -X POST "http://localhost:8000/chat/message" \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"Can you give an example?\",
    \"session_id\": \"$SESSION_ID\"
  }" | jq '.'
```

### 4. Check History

```bash
curl "http://localhost:8000/sessions/$SESSION_ID/history" | jq '.'
```

### 5. Cleanup

```bash
curl -X DELETE "http://localhost:8000/sessions/$SESSION_ID"
```

---

## 📊 Physics Parameters Explained

### τc (tau_c) - Tension/Temperature

- **Range:** [0.5, 2.0]
- **Effect:** Maps to LLM temperature (inverse)
  - τc high → temperature low → focused responses
  - τc low → temperature high → creative responses
- **Mapping:** `temperature = 0.8 / τc`

### ρ (rho) - Focus/Polarity

- **Range:** [-1, 1]
- **Effect:** Maps to presence/frequency penalties
  - ρ > 0 → expansive (explore new concepts)
  - ρ < 0 → conservative (stick to patterns)
  - ρ = 0 → neutral
- **Mapping:**
  - `presence_penalty = -0.6 × ρ`
  - `frequency_penalty = 0.3 × |ρ|`

### δr (delta_r) - Scheduling

- **Range:** [-1, 1]
- **Effect:** Controls context injection timing
  - δr > 0.5 → Context AFTER user prompt (delayed)
  - δr < -0.5 → Context BEFORE user prompt (pre-loaded)
  - δr ≈ 0 → Context interleaved naturally

### κ (kappa) - Curvature/Style

- **Range:** [0, 1]
- **Effect:** System prompt style hints
  - κ > 0.7 → Structured, formal
  - κ < 0.3 → Exploratory, loose
  - κ ≈ 0.5 → Balanced

---

## ⚡ Performance Tips

### 1. Reuse Sessions

```bash
# ❌ BAD: Create new session every message
curl -X POST /chat/message -d '{"text": "..."}'  # New session each time

# ✅ GOOD: Reuse session
SESSION_ID="my-persistent-session"
curl -X POST /chat/message -d "{\"text\": \"...\", \"session_id\": \"$SESSION_ID\"}"
```

### 2. Disable Context for Speed

```bash
# Enable context (slower, ~50ms overhead)
curl -X POST /chat/message -d '{"text": "...", "enable_context": true}'

# Disable context (faster, no graph queries)
curl -X POST /chat/message -d '{"text": "...", "enable_context": false}'
```

### 3. Limit History Size

```bash
# Large history (slower, more tokens)
curl -X POST /chat/message -d '{"text": "...", "max_history": 50}'

# Small history (faster, fewer tokens)
curl -X POST /chat/message -d '{"text": "...", "max_history": 10}'
```

---

## 🛠️ Error Handling

### Standard Error Response

```json
{
    "error": "session_not_found",
    "message": "Session abc-123 does not exist",
    "details": {
        "session_id": "abc-123"
    }
}
```

### Common Errors

| HTTP Code | Error | Cause | Solution |
|-----------|-------|-------|----------|
| 400 | `invalid_profile` | Profile doesn't exist | Check `/profiles` endpoint |
| 404 | `session_not_found` | Session ID invalid | Create new session |
| 500 | `internal_error` | Server error | Check logs |
| 503 | `service_unavailable` | Ollama down | Check Ollama health |

---

## 🔐 Production Checklist

- [ ] Enable API key authentication (config.yaml)
- [ ] Restrict CORS origins to your domain
- [ ] Set up HTTPS (reverse proxy)
- [ ] Configure rate limiting
- [ ] Enable monitoring (Prometheus)
- [ ] Set up automated backups
- [ ] Configure log rotation
- [ ] Use environment variables for secrets

---

## 📚 Additional Resources

- **Interactive Docs:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Architecture:** [README.md](README.md)
- **Migration Guide:** [GETTING_STARTED.md](GETTING_STARTED.md)

---

**Built with FastAPI + Async SQLite + Bezier Physics**

_"Clean Architecture meets Semantic Intelligence"_
