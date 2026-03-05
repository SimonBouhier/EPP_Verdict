# PHASE 3.3 — RELECTURE FRAMEWORK + ADR

> **Instructions pour Claude Code.** Lis le nouveau `CLAUDE.md` en entier AVANT ce fichier.
> Ce n'est PAS une phase de développement. C'est une phase de **mise en conformité**
> du code existant avec les 7 règles anti-dette IA (§5) et de création des ADR (§8).
>
> **RÈGLE ABSOLUE** : Tu ne CORRIGES PAS de code dans cette phase sauf les violations
> bloquantes (§5.1-§5.4). Tu ANNOTES, tu REPORTES, tu CRÉES les ADR. C'est tout.
>
> **État actuel** : 425 passed, 0 failed, 10 skipped
> **État cible** : 425+ passed, 0 failed, ADR créés, rapport de conformité livré

---

## AVANT DE COMMENCER

1. Lis le nouveau `CLAUDE.md` (sections 1 à 9)
2. Lis `ARCHITECTURE.md`
3. Exécute : `pytest tests/ --tb=short 2>&1 | tail -5` — note le résultat exact
4. Exécute : `find . -name "*.py" | grep -v __pycache__ | grep -v node_modules | wc -l` — note le nombre de fichiers

---

## BLOC A — AUDIT §5.1 : INSERT BRUTS

### Objectif

Trouver tout `INSERT INTO` sans `OR IGNORE` / `OR REPLACE` dans du code qui
touche une table avec UNIQUE ou PRIMARY KEY.

### Commande

```bash
grep -rn "INSERT INTO" --include="*.py" database/ services/ cli/ app/ \
  | grep -v "INSERT OR" \
  | grep -v "__pycache__" \
  | grep -v "test_"
```

### Pour chaque résultat

1. Identifier la table cible
2. Vérifier dans `schema.sql` si elle a une UNIQUE ou PRIMARY KEY constraint
3. Si oui → **annoter** avec `# AUDIT[§5.1] 🟡 FRAGILE: INSERT brut sur table avec PK/UNIQUE`
4. Si la table n'a pas de contrainte d'unicité → ignorer

### Correction autorisée

