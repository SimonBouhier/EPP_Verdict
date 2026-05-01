# Research Prompts v1 — Extension EPP

> Trois prompts d'extension de recherche, chacun autonome et ancré sur un
> marqueur précis du repo. Produit selon `META_PROMPT_pour_Claude_Code.md`,
> 2026-04-27, sur la baseline 20 ADRs / 11 théorèmes Lean prouvés / 12
> attestations on-chain devnet.

---

## 1. Cartographie

### Axiomes durs (non négociables — `PITCH.md` §"Five Axioms" + WHITEPAPER §"Five Founding Axioms")

- **A1 — Model Obsolescence** : modèles = consommables, pas infrastructure.
- **A2 — Metrological Sovereignty** : chaque attestation déclare son frame ; pas de frame, pas de comparaison.
- **A3 — Regression Cut Transparency** : toute coupure méthodologique est versionnée ; les attestations produites sous frames différents sont *explicitement non comparables*.
- **A4 — Local Computation, On-Chain Proof** : l'IA tourne localement ; seule la preuve cryptographique part on-chain.
- **A5 — Divergence is the Signal** : le désaccord entre familles de modèles est plus précieux qu'un verdict unanime ; uniformité = mode de défaillance.

### Décisions tranchées (ADRs actifs)

- ADR-001 — Encodage float→u16 [0, 10000], `SCORE_SCALE=10000` [tranché]
- ADR-002 — 4 tiers de confiance (sandbox/proposition/validated/verified) [tranché]
- ADR-003 — Un seul run ESMM (Epistemic Structured Multi-Model) actif par question [tranché]
- ADR-004 — `INSERT OR IGNORE` sur la table concepts [tranché]
- ADR-005 — Tiers multi-critères (0.40 / 0.70 / 0.85) [tranché]
- ADR-006 — `claim_hash = SHA-256(subject + predicate + object + frame)` [tranché, INV-2 prouvé Lean]
- ADR-007 — Attestations append-only [tranché]
- ADR-008 — Authentification submitter Solana, devnet-only [tranché]
- ADR-009 — Neutralité linguistique (avec `COMMUNITY_DECISION_REQUIRED` sur traitement triplets contestés)
- ADR-010 — Traçabilité méthodologique (`consensus_meta`) [tranché]
- ADR-011-v2 — Semantic Fingerprinting [tranché, 4 questions ouvertes Q1-Q4]
- ADR-012 — Bifurcation déterministe / épistémique [tranché, 3 questions ouvertes]
- ADR-013 — Cache-hit épistémique pré-ESMM [appliqué]
- ADR-014 — Audit smart contracts épistémique [tranché, 5 questions ouvertes]
- ADR-016 — Oracle géopolitique ACLED [tranché]
- ADR-018 — Flywheel épistémique [appliqué]
- ADR-019 — Projection Enum V2 on-chain (3 catégories : empirical / deterministic / assessed) [tranché]
- ADR-020 — Architecture Dual-Trust Lean 4, 11 théorèmes prouvés (INV-1, INV-2, INV-4, INV-6) [appliqué, 4 invariants ouverts §7.1]

### Décisions reportées (Phase 3 / `COMMUNITY_DECISION_REQUIRED` / FAQ ouvertes)

