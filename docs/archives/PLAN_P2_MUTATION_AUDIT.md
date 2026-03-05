# PLAN P2 — AUDIT PAR MUTATION · PROTOCOLE "SELF-TORTURE" v2

> **Auteur** : Sim + Claude Opus (auditeur adversarial)
> **Date** : 17 février 2026
> **Baseline** : 553 passed, 0 failed, 11 skipped
> **Cible** : 6 fichiers critiques EPP, 18 mutations

---

## PHILOSOPHIE

"Trust, but Verify." L'erreur humaine est exclue, seule l'hallucination ou
la complaisance de l'IA est ciblée.

**RÈGLE D'OR — Phase 3** : Si un mutant survit, c'est le TEST qui est faible,
pas le code. **INTERDICTION de modifier le code source** (services/).
Seuls les tests (tests/) peuvent être créés ou modifiés.

---

## PHASE 0 : SÉCURISATION DE L'ENVIRONNEMENT

Avant de lancer quoi que ce soit, Claude Code DOIT exécuter dans cet ordre :

```bash
# 0. Hygiène git — détecter les artefacts fantômes
git ls-files --others --exclude-standard
# → Si fichiers inattendus (ex: "nul", "*.pyc", dumps) → supprimer d'abord
# Contexte : Claude Code en WSL peut créer des fichiers fantômes via des
# redirections Windows ("> nul" crée un fichier nommé "nul" en Linux).

# 1. Vérifier que le repo est propre
git status
# → Si "Changes not staged" ou "Untracked files" → ABORT

# 2. Branche isolée
git checkout -b audit-mutation-auto

# 3. Baseline verte (non-négociable)
pytest tests/ --tb=short
# → Si ≠ "553 passed, 0 failed" → ABORT

# 4. Capturer les SHA-256 de tous les fichiers cibles
sha256sum services/esmm/consensus_engine.py \
         services/solana/bridge.py \
         services/esmm/attestation.py \
         services/esmm/pipeline.py \
         services/esmm/cycle_manager.py \
         services/solana/client.py \
         > /tmp/audit_checksums.txt
```

---

## PHASE 1 : LE SCRIPT D'AUTOMATISATION (audit_runner.py)

Ne fais PAS les mutations à la main. Écris un script Python qui fait ceci
pour **chaque** définition de mutation :

### Cycle par mutation :

1. **Backup** : Lit le fichier cible en mémoire. Calcule SHA-256 du contenu.

2. **Injection** : Remplace précisément la chaîne ORIGINAL par MUTANT via
   `str.replace()` (ou regex si nécessaire). Vérifie que exactement 1
   remplacement a eu lieu (`count == 1`). Si 0 ou >1 → mutation INVALIDE,
   skip.

3. **Vérification** : Relit le fichier sur disque, confirme que MUTANT est
   présent et ORIGINAL est absent.

4. **Exécution** : Lance `pytest [fichier_test] --timeout=10 -x -q`

5. **Classification** (3 états, PAS 2) :

   | Exit code | stderr contient | Verdict | Symbole |
   |:---|:---|:---|:---|
   | 0 (tests passent) | — | **MUTANT SURVIVANT** | 🔴 FAIL |
   | ≠ 0 | `AssertionError` | **MUTANT TUÉ** | 🟢 PASS |
   | ≠ 0 | `NameError`, `SyntaxError`, `ImportError`, `TypeError` avant test | **MUTATION INVALIDE** | ⚠️ CRASH |

   > CRITIQUE : Un ⚠️ CRASH n'est PAS un 🟢 PASS. Le test n'a pas détecté
   > la mutation, c'est Python qui a crashé. Ça ne prouve rien sur la
   > robustesse du test.

6. **Restauration** : **DANS UN `try/finally`**. Écrase le fichier modifié
   avec le contenu original en mémoire. Recalcule SHA-256 et compare avec
   le backup. Si mismatch → ABORT IMMÉDIAT.

