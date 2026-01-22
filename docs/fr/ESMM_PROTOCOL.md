# Protocole ESMM - Exploration Semantique Multi-Modeles

## Vue d'ensemble

Le protocole ESMM orchestre plusieurs modeles LLM pour construire collaborativement un graphe de connaissances semantiques.

### Objectifs
- Explorer des domaines conceptuels de maniere systematique
- Construire un consensus inter-modeles
- Identifier et combler les lacunes de connaissances
- Produire une 0-Cochaine de concepts valides

---

## Architecture

### Modeles et Personas

Chaque modele LLM joue un role specifique:

| Modele | Persona | Role |
|--------|---------|------|
| DeepSeek-R1 | Analytique | Raisonnement structure, decomposition |
| Llama 3.3 | Generaliste | Connaissances larges, synthese |
| Gemma 3 | Creatif | Associations originales, exploration |
| Mistral | Critique | Validation, contre-arguments |

### Types de Cycles

#### 1. Cycle Divergent
- **Objectif**: Explorer largement autour d'un concept seed
- **Question type**: "Quels concepts sont lies a {concept}?"
- **Resultat**: Liste de triplets (sujet, relation, objet)

#### 2. Cycle Debat
- **Objectif**: Valider/invalider des relations proposees
- **Question type**: "La relation '{A} {rel} {B}' est-elle valide?"
- **Resultat**: Score de consensus par relation

#### 3. Cycle Meta
- **Objectif**: Identifier les lacunes et planifier l'exploration
- **Question type**: "Quels concepts manquent dans ce domaine?"
- **Resultat**: Liste de knowledge gaps prioritises

---

## 0-Cochaine de Consensus

### Definition

La 0-Cochaine C est une fonction qui assigne a chaque concept un score de consensus:

```
C: Concepts -> [0, 1]
```

### Formule

```
C(concept) = w1 * model_agreement
           + w2 * semantic_consistency
           + w3 * structural_centrality
           + w4 * stability_score
```

Ou:
- `model_agreement`: Proportion de modeles ayant mentionne le concept
- `semantic_consistency`: Coherence des embeddings
- `structural_centrality`: Centralite dans le graphe (PageRank-like)
- `stability_score`: Stabilite temporelle (variance des mentions)

### Types Epistemiques

Chaque concept est classifie:

| Type | Criteres |
|------|----------|
| **Generalist** | Mentionne par tous les modeles, haute centralite |
| **Specialized** | Mentionne par 1-2 modeles, basse centralite |
| **Hybrid** | Mentionne par plusieurs modeles mais avec desaccords |

---

## Gestion VRAM (ModelRotator)

Le `ModelRotator` gere la rotation sequentielle des modeles pour eviter la saturation VRAM:

```python
from services.esmm import ModelRotator, get_model_rotator

rotator = await get_model_rotator()

# Rotation automatique: charge -> genere -> decharge -> suivant
result = await rotator.rotate_and_process(
    models=["llama3.1:8b", "mistral", "gemma3"],
    question="Quels concepts sont lies a entropie?",
    temperature=0.7
)

for model, response in result.responses.items():
    print(f"{model}: {len(response.text)} chars, {response.latency_ms}ms")
```

### Strategie VRAM

1. **Chargement sequentiel**: Un seul modele en VRAM a la fois
2. **keep_alive=0**: Decharge immediatement apres generation
3. **Preload optionnel**: `await rotator.preload_model("llama3.1:8b")`
4. **Batch processing**: Garder un modele pour plusieurs questions

---

## Extraction de Triplets

### Pipeline

```
Reponse LLM -> Parsing JSON -> Validation Pydantic -> Canonicalisation -> Injection
```

### Prompts Few-Shot

Le fichier `services/esmm/prompts.py` fournit des templates avec exemples positifs et negatifs:

```python
from services.esmm import get_triplet_extraction_prompt, CANONICAL_RELATIONS

prompt = get_triplet_extraction_prompt("L'entropie augmente dans un systeme isole")
# Inclut exemples valides ET invalides pour guider le LLM
```

**20 relations canoniques:**

| Categorie | Relations |
|-----------|-----------|
| Causal | `cause`, `caused_by` |
| Hierarchique | `is_a`, `part_of`, `has_part` |
| Associatif | `related_to`, `similar_to`, `opposite_of` |
| Epistemique | `implies`, `contradicts`, `supports`, `requires` |
| Temporel | `precedes`, `follows` |
| Production | `produces`, `consumes`, `enables`, `prevents` |

### Validation Stricte (Pydantic)

Le `TripletValidator` applique une validation rigoureuse:

