# Negative-Space Dataset: Mining the Topology of Disagreement

> Réponse au Prompt C de `RESEARCH_PROMPTS_v1.md`. Research paper draft, 2026-04-27.

---

## Synthèse exécutive

EPP (Epistemic Proof Program) produit pour chaque claim attesté un objet
épistémique structuré : signature 5D (agreement, semantic consistency,
centrality, stability, relation diversity), `vote_entropy`, `claim_type`
auto-détecté, `consensus_meta` retraçant la méthodologie, et — depuis
ADR-018 — un état flywheel explicite (`anchors_found`, `sources_injected`).
Ce papier propose un **schéma de dataset extrait directement de la
blockchain et de la base SQLite**, structuré pour mesurer non pas *ce que
les modèles savent*, mais *comment ils cassent différemment* selon le
domaine, la famille d'architecture et l'état de l'enrichissement par
sources déterministes. Trois patterns topologiques sont définis et
calibrés sur des attestations existantes du repo (`scenario6_1_*`,
`flywheel_v2_*`, et données SWC-107 documentées dans WHITEPAPER §"Smart
Contract Audit"). L'extension multi-cluster (ADR-017 §2.4) ouvre la voie
à un quatrième degré de mesure (la divergence inter-méthodologies). Le
papier répond explicitement à la critique "MMLU 2.0" (§7) en montrant
que la cible du dataset n'est pas une *réponse correcte* mais une
*signature de difficulté*, structurellement immune au tirage par
mémorisation.

---

## 1. Thèse

### 1.1 Le dataset que personne ne construit

Tous les benchmarks AI publics partagent la même cible : la *réponse
correcte*. MMLU mesure le pourcentage de QCM réussis. HellaSwag mesure
le choix de la suite plausible. LiveBench mesure des problèmes nouveaux
mais conserve la même structure : entrée → label → score binaire. Cette
homogénéité est exactement ce qui rend ces benchmarks gameable : un
modèle entraîné sur la distribution des labels peut maximiser son score
sans avoir compris la tâche.

EPP produit un objet structurellement différent. Pour chaque claim, le
protocole capture la *forme* du désaccord entre les modèles avant
d'arriver à un verdict — la signature 5D, le `vote_entropy`, la
trajectoire (initial → après injection flywheel), la sensibilité aux
qualificateurs et au framing. C'est le *négatif* de la connaissance, au
sens photographique : non pas l'image (la réponse), mais ce qui révèle
l'image (la structure des limites).

Le programme conceptuel de `docs/positioning/the_negative_space.md` —
*"un modèle entraîné non sur les attestations mais sur la structure du
graphe lui-même"* — n'a pas encore de méthodologie publiée. Ce papier
propose la première.

### 1.2 Pourquoi ce dataset n'est pas réductible à un benchmark

La cible du dataset n'est *pas* une réponse, c'est une **signature
attendue**. Pour un claim normatif, la signature 5D doit présenter une
agreement basse, une stability basse, et un vote_entropy proche de 1.0.
Pour un claim post-cutoff, elle doit présenter un *delta significatif
sous injection flywheel*. Pour un claim de vulnérabilité de code, elle
doit présenter une *divergence cross-family* mesurable entre 7B et
modèles raisonneurs.

Un modèle qui voudrait gamer ce dataset devrait apprendre à reproduire
la *forme* exacte du désaccord épistémique attendu — c'est-à-dire à
*être* un panel hétérogène de modèles. C'est structurellement plus
difficile que mémoriser des labels. Et le dataset pénalise activement
les solutions homogènes : la dimension `diversity` exige un minimum de
2 familles d'architecture distinctes (WHITEPAPER §"Security & Integrity",
`infer_architecture_family`).

Ce déplacement de cible est précisément ce que la thèse de
`the_negative_space.md` formule : *"there is no majority vote to overfit
on. There is no 'correct answer' to memorize. Only the topology of
disagreement, which is invariant under the kind of gaming and
contamination that plague conventional benchmarks."*

---

## 2. Schéma de dataset

### 2.1 Source de vérité du dataset

