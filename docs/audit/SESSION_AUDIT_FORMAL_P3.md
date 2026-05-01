# Session Audit Formal — P3 (correction structurelle)

> Rapport de session suivant le protocole `BRIEFING_CLAUDE_CODE_P3.md`.
> Date : 2026-04-30. Auteur : Claude Code (Sonnet) sous supervision Sim + Opus.
> Format : preuves observables avant tout commentaire.

---

## TL;DR

**P3 clôturé** ✅ — les 7 critères du briefing §7 sont remplis. Build final
GREEN sur **16 jobs**, pytest conformance **26 passed**, aucune modification
Python. La couche Lean passe de **1 vrai théorème + 7 regression tests** à
**5 vrais théorèmes (4 `iff` + 1 corollaire) + 7 regression tests**. Le
biais B4 (asymétrie soundness/complétude) est fermé sur les 4 tiers ; le
biais B5 (drapeau Bool qui peut mentir) est fermé par typage strict
(`source_anchor : Option SourceAnchor`).

---

## 1. Baseline P3.0 (avant tout refactor)

```
$ wsl bash -c "cd /mnt/c/Users/simon/PROJECTS/EPP_Verdict/Formal; /home/simon/.elan/bin/lake build"
Build completed successfully (16 jobs).

$ python -m pytest tests/test_lean_conformance.py -v --tb=short
============================= 26 passed in 1.37s ==============================
```

État Lean post P1+P2 confirmé observable : 16 jobs, 26 tests verts.

---

## 2. P3.A — Refactor B5 (`source_anchor_nonzero : Bool` → `source_anchor : Option SourceAnchor`)

### 2.1 RED — preuve par grep du périmètre

```
$ rg -n "source_anchor_nonzero" Formal/Formal/
Formal/Formal/Basic.lean:45:  source_anchor_nonzero : Bool
Formal/Formal/RedTests.lean:73:      , source_anchor_nonzero := san }
Formal/Formal/RedTests.lean:79:      , source_anchor_nonzero := san } := by
Formal/Formal/RedTests.lean:104:      , source_anchor_nonzero := san }
Formal/Formal/RedTests.lean:110:      , source_anchor_nonzero := san } := by
Formal/Formal/SourceAnchor.lean:14:  | EpistemicType.deterministic => a.source_anchor_nonzero = true
Formal/Formal/SourceAnchor.lean:23:    a.source_anchor_nonzero = true := by
Formal/Formal/SourceAnchor.lean:33:    (hno : a.source_anchor_nonzero = false) :
```

8 occurrences dans 3 fichiers, conformes au plan §3.2 du briefing.

### 2.2 GREEN — extraits significatifs des modifications

**`Formal/Formal/Basic.lean`** — ajout du type `SourceAnchor` non-construible
avec un hash vide, et changement du champ d'attestation :

```lean
/-- Un SourceAnchor est un hash de source autoritaire externe non-vide
    (typiquement un SHA-256 hexadécimal côté Python/Rust).

    Le constructeur exige une preuve de non-vacuité (`h_nonempty`) :
    il est donc impossible de produire un `SourceAnchor` à partir d'une
    chaîne vide. ... -/
structure SourceAnchor where
  hash : String
  h_nonempty : hash ≠ ""

structure Attestation where
  ...
  source_anchor   : Option SourceAnchor  -- ← refactor B5 (P3.A, 2026-04-30)
```

**`Formal/Formal/SourceAnchor.lean`** — `wellFormed` adapté pour
`Option.isSome` :

```lean
def wellFormed (a : Attestation) : Prop :=
  match a.epistemic_type with
  | EpistemicType.deterministic => a.source_anchor.isSome = true
  | _ => True

theorem deterministic_requires_anchor
    (a : Attestation)
    (hwf : wellFormed a)
    (htype : a.epistemic_type = EpistemicType.deterministic) :
    a.source_anchor.isSome = true := by
  unfold wellFormed at hwf
  rw [htype] at hwf
  exact hwf

theorem deterministic_without_anchor_not_wellformed
    (a : Attestation)
    (htype : a.epistemic_type = EpistemicType.deterministic)
    (hno : a.source_anchor = none) :
    ¬ wellFormed a := by
  unfold wellFormed
  rw [htype, hno]
  simp
```

**`Formal/Formal/RedTests.lean`** — 4 occurrences `source_anchor_nonzero := san`
remplacées par `source_anchor := san` (replace_all unique), paramètre
`(san : Bool)` adapté en `(san : Option SourceAnchor)` (2 théorèmes).
Preuves `rfl` inchangées.

