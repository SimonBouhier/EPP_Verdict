# INSTRUCTIONS — Neutralité Linguistique ESMM (Phase 4.8)

> **Auteur** : Sim (architecte) + Opus (auditeur adversarial)
> **Date** : 15 février 2026
> **Statut** : Prêt pour exécution par Claude Code
> **Protocole** : RED-GREEN-FIX obligatoire pour chaque correction
> **Baseline** : 509 passed, 0 failed, 11 skipped

---

## CONTEXTE

Trois problèmes identifiés lors du premier run ESMM live :

1. **Mimétisme linguistique** — Les prompts (`cycle_prompts.py`, `prompts.py`) sont
   intégralement en français. Les modèles répondent en français par mimétisme.
   `normalize_triplet()` ne couvre que l'anglais. Résultat : 48+ triplets extraits
   par run, 0 consensus, 0 attestations.

2. **Rigidité de l'agrégation** — Le consensus par hash SHA-256 exact écrase les
   nuances linguistiques et sémantiques. Deux triplets identiques en sens mais
   formulés différemment ne fusionnent jamais.

3. **Perte d'information épistémique** — Quand deux formulations d'un même triplet
   obtiennent des scores serrés, le système devrait préserver cette friction comme
   signal de haute valeur, pas la trancher arbitrairement.

**Vision EPP** : Une égalité sémantique (tie) n'est pas une erreur. C'est un signal
de friction épistémique à préserver pour des débats futurs. Les langues, comme les
modèles, sont des consommables.

---

## CORRECTION 1 — Prompts en anglais & verrouillage de sortie

**Nature** : Pragmatique, haute priorité. Débloque le consensus immédiatement.

### Fichiers concernés

- `services/esmm/cycle_prompts.py`
- `services/esmm/prompts.py`

### Actions

**1.1** Traduire en anglais l'intégralité de :
- Les 3 `SYSTEM_PROMPTS` (DIVERGENT, DEBATE, META)
- Les 8 `DIVERGENT_TEMPLATES`
- Les 6 `DEBATE_TEMPLATES`
- Les 6 `META_TEMPLATES`
- `TRIPLET_EXTRACTION_PROMPT` — instructions et exemples few-shot
- `TRIPLET_VALIDATION_PROMPT`
- `RELATION_GENERATION_PROMPT`
- `CONCEPT_EXTRACTION_PROMPT`
- Les exemples (entropie → entropy, photosynthèse → photosynthesis, etc.)
- Les docstrings et commentaires (cohérence)

**1.2** Verrouiller la sortie JSON. Ajouter cette directive dans CHAQUE system prompt
(DIVERGENT, DEBATE, META) ET dans `TRIPLET_EXTRACTION_PROMPT` :

```
CRITICAL: Regardless of the user's input language, ALL output keys and values
in the JSON (subjects, relations, objects) MUST be in English.
```

**1.3** Modifier `prompts.py` ligne 99 : `"Français ou Anglais"` → `"English ONLY for subjects, relations and objects"`.

### Contraintes

- NE PAS toucher à `CANONICAL_RELATIONS` (déjà en anglais)
- NE PAS changer les signatures de fonctions (`get_template`, `get_system_prompt`, etc.)
- NE PAS changer `normalize_relation()` dans `prompts.py` (déjà en anglais)
- CONSERVER la qualité des prompts : exemples pertinents et bien formés
- Le format de sortie JSON reste identique

### RED

```python
def test_prompts_are_english():
    """All ESMM prompts must be in English to ensure cross-model consensus."""
    from services.esmm.cycle_prompts import SYSTEM_PROMPTS, CYCLE_TEMPLATES, CycleType
    from services.esmm.prompts import (
        TRIPLET_EXTRACTION_PROMPT,
        TRIPLET_VALIDATION_PROMPT,
        RELATION_GENERATION_PROMPT,
        CONCEPT_EXTRACTION_PROMPT,
    )

    french_markers = [
        "Tu es", "Quelles sont", "Décris", "Identifie", "Réponds",
        "Liste les", "Comment", "Quels concepts", "À partir de",
        "En analysant", "Y a-t-il", "Explore", "Propose",
    ]

    violations = []

    for cycle_type, prompt in SYSTEM_PROMPTS.items():
        for marker in french_markers:
            if marker in prompt:
                violations.append(f"SYSTEM_PROMPTS[{cycle_type.value}] contains '{marker}'")
                break

    for cycle_type, templates in CYCLE_TEMPLATES.items():
        for i, template in enumerate(templates):
            for marker in french_markers:
                if marker in template:
                    violations.append(f"CYCLE_TEMPLATES[{cycle_type.value}][{i}] contains '{marker}'")
                    break

    for name, prompt in [
        ("TRIPLET_EXTRACTION_PROMPT", TRIPLET_EXTRACTION_PROMPT),
        ("TRIPLET_VALIDATION_PROMPT", TRIPLET_VALIDATION_PROMPT),
        ("RELATION_GENERATION_PROMPT", RELATION_GENERATION_PROMPT),
        ("CONCEPT_EXTRACTION_PROMPT", CONCEPT_EXTRACTION_PROMPT),
    ]:
        for marker in french_markers:
            if marker in prompt:
                violations.append(f"{name} contains '{marker}'")
                break

    assert not violations, f"French found in prompts:\n" + "\n".join(violations)
```

