# Phase 2 : Checklist

## Implementation

### Code Creation
- [ ] `services/consciousness/adaptation.py` (220 lignes)
  - [ ] `AdaptiveConsciousness` classe (hérite ConsciousnessMonitor)
  - [ ] `suggest_adjustments()` - 5 règles adaptation
  - [ ] `apply_adjustments()` - multiplicateurs → params

- [ ] `tests/benchmarks/test_phase_2.py` (250+ lignes)
  - [ ] 20+ tests unitaires
  - [ ] Tester chaque règle
  - [ ] Tester bornes
  - [ ] Tester sérialisation

- [ ] `tests/benchmarks/benchmark_phase_2.py` (180 lignes)
  - [ ] `benchmark_adaptive_conversation()` - 30 tours
  - [ ] Comparaison level 1 vs 2
  - [ ] Mesure latence, stabilité, adjustments

### DB Changes
- [ ] Modifier `database/schema.sql`
  - [ ] Créer table `session_adjustments`
  - [ ] Créer index sur session_id + timestamp

- [ ] Modifier `database/engine.py` (ISpaceDB)
  - [ ] `store_session_adjustments()` méthode
  - [ ] `get_session_adjustments()` méthode

### API Changes
- [ ] Modifier `app/models.py`
  - [ ] Ajouter `profile_adjustments` field à ChatResponse

- [ ] Modifier `app/api/chat.py`
  - [ ] Import `AdaptiveConsciousness`
  - [ ] Initialiser monitor level >= 2
  - [ ] Appeler `suggest_adjustments()` si level >= 2
  - [ ] Stocker adjustments en BD
  - [ ] Inclure dans response

### Unit Tests
```bash
pytest tests/benchmarks/test_phase_2.py -v
```
Attendu :
- [x] 20+ tests découverts
- [ ] 20+ tests passent
- [ ] Duration < 5s

### Benchmark Execution

```bash
python tests/benchmarks/benchmark_phase_2.py
```
Attendu :
- [ ] 30 tours simulés
- [ ] Level 1 : latency moyenne X ms
- [ ] Level 2 : latency moyenne X+overhead ms
- [ ] Overhead < 5ms < target 10ms
- [ ] Adjustments triggérés 8-12 fois

### Manual API Testing

#### Test 1 : consciousness_level=2
```bash
curl -X POST "http://localhost:8000/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What is entropy?",
    "consciousness_level": 2,
    "session_id": "manual_test"
  }' | jq '.profile_adjustments'
```
Attendu : object or null (probabiliste)

#### Test 2 : Historique Adjustments
```bash
# Faire 10 requêtes avec même session_id
# Puis vérifier DB
# SELECT COUNT(*) FROM session_adjustments WHERE session_id = 'manual_test'
```
Attendu : 0-10 rows (les tours avec adjustments)

### Documentation
- [x] `PHASE_2_IMPLEMENTATION.md` exhaustive
- [x] `PHASE_2_CHECKLIST.md` (ce fichier)
- [ ] Examples manuellement testés
- [ ] API docs updated

## Validation Matrix

| Component | Status | Notes |
|-----------|--------|-------|
| adaptation.py | [ ] | A créer |
| test_phase_2.py | [ ] | A créer |
| benchmark_phase_2.py | [ ] | A créer |
| database schema | [ ] | A modifier |
| database engine | [ ] | A modifier |
| app/models.py | [ ] | A modifier |
| app/api/chat.py | [ ] | A modifier |
| Unit tests pass | [ ] | pytest |
| Benchmark overhead < 10ms | [ ] | benchmark |
| API tests pass | [ ] | curl tests |

## Git Operations

```bash
git add services/consciousness/adaptation.py
git add tests/benchmarks/test_phase_2.py
git add tests/benchmarks/benchmark_phase_2.py
git add database/engine.py database/schema.sql
git add app/models.py app/api/chat.py
git add docs/phases/PHASE_2_*.md

git commit -m "Phase 2: Adaptive consciousness with profile adjustment

- AdaptiveConsciousness class with 5 adaptation rules
- Gradual 5% adjustments per interaction
- Session persistence of adjustments
- 20+ unit tests
- Benchmark suite measuring overhead
- Target overhead: < 10ms (< 5ms additional vs Phase 1)"

git tag -a v1.2.0-phase2 -m "Phase 2 complete: Adaptive profiles <10ms overhead"
```

## Testing Strategy

### 1. Unit Tests (15-20 tests)
- Chaque règle d'adaptation individuellement
- Bornes respectées
- JSON sérialisation
- Edge cases

### 2. Integration Tests
- API accepte consciousness_level=2
- Response inclut profile_adjustments
- DB stocke ajustements

### 3. Benchmark (30 tours)
- Mesure overhead
- Vérifie stabilité profil
- Compare vs level 1

### 4. Manual Tests (curl)
- Tester direct API
- Tester historique DB
- Tester avec différents profils

## Success Criteria

Mission Phase 2 complete si :

1. Code
   - [ ] adaptation.py existe et valide
   - [ ] 5 règles implémentées correctement
   - [ ] Tests unitaires 20+
   - [ ] Benchmark existe

2. Performance
   - [ ] Overhead < 10ms average
   - [ ] Pas de regression phase 1
   - [ ] Adjustments triggérés logiquement

3. Data Persistence
   - [ ] Adjustments stockés en BD
   - [ ] Historique récupérable
   - [ ] Index optimisés

4. Documentation
   - [ ] PHASE_2_IMPLEMENTATION.md exhaustive
   - [ ] Examples testés
   - [ ] API docs updated

5. Git
   - [ ] Code commité
   - [ ] Tag v1.2.0-phase2 créé

## Timeline Estimate

- Implementation adapter : 30-40 min
- Tests unitaires : 30-40 min
- Benchmark : 15-20 min
- Manual testing : 15-20 min
- Documentation review : 10-15 min
- **Total : 2-2.5 heures**

## Common Issues & Fixes

### Issue: Overhead > 10ms
**Solution :** 
- Profile suggest_adjustments()
- Vérifier que apply_adjustments() est O(1)
- Cache résultats si besoin

### Issue: Adjustments too aggressive
**Solution :**
- Réduire adaptation_rate (défaut 5% → 3%)
- Augmenter seuils (tension 0.75 → 0.8)

### Issue: DB constrains violation
**Solution :**
- Vérifier foreign keys sessions/adjustments
- Vérifier timestamps uniques

## Rollback Plan

Si Phase 2 ne passe pas tests :

```bash
# Revert commits
git reset --hard HEAD~1

# Ou keep et fix
# Recommencer tests jusqu'à pass
```

---

**Status Phase 2 :** [READY FOR IMPLEMENTATION]
**Blocker :** Phase 1 must be validated
**Next :** Phase 3 après Phase 2 complète
