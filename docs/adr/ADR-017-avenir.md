# ADR-017 : Réseau de Clusters Épistémiques — Architecture Multi-Opérateurs

**Date** : 2026-03-11
**Statut** : Proposé (v1 — vision architecturale)
**Dépendances** : ADR-005 (tiers multi-critères), ADR-006 (claim hash), ADR-008 (authentification submitter), ADR-010 (traçabilité méthodologique), ADR-012 (bifurcation déterministe)
**Axiomes mobilisés** : 1 (obsolescence des modèles), 2 (survie du graphe), 3 (transparence des coupures), 4 (computation locale, preuve on-chain), 5 (la divergence est le signal)

---

## 1. Contexte

### 1.1 — Le problème de la centralisation implicite

EPP fonctionne aujourd'hui comme un pipeline mono-opérateur : un submitter unique (keypair Solana), un ensemble de modèles locaux, un graphe SQLite, une base d'attestations. Le protocole est conçu pour la décentralisation (ADR-008, `COMMUNITY_DECISION_REQUIRED` markers), mais l'unité fondamentale de décentralisation n'est pas définie.

La roadmap actuelle (Phase 1 → Phase 2 → Phase 3) décrit une transition "centralisé maintenant, décentralisé plus tard." Ce récit est structurellement faible : il promet la décentralisation sans nommer l'entité qui se décentralise. Un oracle qui promet de se décentraliser est indistinguable d'un oracle centralisé qui retarde indéfiniment.

### 1.2 — L'observation fondatrice

Le run `scenario_jiang` du 2026-03-11 illustre le problème et la solution simultanément :

- **JIANG-RESOLVED-01** — "Donald Trump won the 2024 US presidential election" : CONTESTED 0.403 (`verdict_ok: false`). Un fait historique avéré que 3 modèles (mistral, llama3.1, gemma3) ne confirment pas. Cause : knowledge cutoff partagé.
- **Wikidata** sur le même claim : `wikidata_status: "found"`, `wikidata_score: 0.85`. La source déterministe corrige le biais LLM.

Si un second opérateur avait fait tourner le même claim avec des modèles différents (phi4-reasoning, deepseek-r1, granite3.3), deux scénarios : soit la même erreur — confirmant un biais systémique documenté, pas un artefact local ; soit un résultat divergent — produisant un signal de second ordre exploitable.

**Ni l'un ni l'autre de ces signaux n'est possible dans un système mono-opérateur.**

Le même pattern se répète dans `benchmark_heavy` (ADR-014) : les modèles raisonneurs sur-contestent tout uniformément (~0.45), tandis que les 7B discriminent mieux. Cette divergence inter-familles EST le signal — mais elle reste aujourd'hui interne à un seul opérateur. Élevée au niveau du réseau, elle devient un mécanisme de marché.

### 1.3 — Le concept : Cluster Épistémique

Un **Cluster EPP** est une instance autonome du protocole opérée par un submitter identifiable (keypair Solana). Chaque cluster :

- Choisit ses modèles LLM (type, quantisation, nombre)
- Configure ses sources déterministes (OFAC, ACLED, Wikidata, etc.)
- Sélectionne ses frames métrologiques
- Produit des attestations on-chain traçables via `consensus_meta` (ADR-010)

La confiance ne se décrète pas — elle **émerge** du track record cumulé de chaque cluster. La compétition entre clusters sur les mêmes claims produit un prix d'équilibre épistémique : la meilleure approximation collective de la vérité, mesurable et vérifiable par quiconque lit la blockchain.

### 1.4 — Ce que le code existant supporte déjà

