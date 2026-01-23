# Référence API Lyra Clean

Documentation complète de tous les endpoints REST de l'API Lyra Clean.

## Base URL

```
http://localhost:8000
```

## Authentication

Actuellement désactivée par défaut. Pour activer (production) :

```yaml
# config.yaml
security:
  api_key_enabled: true
```

Ensuite, ajoutez le header :
```
X-API-Key: your-secret-key
```

---

## Table des matières

1. [Chat](#chat)
2. [Sessions](#sessions)
3. [Profiles](#profiles)
4. [Graph (Lyra-ACE)](#graph-lyra-ace)
5. [Multi-Model (Lyra-ACE)](#multi-model-lyra-ace)
6. [System](#system)

---

## Chat

### POST /chat/message

Envoie un message et reçoit une réponse générée.

#### Request

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "message": "string (required, max 10000 chars)",
  "session_id": "string (optional, auto-generated if omitted)",
  "consciousness_level": "integer (optional, 0-3, default: 0)",
  "profile_name": "string (optional, default: 'balanced')",
  "max_history": "integer (optional, default: 20)",
  "max_context_length": "integer (optional, default: 200)"
}
```

**Parameters:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `message` | string | ✅ | - | Le message utilisateur (1-10000 caractères) |
| `session_id` | string | ❌ | auto-generated | ID de session existante (UUID) |
| `consciousness_level` | integer | ❌ | 0 | Niveau de conscience (0=passif, 1=observateur, 2=adaptatif, 3=mémoire) |
| `profile_name` | string | ❌ | "balanced" | Nom du profil Bézier à utiliser |
| `max_history` | integer | ❌ | 20 | Nombre max de messages d'historique à inclure |
| `max_context_length` | integer | ❌ | 200 | Taille max du contexte sémantique (caractères) |

#### Response

**Status: 200 OK**

```json
{
  "response": "string",
  "session_id": "string",
  "message_index": "integer",
  "physics_state": {
    "t": "float (0-1)",
    "tau_c": "float (0-1)",
    "rho": "float (0-1)",
    "delta_r": "float (0-1)",
    "kappa": "float (0-1, optional)"
  },
  "consciousness": {
    "coherence": "float (0-1)",
    "tension": "float (0-1)",
    "fit": "float (0-1)",
    "pressure": "float (0-1)",
    "stability_score": "float (0-1)",
    "suggestion": {
      "reason": "string",
      "adjustments": {
        "tau_c": "float (delta)",
        "rho": "float (delta)",
        "delta_r": "float (delta)"
      }
    }
  },
  "memory_echoes": [
    {
      "content": "string",
      "similarity": "float (0-1)",
      "turns_ago": "integer"
    }
  ],
  "semantic_context": ["string"],
  "metadata": {
    "latency_ms": "float",
    "tokens": {
      "prompt": "integer",
      "completion": "integer",
      "total": "integer"
    }
  }
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `response` | string | La réponse générée par le LLM |
| `session_id` | string | ID de la session (pour continuité) |
| `message_index` | integer | Index du message dans la session (1-based) |
| `physics_state` | object | État du système physique à ce point |
| `physics_state.t` | float | Temps normalisé [0, 1] dans la session |
| `physics_state.tau_c` | float | Tension/température (contrôle créativité) |
| `physics_state.rho` | float | Focus/polarité (contrôle répétition) |
| `physics_state.delta_r` | float | Planification (contrôle contexte) |
| `physics_state.kappa` | float | Courbure/style (optionnel) |
| `consciousness` | object | Métriques de conscience (si level ≥ 1) |
| `consciousness.coherence` | float | Densité sémantique du contexte |
| `consciousness.tension` | float | Stress système |
| `consciousness.fit` | float | Alignement longueur attendue/réelle |
| `consciousness.pressure` | float | Pression exploration vs exploitation |
| `consciousness.stability_score` | float | Score composite de stabilité |
| `consciousness.suggestion` | object | Ajustements suggérés (si level = 2) |
| `memory_echoes` | array | Messages rappelés (si level = 3) |
| `semantic_context` | array | Concepts injectés depuis le graphe |
| `metadata.latency_ms` | float | Temps de génération (millisecondes) |
| `metadata.tokens` | object | Comptage approximatif de tokens |

#### Error Responses

**400 Bad Request**
```json
{
  "detail": "Message too long (max 10000 chars)"
}
```

**404 Not Found**
```json
{
  "detail": "Session not found: abc123..."
}
```

**422 Unprocessable Entity**
```json
{
  "detail": [
    {
      "loc": ["body", "consciousness_level"],
      "msg": "ensure this value is less than or equal to 3",
      "type": "value_error.number.not_le"
    }
  ]
}
```

**500 Internal Server Error**
```json
{
  "detail": "Ollama request failed after 3 attempts: Connection refused"
}
```

#### Examples

**Example 1: Simple message (consciousness level 0)**

Request:
```bash
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the capital of France?"
  }'
```

Response:
```json
{
  "response": "The capital of France is Paris.",
  "session_id": "d4e5f6...",
  "message_index": 1,
  "physics_state": {
    "t": 0.01,
    "tau_c": 0.50,
    "rho": 0.50,
    "delta_r": 0.30
  },
  "metadata": {
    "latency_ms": 1234.5,
    "tokens": {
      "prompt": 45,
      "completion": 12,
      "total": 57
    }
  }
}
```

**Example 2: With consciousness level 1 (observer)**

Request:
```bash
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain quantum entanglement",
    "consciousness_level": 1
  }'
```

Response:
```json
{
  "response": "Quantum entanglement is a phenomenon...",
  "session_id": "a1b2c3...",
  "message_index": 1,
  "physics_state": {
    "t": 0.01,
    "tau_c": 0.50,
    "rho": 0.50,
    "delta_r": 0.30
  },
  "consciousness": {
    "coherence": 0.82,
    "tension": 0.45,
    "fit": 0.91,
    "pressure": 0.38,
    "stability_score": 0.87
  },
  "semantic_context": [
    "quantum_physics (weight=0.85)",
    "entanglement (weight=0.92)",
    "superposition (weight=0.78)"
  ],
  "metadata": {
    "latency_ms": 1456.2,
    "tokens": {
      "prompt": 67,
      "completion": 145,
      "total": 212
    }
  }
}
```

**Example 3: With memory (level 3) and session continuation**

Request 1:
```bash
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "My favorite color is blue and I love hiking",
    "consciousness_level": 3
  }'
```

Response 1:
```json
{
  "response": "That's wonderful! Blue is a calming color...",
  "session_id": "xyz789...",
  "message_index": 1,
  ...
}
```

Request 2 (later in conversation):
```bash
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What did I say about my interests?",
    "session_id": "xyz789...",
    "consciousness_level": 3
  }'
```

Response 2:
```json
{
  "response": "You mentioned that your favorite color is blue and you love hiking!",
  "session_id": "xyz789...",
  "message_index": 5,
  "physics_state": {
    "t": 0.05,
    "tau_c": 0.52,
    "rho": 0.48,
    "delta_r": 0.35
  },
  "consciousness": {
    "coherence": 0.75,
    "tension": 0.40,
    "fit": 0.88,
    "pressure": 0.35,
    "stability_score": 0.82
  },
  "memory_echoes": [
    {
      "content": "My favorite color is blue and I love hiking",
      "similarity": 0.91,
      "turns_ago": 4
    }
  ],
  "metadata": {
    "latency_ms": 1678.9,
    "tokens": {
      "prompt": 89,
      "completion": 34,
      "total": 123
    }
  }
}
```

**Example 4: Using aggressive profile**

Request:
```bash
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Generate 5 creative sci-fi story ideas",
    "profile_name": "aggressive",
    "consciousness_level": 0
  }'
```

Response:
```json
{
  "response": "1. A civilization that lives inside a black hole...\n2. Time travelers who can only move sideways through parallel universes...\n3. ...",
  "session_id": "abc456...",
  "message_index": 1,
  "physics_state": {
    "t": 0.01,
    "tau_c": 0.85,
    "rho": 0.60,
    "delta_r": 0.40
  },
  "metadata": {
    "latency_ms": 2345.6,
    "tokens": {
      "prompt": 52,
      "completion": 287,
      "total": 339
    }
  }
}
```

---

## Sessions

### POST /sessions

Crée une nouvelle session explicitement.

#### Request

**Body:**
```json
{
  "profile_name": "string (optional, default: 'balanced')",
  "max_messages": "integer (optional, default: 100)",
  "time_mapping": "string (optional, default: 'logarithmic')"
}
```

**Parameters:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `profile_name` | string | ❌ | "balanced" | Profil Bézier à utiliser |
| `max_messages` | integer | ❌ | 100 | Nombre max de messages pour t ∈ [0, 1] |
| `time_mapping` | string | ❌ | "logarithmic" | Type de mapping temps (linear, logarithmic, sigmoid) |

#### Response

**Status: 201 Created**

```json
{
  "session_id": "string",
  "created_at": "string (ISO 8601)",
  "profile_name": "string"
}
```

#### Example

Request:
```bash
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "profile_name": "aggressive",
    "max_messages": 50,
    "time_mapping": "linear"
  }'
```

Response:
```json
{
  "session_id": "f7a8b9c0d1e2f3...",
  "created_at": "2025-01-14T10:30:00Z",
  "profile_name": "aggressive"
}
```

---

### GET /sessions/{session_id}

Récupère les informations d'une session.

#### Parameters

| Parameter | Type | Location | Description |
|-----------|------|----------|-------------|
| `session_id` | string | path | UUID de la session |

#### Response

**Status: 200 OK**

```json
{
  "session_id": "string",
  "created_at": "string (ISO 8601)",
  "message_count": "integer",
  "profile_name": "string",
  "time_mapping": "string",
  "last_activity": "string (ISO 8601)"
}
```

#### Example

Request:
```bash
curl http://localhost:8000/sessions/f7a8b9c0d1e2f3...
```

Response:
```json
{
  "session_id": "f7a8b9c0d1e2f3...",
  "created_at": "2025-01-14T10:30:00Z",
  "message_count": 15,
  "profile_name": "balanced",
  "time_mapping": "logarithmic",
  "last_activity": "2025-01-14T11:45:23Z"
}
```

---

### GET /sessions/{session_id}/history

Récupère l'historique complet d'une session.

#### Parameters

| Parameter | Type | Location | Description |
|-----------|------|----------|-------------|
| `session_id` | string | path | UUID de la session |
| `limit` | integer | query | Nombre max de messages (optionnel) |
| `offset` | integer | query | Offset pour pagination (optionnel) |

#### Response

**Status: 200 OK**

```json
{
  "session_id": "string",
  "messages": [
    {
      "role": "string (user | assistant | system)",
      "content": "string",
      "timestamp": "string (ISO 8601)",
      "message_index": "integer",
      "physics_state": {
        "t": "float",
        "tau_c": "float",
        "rho": "float",
        "delta_r": "float"
      }
    }
  ],
  "total_messages": "integer"
}
```

#### Example

Request:
```bash
curl "http://localhost:8000/sessions/f7a8b9c0d1e2f3.../history?limit=10&offset=0"
```

Response:
```json
{
  "session_id": "f7a8b9c0d1e2f3...",
  "messages": [
    {
      "role": "user",
      "content": "Hello Lyra",
      "timestamp": "2025-01-14T10:30:15Z",
      "message_index": 1
    },
    {
      "role": "assistant",
      "content": "Hello! How can I help you today?",
      "timestamp": "2025-01-14T10:30:17Z",
      "message_index": 2,
      "physics_state": {
        "t": 0.01,
        "tau_c": 0.50,
        "rho": 0.50,
        "delta_r": 0.30
      }
    },
    ...
  ],
  "total_messages": 15
}
```

---

### DELETE /sessions/{session_id}

Supprime une session et tout son historique.

#### Parameters

| Parameter | Type | Location | Description |
|-----------|------|----------|-------------|
| `session_id` | string | path | UUID de la session |

#### Response

**Status: 200 OK**

```json
{
  "success": true,
  "message": "Session deleted"
}
```

**Status: 404 Not Found**

```json
{
  "detail": "Session not found"
}
```

#### Example

Request:
```bash
curl -X DELETE http://localhost:8000/sessions/f7a8b9c0d1e2f3...
```

Response:
```json
{
  "success": true,
  "message": "Session deleted"
}
```

---

## Profiles

### GET /profiles

Liste tous les profils Bézier disponibles.

#### Response

**Status: 200 OK**

```json
{
  "profiles": [
    {
      "name": "string",
      "description": "string",
      "parameters": ["string"]
    }
  ]
}
```

#### Example

Request:
```bash
curl http://localhost:8000/profiles
```

Response:
```json
{
  "profiles": [
    {
      "name": "balanced",
      "description": "Balanced temperature and focus throughout conversation",
      "parameters": ["tau_c", "rho", "delta_r"]
    },
    {
      "name": "aggressive",
      "description": "High temperature, exploratory behavior",
      "parameters": ["tau_c", "rho", "delta_r"]
    },
    {
      "name": "conservative",
      "description": "Low temperature, focused and deterministic",
      "parameters": ["tau_c", "rho", "delta_r"]
    }
  ]
}
```

---

### GET /profiles/{profile_name}

Récupère les détails d'un profil spécifique.

#### Parameters

| Parameter | Type | Location | Description |
|-----------|------|----------|-------------|
| `profile_name` | string | path | Nom du profil |
| `preview` | integer | query | Nombre de points à échantillonner (optionnel) |

#### Response (sans preview)

**Status: 200 OK**

```json
{
  "name": "string",
  "description": "string",
  "curves": {
    "tau_c": [
      {"t": "float", "value": "float"}
    ],
    "rho": [
      {"t": "float", "value": "float"}
    ],
    "delta_r": [
      {"t": "float", "value": "float"}
    ],
    "kappa": [
      {"t": "float", "value": "float"}
    ]
  }
}
```

#### Response (avec preview)

**Status: 200 OK**

```json
{
  "name": "string",
  "description": "string",
  "trajectory": [
    {
      "t": "float",
      "tau_c": "float",
      "rho": "float",
      "delta_r": "float",
      "kappa": "float"
    }
  ]
}
```

#### Examples

**Without preview:**

Request:
```bash
curl http://localhost:8000/profiles/balanced
```

Response:
```json
{
  "name": "balanced",
  "description": "Balanced temperature and focus",
  "curves": {
    "tau_c": [
      {"t": 0.0, "value": 0.50},
      {"t": 0.33, "value": 0.45},
      {"t": 0.67, "value": 0.55},
      {"t": 1.0, "value": 0.50}
    ],
    "rho": [
      {"t": 0.0, "value": 0.50},
      {"t": 0.33, "value": 0.50},
      {"t": 0.67, "value": 0.50},
      {"t": 1.0, "value": 0.50}
    ],
    "delta_r": [
      {"t": 0.0, "value": 0.30},
      {"t": 0.33, "value": 0.35},
      {"t": 0.67, "value": 0.35},
      {"t": 1.0, "value": 0.30}
    ]
  }
}
```

**With preview:**

Request:
```bash
curl "http://localhost:8000/profiles/balanced?preview=20"
```

Response:
```json
{
  "name": "balanced",
  "description": "Balanced temperature and focus",
  "trajectory": [
    {"t": 0.00, "tau_c": 0.500, "rho": 0.500, "delta_r": 0.300},
    {"t": 0.05, "tau_c": 0.487, "rho": 0.500, "delta_r": 0.312},
    {"t": 0.10, "tau_c": 0.475, "rho": 0.500, "delta_r": 0.323},
    {"t": 0.15, "tau_c": 0.463, "rho": 0.500, "delta_r": 0.333},
    {"t": 0.20, "tau_c": 0.452, "rho": 0.500, "delta_r": 0.342},
    ...
    {"t": 1.00, "tau_c": 0.500, "rho": 0.500, "delta_r": 0.300}
  ]
}
```

---

## Graph (Lyra-ACE)

L'API Graph fournit des endpoints pour les mutations du graphe sémantique avec piste d'audit et capacités de rollback.

### POST /graph/delta

Applique un delta (mutation) atomique au graphe sémantique.

#### Request

**Paramètres Query:**

| Paramètre | Type | Requis | Défaut | Description |
|-----------|------|--------|--------|-------------|
| `session_id` | string | Non | - | ID de session pour l'audit |
| `kappa_alpha` | float | Non | 0.5 | Coefficient kappa hybride [0, 1] |

**Body:**
```json
{
  "operation": "string (add_edge | update_edge | delete_edge | add_node | update_node | delete_node)",
  "source": "string (requis)",
  "target": "string (requis pour opérations sur arêtes)",
  "weight": "float (0-1, requis pour add/update edge)",
  "confidence": "float (0-1, défaut: 1.0)",
  "model_source": "string (défaut: 'system')",
  "reason": "string (optionnel)"
}
```

#### Response

**Status: 200 OK**

```json
{
  "delta_id": "integer",
  "operation": "string",
  "source": "string",
  "target": "string",
  "old_weight": "float (null si nouveau)",
  "new_weight": "float",
  "old_kappa": "float (null si nouveau)",
  "new_kappa": "float",
  "applied_at": "float (timestamp)"
}
```

#### Réponses d'erreur

**400 Bad Request** - Paramètres de delta invalides
**429 Too Many Requests** - Limite de mutation dépassée (5% de la taille du graphe)
**404 Not Found** - Concept source ou cible non trouvé

#### Exemple

Requête:
```bash
curl -X POST "http://localhost:8000/graph/delta?session_id=abc-123&kappa_alpha=0.5" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "add_edge",
    "source": "entropie",
    "target": "chaos",
    "weight": 0.75,
    "confidence": 0.9,
    "reason": "Extrait de la conversation"
  }'
```

Réponse:
```json
{
  "delta_id": 42,
  "operation": "add_edge",
  "source": "entropie",
  "target": "chaos",
  "old_weight": null,
  "new_weight": 0.75,
  "old_kappa": null,
  "new_kappa": 0.62,
  "applied_at": 1705234567.89
}
```

---

### GET /graph/kappa/{source}/{target}

Calcule la courbure κ hybride pour une arête.

#### Paramètres

| Paramètre | Type | Emplacement | Description |
|-----------|------|-------------|-------------|
| `source` | string | path | Concept source |
| `target` | string | path | Concept cible |
| `alpha` | float | query | Coefficient hybride [0, 1] (défaut: 0.5) |
| `store_history` | boolean | query | Stocker dans kappa_history (défaut: false) |

#### Response

**Status: 200 OK**

```json
{
  "source": "string",
  "target": "string",
  "kappa_ollivier": "float",
  "kappa_jaccard": "float",
  "kappa_hybrid": "float",
  "alpha": "float"
}
```

**Formules:**
- **Ollivier**: `kappa_o = 1/deg(u) + 1/deg(v) - 2/w`
- **Jaccard**: `kappa_j = |N(u) ∩ N(v)| / |N(u) ∪ N(v)|`
- **Hybride**: `kappa = alpha * kappa_o_norm + (1-alpha) * kappa_j`

---

### GET /graph/deltas

Récupère l'historique des deltas.

#### Paramètres

| Paramètre | Type | Emplacement | Description |
|-----------|------|-------------|-------------|
| `session_id` | string | query | Filtrer par session (optionnel) |
| `limit` | integer | query | Résultats max (défaut: 100, max: 1000) |
| `include_rolled_back` | boolean | query | Inclure les deltas annulés (défaut: false) |

#### Response

**Status: 200 OK**

```json
{
  "deltas": [
    {
      "delta_id": "integer",
      "operation": "string",
      "source": "string",
      "target": "string",
      "old_weight": "float",
      "new_weight": "float",
      "applied_at": "float",
      "rolled_back": "boolean"
    }
  ],
  "count": "integer"
}
```

---

### POST /graph/rollback

Annule des deltas pour restaurer l'état précédent du graphe.

#### Paramètres

| Paramètre | Type | Emplacement | Requis | Description |
|-----------|------|-------------|--------|-------------|
| `session_id` | string | query | Oui | ID de session |
| `to_timestamp` | float | query | Non* | Annuler jusqu'à ce timestamp |
| `delta_ids` | array | query | Non* | IDs de deltas spécifiques à annuler |

*`to_timestamp` ou `delta_ids` doit être fourni.

#### Response

**Status: 200 OK**

```json
{
  "rolled_back": "integer (nombre)",
  "session_id": "string"
}
```

---

### GET /graph/stats

Obtient les statistiques de mutation.

#### Response

**Status: 200 OK**

```json
{
  "total_deltas": "integer",
  "deltas_by_operation": {
    "add_edge": "integer",
    "update_edge": "integer",
    "delete_edge": "integer"
  },
  "rolled_back_count": "integer",
  "graph_size": "integer",
  "mutation_limit": "integer (5% du graphe)"
}
```

---

## ESMM Phase 1 (Lyra-ACE)

Endpoints pour la Phase 1 du protocole ESMM: population du graphe, generation de relations, et injection de graines semantiques.

### POST /graph/populate

Charge les concepts depuis un fichier et genere leurs embeddings.

#### Request

**Body:**
```json
{
  "source_file": "string (default: 'data/topics.txt')",
  "generate_embeddings": "boolean (default: true)",
  "batch_size": "integer (1-200, default: 50)",
  "skip_existing": "boolean (default: true)"
}
```

#### Response

**Status: 200 OK**

```json
{
  "concepts_loaded": "integer",
  "concepts_skipped": "integer",
  "embeddings_generated": "integer",
  "embeddings_failed": "integer",
  "duplicates_found": "integer",
  "duration_ms": "float",
  "errors": ["string"]
}
```

#### Exemple

```bash
curl -X POST http://localhost:8000/graph/populate \
  -H "Content-Type: application/json" \
  -d '{
    "source_file": "data/topics.txt",
    "generate_embeddings": true,
    "batch_size": 50
  }'
```

---

### POST /graph/generate-relations

Genere des relations basees sur la similarite des embeddings.

#### Request

**Body:**
```json
{
  "similarity_threshold": "float (0.3-0.95, default: 0.6)",
  "confidence": "float (0.1-1.0, default: 0.7)",
  "max_neighbors": "integer (1-100, default: 20)",
  "limit_concepts": "integer (optional)"
}
```

#### Response

**Status: 200 OK**

```json
{
  "relations_created": "integer",
  "relations_skipped": "integer",
  "concepts_processed": "integer",
  "average_similarity": "float",
  "duration_ms": "float",
  "errors": ["string"]
}
```

---

### POST /graph/inject-seed

Injecte la graine semantique ESMM dans le graphe.

#### Request

**Body:**
```json
{
  "seed_type": "string (minimal | standard | extended)",
  "generate_embeddings": "boolean (default: true)",
  "skip_existing_concepts": "boolean (default: true)"
}
```

**Types de graines:**
- `minimal`: ~10 paires essentielles (cause/effet, theorie/pratique)
- `standard`: ~40 paires couvrant les domaines principaux
- `extended`: ~80 paires incluant sciences, cognition, langage

#### Response

**Status: 200 OK**

```json
{
  "concepts_created": "integer",
  "relations_created": "integer",
  "concepts_existed": "integer",
  "duration_ms": "float",
  "seed_type": "string",
  "errors": ["string"]
}
```

#### Exemple

```bash
curl -X POST http://localhost:8000/graph/inject-seed \
  -H "Content-Type: application/json" \
  -d '{"seed_type": "standard", "generate_embeddings": true}'
```

---

### GET /graph/similar/{concept_id}

Trouve les concepts les plus similaires via embeddings.

#### Parametres

| Parametre | Type | Emplacement | Description |
|-----------|------|-------------|-------------|
| `concept_id` | string | path | ID du concept source |
| `top_k` | integer | query | Nombre de resultats (1-100, default: 10) |
| `min_similarity` | float | query | Similarite minimum (0-1, default: 0.5) |

#### Response

**Status: 200 OK**

```json
{
  "concept_id": "string",
  "similar_concepts": [
    {"concept_id": "string", "similarity": "float"}
  ],
  "count": "integer"
}
```

---

### GET /graph/phase1-stats

Statistiques completes de la Phase 1 ESMM.

#### Response

**Status: 200 OK**

```json
{
  "population": {
    "total_concepts": "integer",
    "with_embeddings": "integer",
    "by_source": {"seed": "integer", "topics": "integer"}
  },
  "relations": {
    "total_relations": "integer",
    "by_model_source": {"seed": "integer", "embedding_similarity": "integer"},
    "weight_distribution": {"high": "integer", "medium": "integer", "low": "integer"},
    "average_kappa": "float"
  },
  "seed": {
    "seed_concepts": "integer",
    "seed_relations": "integer",
    "average_kappa": "float",
    "average_degree": "float",
    "seed_coverage": "boolean"
  }
}
```

---

### GET /graph/seeds/available

Liste les types de graines disponibles.

#### Response

**Status: 200 OK**

```json
{
  "minimal": {
    "concepts": "integer",
    "relations": "integer",
    "categories": ["string"]
  },
  "standard": {
    "concepts": "integer",
    "relations": "integer",
    "categories": ["string"]
  },
  "extended": {
    "concepts": "integer",
    "relations": "integer",
    "categories": ["string"]
  }
}
```

---

### GET /graph/cochain/export

Exporte la 0-cochaine pour visualisation externe (PCA/t-SNE).

#### Parametres

| Parametre | Type | Emplacement | Description |
|-----------|------|-------------|-------------|
| `format` | string | query | Format d'export (json \| csv, default: json) |
| `min_consensus` | float | query | Consensus minimum (0-1, default: 0) |

#### Response (JSON)

**Status: 200 OK**

```json
{
  "points": [
    {
      "id": "string",
      "consensus": "float",
      "type": "string (generalist | specialized | hybrid)",
      "x": "float",
      "y": "float",
      "z": "float"
    }
  ],
  "count": "integer"
}
```

#### Response (CSV)

Fichier CSV telecharge avec colonnes: `id,consensus,type,x,y,z`

---

### GET /graph/cochain/stats

Statistiques de la 0-cochaine ESMM.

#### Response

**Status: 200 OK**

```json
{
  "total_entries": "integer",
  "by_epistemic_type": {
    "generalist": {"count": "integer", "avg_consensus": "float"},
    "specialized": {"count": "integer", "avg_consensus": "float"},
    "hybrid": {"count": "integer", "avg_consensus": "float"}
  },
  "average_consensus": "float",
  "average_stability": "float",
  "consensus_distribution": {
    "high": "integer",
    "medium": "integer",
    "low": "integer"
  }
}
```

---

## ESMM Phase 3 - Orchestration

Endpoints pour le protocole ESMM complet avec orchestration autonome, detection de lacunes et construction de 0-cochaine.

### POST /graph/esmm-run

Lance un run ESMM complet en arriere-plan.

#### Request

**Body:**
```json
{
  "models": ["llama3.1:8b", "deepseek-r1:8b"],
  "seed_type": "standard",
  "cycles_per_type": {
    "divergent": 5,
    "debate": 3,
    "meta": 2
  },
  "min_consensus": 0.5,
  "adaptive_cycles": true,
  "detect_gaps": true,
  "build_cochain": true
}
```

**Parametres:**

| Champ | Type | Requis | Defaut | Description |
|-------|------|--------|--------|-------------|
| `models` | array | Oui | - | Liste des modeles (max 2, whitelist) |
| `seed_type` | string | Non | "standard" | Type de graine (minimal/standard/extended) |
| `cycles_per_type` | object | Non | {3,2,1} | Cycles par type |
| `min_consensus` | float | Non | 0.5 | Seuil de consensus minimum |
| `adaptive_cycles` | boolean | Non | true | Adaptation dynamique |
| `detect_gaps` | boolean | Non | true | Detection de lacunes |
| `build_cochain` | boolean | Non | true | Construction 0-cochaine |

#### Response

**Status: 202 Accepted**

```json
{
  "run_id": 1,
  "status": "running",
  "message": "Run ESMM demarre en arriere-plan",
  "cycles_planned": 10,
  "models": ["llama3.1:8b", "deepseek-r1:8b"]
}
```

---

### GET /graph/esmm-run/{run_id}

Recupere le statut d'un run ESMM.

#### Parametres

| Parametre | Type | Emplacement | Description |
|-----------|------|-------------|-------------|
| `run_id` | integer | path | ID du run |

#### Response

**Status: 200 OK**

```json
{
  "run_id": 1,
  "status": "running",
  "progress_percent": 45.5,
  "cycles_completed": 5,
  "cycles_planned": 10,
  "current_cycle": "debate",
  "current_iteration": 2,
  "triplets_extracted": 127,
  "triplets_injected": 98,
  "started_at": "2026-01-22T14:30:00Z",
  "elapsed_seconds": 345.2
}
```

**Valeurs de status:**
- `pending` : En attente
- `running` : En cours
- `paused` : Mis en pause
- `completed` : Termine
- `failed` : Echec

---

### GET /graph/esmm-run/{run_id}/result

Recupere le resultat complet d'un run termine.

#### Response

**Status: 200 OK**

```json
{
  "run_id": 1,
  "status": "completed",
  "cycles_completed": 10,
  "total_triplets": 245,
  "triplets_injected": 198,
  "cochain_size": 156,
  "gaps_detected": 23,
  "coverage_score": 0.72,
  "consensus_density": 0.68,
  "epistemic_diversity": 0.54,
  "structural_stability": 0.81,
  "duration_ms": 845200,
  "models_used": ["llama3.1:8b", "deepseek-r1:8b"],
  "adaptation_applied": true,
  "cycles_added": 2
}
```

---

### POST /graph/esmm-run/{run_id}/pause

Met en pause un run ESMM en cours.

#### Response

**Status: 200 OK**

```json
{
  "run_id": 1,
  "status": "paused",
  "message": "Run mis en pause apres le cycle 5",
  "can_resume": true
}
```

---

### POST /graph/esmm-run/{run_id}/resume

Reprend un run ESMM en pause.

#### Response

**Status: 200 OK**

```json
{
  "run_id": 1,
  "status": "running",
  "message": "Run repris a partir du cycle 6",
  "cycles_remaining": 5
}
```

---

### GET /graph/esmm-run/{run_id}/cycles

Recupere l'historique des cycles d'un run.

#### Parametres

| Parametre | Type | Emplacement | Description |
|-----------|------|-------------|-------------|
| `run_id` | integer | path | ID du run |
| `cycle_type` | string | query | Filtrer par type (divergent/debate/meta) |
| `limit` | integer | query | Nombre max (defaut: 20) |

#### Response

**Status: 200 OK**

```json
{
  "run_id": 1,
  "cycles": [
    {
      "cycle_id": 1,
      "cycle_type": "divergent",
      "iteration": 1,
      "question": "Quels concepts sont lies a entropie?",
      "triplets_extracted": 12,
      "consensus_score": 0.75,
      "duration_ms": 45200,
      "timestamp": "2026-01-22T14:30:15Z"
    }
  ],
  "total": 10
}
```

---

### GET /graph/coverage/metrics

Recupere les metriques de couverture globales du graphe.

#### Response

**Status: 200 OK**

```json
{
  "coverage_score": 0.72,
  "consensus_density": 0.68,
  "epistemic_diversity": 0.54,
  "structural_stability": 0.81,
  "graph_density": 0.023,
  "isolated_ratio": 0.12,
  "total_concepts": 1456,
  "total_relations": 3892,
  "avg_degree": 5.34,
  "clustering_coefficient": 0.42
}
```

**Metriques:**
- `coverage_score` : Score composite [0,1]
- `consensus_density` : Accord moyen inter-modeles
- `epistemic_diversity` : Entropie Shannon des types
- `structural_stability` : Coefficient de clustering moyen
- `isolated_ratio` : Proportion de concepts isoles

---

### GET /graph/gaps/active

Recupere les lacunes actives prioritisees.

#### Parametres

| Parametre | Type | Emplacement | Description |
|-----------|------|-------------|-------------|
| `gap_type` | string | query | Filtrer par type (isolated/unstable/bridge) |
| `limit` | integer | query | Nombre max (defaut: 30) |

#### Response

**Status: 200 OK**

```json
[
  {
    "gap_id": 1,
    "gap_type": "bridge",
    "priority": 0.85,
    "details": {
      "cluster_a": "thermodynamique",
      "cluster_b": "theorie_information",
      "distance": 0.65
    },
    "suggested_question": "Quel est le lien entre entropie thermodynamique et entropie de Shannon?",
    "detected_at": "2026-01-22T14:45:00Z",
    "run_id": 1
  },
  {
    "gap_id": 2,
    "gap_type": "isolated",
    "priority": 0.72,
    "details": {
      "concept": "neguentropie",
      "degree": 2
    },
    "suggested_question": "Quels concepts sont relies a neguentropie?",
    "detected_at": "2026-01-22T14:45:00Z",
    "run_id": 1
  }
]
```

---

### POST /graph/gaps/{gap_id}/address

Marque une lacune comme adressee.

#### Parametres

| Parametre | Type | Emplacement | Description |
|-----------|------|-------------|-------------|
| `gap_id` | integer | path | ID de la lacune |

#### Request

**Body:**
```json
{
  "resolution": "explored",
  "notes": "Exploration via cycle divergent supplementaire"
}
```

#### Response

**Status: 200 OK**

```json
{
  "gap_id": 1,
  "status": "addressed",
  "addressed_at": "2026-01-22T15:00:00Z"
}
```

---

## Multi-Model (Lyra-ACE)

L'API Multi-Model permet la génération avec plusieurs LLMs et le calcul de consensus.

### GET /multimodel/models

Liste les modèles disponibles sur Ollama.

#### Paramètres

| Paramètre | Type | Emplacement | Description |
|-----------|------|-------------|-------------|
| `refresh` | boolean | query | Forcer rafraîchissement (défaut: false) |

#### Response

**Status: 200 OK**

```json
{
  "models": ["llama3.1:8b", "mistral:latest", "gpt-oss:20b"],
  "count": 3
}
```

---

### POST /multimodel/generate

Génère des réponses avec plusieurs modèles et calcule le consensus.

#### Request

**Body:**
```json
{
  "text": "string (requis)",
  "models": ["string"] (requis, min 2),
  "session_id": "string (optionnel)",
  "profile": "string (défaut: 'balanced')",
  "stop_on_first_success": "boolean (défaut: false)"
}
```

#### Response

**Status: 200 OK**

```json
{
  "best_response": "string",
  "best_model": "string",
  "responses": {
    "nom_modele": {
      "model": "string",
      "text": "string",
      "latency_ms": "float",
      "tokens": "integer",
      "success": "boolean",
      "error": "string (null si succès)"
    }
  },
  "consensus": {
    "length_variance": "float",
    "avg_latency_ms": "float",
    "success_rate": "float",
    "model_weights": {
      "nom_modele": "float"
    }
  },
  "session_id": "string",
  "physics_state": {
    "t": "float",
    "tau_c": "float",
    "rho": "float",
    "delta_r": "float"
  }
}
```

#### Exemple

Requête:
```bash
curl -X POST http://localhost:8000/multimodel/generate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Expliquez l'\''entropie simplement",
    "models": ["llama3.1:8b", "mistral:latest"],
    "profile": "analytical"
  }'
```

Réponse:
```json
{
  "best_response": "L'entropie est une mesure du désordre...",
  "best_model": "mistral:latest",
  "responses": {
    "llama3.1:8b": {
      "model": "llama3.1:8b",
      "text": "L'entropie mesure le caractère aléatoire...",
      "latency_ms": 1234.5,
      "tokens": 87,
      "success": true,
      "error": null
    },
    "mistral:latest": {
      "model": "mistral:latest",
      "text": "L'entropie est une mesure du désordre...",
      "latency_ms": 1456.2,
      "tokens": 92,
      "success": true,
      "error": null
    }
  },
  "consensus": {
    "length_variance": 0.12,
    "avg_latency_ms": 1345.35,
    "success_rate": 1.0,
    "model_weights": {
      "llama3.1:8b": 0.48,
      "mistral:latest": 0.52
    }
  },
  "session_id": "xyz-789",
  "physics_state": {
    "t": 0.01,
    "tau_c": 0.45,
    "rho": 0.55,
    "delta_r": 0.35
  }
}
```

---

## System

### GET /

Sert l'interface web statique.

#### Response

**Status: 200 OK**

Retourne le fichier HTML de l'interface web (`app/static/index.html`).

---

### GET /api

Endpoint racine de l'API (informations basiques).

#### Response

**Status: 200 OK**

```json
{
  "name": "Lyra Clean API",
  "version": "1.0.0",
  "description": "Physics-driven LLM conversation system"
}
```

#### Example

Request:
```bash
curl http://localhost:8000/api
```

Response:
```json
{
  "name": "Lyra Clean API",
  "version": "1.0.0",
  "description": "Physics-driven LLM conversation system"
}
```

---

### GET /health

Health check complet du système.

#### Response

**Status: 200 OK**

```json
{
  "status": "string (healthy | degraded | unhealthy)",
  "timestamp": "string (ISO 8601)",
  "database": {
    "connected": "boolean",
    "concepts": "integer",
    "sessions": "integer",
    "events": "integer"
  },
  "ollama": {
    "connected": "boolean",
    "model": "string",
    "available": "boolean",
    "models": ["string"]
  }
}
```

**Status Codes:**
- `healthy` : Tous les composants fonctionnent
- `degraded` : Certains composants ne fonctionnent pas (ex: Ollama down mais DB OK)
- `unhealthy` : Composants critiques en échec

#### Example

Request:
```bash
curl http://localhost:8000/health
```

Response (healthy):
```json
{
  "status": "healthy",
  "timestamp": "2025-01-14T10:30:00Z",
  "database": {
    "connected": true,
    "concepts": 1234,
    "sessions": 56,
    "events": 789
  },
  "ollama": {
    "connected": true,
    "model": "gpt-oss:20b",
    "available": true,
    "models": ["gpt-oss:20b", "llama3:latest"]
  }
}
```

Response (degraded):
```json
{
  "status": "degraded",
  "timestamp": "2025-01-14T10:30:00Z",
  "database": {
    "connected": true,
    "concepts": 1234,
    "sessions": 56,
    "events": 789
  },
  "ollama": {
    "connected": false,
    "error": "Connection refused"
  }
}
```

---

### GET /stats

Statistiques système globales.

#### Response

**Status: 200 OK**

```json
{
  "database": {
    "size_mb": "float",
    "concepts": "integer",
    "relations": "integer",
    "sessions": "integer",
    "events": "integer",
    "profiles": "integer"
  },
  "uptime_seconds": "float"
}
```

#### Example

Request:
```bash
curl http://localhost:8000/stats
```

Response:
```json
{
  "database": {
    "size_mb": 45.6,
    "concepts": 1234,
    "relations": 5678,
    "sessions": 56,
    "events": 789,
    "profiles": 3
  },
  "uptime_seconds": 3600.5
}
```

---

## Rate Limiting

Configurable dans `config.yaml` :

```yaml
security:
  rate_limit_per_minute: 60
```

Lorsque la limite est atteinte :

**Status: 429 Too Many Requests**

```json
{
  "detail": "Rate limit exceeded. Try again in 30 seconds."
}
```

Headers inclus :
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1642156800
```

---

## Error Codes Reference

| Code | Nom | Description |
|------|-----|-------------|
| 200 | OK | Requête réussie |
| 201 | Created | Ressource créée (ex: nouvelle session) |
| 400 | Bad Request | Paramètres invalides |
| 404 | Not Found | Ressource introuvable (session, profil) |
| 422 | Unprocessable Entity | Validation Pydantic échouée |
| 429 | Too Many Requests | Rate limit dépassé |
| 500 | Internal Server Error | Erreur serveur (Ollama down, DB error) |
| 503 | Service Unavailable | Service temporairement indisponible |

---

## Webhooks (Future)

Fonctionnalité prévue pour notifications :
- Nouvelle session créée
- Métriques de conscience dépassent seuil
- Adaptation suggérée

Configuration future :
```yaml
webhooks:
  enabled: true
  url: "https://your-webhook-endpoint.com"
  events: ["session.created", "consciousness.alert"]
```

---

## SDK / Client Libraries

### Python

```python
import requests

class LyraClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session_id = None

    def chat(self, message, consciousness_level=0, **kwargs):
        response = requests.post(
            f"{self.base_url}/chat/message",
            json={
                "message": message,
                "session_id": self.session_id,
                "consciousness_level": consciousness_level,
                **kwargs
            }
        )
        response.raise_for_status()
        data = response.json()
        self.session_id = data["session_id"]
        return data

# Usage
client = LyraClient()
response = client.chat("Hello Lyra!", consciousness_level=2)
print(response["response"])
```

### JavaScript (Node.js)

```javascript
const axios = require('axios');

class LyraClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
        this.sessionId = null;
    }

    async chat(message, consciousnessLevel = 0, options = {}) {
        const response = await axios.post(`${this.baseUrl}/chat/message`, {
            message,
            session_id: this.sessionId,
            consciousness_level: consciousnessLevel,
            ...options
        });

        this.sessionId = response.data.session_id;
        return response.data;
    }
}

// Usage
const client = new LyraClient();
const response = await client.chat('Hello Lyra!', 2);
console.log(response.response);
```

### cURL Scripts

**chat.sh**
```bash
#!/bin/bash
SESSION_ID=""

chat() {
    local MESSAGE="$1"
    local LEVEL="${2:-0}"

    RESPONSE=$(curl -s -X POST http://localhost:8000/chat/message \
        -H "Content-Type: application/json" \
        -d "{
            \"message\": \"$MESSAGE\",
            \"session_id\": \"$SESSION_ID\",
            \"consciousness_level\": $LEVEL
        }")

    SESSION_ID=$(echo "$RESPONSE" | jq -r '.session_id')
    echo "$RESPONSE" | jq -r '.response'
}

# Usage
chat "Hello Lyra!" 0
chat "Tell me more" 2
```

---

## OpenAPI Specification

Documentation OpenAPI disponible à :

```
http://localhost:8000/docs
```

Ou téléchargez le JSON :

```bash
curl http://localhost:8000/openapi.json > lyra_openapi.json
```

---

## Support

- 📖 [Guide utilisateur](USER_GUIDE.md)
- 🔧 [Guide développeur](DEVELOPER_GUIDE.md)
- 🐛 [GitHub Issues](https://github.com/yourusername/lyra_clean_bis/issues)
