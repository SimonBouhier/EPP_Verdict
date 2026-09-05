---
title: "Competitive Landscape"
editUrl: false
---

> **Historical material.** Preserved in its original context. Former blockchain, cluster and sprint claims do not define the current project. Read the [current scope](/current-status/) and [ADR-022](/adrs/adr-022-post-blockchain-refocus/).

> **Verdict**: nobody is building exactly this. Several projects occupy
> adjacent territory; EPP's specific combination is a genuine gap.
>
> *Originally compiled as `Key Takeaways for EPP.md` in the sprint
> working dir. Migrated 2026-04-23.*

## Closest Competitors

| Player | What they do | What EPP does differently |
|:-------|:-------------|:--------------------------|
| **Supra Threshold AI Oracles** | Multi-agent LLM committees + threshold BLS signatures | Binary consensus (quorum or not). No disagreement measurement, no Brier scores, no calibration |
| **APRO ($AT)** | Two-layer AI oracle (LLM parsing + watchdog auditing), BNB-native | Data feed verification. Rejects outliers, doesn't measure WHY they disagree |
| **Chainlink** | Exploring multi-model aggregation in DON infrastructure | Conceptual stage. Treats AI like another price feed — aggregates to median, no epistemic signal |
| **ORA Protocol** ($20M funded) | Verifiable single-model inference via opML on Ethereum | Single model, not multi-model consensus |
| **Ritual** ($25M funded) | Decentralized AI compute (zkML/opML/TEE) | Infrastructure layer, not an oracle. No consensus or calibration primitive |
| **ZkAGI** | ZK proofs for AI inference on Solana | Privacy-focused single-model verification. No ensemble, no scoring rules |

## The Core Insight

Every AI oracle treats consensus as binary — threshold reached or not.
Nobody measures the *quality or degree* of disagreement. Nobody uses
proper scoring rules. Nobody records methodology traceability.

**EPP's moat**: disagreement is signal, not noise. Brier scores,
diversity bonuses, and full methodology traceability are entirely absent
from every competitor.

## Market Context

- Oracle TVS: $58B+ (Chainlink alone: $31B)
- AI-in-blockchain: $657M (2025) → $3.46B (2034) at 22.9% CAGR
- Prediction market volume: $27.9B+ in the past year
- Grid saturation: 121 oracle+AI products on Solana / 101 distinct
  roots — but EPP's specific niche (epistemic calibration) is empty
- Accelerator portfolio: no direct overlap found

## Key Archive Grounding

- **"Economics of disagreement"** (Soklakov, arXiv) — Treats
  disagreement between probabilistic models as an investable signal.
  Direct theoretical foundation for EPP.
- **"Two thousand years of the oracle problem"** (Caldarelli, arXiv 2025) — The trust problem EPP addresses is literally ancient.
- **Solana Attestation Service** (May 2025) — Natural composability layer for EPP's on-chain attestations.
- **"Beyond Binary Rewards"** (arXiv 2025) — Uses Brier scores to train LMs that reason about their own uncertainty. Validates EPP's scoring approach.

## Bootstrap Path

EPP can be both sides of the market at launch — run its own model
ensemble, generate attestations. Best entry point: prediction market
resolution on Solana (concrete pain, measurable improvement over
UMA-style 24-48h optimistic disputes).

---

## Tier 1: Directly EPP-Adjacent (AI consensus + on-chain attestation)

### Epistemia (Cypherpunk Sep 2025)

The closest project to EPP in the entire corpus. A decentralized
knowledge protocol where 10+ independent AI models each produce
evidence-backed versions of knowledge, with every past revision stored
on-chain. Uses a wagering mechanism where users bet on which AI-generated
version is correct.

**Key difference from EPP**: Epistemia gamifies knowledge curation via
NFTs and token-burning; EPP measures epistemic quality via Brier scores
and diversity bonuses. Epistemia asks "which AI version wins the bet?"
EPP asks "how well-calibrated is the consensus and how much do they
disagree?"

### Predict Link Oracle (Cypherpunk Sep 2025)

Hybrid oracle with LLM agents scanning 40+ verified sources (AP, Reuters,
CoinGecko) to auto-submit proposals with confidence scores. Sub-2-hour
finality vs 24-48h traditional optimistic oracles. Closest to EPP on the
oracle side — but uses AI for data aggregation from external sources,
not multi-model epistemic measurement on claims. Single-proposer model,
not multi-model consensus.

### Edge Bounty (Cypherpunk Sep 2025)