Si l'INSERT brut est dans `engine.py` et touche une table à PRIMARY KEY,
remplacer par `INSERT OR IGNORE INTO` sauf si le comportement attendu est
un crash sur doublon (rare — documenter si c'est le cas).

⚡ **VÉRIFIE APRÈS** : `pytest tests/ --tb=short`

---

## BLOC B — AUDIT §5.2 : EXCEPT PASS SANS JUSTIFICATION

### Objectif

Trouver tout bloc `except` qui avale l'erreur sans log, re-raise, ni commentaire.

### Commande

```bash
grep -rn "except" --include="*.py" -A2 database/ services/ app/ cli/ \
  | grep -B1 "pass$" \
  | grep -v "logger\.\|logging\.\|raise\|AUDIT\|# OK:" \
  | grep -v "__pycache__" | grep -v "test_"
```

### Pour chaque résultat

1. Le `except: pass` est-il dans du code qui modifie la DB ? → 🔴 CRITICAL
2. Est-il dans une migration/initialisation idempotente ? → 🟢 ACCEPTED
3. Est-il dans un fallback avec dégradation silencieuse ? → 🟡 FRAGILE

### Action

Ajouter un commentaire justificatif sur chaque `except: pass` non annoté :

```python
# Déjà annoté AUDIT[] → ne rien faire
# AUDIT[A2-005] 🟢 ACCEPTED: ...

# Pas encore annoté → ajouter
except Exception:
    pass  # OK: ALTER TABLE idempotent — colonne peut déjà exister
```

⚠️ **NE PAS corriger le code** (pas de remplacement except:pass → logger).
Seulement annoter. Les corrections seront priorisées après.

---

## BLOC C — AUDIT §5.3 : PROPAGATION DES SIGNATURES

### Objectif

Pour chaque méthode publique de `engine.py` (ISpaceDB), vérifier que tous les
appelants utilisent la bonne signature.

### Méthode

```bash
# 1. Lister les méthodes publiques de ISpaceDB
grep -n "async def [a-z]" database/engine.py | grep -v "^\s*async def _" | head -40

# 2. Pour les méthodes critiques, vérifier les appelants
CRITICAL_METHODS="add_concept store_attestation record_model_prediction log_tier_transition upsert_relations_batch create_esmm_run rollback_deltas"

for m in $CRITICAL_METHODS; do
  echo "========== $m =========="
  echo "--- DÉFINITION ---"
  grep -n "async def $m" database/engine.py
  echo "--- APPELS ---"
  grep -rn "\.$m\|await.*$m" --include="*.py" services/ cli/ app/ tests/ | grep -v "def $m" | grep -v __pycache__
  echo ""
done
```

### Pour chaque mismatch trouvé

- Documenter : fichier, ligne, paramètre manquant ou incorrect
- Corriger SEULEMENT si c'est un crash garanti (ValueError, TypeError)
- Annoter si c'est un risque latent

---

## BLOC D — AUDIT §5.4 : COHÉRENCE SCHÉMA ↔ CODE

### Objectif

Vérifier que toute table et colonne référencée dans `engine.py` existe dans `schema.sql`.

### Commande

```bash
# Tables
grep -oP "(?:FROM|INTO|UPDATE|JOIN)\s+(\w+)" database/engine.py \
  | awk '{print $2}' | sort -u | grep -v SET > /tmp/code_tables.txt

grep -oP "CREATE TABLE IF NOT EXISTS (\w+)" database/schema.sql \
  | awk '{print $NF}' | sort > /tmp/schema_tables.txt

echo "=== TABLES DANS LE CODE MAIS PAS DANS LE SCHÉMA ==="
comm -23 /tmp/code_tables.txt /tmp/schema_tables.txt

echo "=== TABLES DANS LE SCHÉMA MAIS PAS DANS LE CODE ==="
comm -13 /tmp/code_tables.txt /tmp/schema_tables.txt
```

### Si des tables manquent

**STOP.** C'est une violation §5.4 bloquante. Signaler immédiatement avec :
- La liste des tables manquantes
- Les méthodes qui les référencent
- Les colonnes déduites des INSERT/SELECT

Ne PAS ajouter les tables toi-même sans instruction explicite.

### Vérification des colonnes critiques

Pour les 5 tables les plus utilisées (`concepts`, `relations`, `attestations`,
`triplet_extractions`, `graph_deltas`), comparer les colonnes :

```bash
# Colonnes dans un INSERT engine.py (exemple pour attestations)
grep -A20 "INSERT INTO attestations" database/engine.py | head -25

# Colonnes dans le CREATE TABLE schema.sql
sed -n '/CREATE TABLE.*attestations/,/);/p' database/schema.sql
```

---

## BLOC E — AUDIT §5.5 : SINGLETONS VÉRIFIÉS

### Objectif

Inventaire de tous les singletons et vérification qu'ils gèrent le changement
de paramètres.

### Commande

```bash
grep -rn "global _" --include="*.py" database/ services/ app/ \
  | grep -v __pycache__ | grep -v test_
```

### Pour chaque singleton trouvé

Remplir ce tableau :

```
| Fichier | Variable | Vérifie params ? | Reset existe ? | Annoté ? |
|---------|----------|-----------------|----------------|----------|
```

Les singletons connus (vérifier l'état actuel) :
- `database/pool.py` : `_pool_instance` — corrigé Phase 3.1 (vérifie db_path)
- `database/engine.py` : `_db_instance` via `get_db()` — close_db() existe
- `services/config_loader.py` : `_config` — reset_config() existe
- `services/esmm/entity_resolver.py` : `_resolver_instance` — reset ?
- `services/providers/ollama.py` : `_ollama_instance` — reset ?
- `services/providers/ollama_embeddings.py` : `_ollama_embedding_instance` — reset ?

Si un singleton n'a ni vérification de params ni reset → annoter :
`# AUDIT[§5.5] 🟡 FRAGILE: singleton sans vérification de changement de params`

---

## BLOC F — AUDIT §5.6 : TESTS SUBSTANTIFS

### Objectif

Identifier les tests dont l'assertion la plus forte est `assert X is not None`.

### Commande

```bash
# Assertions faibles
grep -rn "assert.*is not None$" --include="*.py" tests/
grep -rn "assert True$" --include="*.py" tests/
grep -rn "assert.*is True$" --include="*.py" tests/

# Ratio assertions/tests
for f in tests/test_*.py; do
  tests=$(grep -c "def test_" "$f" 2>/dev/null)
  asserts=$(grep -c "assert " "$f" 2>/dev/null)
  [ "$tests" -gt 0 ] && echo "$f: $asserts asserts / $tests tests (ratio: $((asserts / tests)))"
done 2>/dev/null
```

### Action

Lister les fichiers avec ratio < 2 assertions/test. Ce sont les fichiers
les plus susceptibles de contenir des tests tautologiques.

Ne PAS modifier les tests. Lister seulement.

---

## BLOC G — AUDIT §5.7 : CONFIGURATION EFFECTIVE

### Objectif

Identifier les clés de `config.yaml` jamais lues par le code, et les valeurs
hardcodées dans le code qui devraient venir de config.yaml.

### Commande

```bash
# Clés lues depuis config dans le code
grep -rn "get_value\|get_section\|get_config" --include="*.py" \
  services/ database/ cli/ app/ | grep -v __pycache__ | grep -v test_

# Clés définies dans config.yaml
grep -E "^\s+\w+:" config.yaml | sed 's/:.*//' | sed 's/^\s*//'

# Valeurs hardcodées candidates
grep -rn '"data/ispace.db"\|"data/epp.db"\|"http://localhost:11434"\|"mxbai-embed-large"' \
  --include="*.py" database/ services/ | grep -v __pycache__ | grep -v test_
```

### Action

Produire deux listes :
1. **Clés config.yaml orphelines** (définies mais jamais lues)
2. **Valeurs hardcodées** (dans le code mais devraient venir de config)

Ne PAS corriger. Lister seulement.

---

## BLOC H — CRÉATION DES ADR

### Objectif

Créer le dossier `docs/adr/` et les 7 ADR identifiés dans CLAUDE_OPUS.md §8.

### Étape 1 — Créer le dossier

```bash
mkdir -p docs/adr
```

### Étape 2 — Créer chaque ADR

⚡ **VÉRIFIE D'ABORD** pour chaque ADR : retrouve dans le code la décision réelle
et ses paramètres. Ne PAS inventer les valeurs — les lire dans le code.

#### ADR-001 : Encodage float → u16 pour Solana

```bash
# Vérifier le SCORE_SCALE réel
grep -n "SCORE_SCALE\|10000\|float_to_u16" services/solana/bridge.py | head -5
```

Puis créer `docs/adr/ADR-001.md` :

```markdown
# ADR-001 : Encodage float → u16 [0, 10000] pour Solana
**Date** : 2026-02-06
**Statut** : Actif

## Contexte
Solana n'a pas de type float natif. Les scores de consensus et les composantes
de la signature 5D sont des floats [0.0, 1.0] côté Python.

## Décision
Multiplier par 10000 et stocker comme u16. Précision : 4 décimales.
Roundtrip testé : `decode(encode(f)) ≈ f` avec tolérance 1e-4.

## Conséquences
Ne PAS changer le SCORE_SCALE sans migrer toutes les attestations on-chain existantes.
```

#### ADR-002 : 4 tiers de confiance

```bash
grep -n "sandbox\|proposition\|validated\|verified" services/esmm/attestation.py | head -10
```

```markdown
# ADR-002 : 4 tiers de confiance (sandbox → proposition → validated → verified)
**Date** : 2026-02-08
**Statut** : Actif

## Contexte
Les anciens tiers (low/medium/high) ne capturaient pas la sémantique épistémique.
Le tier "verified" nécessite une source externe (source_anchor).

## Décision
4 tiers ordonnés : sandbox < proposition < validated < verified.
Dérivation multi-critères (score, modèles, familles d'architecture).

## Conséquences
Les attestations existantes utilisent ces tiers. Tout changement de nom ou
de sémantique casse la compatibilité. Les tests Phase 0.3 en dépendent.
```

#### ADR-003 : Pipeline unique (pas de run parallèle)

```bash
grep -n "SINGLE_RUN\|double.*run\|already.*running\|D1" services/esmm/pipeline.py | head -5
```

```markdown
# ADR-003 : Pipeline unique — un seul run ESMM à la fois
**Date** : 2026-02-10
**Statut** : Actif

## Contexte
Deux runs simultanés sur la même question produiraient deux attestations
différentes (timestamps, consensus légèrement différent).

## Décision
Un seul run ESMM actif par question. Vérifié dans pipeline.py (décision D1).

## Conséquences
Ne PAS paralléliser les runs ESMM sans revoir la déduplication des attestations.
```

#### ADR-004 : INSERT OR IGNORE sur concepts (pas REPLACE)

```bash
grep -n "INSERT OR IGNORE INTO concepts" database/engine.py | head -3
```

```markdown
# ADR-004 : INSERT OR IGNORE sur concepts (pas REPLACE)
**Date** : 2026-02-05
**Statut** : Actif

## Contexte
INSERT OR REPLACE détruit les métadonnées existantes (created_at, embeddings,
degree) lors d'un remplacement. Un concept réinjecté doit conserver son historique.

## Décision
INSERT OR IGNORE sur la table concepts. Si le concept existe, on ne touche à rien.

## Conséquences
Pour mettre à jour un concept existant, utiliser UPDATE explicite, pas INSERT OR REPLACE.
```

#### ADR-005 : Confidence tiers multi-critères

```bash
grep -n "derive_confidence_tier\|models_consulted.*architecture" services/esmm/attestation.py | head -5
```

```markdown
# ADR-005 : Tiers de confiance dérivés multi-critères
**Date** : 2026-02-08
**Statut** : Actif

## Contexte
Un seuil unique sur le consensus_score ne capture pas la robustesse.
Un score de 0.8 avec 2 modèles de la même famille ≠ 0.8 avec 3 familles.

## Décision
derive_confidence_tier() utilise : consensus_score + models_consulted +
architecture_families. Seuils définis dans le code, pas dans config.yaml.

## Conséquences
Ne PAS revenir à un tier par seuil simple. Les seuils multi-critères sont
la raison d'être de la signature 5D.
```

#### ADR-006 : Claim hash = SHA-256

```bash
grep -n "compute_claim_hash\|sha256\|claim_hash" services/esmm/attestation.py | head -5
```

```markdown
# ADR-006 : Claim hash = SHA-256(subject + predicate + object + frame)
**Date** : 2026-02-05
**Statut** : Actif

## Contexte
Le claim hash identifie de manière unique un triplet dans un cadre métrologique.
Il sert de clé de déduplication et de chaînage d'attestations.

## Décision
SHA-256 du JSON canonique {subject, predicate, object, metrological_frame}.
Encodage UTF-8, tri des clés, séparateurs compacts.

## Conséquences
Changer la formule du hash casse le chaînage (previous_hash) et la déduplication.
Les attestations on-chain référencent ce hash. Immuable.
```

#### ADR-007 : Attestations append-only

```bash
grep -n "UPDATE.*attestation\|append.only" database/engine.py | head -5
```

```markdown
# ADR-007 : Attestations append-only (pas d'UPDATE sauf solana_tx)
**Date** : 2026-02-05
**Statut** : Actif

## Contexte
Une attestation est un fait épistémique horodaté. La modifier après coup
invaliderait sa signature et son hash.

## Décision
Seuls les champs de soumission Solana (solana_tx_signature, submission_status)
peuvent être mis à jour. Le contenu épistémique est immuable.

## Conséquences
Pour corriger une attestation, en créer une nouvelle avec previous_hash
pointant vers l'ancienne. Ne JAMAIS UPDATE le contenu.
```

### Vérification Bloc H

```bash
ls -la docs/adr/
# Attendu : 7 fichiers ADR-001.md à ADR-007.md
cat docs/adr/ADR-001.md | wc -l
# Attendu : ~12 lignes par fichier (pas plus)
```

---

## BLOC I — RAPPORT DE CONFORMITÉ

### Objectif

Produire un rapport synthétique de conformité aux 7 règles anti-dette.

### Format

```markdown
## Rapport de Conformité §5 — CLAUDE.md
Date : YYYY-MM-DD

### §5.1 — INSERT bruts
- X trouvés, Y corrigés, Z annotés

### §5.2 — except:pass sans justification
- X trouvés, Y déjà annotés AUDIT[], Z nouvellement annotés

### §5.3 — Signatures non propagées
- X méthodes vérifiées, Y mismatches trouvés

### §5.4 — Schéma ↔ code
- Tables : X dans le code, Y dans le schéma, Z divergences
- Colonnes critiques vérifiées : (liste)

### §5.5 — Singletons
| Fichier | Variable | Vérifie params | Reset | Annoté |
|---------|----------|---------------|-------|--------|

### §5.6 — Tests substantifs
- Fichiers avec ratio < 2 : (liste)
- Assertions faibles : X total

### §5.7 — Configuration
- Clés orphelines : X
- Valeurs hardcodées : Y

### ADR créés : 7 (docs/adr/ADR-001 à ADR-007)
```

Ce rapport est ajouté à la fin de `CHANGELOG.md` comme entrée Phase 3.3.

---

## VALIDATION FINALE

```bash
# 1. Tests (rien ne doit avoir cassé)
pytest tests/ --tb=short 2>&1 | tail -5

# 2. ADR
ls docs/adr/ADR-*.md | wc -l  # Attendu : 7

# 3. Annotations nouvelles
grep -rn "AUDIT\[§5" --include="*.py" database/ services/ app/ cli/ | wc -l

# 4. Rapport de conformité
# → Intégré dans CHANGELOG.md

# 5. Diff documentation (preuve C9)
echo "=== CHANGELOG.md ==="
git diff docs/fr/CHANGELOG.md | head -20
echo "=== docs/adr/ ==="
git status docs/adr/
```

### CHANGELOG.md

```markdown
## [2026-02-12] Phase 3.3 — Relecture framework + ADR

- Audit de conformité CLAUDE.md §5 (7 règles anti-dette IA)
- Créé 7 Architecture Decision Records (docs/adr/ADR-001 à ADR-007)
- Annoté X violations §5.1-§5.7 dans le code
- Rapport de conformité : Y INSERT bruts, Z except:pass, W singletons
- Tests: 425 passed, 0 failed, 10 skipped
```

---

## CE QUE TU NE FAIS PAS DANS CETTE PHASE

1. **Tu ne refactorises PAS.** Pas de migration des tests asyncio.run → async def.
2. **Tu ne corriges PAS les except:pass.** Tu les annotes, c'est tout.
3. **Tu ne crées PAS de nouveaux tests.** Tu audites les existants.
4. **Tu ne touches PAS à config.yaml.** Tu listes les incohérences.
5. **Tu ne modifies PAS les singletons.** Tu documentes leur état.
6. **Tu ne changes PAS les ADR après les avoir créés.** Ils sont figés.

La seule exception : les violations §5.1 (INSERT brut) et §5.3 (signature fantôme)
qui sont des crashs runtime garantis peuvent être corrigées, avec pytest après.

---

*Phase 3.3 — Relecture framework + conformité CLAUDE.md*
*Audit only. Annotate, don't fix.*
