# Phase 3 : Checklist

## Implementation

### Code Creation
- [ ] `services/consciousness/memory.py` (300 lignes)
  - [ ] `MemoryEntry` dataclass
  - [ ] `SemanticMemory` classe principale
  - [ ] `store_message()` - encoder + stocker
  - [ ] `recall_similar()` - similarité cosine + decay
  - [ ] `format_memory_echo()` - injection prompt
  - [ ] `_compute_similarity()` - cosine

- [ ] `tests/benchmarks/test_phase_3.py` (300+ lignes)
  - [ ] 10+ tests unitaires
  - [ ] Tester store/recall
  - [ ] Tester decay
  - [ ] Tester similarities
  - [ ] Tester edge cases

- [ ] `tests/benchmarks/benchmark_phase_3.py` (250 lignes)
  - [ ] `benchmark_full_conversation_with_memory()` - 20 tours
  - [ ] `benchmark_memory_recall_performance()` - scalabilité
  - [ ] Mesure latence, recalls, usage

### DB Changes
- [ ] Modifier `database/schema.sql`
  - [ ] Créer table `semantic_memory`
  - [ ] Créer indexes session + timestamp

- [ ] Modifier `database/engine.py` (ISpaceDB)
  - [ ] `store_memory_entry()` méthode
  - [ ] `load_session_memory()` méthode
  - [ ] `cleanup_old_memory()` optionnel

### Embedding Integration
- [ ] Intégrer mxbai-embed-large via Ollama
  - [ ] Vérifier que modèle disponible
  - [ ] Encoder test query
  - [ ] Vérifier 1024D output

### API Changes
- [ ] Modifier `app/models.py`
  - [ ] Ajouter `memory_echo` field à ChatResponse

- [ ] Modifier `app/api/chat.py`
  - [ ] Import `SemanticMemory`
  - [ ] Initialiser si consciousness_level >= 3
  - [ ] Appeler `recall_similar()` AVANT LLM
  - [ ] Injecter memory_echo dans prompt
  - [ ] Stocker message en mémoire APRÈS LLM
  - [ ] Inclure memory_echo dans response

### Unit Tests
```bash
pytest tests/benchmarks/test_phase_3.py -v
```
Attendu :
- [ ] 10+ tests découverts
- [ ] 10+ tests passent
- [ ] Duration < 5s

### Benchmark Execution

```bash
python tests/benchmarks/benchmark_phase_3.py
```
Attendu :
- [ ] Conversation 20 tours simulée
- [ ] Level 0 baseline
- [ ] Level 3 avec mémoire
- [ ] Overhead < 20ms
- [ ] Memory recalls fonctionnent

### Manual API Testing

#### Test 1 : Conversation Multi-Tour
```bash
# Tour 1
curl -X POST "http://localhost:8000/chat/message" \
  -d '{"text": "Explain entropy", "consciousness_level": 3, "session_id": "mem_test"}' \
  | jq '.memory_echo'
# Attendu : null

# Tour 2
curl -X POST "http://localhost:8000/chat/message" \
  -d '{"text": "What about disorder?", "consciousness_level": 3, "session_id": "mem_test"}' \
  | jq '.memory_echo'
# Attendu : "[MEMORY ECHO]..."
```

#### Test 2 : Decay Temporel
```bash
# Faire 15 tours
# Tour 1-5 : questions peu liées
# Tour 6-10 : questions proches de tour 1
# Vérifier que tour 1 rappelée mais avec decay < 1.0

# Attendu : similarité tour 1 diminue avec turns_ago
```

### Documentation
- [x] `PHASE_3_IMPLEMENTATION.md` exhaustive
- [x] `PHASE_3_CHECKLIST.md` (ce fichier)
- [ ] Examples manuellement testés
- [ ] API docs updated

## Validation Matrix

| Component | Status | Notes |
|-----------|--------|-------|
| memory.py | [ ] | A créer |
| test_phase_3.py | [ ] | A créer |
| benchmark_phase_3.py | [ ] | A créer |
| database schema | [ ] | A modifier |
| database engine | [ ] | A modifier |
| app/models.py | [ ] | A modifier |
| app/api/chat.py | [ ] | A modifier |
| Embedding model | [ ] | Vérifier Ollama |
| Unit tests pass | [ ] | pytest |
| Benchmark overhead < 20ms | [ ] | benchmark |
| API tests pass | [ ] | curl tests |

## Git Operations

