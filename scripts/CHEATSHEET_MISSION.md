# ⚡ CHEAT SHEET - Mission Conscience Modulaire

## 🎯 Quick Reference

### Documents
1. **INSTRUCTIONS_HAIKU_CONSCIOUSNESS.md** (45 pages) → Mission complète
2. **GUIDE_TRANSMISSION_HAIKU.md** (10 pages) → Comment transmettre
3. **Ce fichier** → Commandes rapides

---

## 📋 Phases & Checkpoints

```
PHASE 0: Baseline        [1h]   → Benchmarks référence
PHASE 1: Métriques       [1-2h] → Overhead < 5ms
PHASE 2: Adaptation      [1-2h] → Overhead < 10ms
PHASE 3: Mémoire         [1-2h] → Overhead < 20ms
VALIDATION: Rapport      [30m]  → Analyse complète
```

---

## 🚀 Commandes Essentielles

### Démarrer serveur
```bash
cd lyra_clean
python app/main.py
```

### Vérifier santé
```bash
curl http://localhost:8000/health | jq '.status'
```

### Tests unitaires
```bash
# Phase N
pytest tests/benchmarks/test_phase_N.py -v
```

### Benchmark phase
```bash
# Phase N
python tests/benchmarks/benchmark_phase_N.py
```

### Résultats
```bash
# Voir CSV générés
ls -lh benchmark_results/

# Lire derniers résultats
tail -20 benchmark_results/phase1_*.csv
```

### Git
```bash
# Commit phase
git add .
git commit -m "Phase N: [description]"
git tag v1.N.0-phaseN
```

---

## ✅ Validation Rapide (à chaque phase)

```bash
# 1. Tests passent ?
pytest tests/benchmarks/test_phase_N.py -v
# Attendu : X/X passed

# 2. Benchmark OK ?
python tests/benchmarks/benchmark_phase_N.py
# Attendu : overhead < target

# 3. API fonctionne ?
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"text":"Test","consciousness_level":N}' | jq '.consciousness'
# Attendu : métriques affichées

# 4. Documentation créée ?
ls docs/phases/PHASE_N_*.md
# Attendu : 2 fichiers (IMPLEMENTATION + CHECKLIST)

# 5. Commit fait ?
git log --oneline | head -1
# Attendu : "Phase N: ..."
```

---

## 🎯 Targets de Performance

| Phase | Niveau | Overhead Max | Métriques |
|-------|--------|--------------|-----------|
| 0 | - | - | Baseline |
| 1 | Passive | < 5ms | coherence, tension, fit, pressure |
| 2 | Adaptive | < 10ms | + profile_adjustments |
| 3 | Full | < 20ms | + memory_echo |

---

## 🚨 Signaux d'Alerte

### ❌ Tests échouent
```bash
# Debug
pytest tests/benchmarks/test_phase_N.py -v -s

# Si imports fail
export PYTHONPATH=/path/to/lyra_clean:$PYTHONPATH
```

### ❌ Overhead trop élevé
```bash
# Profiler
python -m cProfile -s cumtime tests/benchmarks/benchmark_phase_N.py

# Optimiser fonction lente
```

### ❌ API casse
```bash
# Rollback
git reset --hard HEAD^

# Redémarrer serveur
pkill -f "python app/main.py"
python app/main.py
```

---

## 📊 Prompt de Suivi (copier-coller)

**À envoyer à Haiku régulièrement :**

```
Status report :

Phase : [0/1/2/3] ?
Progression : [%] ?
Tests : [X]/[X] passent ?
Benchmark : [X]ms < [Y]ms ?
Blocages : [oui/non] ?

Prochaine étape : ?
```

---

## 🎓 Commandes par Phase

### Phase 0 (Baseline)
```bash
# Créer structure
mkdir -p tests/benchmarks services/consciousness docs/phases

# Lancer baseline
python tests/benchmarks/benchmark_suite.py

# Vérifier résultats
ls benchmark_results/baseline_*.csv
```

### Phase 1 (Métriques)
```bash
# Tests
pytest tests/benchmarks/test_phase_1.py -v

# Benchmark
python tests/benchmarks/benchmark_phase_1.py

# Test manuel
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"text":"Test","consciousness_level":1}' | jq '.consciousness'
```