### 2.3 FIX — sortie observable

```
$ wsl bash -c "cd /mnt/c/Users/simon/PROJECTS/EPP_Verdict/Formal; /home/simon/.elan/bin/lake build"
✔ [2/16] Built Formal.Basic (2.8s)
✔ [4/16] Built Formal.TierBoundary (742ms)
✔ [5/16] Built Formal.SourceAnchor (719ms)
✔ [6/16] Built Formal.ClaimHash (779ms)
✔ [10/16] Built Formal.RedTests (2.8s)
✔ [12/16] Built Formal (2.6s)
✔ [14/16] Built Main (2.7s)
Build completed successfully (16 jobs).

$ rg -n "source_anchor_nonzero" Formal/
Formal/Formal/Basic.lean:50:    précédemment un `Bool` (`source_anchor_nonzero`) qui pouvait mentir
```

`source_anchor_nonzero` n'apparaît plus que dans le commentaire historique
de `Basic.lean:50` (qui décrit le refactor). Aucune utilisation dans le
code Lean actif.

```
$ python -m pytest tests/test_lean_conformance.py -v --tb=short
...
tests/test_lean_conformance.py::TestInv6DeterministicAnchorStrict::test_deterministic_without_anchor_is_rejected PASSED [100%]
============================= 26 passed in 0.32s ==============================
```

P3.A.FIX : tous les tests Python passent identiquement à la baseline.
Aucune modification de `services/esmm/attestation.py` ou
`services/solana/bridge.py` n'a été nécessaire — le refactor est
strictement Lean comme demandé §3.3.

---

## 3. P3.B — Extension `iff` sur les 4 tiers

### 3.1 RED — preuve observable du gap B4

Création du fichier temporaire `Formal/Formal/_RedTestVacuity.lean` :

```lean
import Formal.Basic

def assignTierTrivial (_ : Score) (_ : Nat) (_ : Bool) : ConfidenceTier :=
  ConfidenceTier.sandbox

theorem tier_verified_implies_conditions_vacuous
    (s : Score) (m : Nat) (a : Bool)
    (h : assignTierTrivial s m a = ConfidenceTier.verified) :
    s.val ≥ 8500 ∧ (m ≥ 3 ∨ a = true) := by
  unfold assignTierTrivial at h
  contradiction
```

Ajout temporaire de l'import dans `Formal.lean` :
`import Formal._RedTestVacuity  -- TEMPORAIRE P3.B.RED`.

```
$ wsl bash -c "cd /mnt/c/Users/simon/PROJECTS/EPP_Verdict/Formal; /home/simon/.elan/bin/lake build"
✔ [12/18] Built Formal._RedTestVacuity (2.3s)
✔ [13/18] Built Formal._RedTestVacuity:c.o (99ms)
✔ [14/18] Built Formal (2.3s)
...
Build completed successfully (18 jobs).
```

**Le théorème `tier_verified_implies_conditions_vacuous` compile en GREEN
sur une fonction qui retourne toujours `sandbox`.** C'est la preuve
matérielle que la version directionnelle `tier_verified_implies_conditions`
ne suffit pas à caractériser `assignTier`. Justifie l'extension `iff`.

### 3.2 GREEN — extraits significatifs

`Formal/Formal/TierBoundary.lean` réécrit avec 4 théorèmes `iff` + corollaire :

```lean
theorem tier_verified_iff_conditions (s : Score) (m : Nat) (a : Bool) :
    assignTier s m a = ConfidenceTier.verified ↔
    (s.val ≥ 8500 ∧ (m ≥ 3 ∨ a = true)) := by
  unfold assignTier
  constructor
  · intro h
    split at h
    · assumption
    · split at h
      · cases h
      · split at h
        · cases h
        · cases h
  · intro hA
    rw [if_pos hA]
```

Pour les 3 tiers cumulatifs (`validated`, `proposition`, `sandbox`), les
preuves utilisent `next hnA =>` / `next hB =>` etc. pour récupérer les
gardes des `split` :

```lean
theorem tier_validated_iff_conditions (s : Score) (m : Nat) (a : Bool) :
    assignTier s m a = ConfidenceTier.validated ↔
    (¬ (s.val ≥ 8500 ∧ (m ≥ 3 ∨ a = true))
     ∧ s.val ≥ 7000 ∧ m ≥ 3) := by
  unfold assignTier
  constructor
  · intro h
    split at h
    · cases h
    · next hnA =>
      split at h
      · next hB =>
        exact ⟨hnA, hB.1, hB.2⟩
      · split at h
        · cases h
        · cases h
  · intro ⟨hnA, h7, h3⟩
    rw [if_neg hnA, if_pos ⟨h7, h3⟩]
```

