# INSTRUCTIONS_MIGRATION_SOURCES.md
# Instructions de Migration : `services/rwa/` → `services/sources/`

> **Destinataire** : Claude Code
> **Commanditaire** : Sim
> **Validé par** : Claude Opus (Auditeur Adversarial)
> **Prérequis** : Rapport diagnostic du 2026-03-05 (Phase 1-4 validé ✅)
> **Date** : 2026-03-05

---

## SÉQUENÇAGE OBLIGATOIRE

Ce document contient **deux phases séquentielles**. La Phase B ne peut pas
commencer tant que la Phase A n'est pas terminée et validée.

| Phase | Objet | Critère de sortie |
|:------|:------|:-----------------|
| **A** | Stabilisation baseline — 9 échecs Solana + finalisation adapters inachevés | 0 failed, ≥693 passed, ≤10 skipped |
| **B** | Migration `services/rwa/` → `services/sources/` | Baseline identique, 0 référence `services.rwa` résiduelle |

---

# PHASE A — STABILISATION BASELINE

## A.0 — Contexte

9 tests échouent dans `tests/test_phase4_solana.py` (classes `TestTransactionBuildingMockMode`
et `TestSubmitterAuth`) avec `ValueError: Invalid Base58 string` dans `derive_attestation_pda()`.
Deux fichiers non finalisés existent dans `services/rwa/adapters/` : `nist_codata.py` et `wikidata.py`.
Ces éléments sont probablement liés — du travail commencé récemment et non achevé.

## A.1 — Diagnostic Solana (lecture seule d'abord)

Exécute et copie intégralement les sorties :

```bash
# 1. Identifier les 9 tests en échec avec les messages d'erreur complets
pytest tests/test_phase4_solana.py -v --tb=short 2>&1

# 2. Examiner derive_attestation_pda — où est-elle définie, qui l'appelle ?
grep -rn "derive_attestation_pda\|attestation_pda" --include="*.py" .

# 3. Vérifier si des modifications récentes touchent ces fichiers
# (les 3-5 derniers commits sur les fichiers Solana)
git log --oneline -5 -- services/solana/ tests/test_phase4_solana.py

# 4. Vérifier l'état des fichiers non commités
git status --short services/ tests/
```

**Objectif** : comprendre la cause racine. Ne pas corriger avant d'avoir documenté
le diagnostic complet. Produire un mini-rapport :

```markdown
## Diagnostic 9 échecs Solana

### Cause identifiée
[description]

### Fichiers impliqués
[liste avec lignes]

### Correction proposée
[description — NE PAS EXÉCUTER avant validation Sim]

### Impact sur nist_codata.py / wikidata.py
[lien ou absence de lien avec les échecs Solana]
```

## A.2 — Audit des fichiers inachevés

Pour chacun des deux fichiers (`nist_codata.py`, `wikidata.py`) :

```bash
# Contenu complet
cat services/rwa/adapters/nist_codata.py
cat services/rwa/adapters/wikidata.py

# Historique git
git log --oneline --follow -- services/rwa/adapters/nist_codata.py
git log --oneline --follow -- services/rwa/adapters/wikidata.py

# Sont-ils suivis par git ?
git ls-files services/rwa/adapters/nist_codata.py services/rwa/adapters/wikidata.py

# Qui les importe ?
grep -rn "nist_codata\|NistCodata\|wikidata\|Wikidata" --include="*.py" .
```

Produire pour chacun :

```markdown
### nist_codata.py
- Suivi git : OUI/NON
- Implémente SourceAdapter : OUI/NON
- Enregistré dans _REGISTRY : OUI/NON
- Importé par : [liste ou "personne"]
- État : complet / en cours / squelette
- Données requises : [fichiers data/ référencés]
- Action recommandée : finaliser / mettre de côté / supprimer

### wikidata.py
[idem]
```

## A.3 — Correction des échecs Solana

**SEULEMENT après validation du diagnostic par Sim.**

Protocole RED-GREEN-FIX :
1. **RED** : les 9 tests échouent actuellement (déjà prouvé — joindre la sortie pytest)
2. **GREEN** : appliquer la correction minimale
3. **FIX** : `pytest tests/ -q --tb=no 2>&1 | tail -5` — objectif **0 failed**

## A.4 — Finalisation des adapters inachevés

**SEULEMENT après validation du diagnostic par Sim.**

