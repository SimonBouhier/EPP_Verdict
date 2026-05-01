# Audit indépendant de la couche `Formal/` — Application du protocole `Formal_Review_EPP.md`

> Audit produit en suivant le protocole §7 du document de revue
> `docs/To_do_list/Formal_Review_EPP.md` (2026-04-28).
> Date du présent audit : 2026-04-30.
> Posture : revue ligne par ligne, valider ou corriger les conclusions
> de la revue d'origine, signaler les biais manqués.
>
> **Avertissement méthodologique reproduit** : cet audit n'est pas
> infaillible. Un LLM peut manquer un biais qu'il cherche, ou en inventer
> un qui n'existe pas. À considérer comme hypothèses de travail à valider,
> pas comme certification.

---

## TL;DR

Application du filtre §7 (les 6 questions) sur **9 fichiers Lean** :

- **1 vrai théorème** au sens « garantie universelle non-triviale » (`tier_verified_implies_conditions`, §B4 partiel à corriger en `iff`).
- **7 regression tests utiles** (1 sur `toClaimCore` + 4 tier red/green + 2 red hash après nettoyage B7).
- **8 énoncés à supprimer** (4 tautologies `Encoding.lean` + 1 doublon textuel `ClaimHash.lean` + 2 cycliques `SourceAnchor.lean` + 1 fichier orphelin `Formal/Basic.lean`).

**Compte honnête défendable** : **1 + 7 = 8 énoncés**, sur 16 — soit
exactement le double du chiffre que retient la revue d'origine (1 + 6 = 7).
La différence vient d'une découverte spécifique : `claim_hash_purity`
n'est pas une tautologie pure, c'est un regression test sur la définition
de `toClaimCore` (cf. §3.1 ci-après).

**Trois découvertes que la revue d'origine a manquées** sont documentées
en §4 :

1. **`Formal/Basic.lean` (racine)** — fichier orphelin contenant `def hello := "world"`, jamais importé, résiduel de `lake init`. Non listé dans l'inventaire de la revue d'origine.
2. **`claim_hash_timestamp_independent` ≡ `claim_hash_submitter_independent`** — les deux théorèmes ont **strictement le même énoncé Lean** (mêmes hypothèses `(hcore : toClaimCore a₁ = toClaimCore a₂)`, même conclusion, même preuve `unfold claimHash; rw [hcore]`). Seuls leur nom et leur commentaire diffèrent. C'est plus grave qu'un corollaire — c'est de la duplication pure.
3. **`Eval.lean` est compté dans `Formal.lean` indirectement via le fichier `Formal.lean` qui ne l'importe pas explicitement** mais Lake construit toute la lib. Il contient 3 `#eval` et **0 théorème**. Non listé dans l'inventaire §3 de la revue d'origine.

---

## 1. Méthode

J'applique strictement le protocole §7 du document de revue, à chaque
énoncé Lean :

1. Avant : *qu'est-ce que je prétends prouver ?* Si la formulation se réduit à *« la fonction f fait ce qu'elle fait »*, suspecter B1.
2. Après : *quelle preuve ?* Si `unfold; rfl` ou `unfold; rw [...]`, B1 probable.
3. *Toutes les hypothèses sont-elles consommées ?* Sinon, B7.
4. *Le théorème prouve-t-il les deux directions de l'équivalence ?* Sinon, B4.
5. *Le nom du fichier et le commentaire d'en-tête correspondent-ils au contenu réel ?* Sinon, B3.
6. *La fonction est-elle un miroir de Rust/Python ?* Si oui, B6 reste ouvert sans test différentiel.

Et le test du §1.2 : *« si je supprimais ce théorème, quelle garantie sur le système réel je perdrais ? »*

- *« aucune »* → tautologie / renommage / supprimer.
- *« j'attraperais une régression sur la définition »* → regression test, garder en l'étiquetant comme tel.
- *« je perdrais une garantie universelle non triviale »* → vrai théorème, garder et étendre.

---

## 2. Périmètre