(Mêmes patterns pour `tier_proposition_iff_conditions` et
`tier_sandbox_iff_conditions`.)

L'ancien théorème conservé en corollaire :

```lean
theorem tier_verified_implies_conditions
    (s : Score) (m : Nat) (a : Bool)
    (h : assignTier s m a = ConfidenceTier.verified) :
    s.val ≥ 8500 ∧ (m ≥ 3 ∨ a = true) :=
  (tier_verified_iff_conditions s m a).mp h
```

Commentaire ajouté en tête de la section tier RedTests dans
`RedTests.lean` (briefing §4.4) :

```lean
/-
  Note (P3.B, 2026-04-30) : depuis l'extension `iff` sur les 4 tiers
  (TierBoundary.lean), les théorèmes universels caractérisent
  complètement `assignTier`. Les 4 RedTests ci-dessous ... restent
  utiles comme regression tests sur des inputs concrets ...
-/
```

Build avec _RedTestVacuity.lean encore présent + 4 iff + corollaire :

```
$ wsl bash -c "... lake build"
✔ [10/18] Built Formal.TierBoundary (2.3s)
✔ [12/18] Built Formal.RedTests (2.5s)
✔ [14/18] Built Formal (2.2s)
✔ [16/18] Built Main (2.4s)
Build completed successfully (18 jobs).

$ python -m pytest tests/test_lean_conformance.py -v --tb=short
============================= 26 passed in 0.23s ==============================
```

### 3.3 FIX — suppression du fichier RED

```
$ rm Formal/Formal/_RedTestVacuity.lean
$ ls Formal/Formal/
Basic.lean
ClaimHash.lean
RedTests.lean
Sanity.lean
SourceAnchor.lean
TierBoundary.lean
```

Retrait de l'import dans `Formal.lean` (suppression de la ligne
`import Formal._RedTestVacuity ...`).

### 3.4 Validation finale P3 — sortie brute

```
$ wsl bash -c "cd /mnt/c/Users/simon/PROJECTS/EPP_Verdict/Formal; /home/simon/.elan/bin/lake clean; /home/simon/.elan/bin/lake build"
✔ [2/16] Built Formal.Basic (2.7s)
✔ [3/16] Built Formal.Basic:c.o (132ms)
✔ [4/16] Built Formal.SourceAnchor (689ms)
✔ [5/16] Built Formal.TierBoundary (737ms)
✔ [6/16] Built Formal.ClaimHash (724ms)
✔ [7/16] Built Formal.TierBoundary:c.o (59ms)
✔ [8/16] Built Formal.SourceAnchor:c.o (47ms)
✔ [9/16] Built Formal.ClaimHash:c.o (86ms)
✔ [10/16] Built Formal.RedTests (2.5s)
✔ [11/16] Built Formal.RedTests:c.o (50ms)
✔ [12/16] Built Formal (2.3s)
✔ [13/16] Built Formal:c.o (56ms)
✔ [14/16] Built Main (2.3s)
✔ [15/16] Built Main:c.o (75ms)
✔ [16/16] Built formal:exe (301ms)
Build completed successfully (16 jobs).

$ python -m pytest tests/test_lean_conformance.py -v --tb=short
...
============================= 26 passed in 0.22s ==============================
```

**16 jobs (cohérent avec baseline P3.0)**, **26 tests passés**, **zéro
warning, zéro erreur**.

---

## 4. Critères de fin P3 (briefing §7) — checklist

1. ✅ `Basic.lean` contient un type `SourceAnchor` non-construible avec hash vide, et `Attestation.source_anchor : Option SourceAnchor`.
2. ✅ `SourceAnchor.lean` adapte `wellFormed` (utilise `Option.isSome = true`) et les deux théorèmes (`deterministic_requires_anchor`, `deterministic_without_anchor_not_wellformed`).
3. ✅ `TierBoundary.lean` contient 4 théorèmes `iff` (verified, validated, proposition, sandbox) + l'ancien `tier_verified_implies_conditions` en corollaire.
4. ✅ `RedTests.lean` adapte les deux constructeurs `Attestation` au nouveau type `source_anchor : Option SourceAnchor`. Preuves `rfl` toujours valides.
5. ✅ `lake clean && lake build` retourne `Build completed successfully (16 jobs)`, zéro warning. Sortie brute reportée §3.4.
6. ✅ `pytest tests/test_lean_conformance.py -v` retourne 26 tests verts. Aucune modification de `services/esmm/attestation.py` ou `services/solana/bridge.py`.
7. ✅ `_RedTestVacuity.lean` supprimé après preuve du gap (vérification par `ls Formal/Formal/`).