| Brique existante | Rôle dans le réseau de clusters | Fichier |
|:---|:---|:---|
| `submitter: Pubkey` dans `EpistemicAttestation` | Identité d'opérateur | `state.rs:18` |
| PDA seeds `[b"attestation", submitter, claim_hash]` | Isolation naturelle : 2 clusters → 2 PDA distinctes pour le même claim | `lib.rs` |
| `is_challenge` + `challenged_attestation` | Contestation inter-clusters | `state.rs:52-53` |
| `consensus_meta` (ADR-010) | Carte d'identité méthodologique d'un cluster | `pipeline.py` |
| `model_track_record` + Brier scores | Germe du système de réputation | `post_crystallization.py` |
| `infer_architecture_family()` | Mesure de diversité intra-cluster | `base.py` |
| `COMMUNITY_DECISION_REQUIRED` markers | Zones de gouvernance explicitement identifiées | `pipeline.py`, `post_crystallization.py`, `consensus_engine.py` |
| `response_deduplicator.py` | Détection Sybil intra-cluster (embedding cosine ≥ 0.95) | `response_deduplicator.py` |
| `CONFIDENCE_TIER_MAP` (4 tiers) | Système de classification déjà calibré pour le multi-source | `bridge.py` |

**Constat** : EPP n'a pas été conçu comme un outil qui pourrait devenir un réseau. Il a été conçu comme un protocole de réseau dont un seul nœud existe aujourd'hui.

---

## 2. Décision

### 2.1 — Principe : le Cluster comme unité atomique de décentralisation

Un Cluster EPP est défini par :

1. **Un opérateur** — une keypair Solana (ADR-008). Identité minimale, pseudonyme possible.
2. **Un manifeste** — document JSON signé déclarant la configuration du cluster (§2.2).
3. **Un track record** — historique cumulé d'attestations on-chain, mesurable par quiconque.

La confiance dans un cluster n'est pas déclarée, elle est **calculable** à partir des données on-chain. Deux observateurs indépendants qui lisent la même blockchain calculent le même score de réputation pour le même cluster.

### 2.2 — ClusterManifest : déclaration d'identité opérationnelle

```python
@dataclass
class ClusterManifest:
    """Déclaration publique d'un cluster EPP."""

    # Identité
    operator_pubkey: str                    # Pubkey Solana du submitter
    cluster_name: str                       # Nom lisible (ex: "EPP-BioMed-Singapore")
    cluster_version: str                    # Semver du pipeline (ex: "0.4.0")

    # Configuration déclarée
    models_declared: List[ModelDeclaration] # Modèles utilisés (id, family, params, quant)
    sources_declared: List[str]             # Sources déterministes actives (ex: ["ofac_sdn", "acled", "wikidata"])
    frames_supported: List[str]             # Frames métrologiques (ex: ["geopolitical_forecast_v1.0"])
    specialization: List[str]               # Domaines revendiqués (ex: ["geopolitics", "smart_contract_audit"])

    # Métadonnées
    created_at: float                       # Timestamp de création
    manifest_hash: str                      # SHA-256 du manifeste canonique (sorted keys, compact)
    signature: str                          # Signature Solana du manifest_hash par operator_pubkey

    # Optionnel
    description: str = ""                   # Description libre
    contact: str = ""                       # URL, email, ou PGP (optionnel, COMMUNITY_DECISION_REQUIRED)
    hardware_declaration: Optional[Dict] = None  # GPU, RAM, VRAM (optionnel, non vérifiable Phase 1)


@dataclass
class ModelDeclaration:
    """Déclaration d'un modèle dans un cluster."""
    model_id: str                           # ex: "mistral:7b"
    architecture_family: str                # ex: "mistral" (via infer_architecture_family)
    parameter_count: Optional[str] = None   # ex: "7B"
    quantization: Optional[str] = None      # ex: "Q4_K_M"
```

**Propriétés critiques** :