| Fichier | Lignes | Théorèmes (count) | Statut |
|:--------|:-------|:------------------|:-------|
| `Formal/Basic.lean` (racine) | 1 | 0 | **Orphelin** (manqué par la revue) |
| `Formal/Formal.lean` (index) | 6 | 0 | OK (boilerplate) |
| `Formal/Main.lean` | 3 | 0 | OK (entry point) |
| `Formal/Formal/Basic.lean` | 47 | 0 | Types — défaut B5 sur `source_anchor_nonzero : Bool` |
| `Formal/Formal/ClaimHash.lean` | 77 | 3 | 1 utile + 1 doublon textuel + 1 corollaire |
| `Formal/Formal/Encoding.lean` | 32 | 4 | 4 tautologies / renommages — fichier mal étiqueté (B3) |
| `Formal/Formal/SourceAnchor.lean` | 39 | 2 | 2 énoncés cycliques (dépendent de B5) |
| `Formal/Formal/TierBoundary.lean` | 40 | 1 | **Seul vrai théorème** + B4 partiel |
| `Formal/Formal/RedTests.lean` | 101 | 6 | 4 tier OK + 2 hash OK après B7 |
| `Formal/Formal/Eval.lean` | 6 | 0 | **Sanity, manqué par la revue** |

**Total** : 16 théorèmes Lean (cohérent avec l'estimation "~16 énoncés"
de la revue), répartis sur 6 fichiers de modules + 3 fichiers boilerplate.

---

## 3. Inventaire ligne par ligne — validation et correction

Pour chaque énoncé, je note : `[Origine]` → `[Mon audit]` → action.
Origine = catégorie attribuée par `Formal_Review_EPP.md` §3.

### 3.1 `Formal/Formal/ClaimHash.lean`

#### `claim_hash_purity` (lignes 48-55)

**Énoncé** : `∀ a₁ a₂, (subject égal, predicate égal, object égal, frame égal) → claimHash a₁ = claimHash a₂`.
**Preuve** : `unfold claimHash toClaimCore claimHashCore; rw [hs, hp, ho, hf]`.

[Origine] → **B1 tautologie / supprimer ou rétrograder en `example`**.

[Mon audit] → **Regression test sur la définition de `toClaimCore`** : si l'on remplaçait `toClaimCore` par une projection qui inclurait `timestamp` (par erreur), le théorème serait **faux** (les 4 hypothèses ne contraignent pas le timestamp, donc `claimHash a₁ ≠ claimHash a₂` deviendrait possible). Le théorème *protège* la projection canonique.

**Test §1.2 appliqué** : *si je supprimais ce théorème, quelle garantie ?* Réponse : la garantie qu'une mutation de `toClaimCore` qui ajouterait un champ extra-canonique soit attrapée à la compilation.

**Action** : **garder, mais requalifier explicitement comme regression test** dans le commentaire (par ex. `/-- Regression test : protège la projection toClaimCore contre l'ajout silencieux d'un champ. -/`). Pas une tautologie pure ; pas non plus un théorème universel non trivial. Position intermédiaire — la revue d'origine est trop sévère.

#### `claim_hash_timestamp_independent` (lignes 61-66)

**Énoncé** : `∀ a₁ a₂, (toClaimCore a₁ = toClaimCore a₂) → claimHash a₁ = claimHash a₂`.
**Preuve** : `unfold claimHash; rw [hcore]`.

[Origine] → **B1 tautologie supprimer (corollaire de 1)**.

[Mon audit] → **Découverte manquée** : ce théorème est **strictement identique** au suivant (`claim_hash_submitter_independent`) — mêmes paramètres (`a₁ a₂ hcore`), même type, même preuve. Reproduit en annexe §A pour vérification. Ce n'est pas un corollaire au sens informel : c'est un **doublon textuel** qui passe le compilateur silencieusement parce que Lean autorise deux théorèmes au même type tant que leurs noms diffèrent.

Par ailleurs : le nom est trompeur — l'hypothèse `hcore` empêche tout cas concret où le timestamp diffère et les autres champs sont égaux, parce que `toClaimCore a₁ = toClaimCore a₂` couvre exactement les cas où les 4 champs canoniques sont égaux *et rien d'autre*. Le théorème ne dit rien de spécifique au timestamp. Le vrai théorème "timestamp-independent" est `claim_hash_purity` (qui couvre exactement ce cas en hypothèse explicite).

