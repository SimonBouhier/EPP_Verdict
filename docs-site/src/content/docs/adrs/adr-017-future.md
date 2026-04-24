---
title: "ADR-017: Epistemic Cluster Network — Multi-Operator Architecture"
description: "Status: Proposed (v1 — architectural vision)"
---
**Date**: 2026-03-11
**Status**: Proposed (v1 — architectural vision)
**Dependencies**: ADR-005 (multi-criteria tiers), ADR-006 (claim hash), ADR-008 (submitter authentication), ADR-010 (methodology traceability), ADR-012 (deterministic bifurcation)
**Axioms invoked**: 1 (model obsolescence), 2 (graph survival), 3 (regression-cut transparency), 4 (local computation, on-chain proof), 5 (divergence is the signal)

---

## 1. Context

### 1.1 — The implicit centralization problem

EPP today operates as a single-operator pipeline: one submitter (Solana keypair), one set of local models, one SQLite graph, one attestation database. The protocol is designed for decentralization (ADR-008, `COMMUNITY_DECISION_REQUIRED` markers), but the fundamental unit of decentralization is undefined.

The current roadmap (Phase 1 → Phase 2 → Phase 3) describes a transition "centralized now, decentralized later." This narrative is structurally weak: it promises decentralization without naming the entity that decentralizes. An oracle that promises to decentralize is indistinguishable from a centralized oracle that delays indefinitely.

### 1.2 — The founding observation

The `scenario_jiang` run from 2026-03-11 illustrates the problem and the solution simultaneously:

- **JIANG-RESOLVED-01** — "Donald Trump won the 2024 US presidential election": CONTESTED 0.403 (`verdict_ok: false`). A proven historical fact that 3 models (mistral, llama3.1, gemma3) do not confirm. Cause: shared knowledge cutoff.
- **Wikidata** on the same claim: `wikidata_status: "found"`, `wikidata_score: 0.85`. The deterministic source corrects the LLM bias.

If a second operator had run the same claim with different models (phi4-reasoning, deepseek-r1, granite3.3), two scenarios: either the same error — confirming a documented systemic bias, not a local artifact; or a divergent result — producing an exploitable second-order signal.

**Neither of these signals is possible in a single-operator system.**

The same pattern repeats in `benchmark_heavy` (ADR-014): reasoning models over-contest everything uniformly (~0.45), while 7B models discriminate better. This inter-family divergence IS the signal — but today it remains internal to a single operator. Lifted to the network level, it becomes a market mechanism.

### 1.3 — The concept: Epistemic Cluster

An **EPP Cluster** is an autonomous instance of the protocol operated by an identifiable submitter (Solana keypair). Each cluster:

- Chooses its LLM models (type, quantization, count)
- Configures its deterministic sources (OFAC, ACLED, Wikidata, etc.)
- Selects its metrological frames
- Produces on-chain attestations traceable via `consensus_meta` (ADR-010)

Trust is not declared — it **emerges** from each cluster's cumulative track record. Competition between clusters on the same claims produces an epistemic equilibrium price: the best collective approximation of truth, measurable and verifiable by anyone reading the blockchain.

### 1.4 — What the existing code already supports

| Existing building block | Role in the cluster network | File |
|:---|:---|:---|
| `submitter: Pubkey` in `EpistemicAttestation` | Operator identity | `state.rs:18` |
| PDA seeds `[b"attestation", submitter, claim_hash]` | Natural isolation: 2 clusters → 2 distinct PDAs for the same claim | `lib.rs` |
| `is_challenge` + `challenged_attestation` | Inter-cluster contestation | `state.rs:52-53` |
| `consensus_meta` (ADR-010) | Methodology fingerprint card of a cluster | `pipeline.py` |
| `model_track_record` + Brier scores | Seed of the reputation system | `post_crystallization.py` |
| `infer_architecture_family()` | Intra-cluster diversity measure | `base.py` |
| `COMMUNITY_DECISION_REQUIRED` markers | Governance zones explicitly identified | `pipeline.py`, `post_crystallization.py`, `consensus_engine.py` |
| `response_deduplicator.py` | Intra-cluster Sybil detection (embedding cosine ≥ 0.95) | `response_deduplicator.py` |
| `CONFIDENCE_TIER_MAP` (4 tiers) | Classification system already calibrated for multi-source | `bridge.py` |

