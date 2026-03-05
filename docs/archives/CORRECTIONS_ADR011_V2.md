# CORRECTIONS ADR-011-v2 — Rapport d'audit Opus

**Date** : 18 février 2026
**Verdict initial** : 🔴 ROUGE — Le fingerprinting est structurellement non-fonctionnel en l'état.
**Verdict post-correction** : 🟢 VERT — 5/5 corrections appliquées, 6/6 vérifications passées, 595 passed.
**Livrable audité** : 4 nouveaux modules + 6 fichiers modifiés, 37 tests, 590 passed.
**Corrections appliquées** : 18 février 2026 — 42 tests (37 + 5 nouveaux), 595 passed.

---

## Résumé

L'architecture est bonne. Les 4 corrections du plan v2 (point d'insertion, relations dans MATCH, rapidfuzz, pas de mutation `_collected_triplets`) sont respectées. Mais 5 bugs empêchent le code de fonctionner en conditions réelles. Deux empêchent le module de charger. Un troisième viole la propriété fondamentale de l'ADR-011-v2.

---

## C1 — 🔴 BLOQUANT : Imports fantômes dans `fingerprint_match.py`

### Le problème

`fingerprint_match.py` lignes 18-21 :

```python
from services.esmm.consensus_engine import (
    _cosine_similarity,
    _normalize_entity,
    _normalize_relation,
)
```

**Ces trois fonctions n'existent pas dans `consensus_engine.py`.** Le fichier réel ne contient que 6 fonctions/méthodes :

```
__init__()
compute_consensus()
_hash_triplet()
get_controversial_triplets()
get_high_agreement_triplets()
create_consensus_engine()
```

Le plan les référençait comme existantes aux lignes 92, 114, 131 du fichier — ces lignes contiennent tout autre chose.

### Conséquence

`import` échoue → tout le module `fingerprint_match` est mort → `reconcile()` lève une exception → fallback `"skipped: error"` systématique. **Le fingerprinting ne se déclenche jamais.**

### Correction attendue

Implémenter les 3 fonctions **dans `fingerprint_match.py`** (self-contained, pas de dépendance cross-module sur des fonctions privées) :

```python
def _normalize_entity(entity: str) -> str:
    """Normalize entity for comparison: lowercase, strip, collapse whitespace."""
    return " ".join(entity.lower().strip().split())

def _normalize_relation(relation: str) -> str:
    """Normalize relation to canonical group.
    
    Maps relation synonyms to canonical forms using the same groups
    as normalize_triplet() in consensus_engine.
    """
    RELATION_GROUPS = {
        "uses": {"uses", "relies_on", "utilizes", "employs", "depends_on"},
        "is_a": {"is_a", "is_type_of", "is_kind_of", "type_of"},
        "part_of": {"part_of", "component_of", "belongs_to", "contained_in"},
        "produces": {"produces", "generates", "creates", "outputs"},
        "invented_by": {"invented_by", "created_by", "designed_by", "developed_by"},
        "related_to": {"related_to", "associated_with", "connected_to"},
    }
    norm = relation.lower().strip().replace("-", "_").replace(" ", "_")
    for canonical, group in RELATION_GROUPS.items():
        if norm in group:
            return canonical
    return norm

def _cosine_similarity(vec_a: list, vec_b: list) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
```

Supprimer l'import depuis `consensus_engine`.

### Vérification

```bash
python -c "from services.esmm.fingerprint_match import match_neighbor_pair; print('OK')"
grep -rn "_normalize_entity\|_normalize_relation\|_cosine_similarity" services/esmm/fingerprint_match.py
# Doit montrer des DEF, pas des IMPORT depuis consensus_engine
```

---

## C2 — 🔴 BLOQUANT : Attribut inexistant `self.cycle_manager.rotator`

### Le problème

`orchestrator.py` ligne 547 :

```python
rotator = self.cycle_manager.rotator
```

L'attribut dans `cycle_manager.py` s'appelle `model_rotator` (ligne 137), pas `rotator` :

```python
self.model_rotator = model_rotator
```

### Conséquence

`AttributeError: 'ExplorationCycleManager' has no attribute 'rotator'` → `reconcile()` crashe → fallback systématique.

### Correction attendue

`orchestrator.py` ligne 547 :

```python
# AVANT (cassé)
rotator = self.cycle_manager.rotator

# APRÈS (correct)
rotator = self.cycle_manager.model_rotator
```

### Vérification

```bash
grep -n "\.rotator" services/esmm/orchestrator.py
# Ne doit plus exister

grep -n "\.model_rotator" services/esmm/orchestrator.py
# Doit exister dans reconcile()
```

---

## C3 — 🟠 CRITIQUE : Contamination inter-modèles dans `expand_terms()`