Si `nist_codata.py` et `wikidata.py` sont du travail en cours à finaliser :
- Les faire implémenter `SourceAdapter` (import de `base.py`)
- Les enregistrer dans `_REGISTRY` (dans `__init__.py`)
- Ajouter les tests RED-GREEN-FIX correspondants
- Mettre à jour le CHANGELOG

Si Sim décide de les mettre de côté pour le moment :
- Ne rien changer — ils seront déplacés mécaniquement avec `git mv` en Phase B
- Documenter leur statut dans le CHANGELOG

## A.5 — Validation baseline Phase A

```bash
pytest tests/ -q --tb=no 2>&1 | tail -5
```

**Critère de sortie Phase A** : 0 failed. Le nombre de passed peut augmenter
(si les adapters sont finalisés avec tests). Le nombre de skipped reste ≤ 10.

**Transmettre à Sim** : la sortie pytest complète + le mini-rapport diagnostic.

---

# PHASE B — MIGRATION `services/rwa/` → `services/sources/`

> **Ne pas commencer Phase B sans l'accord explicite de Sim après Phase A.**

## B.0 — Capturer la baseline de référence

```bash
pytest tests/ -q --tb=no 2>&1 | tail -5
# → Noter : X passed, Y skipped, 0 failed
```

Ce chiffre est la baseline Phase B. Il doit être identique après la migration.

## B.1 — Déplacement physique

```bash
git mv services/rwa services/sources
```

## B.2 — Mise à jour imports internes (`services/sources/`)

Dans `services/sources/__init__.py` : aucune modification attendue (commentaire
seulement), mais vérifier.

Dans `services/sources/adapters/__init__.py` (lignes 2-6) :
```
from services.rwa.adapters.base → from services.sources.adapters.base
from services.rwa.adapters.opensanctions → from services.sources.adapters.opensanctions
from services.rwa.adapters.ofac → from services.sources.adapters.ofac
from services.rwa.adapters.eu_cfsp → from services.sources.adapters.eu_cfsp
from services.rwa.adapters.verra_vcs → from services.sources.adapters.verra_vcs
```

Dans les 4 adaptateurs (1 ligne chacun) :
```
services/sources/adapters/eu_cfsp.py    : from services.rwa.adapters.base → from services.sources.adapters.base
services/sources/adapters/ofac.py       : from services.rwa.adapters.base → from services.sources.adapters.base
services/sources/adapters/opensanctions.py : from services.rwa.adapters.base → from services.sources.adapters.base
services/sources/adapters/verra_vcs.py  : from services.rwa.adapters.base → from services.sources.adapters.base
```

Si `nist_codata.py` et `wikidata.py` contiennent des imports `services.rwa`,
les mettre à jour également.

## B.3 — Mise à jour appelant externe

```
services/esmm/source_anchor_builder.py:48
    from services.rwa.adapters import get_adapter
    → from services.sources.adapters import get_adapter
```

## B.4 — Renommage et mise à jour du fichier de test

```bash
git mv tests/test_rwa_source_anchor.py tests/test_adr012_source_anchor.py
```

**Justification du nom** : alignement sur la convention existante du projet
(`test_adr010_consensus_meta.py`, `test_adr011_fingerprint_*.py`). Le contenu
du fichier teste spécifiquement les composants ADR-012 (source anchors,
adapters, frames RWA, bifurcation déterministe).

Dans `tests/test_adr012_source_anchor.py` — mettre à jour les 9 imports :
```
from services.rwa.adapters → from services.sources.adapters
from services.rwa.adapters.opensanctions → from services.sources.adapters.opensanctions
(etc.)
```

## B.5 — Renommage section config.yaml

```yaml
# Ligne 78 (approximatif)
# AVANT :
rwa:
  sources:
    opensanctions:
      ...

# APRÈS :
sources:
  adapters:
    opensanctions:
      ...
```

⚠️ **Vérification critique** : confirmer qu'aucun code Python ne lit cette
section avant de la renommer :

```bash
grep -rn "get_section.*rwa\|get_config.*rwa\|config\[.rwa.\]" --include="*.py" .
# → 0 résultats attendus (confirmé dans le rapport diagnostic)
```

Si des résultats apparaissent (non prévu), **STOP** — documenter et attendre
instruction.

## B.6 — Audit C1 post-migration (signatures fantômes)