**Observation**: EPP was not designed as a tool that could become a network. It was designed as a network protocol of which only one node exists today.

---

## 2. Decision

### 2.1 — Principle: the Cluster as atomic unit of decentralization

An EPP Cluster is defined by:

1. **An operator** — a Solana keypair (ADR-008). Minimal identity, pseudonym possible.
2. **A manifest** — signed JSON document declaring the cluster configuration (§2.2).
3. **A track record** — cumulative history of on-chain attestations, measurable by anyone.

Trust in a cluster is not declared, it is **computable** from on-chain data. Two independent observers reading the same blockchain compute the same reputation score for the same cluster.

### 2.2 — ClusterManifest: declaration of operational identity

```python
@dataclass
class ClusterManifest:
    """Public declaration of an EPP cluster."""

    # Identity
    operator_pubkey: str                    # Submitter's Solana pubkey
    cluster_name: str                       # Human-readable name (e.g.: "EPP-BioMed-Singapore")
    cluster_version: str                    # Pipeline semver (e.g.: "0.4.0")

    # Declared configuration
    models_declared: List[ModelDeclaration] # Models used (id, family, params, quant)
    sources_declared: List[str]             # Active deterministic sources (e.g.: ["ofac_sdn", "acled", "wikidata"])
    frames_supported: List[str]             # Metrological frames (e.g.: ["geopolitical_forecast_v1.0"])
    specialization: List[str]               # Claimed domains (e.g.: ["geopolitics", "smart_contract_audit"])

    # Metadata
    created_at: float                       # Creation timestamp
    manifest_hash: str                      # SHA-256 of canonical manifest (sorted keys, compact)
    signature: str                          # Solana signature of manifest_hash by operator_pubkey

    # Optional
    description: str = ""                   # Free description
    contact: str = ""                       # URL, email, or PGP (optional, COMMUNITY_DECISION_REQUIRED)
    hardware_declaration: Optional[Dict] = None  # GPU, RAM, VRAM (optional, not verifiable Phase 1)


@dataclass
class ModelDeclaration:
    """Declaration of a model in a cluster."""
    model_id: str                           # e.g.: "mistral:7b"
    architecture_family: str                # e.g.: "mistral" (via infer_architecture_family)
    parameter_count: Optional[str] = None   # e.g.: "7B"
    quantization: Optional[str] = None      # e.g.: "Q4_K_M"
```

**Critical properties**:

- The manifest is **declarative**, not prescriptive. An operator declares its models, but the protocol does not verify (for now) that the actually used models match. This verification is a Phase 3 effort (TEE/ZKP).
- The `manifest_hash` is the SHA-256 of canonical JSON (sorted keys, compact, UTF-8) — same scheme as `source_anchor` (ADR-012).
- The `signature` is the Ed25519 signature of `manifest_hash` by the submitter's keypair. Anyone can verify the manifest indeed comes from the declared operator.

### 2.3 — On-chain anchoring of the manifest

**Phase 1 (hackathon)**: The manifest is stored off-chain (SQLite + signed JSON published). The `manifest_hash` is referenceable in `consensus_meta` under a new `cluster_manifest_hash` key.

**Phase 2 (post-hackathon)**: New Anchor instruction `register_cluster` creating a PDA:

```
seeds = [b"cluster", operator_pubkey]
```

The PDA contains: `manifest_hash`, `created_at`, `last_updated`, `attestation_count`, `is_active`. The full manifest stays off-chain (too large for an economical PDA). The PDA serves as a verifiable anchor root.

**Phase 3**: Manifest update by the same operator only (signature check). Version history kept via a `cluster_manifest_history` table.

### 2.4 — Inter-cluster divergence: second-order signal

When two clusters attest the same claim (same `claim_hash` per ADR-006), the divergence between their verdicts is a second-order epistemic signal. This signal is richer than intra-cluster divergence (between models) because it captures differences in configuration, sources, and methodology.

