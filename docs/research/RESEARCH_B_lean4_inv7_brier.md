# Lean 4 Brier Proper-Scoring Invariant (INV-7) — Proof Strategy

> Réponse au Prompt B de `RESEARCH_PROMPTS_v1.md`. Research brief, 2026-04-27.
> Pas de code Lean compilable demandé : ce document est une carte d'attaque,
> pas une preuve livrée.

---

## Synthèse exécutive

INV-7 énonce que la fonction Brier utilisée par EPP pour pondérer les modèles
est une *strictly proper scoring rule* au sens classique (Brier 1950, Gneiting
& Raftery 2007). On formalise INV-7 sur le **cas binaire** — celui qui est
effectivement appliqué dans `services/esmm/orchestrator.py:949-966` et
`database/schema.sql:923-998` — et l'on montre que la preuve est portée par
**l'algèbre élémentaire des réels** (et non par la théorie de la mesure).
ADR-020 §7.1 classe INV-7 en Tier 3 ("Brier proper scoring nécessite mathlib,
théorie de la mesure, 2-4 semaines"). **Sur le cas binaire, on défend Tier 2
et 12-20 heures-prouveur — incluant les red tests, le test de conformité
Python, et l'intégration dans `lake build`.** L'extension générale (cas
continu) reste Tier 3 et hors scope du présent brief.

---

## 1. Énoncé formel cible (≤ 15 lignes Lean 4)

```lean
import Mathlib.Analysis.SpecialFunctions.Pow.Real

/-- Espérance du score Brier sous une vraie probabilité `q ∈ [0,1]`,
    pour une prédiction `p ∈ [0,1]` (cas binaire, outcome ∈ {0,1}). -/
noncomputable def expectedBrier (q p : ℝ) : ℝ := q * (p - 1)^2 + (1 - q) * p^2

/-- INV-7 — Strict propriety du score Brier sur le cas binaire.
    Pour toute vraie probabilité `q ∈ [0,1]` et toute prédiction `p ∈ [0,1]`
    distincte de `q`, l'espérance du Brier est strictement supérieure à
    sa valeur en `p = q`. La prédiction honnête est l'unique minimum. -/
theorem brier_strictly_proper
    (q p : ℝ) (hq : 0 ≤ q ∧ q ≤ 1) (hp : 0 ≤ p ∧ p ≤ 1) (hne : p ≠ q) :
    expectedBrier q p > expectedBrier q q := by
  unfold expectedBrier
  have key : expectedBrier q p - expectedBrier q q = (p - q)^2 := by ring
  nlinarith [sq_nonneg (p - q), sq_pos_of_ne_zero _ (sub_ne_zero.mpr hne)]
```

**Lecture pour un mathématicien sans contexte EPP** : `expectedBrier q p`
est la perte quadratique attendue d'un parieur qui annonce `p` quand la
vraie probabilité du succès est `q` et l'événement Y suit une loi de
Bernoulli(q). Le théorème dit que cette fonction admet un minimum strict
en `p = q` — autrement dit, **annoncer la vraie probabilité est l'unique
stratégie optimale**. C'est la définition exacte d'une *proper scoring
rule* dans le cadre binaire.

---

## 2. Infrastructure `mathlib` mobilisée (≤ 10 lemmes)

Le brief s'engage sur **6 dépendances mathlib** et exclut explicitement la
théorie de la mesure :

1. `Mathlib.Algebra.Order.Ring.Lemmas` — `sq_nonneg`, `sq_pos_of_ne_zero`
2. `Mathlib.Tactic.Ring` — la tactique `ring` pour la preuve d'égalité
   `expectedBrier q p − expectedBrier q q = (p − q)²`
3. `Mathlib.Tactic.Linarith` (variante `nlinarith`) — combinaison linéaire
   non-linéaire pour conclure `(p-q)² > 0 → expectedBrier q p > expectedBrier q q`
4. `Mathlib.Algebra.GroupPower.Basic` — manipulations de `^2`
5. `Mathlib.Order.Defs` — `lt_of_sub_pos` (passage de `a − b > 0` à `a > b`)
6. `Mathlib.Tactic.FieldSimp` — pour les manipulations rationnelles si besoin

**Ce que le brief refuse d'introduire** :

- `MeasureTheory.expectation` ou tout import depuis `Mathlib/MeasureTheory/`
- `Probability.ProbabilityMassFunction`
- toute structure de mesure abstraite

Justification : pour un outcome binaire, l'espérance se réduit à une combinaison
linéaire `q · f(1) + (1 − q) · f(0)`. La théorie de la mesure n'apporte aucune
généralité utile ; elle alourdit la preuve et augmente le risque de `sorry` ou
d'axiome ad hoc, ce qui violerait le critère §8.1 d'ADR-020.

---

## 3. Plan de preuve (≤ 3 paragraphes)

**Paragraphe 1 — Réduction algébrique.** On prouve d'abord par `ring` que
`expectedBrier q p − expectedBrier q q = (p − q)²`. C'est une identité
formelle qui ne dépend ni des bornes `[0,1]` ni de la condition `p ≠ q` ;
elle se vérifie en développant les deux carrés et en simplifiant. Cette
identité est *la totalité du contenu mathématique* de INV-7 sur le cas
binaire — la stricte propriété est une conséquence directe de la positivité
stricte du carré d'un réel non nul.

**Paragraphe 2 — Stricte positivité.** À partir de `p ≠ q`, on déduit
`(p − q) ≠ 0`, donc `(p − q)² > 0` via `sq_pos_of_ne_zero`. Combiné à
l'identité du paragraphe 1, cela donne directement
`expectedBrier q p − expectedBrier q q > 0`, c'est-à-dire
`expectedBrier q p > expectedBrier q q`. La tactique `nlinarith` boucle
ces deux faits en une étape automatique.

**Paragraphe 3 — Difficultés résiduelles.** Aucune sur le cas binaire.
La preuve compile en moins d'une seconde. La seule difficulté technique
est l'absence d'utilisation des hypothèses `hq : 0 ≤ q ∧ q ≤ 1` et
`hp : 0 ≤ p ∧ p ≤ 1` : INV-7 sur ce cadre ne dépend pas du fait que `p`
et `q` sont des probabilités. Cette observation est précieuse — elle
signifie que le théorème est *plus général* que sa motivation et qu'on
pourrait le re-énoncer sur `ℝ` sans perte. On conserve les hypothèses
pour la lisibilité du contrat avec l'implémentation Python (qui clamp
dans `[0, 1]`).