### Le problème

C'est le bug le plus insidieux. Il ne crashe pas — il viole silencieusement la propriété fondamentale.

`fingerprint_expand.py` ligne 158 :

```python
batch_result = await rotator.batch_sequential_providers(
    provider_ids=list(per_model_terms.keys()),
    questions=[prompts[pid] for pid in per_model_terms.keys()],
)
```

`batch_sequential_providers()` envoie la **même liste de questions** à **chaque provider**. C'est son contrat (conçu pour l'extraction de triplets : même texte, tous les modèles). Mais EXPAND a besoin du **contraire** : chaque modèle reçoit un prompt **différent** (ses propres termes uniquement).

Avec le code actuel, si Mistral a `["PoH", "solana"]` et Llama a `["proof of history", "solana"]`, les deux modèles reçoivent **les deux prompts**. Mistral voit les termes de Llama. La contamination épistémique est **structurellement active**.

L'ADR-011-v2 §2.1 dit : *"Propriété fondamentale : aucun modèle ne voit les sorties d'un autre modèle. La contamination épistémique est structurellement impossible."*

### Correction attendue

Appeler le rotator **une fois par modèle**, pas en batch :

```python
for provider_id, terms in per_model_terms.items():
    prompt = build_expand_prompt(terms)
    try:
        result = await rotator.batch_sequential_providers(
            provider_ids=[provider_id],
            questions=[[{"role": "user", "content": prompt}]],
        )
        # ... parse result ...
    except Exception as e:
        logger.warning(f"[EXPAND] Failed for {provider_id}: {e}")
        parse_failures += 1
```

Note : ceci corrige aussi C4 (format des questions, voir ci-dessous).

### Vérification

```bash
# Le mot "batch" ne doit plus apparaître dans une boucle qui passe N provider_ids
grep -A5 "batch_sequential" services/esmm/fingerprint_expand.py
# Doit montrer provider_ids=[provider_id] (un seul), pas la liste complète
```

---

## C4 — 🟠 FRAGILE : Format des questions incorrect pour `batch_sequential_providers()`

### Le problème

`fingerprint_expand.py` ligne 158 passe les prompts comme `List[str]`. Mais `batch_sequential_providers()` attend des `List[List[Dict]]` (liste de questions, chaque question étant une liste de messages).

Référence : `triplet_extractor.py` lignes 251-256 :

```python
messages = [{"role": "user", "content": text}]
return await rotator.batch_sequential_providers(
    provider_ids=provider_ids,
    questions=[messages],
)
```

### Correction attendue

Si C3 est corrigé (appel par modèle), chaque appel doit être :

```python
questions=[[{"role": "user", "content": prompt}]]
```

Pas :

```python
questions=[prompt]  # ← string nue, va échouer ou être itérée char par char
```

### Vérification

```bash
grep -B2 -A2 "questions=" services/esmm/fingerprint_expand.py
# Doit montrer [[{"role": "user", "content": ...}]]
```

---

## C5 — 🟠 FRAGILE : `apply_alignment_to_triplets()` ne gère que les `dict`

### Le problème

`fingerprint_apply.py` lignes 113-120 :

```python
new_t = copy.copy(triplet)
if isinstance(new_t, dict):
    new_t = dict(new_t)
    new_t["subject"] = _align(new_t.get("subject", ""))
    # ...
aligned.append(new_t)
```

Les `raw_model_triplets` contiennent des objets `ExtractedTriplet` (dataclass), pas des dicts. Le `isinstance(new_t, dict)` sera `False` → le triplet est copié **sans alignement** → le fingerprinting ne fait rien.

Preuve : `triplet_extractor.py` ligne 495 :

```python
raw_model_triplets=dict(model_triplets),
```

Et `model_triplets` (ligne 337-353) contient des `ExtractedTriplet` issus de `validator.validate_batch()`.

### Correction attendue

Ajouter le cas objet après le cas dict :

```python
new_t = copy.copy(triplet)
if isinstance(new_t, dict):
    new_t = dict(new_t)
    new_t["subject"] = _align(new_t.get("subject", ""))
    new_t["relation"] = _align(new_t.get("relation", ""))
    new_t["object"] = _align(new_t.get("object", ""))
elif hasattr(new_t, "subject"):
    # ExtractedTriplet or similar dataclass
    new_t.subject = _align(new_t.subject)
    new_t.relation = _align(new_t.relation)
    obj_val = getattr(new_t, "object", "")
    # 'object' is a builtin — some dataclasses use object_ instead
    if hasattr(new_t, "object"):
        new_t.object = _align(obj_val)
    elif hasattr(new_t, "object_"):
        new_t.object_ = _align(getattr(new_t, "object_", ""))
aligned.append(new_t)
```