7. **Rapport** : Append le résultat dans `MUTATION_REPORT.md`.

### Sécurité post-run :

```python
# En fin de script, APRÈS toutes les mutations :
for filepath, expected_hash in checksums.items():
    actual_hash = sha256(open(filepath, 'rb').read())
    assert actual_hash == expected_hash, f"CORRUPTION: {filepath}"
print("✅ Integrity check passed — all files restored")
```

### Timeout :

Chaque exécution pytest a un timeout de **10 secondes** (certaines mutations
dans des boucles peuvent créer des boucles infinies).

---

## PHASE 2 : LISTE DES MUTATIONS

### GROUPE 1 : CONSENSUS ENGINE (consensus_engine.py)

**M1.1 — Filtre inversé (rejette les bons, garde les mauvais)**

```
Target:  if agreement_ratio < self.min_agreement:
Mutant:  if agreement_ratio > self.min_agreement:
Tests:   tests/test_r2_weighted_consensus.py
```

**M1.2 — Poids inversés (agreement↔confidence)**

```
Target:  agreement_ratio * self.agreement_weight
Mutant:  agreement_ratio * self.confidence_weight
Tests:   tests/test_r2_weighted_consensus.py
```

**M1.3 — Normalisation désactivée (bypass normalize_triplet)**

Code exact dans `_hash_triplet()` :
```python
# ORIGINAL (2 lignes) :
subject, relation, obj = normalize_triplet(raw_subject, raw_relation, raw_obj)
canonical = f"{subject}|{relation}|{obj}"

# MUTANT (remplacer la 1ère ligne) :
subject, relation, obj = raw_subject, raw_relation, raw_obj
canonical = f"{subject}|{relation}|{obj}"
```

Variables `raw_subject`, `raw_relation`, `raw_obj` existent dans le scope
(lignes précédentes de `_hash_triplet`). Mutation syntaxiquement valide. ✅

```
Tests:   tests/test_semantic_merge.py + tests/test_r2_normalize_triplet.py
```

**M1.4 — Tri ascendant (le pire résultat en premier)**

```
Target:  consensus_results.sort(key=lambda x: x.consensus_score, reverse=True)
Mutant:  consensus_results.sort(key=lambda x: x.consensus_score, reverse=False)
Tests:   tests/test_r2_weighted_consensus.py
```

**M1.5 — Écart-type forcé à zéro (controverses invisibles)**

```
Target:  std_confidence = statistics.stdev(confidences)
Mutant:  std_confidence = 0.0
Tests:   tests/test_r2_weighted_consensus.py
```

---

### GROUPE 2 : BRIDGE & SÉRIALISATION (bridge.py)

**M2.1 — Perte de précision float (round supprimé)**

```
Target:  int(round(value * SCORE_SCALE))
Mutant:  int(value * SCORE_SCALE)
Tests:   tests/test_phase1_bridge.py
```

**M2.2 — Échelle incorrecte (10000 → 1000)**

```
Target:  SCORE_SCALE = 10000
Mutant:  SCORE_SCALE = 1000
Tests:   tests/test_phase1_bridge.py + tests/test_solana_deserialize.py
```

**M2.3 — Padding inversé (ljust → rjust)**

```
Target:  encoded.ljust(max_len, b'\x00')
Mutant:  encoded.rjust(max_len, b'\x00')
Tests:   tests/test_phase1_bridge.py
```

**M2.4 — Validation taille supprimée (accepte tout)**

```
Target:  if len(raw) != 32:
Mutant:  if False:
Tests:   tests/test_phase1_bridge.py
```

Note : Ne PAS utiliser `pass` comme mutant (change l'indentation, risque
SyntaxError). Utiliser `if False:` qui est syntaxiquement valide et
désactive la validation.

---

### GROUPE 3 : ATTESTATION (attestation.py)