- **ADR-009** : traitement des triplets `ambiguity_detected=True` (information vs blocage) — `COMMUNITY_DECISION_REQUIRED`
- **ADR-011-v2 §3 Q1-Q4** : injection des micro-graphes dans le graphe principal ; granularité sous-nœuds ; seuils adaptatifs ; rétroaction du graphe existant
- **ADR-012 Questions ouvertes Q1-Q3** : frais différenciés / vecteur de paiement ; intégrité du `raw_response` avant hash (TEE / ZKP) ; durée de validité on-chain et mécanisme de revalidation
- **ADR-014 §8 Q1-Q5** : agrégation contrat-level ; granularité on-chain ; diff-audit ; interaction Slither/ESMM ; extension hors sécurité
- **ADR-015** (différé post-hackathon) : Grand Découplage Kernel / Adapters / Domains
- **ADR-017 §2.5** : poids de la formule `ClusterReputationScore` (0.30/0.20/0.15/0.15/0.10/0.10) — `COMMUNITY_DECISION_REQUIRED`
- **ADR-017 §5.4** : modèles de monétisation (abonnement / pay-per-query / staking / grant) — `COMMUNITY_DECISION_REQUIRED`
- **ADR-017 §8 Q1-Q6** : token de réputation rejeté ; calibration nouveau cluster ; compétition vs coopération ; choix consommateur ; lien Axiome 5 ; METADATACHANNEL
- **ADR-017 Phase 3** : DAO governance, TEE / ZKP des manifestes, staking avec slashing
- **ADR-019 Q1-Q3** : enforcement on-chain des invariants inter-champs ; subdivision `assessed_*` future ; helper `epistemic_type_to_u8` mort
- **ADR-020 §7.1** : INV-3 (PDA uniqueness — redondant avec Solana), INV-5 (regression cut isolation — vacuusement vrai), **INV-7 (Brier proper scoring) Tier 3**, INV-8 (consensus convergence) Tier 3 — non prouvés
- **Code Python** : `services/esmm/consensus_engine.py:207`, `services/esmm/pipeline.py:574`, `services/esmm/post_crystallization.py:55` — traitement de la consensus CONTESTED (cap tier ? réduire diversity_bonus ? cycles supplémentaires ?)

### Negative space déclaré

