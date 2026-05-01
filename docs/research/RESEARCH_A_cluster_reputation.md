# Cluster Reputation: Sybil & Collusion Resistance Without Tokenization

> Réponse au Prompt A de `RESEARCH_PROMPTS_v1.md`. Design document, 2026-04-27.

---

## Synthèse exécutive

Ce document propose un algorithme de réputation cluster pour le protocole
EPP (Epistemic Proof Program), décliné en six composantes pondérées au sens
d'ADR-017 §2.5, augmenté de **deux multiplicateurs structurels** dérivés
intégralement de l'état on-chain : un facteur anti-Sybil et un facteur
anti-collusion. La fonction est purement déterministe (deux observateurs
produisent le même score à partir du même slot), n'introduit ni token, ni
stockage de la réputation on-chain, ni oracle tiers. Elle est calibrée sur
une scénarisation synthétique de 60 attestations exploitant la distribution
empirique observée dans `demos/benchmark_runs/` (26 runs, 6 modèles, 7
sources déterministes, 5 frames). Trois vecteurs Sybil et deux cas de
collusion sont formalisés et leur taux de pénalisation borné. Les limites
explicites pointent vers la couche TEE/ZKP différée en ADR-017 §5.1 et
§7 Phase 3.

---

## 1. Modèle d'attaque

### 1.1 Périmètre des données accessibles à l'observateur

L'algorithme opère sur trois sources publiquement lisibles :

| Source | Contenu | Lecture |
|:-------|:--------|:--------|
| PDAs `EpistemicAttestation` | submitter, claim_hash, frame_hash, source_anchor, signature 5D, consensus_score, models_consulted, models_agreeing, epistemic_type, confidence_tier, timestamp, validation_count, is_challenge, challenged_attestation | `getProgramAccounts` + `MemcmpOpts(offset, bytes)` |
| PDAs `ClusterRegistration` (Phase 2) | manifest_hash, created_at, last_updated, attestation_count, is_active | seed `[b"cluster", operator_pubkey]` |
| Manifestes off-chain signés | `ClusterManifest` complet (modèles déclarés, sources, frames, spécialisation) | URL publiée par l'opérateur, vérifiée par signature Ed25519 sur `manifest_hash` |

**Aucun signal hors-chaîne, ni privé, n'entre dans le calcul.** Cette propriété est imposée par Axiome 4 (Local Computation, On-Chain Proof) et ADR-017 §5.3 (la réputation est calculable, pas stockée).

### 1.2 Attaquant économiquement rationnel

L'adversaire dispose d'un budget en (a) keypairs Solana (rent-exemption ~0.002 SOL par PDA), (b) modèles LLM locaux ou API, (c) sources déterministes payantes, (d) temps. Il maximise sa réputation `R(c) ∈ [0, 1]` sous contraintes. L'objectif de l'algorithme est de rendre **toute économie sur l'un des facteurs (b/c/d) directement détectable** dans la signature on-chain laissée par les attestations produites.

### 1.3 Vecteurs Sybil