```bash
# Aucune référence Python résiduelle au path rwa
grep -rn "services\.rwa\|services/rwa\|from.*\.rwa\.\|from services\.rwa" --include="*.py" .
# → ATTENDU : 0 résultats

# Aucune référence config résiduelle
grep -rn "^rwa:" config.yaml
# → ATTENDU : 0 résultats
# NOTE : les strings "rwa" dans des noms de frames ("rwa_identity_v1.0") ou
# dans des descriptions sont des identifiants sémantiques, PAS des paths.
# Ils ne doivent PAS être renommés.

# Vérifier que l'ancien répertoire n'existe plus
ls -la services/rwa 2>&1
# → ATTENDU : "No such file or directory"
```

## B.7 — Non-régression

```bash
pytest tests/ -q --tb=no 2>&1 | tail -5
# → ATTENDU : exactement la même baseline que B.0
# X passed, Y skipped, 0 failed
```

**Si le chiffre diffère** : ne pas commiter. Exécuter `pytest tests/ -v --tb=short`
pour identifier les tests cassés. Transmettre la sortie à Sim.

## B.8 — Mise à jour documentation

Les fichiers suivants doivent être mis à jour pour remplacer les références
narratives à `services/rwa/` par `services/sources/` :

| Fichier | Occurrences | Nature |
|:--------|:-----------|:-------|
| `ARCHITECTURE.md` | Section "Sources RWA / Bifurcation déterministe" | Paths dans le tableau des composants |
| `CHANGELOG.md` | Entrée de cette migration | Nouvelle entrée en tête de fichier |
| `README.md` | ~5 occurrences | Paths dans la doc utilisateur |

**ADR-012, ADR-013, ADR-014** : les références à `services/rwa/adapters/` dans
ces documents sont historiques. Ajouter une note `[Renommé services/sources/
depuis ADR-014]` sans réécrire l'historique des décisions.

**CHANGELOG.md** — nouvelle entrée (en tête de fichier) :

```markdown
## [2026-03-XX] Migration services/rwa/ → services/sources/ (ADR-014 §2.1)

- Renommage `services/rwa/` → `services/sources/` : alignement sémantique
  (le répertoire accueille toutes les sources autoritaires, pas seulement RWA).
- Renommage `tests/test_rwa_source_anchor.py` → `tests/test_adr012_source_anchor.py`
  (alignement convention ADR-based).
- `config.yaml` : section `rwa:` → `sources:` (aucun code Python ne lisait
  cette section — changement purement documentaire).
- `nist_codata.py` et `wikidata.py` déplacés mais non intégrés dans _REGISTRY
  (statut : [à compléter selon décision Phase A]).
- X passed, Y skipped, 0 failed — baseline préservée.
```

## B.9 — Commit unique

```bash
git add -A
git commit -m "refactor: rename services/rwa/ → services/sources/ (ADR-014 §2.1)

- All imports updated (10 files, 14 lines)
- Test file renamed: test_rwa_source_anchor → test_adr012_source_anchor
- config.yaml section rwa → sources (no runtime reader)
- Docs updated: ARCHITECTURE.md, README.md, CHANGELOG.md
- ADR notes added (ADR-012, ADR-013, ADR-014)
- Baseline preserved: X passed, Y skipped, 0 failed"
```

---

## RÉCAPITULATIF DES LIVRABLES

### Phase A — Livrables à transmettre à Sim
1. Sortie `pytest tests/test_phase4_solana.py -v --tb=short`
2. Mini-rapport diagnostic (cause racine 9 échecs)
3. Audit `nist_codata.py` et `wikidata.py` (statut, contenu, recommandation)
4. Sortie `pytest tests/ -q --tb=no` post-correction (baseline propre)

### Phase B — Livrables à transmettre à Sim
1. Sortie audit C1 (les 3 grep de B.6)
2. Sortie `pytest tests/ -q --tb=no` post-migration (B.7)
3. `git diff --stat` montrant tous les fichiers modifiés
4. CHANGELOG.md mis à jour

---

## CE QUI EST INTERDIT

- ❌ Commencer Phase B sans Phase A validée par Sim
- ❌ Renommer les identifiants sémantiques contenant "rwa"
  (ex: `"rwa_identity_v1.0"`, `ClaimNature`, frame descriptions)
- ❌ Modifier la logique métier des adapters pendant la migration
- ❌ Ajouter ou supprimer des tests pendant la migration Phase B
  (la migration est un renommage pur — le diff ne doit contenir que
  des changements de paths)
- ❌ Faire plusieurs commits pour la Phase B — un seul commit atomique

---

*INSTRUCTIONS_MIGRATION_SOURCES.md — v1.0*
*Rédigé par Claude Opus (Auditeur Adversarial)*
*Validé par Sim*
*Date : 2026-03-05*