**Action** : **supprimer**. Le `claim_hash_purity` couvre déjà la propriété au bon niveau.

#### `claim_hash_submitter_independent` (lignes 71-76)

**Énoncé** : identique au précédent.
**Preuve** : identique.

[Origine] → **B1 tautologie supprimer (corollaire de 1)**.

[Mon audit] → **Doublon de `claim_hash_timestamp_independent`** — voir §A pour la confrontation textuelle.

**Action** : **supprimer**.

### 3.2 `Formal/Formal/Encoding.lean`

#### `score_bounded` (ligne 15)

**Énoncé** : `∀ s : Score, s.val ≤ SCORE_SCALE`.
**Preuve** : `s.h_bound`.

[Origine] → **B2 renommage / supprimer**.

[Mon audit] → **B2 confirmé**. Le terme `s.h_bound` est *littéralement* le champ de la struct `Score` — la preuve est l'identité. Une preuve par projection de champ déclare que le contrat existe ; elle ne le démontre pas.

**Action** : **supprimer**.

#### `zero_score_valid` (ligne 22)

**Énoncé** : `(mkScore 0 _).val = 0`.
**Preuve** : `rfl`.

[Origine] → **B1 tautologie supprimer**.

[Mon audit] → **B1 confirmé**. `mkScore 0 _` est *défini* comme `⟨0, _⟩`, donc `.val = 0` est vrai par l'unfolding de `mkScore`. Aucune information.

**Action** : **supprimer**.

#### `max_score_valid` (ligne 25)

**Énoncé** : `(mkScore 10000 _).val = SCORE_SCALE`.
**Preuve** : `rfl`.

[Origine] → **B1 tautologie supprimer**.

[Mon audit] → **B1 confirmé**. Même observation que ci-dessus, avec en plus le fait que `SCORE_SCALE := 10000` rend l'égalité immédiate après unfolding.

**Action** : **supprimer**.

#### `score_roundtrip_bounded` (lignes 28-30)

**Énoncé** : `∀ s : Score, s.val ≤ SCORE_SCALE ∧ 0 ≤ s.val`.
**Preuve** : `⟨s.h_bound, Nat.zero_le s.val⟩`.

[Origine] → **B1 + B3 — supprimer ou refactorer**.

[Mon audit] → **B1 + B3 confirmés et aggravés**. Le nom annonce un *roundtrip* (encode → decode → quasi-identité). Le contenu prouve seulement le bornage sup *et* la positivité — qui est triviale pour un `Nat`. **Pas de fonction `encode` ou `decode` n'est définie nulle part dans le fichier.** Le nom est une promesse mensongère.

**Test §1.2** : *si je supprimais ce théorème, quelle garantie ?* Aucune. La conjonction `s.val ≤ 10000 ∧ 0 ≤ s.val` est une reformulation triviale de `s : Score`.

**Action** : **supprimer**, ou — si l'on veut honorer le titre du fichier — **modéliser le vrai roundtrip** comme suggéré §4.2 de la revue d'origine. Avant cela : **renommer le fichier en `ScoreBound.lean`** et faire disparaître la mention "INV-1 — Encodage float↔u16" qui crée une attente non tenue (B3 sur le fichier entier).

### 3.3 `Formal/Formal/SourceAnchor.lean`

#### `deterministic_requires_anchor` (lignes 19-26)

**Énoncé** : `∀ a, wellFormed a → a.epistemic_type = deterministic → a.source_anchor_nonzero = true`.
**Preuve** : `unfold wellFormed at hwf; rw [htype] at hwf; exact hwf`.

[Origine] → **B1 tautologie supprimer ou rétrograder**.

[Mon audit] → **B1 confirmé**. La définition de `wellFormed` est *exactement* l'implication. La preuve est un unfolding direct.

