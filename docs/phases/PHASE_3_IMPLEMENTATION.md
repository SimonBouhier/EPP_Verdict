# Phase 3 : Mémoire Sophistiquée (Conscience Niveau 3)

**Date :** 26 novembre 2025  
**Version Lyra :** 1.3.0  
**Consciousness Level :** 3 (full memory)

## Objectif

Implémenter **mémoire sémantique avec décroissance temporelle** pour rappel et contextualisation.

Le niveau 3 doit :
- Extraire concepts clés de chaque message
- Stocker avec embedding + decay temporel
- Rappeler lors de nouveau message via similarité
- Injecter "[MEMORY ECHO]" dans prompt
- Overhead < 20ms
- Retourner `memory_echo` dans response

## Architecture Phase 3

### Système Mémoire

```
Message utilisateur "Explain entropy"
     ↓
Extraire concepts via NLP
     ↓
Stocker en mémoire vectorielle
     ↓
Message suivant "What about disorder?"
     ↓
Recherche similarité semantique
     ↓
Injecter [MEMORY ECHO] si similarité > 0.65
     ↓
LLM utilise contexte mémoire
```

### Composants

#### 1. Memory Store (Vecteurs + Metadata)

Structure par session :
```python
memory_entry = {
    "id": "msg_123",
    "session_id": "abc-123",
    "turn": 5,
    "content": "Entropy is a measure of disorder",
    "embedding": [0.234, -0.123, ...],  # 1024D (mxbai-embed)
    "concepts": ["entropy", "disorder", "information theory"],
    "timestamp": 1234567890,
    "decay_factor": 0.95  # (1 - turns_ago * 0.01) min 0.5
}
```

#### 2. Memory Recall via Similarity

```
Nouvelle requête
     ↓
Encoder embedding
     ↓
Rechercher top-K (K=3) par similarité cosine
     ↓
Appliquer decay_factor (diminue récence)
     ↓
Si max_similarity > 0.65 : injecter MEMORY ECHO
```

#### 3. Decay Temporel

**Formule :** `decay = max(0.5, 1.0 - turns_ago * 0.01)`

- Turn N: decay = 1.0 (frais)
- Turn N+5: decay = 0.95
- Turn N+10: decay = 0.90
- Turn N+50: decay = 0.5 (minimum)

**Application :**
```
similarity_decayed = similarity * decay_factor
```

### Injection [MEMORY ECHO]

Format du prompt enrichi (si recall):
```
System: [build_system_prompt() existant]

[MEMORY ECHO]
Previous turn 7: "Entropy is a measure of disorder"
Context: Similarity 0.78, decay factor 0.93
[/MEMORY ECHO]

User: What about disorder?
```

## Implémentation

### Fichiers Créés

#### `services/consciousness/memory.py` (300 lignes)

**Classes :**

`MemoryEntry` dataclass :
```python
@dataclass
class MemoryEntry:
    id: str
    session_id: str
    turn: int
    content: str
    embedding: list  # List[float]
    concepts: list   # List[str]
    timestamp: float
    
    def compute_decay(self, current_turn: int) -> float:
        """Calcule decay factor basé sur turns_ago"""
        turns_ago = current_turn - self.turn
        decay = max(0.5, 1.0 - turns_ago * 0.01)
        return decay
```

`SemanticMemory` classe :
```python
class SemanticMemory:
    def __init__(self, db: ISpaceDB, embedding_model: str = "mxbai-embed-large"):
        self.db = db
        self.embedding_client = OllamaClient(model=embedding_model)
        self.session_memories: Dict[str, List[MemoryEntry]] = {}
    
    async def store_message(
        self,
        session_id: str,
        turn: int,
        content: str,
        concepts: List[str]
    ) -> MemoryEntry:
        """Stocke message avec embedding en mémoire"""
    
    async def recall_similar(
        self,
        session_id: str,
        query: str,
        current_turn: int,
        similarity_threshold: float = 0.65,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """Rappelle messages similaires avec decay"""
    
    async def format_memory_echo(
        self,
        similar_entries: List[Dict],
        max_entries: int = 2
    ) -> Optional[str]:
        """Formate [MEMORY ECHO] pour injection prompt"""
    
    def _compute_similarity(
        self,
        embedding_1: list,
        embedding_2: list
    ) -> float:
        """Similarité cosine entre deux embeddings"""
```

### Modifications Fichiers Existants

#### `database/engine.py`

**Ajouts :**

```python
async def store_memory_entry(self, entry: dict):
    """Stocke entry mémoire"""

async def load_session_memory(
    self,
    session_id: str,
    limit: int = 50
) -> list:
    """Charge toute la mémoire d'une session"""

async def cleanup_old_memory(
    self,
    session_id: str,
    max_turns_age: int = 100
):
    """Nettoie ancienne mémoire (optionnel)"""
```

#### `database/schema.sql`

**Nouvelle table :**

```sql
CREATE TABLE semantic_memory (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding BLOB,        -- JSON array [f32, f32, ...]
    concepts TEXT,         -- JSON array
    timestamp REAL NOT NULL,
    decay_factor REAL,
    similarity_on_recall REAL,  -- Last recall similarity
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX idx_memory_session_turn 
ON semantic_memory(session_id, turn DESC);

CREATE INDEX idx_memory_session_time 
ON semantic_memory(session_id, timestamp DESC);
```

