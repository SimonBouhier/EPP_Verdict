# PLAN_MIGRATION_RWA_SOURCES.md
# Plan d'Audit Pré-Migration : `services/rwa/` → `services/sources/`

> **Destinataire** : Claude Code
> **Commanditaire** : Sim (validé par Claude Opus — Auditeur Adversarial)
> **Contexte** : ADR-014 §2.1 et §5.5 — pré-requis bloquant avant le moteur d'audit smart contracts
> **Règle d'or** : Ce plan est un guide. Tu as le code sous les yeux, pas nous. Si tu découvres un cas non prévu ici, documente-le. Ne le cache pas, ne le "corrige" pas silencieusement.

---

## OBJECTIF

Produire un **rapport de diagnostic exhaustif** du périmètre d'impact du renommage `services/rwa/` → `services/sources/`. Ce rapport sera validé par Opus AVANT toute modification de code. Aucun fichier ne doit être modifié dans cette phase — c'est un audit en lecture seule.

---

## PHASE 1 — INVENTAIRE COMPLET (lecture seule)

### 1.1 — Arborescence physique

```bash
# Commande exacte à exécuter et à copier intégralement dans le rapport
find services/rwa/ -type f -name "*.py" | sort
```

Documente chaque fichier trouvé avec son rôle (1 ligne par fichier).

### 1.2 — Imports Python référençant `rwa`

Scanne **tout le projet** (pas seulement `services/`). Les imports peuvent venir de n'importe où : tests, CLI, scripts, demos, outils.

```bash
# Pattern 1 : imports directs
grep -rn "from services.rwa\|from services/rwa\|import services.rwa" --include="*.py" .

# Pattern 2 : imports relatifs (depuis l'intérieur de services/)
grep -rn "from .rwa\|from ..rwa\|from \.rwa" --include="*.py" .

# Pattern 3 : références string (dans des configs, des logs, des messages d'erreur)
grep -rn "services/rwa\|services\.rwa\|services\\\\rwa" --include="*.py" .

# Pattern 4 : dans les fichiers non-Python (configs, docs, scripts shell)
grep -rn "services/rwa\|services\.rwa\|services\\\\rwa" --include="*.md" --include="*.yaml" --include="*.yml" --include="*.toml" --include="*.cfg" --include="*.sh" --include="*.sql" .
```

**ATTENTION** : si tu trouves des patterns que ces grep ne couvrent pas (ex: dynamic imports, `importlib`, `__import__`, paths construits par concaténation), documente-les séparément.

### 1.3 — Fichiers `__init__.py`

```bash
# Lister tous les __init__.py dans services/rwa/ et vérifier leur contenu
find services/rwa/ -name "__init__.py" -exec echo "=== {} ===" \; -exec cat {} \;
```

Les `__init__.py` sont critiques : ils définissent les exports publics du module. S'ils contiennent des re-exports (`from .adapters.opensanctions import OpenSanctionsAdapter`), chaque re-export est un point d'impact.

### 1.4 — Registre des adaptateurs

Le fichier `services/rwa/adapters/__init__.py` contient un `_REGISTRY` et `get_adapter()`. Documente :
- Toutes les clés du registre
- Tous les fichiers qui appellent `get_adapter()`
- Tous les fichiers qui appellent `register_adapter()`

```bash
grep -rn "get_adapter\|register_adapter\|_REGISTRY" --include="*.py" .
```

### 1.5 — Tests référençant `rwa`

```bash
grep -rn "rwa" --include="*.py" tests/
```

Liste chaque fichier de test concerné. Pour chacun, note :
- Est-ce un import ?
- Est-ce un string dans un nom de test ou une assertion ?
- Est-ce un path de fixture ?

### 1.6 — Config et documentation

```bash
grep -rn "rwa" config.yaml ARCHITECTURE.md CHANGELOG.md README.md CLAUDE.md CONTROLS.md ADR-*.md
```

### 1.7 — sys.path et path manipulations

Vérifie s'il existe des manipulations de `sys.path` qui ajoutent explicitement un chemin contenant `rwa` :

```bash
grep -rn "sys.path.*rwa\|Path.*rwa" --include="*.py" .
```