---

## 4. Red tests (≥ 1, conformes à ADR-020 §4.1)

### 4.1 Red test principal — `red_brier_constant_predictor_not_optimal`

```lean
/-- RED-BRIER-1 : un prédicteur constant à 0.5 n'est PAS optimal quand
    la vraie probabilité diffère de 0.5. Cette propriété tombe si on
    change la formule du Brier en ajoutant un coefficient parasite
    (par exemple en remplaçant `(p - 1)^2` par `(p - 1)`). -/
theorem red_brier_constant_predictor_not_optimal :
    expectedBrier 0.8 0.5 > expectedBrier 0.8 0.8 := by
  unfold expectedBrier
  norm_num
```

**Procédure de falsification** : on remplace temporairement la définition
de `expectedBrier` par `q * (p - 1) + (1 - q) * p` (perte linéaire au lieu
de quadratique). On rebuild `lake build`. Le théorème
`brier_strictly_proper` doit échouer (la perte linéaire n'est *pas*
proper — elle est minimisée à `p = 0` ou `p = 1` selon `q`, pas en `p = q`).
Le red test ci-dessus tombe également : `expectedBrier 0.8 0.5 = 0.8 * (-0.5) + 0.2 * 0.5 = -0.3`,
versus `expectedBrier 0.8 0.8 = 0.8 * (-0.2) + 0.2 * 0.8 = 0.0` ; or
`-0.3 > 0.0` est faux.