**Mais** — et la revue d'origine le note via B5 — ce théorème est tautologique au sens *fort* : il prouve une implication *définie comme telle* sur un drapeau Bool qui peut mentir. La couche Python peut écrire `source_anchor_nonzero = true` sans qu'un vrai source_anchor existe en base ; Lean ne le voit pas. Le théorème *suppose* que le bool reflète la réalité, et conclut que le bool est vrai.

**Action** : **supprimer**. La vraie garantie viendra du refactor B5 (`source_anchor : Option SourceAnchor`), qui rendra l'invariant trivial *au niveau du type*. Tant que B5 n'est pas corrigé, ce théorème est **circulaire par construction**.

#### `deterministic_without_anchor_not_wellformed` (lignes 30-37)

**Énoncé** : `∀ a, a.epistemic_type = deterministic → a.source_anchor_nonzero = false → ¬ wellFormed a`.
**Preuve** : `unfold wellFormed; rw [htype]; simp [hno]`.

[Origine] → **B1 contrapositive — supprimer**.

[Mon audit] → **B1 confirmé. Contrapositive directe** du précédent. En logique classique, `P → Q` et `¬Q → ¬P` sont équivalents — Lean 4 le sait via `Classical`. Avoir les deux est une duplication.

**Action** : **supprimer**. La logique constructiviste de Lean 4 *peut* parfois nécessiter les deux directions, mais ici la preuve `simp [hno]` montre que la déduction est mécanique — pas un cas où une preuve constructive de la contrapositive ajouterait quelque chose.

### 3.4 `Formal/Formal/TierBoundary.lean`

#### `tier_verified_implies_conditions` (lignes 27-38)

**Énoncé** : `∀ s m a, assignTier s m a = verified → s.val ≥ 8500 ∧ (m ≥ 3 ∨ a = true)`.
**Preuve** : `unfold assignTier at h; split at h; · assumption; · split at h; ...`.

[Origine] → **Théorème réel + B4 partiel — garder et étendre en `iff`**.

[Mon audit] → **Confirmé**. C'est le **seul vrai théorème du corpus** : implication universelle (∀ s m a) qui ne se réduit pas à un unfolding seul, dont la preuve nécessite un raisonnement par cas (`split` + branches), et dont la suppression ferait perdre une garantie sur le comportement d'`assignTier`.

**B4 confirmé** : la direction `conditions → verified` n'est pas prouvée. Une `assignTier` qui retournerait constamment `sandbox` passerait ce théorème vacuusement. La paire de green tests (§3.5 #13, #14) compense partiellement sur 2 inputs spécifiques, mais la complétude universelle manque.