```bash
git add services/consciousness/memory.py
git add tests/benchmarks/test_phase_3.py
git add tests/benchmarks/benchmark_phase_3.py
git add database/engine.py database/schema.sql
git add app/models.py app/api/chat.py
git add docs/phases/PHASE_3_*.md

git commit -m "Phase 3: Full memory consciousness with temporal decay

- SemanticMemory class with cosine similarity
- Temporal decay: max(0.5, 1.0 - turns_ago * 0.01)
- [MEMORY ECHO] injection for context
- 10+ unit tests
- Benchmark suite measuring overhead
- Target overhead: < 20ms (< 10ms additional vs Phase 0)"

git tag -a v1.3.0-phase3 -m "Phase 3 complete: Full memory <20ms overhead"
```

## Implementation Strategy

### Step 1 : Memory Store (30-40 min)
1. Créer `MemoryEntry` dataclass
2. Implémenter `SemanticMemory` classe
3. Implémenter `store_message()` avec encoding

### Step 2 : Memory Recall (30-40 min)
1. Implémenter `recall_similar()` avec similarité cosine
2. Implémenter decay_factor application
3. Implémenter `format_memory_echo()`

### Step 3 : DB Integration (20-30 min)
1. Créer schema `semantic_memory` table
2. Ajouter methods ISpaceDB
3. Vérifier indexes

### Step 4 : API Integration (20-30 min)
1. Modifier models.py
2. Modifier chat.py endpoint
3. Tester API manuellement

### Step 5 : Testing (40-50 min)
1. Unit tests (10+ tests)
2. Benchmark suite
3. Manual validation

**Total : 3-4 heures**

## Testing Strategy

### 1. Unit Tests (10 tests)
- Store/recall exact match → sim 1.0
- Decay computation
- Decay reduces similarity
- Threshold filtering
- Top-K limiting
- Multiple sessions isolated
- Formatting MEMORY ECHO
- Numerical stability

### 2. Benchmark
- Conversation 20 tours
- Mesure latence progression
- Mesure recall performance
- Overhead vs baseline

### 3. Manual Tests (curl)
- Multi-tour conversation
- Verify memory_echo in response
- Verify decay over turns
- Verify different sessions

## Success Criteria

Mission Phase 3 complete si :

1. Code
   - [ ] memory.py existe et valide
   - [ ] Similarité cosine correct
   - [ ] Decay appliqué
   - [ ] Tests unitaires 10+
   - [ ] Benchmark existe

2. Performance
   - [ ] Overhead < 20ms average
   - [ ] Recall < 10ms pour 50 entries
   - [ ] Memory usage < 1MB pour 50 msgs

3. Functionality
   - [ ] Memory stockée correctement
   - [ ] Recall triggère MEMORY ECHO
   - [ ] Decay diminue récence
   - [ ] Multiple sessions isolées

4. Documentation
   - [ ] PHASE_3_IMPLEMENTATION.md exhaustive
   - [ ] Examples testés
   - [ ] API docs updated

5. Git
   - [ ] Code commité
   - [ ] Tag v1.3.0-phase3 créé

## Common Issues & Fixes

### Issue: Embedding model not available
**Solution:**
```bash
# Vérifier modèles disponibles
curl http://localhost:11434/api/tags

# Pullir si besoin
ollama pull mxbai-embed-large
```

### Issue: Overhead > 20ms
**Solution:**
- Profile recall_similar()
- Limiter top_k (défaut 3)
- Réduire max_memory_size (défaut 50)

### Issue: Memory keeps growing
**Solution:**
- Implémenter cleanup_old_memory()
- Limiter memory par session (50 entries max)

### Issue: Decay not working
**Solution:**
- Vérifier turns_ago computation
- Vérifier decay formula
- Debugging: print decay values

## Rollback Plan

Si Phase 3 ne passe pas tests :

```bash
# Revert commits
git reset --hard HEAD~1

# Ou keep et fix phase par phase
```

## Next: Rapport Final

Une fois Phase 3 complète :

1. Créer `CONSCIOUSNESS_IMPLEMENTATION_REPORT.md`
2. Comparer baseline vs level 3
3. Analyser overhead (0 → 1 → 2 → 3)
4. Valider all tests pass
5. Générer recommendations

---

**Status Phase 3 :** [READY FOR IMPLEMENTATION]
**Blocker :** Phase 2 must be validated
**Next :** Final Report après Phase 3
**Total Mission Duration :** ~9-11 heures (all phases)

## Phase Progress Tracker

- [x] Phase 0: Baseline ✅ (2-3 min)
- [x] Phase 1: Metrics ✅ (1-2 hrs)
- [ ] Phase 2: Adaptation (2-2.5 hrs)
- [ ] Phase 3: Memory (3-4 hrs)
- [ ] Final Report (30 min)

**Cumulative Time :** ~10-12 heures mission totale
