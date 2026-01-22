# Phase 0 : Checklist

## Preparation

- [x] Structure dossiers creee
  - [x] `tests/benchmarks/`
  - [x] `services/consciousness/`
  - [x] `docs/phases/`
  - [x] `benchmark_results/`

- [x] Fichiers vides crees
  - [x] `tests/__init__.py`
  - [x] `tests/benchmarks/__init__.py`
  - [x] `services/consciousness/__init__.py`

## Implementation Benchmarking

- [x] `benchmark_suite.py` code complet
- [x] Classe `LyraBenchmark` implementee
- [x] 3 benchmarks definis :
  - [x] `benchmark_latency_basic()` - 50 requetes
  - [x] `benchmark_context_impact()` - 5 prompts
  - [x] `benchmark_profiles()` - 5 profils x 3 prompts

- [x] Methodes utilitaires
  - [x] `check_server_health()`
  - [x] `save_results()` - CSV + JSON config
  - [x] `run_baseline_suite()` - orchestration completes

## Execution

- [x] Serveur FastAPI demarr et operationnel
- [ ] Benchmark suite lancee
- [ ] 3 fichiers CSV generes
  - [ ] `baseline_latency_*.csv` (50 lignes)
  - [ ] `baseline_context_*.csv` (5 lignes)
  - [ ] `baseline_profiles_*.csv` (15 lignes)

## Documentation

- [x] `PHASE_0_BASELINE.md` detailed
  - [x] Objectifs decrits
  - [x] 3 benchmarks expliques
  - [x] Metriques collectees detaillees
  - [x] Interpretation des resultats
  - [x] Checklist de validation

- [x] `PHASE_0_CHECKLIST.md` (ce fichier)

## Validation Resultats

Une fois CSV generes :

- [ ] Ouvrir `benchmark_results/baseline_latency_*.csv`
  - [ ] Verifier que `total_latency_ms` ~ 1200-1300 ms
  - [ ] Verifier que `context_latency_ms` < 15 ms
  - [ ] Verifier que `api_overhead_ms` < 20 ms
  - [ ] Verifier pas de valeurs NaN/Inf
  - [ ] Verifier variance < 10% (std/mean)

- [ ] Ouvrir `benchmark_results/baseline_context_*.csv`
  - [ ] Verifier que overhead_ms ~ 5-15 ms
  - [ ] Verifier que concepts_injected varie (7, 8, 9...)
  - [ ] Verifier que response_length_with > response_length_without

- [ ] Ouvrir `benchmark_results/baseline_profiles_*.csv`
  - [ ] Verifier que tous 5 profils presents
  - [ ] Verifier latency ~1200-1300 ms pour tous
  - [ ] Verifier que tau_c/rho correspondent au profil attendu

## Git Commit

- [ ] Tous fichiers crees ajouts a git
```bash
git add tests/
git add services/consciousness/
git add docs/phases/
git add tests/benchmarks/
git commit -m "Phase 0: Baseline benchmarks infrastructure"
```

## Tag Version

- [ ] Une fois resultats valides :
```bash
git tag -a v1.0.0-baseline -m "Baseline established, 3 benchmarks executed"
```

## Commandes de Validation Rapide

Verifier structure :
```bash
ls tests/benchmarks/
ls services/consciousness/
ls docs/phases/
```

Lancer benchmarks :
```bash
cd /path/to/lyra_clean
python -m pytest tests/benchmarks/ -v
python tests/benchmarks/benchmark_suite.py
```

Verifier resultats :
```bash
ls -lh benchmark_results/
head -5 benchmark_results/baseline_latency_*.csv
```

Analyse rapide latence :
```bash
cat benchmark_results/baseline_latency_*.csv | awk -F',' 'NR>1 {sum+=$2; count++} END {print "Avg latency:", sum/count " ms"}'
```

## Notes Importantes

1. **Durée execution :** ~20-25 minutes esperees
   - 50 requetes x 1300ms = 65s
   - Plus overhead reseau/python/serialization
   - Ollama peut etre impredictible

2. **Ne rien modifier du code existant** pendant Phase 0
   - Objectif : mesurer baseline, pas ameliorer

3. **Sauvegarder les resultats** quelque part (screenshots/archive)
   - Seront references pour phases 1-3

4. **En cas d'erreur**
   - Verifier que serveur est toujours healthy
   - Lancer benchmark a nouveau (peut etre timeout temporaire)
   - Checker logs Ollama si timeouts frequents

## Resultat Attendu Apres Phase 0

```
benchmark_results/
├── baseline_latency_20250126_143022.csv        (50 rows)
├── baseline_latency_20250126_143022_config.json
├── baseline_context_20250126_143145.csv        (5 rows)
├── baseline_context_20250126_143145_config.json
├── baseline_profiles_20250126_143312.csv       (15 rows)
└── baseline_profiles_20250126_143312_config.json

docs/phases/
├── PHASE_0_BASELINE.md
└── PHASE_0_CHECKLIST.md

tests/benchmarks/
├── benchmark_suite.py
└── __init__.py
```

---

**Status Phase 0 :** [EN COURS]
**Deadline :** Aucune (tant que termine avant Phase 1)
**Blocker :** Aucun prevu