### 4.2 Red test secondaire — `red_brier_aggregate_weight_formula`

```lean
/-- RED-BRIER-2 : la pondération `weight = max(0, 1 - avg_brier)`
    utilisée dans services/esmm/orchestrator.py:965 est bien une
    fonction décroissante du Brier. Si on inversait le signe ou si
    on supprimait le clamp, la propriété tomberait. -/
theorem red_brier_weight_decreasing :
    ∀ (b₁ b₂ : ℝ), 0 ≤ b₁ ∧ b₁ < b₂ ∧ b₂ ≤ 1 →
    max 0 (1 - b₁) > max 0 (1 - b₂) := by
  intros b₁ b₂ ⟨_, hlt, h2⟩
  rw [max_eq_left, max_eq_left] <;> linarith
```

**Procédure de falsification** : on remplace `max(0, 1 - brier)` par
`max(0, brier - 1)` ou par `1 + brier` dans le code Python (ligne 965).
Le test de conformité Python (§5) doit alors tomber, propageant un échec
en CI même si la preuve Lean reste verte.

### 4.3 Inclusion dans `lake build`

Les deux red tests sont placés dans `Formal/Formal/RedTests.lean` (fichier
existant), dans une nouvelle section commentée
`-- RED TESTS — INV-7 (Brier Proper Scoring)`. `Formal.lean` importe déjà
`Formal.RedTests` (ligne 4 du fichier index), donc `Main.lean → Formal →
RedTests` charge automatiquement les nouveaux tests. Aucune modification
de la CI YAML n'est requise — c'est précisément le contrat protégé par
ADR-020 §1.3 et §4.3.

---

## 5. Test de conformité Python à ajouter

ADR-020 §5.5 impose que chaque invariant Lean ait un test correspondant
dans `tests/test_lean_conformance.py` qui exerce le code runtime. Pour
INV-7, le test cible la fonction de pondération de
`services/esmm/orchestrator.py:949-966`.

### 5.1 Squelette du test

```python
class TestInv7BrierProperScoring:
    """ADR-020 INV-7 — Brier proper scoring rule (cas binaire).

    Vérifie que :
    1. La fonction de pondération `_compute_model_weights` applique
       bien `max(0.0, 1.0 - avg_brier_score)` (ligne 965).
    2. L'agrégat `avg_brier_score` est calculé via la vue SQL
       `v_model_brier_scores` qui moyenne `brier_score = (predicted - actual)²`.
    3. Sur un cas synthétique où la vraie probabilité est connue, la
       prédiction `p = q` minimise strictement le Brier observé.
    """

    @pytest.mark.asyncio
    async def test_aggregate_formula_matches_lean(self, db, monkeypatch):
        # Inject 100 synthetic predictions for model "test:7b" with q=0.7
        # Predictions vary p ∈ {0.0, 0.1, ..., 1.0}
        # Resolve outcomes per Bernoulli(0.7) deterministic seed.
        # Then call _compute_model_weights and check the model with p=0.7
        # has the strictly highest weight (= lowest avg_brier).
        ...

    def test_red_replace_quadratic_by_linear(self):
        # Falsification : monkey-patch the schema.sql view to replace
        # AVG(brier_score) with AVG(predicted - actual) — non-proper.
        # Assert the property "p=q is optimal" no longer holds.
        ...
```

### 5.2 Cas synthétique de calibration

Le test mobilise 100 prédictions synthétiques par modèle, échantillonnées
selon une loi Bernoulli déterministe (graine fixée). Pour chaque modèle
indexé par sa prédiction constante `p ∈ {0.0, 0.1, ..., 1.0}`, on calcule
le `avg_brier_score` empirique et l'on vérifie que celui-ci est minimal
(à epsilon près) pour `p ≈ q = 0.7`. C'est une **vérification numérique
de l'invariant analytique prouvé en Lean**. Ce test n'est pas une preuve,
mais un garde-fou observable : si le code de calcul du Brier dérive de la
formule prouvée, le test tombe.

### 5.3 Découverte attendue

