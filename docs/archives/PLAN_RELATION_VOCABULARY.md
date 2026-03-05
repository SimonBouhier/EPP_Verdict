# Plan de refactoring — `relation_vocabulary.py` (Source unique de vérité)

> **Auteur** : Claude Opus (Auditeur Adversarial)  
> **Date** : 2026-02-20  
> **Statut** : En attente de validation humaine  
> **Prérequis** : ADR-011-v2 corrections C1-C5 terminées (595 passed, 0 failed)  
> **Contrainte absolue** : ADR-006 — aucun hash existant ne doit changer

---

## 1. Problème

Deux modules définissent chacun leur propre dictionnaire de groupes de relations synonymes :

| Module | Variable | Groupes | Format canonique | Rôle |
|:---|:---|:---|:---|:---|
| `consensus_engine.py` | `_RELATION_GROUPS` | 10 | UPPERCASE (`USES`, `CAUSES`…) | Normalisation pour hashing SHA-256 |
| `fingerprint_match.py` | `RELATION_GROUPS` | 6 | lowercase (`uses`, `produces`…) | Compatibilité des voisins dans le MATCH |

### 1.1 — Divergences constatées (fichiers certifiés du 2026-02-20)

| Synonyme | `consensus_engine.py` | `fingerprint_match.py` | Impact |
|:---|:---|:---|:---|
| `relies_on` | → `DEPENDS_ON` | → `uses` | 🔴 Groupes différents |
| `depends_on` | → `DEPENDS_ON` | → `uses` | 🔴 Groupes différents |
| `produces` | Membre de `CAUSES` | Canonique propre | 🔴 Membre vs canonique |
| `creates`, `generates`, `outputs` | Absents | Membres de `produces` | ⚠️ Manquants dans CE |
| `CAUSES` (6 membres) | Présent | Absent | ⚠️ Groupe entier manquant |
| `ENABLES` (5 membres) | Présent | Absent | ⚠️ Groupe entier manquant |
| `PREVENTS` (5 membres) | Présent | Absent | ⚠️ Groupe entier manquant |
| `HAS` (5 membres) | Présent | Absent | ⚠️ Groupe entier manquant |
| `PROVIDES` (5 membres) | Présent | Absent | ⚠️ Groupe entier manquant |
| `invented_by`, `created_by`… | Absents | Groupe propre | ⚠️ Manquants dans CE |

### 1.2 — Le scénario dangereux

Model A dit `"solana relies_on proof_of_history"`, Model B dit `"solana uses proof_of_history"` :

1. **fingerprint_match** les met dans le même groupe (`uses`) → considère compatibles → fusionne
2. **consensus_engine** normalise en groupes différents (`DEPENDS_ON` vs `USES`) → hashes différents → faits distincts

Le fingerprinting fait un travail de réconciliation que le consensus défait immédiatement après.

### 1.3 — Risque futur

Modification d'un synonyme dans un fichier sans l'autre = divergence silencieuse. Aucun test ni mécanisme pour détecter la dérive.

---

## 2. Périmètre

### IN scope

- `consensus_engine.py` : `_RELATION_GROUPS`, `_RELATION_SYNONYMS` (L39-56)
- `fingerprint_match.py` : `RELATION_GROUPS` dans `_normalize_relation()` (L31-43)
- Nouveau module : `relation_vocabulary.py`
- Nouveau flag : `use_legacy_relation_groups` dans `config.yaml`
- Tests associés (dont CI gate)

### OUT scope (couches séparées, ne bougent pas)

| Module | Raison de l'exclusion |
|:---|:---|
| `prompts.py` | Vocabulaire LLM-facing. `normalize_relation()` importé par `triplet_validator.py` uniquement. Couche prompt. |
| `relation_normalizer.py` | DB-backed, lit `canonical_relations` depuis SQLite. Couche post-extraction. Inchangé depuis Phase 0.1. |
| `schema.sql` (`canonical_relations`) | Données SQL avec aliases français. Couche persistance. |

---

## 3. Solution

### 3.1 — Créer `services/esmm/relation_vocabulary.py` (~80 lignes)

Source unique de vérité. Les 10 groupes de `consensus_engine` forment la base (hash stability ADR-006). Enrichissement depuis `fingerprint_match`. Ajout d'un 11ème groupe `CREATED_BY`.