- **`docs/positioning/the_negative_space.md`** : programme conceptuel "le modèle qui s'entraîne sur la négative" — un dataset entraînable issu de la *topologie du désaccord*, distinct des benchmarks centralisés (MMLU, HellaSwag) qui se gament et stagnent. Pas de méthodologie publiée pour le construire.
- **ADR-020 §5.4 + §7.2** : gap Rust↔Lean non comblé (aucun outil d'extraction Rust→Lean stable en avril 2026) ; absence de panic et overflow Rust non prouvés ; cohérence inter-frames enforced par design mais non prouvée.
- **ADR-017 §5.1** : vérification que les modèles déclarés dans le `ClusterManifest` correspondent aux modèles effectivement exécutés — chantier Phase 3 (TEE / ZKP), explicitement déféré.

> Note : `LEAN4_RESEARCH_BRIEF.md` (cité par ADR-020 §1.2) n'existe pas comme
> fichier dans le repo à la date courante ; ses pièges et tiers de difficulté
> sont conservés dans ADR-020 §1.2 et §7.1, qui sont les sources canoniques
> grep-ables.

---

## 2. Axes retenus

- **Axe A — Réputation cluster calculable, anti-Sybil et anti-collusion sans tokenisation** — marqueur projet : `COMMUNITY_DECISION_REQUIRED` sur les 6 poids ADR-017 §2.5 ; FAQ §8 Q1 (token rejeté) ; risques §6.
- **Axe B — Preuve Lean 4 d'INV-7 (Brier proper scoring)** — marqueur projet : ADR-020 §7.1 (INV-7 explicitement non prouvé, classé Tier 3) ; §8 critères d'acceptation futurs.
- **Axe C — Méthodologie de construction du "dataset de la négative"** — marqueur projet : `docs/positioning/the_negative_space.md` (programme "le modèle qui s'entraîne sur la négative") ; ADR-018 §2.5 (traçabilité flywheel rendant l'extraction tractable).

## 3. Axes rejetés

- **Token de réputation transférable / délégable** — *axiome violé* : ADR-017 §8 Q1 ferme le sujet (« la réputation dans EPP est un *calcul*, pas un actif. Elle ne se transfère pas, ne se trade pas, ne se délègue pas »).
- **Marché de paris ou prediction market adossé aux verdicts EPP** — *axiome violé* : règle dure du méta-prompt (« pas de spéculation financière dans la couche épistémique. Le staking sur la qualité méthodologique reste possible — mais pas un marché de paris adossé aux verdicts »). Aussi proche d'Epistemia (cf. EPP_Pitch_Vision_v3 §"closest conceptual neighbor").
- **Refonte de la formule `claim_hash`** — *déjà tranché* : ADR-006 (immuable) + INV-2 prouvé Lean (théorèmes `claim_hash_purity`, `claim_hash_timestamp_independent`, `claim_hash_submitter_independent`) ; toute modification casserait le chaînage `previous_hash` et l'identité on-chain des claims existants.

---

## 4. Prompt A

# Cluster Reputation: Sybil & Collusion Resistance Without Tokenization

## Contexte EPP nécessaire

EPP est un oracle épistémique sur Solana où chaque "Cluster" (instance opérée
par une keypair Solana) produit des attestations on-chain sous PDA (Program
Derived Address). Identité d'un cluster = `submitter: Pubkey`. PDA seed =
`[b"attestation", submitter, claim_hash]` → deux clusters attestant le même
claim produisent deux PDAs distincts. ADR-017 §2.5 propose un
`ClusterReputationScore` calculable à partir des PDAs (formule pondérée :
0.30 accuracy + 0.20 concordance déterministe + 0.15 survival_rate + 0.15
diversity + 0.10 log_volume + 0.10 age, poids ouverts à la communauté). Le
protocole interdit la tokenisation de cette réputation (§8 Q1). Cross-cluster
query déjà supportée via `getProgramAccounts` + memcmp filter `claim_hash` à
offset 41 (`services/solana/client.py::CLAIM_HASH_OFFSET`).

## Question de recherche

Comment concevoir un algorithme de calcul de réputation cluster, **purement
déterministe à partir de l'état on-chain**, qui reste robuste sous attaque
Sybil (clusters fantômes corrélés) et collusion (clusters partageant
configuration ou résultats), **sans introduire ni token, ni stockage on-chain
de la réputation, ni oracle de réputation tiers** ?

## Contraintes dures (axiomes et décisions du projet)

- **Axiome 5 (Divergence is the Signal)** : la divergence inter-cluster est un signal, pas un défaut à éliminer.
- **ADR-017 §8 Q1** : la réputation est un calcul, jamais un actif. Pas de transfert, pas de délégation.
- **ADR-017 §5.3** : la réputation reste calculable hors-chaîne par tout observateur. Pas de stockage on-chain (sinon on ré-introduit l'oracle de réputation qu'EPP résout).
- **ADR-008** : un keypair = un submitter, aucune délégation.
- **ADR-007** : attestations append-only — pas de slashing rétroactif des PDAs existantes.

## Anti-patterns (ce que la réponse ne doit pas être)

- Token ERC-20-like représentant la réputation → **viole ADR-017 §8 Q1**.
- Reputation indexer privilégié dont les snapshots font foi → **viole ADR-017 §5.3**.
- Slashing automatique on-chain de "mauvaises" attestations → **viole ADR-007** (append-only).
- Filtre anti-Sybil basé uniquement sur "âge minimum" → trivialement contournable par un acteur patient.
- Composante calculée à partir d'un signal off-chain non vérifiable → introduit une couche de confiance externe, contredit Axiome 4.

## Critères de succès

Une proposition est recevable si elle :

- Exprime l'algorithme comme une fonction pure `f: (List[PDA], List[ClusterManifest]) → ℝ` reproductible bit-à-bit par deux observateurs disposant du même état on-chain.
- Identifie **≥ 3 vecteurs Sybil distincts** (ex. clones de manifeste, copie de verdicts d'un peer, partage de keypair via outsourcing) avec, pour chacun, une métrique de détection et sa borne d'efficacité argumentée.
- Traite **≥ 2 cas de collusion** (verdicts coordonnés ; même set de modèles déclarés) et démontre comment le score les pénalise sans connaissance hors-chaîne.
- Calibre les **6 poids §2.5** sur des données mesurables (Brier scores des scénarios attestés `demos/benchmark_runs/`, distribution observée du `vote_entropy`).
- Garantit qu'aucune composante ne devient triviale si on retire le `claim_hash` ou le `frame_hash` de l'entrée.

## Livrable attendu

Un design document de **8 à 14 pages** structuré : (1) modèle d'attaque Sybil
+ collusion ; (2) algorithme proposé avec pseudo-code ≤ 60 lignes ;
(3) calibration des 6 poids avec scénario de test sur ≥ 50 attestations
synthétiques ; (4) limites connues et chantiers reportés à la couche TEE
Phase 3 ; (5) annexe : critères pour ajouter ou retirer une dimension de
la formule de réputation.

## Sources canoniques (à consulter avant de répondre)

- ADR-017 §2.5 (formule), §5.3 (calcul off-chain), §6 (risques Sybil), §8 Q1-Q2 (FAQ)
- ADR-008 (un keypair = un submitter, pas de délégation)
- ADR-007 (append-only — pas de slashing rétroactif)
- `services/esmm/response_deduplicator.py` (déduplication intra-cluster, embedding cosine ≥ 0.95)
- `services/solana/client.py` (`CLAIM_HASH_OFFSET = 41`, query cross-cluster)
- `programs/epp/src/state.rs` (layout PDA 462 bytes, `submitter: Pubkey`)

---

## 5. Prompt B

# Lean 4 Brier Proper-Scoring Invariant (INV-7) — Proof Strategy

## Contexte EPP nécessaire

ADR-020 (Architecture Dual-Trust) maintient une couche Lean 4 où **11 théorèmes
sont prouvés** sur le protocole abstrait (INV-1 encoding float↔u16, INV-2
claim hash purity, INV-4 tier boundary, INV-6 source anchor). Quatre invariants
restent **explicitement non prouvés** (§7.1) : INV-3 (PDA uniqueness — garanti
par Solana, preuve serait redondante), INV-5 (regression cut isolation —
vacuusement vrai), **INV-7 (Brier proper scoring)** et INV-8 (consensus
convergence). INV-7 énonce que l'agrégateur Brier d'EPP (utilisé dans
`services/esmm/post_crystallization.py` pour les transitions de tier) est une
*proper scoring rule* au sens strict (Gneiting & Raftery 2007) :
mathématiquement bien défini, formalisable via `mathlib` (théorie de la
mesure), estimé "Tier 3, 2-4 semaines pour un prouveur débutant". Le gap
Rust↔Lean reste documenté §5.4 — aucun outil d'extraction Rust→Lean n'est
mature en avril 2026.

## Question de recherche

Quelle formulation Lean 4 minimale (énoncé + axiomes `mathlib` mobilisés +
structure de la preuve) permet de prouver que l'agrégateur Brier d'EPP est
une proper scoring rule au sens strict, **sans dépendre d'une extraction
Rust→Lean inexistante** et **sans introduire `sorry`/`admit`/axiome ad hoc** ?

## Contraintes dures (axiomes et décisions du projet)

- **ADR-020 §8** (critères d'acceptation) : pas de `sorry`/`admit`/axiome ad hoc ; ≥ 1 red test inclus dans `lake build` via import depuis `Formal.lean` ; test de conformité ajouté à `tests/test_lean_conformance.py`.
- **ADR-020 §5.4** : pas de prétention que la preuve s'étende mécaniquement au runtime Rust. Le test de conformité Python est le seul pont accepté.
- **Lean 4 = couche partielle existante** : version `leanprover/lean4:v4.29.1`, build CI via `leanprover/lean-action@v1`, 4 modules dans `Formal/Formal/`, 18 jobs compilés. Réutiliser l'infrastructure, ne pas la réinventer.
- **Axiome 5** : le Brier score est appliqué *par modèle* — la formalisation doit préserver la diversité comme variable, pas la moyenner ex ante.

## Anti-patterns (ce que la réponse ne doit pas être)

- Affirmer "Brier proper scoring" via `axiom proper_scoring : ...` → tautologie déguisée, **viole ADR-020 §8 critère 1**.
- Substituer la preuve par un test numérique → ≠ formalisation.
- Importer `mathlib` en bloc sans nommer les lemmes mobilisés → opacité interdite par §8 critère 1.
- Étendre la preuve au runtime Rust ("preuve de correction du programme") → hors scope §5.4.
- Falsifier l'invariant en supprimant un cas de test plutôt qu'en cassant la définition → invalide la double falsification §4.1.

## Critères de succès

Une proposition est recevable si elle :

- Énonce le théorème Lean 4 en **≤ 15 lignes**, lisible par un mathématicien sans contexte EPP.
- Liste les lemmes `mathlib` explicitement nommés (**≤ 10 entrées**, ex. `MeasureTheory.expectation`, `Real.add_pos`).
- Présente un plan de preuve en **≤ 3 paragraphes** pointant les difficultés techniques (continuité, monotonie stricte).
- Décrit **≥ 1 red test** : modification précise (ex. abaisser un coefficient) qui doit faire échouer `lake build`.
- Mappe vers le code Python : numéros de lignes de `services/esmm/post_crystallization.py` qui implémentent l'agrégation.
- Estime honnêtement le coût en heures-prouveur, calibré sur le précédent INV-4 (complété puis falsifié sur 1 session, ADR-020 §1.3).

## Livrable attendu

Un research brief Lean 4 de **6 à 10 pages** : (1) énoncé formel ;
(2) infrastructure `mathlib` mobilisée ; (3) plan de preuve ; (4) red test ;
(5) test de conformité Python à ajouter ; (6) coût estimé. **Pas de code
Lean compilable demandé** — l'objectif est une carte d'attaque, pas une
preuve livrée.

## Sources canoniques (à consulter avant de répondre)

- ADR-020 §3 (inventaire prouvé), §4 (méthodologie non-tautologie), §5 (gap conformité), §7.1 (INV-7 non prouvé, Tier 3), §8 (critères d'acceptation)
- `Formal/Formal/Encoding.lean`, `TierBoundary.lean`, `ClaimHash.lean`, `SourceAnchor.lean` (modèles existants)
- `Formal/Formal/RedTests.lean` (protocole de double falsification)
- `services/esmm/post_crystallization.py` (implémentation runtime de l'agrégation Brier)
- `tests/test_lean_conformance.py` (pont Python↔Lean, 26 tests)
- `docs/positioning/formal_methods_landscape.md` (paysage FV : 3 / 5 400 projets Colosseum, ChronosVault 100+ théorèmes Lean 4)

---

## 6. Prompt C

# Negative-Space Dataset: Mining the Topology of Disagreement

## Contexte EPP nécessaire

EPP produit, pour chaque attestation, une **signature 5D** définie dans
WHITEPAPER §"On-Chain" (agreement, consistency, centrality, stability,
diversity) plus un `vote_entropy` mesurable. L'essai conceptuel
`docs/positioning/the_negative_space.md` argue que la valeur du graphe n'est
pas dans les scores mais dans la **topologie du désaccord** — un dataset
inexistant ailleurs : *"MMLU mesure ce que les modèles ont juste. Nous
mesurons où ils cassent différemment."* L'essai propose explicitement un
programme : *"un modèle entraîné non sur les attestations mais sur la
structure du graphe lui-même"* — i.e. apprendre la meta-structure de la
difficulté épistémique (claim normatif → variance haute / stabilité basse ;
claim post-cutoff → flywheel-sensitive ; claim de vulnérabilité code →
divergence familles 7B vs reasoning).

État courant : 12 attestations on-chain devnet, 6 modèles testés, 7 sources
déterministes intégrées, 5 domaines opérationnels, +0.46 delta flywheel
mesuré. Aucune méthodologie publiée pour transformer ce flux en dataset
entraînable.

## Question de recherche

Quel protocole méthodologique transforme la signature 5D + le `vote_entropy`
+ les marqueurs `flywheel.anchors_found` / `sources_injected` (ADR-018 §2.5)
en un **dataset structuré et étiqueté de difficulté épistémique par domaine
et par famille de modèles**, sans étiquetage humain massif et sans introduire
une ground truth qui rende le dataset gameable comme MMLU / HellaSwag ?

## Contraintes dures (axiomes et décisions du projet)

- **Axiome 5** : le dataset doit préserver la divergence — pas de "label majoritaire" qui efface l'information de désaccord.
- **Axiome 1 (Model Obsolescence)** : la méthodologie doit survivre au changement de modèles. Les features doivent être indépendantes de l'identité d'un modèle spécifique (familles d'architecture autorisées, modèles non).
- **Axiome 3** : chaque entrée porte son `frame_id` et son `consensus_method` (ADR-010). Pas de mélange inter-frames.
- **ADR-018 §6.2** : pas de boucle auto-référentielle. Une attestation VERIFY ne peut alimenter le dataset que si son état flywheel est explicitement documenté (`anchors_found: 0` ou `> 0` avec sources listées).
- **ADR-005** : les 4 tiers (sandbox / proposition / validated / verified) sont des features, jamais le label cible.

## Anti-patterns (ce que la réponse ne doit pas être)

- Étiquetage par majority vote des modèles → écrase la signature 5D, **viole Axiome 5**.
- Dataset borné par "claims dont la ground truth est connue" → ré-introduit MMLU et la triche par memorisation.
- Feature-engineering manuel d'invariants par domaine → ne survit pas à l'ajout de domaine, **viole Axiome 1**.
- Modèle entraîné directement sur (subject, predicate, object) → memorisation, pas apprentissage de la topologie.
- Ignorer le `cluster_manifest_hash` (ADR-017 §2.3) → dataset non reproductible cross-cluster.

## Critères de succès

Une proposition est recevable si elle :

- Spécifie un schéma de dataset (entrée + features + cible) reproductible à partir d'une seule lecture on-chain + SQLite, sans intervention humaine.
- Identifie **≥ 3 patterns topologiques distincts** (ex. claim normatif, claim post-cutoff, claim de vulnérabilité code) avec signature 5D attendue mesurable.
- Pour chaque pattern, ancre la validation sur **≥ 2 attestations existantes** du repo (`demos/benchmark_runs/flywheel_v2_*.json`, `jiang_*.json`, `scenario_6_1_*.json`) avec valeurs grep-ables.
- Décrit comment `inter_cluster_divergence` (ADR-017 §2.4) enrichit le dataset une fois ≥ 2 clusters opérationnels — sans dépendance bloquante.
- Argumente explicitement contre la critique "MMLU 2.0" : pourquoi ce dataset n'est pas réductible à un benchmark gamble-able.

## Livrable attendu

Un research paper draft de **10 à 16 pages** : (1) thèse — le dataset comme
mesure de "où l'IA casse différemment" ; (2) schéma data + extraction depuis
on-chain et SQLite ; (3) ≥ 3 patterns topologiques avec exemples grep-ables ;
(4) protocole d'évaluation préservant Axiome 5 ; (5) extension cross-cluster
(ADR-017) ; (6) confounds connus (training data leakage, frame-induced bias).

## Sources canoniques (à consulter avant de répondre)

- `docs/positioning/the_negative_space.md` (essai conceptuel : "le modèle qui s'entraîne sur la négative")
- ADR-018 §2.5 (traçabilité flywheel : `anchors_found`, `sources_injected`)
- ADR-010 (`consensus_meta` : methodology, conditions, diagnostics)
- ADR-017 §2.4 (`CrossClusterSignal` — extension multi-cluster)
- WHITEPAPER §"On-Chain" (signature 5D définie, PDA 462 bytes)
- `services/esmm/consensus_engine.py` (`vote_entropy`, `semantic_dispersion`)
- `demos/benchmark_runs/` (sources empiriques : `flywheel_v2_*`, `jiang_*`, `scenario_6_1_*`)

---

## 7. Self-check

### Prompt A — Cluster Reputation

- [x] **Axe traçable à un marqueur du projet** → ADR-017 §2.5 (formule pondérée avec poids `COMMUNITY_DECISION_REQUIRED`), §6 (risques Sybil/collusion), §8 Q1 (token rejeté).
- [x] **Contraintes dures citent ≥ 1 axiome/ADR** → Axiome 5, ADR-017 §8 Q1, ADR-017 §5.3, ADR-008, ADR-007.
- [x] **Anti-liste contient ≥ 1 anti-pattern violant un axiome** → "Token ERC-20-like" viole ADR-017 §8 Q1 ; "slashing automatique" viole ADR-007 (append-only) ; "off-chain non vérifiable" contredit Axiome 4.
- [x] **Critères vérifiables** → "fonction pure bit-à-bit reproductible" (test : deux exécutions identiques) ; "≥ 3 vecteurs Sybil" (test : compte) ; "≥ 50 attestations synthétiques" (test : compte) ; "non triviale sans `claim_hash`/`frame_hash`" (test : retirer le champ et vérifier que la sortie change).
- [x] **Livrable borné** → 8 à 14 pages ; pseudo-code ≤ 60 lignes ; calibration ≥ 50 attestations.
- [x] **Aucun nombre non-traçable** → 0.30/0.20/0.15/0.15/0.10/0.10 (ADR-017 §2.5), 0.95 cosine (`response_deduplicator.py` + WHITEPAPER §Security), 462 bytes (README, PITCH, WHITEPAPER), offset 41 (ADR-017 §2.4), 0.40/0.70/0.85 implicites (ADR-005). Tous grep-ables.
- [x] **Aucun acronyme indéfini** → PDA défini inline ; ESMM (mentionné en cartographie + ADR-003) ; ADR (acronyme de projet, README) ; TEE défini ADR-017 §5.1 ; Brier défini WHITEPAPER + ADR-018.
- [x] **Prompt sous 80 lignes** → ~73 lignes du titre `# Cluster Reputation...` à la dernière source canonique.

### Prompt B — Lean 4 INV-7

- [x] **Axe traçable à un marqueur du projet** → ADR-020 §7.1 (INV-7 explicitement non prouvé, classé Tier 3, "2-4 semaines pour un prouveur débutant").
- [x] **Contraintes dures citent ≥ 1 axiome/ADR** → ADR-020 §8 critères d'acceptation, ADR-020 §5.4 (gap Rust), Axiome 5 (Brier per modèle), versionnage Lean dans ADR-020 §9.
- [x] **Anti-liste contient ≥ 1 anti-pattern violant un axiome** → "axiom proper_scoring" viole ADR-020 §8 critère 1 (pas de `sorry`/`admit`/axiome ad hoc) ; "extension au runtime Rust" viole §5.4 ; "moyenner ex ante" violerait Axiome 5.
- [x] **Critères vérifiables** → "≤ 15 lignes" (test : compte), "≤ 10 lemmes mathlib nommés" (test : liste explicite), "≥ 1 red test décrit" (test : modification précise + build doit échouer), "mapping vers numéros de lignes Python" (test : grep).
- [x] **Livrable borné** → 6 à 10 pages ; pas de code Lean compilable.
- [x] **Aucun nombre non-traçable** → 11 théorèmes (ADR-020 §3 + README), 4 invariants ouverts (§7.1), Lean `v4.29.1` (§9), 26 tests conformance (§5.5), 4 modules / 18 jobs (§3 + §4.3), 3 / 5 400 projets Colosseum FV (`formal_methods_landscape.md`).
- [x] **Aucun acronyme indéfini** → ADR (cartographie) ; CI = Continuous Integration (terme générique, contextualisé par "build CI") ; INV-x défini ADR-020 §3 ; `mathlib` désigné comme "Lean 4 standard math library" implicitement par mention de "théorie de la mesure" ; Brier (ADR-018, WHITEPAPER).
- [x] **Prompt sous 80 lignes** → ~71 lignes.

### Prompt C — Negative-Space Dataset

- [x] **Axe traçable à un marqueur du projet** → `docs/positioning/the_negative_space.md` (programme "le modèle qui s'entraîne sur la négative") ; ADR-018 §2.5 (traçabilité flywheel rendant l'extraction tractable).
- [x] **Contraintes dures citent ≥ 1 axiome/ADR** → Axiome 5, Axiome 1, Axiome 3, ADR-018 §6.2, ADR-005.
- [x] **Anti-liste contient ≥ 1 anti-pattern violant un axiome** → "majority vote" viole Axiome 5 ; "feature-engineering manuel par domaine" viole Axiome 1 ; "claims avec ground truth connue" ré-introduit MMLU (contre la thèse même de l'essai negative-space).
- [x] **Critères vérifiables** → "schéma reproductible depuis on-chain + SQLite" (test : extraction sans intervention) ; "≥ 3 patterns topologiques" (test : compte) ; "≥ 2 attestations grep-ables" par pattern (test : `grep` dans `demos/benchmark_runs/`) ; "argumentation contre 'MMLU 2.0'" (test : présence d'une section dédiée).
- [x] **Livrable borné** → 10 à 16 pages, 6 sections explicites.
- [x] **Aucun nombre non-traçable** → 12 attestations on-chain (README, PITCH), 6 modèles (README, PITCH), 7 sources (README, PITCH, WHITEPAPER §"Deterministic Sources"), 5 domaines (README, PITCH), +0.46 delta (PITCH, README, ADR-018 §1.2), 462 bytes (multiplement référencé), 5D (signature définie WHITEPAPER §"On-Chain"). Tous grep-ables.
- [x] **Aucun acronyme indéfini** → MMLU et HellaSwag mentionnés dans WHITEPAPER §"LiveBench on-chain" et `the_negative_space.md` comme "centralized benchmarks that go stale and can be gamed" ; `flywheel.anchors_found` / `sources_injected` définis ADR-018 §2.5 ; `cluster_manifest_hash` défini ADR-017 §2.3 ; `inter_cluster_divergence` défini ADR-017 §2.4 ; ADR (cartographie).
- [x] **Prompt sous 80 lignes** → ~76 lignes.

---

*Fin du document.*