### Phase 2 (Adaptation)
```bash
# Tests
pytest tests/benchmarks/test_phase_2.py -v

# Benchmark (30 turns)
python tests/benchmarks/benchmark_phase_2.py

# Vérifier ajustements
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"text":"Test","session_id":"test","consciousness_level":2}' | \
  jq '.profile_adjustments'
```

### Phase 3 (Mémoire)
```bash
# Tests
pytest tests/benchmarks/test_phase_3.py -v

# Benchmark
python tests/benchmarks/benchmark_phase_3.py

# Test mémoire (multi-turn)
for i in {1..5}; do
  curl -X POST http://localhost:8000/chat/message \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"Message $i\",\"session_id\":\"mem_test\",\"consciousness_level\":3}"
  sleep 1
done
```

---

## 📈 Analyse Rapide Résultats

```bash
# Statistiques latence
cat benchmark_results/phase1_*.csv | \
  awk -F',' 'NR>1 {sum+=$4; count++} END {print "Avg:", sum/count "ms"}'

# Comparer phases
echo "Phase 0 baseline:"
cat benchmark_results/baseline_latency_*.csv | \
  awk -F',' 'NR>1 {sum+=$2} END {print sum/NR "ms"}'

echo "Phase 1 overhead:"
cat benchmark_results/phase1_*.csv | \
  awk -F',' 'NR>1 {sum+=$4} END {print sum/NR "ms"}'
```

---

## 🔍 Debug Commandes

```bash
# Logs serveur
tail -f lyra_clean.log

# Processus Python
ps aux | grep python

# Port 8000 occupé ?
lsof -i :8000
# Tuer si nécessaire :
kill -9 $(lsof -t -i :8000)

# Base de données lockée ?
ls data/ispace.db-wal data/ispace.db-shm
# Supprimer si bloqué :
rm data/ispace.db-wal data/ispace.db-shm
```

---

## 📦 Livrables Attendus

```
lyra_clean/
├── services/consciousness/
│   ├── __init__.py
│   ├── metrics.py           # Phase 1
│   ├── adaptation.py        # Phase 2
│   └── memory.py            # Phase 3
│
├── tests/benchmarks/
│   ├── benchmark_suite.py   # Phase 0
│   ├── test_phase_1.py
│   ├── benchmark_phase_1.py
│   ├── test_phase_2.py
│   ├── benchmark_phase_2.py
│   ├── test_phase_3.py
│   └── benchmark_phase_3.py
│
├── docs/phases/
│   ├── PHASE_0_BASELINE.md
│   ├── PHASE_0_CHECKLIST.md
│   ├── PHASE_1_IMPLEMENTATION.md
│   ├── PHASE_1_CHECKLIST.md
│   ├── PHASE_2_IMPLEMENTATION.md
│   ├── PHASE_2_CHECKLIST.md
│   ├── PHASE_3_IMPLEMENTATION.md
│   ├── PHASE_3_CHECKLIST.md
│   └── CONSCIOUSNESS_IMPLEMENTATION_REPORT.md
│
└── benchmark_results/
    ├── baseline_*.csv
    ├── phase1_*.csv
    ├── phase2_*.csv
    └── phase3_*.csv
```

---

## ⏱️ Timeline Idéal

```
Heure 0:00  → Start Phase 0
Heure 1:00  → Phase 0 validée ✅
Heure 1:15  → Start Phase 1
Heure 3:00  → Phase 1 validée ✅
Heure 3:15  → Start Phase 2
Heure 5:00  → Phase 2 validée ✅
Heure 5:15  → Start Phase 3
Heure 7:00  → Phase 3 validée ✅
Heure 7:15  → Rapport final
Heure 7:45  → Mission complete 🎉
```

---

## 🎯 Critère de Réussite

```python
def mission_success():
    return (
        all_tests_pass() and
        overhead_level_1 < 5 and
        overhead_level_2 < 10 and
        overhead_level_3 < 20 and
        documentation_complete() and
        api_compatible() and
        commits_clean()
    )
```

---

## 📞 Contact

Si Haiku bloque :
1. Décrire problème précisément
2. Partager logs/erreurs
3. Attendre guidance
4. Ne PAS continuer sans déblocage

---

**Version :** 1.0  
**Mise à jour :** 2025-01-16  
**Durée mission :** 4-8 heures