```python
from services.esmm import TripletValidator, extract_and_validate

# Methode complete
validator = TripletValidator(min_confidence=0.5)
triplets, results = validator.validate_llm_output(llm_response)

# Ou raccourci
triplets = extract_and_validate(llm_response, min_confidence=0.5)
```

**Regles de validation:**

- Sujet/objet: 2-100 caracteres
- Pas de pronoms (il, elle, ca, this, that)
- Pas de termes generiques (chose, truc, something)
- Relation: doit etre canonique (normalisee automatiquement)
- Confiance: 0.0-1.0, minimum 0.3 accepte
- Sujet != Objet

### Canonicalisation

1. **Entites**: Resolues via `EntityResolver`
   - Similarite cosinus > 0.92 -> Fusion automatique
   - Similarite > 0.85 -> Candidat a revue

2. **Relations**: Normalisees via `normalize_relation()`
   - Mapping automatique: "causes" -> "cause", "mene_a" -> "cause"
   - Fallback vers "related_to" si non reconnu

### Injection Finale

Un triplet est injecte si:

- Validation Pydantic reussie
- Confiance >= seuil (default 0.5)
- Sujet et objet existent (ou auto-crees)
- Pas de doublon exact

---

## Workflow d'un Run ESMM

```
1. Initialisation
   - Creer esmm_run
   - Charger seed concepts
   - Configurer modeles

2. Exploration (N iterations)
   Pour chaque type de cycle:
     - Generer question
     - Collecter reponses des modeles
     - Extraire triplets
     - Calculer consensus
     - Injecter dans le graphe

3. Analyse des lacunes
   - Detecter concepts isoles
   - Identifier relations instables
   - Trouver ponts manquants

4. Finalisation
   - Calculer 0-Cochaine
   - Classifier types epistemiques
   - Generer metriques

5. Export
   - Statistiques du run
   - Graphe enrichi
   - Cochaine pour visualisation
```

---

## Tables de Donnees

### esmm_runs
Stocke la configuration et les statistiques de chaque run.

### exploration_cycles
Historique detaille de chaque cycle avec:
- Question posee
- Reponses des modeles
- Triplets extraits
- Metriques de consensus

### triplet_extractions
Chaque triplet extrait avec:
- Formes brutes et canoniques
- Confiance et methode d'extraction
- Statut d'injection

### cochain_entries
La 0-Cochaine calculee:
- Score de consensus
- Composantes du score
- Signature 5D pour visualisation
- Type epistemique

### knowledge_gaps
Lacunes identifiees:
- `isolated`: Concept avec peu de connexions
- `unstable`: Relation avec kappa faible
- `bridge`: Pont manquant entre clusters

---

## Metriques d'Evaluation

| Metrique | Description |
|----------|-------------|
| `coverage_score` | Proportion de l'espace semantique couvert |
| `consensus_density` | Moyenne des scores de consensus |
| `epistemic_diversity` | Entropie des types epistemiques |
| `structural_stability` | Kappa moyen du graphe |

---

## Utilisation

### Demarrer un run

```python
from database import get_db

db = await get_db()

# Creer le run
run_id = await db.create_esmm_run(
    config={"cycles_per_type": 5, "models": ["deepseek", "llama"]},
    models=["deepseek-r1", "llama3.3"],
    seed_type="standard"
)

# Mettre a jour le statut
await db.update_esmm_run_status(run_id, "running", "divergent", 1)
```

### Enregistrer un cycle

```python
cycle_id = await db.log_exploration_cycle(
    run_id=run_id,
    cycle_type="divergent",
    iteration=1,
    question_template="Quels concepts sont lies a {concept}?",
    question_rendered="Quels concepts sont lies a entropie?",
    responses={"deepseek": "...", "llama": "..."}
)
```

### Stocker un triplet

```python
extraction_id = await db.store_triplet_extraction(
    subject="entropie",
    relation="related_to",
    object_="information",
    confidence=0.85,
    extraction_method="llm_structured",
    model_source="deepseek-r1",
    cycle_id=cycle_id
)
```

### Mettre a jour la cochaine

```python
await db.upsert_cochain_entry(
    concept_id="entropie",
    consensus_score=0.87,
    model_agreement=0.9,
    semantic_consistency=0.85,
    structural_centrality=0.82,
    stability_score=0.91,
    signature_vector=[0.87, 0.9, 0.85, 0.82, 0.91],
    epistemic_type="generalist",
    contributing_models={"deepseek-r1": 0.4, "llama3.3": 0.35},
    triplet_count=15,
    run_id=run_id
)
```