---

## 5. Décisions prises et leur justification

### 5.1 `Option.isSome = true` plutôt que `∃ x, source_anchor = some x`

Le briefing §3.2 propose `a.source_anchor.isSome` directement dans la
`match` du `wellFormed`. En Lean 4, `Option.isSome` retourne un `Bool`,
pas une `Prop`. Pour rester en `Prop` (cohérent avec la branche `True`
de la `match`), il fallait une coercion explicite. Trois options :

- (a) `a.source_anchor.isSome = true` — comparaison Bool, lisible, cohérente avec le pattern `= true` déjà utilisé pré-refactor.
- (b) `∃ x, a.source_anchor = some x` — pure Prop, mais introduit un quantificateur existentiel à manipuler dans les preuves.
- (c) `match a.source_anchor with | some _ => True | none => False` — explicite mais verbeux.

**Choix : (a)**, conformité avec le pattern existant et lisibilité.

### 5.2 `next hnA =>` plutôt que `rename_i hnA`

Pour récupérer la garde `¬A` créée par `split at h` sur un
`if A then ... else ...`, deux syntaxes Lean 4 :

- `next hnA => ...` — explicite, scope local, échoue si zéro hypothèse non nommée.
- `rename_i hnA; ...` — fonctionnel mais plus permissif, peut renommer accidentellement.

**Choix : `next` partout**, plus discipliné.

### 5.3 Conserver `tier_verified_implies_conditions` comme corollaire

Le briefing §4.3 insiste : *« ne pas le supprimer brutalement — il est
référencé peut-être par des commentaires de code, et un corollaire renommé
préserve la traçabilité historique »*. Implémenté via
`(tier_verified_iff_conditions s m a).mp h`. Une seule ligne, pas de
duplication de raisonnement.

### 5.4 Les 4 `iff` répètent la même formulation des conditions

J'ai conservé la formulation explicite `s.val ≥ 8500 ∧ (m ≥ 3 ∨ a = true)`
dans les 4 théorèmes plutôt qu'introduire des définitions auxiliaires
(`def cond_verified ... `). Périmètre minimal du briefing §6.1 — toute
factorisation supplémentaire est un sur-périmètre.

### 5.5 Ne pas toucher `Sanity.lean` ni les autres fichiers hors P3

`Sanity.lean` (3 `#eval`, 0 théorème, post-P1) est laissé tel quel.
`ClaimHash.lean` (avec sa NOTE GATEKEEPER P1+P2) est laissé tel quel.
Les commentaires hérités de P1+P2 sont préservés.

---

## 6. Pièges rencontrés et résolus

### 6.1 Quoting bash dans WSL

**Symptôme** : `wsl bash -c 'export PATH=$HOME/.elan/bin:$PATH && ...'`
échoue avec `bash: -c: line 1: syntax error near unexpected token '('`.

**Cause** : le PATH Windows hérité (Git, NVIDIA, etc.) contient des
chemins `/mnt/c/Program Files (x86)/...` avec des parenthèses qui sont
interprétées comme tokens de regroupement par bash.

**Résolution** : invocation directe de `lake` par chemin absolu
(`/home/simon/.elan/bin/lake`) sans modifier le PATH. La commande utile
devient `wsl bash -c "cd ...; /home/simon/.elan/bin/lake build"`.

### 6.2 Edit `replace_all=true` couvrant plus que prévu

**Symptôme** : le second Edit `source_anchor_nonzero := san } := by` →
`source_anchor := san } := by` a échoué avec `String to replace not found`.

**Cause** : le premier Edit `replace_all=true` sur
`source_anchor_nonzero := san }` → `source_anchor := san }` avait déjà
remplacé toutes les occurrences, y compris les 2 qui se terminaient par
` := by`. Le pattern recherché par le second Edit n'existait plus.

**Résolution** : vérification par `grep` que `source_anchor_nonzero` était
absent du code actif. Bénéfice imprévu : 1 Edit au lieu de 2, pas de
perte fonctionnelle.