```python
RELATION_GROUPS: Dict[str, Set[str]] = {
    "USES": {"uses", "requires", "needs", "employs", "utilizes", "utilises"},
    "IS_A": {"is_a", "type_of", "is_type", "is_type_of", "kind_of", "instance_of",
             "is_kind_of"},                       # +is_kind_of (ex-fingerprint_match)
    "HAS": {"has", "contains", "includes", "possesses", "owns"},
    "PART_OF": {"part_of", "component_of", "belongs_to", "member_of", "subset_of",
                "contained_in"},                  # +contained_in (ex-fingerprint_match)
    "CAUSES": {"causes", "leads_to", "results_in", "produces", "triggers",
               "creates", "generates", "outputs"},# +creates/generates/outputs (ex-fingerprint_match)
    "ENABLES": {"enables", "allows", "permits", "facilitates", "supports"},
    "PREVENTS": {"prevents", "blocks", "inhibits", "stops", "hinders"},
    "RELATES_TO": {"relates_to", "related_to", "associated_with", "connected_to", "linked_to"},
    "DEPENDS_ON": {"depends_on", "relies_on", "based_on", "built_on"},
    "PROVIDES": {"provides", "offers", "supplies", "gives", "delivers"},
    "CREATED_BY": {"invented_by", "created_by", "designed_by", "developed_by"},
}
```

#### Résolution des conflits

| Conflit | Décision | Justification |
|:---|:---|:---|
| `relies_on`, `depends_on` | → **DEPENDS_ON** | Sémantiquement correct. `fingerprint_match` les avait mal classés dans `uses`. |
| `produces` | ∈ **CAUSES** | Hash stability ADR-006. Changer casserait les hashes existants. |
| `creates`, `generates`, `outputs` | ∈ **CAUSES** | Cohérence avec `produces`. |
| `invented_by` et groupe | Nouveau **CREATED_BY** | N'existait dans aucun groupe de `consensus_engine`. |

#### Exports du module

```python
def build_synonym_map(uppercase_canonicals: bool = False) -> Dict[str, str]:
    """Lookup flat synonyme → canonique. UPPERCASE pour consensus_engine, lowercase pour fingerprint."""

def get_canonical(relation: str, uppercase: bool = False) -> str:
    """Canonique pour une relation. Fallback: la relation elle-même."""

def are_relations_compatible(rel_a: str, rel_b: str) -> bool:
    """True si les deux relations appartiennent au même groupe."""
```

### 3.2 — Flag de déploiement progressif

#### `config.yaml`

```yaml
esmm:
  # ...existing 9 fingerprint keys...
  use_legacy_relation_groups: true   # true = ancien comportement, false = relation_vocabulary.py
```

#### `consensus_engine.py` — conditionnel au flag

```python
from .relation_vocabulary import build_synonym_map

# Legacy groups — frozen snapshot pre-refactoring, used when use_legacy_relation_groups=true
_LEGACY_RELATION_SYNONYMS: Dict[str, str] = {}
_LEGACY_RELATION_GROUPS = {
    "USES": ["uses", "requires", "needs", "employs", "utilizes", "utilises"],
    "IS_A": ["is_a", "type_of", "is_type", "is_type_of", "kind_of", "instance_of"],
    "HAS": ["has", "contains", "includes", "possesses", "owns"],
    "PART_OF": ["part_of", "component_of", "belongs_to", "member_of", "subset_of"],
    "CAUSES": ["causes", "leads_to", "results_in", "produces", "triggers"],
    "ENABLES": ["enables", "allows", "permits", "facilitates", "supports"],
    "PREVENTS": ["prevents", "blocks", "inhibits", "stops", "hinders"],
    "RELATES_TO": ["relates_to", "related_to", "associated_with", "connected_to", "linked_to"],
    "DEPENDS_ON": ["depends_on", "relies_on", "based_on", "built_on"],
    "PROVIDES": ["provides", "offers", "supplies", "gives", "delivers"],
}
for _canonical, _synonyms in _LEGACY_RELATION_GROUPS.items():
    for _syn in _synonyms:
        _LEGACY_RELATION_SYNONYMS[_syn] = _canonical


def _get_relation_synonyms() -> Dict[str, str]:
    """Return active synonym map based on config flag."""
    try:
        from services.config_loader import get_section
        esmm_cfg = get_section("esmm", {})
        if esmm_cfg.get("use_legacy_relation_groups", True):
            return _LEGACY_RELATION_SYNONYMS
    except Exception:
        pass  # Config unavailable (tests, CLI) → use new
    return build_synonym_map(uppercase_canonicals=True)

# SOURCE OF TRUTH: see relation_vocabulary.py — do NOT define local synonym groups
# TODO: Remove _LEGACY after staging validation — see PLAN_RELATION_VOCABULARY.md §3.2
_RELATION_SYNONYMS = _get_relation_synonyms()
```

