---
title: "EPP — One Protocol, Any Truth"
description: "Blockchains can verify that a transaction happened. They cannot verify that a claim is true."
---
> **Pitch document.** Three minutes, three acts, one claim. For the full
> epistemological and architectural narrative see [`WHITEPAPER.md`](/whitepaper/).
> For the live dashboard: [epp-verdict.vercel.app](https://epp-verdict.vercel.app).

---

## The Problem No One Has Solved

Blockchains can verify that a transaction happened. They cannot verify that a claim is true.

Oracles solved data feeds — prices, timestamps, sports scores. But the world runs on claims that aren't data feeds: *Is this entity sanctioned? Is this carbon credit legitimate? Is this smart contract vulnerable? Did this election actually happen?*

Today, these questions are answered by centralized authorities, single-model AI outputs, or human committees. None produce a result that is simultaneously verifiable, reproducible, and anchored on-chain with the methodology that produced it.

EPP does.

---

## What EPP Is

EPP is a consensus protocol for knowledge claims, anchored on Solana.

Multiple AI models — architecturally distinct, independently queried — deliberate through structured adversarial cycles on any verifiable assertion. The result is a cryptographic attestation recording not just *what* was concluded, but *how*, *by whom*, *under what methodology*, and *with what degree of agreement*.

Every attestation carries a 5-dimensional epistemic signature: agreement, semantic consistency, centrality, stability, relation diversity. Every attestation is produced under a versioned metrological frame that makes results from different methodologies explicitly non-comparable. Every attestation is stored as a 462-byte PDA on Solana devnet — today, live, verifiable.

The protocol doesn't care what domain the claim belongs to. It cares whether the claim is decidable, what sources are authoritative, and whether the models agree.

---

## Architecture in One Sentence

**A domain-agnostic kernel that takes any claim, routes it through the right path (AI deliberation or authoritative source lookup), and produces a verifiable attestation — same pipeline, same axioms, same on-chain format, regardless of the claim's subject matter.**

Three paths, one output:

| Path | When | Example |
|:-----|:-----|:--------|
| **VERIFY** | Multi-model deliberation needed | *"Solana effective TPS exceeds 3000"* |
| **DETERMINISTIC** | Authoritative source exists | *"Entity X is on the OFAC sanctions list"* |
| **FLYWHEEL** | Both — verified data injected into AI reasoning | *"Trump won the 2024 election"* |

The kernel (cycle manager, consensus engine, crystallization) never sees the domain. It processes text and probabilities. The domain lives in two interchangeable components: the **adapter** (fetches external data) and the **metrological frame** (defines the measurement methodology). Adding a new domain = one adapter + one frame. The kernel, the on-chain program, the signature, the consensus math — unchanged.

---

## Live Proof: Three Demonstrated Domains, One Protocol

### Act 1 — The Flywheel (knowledge catch-up)

**Claim:** *"Donald Trump won the 2024 US presidential election."*

LLMs alone score **0.43 — CONTESTED**. Their training data ended before the election. They don't know.

EPP queries Wikidata (zero credentials, CC-0 data), retrieves the verified fact, hashes the response as a `source_anchor`, and injects it into the LLM reasoning context during VERIFY.

Result: **0.89 — SUPPORTED**. Same models. Same claim. No retraining. Delta: **+0.46**.

The corrected attestation caches. Next query: **< 1 ms, zero compute**. The graph learned.

Verified end-to-end in the dashboard at `/flywheel?run=flywheel_v2_20260411_135551.json`.

### Act 2 — Deterministic sources (compliance / RWA)

**Claim:** *"Verra VCS project #985 is a registered carbon credit project."*

EPP queries the Verra Registry (public API, zero credentials), retrieves project data for Cordillera Azul National Park (1.35M hectares, Peru, REDD+), hashes the raw response, crystallizes a deterministic attestation.

Result: `source_anchor` = SHA-256 of the Verra response. `epistemic_type = deterministic`. Stored on-chain. Any third party can re-query Verra, re-hash, and verify the anchor matches byte-for-byte.

Same pipeline as Act 1. Different adapter. Different frame. Same 462-byte PDA.

### Act 3 — Smart contract audit (structural claims)

A Solidity function with a known reentrancy vulnerability (SWC-107). EPP slices the contract, submits each function to 3+ models under the `smartcontract_audit_v1.0` frame.

Finding: **7B models discriminate (0.55 CONTESTED on the vulnerable function, 0.79 SUPPORTED on safe ones); reasoning models over-contest uniformly (~0.45)**. The divergence between model families IS the signal — not a failure mode to average away.

---

## What Makes EPP Different (three primitives nobody implements)

**1. Calibration quality as primary output.** Every existing oracle treats consensus as binary. Pyth's confidence interval is statistical spread, not epistemic calibration. UMA's dispute resolution is pass/fail. Supra's threshold BLS says *"quorum agreed"* — not *how well-calibrated*. EPP uses Brier scores and proper scoring rules: the degree and quality of disagreement is the primary on-chain signal.

**2. Full methodology traceability.** Every attestation carries which models assessed (IDs, versions, architecture families), parameters (temperature, system prompt, framing), frame hash, individual model outputs, consensus metadata. Two independent observers reading the same blockchain can identify the exact conditions that produced a verdict. Pyth, UMA, Switchboard, Chainlink, Supra — none do this.

**3. Diversity as signal, not noise.** Existing systems penalize disagreement (outlier rejection, slashing deviants). EPP rewards architectural heterogeneity: minimum 2 families required, diversity is one of the 5 signature dimensions, diversity bonus in scoring. Convergence across different architectures carries more epistemic weight than three instances of the same model agreeing with themselves.

---

## Why This Matters

| Sector | Problem | EPP primitive |
|:-------|:--------|:--------------|
| **DeFi** | Insurance needs to know if events happened; prediction markets need resolution; lending needs to verify real-world collateral | Verifiable deliberation trace replacing multisigs and single-feed oracles |
| **Compliance / AML** | Sanctions screening is binary but multi-source. A single OFAC API call is not an audit trail | Multiple authoritative sources queried, responses hashed, concordance on-chain. The attestation IS the compliance record |
| **AI Governance** | Single-model AI outputs are black boxes | AI disagreement made measurable and permanent; when model families diverge, the divergence is recorded, not averaged away |
| **DAO governance** | Voting on qualitative questions depends on opaque information | Composable attestations readable by any contract without operator permission |

---

## What Exists Today (verifiable now)

| Metric | Value | Proof |
|:-------|:------|:------|
| Live dashboard | `https://epp-verdict.vercel.app` | Vercel production, auto-redeploy on push |
| Test suite | **908 passed**, 11 skipped, 0 failed | `pytest tests/ -q` |
| Architecture decisions | **20 ADRs** | `docs/adr/ADR-*.md` |
| On-chain attestations | **12 pushed** to devnet | `data/devnet_pushed.json` + Solana Explorer |
| Solana program | Live on devnet | `9QtybfyZQFhra1D6S3NtD6jD4z2Z3wcYmf4YXETq8bSD`, deployed slot 450099166 |
| AI models tested | 6 (Mistral, Llama 3.1, Gemma 3, DeepSeek-R1, phi4-reasoning, gpt-oss:20b) | |
| Deterministic sources integrated | 7 (Wikidata, OFAC, OpenSanctions, EU CFSP, Verra VCS, ACLED, NIST) | `services/sources/adapters/` |
| Metrological frames | 7 predefined + custom | `services/solana/metrological_frame.py` |
| Flywheel delta demonstrated | **+0.46** (0.43 → 0.89) | `demos/benchmark_runs/flywheel_v2_*.json` |
| Epistemic cache | < 1 ms on cache hit | ADR-013 |
| Formal verification | Lean 4 — **6 substantive theorems** (tier `iff` + cumulativity) + 7 regression tests + 2 type-level invariants | `Formal/` (ADR-020 + [`docs/audit/`](docs/audit/)) |
| On-chain taxonomy | V2 — 3 categories, Lean 4-ready | ADR-019 |
| Pipeline modes | EXPLORE + VERIFY + DETERMINISTIC + FLYWHEEL | `services/esmm/pipeline.py` |

**Built by one person during the Colosseum sprint window — formal project start at commit [`f12a922`](https://github.com/SimonBouhier/EPP_Verdict/commit/f12a922) (2026-02-13), forking the ESMM kernel from prior personal LLM-orchestration exploration. Consumer GPU. No VC funding. No team. No formal CS or math background — just a logical mind, scientific transparency, and a belief that making AI models disagree on purpose produces something more honest than making them agree.**

---

## The Five Axioms

1. **Model Obsolescence** — Models are consumables, not infrastructure. Any LLM enters or leaves without breaking the protocol.
2. **Metrological Sovereignty** — Every attestation declares its measurement frame. No frame, no comparison.
3. **Regression Cut Transparency** — Version boundaries are explicit, never hidden. Different methodologies produce explicitly non-comparable results.
4. **Local Computation, On-Chain Proof** — AI runs locally (privacy, cost, no vendor lock-in). Only the cryptographic proof goes on-chain.
5. **Divergence is the Signal** — Disagreement between model families is more epistemically valuable than a unanimous verdict. Uniformity is a failure mode, not a feature.

---

## What Comes Next

**Immediate (post-Colosseum):**
- Interactive dashboard submission flow (form → live pipeline run → on-chain push)
- Public `/onchain` feed extended beyond the initial 12 curated attestations
- README / whitepaper / pitch split (shipped with this document)

**Medium-term (6 months):**
- Formal verification of remaining invariants — INV-3 PDA uniqueness, INV-5 regression cut isolation, INV-7 Brier proper scoring (ADR-020 roadmap)
- Epistemic Cluster network (ADR-017) — inter-cluster reputation via on-chain Brier track records
- Additional deterministic source integrations (EU CFSP endpoint migration, OpenSanctions cloud)

**Long-term vision:**
- LiveBench on-chain — every attestation a benchmark data point with full provenance, a reference infrastructure for evaluating AI model performance in an adversarial, domain-specific setting that cannot be gamed because it was never curated in the first place
- The graph that trains models *on disagreement* — see the concept essay [`docs/positioning/the_negative_space.md`](/positioning/the-negative-space/)

---

## The Pitch in One Paragraph

EPP is a protocol that turns any verifiable question into a cryptographic attestation on Solana. Multiple AI models deliberate, authoritative sources anchor, and the result — a 5-dimensional epistemic signature — is stored on-chain for anyone to verify. The same kernel handles sanctions screening, carbon credit validation, election verification, and smart contract auditing without modification. What changes between domains is an adapter and a frame, not the protocol. **Today, live and verifiable: 908 tests, 20 ADRs, 12 attestations on Solana devnet, a +0.46 flywheel delta, a Lean 4-ready on-chain taxonomy, and a public dashboard at [epp-verdict.vercel.app](https://epp-verdict.vercel.app).** Built by one person. Ready for a team.

---

> *Everyone solves the answer. Nobody solves how much to trust it.*
>
> *EPP makes AI models argue under controlled conditions, measures the quality of their disagreement with proper scoring rules, records the full methodology, anchors the result on verified data, and stores the proof on Solana — permanently. One protocol. Any domain. Any model. Verifiable by anyone.*
>
> *The oracle that doesn't trust itself.*
