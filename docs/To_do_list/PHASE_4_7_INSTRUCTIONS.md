# PHASE 4.7 — PEAUFINAGE POST-RECETTE

> **État d'entrée** : 470 passed, 0 failed, 11 skipped.
> **Principe** : Diagnostic avant correction. Pas de code pré-écrit.

---

## §0 — PROTOCOLE DE RÉCUPÉRATION DE CONTEXTE (OBLIGATOIRE)

> Ce bloc est exécuté EN PREMIER à chaque nouvelle session, chaque reprise
> après compression mémoire, chaque nouvel agent. Pas d'exception.
> Il garantit que Claude Code travaille avec les bons axiomes.

```bash
# 1. LIRE les documents fondateurs (dans cet ordre)
cat CLAUDE.md          # Règles anti-dette §5, méthode §7, état du projet §9
cat ARCHITECTURE.md    # Structure réelle du code, dépendances, état composants

# 2. LIRE les ADR pertinents pour cette phase
cat docs/adr/ADR-001.md   # Encodage float→u16 (bridge)
cat docs/adr/ADR-005.md   # Tiers multi-critères (Sybil)
cat docs/adr/ADR-008.md   # Auth submitter Solana

# 3. LIRE le CHANGELOG pour connaître l'historique récent
head -80 CHANGELOG.md     # Phase 4 complète

# 4. CONFIRMER le baseline
pytest tests/ --tb=short 2>&1 | tail -5
# Attendu : 470 passed, 0 failed, 11 skipped
```

**Si le baseline ne correspond pas** → STOP. Signaler l'écart avant de continuer.

**Règle pour toute future phase** : Copier ce §0 en tête de chaque nouveau
fichier d'instructions. Claude Code doit TOUJOURS relire CLAUDE.md et
ARCHITECTURE.md avant de coder. Sa mémoire compressée n'est pas fiable.

---

## BLOC 0 — RAFRAÎCHIR ARCHITECTURE.md (vérifié obsolète)

### Pourquoi c'est le premier bloc

ARCHITECTURE.md est daté du 2026-02-10. La Phase 4 a été livrée le 2026-02-12.
Ce document ne reflète plus l'état réel du code. Si Claude Code le lit (§0),
il aura une vision fausse.

**Note** : CLAUDE.md a été mis à jour manuellement (§9 : Phase 4 ajoutée,
baseline 470 tests, priorités actualisées). Ne PAS le modifier — il est FIGÉ
par convention (ligne 3 du fichier).

### Écarts confirmés sur ARCHITECTURE.md

| # | Section | État actuel ARCHITECTURE.md | Réalité post-Phase 4 |
|---|---------|---------------------------|---------------------|
| 1 | `app/embeddings.py` | Listé "⚠️ Déprécié, émet DeprecationWarning" | **Supprimé** en Phase 4.4 |
| 2 | `schema.sql` | "22 tables SQLite" | `semantic_memory` supprimée → **23 tables** |
| 3 | `config.yaml` | "✅ Fonctionnel" sans détail | Purgé **35→12 clés**, 3 sections mortes supprimées (Phase 4.4) |
| 4 | `client.py` Solana | "✅ Fonctionnel (AUDIT_REQUIRED)" | Phase 4.6 : transaction building, account deser, PDA validation, queries memcmp, mock mode |
| 5 | ADR | Aucune mention | 8 ADR actifs dans `docs/adr/` (ADR-001 à ADR-008) |
| 6 | Phase 4 | Absente | Isolation singletons, sécurité, get_db() warning, close_*() ajoutés |
| 7 | Date | "2026-02-10" | Doit être **"2026-02-12"** |

### Action

⚡ **VÉRIFIE D'ABORD** chaque point avant de modifier :

```bash
# Point 1 : embeddings.py supprimé ?
ls app/embeddings.py 2>/dev/null && echo "EXISTE ENCORE" || echo "SUPPRIMÉ ✅"

# Point 2 : nombre réel de tables
grep -c "CREATE TABLE" database/schema.sql

# Point 3 : nombre réel de clés config
cat config.yaml

# Point 4 : méthodes Solana ajoutées
grep -n "def _build_and_send\|def _deserialize\|def check_pda_exists\|def query_attestations" services/solana/client.py

# Point 5 : ADR existants
ls docs/adr/ADR-*.md

# Point 6 : singletons avec warning
grep -n "logger.warning.*different\|logger.warning.*existing" database/engine.py

# Point 7 : date actuelle
head -5 ARCHITECTURE.md
```

Puis mettre à jour ARCHITECTURE.md pour chaque point CONFIRMÉ :