### GREEN

Traduire tous les prompts. Le test passe.

### FIX

`pytest tests/ -x -q` — baseline maintenue, 0 failed.

---

## CORRECTION 2 — Semantic merge & ambiguity preservation

**Nature** : Structurelle. Rend le système agnostique à la langue et capable de
capturer la nuance au lieu de la trancher arbitrairement.

### Fichiers concernés

- `services/esmm/consensus_engine.py`
- `services/esmm/triplet_extractor.py`

### Architecture en deux passes

```
Passe 1 (existante) : Hash exact après normalize_triplet()
    → fusionne "PoW uses computing power" et "pow uses computing power"
    → gratuit, 0 latence

Passe 2 (nouvelle) : Clustering sémantique via embeddings
    → fusionne "proof of work uses computing power" et
      "preuve de travail utilise puissance de calcul"
    → nécessite un embedding provider (optionnel)
```

### Seuils — NE PAS CONFONDRE

| Seuil | Valeur | Module | Rôle |
|-------|--------|--------|------|
| Sybil detection | 0.95 | `response_deduplicator.py` | Plagiat entre réponses brutes |
| Semantic merge | 0.85 | `consensus_engine.py` | Équivalence sémantique entre triplets |

Ce sont deux concepts distincts. NE PAS réutiliser 0.95 pour le merge sémantique.

### Embedding provider — optionnel, backward compat

L'embedding provider est passé en paramètre optionnel :

```python
async def compute_consensus(
    self,
    all_triplets: ...,
    model_weights: Optional[Dict[str, float]] = None,
    embedding_provider: Optional["EmbeddingProvider"] = None,
) -> List[ConsensusTriplet]:
```

- Si `embedding_provider is None` → passe 2 skippée, comportement identique à l'actuel
- Les 509 tests existants utilisent `embedding_provider=None` → aucune régression
- Le provider est transmis depuis `TripletExtractor` quand disponible

### Méthode d'embedding

L'embedding se fait sur la concaténation du triplet en une seule string :

```python
triplet_text = f"{subject} {relation} {object}"
embedding = await embedding_provider.embed(triplet_text)
```

Un seul vecteur par triplet. Pas d'embedding séparé sujet/relation/objet.

### Extension du dataclass ConsensusTriplet

Ajouter dans `consensus_engine.py` :

```python
@dataclass
class ConsensusTriplet:
    # ... champs existants ...
    variations: List[Tuple[str, str, str]] = field(default_factory=list)
    ambiguity_detected: bool = False
```

- `variations` : toutes les formulations alternatives du cluster sémantique
- `ambiguity_detected` : True si le cluster contenait des candidats à score serré

### Logique de `_semantic_merge()` dans compute_consensus

1. Après l'agrégation par hash exact (passe 1), collecter les triplets non fusionnés.
2. Calculer la similarité cosinus entre ces triplets via embeddings.
3. Si `sim(A, B) > 0.85` → ils parlent de la même chose. Fusionner les votes.
4. Gestion du représentant canonique :
   - Si un triplet domine clairement (ex: 3 votes vs 1) → il devient le canonique.
   - EN CAS D'ÉGALITÉ ou score serré (ex: 2 votes vs 2) :
     - Choisir le représentant le plus court (déterministe, reproductible).
     - Stocker TOUTES les variations dans `variations`.
     - Mettre `ambiguity_detected = True`.

### Traitement des triplets CONTESTED

Les triplets `ambiguity_detected=True` suivent le flux **normal** de cristallisation.
Le flag est **informatif uniquement**, pas bloquant.

