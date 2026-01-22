# 🗺️ LYRA-ACE : Roadmap Architecturale ESMM
## Exploration Sémantique Multi-Modèles

**Version** : 1.0  
**Date** : 2026-01-21  
**Statut** : Architecture de référence

---

## 📋 Table des matières

1. [Vision globale](#1-vision-globale)
2. [Architecture cible](#2-architecture-cible)
3. [Phase 1 : Fondations](#3-phase-1--fondations)
4. [Phase 2 : Extracteur de triplets](#4-phase-2--extracteur-de-triplets)
5. [Phase 3 : Protocole ESMM complet](#5-phase-3--protocole-esmm-complet)
6. [Schémas de données](#6-schémas-de-données)
7. [APIs nécessaires](#7-apis-nécessaires)
8. [Métriques et validation](#8-métriques-et-validation)
9. [Dépendances et risques](#9-dépendances-et-risques)
10. [Calendrier estimé](#10-calendrier-estimé)

---

## 1. Vision globale

### 1.1 Métaphore neurologique

Le système ESMM s'inspire d'une architecture cognitive fractale :

```
                    ┌─────────────────────────────────────────┐
                    │         SPHÈRE CENTRALE                 │
                    │     (Global Workspace / Graphe G)       │
                    │                                         │
                    │   ┌─────────────────────────────┐       │
                    │   │  Concepts + Relations       │       │
                    │   │  κ (courbure) + ρ (densité) │       │
                    │   │  0-cochaîne de consensus    │       │
                    │   └─────────────────────────────┘       │
                    └───────────────┬─────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
            ▼                       ▼                       ▼
    ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
    │   FAISCEAU 1  │       │   FAISCEAU 2  │       │   FAISCEAU N  │
    │   (LLM #1)    │       │   (LLM #2)    │       │   (LLM #N)    │
    │               │       │               │       │               │
    │  ┌─────────┐  │       │  ┌─────────┐  │       │  ┌─────────┐  │
    │  │  ROUE   │  │       │  │  ROUE   │  │       │  │  ROUE   │  │
    │  │ persona │  │       │  │ persona │  │       │  │ persona │  │
    │  │ cycles  │  │       │  │ cycles  │  │       │  │ cycles  │  │
    │  └─────────┘  │       │  └─────────┘  │       │  └─────────┘  │
    └───────┬───────┘       └───────┬───────┘       └───────┬───────┘
            │                       │                       │
            └───────────────────────┼───────────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────────────────┐
                    │         CONSENSUS & ACTIVATION          │
                    │                                         │
                    │   sim(combinaison, attracteur) > θ      │
                    │   → Injection dans le graphe            │
                    │   → Mise à jour de la 0-cochaîne        │
                    └─────────────────────────────────────────┘
```

### 1.2 Équation fondamentale

```
Activation(faisceau_i) = Σⱼ softmax(Q_i · K_j / √d) · V_j

Conscience_émergente = max_i(Activation_i) > seuil_κ

Où :
  - Q = requête (question d'exploration)
  - K = concepts du graphe (embeddings 1024D)
  - V = valeurs sémantiques (poids PPMI + κ)
  - seuil_κ = threshold de consensus (0.8 par défaut)
```

### 1.3 Objectifs du protocole ESMM

| Objectif | Description | Métrique cible |
|----------|-------------|----------------|
| **Cartographie** | Couvrir un espace de connaissances | > 60% de couverture |
| **Consensus** | Extraire une 0-cochaîne pondérée | Score moyen > 0.7 |
| **Cristallisation** | Graphe généraliste + spécialisé | Entropie type > 1.5 |
| **Stabilité** | Relations durables et cohérentes | κ moyen > 0.1 |

---

## 2. Architecture cible

### 2.1 Composants principaux

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           LYRA-ACE ESMM                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    COUCHE ORCHESTRATION                         │    │
│  │                                                                 │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │    │
│  │  │ Question    │  │ Cycle       │  │ Gap                     │  │    │
│  │  │ Generator   │  │ Controller  │  │ Detector                │  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                    │
│                                    ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    COUCHE MULTI-MODÈLES                         │    │
│  │                                                                 │    │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐                 │    │
│  │  │deepseek│  │ llama  │  │mistral │  │ gemma  │   (extensible)  │    │
│  │  │ r1     │  │ 3.1/3.3│  │        │  │   3    │                 │    │
│  │  │        │  │        │  │        │  │        │                 │    │
│  │  │rigorous│  │creative│  │practical│ │skeptic │  ← personas     │    │
│  │  └────────┘  └────────┘  └────────┘  └────────┘                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                    │
│                                    ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    COUCHE EXTRACTION                            │    │
│  │                                                                 │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │    │
│  │  │ Triplet     │  │ Consensus   │  │ Embedding               │  │    │
│  │  │ Extractor   │  │ Calculator  │  │ Generator               │  │    │
│  │  │ (S, R, O)   │  │ (4-model)   │  │ (mxbai 1024D)           │  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                    │
│                                    ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    COUCHE PERSISTANCE                           │    │
│  │                                                                 │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │    │
│  │  │ ISpaceDB    │  │ Graph       │  │ 0-Cochain               │  │    │
│  │  │ (concepts,  │  │ Deltas      │  │ Store                   │  │    │
│  │  │  relations) │  │ (history)   │  │ (consensus scores)      │  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Flux de données

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Question   │─────▶│  4 Modèles   │─────▶│  4 Réponses  │
│  (template)  │      │  (parallel)  │      │  (diverse)   │
└──────────────┘      └──────────────┘      └──────────────┘
                                                   │
                                                   ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Graphe     │◀─────│  Consensus   │◀─────│  Triplets    │
│   enrichi    │      │  pondéré     │      │  (S, R, O)   │
└──────────────┘      └──────────────┘      └──────────────┘
       │
       ▼
┌──────────────┐      ┌──────────────┐
│  0-Cochaîne  │─────▶│  Stable      │
│  mise à jour │      │  Truths      │
└──────────────┘      └──────────────┘
```

---

## 3. Phase 1 : Fondations

### 3.1 Objectif

Créer un graphe sémantique fonctionnel à partir de zéro, peuplé avec les concepts de base et les relations initiales.

### 3.2 Livrables

| Livrable | Description | Critère de succès |
|----------|-------------|-------------------|
| **L1.1** | Script de population initiale | ~600 concepts chargés |
| **L1.2** | Génération de relations | ~2000 relations basiques |
| **L1.3** | Validation du graphe | κ calculable pour toutes les arêtes |
| **L1.4** | Tests d'intégration | API `/graph/delta` fonctionnelle |

### 3.3 Sous-tâches détaillées

#### 3.3.1 Population des concepts (L1.1)

**Entrée** : `topics.txt` (fichier existant avec ~600 concepts)

**Sortie** : Table `concepts` peuplée

```python
# Pseudo-code du script de population
async def populate_concepts_from_topics():
    """
    Charge topics.txt et crée les entrées concepts.
    """
    topics = load_topics_file("topics.txt")
    
    for topic in topics:
        # Nettoyer le texte
        clean_topic = normalize_concept_name(topic)
        
        # Générer embedding 1024D via Ollama
        embedding = await get_embeddings(clean_topic)
        
        # Insérer dans la base
        await db.execute("""
            INSERT OR IGNORE INTO concepts 
            (id, rho_static, degree, embedding, created_at)
            VALUES (?, 0.0, 0, ?, ?)
        """, (clean_topic, serialize_embedding(embedding), time.time()))
    
    return len(topics)
```

**Schéma de données** :

```sql
-- Concepts (existant, enrichir embedding)
ALTER TABLE concepts ADD COLUMN embedding_model TEXT DEFAULT 'mxbai-embed-large';

-- Si embedding n'existe pas encore
UPDATE concepts SET embedding = NULL WHERE embedding IS NULL;
```

#### 3.3.2 Génération des relations initiales (L1.2)

**Stratégie** : Utiliser la similarité cosinus entre embeddings pour créer des relations de base.

```python
async def generate_initial_relations(similarity_threshold=0.6):
    """
    Crée des relations basées sur la similarité d'embeddings.
    """
    concepts = await db.get_all_concepts_with_embeddings()
    
    relations_created = 0
    
    for i, c1 in enumerate(concepts):
        for c2 in concepts[i+1:]:
            # Calculer similarité cosinus
            similarity = cosine_similarity(c1.embedding, c2.embedding)
            
            if similarity >= similarity_threshold:
                # Créer relation bidirectionnelle
                await db.apply_delta(GraphDelta(
                    operation=DeltaOperation.ADD_EDGE,
                    source=c1.id,
                    target=c2.id,
                    weight=similarity,
                    confidence=0.7,  # Confiance modérée (auto-généré)
                    model_source="embedding_similarity"
                ))
                relations_created += 1
    
    return relations_created
```

**Optimisation** : Utiliser un index vectoriel (FAISS ou Annoy) pour éviter O(n²).

#### 3.3.3 Graine sémantique ESMM (L1.3)

**Injecter les oppositions dialectiques fondamentales** :

```python
SEED_GRAPH = {
    "concepts_fondamentaux": [
        ("cause", "effet"),
        ("principe", "application"),
        ("théorie", "pratique"),
        ("abstrait", "concret"),
        ("simple", "complexe"),
        ("local", "global")
    ],
    "domaines_tension": [
        ("quantique", "classique"),
        ("déterministe", "probabiliste"),
        ("continu", "discret"),
        ("objectif", "subjectif"),
        ("empirique", "théorique")
    ]
}

async def inject_seed_graph():
    """Injecte les paires dialectiques fondamentales."""
    for domain, pairs in SEED_GRAPH.items():
        relation_type = "oppose" if domain == "domaines_tension" else "complète"
        
        for concept1, concept2 in pairs:
            # S'assurer que les concepts existent
            await ensure_concept_exists(concept1)
            await ensure_concept_exists(concept2)
            
            # Créer la relation avec haute confiance (seed)
            await db.apply_delta(GraphDelta(
                operation=DeltaOperation.ADD_EDGE,
                source=concept1,
                target=concept2,
                weight=0.9,
                confidence=0.95,
                model_source="seed",
                reason=f"Graine ESMM: {relation_type}"
            ))
```

### 3.4 Critères de validation Phase 1

| Critère | Seuil | Méthode de vérification |
|---------|-------|-------------------------|
| Concepts chargés | ≥ 500 | `SELECT COUNT(*) FROM concepts` |
| Relations créées | ≥ 1000 | `SELECT COUNT(*) FROM relations` |
| Embeddings valides | 100% | Vérifier dimension = 1024 |
| κ calculable | 100% | Tester `compute_kappa_live` sur 10 arêtes |
| API Delta | OK | Test POST `/graph/delta` |

---

## 4. Phase 2 : Extracteur de triplets

### 4.1 Objectif

Permettre au système d'apprendre des conversations en extrayant automatiquement des triplets (Sujet, Relation, Objet) des réponses LLM.

### 4.2 Livrables

| Livrable | Description | Critère de succès |
|----------|-------------|-------------------|
| **L2.1** | Module `TripletExtractor` | Précision > 70% sur dataset test |
| **L2.2** | Intégration dans `/chat/message` | Extraction automatique activable |
| **L2.3** | API `/triplets/extract` | Endpoint standalone |
| **L2.4** | Tests unitaires | Couverture > 80% |

### 4.3 Architecture du TripletExtractor

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TripletExtractor                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐  │
│  │   Text Input    │─────▶│   LLM-based     │─────▶│   Validation    │  │
│  │                 │      │   Extraction    │      │   & Scoring     │  │
│  │  "L'entropie    │      │                 │      │                 │  │
│  │   augmente avec │      │  structured     │      │  confidence,    │  │
│  │   le désordre"  │      │  prompting      │      │  deduplication  │  │
│  └─────────────────┘      └─────────────────┘      └─────────────────┘  │
│                                                            │            │
│                                                            ▼            │
│                                               ┌─────────────────────┐   │
│                                               │  List[Triplet]      │   │
│                                               │                     │   │
│                                               │  ("entropie",       │   │
│                                               │   "augmente_avec",  │   │
│                                               │   "désordre")       │   │
│                                               │                     │   │
│                                               │  confidence: 0.85   │   │
│                                               └─────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Implémentation détaillée

#### 4.4.1 Structure de données

```python
@dataclass
class Triplet:
    """Représente un triplet sémantique extrait."""
    subject: str           # Concept source
    relation: str          # Type de relation
    object: str            # Concept cible
    confidence: float      # Score de confiance [0, 1]
    source_text: str       # Texte d'origine
    extraction_method: str # "llm_structured" | "pattern" | "dependency"
    model_source: str      # Modèle ayant généré le texte d'origine

@dataclass
class ExtractionResult:
    """Résultat complet d'une extraction."""
    triplets: List[Triplet]
    raw_text: str
    extraction_time_ms: float
    model_used: str
    prompt_tokens: int
    completion_tokens: int
```

#### 4.4.2 Module TripletExtractor

```python
class TripletExtractor:
    """
    Extrait des triplets (S, R, O) depuis du texte en langage naturel.
    
    Stratégies d'extraction:
    1. LLM-based: Prompting structuré avec format JSON forcé
    2. Pattern-based: Regex pour structures simples (fallback)
    3. Dependency-based: Analyse syntaxique (optionnel, spaCy)
    """
    
    # Relations canoniques (normalisation)
    CANONICAL_RELATIONS = {
        # Causalité
        "cause": ["provoque", "engendre", "entraîne", "résulte_en"],
        "caused_by": ["causé_par", "dû_à", "résulte_de"],
        
        # Hiérarchie
        "is_a": ["est_un", "est_une", "type_de", "sorte_de"],
        "part_of": ["fait_partie_de", "composant_de", "élément_de"],
        "has_part": ["contient", "comprend", "inclut"],
        
        # Association
        "related_to": ["lié_à", "associé_à", "connecté_à"],
        "similar_to": ["similaire_à", "comparable_à", "analogue_à"],
        "opposite_of": ["opposé_à", "contraire_de", "antithèse_de"],
        
        # Propriété
        "has_property": ["possède", "caractérisé_par", "présente"],
        "used_for": ["utilisé_pour", "sert_à", "permet_de"],
        
        # Temporalité
        "precedes": ["précède", "avant", "antérieur_à"],
        "follows": ["suit", "après", "postérieur_à"],
        
        # Epistémique
        "implies": ["implique", "suggère", "indique"],
        "contradicts": ["contredit", "incompatible_avec", "nie"],
        "supports": ["supporte", "confirme", "renforce"]
    }
    
    EXTRACTION_PROMPT = """
Tu es un extracteur de connaissances structurées. 
Analyse le texte suivant et extrais TOUS les triplets (Sujet, Relation, Objet).

TEXTE:
{text}

INSTRUCTIONS:
1. Identifie chaque affirmation factuelle ou relationnelle
2. Extrais le sujet (concept principal)
3. Identifie la relation (verbe ou lien sémantique)
4. Extrais l'objet (concept lié)
5. Évalue ta confiance (0.0 à 1.0)

FORMAT DE SORTIE (JSON strict):
{{
  "triplets": [
    {{"subject": "...", "relation": "...", "object": "...", "confidence": 0.X}},
    ...
  ]
}}

RÈGLES:
- Utilise des concepts atomiques (1-3 mots max)
- Normalise les relations en snake_case
- Ne garde que les triplets avec confiance > 0.5
- Maximum 10 triplets par texte
"""
    
    def __init__(self, llm_client, min_confidence: float = 0.5):
        self.llm = llm_client
        self.min_confidence = min_confidence
    
    async def extract(
        self, 
        text: str, 
        method: str = "llm_structured"
    ) -> ExtractionResult:
        """
        Extrait les triplets d'un texte.
        
        Args:
            text: Texte à analyser
            method: "llm_structured" | "pattern" | "hybrid"
        
        Returns:
            ExtractionResult avec liste de triplets
        """
        start_time = time.time()
        
        if method == "llm_structured":
            triplets = await self._extract_llm(text)
        elif method == "pattern":
            triplets = self._extract_pattern(text)
        else:  # hybrid
            llm_triplets = await self._extract_llm(text)
            pattern_triplets = self._extract_pattern(text)
            triplets = self._merge_triplets(llm_triplets, pattern_triplets)
        
        # Filtrer par confiance
        triplets = [t for t in triplets if t.confidence >= self.min_confidence]
        
        # Normaliser les relations
        triplets = [self._normalize_relation(t) for t in triplets]
        
        # Dédupliquer
        triplets = self._deduplicate(triplets)
        
        return ExtractionResult(
            triplets=triplets,
            raw_text=text,
            extraction_time_ms=(time.time() - start_time) * 1000,
            model_used=self.llm.model,
            prompt_tokens=len(text) // 4,
            completion_tokens=len(str(triplets)) // 4
        )
    
    async def _extract_llm(self, text: str) -> List[Triplet]:
        """Extraction via LLM avec prompting structuré."""
        prompt = self.EXTRACTION_PROMPT.format(text=text)
        
        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            physics_state=PhysicsState(t=0.5, tau_c=0.7, rho=0, delta_r=0)
        )
        
        # Parser le JSON
        try:
            # Extraire le JSON de la réponse
            json_match = re.search(r'\{[\s\S]*\}', response["text"])
            if json_match:
                data = json.loads(json_match.group())
                return [
                    Triplet(
                        subject=t["subject"].lower().strip(),
                        relation=t["relation"].lower().strip(),
                        object=t["object"].lower().strip(),
                        confidence=float(t.get("confidence", 0.7)),
                        source_text=text[:100],
                        extraction_method="llm_structured",
                        model_source=self.llm.model
                    )
                    for t in data.get("triplets", [])
                ]
        except (json.JSONDecodeError, KeyError) as e:
            logging.warning(f"Failed to parse LLM extraction: {e}")
        
        return []
    
    def _normalize_relation(self, triplet: Triplet) -> Triplet:
        """Normalise la relation vers une forme canonique."""
        relation = triplet.relation.lower().replace(" ", "_")
        
        # Chercher dans les mappings
        for canonical, variants in self.CANONICAL_RELATIONS.items():
            if relation in variants or relation == canonical:
                return Triplet(
                    subject=triplet.subject,
                    relation=canonical,
                    object=triplet.object,
                    confidence=triplet.confidence,
                    source_text=triplet.source_text,
                    extraction_method=triplet.extraction_method,
                    model_source=triplet.model_source
                )
        
        return triplet  # Garder la relation originale si non mappée
```

### 4.5 Intégration dans le flux de chat

```python
# Dans chat.py, après la génération LLM

# STEP 8B: TRIPLET EXTRACTION (if enabled)
if request.enable_triplet_extraction:
    try:
        extractor = TripletExtractor(llm)
        extraction_result = await extractor.extract(response_text)
        
        # Injecter les triplets dans le graphe
        for triplet in extraction_result.triplets:
            await db.apply_delta(GraphDelta(
                operation=DeltaOperation.ADD_EDGE,
                source=triplet.subject,
                target=triplet.object,
                weight=triplet.confidence,
                confidence=triplet.confidence,
                model_source=triplet.model_source,
                reason=f"Extracted: {triplet.relation}"
            ))
        
        logging.info(f"[Triplet] Extracted {len(extraction_result.triplets)} triplets")
    except Exception as e:
        logging.warning(f"Triplet extraction failed: {e}")
```

### 4.6 Critères de validation Phase 2

| Critère | Seuil | Méthode de vérification |
|---------|-------|-------------------------|
| Précision extraction | ≥ 70% | Dataset de test annoté manuellement |
| Rappel extraction | ≥ 50% | Dataset de test |
| Temps extraction | < 2s | Benchmark sur 100 textes |
| Relations normalisées | ≥ 80% | Vérifier mapping vers canoniques |

---

## 5. Phase 3 : Protocole ESMM complet

### 5.1 Objectif

Implémenter l'orchestrateur multi-modèles avec les 3 cycles d'exploration (divergent, débat, méta) et le calcul de la 0-cochaîne.

### 5.2 Livrables

| Livrable | Description | Critère de succès |
|----------|-------------|-------------------|
| **L3.1** | `SemanticExplorationOrchestrator` | 3 cycles fonctionnels |
| **L3.2** | `ZeroCochainCalculator` | Scores de consensus calculés |
| **L3.3** | `KnowledgeGapDetector` | Détection zones sous-explorées |
| **L3.4** | API `/esmm/run` | Exécution protocole complet |
| **L3.5** | Dashboard de visualisation | Graphique d'évolution |

### 5.3 Architecture détaillée de l'orchestrateur

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SemanticExplorationOrchestrator                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        CONFIGURATION                                │    │
│  │                                                                     │    │
│  │  models: List[OllamaWrapper]     # 4 modèles avec personas          │    │
│  │  graph: DynamicDomainGraph       # Graphe cible                     │    │
│  │  diversity_constraints:                                             │    │
│  │    - semantic_distance_min: 0.3  # Réponses doivent différer        │    │
│  │    - concept_coverage_target: 0.7                                   │    │
│  │    - kappa_variance_target: 0.2                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        CYCLE A: DIVERGENT                           │    │
│  │                                                                     │    │
│  │  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐        │    │
│  │  │ Définition    │    │ Transposition │    │ Déconstruction│        │    │
│  │  │ contextuelle  │    │ de domaine    │    │ axiomatique   │        │    │
│  │  │               │    │               │    │               │        │    │
│  │  │ "Définis X    │    │ "Comment Y    │    │ "Quels sont   │        │    │
│  │  │  en contras-  │    │  se manifeste │    │  les axiomes  │        │    │
│  │  │  tant avec    │    │  en domaine Z"│    │  implicites?" │        │    │
│  │  │  3 opposés"   │    │               │    │               │        │    │
│  │  └───────────────┘    └───────────────┘    └───────────────┘        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        CYCLE B: DÉBAT                               │    │
│  │                                                                     │    │
│  │     Round 1              Round 2              Round 3               │    │
│  │  ┌──────────┐         ┌──────────┐         ┌──────────┐             │    │
│  │  │ AVOCAT   │────────▶│ CRITIQUE │────────▶│ SYNTHÈSE │             │    │
│  │  │          │         │          │         │          │             │    │
│  │  │ Défends  │         │ Attaque  │         │ Dépasse  │             │    │
│  │  │ la thèse │         │ les pré- │         │ l'oppo-  │             │    │
│  │  │          │         │ supposés │         │ sition   │             │    │
│  │  └──────────┘         └──────────┘         └──────────┘             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        CYCLE C: MÉTA                                │    │
│  │                                                                     │    │
│  │  Questions auto-réflexives:                                         │    │
│  │  - "Quels biais dans mes réponses précédentes?"                     │    │
│  │  - "Comment ma compréhension de X a-t-elle évolué?"                 │    │
│  │  - "Quelle relation inattendue as-tu découvert?"                    │    │
│  │  - "Quelle serait ta signature épistémique?"                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.4 Personas des modèles

```python
MODEL_PERSONAS = {
    "deepseek-r1": {
        "name": "rigoureux",
        "system_prompt": """Tu es un analyste rigoureux et méthodique.
        - Exige des preuves et des références
        - Décompose les problèmes en étapes logiques
        - Identifie les hypothèses cachées
        - Préfère la précision à la généralité""",
        "temperature": 0.6
    },
    "llama3.3": {
        "name": "créatif",
        "system_prompt": """Tu es un penseur créatif et divergent.
        - Explore des connexions inattendues
        - Propose des analogies originales
        - Questionne les conventions
        - Préfère l'innovation à la conformité""",
        "temperature": 1.0
    },
    "mistral": {
        "name": "pratique",
        "system_prompt": """Tu es un praticien pragmatique.
        - Focus sur l'applicabilité
        - Cherche des exemples concrets
        - Évalue les trade-offs
        - Préfère l'efficacité à l'élégance""",
        "temperature": 0.7
    },
    "gemma3": {
        "name": "sceptique",
        "system_prompt": """Tu es un sceptique constructif.
        - Questionne systématiquement les affirmations
        - Identifie les failles logiques
        - Demande des contre-exemples
        - Préfère la robustesse à la nouveauté""",
        "temperature": 0.5
    }
}
```

### 5.5 Calcul de la 0-cochaîne

```python
class ZeroCochainCalculator:
    """
    Calcule la 0-cochaîne de consensus pour chaque concept.
    
    Une 0-cochaîne est une fonction C: V → ℝ qui assigne à chaque
    concept (sommet) un score de consensus.
    
    Formule:
        C(v) = α * model_agreement(v) + 
               β * semantic_consistency(v) + 
               γ * structural_centrality(v)
    
    Où α + β + γ = 1
    """
    
    def __init__(
        self, 
        graph,
        alpha: float = 0.4,  # Poids accord inter-modèles
        beta: float = 0.3,   # Poids cohérence sémantique
        gamma: float = 0.3   # Poids centralité structurelle
    ):
        self.graph = graph
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
    
    def compute_cochain(
        self, 
        exploration_results: List[Dict]
    ) -> Dict[str, CochainEntry]:
        """
        Calcule la 0-cochaîne complète.
        
        Args:
            exploration_results: Résultats des 3 cycles d'exploration
        
        Returns:
            Dict[concept_id, CochainEntry]
        """
        cochain = {}
        
        # 1. Agréger tous les triplets par concept
        concept_triplets = self._aggregate_by_concept(exploration_results)
        
        for concept_id, triplets in concept_triplets.items():
            # 2. Calculer l'accord inter-modèles
            model_agreement = self._compute_model_agreement(triplets)
            
            # 3. Calculer la cohérence sémantique
            semantic_consistency = self._compute_semantic_consistency(
                concept_id, triplets
            )
            
            # 4. Calculer la centralité structurelle
            structural_centrality = self._compute_structural_centrality(concept_id)
            
            # 5. Score de consensus final
            consensus_score = (
                self.alpha * model_agreement +
                self.beta * semantic_consistency +
                self.gamma * structural_centrality
            )
            
            # 6. Déterminer le type épistémique
            epistemic_type = self._determine_epistemic_type(
                model_agreement, 
                semantic_consistency,
                structural_centrality
            )
            
            cochain[concept_id] = CochainEntry(
                concept_id=concept_id,
                consensus_score=consensus_score,
                model_agreement=model_agreement,
                semantic_consistency=semantic_consistency,
                structural_centrality=structural_centrality,
                epistemic_type=epistemic_type,
                contributing_models=self._get_contributing_models(triplets),
                stability_score=self._compute_stability(concept_id)
            )
        
        return cochain
    
    def _compute_model_agreement(self, triplets: List[Triplet]) -> float:
        """
        Mesure l'accord entre les modèles sur un concept.
        
        Formule: 1 - variance(model_contributions) / max_variance
        
        Si tous les modèles mentionnent le concept → agreement = 1.0
        Si un seul modèle le mentionne → agreement = 0.25
        """
        model_counts = Counter(t.model_source for t in triplets)
        
        # Nombre de modèles uniques
        n_models = len(model_counts)
        total_models = 4  # Configuration standard
        
        # Score basé sur la couverture
        coverage = n_models / total_models
        
        # Score basé sur l'équilibre
        counts = list(model_counts.values())
        if len(counts) > 1:
            balance = 1 - (max(counts) - min(counts)) / sum(counts)
        else:
            balance = 1.0
        
        return 0.6 * coverage + 0.4 * balance
    
    def _determine_epistemic_type(
        self,
        model_agreement: float,
        semantic_consistency: float,
        structural_centrality: float
    ) -> str:
        """
        Détermine si un concept est généraliste, spécialisé ou hybride.
        
        - Généraliste: haut accord, haute centralité, basse spécificité
        - Spécialisé: accord variable, basse centralité, haute cohérence
        - Hybride: scores intermédiaires
        """
        generality_score = (
            model_agreement * 0.4 +
            structural_centrality * 0.4 +
            (1 - semantic_consistency) * 0.2  # Moins spécifique = plus général
        )
        
        if generality_score > 0.7:
            return "generalist"
        elif generality_score < 0.3:
            return "specialized"
        else:
            return "hybrid"

@dataclass
class CochainEntry:
    """Entrée de la 0-cochaîne pour un concept."""
    concept_id: str
    consensus_score: float        # Score final [0, 1]
    model_agreement: float        # Accord inter-modèles
    semantic_consistency: float   # Cohérence sémantique
    structural_centrality: float  # Centralité dans le graphe
    epistemic_type: str           # "generalist" | "specialized" | "hybrid"
    contributing_models: List[str]  # Modèles ayant contribué
    stability_score: float        # Score de stabilité temporelle
```

### 5.6 Détection des lacunes de connaissances

```python
class KnowledgeGapDetector:
    """
    Identifie les zones sous-explorées du graphe pour guider
    les prochaines questions d'exploration.
    """
    
    def __init__(self, graph, cochain: Dict[str, CochainEntry]):
        self.graph = graph
        self.cochain = cochain
    
    def identify_gaps(self) -> KnowledgeGaps:
        """
        Retourne les 3 types de lacunes:
        1. Concepts isolés (degré < 3)
        2. Régions instables (κ < 0)
        3. Ponts manquants entre clusters
        """
        return KnowledgeGaps(
            isolated_concepts=self._find_isolated_concepts(),
            unstable_regions=self._find_unstable_regions(),
            missing_bridges=self._find_missing_bridges()
        )
    
    def _find_isolated_concepts(self, min_degree: int = 3) -> List[str]:
        """Trouve les concepts avec peu de connexions."""
        isolated = []
        for concept_id, entry in self.cochain.items():
            degree = self.graph.get_degree(concept_id)
            if degree < min_degree:
                isolated.append({
                    "concept": concept_id,
                    "degree": degree,
                    "consensus_score": entry.consensus_score
                })
        return sorted(isolated, key=lambda x: x["degree"])
    
    def _find_unstable_regions(self, kappa_threshold: float = 0.0) -> List[Dict]:
        """Trouve les arêtes à courbure négative (tensions)."""
        unstable = []
        for edge in self.graph.get_all_edges():
            if edge.kappa < kappa_threshold:
                unstable.append({
                    "source": edge.source,
                    "target": edge.target,
                    "kappa": edge.kappa,
                    "weight": edge.weight
                })
        return sorted(unstable, key=lambda x: x["kappa"])
    
    def _find_missing_bridges(self) -> List[Dict]:
        """
        Identifie les paires de clusters non connectés qui devraient l'être.
        Utilise la similarité d'embeddings pour détecter les connexions manquantes.
        """
        # Clustering spectral sur le graphe
        clusters = self._spectral_clustering(n_clusters=5)
        
        bridges_needed = []
        for i, cluster_i in enumerate(clusters):
            for j, cluster_j in enumerate(clusters):
                if i >= j:
                    continue
                
                # Calculer la similarité moyenne entre clusters
                avg_similarity = self._cross_cluster_similarity(cluster_i, cluster_j)
                
                # Compter les connexions existantes
                existing_edges = self._count_cross_edges(cluster_i, cluster_j)
                
                # Si similarité haute mais peu de connexions → pont manquant
                if avg_similarity > 0.5 and existing_edges < 3:
                    bridges_needed.append({
                        "cluster_a": list(cluster_i)[:3],  # Exemples
                        "cluster_b": list(cluster_j)[:3],
                        "similarity": avg_similarity,
                        "existing_edges": existing_edges,
                        "priority": avg_similarity * (1 - existing_edges / 10)
                    })
        
        return sorted(bridges_needed, key=lambda x: x["priority"], reverse=True)
```

### 5.7 API Endpoints Phase 3

```python
# router /esmm

@router.post("/esmm/initialize")
async def initialize_esmm(
    seed_type: str = Query("standard", description="Type de graine: standard|minimal|custom"),
    models: List[str] = Query(["deepseek-r1", "llama3.3", "mistral", "gemma3"])
):
    """Initialise l'orchestrateur ESMM avec la configuration."""
    pass

@router.post("/esmm/run-cycle")
async def run_exploration_cycle(
    cycle_type: str = Query(..., description="divergent|debate|meta"),
    iterations: int = Query(5, ge=1, le=20)
):
    """Exécute un cycle d'exploration."""
    pass

@router.post("/esmm/run-full")
async def run_full_protocol(
    cycles_per_type: int = Query(5),
    auto_adapt: bool = Query(True)
):
    """Exécute le protocole ESMM complet (3 cycles)."""
    pass

@router.get("/esmm/cochain")
async def get_cochain(
    min_consensus: float = Query(0.0),
    epistemic_type: Optional[str] = Query(None)
):
    """Récupère la 0-cochaîne actuelle."""
    pass

@router.get("/esmm/gaps")
async def get_knowledge_gaps(
    gap_type: Optional[str] = Query(None, description="isolated|unstable|bridges")
):
    """Identifie les lacunes de connaissances."""
    pass

@router.get("/esmm/stable-truths")
async def get_stable_truths(
    threshold: float = Query(0.8),
    limit: int = Query(50)
):
    """Extrait les connaissances stables (haut consensus)."""
    pass
```

### 5.8 Critères de validation Phase 3

| Critère | Seuil | Méthode de vérification |
|---------|-------|-------------------------|
| Couverture sémantique | > 60% | concepts_uniques / concepts_graine |
| Densité consensus | > 0.7 | moyenne(consensus_score) |
| Diversité épistémique | > 1.5 | entropie(epistemic_type) |
| Stabilité structurelle | > 0.1 | moyenne(κ) |
| Efficacité exploration | > 3.0 | nouvelles_relations / questions |
| Accord inter-modèles | > 0.8 | 1 - variance(model_distribution) |

---

## 6. Schémas de données

### 6.1 Nouvelles tables SQL

```sql
-- ============================================================================
-- TABLE: cochain_entries (0-cochaîne de consensus)
-- ============================================================================
CREATE TABLE IF NOT EXISTS cochain_entries (
    concept_id TEXT PRIMARY KEY,
    consensus_score REAL NOT NULL,           -- Score final [0, 1]
    model_agreement REAL NOT NULL,           -- Accord inter-modèles
    semantic_consistency REAL NOT NULL,      -- Cohérence sémantique
    structural_centrality REAL NOT NULL,     -- Centralité dans graphe
    epistemic_type TEXT NOT NULL,            -- generalist|specialized|hybrid
    contributing_models TEXT NOT NULL,       -- JSON array
    stability_score REAL NOT NULL,           -- Stabilité temporelle
    computed_at REAL NOT NULL,               -- Timestamp
    protocol_version TEXT DEFAULT 'v1',
    
    FOREIGN KEY (concept_id) REFERENCES concepts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cochain_consensus ON cochain_entries(consensus_score DESC);
CREATE INDEX IF NOT EXISTS idx_cochain_type ON cochain_entries(epistemic_type);

-- ============================================================================
-- TABLE: exploration_cycles (Historique des cycles ESMM)
-- ============================================================================
CREATE TABLE IF NOT EXISTS exploration_cycles (
    cycle_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_type TEXT NOT NULL,                -- divergent|debate|meta
    iteration INTEGER NOT NULL,
    question TEXT NOT NULL,
    responses TEXT NOT NULL,                 -- JSON: {model: response}
    triplets_extracted INTEGER NOT NULL,
    consensus_map TEXT,                      -- JSON
    exploration_metrics TEXT,                -- JSON
    started_at REAL NOT NULL,
    completed_at REAL,
    protocol_run_id INTEGER,
    
    FOREIGN KEY (protocol_run_id) REFERENCES esmm_runs(run_id)
);

-- ============================================================================
-- TABLE: esmm_runs (Exécutions du protocole complet)
-- ============================================================================
CREATE TABLE IF NOT EXISTS esmm_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at REAL NOT NULL,
    completed_at REAL,
    config TEXT NOT NULL,                    -- JSON configuration
    models_used TEXT NOT NULL,               -- JSON array
    cycles_completed INTEGER DEFAULT 0,
    total_triplets INTEGER DEFAULT 0,
    final_cochain_size INTEGER,
    status TEXT DEFAULT 'running',           -- running|completed|failed
    error_message TEXT
);

-- ============================================================================
-- TABLE: triplet_extractions (Historique des extractions)
-- ============================================================================
CREATE TABLE IF NOT EXISTS triplet_extractions (
    extraction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_text TEXT NOT NULL,
    subject TEXT NOT NULL,
    relation TEXT NOT NULL,
    object TEXT NOT NULL,
    confidence REAL NOT NULL,
    extraction_method TEXT NOT NULL,
    model_source TEXT NOT NULL,
    injected_to_graph INTEGER DEFAULT 0,     -- Boolean
    delta_id INTEGER,                        -- FK vers graph_deltas si injecté
    extracted_at REAL NOT NULL,
    
    FOREIGN KEY (delta_id) REFERENCES graph_deltas(delta_id)
);

CREATE INDEX IF NOT EXISTS idx_triplets_subject ON triplet_extractions(subject);
CREATE INDEX IF NOT EXISTS idx_triplets_object ON triplet_extractions(object);

-- ============================================================================
-- TABLE: knowledge_gaps (Lacunes identifiées)
-- ============================================================================
CREATE TABLE IF NOT EXISTS knowledge_gaps (
    gap_id INTEGER PRIMARY KEY AUTOINCREMENT,
    gap_type TEXT NOT NULL,                  -- isolated|unstable|bridge
    details TEXT NOT NULL,                   -- JSON
    priority REAL NOT NULL,
    addressed INTEGER DEFAULT 0,             -- Boolean
    addressed_at REAL,
    detected_at REAL NOT NULL,
    protocol_run_id INTEGER,
    
    FOREIGN KEY (protocol_run_id) REFERENCES esmm_runs(run_id)
);
```

### 6.2 Structures de données Python

```python
# Ajouts dans models.py

@dataclass
class TripletData:
    subject: str
    relation: str
    object: str
    confidence: float
    extraction_method: str
    model_source: str

@dataclass
class CochainEntryData:
    concept_id: str
    consensus_score: float
    model_agreement: float
    semantic_consistency: float
    structural_centrality: float
    epistemic_type: str  # Literal["generalist", "specialized", "hybrid"]
    contributing_models: List[str]
    stability_score: float

@dataclass
class KnowledgeGapsData:
    isolated_concepts: List[Dict[str, Any]]
    unstable_regions: List[Dict[str, Any]]
    missing_bridges: List[Dict[str, Any]]

@dataclass
class ExplorationMetrics:
    coverage: float           # Couverture sémantique
    density: float            # Densité de consensus
    diversity: float          # Diversité épistémique
    stability: float          # Stabilité structurelle
    efficiency: float         # Efficacité d'exploration
    agreement: float          # Accord inter-modèles
```

---

## 7. APIs nécessaires

### 7.1 Vue d'ensemble des endpoints

| Phase | Endpoint | Méthode | Description |
|-------|----------|---------|-------------|
| 1 | `/graph/populate` | POST | Charge topics.txt |
| 1 | `/graph/generate-relations` | POST | Crée relations par embeddings |
| 1 | `/graph/inject-seed` | POST | Injecte graine ESMM |
| 2 | `/triplets/extract` | POST | Extrait triplets d'un texte |
| 2 | `/triplets/batch` | POST | Extraction en lot |
| 2 | `/triplets/inject` | POST | Injecte triplets dans graphe |
| 3 | `/esmm/initialize` | POST | Initialise orchestrateur |
| 3 | `/esmm/run-cycle` | POST | Exécute un cycle |
| 3 | `/esmm/run-full` | POST | Protocole complet |
| 3 | `/esmm/cochain` | GET | Récupère 0-cochaîne |
| 3 | `/esmm/gaps` | GET | Lacunes de connaissances |
| 3 | `/esmm/stable-truths` | GET | Vérités stables |
| 3 | `/esmm/status` | GET | Statut exécution |

### 7.2 Contrats d'API détaillés

```yaml
# OpenAPI spec (extrait)

/graph/populate:
  post:
    summary: Charge les concepts depuis topics.txt
    requestBody:
      content:
        application/json:
          schema:
            type: object
            properties:
              source_file:
                type: string
                default: "topics.txt"
              generate_embeddings:
                type: boolean
                default: true
              batch_size:
                type: integer
                default: 50
    responses:
      200:
        content:
          application/json:
            schema:
              type: object
              properties:
                concepts_loaded: integer
                embeddings_generated: integer
                duration_ms: number

/triplets/extract:
  post:
    summary: Extrait des triplets d'un texte
    requestBody:
      content:
        application/json:
          schema:
            type: object
            required: [text]
            properties:
              text:
                type: string
              method:
                type: string
                enum: [llm_structured, pattern, hybrid]
                default: llm_structured
              min_confidence:
                type: number
                default: 0.5
    responses:
      200:
        content:
          application/json:
            schema:
              type: object
              properties:
                triplets:
                  type: array
                  items:
                    $ref: '#/components/schemas/Triplet'
                extraction_time_ms: number

/esmm/run-full:
  post:
    summary: Exécute le protocole ESMM complet
    requestBody:
      content:
        application/json:
          schema:
            type: object
            properties:
              models:
                type: array
                items:
                  type: string
                default: ["deepseek-r1", "llama3.3", "mistral", "gemma3"]
              cycles_per_type:
                type: integer
                default: 5
              auto_adapt:
                type: boolean
                default: true
    responses:
      200:
        content:
          application/json:
            schema:
              type: object
              properties:
                run_id: integer
                status: string
                cycles_completed: integer
                triplets_extracted: integer
                cochain_size: integer
                stable_truths_count: integer
                duration_ms: number
```

---

## 8. Métriques et validation

### 8.1 Métriques par phase

#### Phase 1 : Fondations

| Métrique | Formule | Cible | Alerte |
|----------|---------|-------|--------|
| Concepts chargés | COUNT(concepts) | ≥ 500 | < 400 |
| Embeddings valides | COUNT(embedding != NULL) / COUNT(*) | 100% | < 95% |
| Relations créées | COUNT(relations) | ≥ 1000 | < 500 |
| Connectivité | AVG(degree) | ≥ 3 | < 2 |
| κ distribution | STDDEV(kappa) | < 0.3 | > 0.5 |

#### Phase 2 : Extracteur

| Métrique | Formule | Cible | Alerte |
|----------|---------|-------|--------|
| Précision | TP / (TP + FP) | ≥ 70% | < 60% |
| Rappel | TP / (TP + FN) | ≥ 50% | < 40% |
| F1-Score | 2 * P * R / (P + R) | ≥ 58% | < 50% |
| Latence extraction | AVG(extraction_time_ms) | < 2000 | > 5000 |
| Relations normalisées | canonical / total | ≥ 80% | < 70% |

#### Phase 3 : ESMM complet

| Métrique | Formule | Cible | Alerte |
|----------|---------|-------|--------|
| Couverture sémantique | unique_concepts / seed_concepts | > 0.6 | < 0.4 |
| Densité consensus | AVG(consensus_score) | > 0.7 | < 0.5 |
| Diversité épistémique | H(epistemic_type) | > 1.5 | < 1.0 |
| Stabilité structurelle | AVG(kappa) | > 0.1 | < 0 |
| Efficacité exploration | new_relations / questions | > 3.0 | < 1.5 |
| Accord inter-modèles | 1 - VAR(model_dist) | > 0.8 | < 0.6 |

### 8.2 Dashboard de monitoring

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ESMM MONITORING DASHBOARD                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐         │
│  │     GRAPH EVOLUTION         │    │     CONSENSUS DISTRIBUTION   │         │
│  │                             │    │                             │         │
│  │  Concepts: 623 (+45)        │    │  ▓▓▓▓▓▓▓▓▓▓░░░ 78% high    │         │
│  │  Relations: 2,847 (+312)    │    │  ▓▓▓░░░░░░░░░░ 15% medium  │         │
│  │  Avg κ: 0.23 (+0.02)        │    │  ▓░░░░░░░░░░░░  7% low     │         │
│  │                             │    │                             │         │
│  │  [==========>    ] 67%      │    │  Threshold: 0.8             │         │
│  └─────────────────────────────┘    └─────────────────────────────┘         │
│                                                                             │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐         │
│  │     EPISTEMIC LANDSCAPE     │    │     MODEL CONTRIBUTIONS     │         │
│  │                             │    │                             │         │
│  │     Generalist: 34%         │    │  deepseek-r1  ████████ 28%  │         │
│  │     Hybrid: 45%             │    │  llama3.3     ███████░ 25%  │         │
│  │     Specialized: 21%        │    │  mistral      ███████░ 24%  │         │
│  │                             │    │  gemma3       ██████░░ 23%  │         │
│  │  Entropy: 1.52              │    │                             │         │
│  └─────────────────────────────┘    └─────────────────────────────┘         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     KNOWLEDGE GAPS DETECTED                          │   │
│  │                                                                       │   │
│  │  🔴 12 isolated concepts (degree < 3)                                 │   │
│  │  🟡  5 unstable regions (κ < 0)                                       │   │
│  │  🟠  3 missing bridges between clusters                               │   │
│  │                                                                       │   │
│  │  [View Details] [Auto-Generate Questions] [Export Report]            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Dépendances et risques

### 9.1 Dépendances techniques

| Dépendance | Phase | Criticité | Mitigation |
|------------|-------|-----------|------------|
| Ollama running | Toutes | Critique | Health check au démarrage |
| 4 modèles installés | 3 | Haute | Fallback sur moins de modèles |
| mxbai-embed-large | 1, 2 | Haute | Alternative: all-MiniLM |
| ~16GB VRAM | 3 | Moyenne | Exécution séquentielle |
| SQLite WAL | Toutes | Basse | Fallback standard mode |

### 9.2 Risques identifiés

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Extraction triplets imprécise | Haute | Moyen | Validation humaine échantillon |
| Hallucination consensus | Moyenne | Haute | Cross-validation entre modèles |
| Explosion combinatoire | Basse | Haute | Limiter iterations par cycle |
| Dérive sémantique | Moyenne | Moyenne | Ancrage via graine stable |
| Biais de modèle dominant | Moyenne | Moyenne | Pondération équilibrée |

### 9.3 Plan de contingence

```
SI extraction_precision < 60%:
    → Basculer sur méthode "hybrid" (LLM + patterns)
    → Augmenter min_confidence à 0.7
    → Réduire batch_size

SI consensus_density < 0.5 après 3 cycles:
    → Réinjecter graine seed
    → Réduire diversity_constraints.semantic_distance_min
    → Forcer plus de questions de synthèse (Cycle B)

SI temps_cycle > 30min:
    → Réduire iterations_per_cycle
    → Passer en mode séquentiel (1 modèle à la fois)
    → Utiliser modèles plus légers
```

---

## 10. Calendrier estimé

### 10.1 Timeline globale

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TIMELINE ESMM                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Semaine 1        Semaine 2        Semaine 3        Semaine 4               │
│  ──────────       ──────────       ──────────       ──────────              │
│                                                                             │
│  ┌──────────┐                                                               │
│  │ PHASE 1  │                                                               │
│  │ Fondation│                                                               │
│  │          │                                                               │
│  │ L1.1-L1.4│                                                               │
│  └────┬─────┘                                                               │
│       │                                                                     │
│       └────────────┬                                                        │
│                    │                                                        │
│              ┌─────┴────┐                                                   │
│              │ PHASE 2  │                                                   │
│              │ Triplets │                                                   │
│              │          │                                                   │
│              │ L2.1-L2.4│                                                   │
│              └────┬─────┘                                                   │
│                   │                                                         │
│                   └──────────────┬                                          │
│                                  │                                          │
│                            ┌─────┴────────────────────────────┐             │
│                            │ PHASE 3                          │             │
│                            │ ESMM Complet                     │             │
│                            │                                  │             │
│                            │ L3.1 → L3.2 → L3.3 → L3.4 → L3.5 │             │
│                            └──────────────────────────────────┘             │
│                                                                             │
│  ▓▓▓▓▓ Dev    ░░░░░ Test    ───── Validation                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Détail par phase

| Phase | Durée | Effort | Dépend de |
|-------|-------|--------|-----------|
| **Phase 1** | 3-4 jours | ~20h | Rien |
| └ L1.1 Population | 1 jour | 4h | - |
| └ L1.2 Relations | 1 jour | 6h | L1.1 |
| └ L1.3 Graine | 0.5 jour | 2h | L1.1 |
| └ L1.4 Tests | 1 jour | 6h | L1.1-L1.3 |
| **Phase 2** | 5-7 jours | ~35h | Phase 1 |
| └ L2.1 Extractor | 2 jours | 12h | - |
| └ L2.2 Intégration | 1.5 jours | 8h | L2.1 |
| └ L2.3 API | 1 jour | 6h | L2.1 |
| └ L2.4 Tests | 2 jours | 8h | L2.1-L2.3 |
| **Phase 3** | 10-14 jours | ~60h | Phase 2 |
| └ L3.1 Orchestrateur | 3 jours | 18h | - |
| └ L3.2 0-Cochaîne | 2 jours | 10h | L3.1 |
| └ L3.3 Gap Detector | 2 jours | 8h | L3.2 |
| └ L3.4 API | 2 jours | 10h | L3.1-L3.3 |
| └ L3.5 Dashboard | 3 jours | 12h | L3.4 |

### 10.3 Jalons

| Jalon | Date cible | Critère de succès |
|-------|------------|-------------------|
| **M1**: Graphe fonctionnel | Fin S1 | 500+ concepts, 1000+ relations |
| **M2**: Extraction automatique | Fin S2 | Précision > 70% |
| **M3**: Premier cycle ESMM | Mi-S3 | 1 cycle divergent réussi |
| **M4**: Protocole complet | Fin S3 | 3 cycles + 0-cochaîne |
| **M5**: Production-ready | Fin S4 | Dashboard + monitoring |

---

## 📎 Annexes

### A. Références théoriques

1. **Global Workspace Theory** (Baars, 1988) - Architecture de la conscience
2. **Cell Assemblies** (Hebb, 1949) - Apprentissage par coactivation
3. **Ricci Curvature on Graphs** (Ollivier, 2009) - Courbure discrète
4. **Topological Data Analysis** - 0-cochaînes et homologie

### B. Glossaire

| Terme | Définition |
|-------|------------|
| **0-cochaîne** | Fonction assignant un score à chaque sommet du graphe |
| **κ (kappa)** | Courbure locale d'une arête, mesure la densité structurelle |
| **Triplet (S, R, O)** | Sujet-Relation-Objet, unité atomique de connaissance |
| **Epistemic type** | Classification: généraliste, spécialisé, hybride |
| **Stable truth** | Connaissance avec consensus > 0.8 |

### C. Fichiers à créer

```
lyra_clean/
├── services/
│   └── esmm/
│       ├── __init__.py
│       ├── orchestrator.py      # SemanticExplorationOrchestrator
│       ├── triplet_extractor.py # TripletExtractor
│       ├── cochain.py           # ZeroCochainCalculator
│       ├── gap_detector.py      # KnowledgeGapDetector
│       └── personas.py          # MODEL_PERSONAS config
├── app/
│   └── api/
│       ├── esmm.py              # Router /esmm/*
│       └── triplets.py          # Router /triplets/*
├── scripts/
│   ├── populate_graph.py        # Script Phase 1
│   └── run_esmm_protocol.py     # Script Phase 3
└── tests/
    └── esmm/
        ├── test_extractor.py
        ├── test_cochain.py
        └── test_orchestrator.py
```

---

*Document généré pour le projet Lyra-ACE ESMM*  
*Version 1.0 - 2026-01-21*