#### `fingerprint_match.py` — même flag

```python
from .relation_vocabulary import get_canonical, are_relations_compatible

def _normalize_relation(relation: str) -> str:
    """Normalize relation to canonical group."""
    norm = relation.lower().strip().replace("-", "_").replace(" ", "_")
    try:
        from services.config_loader import get_section
        esmm_cfg = get_section("esmm", {})
        if esmm_cfg.get("use_legacy_relation_groups", True):
            # Frozen legacy 6 groups — exact pre-refactoring behavior
            _LEGACY = {
                "uses": {"uses", "relies_on", "utilizes", "employs", "depends_on",
                         "requires", "needs"},
                "is_a": {"is_a", "is_type_of", "is_kind_of", "type_of"},
                "part_of": {"part_of", "component_of", "belongs_to", "contained_in"},
                "produces": {"produces", "generates", "creates", "outputs"},
                "invented_by": {"invented_by", "created_by", "designed_by", "developed_by"},
                "related_to": {"related_to", "associated_with", "connected_to"},
            }
            for canonical, group in _LEGACY.items():
                if norm in group:
                    return canonical
            return norm
    except Exception:
        pass
    # SOURCE OF TRUTH: see relation_vocabulary.py
    # TODO: Remove legacy branch after staging validation
    return get_canonical(norm)


def _relations_compatible(rel_1: str, rel_2: str) -> bool:
    """Check if two relations are compatible (same canonical group or JW > 0.9)."""
    try:
        from services.config_loader import get_section
        esmm_cfg = get_section("esmm", {})
        use_legacy = esmm_cfg.get("use_legacy_relation_groups", True)
    except Exception:
        use_legacy = False

    if use_legacy:
        # Legacy: compare via local _normalize_relation (which uses legacy groups)
        norm_1 = _normalize_relation(rel_1)
        norm_2 = _normalize_relation(rel_2)
        if norm_1 == norm_2:
            return True
    else:
        if are_relations_compatible(rel_1, rel_2):
            return True

    if jaro_winkler_similarity(rel_1.lower(), rel_2.lower()) > 0.9:
        return True
    return False
```

#### Stratégie de déploiement

| Phase | Flag | Comportement | Quand |
|:---|:---|:---|:---|
| 1 — Merge | `true` | Ancien comportement identique. Zéro risque. | Immédiat |
| 2 — Staging | `false` | Nouveau vocabulaire actif. Valider sur live runs. | Après merge + tests manuels |
| 3 — Nettoyage | Supprimer flag + legacy | `relation_vocabulary.py` seul. | Après validation staging |

Phase 3 = dette technique planifiée, pas oubliée. Commentaires `TODO` dans le code.

---

## 4. Tests

### 4.1 — `test_relation_vocabulary.py` — Module partagé

```
test_every_synonym_resolves         — chaque synonyme des 11 groupes → bon canonique
test_uppercase_mode                 — build_synonym_map(True) retourne UPPERCASE
test_lowercase_mode                 — build_synonym_map(False) retourne lowercase
test_compatible_same_group          — are_relations_compatible("relies_on", "depends_on") → True
test_incompatible_different_group   — are_relations_compatible("uses", "depends_on") → False
test_compatible_self                — are_relations_compatible("uses", "uses") → True
test_unknown_relation_fallback      — get_canonical("unknown_thing") → "unknown_thing"
test_created_by_group               — get_canonical("invented_by") et "designed_by" → même canonique
test_no_orphan_synonyms             — chaque synonyme n'appartient qu'à un seul groupe
```

### 4.2 — Tests non-régression hashing (CI gate, bloquant avant merge)

Principe : hardcoder les hashes SHA-256 produits par l'ancien code comme valeurs de référence. Calculer avec le nouveau. Asserter l'identité stricte.

