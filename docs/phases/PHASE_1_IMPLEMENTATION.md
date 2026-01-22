# Phase 1 : Metriques Passives (Conscience Niveau 1)

**Date :** 26 novembre 2025
**Version Lyra :** 1.1.0
**Consciousness Level :** 1 (passif)

## Objectif

Implémenter le calcul de métriques épistémiques **sans modifier le comportement du système**. 

Le niveau 1 doit :
- Calculer 4 métriques (coherence, tension, fit, pressure)
- Ajouter les résultats à la réponse API
- Rester transparent (pas d'adaptation, juste mesure)
- Overhead < 5ms

## Implémentation

### Fichiers Créés

#### `services/consciousness/metrics.py` (185 lignes)

Module core pour calcul de métriques épistémiques.

**Classe `ConsciousnessMetrics` :**
- Dataclass stockant les 4 métriques
- Propriété `stability_score` : score composite
- Méthode `dict()` : sérialisation JSON (arrondi 3 décimales)

**Classe `ConsciousnessMonitor` :**
- Moniteur principal (support niveaux 0-3)
- Initialisation avec `level` (0=off, 1=passive, 2=adaptive, 3=full)
- Méthode `compute_metrics()` :
  - Arguments : context_weight, num_concepts, physics_state, response_length
  - Retour : ConsciousnessMetrics si level >= 1, sinon None
  - Overhead cible : < 5ms

**Méthodes Privées de Calcul :**

1. `_compute_coherence(weight, n_concepts)` 
   - Formule : `min(1.0, weight / (n_concepts * 0.8))`
   - Rationale : poids moyen de 0.8 par concept = bonne cohérence
   - Saturé à 1.0

2. `_compute_pressure(tau_c, delta_r)`
   - Formule : `0.3 * |delta_r| + 0.7 * (tau_c / (tau_c + 1.0))`
   - Mesure : charge exploration/exploitation
   - delta_r élevé → exploration temporelle
   - tau_c élevé → contrainte forte

3. `_compute_fit(rho, response_length)`
   - Mesure : alignement production vs attentes
   - Rho > 0 : attendu expansif (200-300 mots)
   - Rho < 0 : attendu concis (100-150 mots)
   - Formule : `1.0 - |actual - expected| / expected`
   - Saturé à [0, 1]

4. `_compute_tension(coherence, pressure)`
   - Formule : `0.4 * (1 - coherence) + 0.6 * pressure`
   - Stress système = structure faible OU charge forte
   - Poids : 60% pressure, 40% coherence

### Fichiers Modifiés

#### `app/models.py`

**Nouvelle classe ChatRequest :**
```python
class ChatRequest(BaseModel):
    text: str
    session_id: Optional[str] = None
    profile: str = "balanced"
    enable_context: bool = True
    max_history: int = 20
    consciousness_level: int = 0  # NEW: 0=off, 1=passive, 2=adaptive, 3=full
    
    @validator('consciousness_level')
    def validate_consciousness_level(cls, v):
        if v not in [0, 1, 2, 3]:
            raise ValueError("consciousness_level must be 0, 1, 2, or 3")
        return v
```

**Nouvelle classe ChatResponse :**
```python
class ChatResponse(BaseModel):
    text: str
    session_id: str
    physics_state: dict
    context: Optional[dict] = None
    latency: dict
    tokens: Optional[dict] = None
    consciousness: Optional[dict] = None  # NEW: metriques si level >= 1
```

#### `app/api/chat.py`

**Modifications dans endpoint `/message` :**

1. Importer `ConsciousnessMonitor` de `services.consciousness.metrics`
2. Initialiser monitor basé sur `request.consciousness_level`
3. Après génération réponse :
   - Si level >= 1 : appeler `consciousness_monitor.compute_metrics()`
   - Passer dans ConsciousnessMetrics dans réponse JSON
4. Les modifications se font APRÈS génération réponse (pas d'impact latence génération)

### Tests Unitaires

**Fichier :** `tests/benchmarks/test_phase_1.py` (200+ lignes)

**Classes de Test :**

`TestConsciousnessMetrics` :
- `test_monitor_level_0_returns_none()` : level 0 → None
- `test_monitor_level_1_returns_metrics()` : level 1 → ConsciousnessMetrics
- `test_high_coherence_scenario()` : contexte fort → coherence > 0.7
- `test_low_coherence_scenario()` : contexte faible → coherence < 0.3
- `test_high_pressure_scenario()` : tau_c/delta_r élevés → pressure > 0.7
- `test_low_pressure_scenario()` : tau_c/delta_r bas → pressure < 0.4
- `test_high_tension_scenario()` : coherence basse + pressure haute → tension > 0.6
- `test_good_fit_with_positive_rho()` : rho positif + réponse longue → fit > 0.7
- `test_good_fit_with_negative_rho()` : rho négatif + réponse courte → fit > 0.7
- `test_metrics_dict_serialization()` : dict() produit JSON valide
- `test_zero_concepts_edge_case()` : zéro concept → coherence = 0
- `test_empty_response_edge_case()` : réponse vide valide
- `test_stability_score_calculation()` : formula exacte vérifiée
- `test_metrics_normalization_bounds()` : tous métriques dans [0,1]

**Exécution :**
```bash
pytest tests/benchmarks/test_phase_1.py -v
# Attendu : 13+ tests passent, duration < 5s
```

### Benchmark

**Fichier :** `tests/benchmarks/benchmark_phase_1.py` (130 lignes)

**Fonction `benchmark_consciousness_overhead()` :**
- Compare 5 prompts différents
- Pour chaque prompt :
  - Level 0 : API call sans conscience
  - Level 1 : API call avec consciousness_level=1
- Mesure overhead en ms et %
- Target : < 5ms average

**Résultats sauvegardés :**
- CSV : `phase1_consciousness_overhead_YYYYMMDD_HHMMSS.csv`
- JSON config : `phase1_consciousness_overhead_YYYYMMDD_HHMMSS_config.json`

**Exécution :**
```bash
python tests/benchmarks/benchmark_phase_1.py
# Attendu : overhead_ms.mean() < 5.0
# Durée : ~30 secondes (5 prompts x ~6s chacun)
```

## Métriques Épistémiques

### 1. Coherence (0-1) : Densité Sémantique

**Formule :** `min(1.0, avg_weight / 0.8)`

**Composants :**
- `context_weight` : Somme poids de tous concepts injectés
- `num_concepts` : Nombre concepts
- `avg_weight` : Poids moyen = context_weight / num_concepts

**Interprétation :**
- **> 0.7** : Contexte fort, concepts bien connectés (graphe dense)
- **0.4-0.7** : Contexte moyen, structure stable
- **< 0.4** : Contexte faible, concepts épars (graphe fragmenté)

**Cas Extrêmes :**
- Zéro concepts → 0.0
- Poids parfait (0.8/concept) → 1.0
- Poids très élevé (> 0.8/concept) → saturé à 1.0

### 2. Tension (0-1) : Stress Système

**Formule :** `0.4 * (1 - coherence) + 0.6 * pressure`

**Signification :**
- Mesure stress/instabilité du système
- 60% basé sur pressure (charge exploration/exploitation)
- 40% basé sur manque coherence (structure faible)

**Interprétation :**
- **> 0.8** : Haute tension → risque instabilité
- **0.5-0.8** : Tension modérée → fonctionnement normal
- **< 0.5** : Basse tension → système stable/relaxe

### 3. Fit (0-1) : Alignement Production vs Attentes

**Calcul :**
```
expected_length = {
  rho > 0  → 200 + rho * 100  (expansif)
  rho < 0  → 150 + rho * 50   (concis)
  rho = 0  → 150             (neutre)
}
deviation = |response_length - expected_length| / expected_length
fit = 1.0 - min(1.0, deviation)
```

**Interprétation :**
- **> 0.8** : Excellent fit → output correspond aux attentes
- **0.5-0.8** : Bon fit → alignement acceptable
- **< 0.5** : Mauvais fit → output dépasse/trop court

### 4. Pressure (0-1) : Charge Exploration/Exploitation

**Formule :** `0.3 * |delta_r| + 0.7 * (tau_c / (tau_c + 1.0))`

**Composants :**
- `delta_r` : Décalage dérivation (exploration temporelle)
- `tau_c` : Paramètre contrainte chaude (rigidité du profil)

**Interprétation :**
- **> 0.8** : Haute charge → système sous pression
- **0.4-0.7** : Pression modérée → équilibre normal
- **< 0.4** : Basse pression → système relaxe

### 5. Stability Score (composite)

**Formule :** `(coherence + fit) / 2 - tension * 0.5`

**Rationale :**
- Score composé :
  - Moyenne coherence + fit (facteurs positifs)
  - Moins tension pondérée (facteur négatif)
- Range : [-0.5, 1.0]

**Interprétation :**
- **> 0.7** : Très stable
- **0.3-0.7** : Stable
- **< 0.3** : Instabilité potentielle

## API Changes

### Request
```json
{
  "text": "What is entropy?",
  "consciousness_level": 1
}
```

### Response (nouveau champ)
```json
{
  "text": "...",
  "consciousness": {
    "coherence": 0.78,
    "tension": 0.42,
    "fit": 0.85,
    "pressure": 0.51,
    "stability_score": 0.60
  }
}
```

## Exemples d'Utilisation

### cURL Level 0 (baseline)
```bash
curl -X POST "http://localhost:8000/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Explain entropy",
    "consciousness_level": 0
  }'
# Réponse : pas de champ "consciousness"
```

### cURL Level 1 (metrics)
```bash
curl -X POST "http://localhost:8000/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Explain entropy",
    "consciousness_level": 1
  }' | jq '.consciousness'
# Output :
# {
#   "coherence": 0.78,
#   "tension": 0.42,
#   "fit": 0.85,
#   "pressure": 0.51,
#   "stability_score": 0.60
# }
```

### Python
```python
import httpx

with httpx.Client() as client:
    response = client.post(
        "http://localhost:8000/chat/message",
        json={
            "text": "What is consciousness?",
            "consciousness_level": 1
        }
    )
    data = response.json()
    
    if data.get("consciousness"):
        print(f"Coherence: {data['consciousness']['coherence']}")
        print(f"Tension: {data['consciousness']['tension']}")
        print(f"Stability: {data['consciousness']['stability_score']}")
```

## Performance Expectations

### Overhead Latence Phase 1

**Target :** < 5ms average

**Composition :**
- Calcul 4 métriques : ~1-2ms
- Sérialisation JSON : ~0.5-1ms
- Total : ~2-3ms (< 5ms target)

**Validation :**
- Exécuter `benchmark_phase_1.py`
- Vérifier `overhead_ms.mean() < 5.0`
- Si > 5ms → profiler et optimiser

### Scalabilité

Métriques calculées en O(1) :
- Aucune boucle
- Aucune requête DB
- Juste arithmétique

Donc overhead reste constant peu importe :
- Longueur response
- Nombre concepts
- Taille graphe

## Integration Checklist

### Code Implementation
- [x] `metrics.py` complet avec ConsciousnessMonitor
- [x] Tests unitaires complets (13+ tests)
- [ ] Modifier `app/models.py` ajouter champs
- [ ] Modifier `app/api/chat.py` intégrer calcul
- [ ] Tests unitaires passent
- [ ] Benchmark crée et fonctionnel

### API Validation
- [ ] Endpoint `/chat/message` accepte `consciousness_level`
- [ ] Réponse contient `consciousness` field si level >= 1
- [ ] Réponse ne contient PAS `consciousness` si level = 0
- [ ] Validation : consciousness_level doit être 0-3

### Manual Testing
```bash
# Test level 0 : pas de metriques
curl -X POST "http://localhost:8000/chat/message" \
  -d '{"text": "test", "consciousness_level": 0}' | jq 'has("consciousness")'
# Attendu : false

# Test level 1 : metriques present
curl -X POST "http://localhost:8000/chat/message" \
  -d '{"text": "test", "consciousness_level": 1}' | jq '.consciousness'
# Attendu : object avec coherence, tension, fit, pressure, stability_score
```

### Documentation
- [x] `PHASE_1_IMPLEMENTATION.md` (ce fichier)
- [x] `PHASE_1_CHECKLIST.md`
- [ ] Exemples testés et validés
- [ ] API docs générées (`/docs`)

## Benchmarks Results Format

### CSV Columns (benchmark_phase_1.py output)

```
prompt,level_0_latency_ms,level_1_latency_ms,overhead_ms,overhead_percent,coherence,tension,fit,pressure
"What is entropy?",1245.32,1248.15,2.83,0.23,0.78,0.42,0.85,0.51
"Explain quantum mechanics",1312.45,1316.23,3.78,0.29,0.82,0.38,0.82,0.48
...
```

### Expected Output
```
SUMMARY:
Requests completed: 5/5
Average overhead: 3.21ms (0.26%)
Max overhead: 4.12ms
Std dev: 0.89ms

Target: < 5ms
RESULT: PASS - Overhead acceptable [avg=3.21ms]
```

## Transition vers Phase 2

Une fois Phase 1 validée :
- [ ] Tous tests passent
- [ ] Overhead < 5ms confirmé
- [ ] API compatible (level 0 inchangé)
- [ ] Documentation complète

Alors passer à Phase 2 : Adaptation Douce

---

**Status Phase 1 :** [EN ATTENTE IMPLEMENTATION]
**Prerequis :** Phase 0 baseline etablie
**Blockers :** Aucun