**M3.1 — Seuil verified dégradé (0.85 → 0.50)**

Code exact dans `derive_confidence_tier()` (version multi-paramètres) :
```
Target:  if (consensus_score >= 0.85
Mutant:  if (consensus_score >= 0.50
Tests:   tests/test_phase03_attestation.py
```

**M3.2 — Hash canonique corrompu (subject↔object inversés)**

Code exact dans `compute_claim_hash()` :
```
Target:  f"{subject}|{predicate}|{object_}"
Mutant:  f"{object_}|{predicate}|{subject}"
Tests:   tests/test_phase03_attestation.py
```

**M3.3 — Votes négatifs comptés comme positifs**

Code exact dans `crystallize()` :
```
Target:  models_agreeing = sum(1 for v in model_votes if v.agreed)
Mutant:  models_agreeing = len(model_votes)
Tests:   tests/test_phase03_attestation.py
```

---

### GROUPE 4 : PIPELINE (pipeline.py)

**M4.1 — Injection forcée (filtre de confiance désactivé)**

```
Target:  if triplet["consensus_score"] >= config.min_confidence_for_injection:
Mutant:  if True:
Tests:   tests/test_phase3_pipeline.py
```

**M4.2 — Type de retour None vs liste vide**

Chercher dans `_extract_triplets_from_question()` le `return` en cas d'erreur :
```
Target:  return [], 0, None
Mutant:  return None, 0, None
Tests:   tests/test_phase3_pipeline.py
```

Teste la robustesse du code appelant (`for triplet in extracted_triplets`
crashera sur `None`).

---

### GROUPE 5 : CYCLE MANAGER (cycle_manager.py)

**M5.1 — Amnésie du LLM (réponses vidées)**

```
Target:  responses = await self._query_models(question, cycle_type, timeout)
Mutant:  responses = []
Tests:   tests/test_phase3_orchestrator.py
```

---

### GROUPE 6 : DÉSÉRIALISEUR SOLANA (client.py)

**M6.1 — Champ last_revalidated hardcodé (bypass lecture)**

```
Target:  last_revalidated = struct.unpack("<q", data[offset:offset+8])[0]
Mutant:  last_revalidated = 0; offset += 8
Tests:   tests/test_solana_deserialize.py::test_roundtrip_serialize_deserialize
```

Note : le `offset += 8` est nécessaire pour que le reste de la
désérialisation ne soit pas décalé. Sans ça, tous les champs suivants
seraient corrompus et le test crasherait (⚠️ CRASH, pas 🟢 TUÉ).

**M6.2 — Assertion taille supprimée**

```
Target:  if offset != len(data):
Mutant:  if False:
Tests:   tests/test_solana_deserialize.py::test_deserialize_invalid_size
```

**M6.3 — Endianness inversée**

```
Target:  struct.unpack("<q", data[offset:offset+8])
Mutant:  struct.unpack(">q", data[offset:offset+8])
Tests:   tests/test_solana_deserialize.py::test_roundtrip_serialize_deserialize
```

---

## RÉCAPITULATIF DES MUTATIONS

| # | Fichier | Mutation | Cible |
|:---|:---|:---|:---|
| M1.1 | consensus_engine.py | Filtre inversé | agreement < → > |
| M1.2 | consensus_engine.py | Poids inversés | weight_a ↔ weight_c |
| M1.3 | consensus_engine.py | Normalisation bypass | normalize_triplet skip |
| M1.4 | consensus_engine.py | Tri inversé | reverse=True → False |
| M1.5 | consensus_engine.py | Stdev nulle | stdev → 0.0 |
| M2.1 | bridge.py | Round supprimé | round() retiré |
| M2.2 | bridge.py | Échelle 10x | 10000 → 1000 |
| M2.3 | bridge.py | Padding inversé | ljust → rjust |
| M2.4 | bridge.py | Validation taille off | if len != 32 → if False |
| M3.1 | attestation.py | Seuil dégradé | 0.85 → 0.50 |
| M3.2 | attestation.py | Hash inversé | subject↔object |
| M3.3 | attestation.py | Votes aveugle | sum(agreed) → len() |
| M4.1 | pipeline.py | Injection forcée | if score >= → if True |
| M4.2 | pipeline.py | Return None | return [] → return None |
| M5.1 | cycle_manager.py | Réponses vides | query_models → [] |
| M6.1 | client.py | Champ hardcodé | unpack → 0 |
| M6.2 | client.py | Validation off | offset check → if False |
| M6.3 | client.py | Endianness | little → big endian |