```
@pytest.mark.ci_gate
test_hash_stability_uses            — ("solana", "uses", "proof of history")
test_hash_stability_relies_on       — ("solana", "relies_on", "proof of history")
test_hash_stability_produces        — ("photosynthesis", "produces", "oxygen")
test_hash_stability_leads_to        — ("entropy", "leads_to", "disorder")
test_hash_stability_enables         — ("api", "enables", "integration")
test_hash_stability_related_to      — ("bitcoin", "related_to", "blockchain")
test_hash_stability_part_of         — ("wheel", "part_of", "car")
test_hash_stability_unknown         — ("X", "unknown_rel", "Y") — passthrough
test_hash_stability_entity_synonym  — ("pow", "uses", "energy") — PoW → proof of work
test_hash_stability_created_by      — ("bitcoin", "invented_by", "satoshi") — nouveau, vérifie déterminisme
```

Implémentation : chaque test calcule le hash via les deux chemins (legacy hardcodé + nouveau `build_synonym_map`), asserte l'égalité. Les hashes de référence sont aussi des constantes pour détecter toute dérive future.

### 4.3 — Mise à jour de `test_adr011_fingerprint_match.py`

#### Identification des tests à réviser

```bash
grep -n "relies_on\|depends_on\|_relations_compatible\|_normalize_relation" tests/test_adr011_fingerprint_match.py
```

Tous les tests utilisant `_relations_compatible()` ou `_normalize_relation()` doivent être vérifiés. Les cas affectés par `relies_on` (ancien: `uses`, nouveau: `DEPENDS_ON`) doivent être ajustés.

#### Nouveaux cas explicites pour les incompatibilités

```
test_incompatible_relies_on_vs_uses         — ("relies_on", "uses") → False
                                              (LE changement de comportement voulu)
test_compatible_relies_on_vs_depends_on     — ("relies_on", "depends_on") → True
test_compatible_creates_vs_causes           — ("creates", "causes") → True
test_compatible_invented_by_vs_designed_by  — ("invented_by", "designed_by") → True
test_incompatible_enables_vs_uses           — ("enables", "uses") → False
test_normalize_relies_on                    — _normalize_relation("relies_on") → DEPENDS_ON
test_normalize_produces                     — _normalize_relation("produces") → CAUSES
```

#### Tests du flag legacy

```
test_legacy_flag_true_preserves_old   — flag=true : ("relies_on", "uses") → True (ancien)
test_legacy_flag_false_uses_new       — flag=false : ("relies_on", "uses") → False (nouveau)
```

---

## 5. Séquence d'exécution

| # | Action | Fichier(s) | Risque | Gate |
|:--|:-------|:-----------|:-------|:-----|
| 1 | Créer module partagé | `relation_vocabulary.py` (~80 lignes) | Nul | — |
| 2 | Tests module partagé | `test_relation_vocabulary.py` | Nul | Verts |
| 3 | Tests hash stability CI gate | dans `test_relation_vocabulary.py` | Nul | Verts + hashes hardcodés |
| 4 | Ajouter flag config | `config.yaml` (+1 clé) | Nul | — |
| 5 | Migrer `consensus_engine.py` | Import + flag legacy | **Critique** | — |
| 6 | **GATE** régression flag=true | `pytest tests/` | — | **STOP si échec** |
| 7 | Migrer `fingerprint_match.py` | Import + flag legacy | Moyen | — |
| 8 | **GATE** régression flag=true | `pytest tests/` | — | **STOP si échec** |
| 9 | Ajuster tests fingerprint | `test_adr011_fingerprint_match.py` | Faible | — |
| 10 | Tests flag=false | Basculer flag, `pytest tests/` | Moyen | Verts |
| 11 | Documentation | ADR-011-v2 Q5, ARCHITECTURE.md | Nul | — |

Les étapes 5-8 déploient avec `flag=true` → aucun changement de comportement → régression verte garantie. L'étape 10 valide le nouveau comportement.

---

## 6. Vérification finale (10 preuves)