Turns smartphones into verifiable inference nodes. Workers run CLIP
embeddings on-device, submit signed execution proofs, and a server
reaches r=3 cosine consensus before settling USDC payouts. Records IPFS
result URI on-chain. The only project using multi-node inference
consensus with a verification threshold — conceptually parallel to EPP's
multi-model agreement, but for embedding similarity (deterministic), not
epistemic claims (subjective).

## Tier 2: Verifiable AI Output + On-Chain Proof

- **Signed AI** (Breakout Apr 2025) — Infrastructure for AI agents to cryptographically sign decisions and record them as cNFTs on Solana. Could serve as a composable signing layer for EPP attestations.
- **CortexHub** (Cypherpunk Sep 2025) — Decentralized LLM model hosting with verifiable weight history ("HuggingFace on-chain"). Complementary: EPP could use CortexHub-style provenance to prove which model weights were used in each attestation.
- **Whispr** (Cypherpunk Sep 2025) — Privacy-native, on-device AI copilot in Rust. Hashes session metadata onto Solana as verifiable proof of local AI reasoning. "Proof of reasoning" concept — lighter than EPP (single model, hash-only).
- **Habili Agent Network** (Breakout Apr 2025) — Decentralized protocol for autonomous AI agent discovery and verifiable activity logs. Adjacent for multi-agent coordination, not epistemic claim assessment.

## Tier 3: Truth Verification + AI-Assisted Fact-Checking

- **EventDAO** (Cypherpunk Sep 2025) — Community-driven truth verification of real-world events using AI + blockchain + staking. EPP removes the crowd and replaces it with calibrated multi-model consensus.
- **404 Fake Not Found** (Breakout Apr 2025) — AI agents flag misinformation, users verify content to earn TRUE tokens. Crowd-mediated, not multi-LLM calibrated.
- **Certana** (Cypherpunk Sep 2025) — Digital content authenticity via ML and ZK-proofs. Specific to media authenticity, not general claims.

## Tier 4: On-Chain Attestation Infrastructure (Non-AI)

- **Attest Protocol** (Radar Sep 2024, Public Goods Award $10K) — Unified trust and reputation infrastructure for on-chain attestations. "HTTPS on the blockchain." General-purpose attestation primitive — EPP could build on top of this or SAS for its attestation layer.
- **Chronotrace** (Cypherpunk Sep 2025) — Cross-chain cryptographic attestations with timestamped verification. Attestation infrastructure for content provenance.

## Tier 5: AI Agent Evaluation + Benchmarking

- **Forge AI** (Breakout Apr 2025, HM $5K) — Competitive arena for testing autonomous AI agents. EPP's Brier scores are a more rigorous version of this evaluation concept.
- **Excalead** (Cypherpunk Sep 2025, HM) — Automated smart contract audits using AI + formal verification. Subscription model. Shares the "AI-generated assessment with on-chain proof" pattern.
- **Project Plutus** (Breakout Apr 2025, 2nd Place AI $20K) — Simplified deployment of autonomous AI agents on Solana. AI deployment infra EPP's models would need.

## Tier 6: Peripheral but Noteworthy

- **Pearl Protocol** — Federated learning + differential privacy on Solana. Privacy-preserving training, not inference verification.
- **LayerNet** (Renaissance Mar 2024) — Listed "lack of verifiable AI" as a problem tag. Early framing.
- **Tessera** (Breakout) — Decentralized inference on consumer GPUs with probabilistic verification. Compute distribution, not epistemic measurement.
- **PrivAgent** (Cypherpunk) — Multi-agent privacy system (ZK compression, MEV protection). Multi-agent for privacy, not consensus measurement.

---

## Key Takeaways for EPP

1. **Epistemia is the project to study most closely.** It uses 10+ independent AI models on the same knowledge claim with on-chain versioning — the closest architectural cousin. Different mechanism (wagering/NFTs vs. Brier score calibration). Reach out to the builder.
2. **Edge Bounty's r=3 cosine consensus** is the only multi-node inference verification pattern in the corpus — validates that the "compare multiple inference outputs" primitive has builder interest.
3. **No project measures epistemic disagreement.** Not one. The gap is confirmed across 3 parallel queries and 40+ results.
4. **Attestation infrastructure exists** (Attest Protocol, SAS, Signed AI) — EPP doesn't need to build the attestation layer from scratch. Compose with what's there.
5. **AI track at Breakout had 501 submissions** (16.7% of 2,992 projects). LLM in tech stack: 170 projects. Almost all are AI-assisted tools, not AI-verified outputs. The verification layer is the missing primitive.