Le dataset est extrait sans intervention humaine à partir de deux
sources publiquement lisibles :

| Source | Contenu | Accès |
|:-------|:--------|:------|
| Solana devnet (programme `9QtybfyZQFhra1D6S3NtD6jD4z2Z3wcYmf4YXETq8bSD`) | PDAs `EpistemicAttestation` (462 bytes chacun) | `getProgramAccounts` |
| SQLite locale `data/epp_devnet.db` | Table `attestations` (riche `consensus_meta`, raw model votes, vote_entropy) | lecture directe |

L'on-chain porte la *projection* compacte (signature 5D × u16, tier,
epistemic_type V2 ADR-019, claim_hash) ; la SQLite porte le `consensus_meta`
complet (méthodologie, conditions, diagnostics) — c'est-à-dire *la
substance topologique*. Le `claim_hash` (SHA-256 de subject + predicate +
object + frame, ADR-006) lie de manière déterministe les deux côtés.

### 2.2 Structure d'une entrée du dataset

```python
@dataclass
class NegativeSpaceEntry:
    # ── Identité (Axiome 3 — non comparable hors frame) ──
    claim_hash: bytes             # 32 bytes — clé primaire
    frame_id: str                 # ex. "general_knowledge_v1.0"
    frame_hash: bytes             # 32 bytes — versionnage frame
    consensus_method: str         # ex. "hash_exact_v2+semantic_merge_v1"
    cluster_manifest_hash: str    # ADR-017 §2.3 — méthodo opérateur

    # ── Features topologiques (entrée du modèle) ──
    sig_5d: tuple[float, float, float, float, float]
        # (agreement, consistency, centrality, stability, diversity)
    vote_entropy: float           # ∈ [0, 1+]
    claim_type_detected: str      # empirical | definitional | speculative | normative | security_audit
    architecture_families: tuple[str, ...]   # familles ayant participé
    n_models: int
    n_models_agreeing: int

    # ── État flywheel (ADR-018 §2.5) ──
    flywheel_anchors_found: int
    flywheel_sources_injected: tuple[str, ...]
    flywheel_baseline_score: float | None     # avant injection (si mesuré)
    flywheel_delta: float | None              # post − pré (si mesuré)

    # ── Pair contexte (optionnel — pour mesurer sensibilité framing) ──
    paired_claim_hash: bytes | None
        # claim "miroir" (cf. NORM-01 ↔ NORM-02, BIAS-01 ↔ BIAS-02)
    paired_score_delta: float | None

    # ── Cross-cluster (ADR-017, prêt mais inactif Phase 1) ──
    inter_cluster_divergence: float | None    # max − min sur peers
    n_clusters_attesting: int

    # ── Cible (signature topologique attendue, pas un label binaire) ──
    expected_pattern: str | None
        # ∈ {normative, post_cutoff_empirical, code_vulnerability,
        #    framing_sensitive, qualifier_sensitive, ...}
    expected_signature_band: dict[str, tuple[float, float]] | None
        # ex. {"agreement": (0, 0.4), "stability": (0, 0.5),
        #      "vote_entropy": (0.9, 1.0)}
```

**Remarques** :

- `expected_pattern` et `expected_signature_band` peuvent être absents
  pour les claims dont aucun pattern de référence ne s'applique. C'est
  *intentionnel* : l'absence d'attribution de pattern est elle-même un
  signal exploitable (claim atypique).
- `cluster_manifest_hash` permet de filtrer ou pondérer les entrées
  selon la méthodologie de l'opérateur. Sans cette clé, le dataset
  n'est pas reproductible cross-cluster (ADR-017 §2.3).
- Le tier (`sandbox` / `proposition` / `validated` / `verified`) n'est
  pas une cible : il est un **feature dérivé** de la signature 5D et
  des conditions de promotion (ADR-005). Le ré-utiliser comme label
  ré-introduirait la circularité que l'architecture évite par design.

### 2.3 Pipeline d'extraction (déterministe, pure)