```bash
# 1. Plus de _RELATION_GROUPS local dans consensus_engine
grep "^_RELATION_GROUPS" services/esmm/consensus_engine.py
# ATTENDU : VIDE (seul _LEGACY_RELATION_GROUPS temporaire)

# 2. Plus de RELATION_GROUPS local dans fingerprint_match (hors legacy)
grep "RELATION_GROUPS" services/esmm/fingerprint_match.py | grep -v "_LEGACY\|import\|legacy"
# ATTENDU : VIDE

# 3. Import correct consensus_engine
grep "from.*relation_vocabulary" services/esmm/consensus_engine.py
# ATTENDU : from .relation_vocabulary import build_synonym_map

# 4. Import correct fingerprint_match
grep "from.*relation_vocabulary" services/esmm/fingerprint_match.py
# ATTENDU : from .relation_vocabulary import get_canonical, are_relations_compatible

# 5. Flag présent dans config
grep "use_legacy_relation_groups" config.yaml
# ATTENDU : use_legacy_relation_groups: true

# 6. Hash CI gate
pytest tests/test_relation_vocabulary.py -v -k "hash_stability" -m "ci_gate"
# ATTENDU : tous PASSED

# 7. Module partagé complet
pytest tests/test_relation_vocabulary.py -v
# ATTENDU : tous PASSED

# 8. Tests fingerprint (flag=true)
pytest tests/test_adr011_fingerprint_match.py -v
# ATTENDU : tous PASSED

# 9. Régression complète (flag=true)
pytest tests/ --tb=short
# ATTENDU : 595+ passed, 0 failures

# 10. Régression complète (flag=false)
# Basculer use_legacy_relation_groups: false, puis :
pytest tests/ --tb=short
# ATTENDU : 595+ passed, 0 failures
```

---

## 7. Ce qui ne change PAS

- `_ENTITY_SYNONYMS`, `_WORD_SYNONYMS` dans `consensus_engine.py`
- `prompts.py` `CANONICAL_RELATIONS` et `normalize_relation()`
- `relation_normalizer.py` (DB-backed)
- `schema.sql` `canonical_relations`
- Aucun hash SHA-256 existant (vérifié par CI gate)
- Format de `_RELATION_SYNONYMS` consommé par `_normalize_relation()` dans CE
- `_normalize_entity()` et `_cosine_similarity()` dans FM
- Interface publique de `reconcile()` dans `orchestrator.py`
- `ESMMRunResult.reconciliation_meta`
- `config.yaml` `esmm.fingerprint` (9 clés existantes)

---

## 8. Documentation

### 8.1 — ADR-011-v2 : Ajouter Q5

> **Q5 — Vocabulaire partagé des relations.** L'implémentation initiale définissait des groupes de relations synonymes indépendamment dans `consensus_engine.py` (10 groupes) et `fingerprint_match.py` (6 groupes), avec des divergences concrètes (`relies_on` → DEPENDS_ON dans le consensus mais → `uses` dans le fingerprinting). Résolu par extraction d'un module partagé `relation_vocabulary.py` (11 groupes, superset). Le conflit `produces ∈ CAUSES` est un choix de compatibilité ADR-006 (hash stability). Les vocabulaires de `prompts.py` (LLM-facing) et `relation_normalizer.py` (DB-backed) restent séparés. Déploiement via flag `use_legacy_relation_groups`.

### 8.2 — ARCHITECTURE.md

Ajouter `relation_vocabulary.py` comme module ESMM, source de vérité des groupes de relations.

### 8.3 — Commentaires code

```python
# consensus_engine.py + fingerprint_match.py :
# SOURCE OF TRUTH: see relation_vocabulary.py — do NOT define local synonym groups
# TODO: Remove _LEGACY after staging validation — see PLAN_RELATION_VOCABULARY.md §3.2
```

### 8.4 — CHANGELOG.md (après exécution)

```
## [2026-02-XX] Refactoring — relation_vocabulary.py (source unique de vérité)

- Nouveau module relation_vocabulary.py : 11 groupes, superset consensus_engine (10) +
  fingerprint_match (6). Résolution conflits relies_on→DEPENDS_ON, produces∈CAUSES (ADR-006).
- consensus_engine.py : _RELATION_GROUPS local supprimé, import depuis relation_vocabulary
- fingerprint_match.py : RELATION_GROUPS local supprimé, import depuis relation_vocabulary
- Flag use_legacy_relation_groups (config.yaml) pour déploiement progressif
- N tests ajoutés dont M CI gate (hash stability). Baseline: 595 → XXX passed, 0 failed
```