**Computation**: For a given `claim_hash`, an observer performs `getProgramAccounts` with `memcmp` filter on `claim_hash` (offset 41, 32 bytes — `client.py:CLAIM_HASH_OFFSET`), without filtering on `submitter`. They get all attestations from all clusters for this claim. Divergence is:

```
inter_cluster_divergence = max(scores) - min(scores)
```

With finer metrics:

```python
@dataclass
class CrossClusterSignal:
    """Inter-cluster epistemic signal for a given claim."""

    claim_hash: str
    clusters_attesting: int                   # Number of clusters that attested
    score_range: Tuple[float, float]          # (min_score, max_score)
    divergence: float                         # max - min
    mean_score: float                         # Weighted average (by cluster reputation)
    weighted_mean_score: float                # Average weighted by cluster reputation
    tier_distribution: Dict[str, int]         # {"sandbox": 1, "validated": 2, ...}
    sources_union: Set[str]                   # Union of deterministic sources used
    models_union: Set[str]                    # Union of model families
    concordance_with_deterministic: Optional[float]  # If deterministic source available
```

**Interpretation**:

| Divergence | Clusters | Signal |
|:---|:---|:---|
| Low (< 0.10) | ≥ 3 | Strong convergence — high confidence |
| Moderate (0.10–0.30) | ≥ 2 | Uncertainty zone — claim needs investigation |
| High (> 0.30) | ≥ 2 | Significant divergence — methodological bias or intrinsically ambiguous claim |
| N/A | only 1 | Uncorroborated attestation — confidence limited to the cluster's track record |

### 2.5 — Computable reputation system (Cluster Reputation Score)

A cluster's reputation is a function **computable by anyone** from on-chain data and public manifests. No reputation oracle is needed — the blockchain IS the reputation oracle.

```python
@dataclass
class ClusterReputationScore:
    """Cluster reputation score, computable on-chain."""

    operator_pubkey: str
    total_attestations: int                  # Raw volume
    age_days: int                            # Age of first PDA

    # Historical accuracy
    brier_score_aggregate: float             # Mean Brier score on resolved claims
    accuracy_on_resolved: float              # % of correct verdicts on resolved claims

    # Diversity
    model_families_declared: int             # Distinct families in the manifest
    sources_declared: int                    # Active deterministic sources
    frames_used: int                         # Distinct metrological frames used

    # Resilience
    challenges_received: int                 # Number of challenges received (is_challenge PDAs)
    challenges_survived: int                 # Challenges where the original verdict held
    survival_rate: float                     # challenges_survived / challenges_received

    # Concordance
    concordance_with_deterministic: float    # Correlation with deterministic sources (when available)
    concordance_with_peers: float            # Correlation with the majority of other clusters

    # Composite score
    reputation_score: float                  # Aggregated score [0, 1]
```

**Composite score formula** (COMMUNITY_DECISION_REQUIRED — proposed initial weights):

```
reputation_score = (
    0.30 * accuracy_on_resolved +        # Accuracy reigns
    0.20 * concordance_with_deterministic + # Factual anchoring
    0.15 * survival_rate +                # Resistance to challenges
    0.15 * diversity_score +              # Models + sources diversity
    0.10 * log_volume_normalized +        # Volume matters, but with diminishing returns
    0.10 * age_normalized                 # Seniority stabilizes
)
```

The weights are governance parameters (`COMMUNITY_DECISION_REQUIRED`). The formula is versioned in the `consensus_meta` of every reputation computation.

### 2.6 — Cross-cluster query (off-chain, Phase 1)

The cross-cluster query mechanism uses Solana's existing capabilities:

```python
async def query_cross_cluster(
    claim_hash: str,
    client: "EppSolanaClient",
) -> List[Dict[str, Any]]:
    """
    Retrieves all attestations for a given claim_hash,
    across all clusters.

    Uses getProgramAccounts with memcmp filter on claim_hash
    at offset CLAIM_HASH_OFFSET (41 bytes in the state.rs layout).
    """
    # The memcmp filter does NOT filter on submitter → returns all clusters
    attestations = await client.query_attestations_by_claim(
        claim_hash=claim_hash,
        min_consensus=0.0,  # Get everything
    )

    # Group by submitter (= cluster)
    by_cluster = defaultdict(list)
    for att in attestations:
        by_cluster[att["submitter"]].append(att)

    return by_cluster
```