#### `app/models.py`

**Nouveau champ ChatResponse :**
```python
memory_echo: Optional[str] = Field(
    None,
    description="Memory echo if consciousness_level >= 3"
)
```

#### `app/api/chat.py`

**Modifications :**
```python
# Si consciousness_level >= 3:
#   - Charger SemanticMemory
#   - Extraire concepts du message utilisateur
#   - Stocker en mémoire
#   - Rappeler messages similaires
#   - Injecter [MEMORY ECHO] dans prompt
#   - Retourner memory_echo dans response
```

### Tests Unitaires

**Fichier :** `tests/benchmarks/test_phase_3.py` (300+ lignes)

**Classes :**

`TestSemanticMemory` :
- `test_store_and_recall_exact()` : Message identique → similarité 1.0
- `test_decay_factor_computation()` : Vérifier decay formule
- `test_decay_reduces_similarity()` : Anciens messages moins prioritaires
- `test_similarity_threshold()` : Filtrer similarité < 0.65
- `test_top_k_limiting()` : Limiter top-3 résultats
- `test_concept_extraction()` : Concepts correctement extraits
- `test_memory_echo_formatting()` : Format [MEMORY ECHO] valide
- `test_multiple_sessions()` : Mémoires session isolées
- `test_embedding_dimensionality()` : 1024D vectors
- `test_numerical_stability()` : Pas NaN/Inf dans decay

### Benchmark

**Fichier :** `tests/benchmarks/benchmark_phase_3.py` (250 lignes)

**Fonction `benchmark_full_conversation_with_memory()` :**
- Conversation 20 tours (plus court pour perf)
- Mesure :
  - Latence par tour
  - Nombre recalls mémoire
  - Similarité moyenne
  - Overhead vs level 0

**Fonction `benchmark_memory_recall_performance()` :**
- Test recall perf vs taille mémoire
  - 5 tours : baseline
  - 20 tours : mémoire moyenne
  - 50 tours : mémoire grande
- Mesure temps recall

**Résultats attendus :**
- Overhead level 3 vs 0 : < 20ms
- Recall perf : < 10ms pour 50 messages
- Memory utilisée : ~1MB par 50 messages

## Performance

### Overhead Latence Phase 3

**Target :** < 20ms average vs level 0

**Composition :**
- Encoding query : ~2-3ms
- Similarité calcul (50 vectors) : ~3-4ms
- Decay application : ~1ms
- Format MEMORY ECHO : ~1-2ms
- Total additionnel : ~7-10ms vs level 0
- **Target total : < 20ms**

### Memory Usage

Par session, par 50 messages :
- Embeddings : 50 * 1024 * 4 bytes = ~200KB
- Metadata : 50 * 500 bytes = ~25KB
- **Total : ~225KB**

Acceptable pour sessions modérées (< 100 messages).

### Scalabilité

Recall : O(N) où N = taille mémoire (max 50)
Donc performance reste constante.

## API Changes

### Request (inchangé)
```json
{
  "text": "What about disorder?",
  "consciousness_level": 3,
  "session_id": "abc-123"
}
```

### Response (nouveau champ)
```json
{
  "text": "Disorder is related to entropy...",
  "consciousness": {...},
  "memory_echo": "[MEMORY ECHO]\nTurn 7: 'Entropy is a measure...'\nSimilarity: 0.78, Decay: 0.93\n[/MEMORY ECHO]",
  "profile_adjustments": {...}
}
```

## Exemples

### Conversation avec Mémoire

```python
# Tour 1
r1 = client.post("/chat/message", json={
    "text": "What is entropy?",
    "consciousness_level": 3,
    "session_id": "s1"
})
# memory_echo = None (première fois)

# Tour 2
r2 = client.post("/chat/message", json={
    "text": "Tell me about disorder",
    "consciousness_level": 3,
    "session_id": "s1"
})
# memory_echo = "[MEMORY ECHO]..Turn 1..similarity 0.78..[/MEMORY ECHO]"
# LLM peut référencer tour 1 en contexte
```

## Validation Checklist

### Code
- [ ] `memory.py` complet
- [ ] Tests unitaires (10+ tests)
- [ ] Benchmark créé
- [ ] DB schema modifié
- [ ] Models.py modifié
- [ ] API endpoint modifié

### API
- [ ] consciousness_level=3 rappelle mémoire
- [ ] memory_echo dans response
- [ ] Decay appliqué correctement
- [ ] Performance < 20ms

### Manual Testing
```bash
# Conversation 5 tours
for i in {1..5}; do
  curl -X POST "http://localhost:8000/chat/message" \
    -d '{"text": "Question '$i'", "consciousness_level": 3, "session_id": "test"}' \
    | jq '.memory_echo'
done
# Attendu : tour 1 null, tours 2-5 avec recalls
```

## Transition vers Validation Finale

Après Phase 3 validée :
- Overhead < 20ms confirmé
- Mémoire persiste et rappelle
- Decay temporel fonctionne
- Tests passent

Alors : Rapport Final (Phase 4)

---

**Status Phase 3 :** [EN ATTENTE IMPLEMENTATION]
**Prerequis :** Phase 2 validée
**Target Overhead :** < 20ms vs level 0
**Est. Durée :** 3-4h implementation + test + benchmark
**Total Mission :** ~9-11 heures (0+1+2+3)