Alternative plus simple : convertir les triplets en dict à l'accumulation dans `orchestrator.py` :

```python
# Dans execute_cycles(), lors de l'accumulation
for model_id, triplets in result.raw_model_triplets.items():
    as_dicts = []
    for t in triplets:
        if isinstance(t, dict):
            as_dicts.append(t)
        elif hasattr(t, '__dict__'):
            as_dicts.append(vars(t))
        else:
            as_dicts.append({"subject": getattr(t, "subject", ""),
                             "relation": getattr(t, "relation", ""),
                             "object": getattr(t, "object", ""),
                             "confidence": getattr(t, "confidence", 0.0)})
    self._raw_model_triplets.setdefault(model_id, []).extend(as_dicts)
```

Cette deuxième option est préférable : elle normalise les données **une fois** au point d'entrée, et tous les consumers en aval (EXPAND, MATCH, APPLY, consensus cross-cycle) reçoivent un format uniforme.

### Vérification

```bash
# Test unitaire : passer des ExtractedTriplet à apply_alignment_to_triplets
# et vérifier que l'alignement est appliqué (pas juste copié)
pytest tests/test_adr011_fingerprint_apply.py -v -k "triplet"
```

---

## Séquence de correction

| Ordre | Bug | Fichier | Complexité | Statut |
|:------|:----|:--------|:-----------|:-------|
| 1 | C1 — Imports fantômes | `fingerprint_match.py` | 3 fonctions à écrire (~30 lignes) | ✅ Corrigé |
| 2 | C2 — `.rotator` → `.model_rotator` | `orchestrator.py` | 1 ligne | ✅ Corrigé |
| 3 | C3+C4 — Contamination + format | `fingerprint_expand.py` | Réécrire la boucle d'appel (~15 lignes) | ✅ Corrigé |
| 4 | C5 — dict vs objet | `orchestrator.py` + `fingerprint_apply.py` | ~15 lignes | ✅ Corrigé |
| 5 | Tests | `test_adr011_*.py` | 7 tests ajoutés | ✅ 42 passed |
| 6 | Régression | `pytest tests/` | 0 régression | ✅ 595 passed |

---

## Vérification finale exigée

Après corrections, fournir les preuves suivantes :

```bash
# 1. Import propre — aucun import depuis consensus_engine dans fingerprint_match
grep "from.*consensus_engine" services/esmm/fingerprint_match.py
# Doit être VIDE

# 2. Attribut correct
grep "\.rotator" services/esmm/orchestrator.py
# Doit être VIDE (sauf .model_rotator)

# 3. Pas de contamination — un seul provider par appel
grep -A3 "batch_sequential" services/esmm/fingerprint_expand.py
# Doit montrer provider_ids=[provider_id] (singulier)

# 4. Format messages correct
grep "questions=" services/esmm/fingerprint_expand.py
# Doit montrer [[{"role": ...}]]

# 5. Tests passent
pytest tests/test_adr011_fingerprint_config.py tests/test_adr011_fingerprint_expand.py tests/test_adr011_fingerprint_match.py tests/test_adr011_fingerprint_apply.py tests/test_adr011_integration.py -v

# 6. Régression complète
pytest tests/ --tb=short
```

Rien n'est validé tant que ces 6 vérifications ne sont pas fournies avec les logs.

### Résultats des vérifications (18 février 2026)

1. `grep "from.*consensus_engine" services/esmm/fingerprint_match.py` → **VIDE** ✅
2. `grep "\.rotator\b" services/esmm/orchestrator.py` → **VIDE** (seul `.model_rotator` ligne 560) ✅
3. `grep -A3 "batch_sequential" services/esmm/fingerprint_expand.py` → `provider_ids=[provider_id]` ✅
4. `grep "questions=" services/esmm/fingerprint_expand.py` → `[[{"role": "user", "content": prompt}]]` ✅
5. 42 tests ADR-011 → **42 passed** ✅
6. Régression complète → **595 passed, 11 skipped, 0 failures** ✅

---

## Ce qui est bon et ne doit pas changer

- `reconcile()` publique entre `execute_cycles()` et `finalize_run()` ✅
- Relations dans le MATCH (`_relations_compatible` + `match_neighbor_pair` 4 args) ✅
- `rapidfuzz` sans implémentation maison ✅
- `_final_consensus_triplets` sans mutation de `_collected_triplets` ✅
- Union-Find avec path compression ✅
- 4 modules ≤ 200 lignes ✅
- `ESMMRunResult.reconciliation_meta` ✅
- Config.yaml `esmm.fingerprint` 9 clés ✅
- `__init__.py` exports complets ✅
- Fallback timeout/erreur dans `reconcile()` ✅
