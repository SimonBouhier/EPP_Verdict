# Phase 2 : Adaptation Douce (Conscience Niveau 2)

**Date :** 26 novembre 2025  
**Version Lyra :** 1.2.0  
**Consciousness Level :** 2 (adaptatif)

## Objectif

Implémenter **adaptation progressive et graduelle** des profils Bezier basée sur métriques épistémiques.

Le niveau 2 doit :
- Observer métriques Phase 1 (coherence, tension, fit, pressure)
- Suggérer ajustements graduels (5% par interaction)
- Persister histoire d'ajustements en session
- Adapter paramètres Bezier (tau_c, rho, delta_r)
- Overhead < 10ms
- Retourner `profile_adjustments` dans response

## Architecture Phase 2

### Adapter Pattern

**Concept :** Ajuster profils en réaction à métriques sans rupture brusque.

```
Métriques Phase 1
     ↓
AdaptiveConsciousness
     ↓
Suggérer ajustements (5% graduel)
     ↓
Stocker en BD
     ↓
Appliquer au prochain tour
```

### Règles d'Adaptation

Les 5 règles implémentées dans `AdaptiveConsciousness.suggest_adjustments()` :

#### Règle 1 : Tension Haute (> 0.75) → Réduire Tau_c
**Rationale :** Haute tension indique rigidité excessive. Réduire tau_c abaisse la contrainte.
```
Si tension > 0.75:
    tau_c_multiplier = 1.0 - adaptation_rate (défaut 5%)
    Raison : "High tension - reducing tau_c"
```

#### Règle 2 : Coherence Basse (< 0.3) → Ajuster Rho
**Rationale :** Contexte fragmenté, augmenter focus (rho) pour concentration.
```
Si coherence < 0.3:
    Si rho > 0 : rho_shift = -adaptation_rate (concentrer)
    Si rho < 0 : rho_shift = +adaptation_rate (moins concis)
    Raison : "Low coherence - adjusting focus"
```

#### Règle 3 : Bon Fit + Stabilité (fit > 0.8 ET stability > 0.7) → Encourager Exploration
**Rationale :** Système stable et en accord, augmenter delta_r pour exploration.
```
Si fit > 0.8 ET stability > 0.7:
    delta_r_multiplier = 1.0 + adaptation_rate * 0.5 (prudent)
    Raison : "High fit & stability - encouraging exploration"
```

#### Règle 4 : Pression Très Haute (> 0.85) → Réduire Charge
**Rationale :** Pressure extrême = surcharge. Réduire tau_c et delta_r.
```
Si pressure > 0.85:
    tau_c_multiplier = 1.0 - adaptation_rate * 1.5 (double réduction)
    delta_r_multiplier = 1.0 - adaptation_rate
    Raison : "Very high pressure - reducing load"
```

#### Règle 5 : Session Longue + Tension Stable → No-op
**Rationale :** Après 30 messages, si tension stable (0.4-0.6), système équilibré. Ne pas perturber.
```
Si message_count > 30 ET 0.4 < tension < 0.6:
    return None  # Aucun ajustement
```

### Format Réponse `profile_adjustments`

```json
{
  "tau_c_multiplier": 0.95,
  "reason": "High tension (0.82) - reducing tau_c; Very high pressure (0.87) - reducing load",
  "triggered_by": {
    "coherence": 0.45,
    "tension": 0.82,
    "fit": 0.72,
    "pressure": 0.87
  }
}
```

Ou si multiples règles déclenchées :
```json
{
  "tau_c_multiplier": 0.925,
  "delta_r_multiplier": 0.95,
  "rho_shift": -0.05,
  "reason": "High tension...; Low coherence...; Very high pressure...",
  "triggered_by": {...}
}
```

## Implémentation

### Fichiers Créés

#### `services/consciousness/adaptation.py` (220 lignes)

**Classe `AdaptiveConsciousness(ConsciousnessMonitor)` :**

Hérite de `ConsciousnessMonitor`, ajoute adaptation.

```python
class AdaptiveConsciousness(ConsciousnessMonitor):
    def __init__(self, level: int = 2, adaptation_rate: float = 0.05):
        super().__init__(level)
        self.adaptation_rate = adaptation_rate  # Défaut 5% par interaction
    
    def suggest_adjustments(
        self,
        metrics: ConsciousnessMetrics,
        current_profile: dict,
        session_length: int
    ) -> Optional[Dict[str, float]]:
        """Suggère ajustements basés sur métriques + historique"""
    
    def apply_adjustments(
        self,
        current_params: dict,
        adjustments: dict
    ) -> dict:
        """Applique multiplicateurs aux paramètres"""
```

**Méthode `suggest_adjustments()` :**
- Retour None si level < 2
- Applique 5 règles
- Retour dict avec multiplicateurs + raison

**Méthode `apply_adjustments()` :**
- Applique multiplicateurs aux paramètres
- Respecte bornes : tau_c [0.5, 2.0], rho [-1, 1], delta_r [-1, 1]
- Retourne params modifiés

### Modifications Fichiers Existants

#### `database/engine.py` (ISpaceDB)

**Ajouts :**

```python
async def store_session_adjustments(
    self,
    session_id: str,
    adjustments: dict,
    metrics: dict
):
    """Stocke ajustements + métriques pour une session"""

async def get_session_adjustments(
    self,
    session_id: str,
    limit: int = 10
) -> list:
    """Récupère historique ajustements"""
```

#### `database/schema.sql`

**Nouvelle table :**

```sql
CREATE TABLE session_adjustments (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    adjustments TEXT NOT NULL,  -- JSON
    metrics TEXT NOT NULL,      -- JSON
    timestamp REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX idx_adjustments_session 
ON session_adjustments(session_id, timestamp DESC);
```