```python
def extract_negative_space_dataset(
    devnet_pdas: list[AttestationPDA],
    db: ISpaceDB,
    pattern_taxonomy: PatternTaxonomy,
) -> list[NegativeSpaceEntry]:
    entries = []
    for pda in devnet_pdas:
        att = db.get_attestation_by_claim_hash(pda.claim_hash)
        meta = json.loads(att.consensus_meta)

        sig5d = (
            meta["signature"]["agreement"],
            meta["signature"]["semantic_consistency"],
            meta["signature"]["centrality"],
            meta["signature"]["stability"],
            meta["signature"]["relation_diversity"],
        )
        flywheel = meta.get("methodology", {}).get("flywheel", {})
        paired = pattern_taxonomy.find_pair(att.subject, att.predicate, att.object)
        inferred_pattern = pattern_taxonomy.classify(att, sig5d, meta)

        entries.append(NegativeSpaceEntry(
            claim_hash=pda.claim_hash,
            frame_id=meta["frame_id"],
            frame_hash=pda.frame_hash,
            consensus_method=meta["methodology"]["consensus_method"],
            cluster_manifest_hash=meta["methodology"].get("cluster_manifest_hash", ""),
            sig_5d=sig5d,
            vote_entropy=meta["diagnostics"]["vote_entropy"],
            claim_type_detected=att.claim_type,
            architecture_families=tuple(meta["conditions"]["architecture_families"]),
            n_models=meta["conditions"]["models_total"],
            n_models_agreeing=meta["conditions"]["models_agreed"],
            flywheel_anchors_found=flywheel.get("anchors_found", 0),
            flywheel_sources_injected=tuple(flywheel.get("sources_injected", [])),
            flywheel_baseline_score=flywheel.get("baseline_score"),
            flywheel_delta=flywheel.get("delta"),
            paired_claim_hash=paired.claim_hash if paired else None,
            paired_score_delta=paired.score_delta if paired else None,
            inter_cluster_divergence=None,  # Activé en Phase 2 (ADR-017)
            n_clusters_attesting=1,         # idem
            expected_pattern=inferred_pattern.name if inferred_pattern else None,
            expected_signature_band=inferred_pattern.band if inferred_pattern else None,
        ))
    return entries
```

L'extraction est :

- **Pure** : aucun appel réseau hormis les deux lectures publiques décrites §2.1.
- **Reproductible** : deux exécutions sur le même état (slot Solana fixé +
  snapshot SQLite) produisent le même dataset.
- **Sans étiquetage humain** : `pattern_taxonomy` est une classification
  basée sur la signature 5D et les métadonnées (cf. §3 et §6.2).

---

## 3. Trois patterns topologiques ancrés sur le repo

### 3.1 Pattern P1 — Claim normatif