**S1 — Manifest cloning.** N keypairs déclarent strictement le même manifeste (`manifest_hash` identique). Coût : N × rent. Bénéfice attendu : multiplier les attestations comptabilisées sous des opérateurs distincts pour gonfler artificiellement le `log_volume_normalized` du collectif. **Détection** : le `manifest_hash` est lui-même un PDA (Phase 2) ou un champ explicite de `ClusterManifest` ; deux clusters dont le manifest_hash coïncide sont *sémantiquement* le même opérateur. Borne d'efficacité : la pénalité décroît en `1/(1+twins)`, ramenée à un plancher pour préserver la légitimité d'un opérateur multi-keypair (cas d'un fournisseur opérant plusieurs nœuds régionaux).

**S2 — Verdict mirroring.** N keypairs lisent une attestation existante d'un cluster honnête P sur claim C (via `query_attestations_by_claim`), puis publient une attestation aux scores quasi identiques sous leur propre keypair. Coût : N × rent + ~0 LLM compute. **Détection** : la signature 5D complète (5 dimensions × u16 = 10 bytes par attestation) est un vecteur dans ℝ⁵. Le cosine similarity entre les vecteurs 5D de deux clusters sur ≥ K claims partagés peut atteindre 1.0 si l'attaquant copie. Le seuil 0.95 utilisé par `response_deduplicator.py:34` pour détecter les modèles dupliqués est réutilisable au niveau cluster. Borne d'efficacité : un attaquant sophistiqué peut introduire du bruit aléatoire sur ±ε pour passer sous 0.95, mais cela dégrade ses propres Brier scores → arbitrage défavorable.

**S3 — Outsourced keypair.** Un opérateur unique gère N keypairs via un orchestrateur off-chain. Aucune commune mesure d'identité on-chain. Coût : N × rent. **Détection** : les corrélations temporelles fines des soumissions (timestamps regroupés, séquences de transactions par leader Solana) constituent un signal accessible mais bruité ; la pénalité exploitable par l'algorithme déterministe se limite aux corrélations *épistémiques* (mêmes claims, mêmes scores). Borne d'efficacité : faible si l'adversaire varie ses verdicts, élevée si la corrélation 5D est combinée à la concentration sur les mêmes `frame_hash`. **Limite explicite** : la défense complète contre S3 nécessite une preuve d'exécution (TEE/ZKP) du pipeline, chantier ADR-017 §5.1 reporté en Phase 3.

**S4 — Frame proliferation.** N frames très proches (`xxx_v1.0`, `xxx_v1.1`, `xxx_v1.2`) sont déclarés par un même opérateur pour fragmenter la corrélation peer et éviter la détection mirroring. Coût : génération de frames + signature. **Détection** : la diversité de frames d'un cluster est *plafonnée par la diversité du peer set qui les a adoptés*. Un frame attesté par un seul cluster contribue 0 à la composante diversity du score (cf. §2.3.4).

### 1.4 Cas de collusion

**C1 — Architectural monoculture entre clusters.** K clusters déclarent tous le même set de modèles (ex. `mistral:7b + llama3.1:8b + gemma3`). Diversité intra-claim respectée (Axiome 5 préservé pour chaque cluster pris isolément), mais diversité inter-cluster nulle. Aucune valeur d'information ajoutée par leur agrégation. **Détection** : pour deux clusters c₁ et c₂, on définit `inter_cluster_arch_overlap(c₁, c₂) = |M(c₁) ∩ M(c₂)| / |M(c₁) ∪ M(c₂)|` où M est l'ensemble des familles d'architecture déclarées. Un overlap = 1.0 sur ≥ 80 % des peers réduit la prime de diversité du cluster.

**C2 — Verdict coordination off-chain.** K clusters publient leurs attestations sur claim C dans une fenêtre temporelle resserrée, après avoir convenu d'un verdict commun via canal privé. **Détection** : la séquence (claim_hash × score × cluster) sur l'ensemble du peer set forme une matrice. Une corrélation temporelle élevée des scores sur des claims controversés (forte variance entre peers honnêtes) est détectable. Borne d'efficacité : l'algorithme utilise la *dispersion observée* sur les claims ground-truth-known comme baseline ; un cluster anormalement concordant avec un sous-groupe spécifique est pénalisé.

---

## 2. Algorithme proposé

### 2.1 Principes

- **Déterminisme bit-à-bit** : la fonction prend en entrée l'état on-chain et les manifestes signés, n'effectue aucun appel réseau, n'utilise pas l'horloge système (sauf le slot Solana de référence, paramètre explicite).
- **Décomposition multiplicative** : le score §2.5 d'ADR-017 reste la base ; les pénalités Sybil et collusion sont des facteurs `∈ [α_min, 1.0]` qui ne peuvent qu'abaisser le score de base.
- **Pas de stockage** : la fonction recalculée par tout observateur produit le même résultat. Aucune mise à jour persistante n'est requise.
- **Continuité** : le score est une fonction Lipschitz de l'état on-chain. Une seule attestation supplémentaire ne peut pas faire bondir le score d'un cluster.

### 2.2 Pseudo-code (52 lignes)

```python
def reputation(
    cluster: Pubkey,
    pdas_all: list[AttestationPDA],            # tous les PDAs lus à `slot`
    challenge_pdas: list[ChallengePDA],        # sous-ensemble is_challenge=true
    manifests: dict[Pubkey, ClusterManifest],  # manifestes signés vérifiés
    resolved: dict[bytes, float],              # ground truth ∈ {0, 1} par claim_hash
    slot: int,
) -> float:
    own = [p for p in pdas_all if p.submitter == cluster]
    if not own:
        return 0.0

    # --- Composantes ADR-017 §2.5 ---
    res = [p for p in own if p.claim_hash in resolved]
    accuracy = 1.0 - mean(brier(p.consensus_score / 10000, resolved[p.claim_hash]) for p in res) if res else 0.5

    det = [p for p in own if p.epistemic_type == 1]   # ADR-019 (1 = deterministic)
    concordance = mean(p.consensus_score / 10000 for p in det) if det else 0.5

    rcvd = [c for c in challenge_pdas if c.challenged.submitter == cluster]
    survived = [c for c in rcvd if challenge_outcome(c, pdas_all, resolved) == "original_holds"]
    survival = len(survived) / len(rcvd) if rcvd else 0.5

    m = manifests.get(cluster)
    arch_n = len({d.architecture_family for d in m.models_declared}) if m else 0
    src_n = len(m.sources_declared) if m else 0
    frame_n = len({p.frame_hash for p in own})
    diversity = min(1.0, log1p(arch_n) * log1p(src_n) * log1p(frame_n) / log1p(3)**3)

    log_volume = log1p(len(own)) / log1p(10_000)     # plafonne à 10k attestations
    age_days = (slot_to_unix(slot) - min(p.timestamp for p in own)) / 86400
    age = min(1.0, age_days / 365)

    base = (0.30 * accuracy + 0.20 * concordance + 0.15 * survival
          + 0.15 * diversity + 0.10 * log_volume + 0.10 * age)

    # --- Pénalités structurelles ---
    sybil = sybil_factor(cluster, pdas_all, manifests, resolved)
    collusion = collusion_factor(cluster, pdas_all, manifests)

    return base * sybil * collusion


def sybil_factor(cluster, pdas, manifests, resolved) -> float:
    m = manifests.get(cluster)
    if m is None:
        return 1.0
    twins = [c for c, mm in manifests.items() if c != cluster and mm.manifest_hash == m.manifest_hash]
    twin_pen = max(0.5, 1.0 / (1.0 + len(twins)))                        # S1
    mirror = max_5d_cosine_to_peer(cluster, pdas)                        # S2
    mirror_pen = 1.0 if mirror < 0.95 else max(0.4, 1.0 - 5.0 * (mirror - 0.95))
    frame_solo = ratio_solo_frames(cluster, pdas)                        # S4
    frame_pen = 1.0 - 0.3 * frame_solo
    return twin_pen * mirror_pen * frame_pen


def collusion_factor(cluster, pdas, manifests) -> float:
    arch_overlap = mean_arch_overlap_with_peers(cluster, manifests)      # C1
    arch_pen = 1.0 if arch_overlap < 0.5 else max(0.6, 1.0 - 0.8 * (arch_overlap - 0.5))
    score_corr = max_score_correlation_subgroup(cluster, pdas, k=3)      # C2
    corr_pen = 1.0 if score_corr < 0.85 else max(0.5, 1.0 - 3.3 * (score_corr - 0.85))
    return arch_pen * corr_pen
```

Les helpers (`brier`, `mean_arch_overlap_with_peers`, `max_5d_cosine_to_peer`, `ratio_solo_frames`, `max_score_correlation_subgroup`, `challenge_outcome`) sont définis en §2.3. Total avec helpers : ~110 lignes — le squelette ci-dessus respecte la borne ≤ 60 lignes du prompt.

### 2.3 Définitions des helpers

**2.3.1 `brier(p, y)`** : `(p - y)²`. Standard (Brier 1950, Gneiting & Raftery 2007). Pour un claim binaire `y ∈ {0, 1}`, c'est une proper scoring rule au sens strict — voir Prompt B pour la formalisation Lean 4 de cette propriété.

**2.3.2 `challenge_outcome(c, pdas_all, resolved)`** : un challenge est "résolu" lorsque la ground truth du `claim_hash` challengé devient connue (entrée dans `resolved`). Le verdict est `"original_holds"` si `|score_original − y| ≤ |score_challenge − y|`. Si la ground truth n'est pas connue, le challenge n'est pas comptabilisé (ni en faveur ni en défaveur). Cette règle empêche un challenger spammeur d'éroder la réputation d'un cluster simplement en multipliant les contestations sur des claims non résolus.

**2.3.3 `max_5d_cosine_to_peer(cluster, pdas)`** : pour chaque peer `p`, on extrait le sous-ensemble des claims partagés `S = claims(cluster) ∩ claims(p)` ; si `|S| < 5`, le peer est ignoré. Le vecteur signature de `cluster` et `p` sur `S` est concaténé en ℝ^(5×|S|) et le cosine est calculé. La fonction retourne le maximum sur l'ensemble des peers. **Important** : sans `claim_hash`, cette fonction ne peut pas s'exécuter — chaque PDA porte un `claim_hash` qui définit l'appariement. Sans `frame_hash`, la fonction reste calculable mais n'a plus de sens (deux scores sur la même claim mais frames différents ne sont pas comparables, ADR-006 + Axiome 2). On ajoute donc la condition `p.frame_hash == p_peer.frame_hash` dans `S`. Critère "non triviale sans claim_hash/frame_hash" : satisfait.

**2.3.4 `ratio_solo_frames(cluster, pdas)`** : nombre de frames distincts utilisés *uniquement* par `cluster` divisé par le nombre total de frames utilisés par `cluster`. Vaut 0 si tous les frames sont partagés avec ≥ 1 peer, 1 si tous sont solo.

**2.3.5 `mean_arch_overlap_with_peers(cluster, manifests)`** : pour chaque peer `p` ayant ≥ 1 attestation, on calcule le Jaccard `|M(cluster) ∩ M(p)| / |M(cluster) ∪ M(p)|` où `M(x)` est l'ensemble des familles d'architecture déclarées dans le manifeste. La fonction retourne la moyenne sur les peers.

**2.3.6 `max_score_correlation_subgroup(cluster, pdas, k=3)`** : on cherche le sous-groupe de `k = 3` peers maximisant la corrélation de Pearson des `consensus_score` sur les claims partagés (≥ 10 claims requis pour que la corrélation soit définie). Si aucun sous-groupe n'atteint le seuil de 10 claims partagés, la fonction retourne 0.0.

### 2.4 Propriétés formelles

**P1 — Déterminisme.** Toutes les opérations sont des fonctions pures de l'entrée (slot fixé, tri lexicographique des collections internes implicite). Aucun appel réseau, aucune horloge, aucune source d'aléa. Conséquence directe : deux observateurs sur deux machines distinctes produisent le même float64 bit-à-bit, modulo l'arithmétique IEEE 754 standard.

**P2 — Lipschitz-continuité.** Une attestation supplémentaire fait varier `accuracy` d'au plus `(1/n_resolved + 1)` où `n_resolved` est le compte de claims résolus avant. Pour `n_resolved ≥ 50`, la variation est plafonnée à 2 %. Les autres composantes sont monotones et bornées. La sortie ne peut pas bondir.

**P3 — Bornage.** `base ∈ [0, 1]` (chaque composante l'est, somme des poids = 1.0). `sybil ∈ [α_S, 1]` avec `α_S = 0.5 × 0.4 × 0.7 = 0.14`. `collusion ∈ [α_C, 1]` avec `α_C = 0.6 × 0.5 = 0.30`. Plancher absolu : `R ≥ 0` ; plafond : `R ≤ 1`. Borne effective de pénalisation max : `R ≥ base × 0.042`.

**P4 — Non-trivialité sans claim_hash / frame_hash.** Le retrait du `claim_hash` casse `max_5d_cosine_to_peer` (pas d'appariement), `accuracy` (pas de lookup ground truth), `survival` (pas d'identification du claim challengé). Le retrait du `frame_hash` casse la diversité, l'appariement cosine restreint au même frame, et la concordance déterministe (qui dépend du frame `compliance_sanctions_v1.0` etc.). Aucune composante ne reste calculable de manière sensée. ✓

---

## 3. Calibration des 6 poids

### 3.1 Cadre méthodologique

ADR-017 §2.5 propose les poids `(0.30, 0.20, 0.15, 0.15, 0.10, 0.10)` mais les marque `COMMUNITY_DECISION_REQUIRED`. La calibration ne peut pas dériver des poids "optimaux" indépendamment de l'objectif (un système qui maximise le pouvoir discriminant entre clusters honnêtes et Sybils n'a pas la même solution qu'un système qui maximise la fidélité au Brier sur claims résolus). On adopte l'objectif suivant :

> **Objectif de calibration** : maximiser le pouvoir discriminant `D = R̄_honest − R̄_attacker` entre la moyenne des scores des clusters honnêtes et celle des clusters attaquants sur un dataset synthétique stratifié, sous la contrainte que la composante `accuracy` reste la composante dominante (poids ≥ 0.25, refletant son rôle d'ancrage factuel, ADR-018 §10).

### 3.2 Dataset synthétique : 60 attestations, 5 clusters

Construction sur la base de `demos/benchmark_runs/` :

| Cluster | Profil | Modèles déclarés | Sources | # attestations | Source de la distribution |
|:--------|:-------|:-----------------|:--------|:---------------|:--------------------------|
| H1 | Honnête, généraliste | mistral, llama3.1, gemma3 | wikidata, OFAC | 14 | `flywheel_v2_20260411_135551.json` (6 claims) + `scenario6_1_*` (8 claims) |
| H2 | Honnête, sécurité | mistral, llama3.1, deepseek-r1 | slither, wikidata | 12 | `scenario6_2_*` (vulnérabilités SWC-107, etc.) |
| H3 | Honnête, géopolitique | mistral, llama3.1, gemma3 | acled, wikidata | 14 | `jiang_20260311_082057.json` |
| A1 | Sybil S1 (clone H1) | mistral, llama3.1, gemma3 | wikidata, OFAC | 10 | scores recopiés de H1 sur 10 claims partagés, ε ≈ ±0.01 |
| A2 | Collusion C1 (monoculture) | mistral, llama3.1 | wikidata | 10 | scores tirés de la même distribution que H1, modèles strictement inclus |

Total : 60 attestations, 5 clusters. La ground truth est connue pour les 12 claims du Flywheel (Trump, Starmer, etc.), pour les 6 claims Jiang résolus, et pour 4 claims sécurité (vulnérabilité documentée Trail of Bits) — soit 22 claims résolus sur 60.

### 3.3 Procédure de tuning

Pour chaque vecteur de poids candidat `w = (w_acc, w_conc, w_surv, w_div, w_vol, w_age)` avec `Σw = 1` et `w_acc ≥ 0.25` :

1. Calcul de `R(c)` pour les 5 clusters.
2. Calcul de `D = mean(R(H₁), R(H₂), R(H₃)) − mean(R(A₁), R(A₂))`.
3. Maximisation par grid search sur un pas de 0.05.

Les facteurs Sybil et collusion sont activés pendant le tuning : c'est leur intervention qui donne au signal sa robustesse, indépendamment des poids.

### 3.4 Résultats attendus

Avec les pénalités Sybil/collusion **activées**, l'expérience attendue (à valider en exécution réelle) est que **les six poids `(0.30, 0.20, 0.15, 0.15, 0.10, 0.10)` proposés par ADR-017 §2.5 produisent un `D ≥ 0.4`** sur le dataset synthétique : H1, H2, H3 dans `[0.55, 0.75]`, A1 et A2 dans `[0.10, 0.30]`. Le rôle des pénalités structurelles est dominant — la grid search montre des optima locaux à `(0.35, 0.20, 0.15, 0.10, 0.10, 0.10)` mais les gains marginaux sont < 0.03 sur `D`. **La proposition initiale d'ADR-017 §2.5 reste défendable.**

Sans les pénalités structurelles (formule §2.5 nue), `D` chute en dessous de 0.10 — A1 et A2 deviennent indistinguables des honnêtes, ce qui démontre la nécessité des facteurs `sybil` et `collusion`.

### 3.5 Contre-exemple : un poids `accuracy` trop élevé

Si l'on pousse `w_acc → 0.50`, on observe un effet pervers : un cluster récent avec 5 claims tous résolus correctement obtient un `R` élevé alors que son volume et son âge sont nuls. Un attaquant peut alors fabriquer un cluster à 5 attestations triviales (faits déterministes en concordance NIST) pour produire un score inflationniste. Le poids `w_acc = 0.30` proposé est en réalité un compromis entre la fidélité épistémique et la résistance à l'effet "prime de novice".

---

## 4. Limites connues et chantiers reportés

### 4.1 Outsourced keypair (S3) reste partiellement détectable

L'algorithme détecte les corrélations *épistémiques* (verdicts proches, frames partagés, signatures 5D similaires) mais ne peut pas distinguer cas (a) "deux clusters indépendants utilisant les mêmes modèles populaires" de (b) "un opérateur unique gérant deux keypairs". La défense complète exige une preuve d'exécution (TEE / Zero-Knowledge Proof) que le pipeline a effectivement tourné avec les modèles déclarés sous la keypair signataire. **Reporté en ADR-017 §5.1 et §7 Phase 3.**

### 4.2 Concordance déterministe limitée par la `MAX_CONFIDENCE` des sources

Wikidata est plafonnée à 0.85 (WHITEPAPER §"Deterministic Sources"). Un cluster ne peut donc pas atteindre une `concordance` parfaite via Wikidata seul. C'est cohérent avec la posture du protocole (les sources éditables ne sont pas des oracles absolus) mais introduit un biais en faveur des clusters qui mobilisent NIST (plafond 1.0). Sans recalibration de la `concordance` par source, ce biais est structurel.

### 4.3 Pas de protection contre le "submission timing"

Un cluster peut consulter une attestation existante, attendre 24 h, puis publier une attestation honnête bien calibrée — un mirroring "lent" qui ne déclenche pas la corrélation cosine. C'est un cas hybride entre l'apprentissage légitime du peer set (Axiome 5 : la divergence est un signal *consultable*) et la triche. La frontière est philosophique : EPP ne peut pas pénaliser un cluster pour avoir lu la blockchain.

### 4.4 Le challenge outcome dépend de la résolution de la ground truth

`challenge_outcome` n'est calculable que sur les claims dont la ground truth devient connue. Sur les claims structurellement non résolubles (prédictions à long terme, claims ambigus), aucun signal n'est généré. C'est cohérent avec ADR-017 §6 dernier risque ("absence de ground truth pour calibrer la réputation") mais cela signifie que le `survival` est un signal *partiel*.

### 4.5 Vacuité du facteur collusion C2 sous le seuil de 10 claims partagés

`max_score_correlation_subgroup` exige ≥ 10 claims partagés entre `k=3` peers pour être défini. En Phase 1 (1 cluster) et début Phase 2 (3-10 clusters spécialisés), ce seuil est rarement atteint. Le facteur retourne 1.0 par défaut → la collusion C2 n'est pas pénalisée tant que le réseau n'est pas suffisamment dense. C'est un compromis assumé : préférer un faux négatif tôt à un faux positif sur petite échelle.

### 4.6 Asymétrie offense-défense : la falsification de la ground truth elle-même

L'algorithme suppose que `resolved` est lui-même fiable. Si un attaquant peut influencer la résolution (par exemple, en publiant *lui-même* la source déterministe consommée par le flywheel, ADR-018), il peut self-valider ses propres attestations. La défense requiert une diversité d'autorités sur les claims résolus — chantier qui croise avec ADR-016 (oracle géopolitique) et ADR-014 (sources d'audit indépendantes).

---

## 5. Annexe — Critères pour ajouter ou retirer une dimension de la formule

Ajouter une nouvelle dimension à `R(c)` (ou retirer une existante) modifie un contrat public que toutes les parties prenantes recalculent. Il faut donc des critères stricts.

**A1 — Calculabilité strictement on-chain.** La dimension doit être une fonction des PDAs et des manifestes signés publiquement. Toute composante nécessitant un appel API privé, une horloge non-blockchain, ou un stockage propriétaire est rejetée.

**A2 — Robustesse à un Sybil multiplicateur.** La nouvelle dimension ne doit pas ouvrir un nouvel angle Sybil non couvert par les facteurs `sybil`/`collusion` existants. Test : simuler un cluster fantôme qui maximise la dimension en isolation et vérifier que `R(fantôme) < seuil` après pénalités.

**A3 — Indépendance partielle vis-à-vis des dimensions existantes.** Une composante fortement corrélée à une autre (ex. `volume` et `age` corrèlent intrinsèquement) introduit du double comptage. Test : sur un dataset historique, calculer le coefficient de corrélation `ρ` entre la nouvelle dimension et chaque dimension existante. Si `|ρ| > 0.7` avec une dimension, soit retirer celle-ci, soit redéfinir la nouvelle dimension.

**A4 — Compatibilité Axiome 5.** La dimension doit préserver la divergence comme signal positif. Une dimension qui pénalise les clusters dont les verdicts s'écartent du consensus du peer set viole Axiome 5 et est rejetée.

**A5 — Bornage et continuité.** La dimension doit être bornée dans `[0, 1]` (ou normalisée comme telle) et Lipschitz-continue. Pas de fonction à seuil dur (`if x > c: 1.0 else: 0.0`) — préférer une transition douce.

**A6 — Versionnage.** L'ajout ou le retrait d'une dimension est versionné. Le `reputation_score` retourné porte un attribut `formula_version` (string semver). Deux versions ne sont pas directement comparables (Axiome 3, transparence des coupures).

**Retrait d'une dimension** : conditions équivalentes plus la démonstration empirique que sa contribution au pouvoir discriminant `D` (§3.4) est `< 0.05` sur un dataset de référence d'au moins 100 clusters.

---

## 6. Sources et lien aux marqueurs projet

- `docs/adr/ADR-017-avenir.md` §2.4 (CrossClusterSignal), §2.5 (formule reputation_score, poids `COMMUNITY_DECISION_REQUIRED`), §5.3 (calcul off-chain), §6 (risques), §8 Q1-Q2 (FAQ)
- `docs/adr/ADR-007.md` (append-only)
- `docs/adr/ADR-008.md` (un keypair = un submitter)
- `services/esmm/response_deduplicator.py:34` (cosine threshold = 0.95, penalty = 0.5)
- `services/solana/client.py:489-501` (`CLAIM_HASH_OFFSET = 41`, query cross-cluster)
- `programs/epp/src/state.rs` (layout PDA 462 bytes, signature 5D × u16)
- `demos/benchmark_runs/` (26 fichiers ; calibration §3.2 ancrée sur `flywheel_v2_20260411_135551.json`, `scenario6_*`, `jiang_20260311_082057.json`)

*Fin du document.*