La politique future concernant les triplets contestés (capper le confidence_tier,
réduire le diversity_bonus, relancer un cycle de débat, soumettre à un review humain)
est une **décision communautaire** qui ne doit PAS être tranchée par l'équipe fondatrice.

**Annotation obligatoire** — Claude Code DOIT ajouter ce commentaire dans chaque
fichier concerné, à l'endroit le plus pertinent :

```python
# COMMUNITY_DECISION_REQUIRED: The treatment of CONTESTED consensus
# (ambiguity_detected=True) is deliberately left open. Possible future
# policies include: cap confidence_tier, reduce diversity_bonus, require
# additional debate cycles, or flag for human review. This decision
# should be made by the open-source community, not by the founding team.
# See ADR-009 (pending) for context.
```

Fichiers à annoter :
- `consensus_engine.py` — au niveau du flag `ambiguity_detected`
- `post_crystallization.py` — au niveau du calcul de diversity bonus
- `pipeline.py` — au niveau de la boucle de cristallisation

---

## TESTS RED-GREEN-FIX

### Tests Correction 1

```python
def test_prompts_are_english():
    """Voir section Correction 1 — RED."""
```

### Tests Correction 2

```python
def test_semantic_merge_cross_language():
    """Triplets in different languages about the same concept should merge."""
    # "proof of work USES computing power" (model_A, anglais)
    # "preuve de travail USES puissance de calcul" (model_B, français)
    # Avec embedding provider → cosinus > 0.85 → merge
    # → agreement_ratio >= 2/N → passe le consensus
    assert len(consensus_triplets) >= 1
    assert consensus_triplets[0].agreement_ratio >= 0.5


def test_ambiguity_preservation():
    """Tied votes must preserve all variations, not discard them."""
    # 1 vote pour formulation A, 1 vote pour formulation B, sim > 0.85
    # Le consensus final DOIT contenir les deux textes dans variations
    # et ambiguity_detected == True
    result = consensus_triplets[0]
    assert result.ambiguity_detected is True
    assert len(result.variations) >= 2


def test_semantic_merge_no_false_merge():
    """Triplets about different concepts must NOT merge."""
    # "proof of work USES computing power" et "ice cream HAS flavor"
    # → embeddings très différents → cosinus < 0.85 → pas de merge
    assert len(consensus_triplets) >= 2  # restent séparés


def test_consensus_without_embeddings():
    """Without embedding provider, consensus works as before (hash only)."""
    # Même comportement que pré-semantic-merge
    # Aucun triplet ne fusionne cross-langue
    # Aucune variation stockée
    # ambiguity_detected toujours False
    for t in consensus_triplets:
        assert t.ambiguity_detected is False
        assert t.variations == []
```

---

## ORDRE D'EXÉCUTION

1. **Correction 1** (prompts anglais) — RED → GREEN → FIX
2. **Correction 2** (semantic merge) — RED → GREEN → FIX
3. Relancer `python tests/first_live_run.py`

Si toujours 0 attestations après les deux corrections :
- Vérifier que `min_consensus` est bien à 0.5
- Logger les hashes avant/après normalisation pour diagnostic
- Vérifier que les modèles produisent bien des triplets anglais

---

## DOCUMENTATION POST-IMPLÉMENTATION

### CHANGELOG

Une entrée par correction, format factuel standard.

### ARCHITECTURE.md

Mettre à jour la section consensus_engine.py :
- Documenter les deux passes (hash exact + semantic merge)
- Documenter le dataclass étendu (variations, ambiguity_detected)

### ADR-009 — Language Neutrality in ESMM Protocol (à rédiger)

**Titre** : Language Neutrality in ESMM Protocol

**Décision** : Les langues sont des consommables, comme les modèles. Le protocole
ESMM ne prescrit pas de langue de délibération. Il prescrit :
1. Un format de sortie structuré (triplet JSON)
2. Des relations canoniques en anglais (`CANONICAL_RELATIONS`)
3. Une normalisation sémantique langue-agnostique (embedding-based)
4. Une langue de restitution = celle de l'utilisateur

Les modèles sont libres de délibérer dans la langue de leur choix.
Seule la sortie structurée doit suivre les relations canoniques.

**Zones ouvertes** (COMMUNITY_DECISION_REQUIRED) :
- Traitement des triplets CONTESTED
- Seuil optimal pour le merge sémantique (0.85 = point de départ)
- Pondération des triplets contestés dans le calcul de confiance