**Définition** : claim portant un jugement de valeur sans cible factuelle
décidable (goût, esthétique, opinion morale). Le protocole doit refuser
de trancher (WHITEPAPER §"Edge Cases" : *"the protocol does not pretend
all claims are equal"*).

**Signature attendue** :

| Dimension | Bande |
|:----------|:------|
| `agreement` | [0.0, 0.45] |
| `stability` | [0.0, 0.55] |
| `vote_entropy` | [0.85, 1.0] |
| `claim_type_detected` | `"normative"` |
| `consensus_score` | [0.20, 0.45] (effet pénalité décidabilité = ×0.70 d'après WHITEPAPER §"Claim Classification & Decidability") |

**Cas d'école grep-ables** :

| Claim ID | Claim | Consensus | Vote entropy | Source |
|:---------|:------|:----------|:-------------|:-------|
| NORM-01 | "Pineapple on pizza is a perfectly valid and delicious choice" | 0.2912 | 1.0 | `demos/benchmark_runs/scenario6_1_20260309_193253.json` |
| NORM-02 | "Pineapple on pizza is a culinary heresy that should be banned" | 0.2268 | 1.0 | idem |

Les deux claims partagent le pattern et confirment sa stabilité au
framing inverse — le `paired_score_delta = NORM-02 - NORM-01 = -0.064`
est faible relativement à la dispersion intra-pattern, ce qui valide la
détection. À comparer avec le pattern P4 (sensibilité au framing) §3.4
ci-après, où le delta est ~5× plus grand.

### 3.2 Pattern P2 — Claim empirique post-cutoff (flywheel-sensitive)

**Définition** : claim factuel dont la vérité a évolué après le cutoff
de training des LLMs déployés. La signature pré-injection est dégradée
(les modèles ne savent pas) ; la signature post-injection se redresse
quand une source déterministe (Wikidata, NIST, ACLED) est injectée
dans le contexte (ADR-018 §2.3).

**Signature attendue** :

- *Pré-flywheel* : `agreement` ≤ 0.5, `consensus_score` ≤ 0.5, verdict
  `CONTESTED` ou `INSUFFICIENT_EVIDENCE`.
- *Post-flywheel* (avec `flywheel_anchors_found ≥ 1` et `sources_injected`
  non vide) : `consensus_score` ≥ 0.55, **et** `vote_entropy` reste élevé
  (≥ 0.7) — le garde-fou ADR-018 §10 contre le conformisme aveugle.
- `flywheel_delta` ≥ +0.10.

**Cas d'école grep-ables** :

| Claim ID | Claim | Pré | Post | Delta | Vote entropy post | Source |
|:---------|:------|:----|:-----|:------|:------------------|:-------|
| FW2-01 | "Donald Trump won the 2024 US presidential election" | 0.43 | 0.5862 | +0.1562 | 0.996792 | `demos/benchmark_runs/flywheel_v2_20260411_135551.json` |
| FW2-02 | "Keir Starmer is the current Prime Minister of the United Kingdom" | n/a | 0.76 | n/a | 1.0 | idem |

**Note importante** : le delta canonique +0.46 (0.43 → 0.89) cité dans
README, PITCH et ADR-018 §1.2 est issu d'un run antérieur ; le run
2026-04-11 le plus récent montre +0.1562 sur le même claim, ce qui reste
significativement au-dessus du seuil P2 (+0.10). La bande `[+0.10, +0.50]`
proposée englobe les deux runs et reflète la variance attendue inter-runs.

### 3.3 Pattern P3 — Claim de vulnérabilité de code

**Définition** : claim portant sur la présence d'une vulnérabilité de
sécurité dans une fonction Solidity (ADR-014). Pattern caractérisé par
une **divergence cross-family** mesurable : les modèles 7B (mistral,
llama3.1) discriminent entre fonctions vulnérables et sûres ; les
modèles raisonneurs (deepseek-r1, phi4-reasoning) sur-contestent
uniformément.

**Signature attendue** :

- `claim_type_detected` = `"security_audit"` (ADR-014 §2.4 a ajouté
  `CLAIM_TYPE_PENALTIES["security_audit"] = 1.0`).
- Sur fonction *vulnérable* (SWC-107 reentrancy) : 7B `consensus_score`
  ∈ [0.50, 0.60] CONTESTED ; raisonneur ∈ [0.40, 0.50] CONTESTED.
- Sur fonction *safe* (`addToBalance`) : 7B [0.75, 0.85] SUPPORTED ;
  raisonneur [0.65, 0.80] SUPPORTED.
- **Discrimination** = `score_safe − score_vulnerable` : 7B ≈ 0.24 ;
  raisonneur ≈ 0.28 mais à un niveau global plus bas.

**Cas d'école grep-ables** (WHITEPAPER §"Empirical Results > Smart Contract Audit (ADR-014)") :

| Function | Vulnerable? | Light (7B) | Heavy (20B+) |
|:---------|:------------|:-----------|:-------------|
| `withdrawBalance` (SWC-107) | YES | 0.55 CONTESTED | 0.46 CONTESTED |
| `addToBalance` | No | 0.79 SUPPORTED | 0.74 SUPPORTED |
| `getBalance` | No | 0.79 SUPPORTED | 0.41 CONTESTED |

La ligne `getBalance` est particulièrement instructive : un modèle 7B
détecte correctement l'absence de vulnérabilité (0.79), un modèle
raisonneur la conteste à tort (0.41). Cette divergence inter-family
est le signal P3 — elle est *plus informative* qu'un consensus unanime.

### 3.4 Pattern P4 (bonus, pré-identifié) — Sensibilité au framing

**Définition** : claim factuel rendu via deux framings opposés. La bande
attendue est un `paired_score_delta` significatif (> 0.15) sur des
claims auto-classés `empirical`, signalant que le modèle internalise le
framing plutôt que la proposition factuelle.

**Cas d'école** : BIAS-01 ("French military strong tradition") = 0.76
SUPPORTED ; BIAS-02 ("Did the French always surrender") = 0.572 CONTESTED.
`paired_score_delta = -0.188`. Source : `scenario6_1_20260309_193253.json`.

P4 est répertorié pour démonstration mais le prompt ne demande que
≥ 3 patterns ; on le mentionne pour montrer que la taxonomie est
extensible sans casser la structure.

### 3.5 Pattern P5 (bonus) — Sensibilité au qualificateur

**Définition** : claims `empirical` paire dont la vérité dépend d'un
qualificateur explicite ou implicite. Le `qualifier_delta` du pair
mesure la nuance détectée.

**Cas d'école** (WHITEPAPER §"Edge Cases" et `scenario6_2_20260302_215338.json`) :
- AQU-01/02 (Water boils at 100°C) : delta 0.0067, `nuance_detected: false` (signal d'angle mort).
- LAW-01/02 : delta 0.312, `nuance_detected: true` (signal sain).

L'asymétrie entre AQU et LAW expose un pattern : certains domaines de
connaissance (physique élémentaire) ne déclenchent pas la nuance
attendue ; d'autres (raisonnement légal) la déclenchent.

---

## 4. Protocole d'évaluation préservant Axiome 5

### 4.1 Pas de "label majoritaire", pas de "réponse correcte"

L'évaluation d'un modèle entraîné sur ce dataset ne se fait *pas* en
mesurant son taux de prédiction correcte d'un label binaire. Elle se
fait par **adéquation à la bande topologique attendue** :

```python
def evaluate_pattern_match(
    predicted_band: dict[str, tuple[float, float]],
    observed_signature: NegativeSpaceEntry,
) -> dict[str, bool | float]:
    """
    Pour chaque dimension de la signature, vérifie si la valeur observée
    se situe dans la bande prédite. Retourne un dict d'overlap, pas un
    score binaire.
    """
    return {
        "agreement_in_band": predicted_band["agreement"][0] <= observed_signature.sig_5d[0] <= predicted_band["agreement"][1],
        "stability_in_band": predicted_band["stability"][0] <= observed_signature.sig_5d[3] <= predicted_band["stability"][1],
        "vote_entropy_in_band": predicted_band["vote_entropy"][0] <= observed_signature.vote_entropy <= predicted_band["vote_entropy"][1],
        "agreement_dist": observed_signature.sig_5d[0] - 0.5 * sum(predicted_band["agreement"]),
        # ... plus 4 dimensions et les indicateurs flywheel/paired
    }
```

Le score d'évaluation global est la fraction de dimensions tombant dans
la bande attendue, *pondérée par l'importance de la dimension dans la
définition du pattern*. Pour P1 (normatif), `vote_entropy` et `agreement`
sont les dimensions principales ; `centrality` est secondaire.

### 4.2 La diversité comme contrainte d'entrée

Pour qu'une entrée du dataset soit valide, elle doit avoir été produite
sous Axiome 5 — c'est-à-dire avec ≥ 2 familles d'architecture distinctes
(WHITEPAPER §"Security & Integrity"). Le filtre est appliqué à
l'extraction :

```python
if len(set(entry.architecture_families)) < 2:
    continue  # Entrée rejetée — diversité insuffisante (Axiome 5)
```

Ce filtre est non-négociable : le dataset ne peut pas accumuler des
attestations produites par 3 instances du même modèle, qui
introduiraient un biais de confirmation systémique sans information
topologique authentique.

### 4.3 Préservation du désaccord

Le dataset n'agrège *jamais* les votes individuels en un label unique.
Chaque entrée porte la signature 5D *résultante du désaccord mesuré*.
Le passage à un label dégraderait le contenu informatif :

> *"Une entrée où agreement = 0.4 et entropy = 0.95 n'est pas équivalente
> à une entrée label=CONTESTED. La première dit en plus que les modèles
> ont divergé symétriquement ; la seconde efface cette information."*

C'est l'argument central contre les benchmarks classiques (MMLU,
HellaSwag) : la fonction de perte d'un classifieur entraîné sur un label
unique pousse mécaniquement à l'homogénéisation. La fonction de perte
proposée ici (adéquation à une bande) admet plusieurs minima locaux,
chacun correspondant à un pattern topologique distinct.

---

## 5. Extension cross-cluster (ADR-017)

### 5.1 Le multiplicateur d'information

Tant que le réseau EPP n'a qu'un seul opérateur (Phase 1), le dataset
capture la *topologie intra-cluster* du désaccord — c'est-à-dire la
divergence entre les modèles d'un opérateur unique. ADR-017 §2.4
introduit `CrossClusterSignal` lorsque ≥ 2 clusters opèrent : un même
`claim_hash` peut alors être attesté par plusieurs opérateurs avec des
sets de modèles, des sources et des frames potentiellement distincts.

Une nouvelle dimension de signature devient mesurable :

```python
@dataclass
class InterClusterDimension:
    n_clusters_attesting: int
    score_range: tuple[float, float]            # min, max sur peers
    divergence: float                            # max - min
    sources_union_size: int                      # union des sources
    architecture_families_union: set[str]        # union des familles
    methodology_overlap: float                   # similarity des consensus_method
```

L'enrichissement du dataset est mécanique : on ajoute un champ
`inter_cluster_dimension: InterClusterDimension | None` à
`NegativeSpaceEntry` (cf. §2.2). En Phase 1, ce champ vaut `None` et
n'altère pas la calibration des patterns P1, P2, P3.

### 5.2 Trois patterns inter-cluster prévisibles

- **CC-A — Convergence forte** : `divergence < 0.10` sur ≥ 3 clusters.
  Signal de consensus de second ordre — la claim est *robuste* à la
  méthodologie. À distinguer de P3 (où la divergence intra-cluster
  cross-family est *attendue*).
- **CC-B — Divergence méthodologique** : `divergence > 0.30` sur ≥ 2
  clusters dont les `cluster_manifest_hash` diffèrent significativement.
  Signal exploitable pour *attribuer* la divergence à un facteur
  méthodologique précis (modèles, sources, frame).
- **CC-C — Solitude attestative** : un seul cluster atteste un claim. Le
  pattern intra-cluster est valide mais non confirmé. Signal neutre,
  marqueur de zone à explorer.

### 5.3 Pas de dépendance bloquante

Le dataset Phase 1 *n'attend pas* la mise en réseau pour être utile. Les
trois patterns intra-cluster (P1, P2, P3) sont déjà ancrés sur des
attestations existantes. L'extension cross-cluster est un degré de
liberté supplémentaire, pas un prérequis.

---

## 6. Limites connues et confounds

### 6.1 Training data leakage (P2 surtout)

Les claims post-cutoff exploitent la limite de connaissance des LLMs.
Un modèle ré-entraîné après le cutoff connaîtra la réponse et
n'exhibera plus la signature P2. Le dataset doit donc porter explicitement :

- Le `model_id` et idéalement la `model_version` de chaque modèle
  participant (déjà capturé dans `consensus_meta.conditions.models`).
- Une indication temporelle de la source flywheel injectée
  (`source_anchor_meta.fetched_at` issu d'ADR-012).

Sans ces métadonnées, un dataset capturé en 2026-04 et exploité en
2027-04 produirait des prédictions caduques sur P2. C'est une
**dépendance temporelle assumée** — le dataset est lui-même un objet
historique versionné, pas un benchmark "intemporel".

### 6.2 Frame-induced bias

Le `frame_id` (ADR-006) entre dans le `claim_hash`, donc deux attestations
sous frames différents sont **explicitement non comparables** (Axiome 3).
Cette propriété est respectée par le filtre `frame_id == frame_id` lors
de l'évaluation cross-cluster (§5). Mais elle introduit un risque de
sur-spécialisation : un pattern P1 calibré sur `general_knowledge_v1.0`
ne peut pas être testé directement sur `compliance_sanctions_v1.0`. La
taxonomie de patterns doit donc être *frame-aware* — un pattern est
caractérisé par (signature attendue × ensemble de frames compatibles).

### 6.3 Décidabilité penalty et consensus_score

Le `consensus_score` ancré on-chain est *post-pénalité* : pour un claim
normatif, le score 0.41 ESMM brut devient 0.29 après pénalité ×0.7 (cf.
WHITEPAPER §"Claim Classification & Decidability"). Pour reconstruire
le score brut (utile à certains patterns), il faut consulter la SQLite
(`consensus_meta.diagnostics`). Le dataset doit exposer les deux —
sinon la calibration des bandes P1 doit être faite sur le score
post-pénalité, ce qui couple la détection du pattern à la version
courante de la table de pénalités. Versionner le `consensus_method`
(ADR-010) est suffisant pour gérer cette dépendance.

### 6.4 Auto-référentialité du flywheel (ADR-018 §6.2)

Une attestation VERIFY produite *avec* flywheel ne peut pas servir de
ground truth pour une autre attestation VERIFY (sinon boucle de
confirmation). Le dataset respecte ce contrat : la cible
`expected_pattern` n'est *jamais* dérivée d'une attestation VERIFY ;
elle est dérivée soit d'un argument structurel (claim_type +
sig_5d band), soit d'une source déterministe pure (ACLED, Wikidata,
NIST).

### 6.5 Volume

À la date du papier (2026-04-27), 12 attestations sont publiées on-chain
devnet. La SQLite locale contient des centaines d'attestations issues
des 26 runs benchmark. C'est suffisant pour calibrer les bandes des
patterns P1, P2, P3 sur des cas d'école précis, mais insuffisant pour
entraîner un modèle de classification de patterns à grande échelle.
Le dataset est utilisable comme *banc de test de méthodologie* avant
d'être un dataset d'entraînement opérationnel — séquence ADR-017 Phase
2-3 → 50+ clusters → augmentation naturelle du volume.

---

## 7. Réponse à la critique "MMLU 2.0"

### 7.1 La critique

Un reviewer pourrait objecter : *"Vous proposez un dataset extrait
d'attestations EPP. Une fois publié, ce dataset deviendra une cible
d'optimisation. Les modèles seront entraînés à reproduire la signature
attendue. Vous reproduisez le piège MMLU."*

### 7.2 Pourquoi cette critique ne tient pas

**Argument 1 — La cible n'est pas une réponse.** Pour gamer MMLU, il
suffit d'apprendre un mapping (entrée → label). Pour gamer ce dataset,
il faut apprendre à *reproduire la forme du désaccord d'un panel
hétérogène de modèles*. L'optimum local est un panel hétérogène —
c'est-à-dire la solution structurelle d'EPP, pas un raccourci. Le
dataset est *invariant sous l'attaque par modèle homogène*.

**Argument 2 — La diversité est une contrainte d'entrée.** Le filtre
§4.2 exige ≥ 2 familles d'architecture pour chaque entrée. Un attaquant
qui voudrait gamer le dataset devrait *exécuter ≥ 2 modèles
architecturalement distincts en parallèle* à chaque inférence. Le coût
d'inférence est multiplié, pas réduit. C'est l'inverse de l'incitation
MMLU.

**Argument 3 — La cible est versionnée, pas universelle.** Le
`consensus_method` (ADR-010) et le `cluster_manifest_hash` (ADR-017
§2.3) sont des coordonnées explicites. Une signature attendue P1
dépend de la version de l'algorithme de consensus et de la
configuration cluster. Deux datasets à six mois d'écart sont
*explicitement non comparables* (Axiome 3). Un modèle entraîné sur la
version V1 du dataset n'a pas de garantie sur la version V2 — la
cible bouge structurellement, par design.

**Argument 4 — Le flywheel injecte du nouveau.** Au fur et à mesure que
de nouvelles sources déterministes sont ajoutées (ADR-012, ADR-016,
ADR-018), le pattern P2 capture une distribution différente. La cible
est *dynamique en fonction de l'enrichissement déterministe* — ce qui
est exactement la propriété qui manque aux benchmarks figés.

**Argument 5 — Le négatif n'est pas exploitable comme un positif.** La
distinction ontologique entre *réponse* et *signature de difficulté*
est plus qu'un détail de cadre. Apprendre une réponse, c'est apprendre
une fonction `q → r`. Apprendre une signature, c'est apprendre une
fonction `q → P(D)` où `D` est l'espace des distributions de votes. La
seconde est strictement plus riche, et son apprentissage ne déclasse
pas la première — un modèle qui prédit correctement la signature de
difficulté reste *ignorant de la réponse*. Cette distinction est
explicite dans `the_negative_space.md` : *"Not knowledge. The negative
of knowledge — the precise, reproducible, formally constrained map of
where knowledge fails."*

---

## 8. Limites du papier et suites possibles

- **Le papier ne livre pas de classifieur entraîné**. La taxonomie de
  patterns est définie ; sa calibration sur ≥ 100 attestations
  diversifiées (post-Phase 2) est un travail empirique à conduire en
  suite.
- **L'extension cross-cluster (§5) est conditionnelle**. Tant que ≥ 2
  clusters ne sont pas opérationnels, les dimensions inter-cluster
  restent théoriques.
- **La pondération des dimensions de la signature 5D dans l'évaluation
  (§4.1) reste à empiriquement justifier**. La proposition implicite
  (`agreement` et `vote_entropy` comme dimensions principales pour P1)
  s'appuie sur la lecture des cas d'école §3.1, pas sur une analyse
  multivariée formelle — celle-ci nécessite davantage de données.
- **L'intégration au protocole EPP n'est pas tranchée.** Le dataset
  pourrait vivre comme un module externe (lecture seule de la
  blockchain et de SQLite) ou comme une vue SQL native dans
  `database/schema.sql`. Le choix dépend de la fréquence d'usage et
  ouvre potentiellement un nouvel ADR.

---

## 9. Sources et lien aux marqueurs projet

- `docs/positioning/the_negative_space.md` (programme conceptuel : "le modèle qui s'entraîne sur la négative", topologie du désaccord)
- `docs/adr/ADR-018.md` §2.5 (traçabilité flywheel : `anchors_found`, `sources_injected`, `delta`), §6.2 (pas de boucle auto-référentielle), §10 (vote_entropy > 0.7 attendu post-injection)
- `docs/adr/ADR-010.md` (`consensus_meta` : methodology, conditions, diagnostics)
- `docs/adr/ADR-017-avenir.md` §2.3 (`cluster_manifest_hash`), §2.4 (`CrossClusterSignal`)
- `docs/adr/ADR-014.md` (audit smart contracts, `claim_type = security_audit`)
- `docs/adr/ADR-006.md` (claim_hash inclut frame, contrat de non-comparabilité Axiome 3)
- `docs/adr/ADR-019.md` (Enum V2 on-chain : 0=empirical, 1=deterministic, 2=assessed)
- `WHITEPAPER.md` §"On-Chain" (signature 5D définie, PDA 462 bytes), §"Claim Classification & Decidability" (table des pénalités), §"Smart Contract Audit (ADR-014)" (table SWC-107 cross-family)
- `services/esmm/consensus_engine.py` (`vote_entropy`, `semantic_dispersion`)
- `services/providers/base.py::infer_architecture_family` (filtre Axiome 5 §4.2)
- `demos/benchmark_runs/scenario6_1_20260309_193253.json` (NORM-01, NORM-02, BIAS-01, BIAS-02 — patterns P1, P4)
- `demos/benchmark_runs/scenario6_2_20260302_215338.json` (AQU-01/02, LAW-01/02 — pattern P5)
- `demos/benchmark_runs/flywheel_v2_20260411_135551.json` (FW2-01 Trump, FW2-02 Starmer — pattern P2)
- `demos/benchmark_runs/jiang_20260311_082057.json` (Jiang predictions, géopolitique — sources additionnelles pour P2)

*Fin du document.*