- Le manifeste est **déclaratif**, pas prescriptif. Un opérateur déclare ses modèles, mais le protocole ne vérifie pas (pour l'instant) que les modèles réellement utilisés correspondent. Cette vérification est un chantier Phase 3 (TEE/ZKP).
- Le `manifest_hash` est le SHA-256 du JSON canonique (sorted keys, compact, UTF-8) — même schéma que `source_anchor` (ADR-012).
- La `signature` est la signature Ed25519 du `manifest_hash` par la keypair du submitter. N'importe qui peut vérifier que le manifeste provient bien de l'opérateur déclaré.

### 2.3 — Ancrage on-chain du manifeste

**Phase 1 (hackathon)** : Le manifeste est stocké off-chain (SQLite + JSON signé publié). Le `manifest_hash` est référençable dans `consensus_meta` sous une nouvelle clé `cluster_manifest_hash`.

**Phase 2 (post-hackathon)** : Nouvelle instruction Anchor `register_cluster` créant un PDA :

```
seeds = [b"cluster", operator_pubkey]
```

Le PDA contient : `manifest_hash`, `created_at`, `last_updated`, `attestation_count`, `is_active`. Le manifeste complet reste off-chain (trop grand pour un PDA économique). La PDA sert de racine d'ancrage vérifiable.

**Phase 3** : Mise à jour du manifeste par le même opérateur uniquement (signature check). Historique des versions conservé via une table `cluster_manifest_history`.

### 2.4 — Divergence inter-clusters : signal de second ordre

Quand deux clusters attestent le même claim (même `claim_hash` au sens ADR-006), la divergence entre leurs verdicts est un signal épistémique de second ordre. Ce signal est plus riche que la divergence intra-cluster (entre modèles) car il capture des différences de configuration, de sources, et de méthodologie.

**Calcul** : Pour un `claim_hash` donné, un observateur effectue un `getProgramAccounts` avec filtre `memcmp` sur `claim_hash` (offset 41, 32 bytes — `client.py:CLAIM_HASH_OFFSET`), sans filtre sur `submitter`. Il obtient toutes les attestations de tous les clusters pour ce claim. La divergence est :

```
inter_cluster_divergence = max(scores) - min(scores)
```

Avec des métriques plus fines :

```python
@dataclass
class CrossClusterSignal:
    """Signal épistémique inter-clusters pour un claim donné."""

    claim_hash: str
    clusters_attesting: int                   # Nombre de clusters ayant attesté
    score_range: Tuple[float, float]          # (min_score, max_score)
    divergence: float                         # max - min
    mean_score: float                         # Moyenne pondérée (par réputation cluster)
    weighted_mean_score: float                # Moyenne pondérée par cluster reputation
    tier_distribution: Dict[str, int]         # {"sandbox": 1, "validated": 2, ...}
    sources_union: Set[str]                   # Union des sources déterministes utilisées
    models_union: Set[str]                    # Union des familles de modèles
    concordance_with_deterministic: Optional[float]  # Si source déterministe disponible
```

**Interprétation** :

| Divergence | Clusters | Signal |
|:---|:---|:---|
| Faible (< 0.10) | ≥ 3 | Convergence forte — confiance élevée |
| Modérée (0.10–0.30) | ≥ 2 | Zone d'incertitude — claim nécessite investigation |
| Forte (> 0.30) | ≥ 2 | Divergence significative — biais méthodologique ou claim intrinsèquement ambigu |
| N/A | 1 seul | Attestation non corroborée — confiance limitée au track record du cluster |

### 2.5 — Système de réputation calculable (Cluster Reputation Score)

La réputation d'un cluster est une fonction **calculable par quiconque** à partir des données on-chain et des manifestes publics. Aucun oracle de réputation n'est nécessaire — la blockchain EST l'oracle de réputation.

```python
@dataclass
class ClusterReputationScore:
    """Score de réputation d'un cluster, calculable on-chain."""

    operator_pubkey: str
    total_attestations: int                  # Volume brut
    age_days: int                            # Ancienneté du premier PDA

    # Précision historique
    brier_score_aggregate: float             # Brier score moyen sur les claims résolus
    accuracy_on_resolved: float              # % de verdicts corrects sur claims résolus

    # Diversité
    model_families_declared: int             # Familles distinctes dans le manifeste
    sources_declared: int                    # Sources déterministes actives
    frames_used: int                         # Frames métrologiques distincts utilisés

    # Résilience
    challenges_received: int                 # Nombre de challenges reçus (is_challenge PDAs)
    challenges_survived: int                 # Challenges où le verdict original a tenu
    survival_rate: float                     # challenges_survived / challenges_received

    # Concordance
    concordance_with_deterministic: float    # Corrélation avec sources déterministes (quand dispo)
    concordance_with_peers: float            # Corrélation avec la majorité des autres clusters

    # Score composite
    reputation_score: float                  # Score agrégé [0, 1]
```

**Formule du score composite** (COMMUNITY_DECISION_REQUIRED — poids initiaux proposés) :

```
reputation_score = (
    0.30 * accuracy_on_resolved +        # La précision est reine
    0.20 * concordance_with_deterministic + # Ancrage factuel
    0.15 * survival_rate +                # Résistance aux challenges
    0.15 * diversity_score +              # Diversité modèles + sources
    0.10 * log_volume_normalized +        # Le volume compte, mais décroissant
    0.10 * age_normalized                 # L'ancienneté stabilise
)
```

Les poids sont des paramètres de gouvernance (`COMMUNITY_DECISION_REQUIRED`). La formule est versionnée dans `consensus_meta` de chaque calcul de réputation.

### 2.6 — Requête cross-cluster (off-chain, Phase 1)

Le mécanisme de query cross-cluster utilise les capacités existantes de Solana :

```python
async def query_cross_cluster(
    claim_hash: str,
    client: "EppSolanaClient",
) -> List[Dict[str, Any]]:
    """
    Récupère toutes les attestations pour un claim_hash donné,
    tous clusters confondus.

    Utilise getProgramAccounts avec filtre memcmp sur claim_hash
    à l'offset CLAIM_HASH_OFFSET (41 bytes dans le layout state.rs).
    """
    # Le filtre memcmp ne filtre PAS sur submitter → retourne tous les clusters
    attestations = await client.query_attestations_by_claim(
        claim_hash=claim_hash,
        min_consensus=0.0,  # Tout récupérer
    )

    # Grouper par submitter (= cluster)
    by_cluster = defaultdict(list)
    for att in attestations:
        by_cluster[att["submitter"]].append(att)

    return by_cluster
```

**Point critique** : `query_attestations_by_claim()` dans `client.py` filtre déjà sur `claim_hash` via `memcmp`. Le code existant supporte nativement la requête cross-cluster sans modification.

---

## 3. Ce qui change

| Composant | Modification | Phase |
|:---|:---|:---|
| `services/cluster/manifest.py` | **NOUVEAU** — `ClusterManifest`, `ModelDeclaration`, `sign_manifest()`, `verify_manifest()`, `hash_manifest()` | Phase 1 |
| `services/cluster/reputation.py` | **NOUVEAU** — `ClusterReputationScore`, `compute_reputation()`, `CrossClusterSignal`, `compute_cross_cluster_signal()` | Phase 2 |
| `services/esmm/pipeline.py` | +`cluster_manifest_hash` dans `consensus_meta.methodology` | Phase 1 |
| `config.yaml` | +section `cluster` (name, specialization, description) | Phase 1 |
| `cli/epp_cli.py` | +commandes `epp cluster register`, `epp cluster show`, `epp cluster query <claim_hash>` | Phase 1-2 |
| `programs/epp/src/lib.rs` | +instruction `register_cluster` (PDA: `[b"cluster", submitter]`) | Phase 2 |
| `programs/epp/src/state.rs` | +struct `ClusterRegistration` (~128 bytes) | Phase 2 |
| `README_EN.md` | Réécriture intro : EPP comme protocole de réseau, pas outil centralisé | Phase 1 |
| `tests/` | +tests manifeste, signature, cross-cluster query, reputation | Phase 1-2 |

## 4. Ce qui ne change pas

- Structure on-chain `EpistemicAttestation` (462 bytes) — **aucune modification**. Le champ `submitter` sert déjà d'identifiant cluster.
- Claim hash (ADR-006) — immuable. Deux clusters attestant le même claim utilisent le même `claim_hash`.
- Pipeline `run_pipeline()` — inchangé. Le manifeste est un enrichissement de `consensus_meta`, pas une modification du flux.
- Tiers de confiance (ADR-005) — inchangés au niveau intra-cluster. Le cross-cluster produit un signal additionnel, pas un override.
- Semantic Fingerprinting (ADR-011-v2) — intra-cluster uniquement. Pas de merge inter-clusters.
- Sources déterministes (ADR-012) — chaque cluster configure ses propres sources. Pas de partage de snapshots.
- Challenge mechanism — déjà fonctionnel. Un cluster B challenge un cluster A via `is_challenge=true` + `challenged_attestation` pointant vers la PDA de A.

---

## 5. Contraintes d'implémentation

### 5.1 — Le manifeste est déclaratif, pas vérifiable (Phase 1-2)

Un opérateur peut déclarer utiliser 5 modèles et n'en utiliser qu'un seul. Le protocole ne vérifie pas — il fait confiance au track record. Si le cluster déclare une diversité qu'il n'a pas, ses Brier scores seront probablement mauvais, et sa réputation en souffrira.

**Phase 3** : TEE (Trusted Execution Environment) ou ZKP pour prouver que le pipeline a réellement été exécuté avec les modèles déclarés. C'est un chantier majeur, explicitement déféré.

### 5.2 — Pas de communication inter-clusters (Phase 1)

Les clusters ne communiquent pas entre eux. Chaque cluster fonctionne en isolation. Le signal inter-clusters est calculé a posteriori par un observateur qui lit la blockchain. C'est un choix délibéré :

- **Pas de gossip protocol** — les clusters n'ont pas besoin de se connaître.
- **Pas de routing** — un claim n'est pas "envoyé" à un cluster. L'opérateur choisit quels claims traiter.
- **Pas de consensus inter-clusters** — la divergence est le signal (Axiome 5), pas un problème à résoudre.

### 5.3 — La réputation est calculable, pas stockée on-chain (Phase 1-2)

Le `ClusterReputationScore` est un calcul off-chain effectué par quiconque lit les PDAs. Stocker la réputation on-chain introduirait un oracle de réputation — exactement le problème qu'EPP résout. La réputation reste un calcul pur, déterministe, reproductible.

**Phase 3** : Un "reputation indexer" pourrait publier des snapshots périodiques on-chain pour les consommateurs qui ne veulent pas recalculer. Mais le calcul reste toujours vérifiable indépendamment.

### 5.4 — Économie : la valeur est dans le track record, pas dans l'attestation

Un cluster ne monétise pas les attestations individuelles. La valeur économique réside dans :

1. **Le track record cumulé** — un cluster avec 10 000 attestations et 94% de précision sur les claims résolus a une valeur de réputation mesurable.
2. **La spécialisation** — un cluster spécialisé biomédecine avec des sources PubMed/ClinicalTrials intégrées produit des attestations que personne d'autre ne peut produire.
3. **La fraîcheur** — un cluster qui maintient des sources ACLED/Wikidata à jour produit des attestations plus fiables que celui qui ne le fait pas.

Modèles de monétisation possibles (`COMMUNITY_DECISION_REQUIRED`) :

- **Abonnement** : un protocole DeFi souscrit aux attestations d'un cluster de confiance.
- **Pay-per-query** : un smart contract consomme une attestation on-chain et paie le cluster émetteur.
- **Staking** : un opérateur stake des SOL sur la qualité de son track record. Si ses attestations sont régulièrement challengées avec succès, son stake est slashé.
- **Grant/subvention** : un écosystème (fondation Solana, DAO recherche) finance un cluster spécialisé.

### 5.5 — Isolation du module cluster

Le répertoire `services/cluster/` est un module autonome. Il importe `services/solana/client.py` pour les queries on-chain et `services/esmm/attestation.py` pour les types. **Aucun module existant n'importe `services/cluster/`**. Le cluster est un enrichissement du pipeline, pas une modification.

---

## 6. Risques

| Risque | Probabilité | Mitigation |
|:---|:---|:---|
| Sybil clusters : un acteur crée 100 clusters pour gonfler le consensus apparent | Moyenne | Le coût de création de PDA (rent exemption) crée une barrière économique minimale. Le track record individuel de chaque cluster est évaluable. Un cluster sans historique n'a pas de poids. Phase 3 : staking requis. |
| Manifeste mensonger : un cluster déclare des modèles qu'il n'utilise pas | Haute (Phase 1-2) | Accepté explicitement. Le track record corrige : un cluster menteur produira des attestations de mauvaise qualité. Phase 3 : TEE/ZKP. |
| Collusion inter-clusters : plusieurs opérateurs coordonnent leurs verdicts | Faible | Les Brier scores punissent les erreurs coordonnées quand la ground truth émerge. La diversité des sources déterministes rend la collusion coûteuse à maintenir. |
| Coût d'attestation on-chain à grande échelle | Moyenne | 462 bytes/PDA × rent exemption Solana. Atténuation : batch submissions, compression via merkle roots (Phase 3), sélection des claims à ancrer. |
| Fragmentation : trop de clusters avec trop peu d'attestations chacun | Faible | La spécialisation crée des niches naturelles. Un cluster biomédecine n'est pas en compétition avec un cluster géopolitique. |
| Absence de ground truth pour calibrer la réputation | Haute (Phase 1) | Seuls les claims avec résolution vérifiable (élections, données ACLED, Wikidata) contribuent au Brier score. Les claims non résolus ne comptent pas dans le score de précision. |

---

## 7. Impact sur la roadmap

La roadmap est reformulée avec le cluster comme unité fondamentale :

| Phase | Nom | Description | Cluster |
|:---|:---|:---|:---|
| **1** (déc. 2025 – fév. 2026) ✅ | Premier cluster | Pipeline ESMM + Solana devnet. Prouver que le protocole fonctionne. | 1 cluster (fondateur) |
| **1.5** (mars 2026) ✅ | Multi-domaine | Smart contract audit + géopolitique + sources déterministes. Prouver que le protocole est domain-agnostique. | 1 cluster, 3 domaines |
| **2** (post-hackathon) | Multi-cluster | ClusterManifest on-chain, cross-cluster queries, reputation indexer. Prouver que le réseau fonctionne. | 3-10 clusters |
| **2.5** | Contestation active | Protocole de challenge formalisé entre clusters. La divergence inter-clusters devient un signal de premier ordre. | 10-50 clusters |
| **3** | Gouvernance | DAO pour les paramètres de gouvernance (`COMMUNITY_DECISION_REQUIRED` zones). TEE/ZKP pour vérification des manifestes. Staking. | 50+ clusters |

---

## 8. FAQ — Questions ouvertes

**Q1 — Pourquoi ne pas utiliser un token de réputation ?**
Un token de réputation introduit de la spéculation financière dans un système épistémique. La réputation dans EPP est un *calcul*, pas un actif. Elle ne se transfère pas, ne se trade pas, ne se délègue pas. Elle se mérite par le track record et se perd par les mauvaises attestations. `COMMUNITY_DECISION_REQUIRED` : la communauté pourrait décider d'un token ultérieurement, mais le système doit fonctionner sans.

**Q2 — Comment un nouveau cluster gagne-t-il de la crédibilité ?**
De la même façon qu'un nouveau chercheur : en produisant des attestations vérifiables sur des claims dont la ground truth est connue. Le dataset de calibration (contrôles positifs/négatifs comme Yemen/Suisse, Trump 2024, Earth orbits Sun) sert de benchmark public. Un cluster qui score bien sur les contrôles gagne en crédibilité initiale.

**Q3 — Les clusters sont-ils en compétition ou en coopération ?**
Les deux. Ils sont en compétition pour la réputation (le meilleur Brier score gagne en crédibilité). Ils sont en coopération involontaire : la diversité des approches produit un signal collectif plus riche que n'importe quel cluster isolé. C'est une sélection naturelle épistémique.

**Q4 — Comment un consommateur (DeFi protocol, DAO) choisit-il quel cluster consommer ?**
Par le score de réputation calculable, filtré par spécialisation. Un protocole DeFi qui a besoin d'attestations de conformité sanctions choisira le cluster avec le meilleur track record sur les frames `compliance_sanctions_v1.0`. Le choix est transparent et auditable.

**Q5 — Quel est le lien avec l'Axiome 5 (Divergence is the Signal) ?**
L'Axiome 5 s'appliquait initialement aux divergences entre modèles au sein d'un cluster. ADR-017 l'élève au niveau du réseau : la divergence entre clusters est un signal épistémique de second ordre, plus riche que la divergence intra-cluster car elle capture des différences de méthodologie, de sources, et de configuration.

**Q6 — Le `METADATACHANNEL` mentionné dans la vision produit s'intègre-t-il ici ?**
Oui. Le METADATACHANNEL est le mécanisme par lequel de nouvelles sources de données rejoignent le réseau. Chaque source déterministe est un canal. Chaque cluster choisit quels canaux activer. Un cluster qui active plus de canaux fiables produit de meilleures attestations. Le METADATACHANNEL est aux sources ce que le multi-modèle est aux LLMs : un marché de la diversité.

---

## 9. Références

### Internes
- ADR-005 : Tiers de confiance multi-critères — base du scoring intra-cluster
- ADR-006 : Claim hash SHA-256 déterministe — identifiant cross-cluster d'un claim
- ADR-008 : Authentification submitter — identité minimale d'un opérateur
- ADR-010 : Traçabilité méthodologique — carte d'identité méthodologique d'un cluster
- ADR-012 : Bifurcation déterministe — sources autoritaires configurables par cluster
- ADR-014 : Audit smart contracts — premier cas d'usage de spécialisation cluster
- Axiome 5 : Divergence is the Signal — fondement théorique du cross-cluster signal

### Données empiriques
- `scenario_jiang` (2026-03-11) : JIANG-RESOLVED-01 — démonstration du biais LLM partagé corrigible par source déterministe
- `scenario_6_1` : Napoléon 0.96 SUPPORTED (faux positif) — même pattern que JIANG-RESOLVED-01
- `benchmark_heavy` : phi4/deepseek-r1 over-contesting (~0.45 uniforme) — divergence inter-familles comme signal

### Codebase — points d'ancrage
- `programs/epp/src/state.rs:18` : `submitter: Pubkey` — identité cluster on-chain
- `programs/epp/src/lib.rs` : PDA seeds — isolation naturelle inter-clusters
- `services/solana/client.py:CLAIM_HASH_OFFSET` : offset memcmp pour query cross-cluster
- `services/esmm/post_crystallization.py` : hook track record — base du système de réputation
- `services/providers/base.py:infer_architecture_family()` : mesure de diversité

---

## 10. Ordre d'implémentation recommandé

### Phase 1 — Hackathon (avant 6 avril)

1. `services/cluster/manifest.py` — `ClusterManifest`, `ModelDeclaration`, `hash_manifest()`, `sign_manifest()`, `verify_manifest()`
2. `config.yaml` — section `cluster` (name, specialization, description)
3. `services/esmm/pipeline.py` — ajouter `cluster_manifest_hash` dans `consensus_meta.methodology`
4. `cli/epp_cli.py` — commande `epp cluster show` (affiche le manifeste local)
5. `README_EN.md` — réécriture de l'introduction avec la vision cluster
6. Tests : manifeste, signature, hash, intégration consensus_meta (≥10 tests)

### Phase 2 — Post-hackathon

7. `services/cluster/reputation.py` — `ClusterReputationScore`, `compute_reputation()`
8. `services/cluster/cross_cluster.py` — `CrossClusterSignal`, `query_cross_cluster()`
9. Instruction Anchor `register_cluster` + struct `ClusterRegistration`
10. `cli/epp_cli.py` — `epp cluster register`, `epp cluster query <claim_hash>`
11. Tests cross-cluster, reputation (≥20 tests)

### Phase 3 — Gouvernance

12. DAO pour les `COMMUNITY_DECISION_REQUIRED` zones
13. TEE/ZKP pour vérification des manifestes
14. Staking mechanism
15. Reputation indexer on-chain (snapshots périodiques)