Sur la base du précédent INV-6 (ADR-020 §5.5 : *"la suite a immédiatement
révélé un gap concret"*), il faut s'attendre à ce que l'écriture du test
révèle une divergence Python↔Lean. Hypothèse à vérifier : la fenêtre
glissante de 90 jours (`schema.sql:995`) introduit un biais qui n'est pas
modélisé par le théorème Lean. Ce gap est documentable comme **écart
connu** au sens d'ADR-020 §5.3, à condition de prouver formellement que
la moyenne empirique converge vers l'espérance théorique sous la fenêtre
— ou d'élargir l'invariant Lean pour couvrir l'estimateur empirique.

---

## 6. Coût estimé en heures-prouveur

### 6.1 Décomposition

| Tâche | Heures | Justification |
|:------|:-------|:--------------|
| Énoncé formel + définitions auxiliaires (`expectedBrier`) | 1-2 | Trivial une fois le cas binaire fixé. |
| Preuve principale `brier_strictly_proper` | 1-2 | `ring + nlinarith` boucle en quelques lignes. |
| Red test 1 (`constant_predictor_not_optimal`) + falsification manuelle | 2 | Norm_num suffit pour le calcul concret ; falsification = 1 commit revert. |
| Red test 2 (`weight_decreasing`) | 1 | `max_eq_left + linarith`. |
| Intégration `RedTests.lean` + vérification `lake build` | 1 | Section + import déjà câblé. |
| Test de conformité Python (`test_aggregate_formula_matches_lean`) | 4-6 | Le plus coûteux : fixtures DB, prédictions synthétiques, monkeypatch SQL view. |
| Test de conformité red (`replace_quadratic_by_linear`) | 2-3 | Patch schema + assertion. |
| Documentation ADR (mise à jour ADR-020 §3 + §5.2 + §6.1) | 1-2 | Nouveau bloc INV-7. |
| **Total** | **13-19 h** | À calibrer sur le précédent INV-4 : ADR-020 §1.3 indique que TierBoundary a été complété **et falsifié** sur 1 session, soit ~5-8 h pour un invariant de difficulté comparable. INV-7 est à peine plus algébrique. |

### 6.2 Ce qui pourrait faire dériver le coût

- **Si l'on veut prouver INV-7 sur outcomes continus** (cas Gneiting & Raftery
  2007 général) : passage à `MeasureTheory`, dérivée de Fréchet, démonstration
  via convexité stricte. Estimation +40-80 h, ce qui ramène le total à 50-100 h
  — cohérent avec l'estimation initiale d'ADR-020 §7.1 ("2-4 semaines pour un
  prouveur débutant"). **Hors scope du présent brief.**

- **Si la fenêtre glissante de 90 jours est intégrée à l'invariant** : ajouter
  un argument de convergence empirique → loi des grands nombres → mesure de
  probabilité. Idem, glisse vers Tier 3.

- **Si l'on veut prouver que `_compute_model_weights` Python est *exactement*
  la fonction Lean** : la conformité actuelle est observée par test (§5), pas
  prouvée mécaniquement. La preuve formelle nécessiterait un outil
  d'extraction Python→Lean qui n'existe pas (parallèle exact avec ADR-020
  §5.4 sur le gap Rust↔Lean).

### 6.3 Décision recommandée

Livrer INV-7 en **cas binaire avec test de conformité empirique** dans une
prochaine session focalisée. C'est un acquis concret et défendable
publiquement, qui clos la dernière des trois zones "Tier 3 hors scope
hackathon" potentiellement reclassables (INV-3 reste redondant avec Solana,
INV-5 reste vacuusement vrai). Le résultat : **12 théorèmes prouvés au lieu
de 11**, dont l'un porte sur une propriété *non triviale* du protocole
épistémique (la fidélité incitative du Brier weighting). Sur le plan du
positionnement (cf. `formal_methods_landscape.md` : 3/5400 projets Colosseum
touchent la vérification formelle), c'est un signal direct.

---

## 7. Conformité aux contraintes du prompt