**Action** : **garder + étendre en `iff`** (cf. §4.1 de la revue d'origine). Faire de même pour les 3 autres tiers (`validated`, `proposition`, `sandbox`) — engagement formel non trivial sur `assignTier`. Coût estimé : 1-2 jours, gain élevé.

### 3.5 `Formal/Formal/RedTests.lean`

#### `red_tier_1_low_score_not_verified` (lignes 21-24)

**Énoncé** : `assignTier (⟨5000, _⟩) 5 true ≠ verified`.
**Preuve** : `unfold assignTier; simp`.

[Origine] → **Regression test — garder**.

[Mon audit] → **Regression test confirmé. B8 sur le fond** (vérification ponctuelle vs universelle), mais la revue d'origine le note implicitement et l'accepte comme rôle légitime.

**Action** : **garder**, en complément du `iff` universel proposé §4.1 de la revue (qui couvre le cas général et rend ce test redondant *en théorie*, mais utile *en pratique* comme regression).

#### `red_tier_2_no_anchor_few_models_not_verified` (lignes 28-31)

**Énoncé** : `assignTier (⟨8500, _⟩) 1 false ≠ verified`.

[Origine] → **Regression test — garder**.

[Mon audit] → **Confirmé**. Même remarque.

**Action** : **garder**.

#### `green_tier_1_high_score_many_models_verified` (lignes 36-39)

**Énoncé** : `assignTier (⟨8500, _⟩) 3 false = verified`.

[Origine] → **Regression test — garder**.

[Mon audit] → **Confirmé**.

**Action** : **garder**.

#### `green_tier_2_high_score_with_anchor_verified` (lignes 43-46)

**Énoncé** : `assignTier (⟨8500, _⟩) 1 true = verified`.

[Origine] → **Regression test — garder**.

[Mon audit] → **Confirmé**.

**Action** : **garder**.

#### `red_hash_1_timestamp_independence` (lignes 56-74)

**Énoncé** : avec `(ht_differ : t₁ ≠ t₂)`, sur deux attestations identiques sauf sur le timestamp, prouve l'égalité des hashes.
**Preuve** : `rfl`.

[Origine] → **Regression test + B7 — garder, retirer hyp inutilisée**.

[Mon audit] → **B7 confirmé** : la preuve `rfl` n'utilise jamais `ht_differ`. Le théorème est aussi vrai pour `t₁ = t₂`, ce qui est trivial. L'hypothèse est purement décorative.

Note additionnelle : la preuve `rfl` est révélatrice — elle ne déplie même pas `claimHash`. Cela signifie que *deux attestations construites avec les mêmes 4 champs canoniques (s, p, o, f) sont structurellement identiques au regard de `claimHash`*, indépendamment de tout le reste. C'est un fait définitionnel sur la projection `toClaimCore`. Ce n'est donc pas seulement un regression test sur des cas — c'est un test que la projection canonique reste correcte.

**Action** : **garder, retirer `(ht_differ : t₁ ≠ t₂)` de la signature**, reformuler le commentaire en *"le hash est totalement indépendant du timestamp, y compris (par implication) lorsqu'ils diffèrent"*.

#### `red_hash_2_submitter_independence` (lignes 81-100)

**Énoncé** : analogue avec submitter.

[Origine] → **Regression test + B7 — garder, retirer hyp inutilisée**.

[Mon audit] → **B7 confirmé**, même remarque que ci-dessus.

**Action** : **garder, retirer `(hs_differ : sub₁ ≠ sub₂)` de la signature**.

### 3.6 Fichiers non listés dans l'inventaire §3 de la revue

#### `Formal/Basic.lean` (racine)

```lean
def hello := "world"
```

[Origine] → **Non mentionné**.

[Mon audit] → **Fichier orphelin**. Vérification : `Formal.lean` (le module index) importe `Formal.Basic`, ce qui pointe vers `Formal/Formal/Basic.lean` (le fichier riche). Le fichier `Formal/Basic.lean` au niveau racine n'est référencé nulle part. Il est résiduel d'un boilerplate `lake init`.

**Risque** : un contributeur futur peut confondre les deux fichiers `Basic.lean` et éditer le mauvais. Le compilateur ne signalera rien (le fichier racine est ignoré par le module).

**Action** : **supprimer** `Formal/Basic.lean`.

#### `Formal/Formal/Eval.lean`

```lean
import Formal.Basic
import Formal.TierBoundary

#eval assignTier (⟨5000, by omega⟩ : Score) 5 true
#eval assignTier (⟨9000, by omega⟩ : Score) 1 false
#eval assignTier (⟨9000, by omega⟩ : Score) 3 false
```

[Origine] → **Non mentionné** (la revue propose à §4.5 de "garder uniquement comme fichier de sanity check explicitement nommé `Examples.lean` ou `Sanity.lean`", mais ne l'inclut pas dans l'inventaire §3).

[Mon audit] → **Sanity check, 0 théorème**. Le fichier exécute 3 appels à `assignTier` et imprime le résultat à la compilation. Utile pour vérifier visuellement que la fonction a le bon comportement, mais sans valeur formelle.

**Risque** : compté implicitement dans "11 théorèmes prouvés" si l'on regarde la liste des fichiers dans `Formal/Formal/`.

**Action** : **renommer en `Sanity.lean`** ou **déplacer hors de la lib formelle** (vers un répertoire `examples/` séparé). Documenter explicitement qu'il ne contribue pas au compte des théorèmes.

### 3.7 `Formal/Formal/Basic.lean` — types de base

Pas de théorème, mais le défaut B5 (`source_anchor_nonzero : Bool`) est un **défaut structurel du modèle** qui rend cycliques les théorèmes de SourceAnchor.lean.

[Origine] → identifie correctement B5 dans la taxonomie §2 et propose le fix §4.3.

[Mon audit] → **B5 confirmé**. Sans ce fix, INV-6 reste circulaire.

**Action** : **prioriser le refactor §4.3** (`source_anchor : Option SourceAnchor` avec constructeur exigeant non-vacuité). Une fois ce refactor fait, les énoncés `deterministic_requires_anchor` et `deterministic_without_anchor_not_wellformed` deviennent vraiment tautologiques *au sens fort* (la propriété est garantie par le type) — et peuvent alors être supprimés sans perte.

---

## 4. Désaccords et découvertes vis-à-vis de la revue d'origine

### 4.1 `claim_hash_purity` : pas une simple tautologie

La revue d'origine classe ce théorème en B1 et propose de le supprimer ou
de le rétrograder en `example`. Mon audit le requalifie en **regression
test sur la définition de `toClaimCore`** — la suppression ferait perdre
une garantie qu'une modification accidentelle de la projection canonique
soit attrapée à la compilation.

**Désaccord** : la revue est trop sévère pour cet énoncé. La position
"supprimer" n'est défendable que si l'on retire aussi la responsabilité
de protéger la projection canonique — or c'est précisément ce qui rend
INV-2 critique pour ADR-017 (cross-cluster comparability). Position
intermédiaire : **garder + commenter explicitement comme regression test**.

### 4.2 `claim_hash_timestamp_independent` ≡ `claim_hash_submitter_independent` : doublon textuel

La revue classe les deux comme "corollaires de #1" et propose la
suppression de chacun individuellement. Mon audit montre que les deux
théorèmes sont **strictement identiques au sens Lean** (mêmes paramètres,
mêmes types, même preuve). Cf. annexe §A.

**Découverte** : ce n'est pas un simple corollaire dupliqué — c'est un
doublon qui passe silencieusement la compilation. Lean 4 autorise N
théorèmes du même type tant que leurs noms diffèrent. Cela permet une
**inflation décorative du compte** : un seul théorème compte pour deux.

**Action** : supprimer **les deux** (et garder seulement
`claim_hash_purity`, qui exprime la propriété au bon niveau d'abstraction).

### 4.3 `Formal/Basic.lean` racine : fichier orphelin manqué

La revue d'origine ne le mentionne pas. C'est un point d'hygiène mineur
(une ligne de boilerplate non utilisée) mais un signal que la revue
d'origine s'est concentrée sur l'inventaire des théorèmes sans auditer
l'arborescence physique de `Formal/`.

**Action** : supprimer.

### 4.4 `Eval.lean` : fichier sanity manqué dans l'inventaire

La revue mentionne `Eval.lean` en §4.5 ("garder uniquement comme fichier
de sanity check") mais ne l'inclut pas dans le tableau d'inventaire §3.
Pour un compte rigoureux de "ce qui est dans la lib", il faut le lister.

**Action** : le lister explicitement et le **renommer**. Documenter qu'il
ne contribue pas au compte des théorèmes.

### 4.5 Calcul honnête du compte — divergence finale

| Catégorie | Revue d'origine | Mon audit |
|:----------|:----------------|:----------|
| Vrai théorème | 1 | 1 |
| Regression tests utiles | 6 | **7** (inclut `claim_hash_purity`) |
| Énoncés à supprimer | ~9 | **8** (inclut le doublon textuel) |
| **Total** | **16** | **16** |
| **Fichiers inspectés** | 6 (modules) | **9** (modules + boilerplate) |

L'écart d'1 unité tient au reclassement de `claim_hash_purity` (de
"supprimer" à "garder en regression test"). Ce reclassement est
défendable parce que le test §1.2 produit la réponse *« j'attraperais
une régression sur `toClaimCore` »* — qui est la définition opérationnelle
d'un regression test selon la revue elle-même.

---

## 5. Plan d'action priorisé

Par ordre de coût croissant et bénéfice décroissant.

### Priorité 1 — Hygiène, coût négligeable

1. **Supprimer `Formal/Basic.lean` (racine)** — fichier orphelin. Aucun import à mettre à jour.
2. **Supprimer `claim_hash_timestamp_independent`** ou **`claim_hash_submitter_independent`** (doublon textuel — un seul des deux est nécessaire ; pour la cohérence avec le RedTests, garder la version qui pointe vers `red_hash_1`/`red_hash_2`, mais ces RedTests ne dépendent pas du théorème via import direct).
3. **Renommer `Eval.lean` en `Sanity.lean`** et le retirer de la lib (ou le déclarer hors périmètre formel).

### Priorité 2 — Nettoyage des tautologies, coût faible

4. **Supprimer les 4 énoncés tautologiques de `Encoding.lean`** (`score_bounded`, `zero_score_valid`, `max_score_valid`, `score_roundtrip_bounded`).
5. **Renommer `Encoding.lean` en `ScoreBound.lean`** (B3) et faire disparaître la mention "INV-1 — Encodage float↔u16" qui crée une attente non tenue.
6. **Retirer les hypothèses fantômes** `(ht_differ : t₁ ≠ t₂)` et `(hs_differ : sub₁ ≠ sub₂)` des deux red hash tests (B7).
7. **Documenter `claim_hash_purity` comme regression test** dans son commentaire (et non comme théorème universel).

### Priorité 3 — Correction structurelle, coût moyen

8. **Refactor B5** : remplacer `source_anchor_nonzero : Bool` par `source_anchor : Option SourceAnchor` dans `Basic.lean`, avec un type `SourceAnchor` non-construible avec un hash vide. Conséquence : les deux théorèmes de `SourceAnchor.lean` deviennent triviaux *au niveau du type*, et peuvent être supprimés sans perte.
9. **Étendre `tier_verified_implies_conditions` en `tier_verified_iff_conditions`** (B4). Coût : 1-2 jours.
10. **Faire le pendant pour `validated`, `proposition`, `sandbox`**. Coût : 1 jour additionnel. Gain : 4 vrais théorèmes au lieu d'1.

### Priorité 4 — Élargissement formel, coût élevé

11. **Modéliser le vrai round-trip d'encodage** (en `Rat` plutôt qu'en `Float` pour éviter IEEE 754). Cf. §4.2 et §5.2 de la revue d'origine. Coût : 2-3 jours.
12. **Property-based testing croisé Python ↔ Lean** sur `assignTier` et `claim_hash`. Cf. §5.3 de la revue d'origine. Coût : 2-3 jours. **Gain le plus élevé** : c'est la seule action qui adresse réellement B6 (décalage spec/code).
13. **INV-3 PDA uniqueness** ou **INV-7 Brier proper scoring** (cf. réponse au Prompt B `RESEARCH_B_lean4_inv7_brier.md`). Coût : 13-19h pour INV-7 sur le cas binaire.

### Priorité 5 — Communication

14. **Réviser le discours public** selon §6.1-§6.2 de la revue d'origine. Suppression de "11 théorèmes prouvés" au profit d'une formulation honnête qui mentionne les regression tests, le test différentiel empirique, et la limite spec/code.
15. **Considérer la transformation de la méthodologie en livrable explicite** (§6.3 de la revue d'origine) — l'auteur a documenté un protocole de stress-test adversarial qui mérite un ADR ou un papier court.

---

## 6. Risque de l'auditeur

Cet audit est lui-même produit par un LLM (Claude). Les biais qu'il
cherche (B1-B8) sont les biais que le document d'origine identifie. Il
est *probable* que d'autres biais existent dans `Formal/` que ce
protocole ne détecte pas — par exemple :

- **B9 hypothétique — Type fantôme** : un type Lean qui ne correspond à *aucune* structure côté Python/Rust. Test de détection : pour chaque struct dans `Basic.lean`, vérifier qu'elle a un homologue en Python ou Rust avec correspondance champ-à-champ. Non couvert ici.
- **B10 hypothétique — Importation morte** : un fichier `Formal/X.lean` importé par `Formal.lean` mais dont aucun théorème n'est référencé par les autres modules ni par les RedTests. Détectable par grep cross-module.

Le présent audit ne traite pas ces biais. Il s'appuie sur la taxonomie
B1-B8 fournie par la revue d'origine. Élargir la taxonomie est un
exercice futur.

**Bilan honnête** : cet audit valide la conclusion de la revue d'origine
à ~95% (1 désaccord substantiel sur `claim_hash_purity`, 3 découvertes
manquées de portée limitée). La revue d'origine reste la source
canonique ; le présent document affine la marge sur 4 énoncés (#1, #2,
#3, le fichier orphelin, et `Eval.lean`).

---

## Annexe A — Confrontation textuelle des deux théorèmes "indépendance"

Extrait littéral de `Formal/Formal/ClaimHash.lean`, lignes 61-66 :

```lean
theorem claim_hash_timestamp_independent
    (a₁ a₂ : Attestation)
    (hcore : toClaimCore a₁ = toClaimCore a₂) :
    claimHash a₁ = claimHash a₂ := by
  unfold claimHash
  rw [hcore]
```

Extrait littéral de `Formal/Formal/ClaimHash.lean`, lignes 71-76 :

```lean
theorem claim_hash_submitter_independent
    (a₁ a₂ : Attestation)
    (hcore : toClaimCore a₁ = toClaimCore a₂) :
    claimHash a₁ = claimHash a₂ := by
  unfold claimHash
  rw [hcore]
```

Différences :

- ligne 1 : `claim_hash_timestamp_independent` vs `claim_hash_submitter_independent` — **nom**.
- corps de la preuve : **identique**.
- signature : **identique** (paramètres, hypothèses, conclusion).

Conséquence : Lean 4 compile les deux comme deux *labels* distincts pour
**la même proposition prouvée**. Aucun outil natif Lean ne signale ce
doublon (ni `lake build`, ni l'IDE). Détection : revue humaine ou outil
externe (par ex. parser AST + diff sur les paires `(signature, preuve)`).

---

## Annexe B — Application du test §1.2 sur les 16 énoncés

Tableau récapitulatif. Colonne "garantie perdue" = réponse à la question
*« si je supprimais ce théorème, quelle garantie sur le système réel je
perdrais ? »*.

| # | Énoncé | Garantie perdue | Catégorie §1.2 |
|---|--------|-----------------|----------------|
| 1 | `claim_hash_purity` | Détection régression sur `toClaimCore` | Regression test |
| 2 | `claim_hash_timestamp_independent` | aucune (doublon de #3) | Tautologie |
| 3 | `claim_hash_submitter_independent` | aucune (doublon de #2) | Tautologie |
| 4 | `score_bounded` | aucune (champ déclaré) | Renommage |
| 5 | `zero_score_valid` | aucune (`rfl` trivial) | Tautologie |
| 6 | `max_score_valid` | aucune (`rfl` trivial) | Tautologie |
| 7 | `score_roundtrip_bounded` | aucune (conjonction triviale, sans `Float`) | Tautologie + B3 |
| 8 | `tier_verified_implies_conditions` | Garantie universelle non-triviale | **Vrai théorème** |
| 9 | `deterministic_requires_anchor` | aucune (def de `wellFormed`, B5) | Tautologie |
| 10 | `deterministic_without_anchor_not_wellformed` | aucune (contrapositive de #9) | Tautologie |
| 11 | `red_tier_1_low_score_not_verified` | Détection régression sur input précis | Regression test |
| 12 | `red_tier_2_no_anchor_few_models_not_verified` | Détection régression sur input précis | Regression test |
| 13 | `green_tier_1_high_score_many_models_verified` | Détection régression sur input précis | Regression test |
| 14 | `green_tier_2_high_score_with_anchor_verified` | Détection régression sur input précis | Regression test |
| 15 | `red_hash_1_timestamp_independence` | Détection régression sur projection canonique | Regression test (B7 à corriger) |
| 16 | `red_hash_2_submitter_independence` | Détection régression sur projection canonique | Regression test (B7 à corriger) |

**Total** :
- Vrais théorèmes : 1 (#8)
- Regression tests : 7 (#1, #11, #12, #13, #14, #15, #16)
- À supprimer : 8 (#2, #3, #4, #5, #6, #7, #9, #10)

*Fin du document.*