**Critical point**: `query_attestations_by_claim()` in `client.py` already filters on `claim_hash` via `memcmp`. Existing code natively supports cross-cluster queries without modification.

---

## 3. What changes

| Component | Modification | Phase |
|:---|:---|:---|
| `services/cluster/manifest.py` | **NEW** — `ClusterManifest`, `ModelDeclaration`, `sign_manifest()`, `verify_manifest()`, `hash_manifest()` | Phase 1 |
| `services/cluster/reputation.py` | **NEW** — `ClusterReputationScore`, `compute_reputation()`, `CrossClusterSignal`, `compute_cross_cluster_signal()` | Phase 2 |
| `services/esmm/pipeline.py` | +`cluster_manifest_hash` in `consensus_meta.methodology` | Phase 1 |
| `config.yaml` | +section `cluster` (name, specialization, description) | Phase 1 |
| `cli/epp_cli.py` | +commands `epp cluster register`, `epp cluster show`, `epp cluster query <claim_hash>` | Phase 1-2 |
| `programs/epp/src/lib.rs` | +instruction `register_cluster` (PDA: `[b"cluster", submitter]`) | Phase 2 |
| `programs/epp/src/state.rs` | +struct `ClusterRegistration` (~128 bytes) | Phase 2 |
| `README_EN.md` | Intro rewrite: EPP as network protocol, not centralized tool | Phase 1 |
| `tests/` | +tests for manifest, signature, cross-cluster query, reputation | Phase 1-2 |

## 4. What does not change

- On-chain `EpistemicAttestation` structure (462 bytes) — **no modification**. The `submitter` field already serves as cluster identifier.
- Claim hash (ADR-006) — immutable. Two clusters attesting the same claim use the same `claim_hash`.
- Pipeline `run_pipeline()` — unchanged. The manifest is an enrichment of `consensus_meta`, not a flow modification.
- Confidence tiers (ADR-005) — unchanged at the intra-cluster level. Cross-cluster produces an additional signal, not an override.
- Semantic Fingerprinting (ADR-011-v2) — intra-cluster only. No inter-cluster merge.
- Deterministic sources (ADR-012) — each cluster configures its own sources. No snapshot sharing.
- Challenge mechanism — already functional. A cluster B challenges a cluster A via `is_challenge=true` + `challenged_attestation` pointing to A's PDA.

---

## 5. Implementation constraints

### 5.1 — The manifest is declarative, not verifiable (Phase 1-2)

An operator can declare using 5 models and use only one. The protocol does not verify — it trusts the track record. If the cluster declares diversity it does not have, its Brier scores will likely be poor, and its reputation will suffer.

**Phase 3**: TEE (Trusted Execution Environment) or ZKP to prove that the pipeline was actually executed with the declared models. This is a major effort, explicitly deferred.

### 5.2 — No inter-cluster communication (Phase 1)

Clusters do not communicate with each other. Each cluster operates in isolation. The inter-cluster signal is computed a posteriori by an observer who reads the blockchain. This is a deliberate choice:

- **No gossip protocol** — clusters don't need to know each other.
- **No routing** — a claim is not "sent" to a cluster. The operator chooses which claims to handle.
- **No inter-cluster consensus** — divergence is the signal (Axiom 5), not a problem to solve.

### 5.3 — Reputation is computable, not stored on-chain (Phase 1-2)

The `ClusterReputationScore` is an off-chain computation performed by anyone reading the PDAs. Storing reputation on-chain would introduce a reputation oracle — exactly the problem EPP solves. Reputation remains a pure, deterministic, reproducible computation.

**Phase 3**: A "reputation indexer" could publish periodic snapshots on-chain for consumers who don't want to recompute. But the computation always remains independently verifiable.

### 5.4 — Economy: value lies in the track record, not in the attestation

A cluster does not monetize individual attestations. Economic value lies in:

1. **The cumulative track record** — a cluster with 10,000 attestations and 94% accuracy on resolved claims has measurable reputation value.
2. **Specialization** — a biomedical cluster with integrated PubMed/ClinicalTrials sources produces attestations no one else can produce.
3. **Freshness** — a cluster maintaining up-to-date ACLED/Wikidata sources produces more reliable attestations than one that does not.

Possible monetization models (`COMMUNITY_DECISION_REQUIRED`):

- **Subscription**: a DeFi protocol subscribes to a trusted cluster's attestations.
- **Pay-per-query**: a smart contract consumes an on-chain attestation and pays the issuing cluster.
- **Staking**: an operator stakes SOL on the quality of its track record. If its attestations are regularly successfully challenged, its stake is slashed.
- **Grant/subsidy**: an ecosystem (Solana Foundation, research DAO) funds a specialized cluster.

### 5.5 — Cluster module isolation

The `services/cluster/` directory is an autonomous module. It imports `services/solana/client.py` for on-chain queries and `services/esmm/attestation.py` for types. **No existing module imports `services/cluster/`**. The cluster is a pipeline enrichment, not a modification.

---

## 6. Risks

| Risk | Probability | Mitigation |
|:---|:---|:---|
| Sybil clusters: an actor creates 100 clusters to inflate apparent consensus | Medium | The PDA creation cost (rent exemption) creates a minimal economic barrier. Each cluster's individual track record is evaluable. A cluster without history has no weight. Phase 3: required staking. |
| Lying manifest: a cluster declares models it doesn't use | High (Phase 1-2) | Explicitly accepted. The track record corrects: a lying cluster will produce poor-quality attestations. Phase 3: TEE/ZKP. |
| Inter-cluster collusion: multiple operators coordinate verdicts | Low | Brier scores punish coordinated errors when ground truth emerges. Diversity of deterministic sources makes collusion expensive to maintain. |
| Large-scale on-chain attestation cost | Medium | 462 bytes/PDA × Solana rent exemption. Mitigation: batch submissions, compression via Merkle roots (Phase 3), claim-selection for anchoring. |
| Fragmentation: too many clusters with too few attestations each | Low | Specialization creates natural niches. A biomedical cluster does not compete with a geopolitical cluster. |
| Absence of ground truth to calibrate reputation | High (Phase 1) | Only claims with verifiable resolution (elections, ACLED data, Wikidata) contribute to the Brier score. Unresolved claims do not count in the accuracy score. |

---

## 7. Roadmap impact

The roadmap is reformulated with the cluster as the fundamental unit:

| Phase | Name | Description | Cluster |
|:---|:---|:---|:---|
| **1** (Dec 2025 – Feb 2026) ✅ | First cluster | ESMM pipeline + Solana devnet. Prove the protocol works. | 1 cluster (founder) |
| **1.5** (March 2026) ✅ | Multi-domain | Smart contract audit + geopolitics + deterministic sources. Prove the protocol is domain-agnostic. | 1 cluster, 3 domains |
| **2** (post-hackathon) | Multi-cluster | On-chain ClusterManifest, cross-cluster queries, reputation indexer. Prove the network works. | 3-10 clusters |
| **2.5** | Active contestation | Formalized challenge protocol between clusters. Inter-cluster divergence becomes a first-order signal. | 10-50 clusters |
| **3** | Governance | DAO for governance parameters (`COMMUNITY_DECISION_REQUIRED` zones). TEE/ZKP for manifest verification. Staking. | 50+ clusters |

---

## 8. FAQ — Open questions

**Q1 — Why not use a reputation token?**
A reputation token introduces financial speculation into an epistemic system. Reputation in EPP is a *computation*, not an asset. It does not transfer, trade, or delegate. It is earned by track record and lost by bad attestations. `COMMUNITY_DECISION_REQUIRED`: the community could decide on a token later, but the system must work without one.

**Q2 — How does a new cluster gain credibility?**
The same way as a new researcher: by producing verifiable attestations on claims whose ground truth is known. The calibration dataset (positive/negative controls like Yemen/Switzerland, Trump 2024, Earth orbits Sun) serves as a public benchmark. A cluster that scores well on the controls gains initial credibility.