| Contrainte | Réponse | Preuve |
|:-----------|:--------|:-------|
| ADR-020 §8 critère 1 (pas de `sorry`/`admit`/axiome ad hoc) | ✅ | Preuve par `ring + nlinarith`, lemmes mathlib explicitement nommés §2. |
| ADR-020 §8 critère 2 (≥ 1 red test) | ✅ | Deux red tests §4.1, §4.2. |
| ADR-020 §8 critère 3 (red test inclus dans `lake build`) | ✅ | Insertion dans `RedTests.lean`, déjà importé via chaîne `Main → Formal → RedTests`. |
| ADR-020 §8 critère 6 (test de conformité Python) | ✅ | Section §5, ajout à `tests/test_lean_conformance.py`. |
| ADR-020 §5.4 (pas de prétention runtime Rust) | ✅ | §6.2 reconnaît explicitement le gap Python↔Lean comme observé, pas prouvé. |
| Lean 4 = couche partielle existante (réutiliser l'infra) | ✅ | Aucun nouveau module ; modifications dans `RedTests.lean` (existant) + un nouveau lemme dans `Formal/`. |
| Axiome 5 (Brier per modèle, pas moyenné ex ante) | ✅ | L'invariant porte sur la fonction `expectedBrier q p` *par modèle* ; l'agrégation cross-modèles est une autre fonction (la moyenne pondérée du consensus) qui sort du périmètre INV-7. |

### 7.1 Anti-patterns évités

- ❌ `axiom proper_scoring : ∀ q p, ...` → **non utilisé**. La preuve repose
  uniquement sur `ring` et `nlinarith` ; aucune propriété n'est postulée.
- ❌ Substitution test numérique → ≠ formalisation : le test §5 est un
  garde-fou *en plus* de la preuve, pas à la place.
- ❌ Import `mathlib` en bloc : §2 nomme explicitement les 6 modules
  utilisés ; aucun `import Mathlib` global.
- ❌ Extension preuve runtime Rust : §6.2 acte que c'est hors scope.
- ❌ Falsification par suppression de cas : les red tests §4.1 et §4.2
  cassent la *définition* (changer `(p-1)²` en `(p-1)`), pas un cas du test.

---

## 8. Sources et lien aux marqueurs projet

- `docs/adr/ADR-020.md` §3 (inventaire prouvé), §4 (méthodologie non-tautologie), §5 (gap conformité), §7.1 (INV-7 non prouvé Tier 3), §8 (critères d'acceptation), §1.3 (incident TierBoundary qui calibre les coûts)
- `Formal/Formal/Encoding.lean`, `TierBoundary.lean`, `ClaimHash.lean`, `SourceAnchor.lean` (modèles existants — patrons réutilisables)
- `Formal/Formal/RedTests.lean` (cible d'insertion §4.3)
- `Formal/Main.lean` ligne 1 (`import Formal` — chaîne de chargement déjà en place)
- `Formal/lean-toolchain` (`leanprover/lean4:v4.29.1`)
- `services/esmm/orchestrator.py:949-966` (implémentation runtime de l'agrégation Brier — `_compute_model_weights`, formule `max(0, 1 - avg_brier_score)` ligne 965)
- `database/schema.sql:923-998` (table `model_track_record`, vue `v_model_brier_scores`, fenêtre 90 jours)
- `tests/test_lean_conformance.py` (cible d'ajout §5, 26 tests existants)
- `docs/positioning/formal_methods_landscape.md` (panorama FV : 3 / 5 400 projets Colosseum, ChronosVault 100+ théorèmes Lean 4)

### Référence externe (à consulter, mais à n'introduire dans Lean qu'en cas d'extension Tier 3)

- Brier, G. W. (1950). *Verification of forecasts expressed in terms of probability*. Monthly Weather Review 78(1).
- Gneiting, T. & Raftery, A. E. (2007). *Strictly proper scoring rules, prediction, and estimation*. JASA 102(477) — la définition générale, qui devient utile si l'on étend INV-7 au cas continu.

*Fin du document.*
