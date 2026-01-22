# Phase 0 : Baseline Etablie

**Date :** 26 novembre 2025
**Version Lyra :** 1.0.0
**Consciousness Level :** 0 (aucune conscience)

## Objectif

Etablir les benchmarks de reference pour mesurer l'impact de chaque niveau de conscience.

Cette phase ne modifie AUCUN code Lyra - elle mesure simplement le comportement de base.

## Benchmarks Executes

### Benchmark 1 : Latence de Base (50 requetes)

Mesure la latence totale et son breakdown pour des appels simples avec contexte.

**Metriques collectees :**
- `total_latency_ms` : Latence complete de bout en bout
- `context_latency_ms` : Temps extraction contexte du graphe
- `llm_latency_ms` : Temps generation reponse par Ollama
- `api_overhead_ms` : Frais API/serialization

**Prompts utilis :** "What is entropy?"

**Interpretation :**
- La latence moyenne etabilt un baseline contre lequel mesurer l'overhead des niveaux 1-3
- Context_latency donne une indication de la performance du graphe
- API_overhead permet de valider que modifications futures ne degradent pas performance reseau

### Benchmark 2 : Impact Injection Contexte (5 prompts)

Compare requetes avec et sans contexte inject.

**Metriques collectees :**
- `latency_without_ms` : Temps sans extraction contexte
- `latency_with_ms` : Temps avec extraction + injection
- `overhead_ms` : Difference brute
- `overhead_percent` : Difference relative
- `concepts_injected` : Nombre de concepts inseres dans prompt
- `response_length_*` : Evolution longueur reponse

**Prompts :**
1. "What is entropy?"
2. "Explain quantum mechanics"
3. "How does photosynthesis work?"
4. "What is machine learning?"
5. "Describe the water cycle"

**Interpretation :**
- Overhead_percent donne une indication de cout relatif du contexte
- Concepts_injected montre la densité du graphe par domaine
- Response_length compare impact contexte sur produits generes

### Benchmark 3 : Comparaison Profils (5 profils x 3 prompts = 15 tests)

Compare comportement des 5 profils Bezier existants.

**Profils testes :**
- balanced : Tau_c ~ 1.0, rho ~ 0.0 (neutre)
- creative : Tau_c ~ 0.5, rho ~ 0.5 (exploration creative)
- safe : Tau_c ~ 1.5, rho ~ -0.2 (prudent, concis)
- analytical : Tau_c ~ 1.2, rho ~ 0.3 (detaille)
- concise : Tau_c ~ 1.0, rho ~ -0.5 (tres court)

**Metriques collectees :**
- `latency_ms` : Latence par profil
- `response_length` : Longueur moyenne reponse
- `tau_c` : Parametre contrainte chaude
- `rho` : Parametre directionalite
- `delta_r` : Decalage derivation

**Prompts :**
1. "Explain entropy"
2. "What is consciousness?"
3. "Describe evolution"

**Interpretation :**
- Differentes latences entre profils indiquent variabilite Ollama
- Longueur reponse confirme que profils affectent output
- Physics_state permet validation que parametres sont correctement appliques

## Resultats Attendus

Les resultats seront sauvegardes sous forme de CSV dans `benchmark_results/` :

```
benchmark_results/
├── baseline_latency_YYYYMMDD_HHMMSS.csv
├── baseline_latency_YYYYMMDD_HHMMSS_config.json
├── baseline_context_YYYYMMDD_HHMMSS.csv
├── baseline_context_YYYYMMDD_HHMMSS_config.json
├── baseline_profiles_YYYYMMDD_HHMMSS.csv
└── baseline_profiles_YYYYMMDD_HHMMSS_config.json
```

## Metriques Cibles

### Latence Baseline
- **Esperee :** ~1200-1300 ms (principalement LLM)
- **Variance acceptable :** +/- 10%
- **Context extraction :** < 15 ms
- **API overhead :** < 20 ms

### Context Injection Overhead
- **Esperee :** +5-15 ms (+0.4-1.2%)
- **Interprettion :** Cout negligeable, extraction rapide

### Variabilite entre Profils
- **Esperee :** +/- 5% autour baseline
- **Interpretation :** Profils modifient output pas latence significativement

## Validation Checklist

- [x] Structure dossiers cree
- [x] `benchmark_suite.py` implemente
- [x] Serveur demarr et healthy
- [x] Benchmark baseline lance
- [ ] 3 fichiers CSV generes
- [ ] Documentation baseline completee
- [ ] Resultats valides et coherents
- [ ] Commit effectue

## Interpretation des Resultats

Une fois benchmarks termines, les fichiers CSV permettront de :

1. **Valider performance baseline**
   - Confirmer que Ollama + API fournissent latence stable
   - Identifier anomalies (spikes, timeouts)

2. **Etablir references**
   - Latence moyenne servira de comparaison pour phases 1-3
   - Overhead contexte servira de baseline pour phase 1+

3. **Detecter instabilites**
   - Variance elevee dans overhead suggere problemes reseau/serveur
   - Differentes latences entre profils suggerent variabilite Ollama

4. **Documenter caracteristiques**
   - Nombre moyen concepts injectes per domain
   - Longueur moyenne reponse par profil

## Notes de Implementation

### Mecanisme Sauvegarde
- CSV : Une ligne par requete avec toutes metriques
- JSON config : Parametres du benchmark (n_requests, prompts, etc.)
- Timestamp : Chaque execution genere fichiers dateS (archive automatique)

### Gestion Erreurs
- Exceptions reseau captureés et enregistrees
- Erreurs individuelles ne bloquent pas suite complete
- Sessions timeout parametrees a 60s

### Performance de Benchmark
- 50 requetes latence x 1300ms ~ 65s + overhead
- 5 requetes x 2 conditions (with/without) ~ 30s
- 15 requetes profils ~ 20s
- **Total estime : 2-3 minutes** + overhead LLM

Temps total reel : ~20-25 minutes (Ollama peut etre lent)

## Prochaines Etapes

Apres validation resultats baseline :
1. Passer a Phase 1 : Metriques Passives
2. Comparer overhead phase 1 vs baseline
3. Valider que conscience_level=0 donne memes resultats baseline

---

**Statut :** [EN ATTENTE DE RESULTATS]
**Commit :** A faire une fois Phase 0 validee
**Tag :** v1.0.0-baseline (apres validation)