#### `app/models.py`

**Nouveau champ ChatResponse :**
```python
profile_adjustments: Optional[dict] = Field(
    None,
    description="Suggested profile adjustments if consciousness_level >= 2"
)
```

#### `app/api/chat.py`

**Modifications endpoint `/message` :**

```python
# Après calcul metrics Phase 1
profile_adjustments = None
if request.consciousness_level >= 2 and consciousness_metrics:
    # Charger AdaptiveConsciousness au lieu ConsciousnessMonitor
    # Appeler suggest_adjustments()
    # Stocker en BD
```

### Tests Unitaires

**Fichier :** `tests/benchmarks/test_phase_2.py` (250+ lignes)

**Classes :**

`TestAdaptiveConsciousness` :
- Tester calcul suggestions (suggest_adjustments)
- Tester application paramètres (apply_adjustments)
- Tester chaque règle d'adaptation individuellement
- Tester interactions multiples règles
- Tester bornes paramètres
- Tester sérialisation JSON

Exemples de tests :
- `test_high_tension_reduces_tau_c()` : Vérifier que tension > 0.75 → tau_c *= 0.95
- `test_low_coherence_adjusts_rho()` : coherence < 0.3 → rho modifié
- `test_no_adjustment_long_session_stable()` : > 30 messages + tension modérée → None
- `test_multiple_rules_trigger()` : Vérifier combinaisons règles
- `test_bounds_enforcement()` : tau_c reste [0.5, 2.0]
- `test_adjustments_serialization()` : dict() produit JSON valide

### Benchmark

**Fichier :** `tests/benchmarks/benchmark_phase_2.py` (180 lignes)

**Fonction `benchmark_adaptive_conversation()` :**
- Conversation longue : 30 messages
- Prompts variés (simples → complexes)
- Test 1 : Profil statique (level 1)
- Test 2 : Profil adaptatif (level 2)
- Mesure :
  - Latence par tour
  - Evolution tension
  - Nombre adjustments triggérés
  - Comparaison stabilité

**Format CSV :**
```
turn,level,prompt,latency_ms,coherence,tension,fit,stability,adjustments
0,1,"Hello",8234.5,0.0,0.61,0.0,-0.305,None
0,2,"Hello",8245.3,0.0,0.61,0.0,-0.305,"tau_c_mult:0.95"
...
```

**Résultats attendus :**
- Overhead level 2 vs 1 : < 5ms (total < 10ms)
- Tension plus stable sur 30 tours avec level 2
- 8-12 ajustements sur 30 tours

## Performance

### Overhead Latence Phase 2

**Target :** < 10ms average (< 5ms additionnel vs Phase 1)

**Composition :**
- Appel `suggest_adjustments()` : ~1-2ms
- Application paramètres : ~0.5-1ms
- Stockage BD : ~1-2ms
- Total : ~3-5ms supplémentaire

### Scalabilité

Méthodes O(1) sauf :
- Stockage BD : O(1) avec index
- Historique chargé pour session_length : O(1) accès

Donc overhead reste constant peu importe conversation longue.

## API Changes

### Request (inchangé)
```json
{
  "text": "What is entropy?",
  "consciousness_level": 2
}
```

### Response (nouveau champ)
```json
{
  "text": "...",
  "consciousness": {...},
  "profile_adjustments": {
    "tau_c_multiplier": 0.95,
    "reason": "High tension - reducing tau_c",
    "triggered_by": {...}
  }
}
```

## Exemples d'Usage

### Conversation Adaptive

```python
# Tour 1
response_1 = client.post("/chat/message", 
    json={"text": "Hello", "consciousness_level": 2})
adj_1 = response_1["profile_adjustments"]  # Peut être None

# Tour 2-30 (profil adapté graduellement)
for i in range(2, 31):
    response = client.post("/chat/message",
        json={"text": f"Question {i}", "consciousness_level": 2})
    if response["profile_adjustments"]:
        print(f"  Adjusted: {response['profile_adjustments']['reason']}")
```

### Recuperer Historique Adjustments

```python
# DB query
adjustments = db.get_session_adjustments(session_id, limit=20)
# [
#   {"adjustments": {...}, "metrics": {...}, "timestamp": 1234567890},
#   ...
# ]
```

## Validation Checklist

### Code
- [ ] `adaptation.py` complet
- [ ] Tests unitaires (20+ tests)
- [ ] Benchmark créé
- [ ] DB schema modifié
- [ ] Models.py modifié
- [ ] API endpoint modifié

### API
- [ ] consciousness_level=2 crée adjustments
- [ ] adjustments respectent bornes
- [ ] historique stocké correctement
- [ ] performance < 10ms

### Manual Testing
```bash
# Tour 1
curl -X POST "http://localhost:8000/chat/message" \
  -d '{"text": "Hello", "consciousness_level": 2, "session_id": "test1"}' \
  | jq '.profile_adjustments'
# Attendu : null (probabiliste) ou object

# Tour 2 (même session)
curl -X POST "http://localhost:8000/chat/message" \
  -d '{"text": "More", "consciousness_level": 2, "session_id": "test1"}' \
  | jq '.profile_adjustments'
# Attendu : adjustments si tension/coherence déclenchent
```

## Transition vers Phase 3

Après Phase 2 validée :
- Overhead < 10ms confirmé
- Profils s'adaptent graduellement
- Historique persisté
- Tests passent

Alors : Phase 3 - Mémoire Sophistiquée

---

**Status Phase 2 :** [EN ATTENTE IMPLEMENTATION]
**Prerequis :** Phase 1 validée
**Target Overhead :** < 10ms vs level 0
**Est. Durée :** 2-3h implementation + test + benchmark