**Total : 18 mutations sur 6 fichiers**

---

## PHASE 3 : PROTOCOLE DE CORRECTION (BOUCLE D'INTERVENTION)

### Pour chaque 🔴 MUTANT SURVIVANT :

1. **INTERDICTION** de modifier le code source (`services/`).

2. **OBLIGATION** de créer/modifier un test dans `tests/` qui spécifie
   explicitement le comportement que le mutant a cassé.
   Exemple : "Je m'attends à ce que le premier résultat ait le score le plus
   élevé" (tue M1.4).

3. **Validation** : Relancer `audit_runner.py` UNIQUEMENT sur le mutant
   corrigé pour confirmer qu'il est maintenant 🟢 TUÉ.

4. **Non-régression** : Relancer `pytest tests/ --tb=short` complet.
   Si un nouveau test casse un test existant → REVERT et recommencer.

### Critères d'arrêt :

- **Maximum 2 itérations de correction par mutant.**
  Si un mutant survit après 2 tentatives → escalade vers Opus pour analyse.

- **Critère de succès final** :
  - 0 🔴 MUTANT SURVIVANT (les ⚠️ CRASH sont acceptables si justifiés)
  - pytest complet vert (553 + N nouveaux tests, 0 failed)

### Pour chaque ⚠️ CRASH :

Analyser manuellement. Si le crash est causé par une variable inexistante
dans le scope muté → la mutation est mal conçue, la marquer SKIP dans le
rapport. Si le crash révèle une fragilité réelle (le code ne gère pas
les types inattendus) → traiter comme un 🔴.

---

## PHASE 4 : NETTOYAGE FINAL

```bash
# 1. Supprimer le script éphémère
rm audit_runner.py

# 2. NE PAS supprimer le rapport — c'est une preuve d'audit
# MUTATION_REPORT.md reste dans le repo

# 3. Suite complète
pytest tests/ --tb=short
# → Doit afficher 553+N passed, 0 failed

# 4. Vérification intégrité fichiers source
sha256sum -c /tmp/audit_checksums.txt
# → Tous les fichiers doivent matcher (aucune mutation résiduelle)

# 5. Commit
git add tests/ MUTATION_REPORT.md
git commit -m "test: hardening via mutation audit P2 — 18 mutations, 0 survivors"

# 6. Merge
git checkout main
git merge audit-mutation-auto
git branch -d audit-mutation-auto
```

---

## LIVRABLES EXIGÉS (6 preuves)

| # | Preuve | Format |
|:---|:---|:---|
| 1 | Log baseline (553 passed, 0 failed) | Sortie pytest |
| 2 | `MUTATION_REPORT.md` complet (18 entrées) | Fichier |
| 3 | Log des corrections Phase 3 (si mutants survivants) | Sortie pytest par mutant |
| 4 | Log pytest final (553+N passed, 0 failed) | Sortie pytest |
| 5 | `sha256sum -c` — intégrité fichiers source | Sortie terminal |
| 6 | `git diff --stat` — résumé des tests ajoutés | Sortie git |

**Sans ces 6 preuves → 🔴 ROUGE rejeté.**

---

*PLAN_P2_MUTATION_AUDIT.md — EPP_Verdict*
*Sim + Claude Opus — 17 février 2026*