### 6.3 Pas de mathlib disponible

Risque anticipé par briefing §6.3. Aucune tactique mathlib n'a été
nécessaire. Le core Lean 4 fournit tout ce qu'il faut : `if_pos`,
`if_neg`, `split`, `next`, `cases`, `assumption`, `contradiction`, `rw`,
`simp`. La preuve la plus complexe (`tier_sandbox_iff_conditions`)
nécessite 3 niveaux de `split at h` + 3 `next hn... =>` ; tout reste
dans le core.

---

## 7. État des invariants formels après P3

| ID | Statut Lean | Description |
|:---|:-----------|:------------|
| INV-2 (claim hash purity) | regression test | `ClaimHash.lean::claim_hash_purity` — protège la projection canonique |
| **INV-4 (verified)** | **vrai théorème `iff`** | `TierBoundary.lean::tier_verified_iff_conditions` |
| **INV-4 (validated)** | **vrai théorème `iff`** | `TierBoundary.lean::tier_validated_iff_conditions` |
| **INV-4 (proposition)** | **vrai théorème `iff`** | `TierBoundary.lean::tier_proposition_iff_conditions` |
| **INV-4 (sandbox)** | **vrai théorème `iff`** | `TierBoundary.lean::tier_sandbox_iff_conditions` |
| INV-4 (legacy) | corollaire | `tier_verified_implies_conditions` ← `iff.mp` |
| INV-6 (deterministic anchor) | tautologique mais B5 fermé | typage strict `Option SourceAnchor` |

**Compte honnête** : **5 vrais théorèmes** (4 `iff` non triviaux + 1 corollaire dérivé)
+ **7 regression tests** (1 hash purity + 4 tier red/green + 2 hash red).

---

## 8. Suggestions pour P4

Hiérarchisé par impact / coût.

### P4.1 — Property-based testing croisé Python ↔ Lean (B6) — *plus haut levier*

Identifié comme l'action décisive dans `Formal_Review_EPP.md` §5.3 et
mon audit `RESEARCH_FORMAL_AUDIT.md` §5 P4. C'est le seul travail qui
adresse réellement le décalage spec/code. Sans lui, *aucune* preuve Lean
ne dit quoi que ce soit sur le système déployé.

**Implémentation suggérée** :
- Réimplémenter en Python pur un oracle `lean_oracle_assign_tier` qui mime exactement la spec Lean.
- Avec Hypothesis, générer 10 000 triplets `(score, models, has_anchor)` aléatoires.
- Asserter l'égalité avec la fonction Python de production.
- Idem pour `claim_hash` : 10 000 inputs, vérification que le hash dépend strictement des 4 champs canoniques.

Coût estimé : 2-3 jours.

### P4.2 — Renforcement du type `SourceAnchor` (longueur/format)

Le `SourceAnchor` actuel exige seulement `hash ≠ ""`. On peut renforcer :
- `h_length : hash.length = 64` (SHA-256 hex)
- `h_charset : ∀ c ∈ hash.toList, c.isHexDigit`

Coût estimé : 1 jour. Bénéfice : invariant plus serré, mais redondant
avec validation côté Python (Pydantic).

### P4.3 — INV-7 Brier proper scoring (cas binaire)

Cf. `RESEARCH_B_lean4_inv7_brier.md` qui défend Tier 2 (et non Tier 3
comme classé dans ADR-020 §7.1) sur le cas binaire. **12-19 h estimées**,
ferme un autre invariant non trivial.

### P4.4 — Suppression du champ commentaire historique de Basic.lean

Le commentaire ligne 50 mentionne encore `source_anchor_nonzero` dans le
texte explicatif. Une fois le refactor B5 stabilisé sur quelques mois,
ce commentaire pourra être nettoyé. Hors P3-P4 immédiat.

---

## 9. Ce que P3 *ne fait pas* (et pourquoi)

- **Pas de touche à `Sanity.lean`** : hors périmètre, contient des `#eval` post-P1.
- **Pas de modification Python** : briefing §3.3 explicite — refactor strictement Lean.
- **Pas de mathlib** : briefing §6.3 explicite, le core Lean 4 a suffi.
- **Pas de nouveau ADR** : tâche d'audit, pas de décision d'architecture.
- **Pas de nouvelle dimension d'invariant** : pas d'INV-3, INV-5, INV-7, INV-8 — ces chantiers sont post-P3 (cf. §8.3).

---

*Fin du rapport.*