---

## PHASE 2 — ANALYSE D'IMPACT

À partir des résultats de la Phase 1, produis un tableau structuré :

```markdown
| # | Fichier | Ligne(s) | Type de référence | Action requise | Risque |
|---|---------|----------|-------------------|----------------|--------|
| 1 | cli/epp_cli.py | 42 | import from services.rwa.adapters | Renommer import | Faible |
| 2 | ... | ... | ... | ... | ... |
```

**Types de référence possibles** :
- `import` : import Python direct
- `import_relative` : import relatif
- `string_ref` : référence dans un string (log, message, config key)
- `registry` : enregistrement dans un registre d'adaptateurs
- `doc` : référence dans un fichier de documentation
- `test_import` : import dans un fichier de test
- `test_string` : string dans un test (nom de test, assertion)
- `config` : référence dans config.yaml ou autre config
- `dynamic` : import dynamique ou path construit programmatiquement

**Niveaux de risque** :
- `Faible` : renommage mécanique, aucune logique impactée
- `Moyen` : renommage + vérification que le comportement est préservé
- `Élevé` : renommage + changement potentiel de sémantique ou d'import circulaire

---

## PHASE 3 — VÉRIFICATION DES INVARIANTS

Avant de proposer un plan de migration, confirme ces invariants :

### 3.1 — Pas d'import circulaire existant

```bash
# Vérifie que services/rwa/ n'importe pas de module qui importe services/rwa/
# (boucle d'import)
```

Documente la chaîne d'imports complète de chaque fichier dans `services/rwa/`.

### 3.2 — Pas de dépendance externe sur le nom `rwa`

Vérifie que rien d'externe au projet (Anchor, configs Solana, .env, Dockerfile, requirements.txt, setup.py/pyproject.toml) ne référence `services/rwa`.

```bash
grep -rn "rwa" --include="*.toml" --include="*.cfg" --include="*.txt" --include="*.json" --include="*.env*" --include="Dockerfile*" --include="*.lock" .
```

### 3.3 — Baseline des tests

```bash
# Exécuter AVANT toute modification pour capturer la baseline exacte
pytest tests/ -q --tb=no 2>&1 | tail -5
```

Note le nombre exact : `N passed, M skipped, 0 failed`. Ce chiffre est la baseline de non-régression.

---

## PHASE 4 — RAPPORT STRUCTURÉ

Produis un rapport unique avec les sections suivantes :

```markdown
# Rapport Diagnostic — Migration services/rwa → services/sources

## 1. Arborescence (Phase 1.1)
[sortie find]

## 2. Tableau d'impact complet (Phase 2)
[tableau]

## 3. Points d'attention
- Import circulaire détecté : OUI/NON (Phase 3.1)
- Dépendance externe sur le nom rwa : OUI/NON (Phase 3.2)
- Cas non prévus par le plan : [liste ou "aucun"]

## 4. Baseline tests
N passed, M skipped, 0 failed

## 5. Estimation du périmètre
- Fichiers à modifier : X
- Lignes à modifier : Y
- Fichiers de test à modifier : Z

## 6. Proposition de plan de migration
[Claude Code propose son plan — à valider par Opus avant exécution]
```

---

## CE QUI EST INTERDIT DANS CETTE PHASE

- ❌ Modifier un seul fichier
- ❌ Créer un seul fichier
- ❌ Exécuter un refactoring automatique
- ❌ "Corriger" un problème découvert pendant l'audit
- ❌ Omettre un résultat de grep parce qu'il "semble pas important"

## CE QUI EST ATTENDU

- ✅ Exécuter toutes les commandes et copier la sortie brute
- ✅ Documenter tout ce qui est trouvé, même si c'est inattendu
- ✅ Signaler les cas non couverts par ce plan
- ✅ Produire le rapport structuré Phase 4 complet
- ✅ Proposer (sans exécuter) un plan de migration adapté à ce qu'il a trouvé

---

*PLAN_MIGRATION_RWA_SOURCES.md — v1.0*
*Rédigé par Claude Opus (Auditeur Adversarial)*
*Validé par Sim*
*Date : 2026-03-05*