**Q3 — Are clusters in competition or cooperation?**
Both. They compete for reputation (the best Brier score gains credibility). They cooperate involuntarily: the diversity of approaches produces a richer collective signal than any isolated cluster. This is epistemic natural selection.

**Q4 — How does a consumer (DeFi protocol, DAO) choose which cluster to consume?**
By the computable reputation score, filtered by specialization. A DeFi protocol needing sanctions-compliance attestations will choose the cluster with the best track record on `compliance_sanctions_v1.0` frames. The choice is transparent and auditable.

**Q5 — What is the link with Axiom 5 (Divergence is the Signal)?**
Axiom 5 initially applied to divergences between models within a cluster. ADR-017 lifts it to the network level: divergence between clusters is a second-order epistemic signal, richer than intra-cluster divergence because it captures differences in methodology, sources, and configuration.

**Q6 — Does the `METADATACHANNEL` mentioned in the product vision integrate here?**
Yes. The METADATACHANNEL is the mechanism by which new data sources join the network. Each deterministic source is a channel. Each cluster chooses which channels to activate. A cluster activating more reliable channels produces better attestations. The METADATACHANNEL is to sources what multi-model is to LLMs: a marketplace of diversity.

---

## 9. References

### Internal
- ADR-005: Multi-criteria confidence tiers — basis of intra-cluster scoring
- ADR-006: Deterministic SHA-256 claim hash — cross-cluster claim identifier
- ADR-008: Submitter authentication — minimal operator identity
- ADR-010: Methodology traceability — methodology fingerprint card of a cluster
- ADR-012: Deterministic bifurcation — authoritative sources configurable per cluster
- ADR-014: Smart contract audit — first cluster-specialization use case
- Axiom 5: Divergence is the Signal — theoretical foundation of the cross-cluster signal

### Empirical data
- `scenario_jiang` (2026-03-11): JIANG-RESOLVED-01 — demonstration of shared LLM bias correctable by deterministic source
- `scenario_6_1`: Napoleon 0.96 SUPPORTED (false positive) — same pattern as JIANG-RESOLVED-01
- `benchmark_heavy`: phi4/deepseek-r1 over-contesting (~0.45 uniform) — inter-family divergence as signal

### Codebase — anchor points
- `programs/epp/src/state.rs:18`: `submitter: Pubkey` — on-chain cluster identity
- `programs/epp/src/lib.rs`: PDA seeds — natural inter-cluster isolation
- `services/solana/client.py:CLAIM_HASH_OFFSET`: memcmp offset for cross-cluster query
- `services/esmm/post_crystallization.py`: track-record hook — basis of the reputation system
- `services/providers/base.py:infer_architecture_family()`: diversity measure

---

## 10. Recommended implementation order

### Phase 1 — Hackathon (before April 6)

1. `services/cluster/manifest.py` — `ClusterManifest`, `ModelDeclaration`, `hash_manifest()`, `sign_manifest()`, `verify_manifest()`
2. `config.yaml` — section `cluster` (name, specialization, description)
3. `services/esmm/pipeline.py` — add `cluster_manifest_hash` in `consensus_meta.methodology`
4. `cli/epp_cli.py` — command `epp cluster show` (displays the local manifest)
5. `README_EN.md` — intro rewrite with the cluster vision
6. Tests: manifest, signature, hash, `consensus_meta` integration (≥10 tests)

### Phase 2 — Post-hackathon

7. `services/cluster/reputation.py` — `ClusterReputationScore`, `compute_reputation()`
8. `services/cluster/cross_cluster.py` — `CrossClusterSignal`, `query_cross_cluster()`
9. Anchor instruction `register_cluster` + struct `ClusterRegistration`
10. `cli/epp_cli.py` — `epp cluster register`, `epp cluster query <claim_hash>`
11. Tests cross-cluster, reputation (≥20 tests)

### Phase 3 — Governance

12. DAO for `COMMUNITY_DECISION_REQUIRED` zones
13. TEE/ZKP for manifest verification
14. Staking mechanism
15. On-chain reputation indexer (periodic snapshots)