1. Supprimer la ligne `embeddings.py` du tableau legacy (si confirmé supprimé)
2. Corriger le nombre de tables (mettre le résultat exact du grep)
3. Ajouter note purge config : "Purgé Phase 4.4 : 12 clés effectives"
4. Mettre à jour section Solana avec les méthodes confirmées par grep
5. Ajouter section "Architecture Decision Records" référençant `docs/adr/`
6. Ajouter changements Phase 4 structurels confirmés par grep
7. Mettre à jour la date

**Attention** : ne modifier QUE ce qui est confirmé par les grep.

### Validation Bloc 0

```bash
head -5 ARCHITECTURE.md         # date = 2026-02-12
grep "embeddings.py" ARCHITECTURE.md  # ne doit rien retourner (sauf dans legacy supprimé)
grep "ADR" ARCHITECTURE.md            # doit retourner la nouvelle section
pytest tests/ --tb=short              # aucun changement fonctionnel attendu
```

---

## BLOC A — DIAGNOSTIC : `infer_architecture_family()` et providers

### Problème suspecté (⚠️ INFÉRÉ, possiblement périmé)

Opus suspecte que certains providers (`openai_compat.py`, `anthropic.py`)
hardcodent leur `architecture_family` au lieu d'appeler la fonction
centralisée `infer_architecture_family()`. Si c'est le cas, l'amélioration
Phase 4.5 (first-token match) ne profite pas à ces providers.

### A.1 — Diagnostic complet

```bash
# 1. État actuel de la fonction centralisée
grep -A15 "def infer_architecture_family" services/providers/base.py

# 2. TOUS les endroits où architecture_family est assigné dans les providers
grep -rn "architecture_family" --include="*.py" services/providers/ \
  | grep -v __pycache__ | grep -v test_ | grep -v mock

# 3. Spécifiquement : providers qui hardcodent au lieu de déléguer
grep -rn "architecture_family.*=.*\"transformer\|architecture_family.*=.*\"openai\|architecture_family.*=.*\"anthropic\|architecture_family.*=.*\"google\|architecture_family.*=.*\"unknown" \
  --include="*.py" services/providers/ \
  | grep -v __pycache__ | grep -v test_ | grep -v mock | grep -v base.py
```

### A.2 — Décision

- **Si 0 résultats en A.1 étape 3** → Rapport : "Bloc A : ✅ déjà conforme."

- **Si ≥ 1 résultat** → Pour CHAQUE provider qui hardcode :
  1. Remplacer le hardcode par `infer_architecture_family(self.model)`
  2. Ajouter l'import si nécessaire
  3. Écrire UN test qui vérifie la cohérence
  4. Relancer le grep → doit retourner 0

### Validation Bloc A

```bash
pytest tests/ --tb=short
```

---

## BLOC B — DIAGNOSTIC : état de `client.py` post Phase 4.6

### Problème suspecté (⚠️ INFÉRÉ, possiblement périmé)

Opus suspecte que `client.py` contient encore des `NotImplementedError`.

### B.1 — Diagnostic complet

```bash
# 1. NotImplementedError résiduels
grep -n "NotImplementedError\|raise NotImplemented" services/solana/client.py

# 2. Méthodes déclarées par le CHANGELOG Phase 4.6
grep -n "def _build_and_send_submit_tx\|def _deserialize_attestation_account\|def check_pda_exists\|def query_attestations" services/solana/client.py

# 3. Couverture tests : mock vs réel
echo "=== Tests Solana ==="
grep -c "def test_" tests/test_*solana* tests/test_*bridge* 2>/dev/null

echo "=== Références mock ==="
grep -c "MOCK\|mock_sig\|mock_mode" tests/test_*solana* tests/test_*bridge* 2>/dev/null

echo "=== Références sérialisation réelle ==="
grep -c "borsh\|serialize\|_build_and_send\|deserialize_attestation" tests/test_*solana* tests/test_*bridge* 2>/dev/null
```

### B.2 — Décision

- **0 NotImplementedError ET 4 méthodes existent** → "Bloc B : ✅ complet."
- **NotImplementedError seulement dans branches réseau** → "Bloc B : ⚠️ mock OK."
  Annoter si non fait : `# AUDIT[A10-MVP] 🟡`
- **Méthodes absentes** → "Bloc B : ❌ CHANGELOG déclaratif." Signaler SANS corriger.

Si tous les tests sont mock-only ET `_build_and_send_submit_tx()` existe →
ajouter 1-2 tests sérialisation pure (sans réseau).

---

## BLOC C — ADR-008 (vérification uniquement)

ADR-008 existe et est complet (vérifié : keypair management, signature,
restrictions, risques acceptés, références `lib.rs:124`, AUDIT `A10-021/009/008`).

```bash
cat docs/adr/ADR-008.md
# Vérifier : existe, ~40 lignes, cohérent avec config.py
```

**Ne PAS réécrire.**

---

## BLOC D — DIAGNOSTIC : annotations AUDIT obsolètes

### D.1 — Diagnostic

```bash
echo "=== pool.py A2-001 (corrigé Phase 4.2 ?) ==="
grep -n "AUDIT\[A2-001\]" database/pool.py

echo "=== pool.py A2-002 (corrigé Phase 4.2 ?) ==="
grep -n "AUDIT\[A2-002\]" database/pool.py

echo "=== session_storage §5.1 (corrigé Phase 4.1 ?) ==="
grep -n "AUDIT\[§5.1\]" services/session_storage.py

echo "=== entity_resolver §5.5 (corrigé Phase 4.3 ?) ==="
grep -n "AUDIT\[§5.5\]" services/entity_resolver.py

echo "=== relation_normalizer §5.5 (corrigé Phase 4.3 ?) ==="
grep -n "AUDIT\[§5.5\]" services/relation_normalizer.py

echo "=== Vue d'ensemble ==="
grep -rn "AUDIT\[.*🔴" --include="*.py" database/ services/ | grep -v FIXED | grep -v __pycache__ | wc -l
grep -rn "AUDIT\[.*🟡" --include="*.py" database/ services/ | grep -v FIXED | grep -v __pycache__ | wc -l
grep -rn "FIXED" --include="*.py" database/ services/ | grep AUDIT | grep -v __pycache__ | wc -l
```

### D.2 — Décision

Pour chaque annotation : regarder le code autour.
- **Si corrigé** → `# AUDIT[...] 🔴→✅ FIXED Phase 4.X: description`
- **Si déjà FIXED** → ne rien toucher
- **Si pas corrigé** → laisser l'annotation

---

## BLOC E — DIAGNOSTIC : tests property-based (hypothesis)

### E.1 — Diagnostic

```bash
pip list 2>/dev/null | grep -i hypothesis
grep -rn "hypothesis\|@given\|from hypothesis" --include="*.py" tests/
ls tests/test_*bridge* tests/test_*property* 2>/dev/null
```

### E.2 — Décision

- **Tests hypothesis existent** → ✅ Rien à faire.
- **Absents** → Installer hypothesis, ajouter 2 tests (spécifications) :
  - `∀ f ∈ [0.0, 1.0] : |u16_to_float(float_to_u16(f)) - f| < 1e-4` (ADR-001)
  - `∀ (s, p, o) : compute_claim_hash(s,p,o,"frame") déterministe, 64 hex` (ADR-006)

---

## VALIDATION FINALE

```bash
pytest tests/ --tb=short
ls docs/adr/ADR-*.md | wc -l   # Attendu : 8
head -5 ARCHITECTURE.md         # Date = 2026-02-12
```

---

## RAPPORT DE LIVRAISON

```
=== PHASE 4.7 — RAPPORT ===

BLOC 0 — Documentation
  ARCHITECTURE.md : [N points corrigés sur 7]
  Date : 2026-02-12

BLOC A — infer_architecture_family()
  Diagnostic grep étape 3 : [résultat exact]
  Verdict : ✅ / ❌ N providers corrigés
  Test ajouté : oui/non

BLOC B — client.py
  NotImplementedError : [0 / N]
  Méthodes CHANGELOG : [présentes / manquantes]
  Tests : [X total, Y mock, Z réels]
  Verdict : ✅ / ⚠️ / ❌

BLOC C — ADR-008
  Existe : ✅
  Cohérent : oui/non

BLOC D — Annotations AUDIT
  FIXED : N
  🔴 restants : N
  🟡 restants : N

BLOC E — Property-based tests
  hypothesis : présent/absent
  Tests existants : oui/non
  Action : rien / N ajoutés

Tests finaux : X passed, 0 failed, Y skipped
ADR consultés : ADR-001, ADR-005, ADR-008
```

## CE QUE CETTE PHASE NE FAIT PAS

- Pas de correctif pré-rédigé (diagnostic d'abord)
- Pas de refactoring (R6)
- Pas d'implémentation Solana si méthodes manquent
- Pas de nouveaux ADR au-delà de ADR-008
- Pas de modification de schema.sql

---

*PHASE_4_7_INSTRUCTIONS.md — EPP_Verdict v3*
*Rédigé par Claude Opus — 12 février 2026*
*v3 : §0 récupération contexte, Bloc 0 ARCHITECTURE.md, biais P8 inversé corrigé.*
