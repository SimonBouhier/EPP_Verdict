# EPP — Epistemic Proof Protocol

**Colosseum Hackathon Submission — Infrastructure Track**

---

## The Gap Nobody Sees

Chainlink solves the price. Pyth solves the speed. Both answer: *what is the number?*

Nobody answers: *how much should you trust this claim — and why?*

There are 121 oracle and AI products on Solana. Not one measures the calibration quality of AI consensus. Not one records which models produced a verdict, under what conditions, with what level of disagreement. Not one treats the *pattern of disagreement* as a signal worth preserving.

The Bank for International Settlements calls this an epistemological gap, not a technical one. Caldarelli (2025) asks whether AI can solve the blockchain oracle problem. His answer: no — but it can help mitigate it.

EPP is the infrastructure for that answer.

---

## What EPP Does

EPP is a verifiable AI consensus engine. Multiple AI models independently assess a claim through structured adversarial deliberation, and the protocol anchors the result — including the full methodology that produced it — as a cryptographic attestation on Solana.

The output is not a vote count. It is an *epistemic measurement*: a 5-dimensional signature capturing agreement, consistency, centrality, stability, and diversity — with the complete audit trail of how it was produced.

### The ESMM Deliberation Architecture

Most multi-model debate frameworks let every model see every other model's response. This produces what the literature calls "conformity-driven collapse" — models converge toward the dominant opinion regardless of correctness.

ESMM prevents this through **epistemic isolation**:

**1 — ASSESS.** Each model evaluates the claim independently. No model sees any peer output. Responses are SHA-256 committed before proceeding.

**2 — CHALLENGE.** Circular adversarial rotation. Model[i] sees *only* Model[(i+1)%N]'s verdict and must contest it. This prevents cascade conformism while forcing engagement with exactly one opposing perspective.

**3 — ADJUDICATE.** All evidence from ASSESS and CHALLENGE feeds into weighted synthesis. The output is a 5-dimensional epistemic signature with vote entropy as an explicit anti-conformism metric.

Additional safeguards: heterogeneous models are enforced (minimum 2 architecture families — e.g., Mistral + Llama, not 3× the same architecture). Claims are auto-classified (empirical, definitional, speculative, normative) and handled with different scoring thresholds. The protocol knows what it *cannot* adjudicate — an opinion like "pineapple on pizza is delicious" scores 0.29 and is flagged as normative.

### Three Modes, One Protocol

**EXPLORE** — Open-ended knowledge extraction. Models build a semantic knowledge graph through multi-cycle deliberation.

**VERIFY** — Factual claim verification. A claim enters ASSESS → CHALLENGE → ADJUDICATE and produces a signed attestation.

**DETERMINISTIC** — For facts that don't need debate. Sanctions screening (OFAC, OpenSanctions, EU CFSP), carbon credit validation (Verra VCS), institutional data. EPP queries the authoritative source, hashes the raw response, and produces an attestation without invoking LLMs — because adding uncertainty to a binary fact is noise, not epistemology.

---

## What Makes It Different

Several projects anchor AI-assisted resolution or confidence metrics on-chain. Pyth publishes confidence intervals on price feeds. UMA resolves qualitative claims via optimistic dispute on Ethereum. Supra's Threshold AI Oracles use multi-agent LLM committees with BLS threshold signatures.

EPP differs on three specific dimensions that no competitor implements:

### 1. Calibration Quality as Output

Every existing system treats consensus as binary: threshold reached or not, dispute resolved or not, confidence within bounds or not. Pyth's confidence interval is statistical spread of publisher prices, not epistemic calibration. UMA's resolution is pass/fail — was the proposer correct? Supra's signature says "quorum agreed" — not how well-calibrated the agreement is.

EPP uses Brier scores and proper scoring rules that *incentivize honest probability estimates*. The degree and quality of disagreement is the primary on-chain signal, not a side effect.

### 2. Full Methodology Traceability

No oracle records: which specific models assessed the claim (IDs, versions, architecture families), what parameters were used (temperature, system prompt, framing), what metrological frame was applied, individual model outputs alongside the aggregate, and the full consensus metadata.

Every EPP attestation carries all of this in a 462-byte PDA on Solana. Two independent observers reading the same blockchain can reproduce the exact conditions that produced a verdict. The deliberation is not just recorded — it is independently auditable.

### 3. Diversity as Signal, Not Noise

Existing systems penalize disagreement. Pyth rejects outlier publishers. Switchboard slashes deviants. UMA treats disputes as friction to be minimized.

EPP inverts this: architectural diversity is *rewarded* because epistemically diverse panels are empirically better-calibrated. The protocol enforces minimum 2 architecture families and measures diversity as one of the 5 signature dimensions. Disagreement is data.

---

## Proof It Works: The Epistemic Flywheel

AI models know nothing about events after their training data was compiled. EPP exploits this limitation.

The protocol connects AI deliberation to authoritative data sources (NIST, OFAC, Wikidata, ACLED, Verra). When verified data exists for a claim, the Epistemic Flywheel injects it into the models' reasoning context — not as a directive, but as evidence they are free to contest.

**Measured result** — claim: "Donald Trump won the 2024 US presidential election":

| Stage | Score | Verdict | Time |
|:------|:------|:--------|:-----|
| LLMs alone (no context) | 0.43 | CONTESTED | ~105s |
| + Flywheel (Wikidata injected) | 0.89 | SUPPORTED | ~110s |
| Subsequent queries (graph cache) | 0.89 | SUPPORTED | <1ms |

Same models. Same claim. No retraining. **+0.46 score delta from injecting one verified fact.** Three orders of magnitude in cost reduction on subsequent queries.

The system detects what it doesn't know, what it got wrong, and when external data corrected it — and every stage is attested on-chain with the full methodology trace.

---

## Domain Generality — Demonstrated

EPP is not a single-purpose tool. The protocol is domain-agnostic by design:

**Geopolitics** — Yemen conflict: 0.96 SUPPORTED. Switzerland conflict: 0.62 CONTESTED. Stable across multiple independent runs with different model combinations.

**Smart Contract Audit** — Reentrancy vulnerability (SWC-107): detected at 0.55 CONTESTED. Safe functions: 0.79 SUPPORTED. Auto-classified by vulnerability type.

**Compliance** — Four sanctions adapters integrated (OFAC, OpenSanctions, EU CFSP, Verra VCS). Deterministic mode: zero LLM compute, cryptographic hash of source response.

**Physical Sciences** — NIST adapter for fundamental constants. Flywheel corrects AI hallucinations on physical claims against authoritative measurements.

**Edge Cases** — "Pineapple on pizza is delicious": 0.29, flagged normative. "The Moon is made of cheese": zero attestations, graceful refusal. Napoleon's height myth: exposes shared training bias across all models as measurable data.

---

## What Has Been Built (5 weeks, solo builder)

| Metric | Value |
|:-------|:------|
| Test suite | [VERIFY: run `pytest tests/ -q` for current count] |
| Architecture decisions | 18 ADRs |
| AI models tested | 6 (Mistral, Llama 3.1, Gemma 3, DeepSeek-R1, phi4-reasoning, granite3.3) |
| Deterministic sources | 7 integrated |
| Domains demonstrated | 5 (epistemic, audit, geopolitics, compliance, physics) |
| Pipeline modes | EXPLORE + VERIFY + DETERMINISTIC + FLYWHEEL |
| Benchmark claims evaluated | 37+ across 7 datasets |
| Flywheel effect | +0.46 demonstrated (0.43 → 0.89) |
| Solana program | Anchor/Rust, deployed on devnet |
| On-chain footprint | 462-byte PDA per attestation |

Everything runs locally on a consumer GPU (RTX 4090) with open-source models via Ollama. No API keys. No cloud dependency. No vendor lock-in.

---

## The Vision: Epistemic Clusters

EPP is designed as a network, not a tool. The unit of decentralization is the **Epistemic Cluster** — an autonomous protocol instance with its own models, data sources, and metrological frames, operated by an identifiable Solana keypair.

Trust is not declared — it *emerges* from the cumulative track record, calculable by anyone directly from the blockchain. Two observers reading the same chain compute the same reputation score.

When two clusters attest the same claim with different results, the divergence is not a failure — it is an inter-cluster measurement capturing differences in methodology, sources, and model selection.

The architecture is ready: PDA seeds include `submitter` for natural per-cluster isolation. `consensus_meta` is the cluster's methodological fingerprint. The challenge mechanism (`is_challenge` + `challenged_attestation`) enables inter-cluster contestation. Only one node exists today — but every on-chain field was designed for a multi-cluster world.

---

## Why Infrastructure. Why Public Goods.

EPP is not an AI product. It is an **epistemic primitive** — a new on-chain signal that any protocol can consume.

A DeFi protocol reads EPP attestations to assess qualitative risk before executing. A compliance firm operates a specialized cluster with auditable Brier accuracy. A governance DAO consumes calibrated consensus before voting on subjective proposals. None of these consumers need to trust EPP — they verify the methodology on-chain and evaluate the track record themselves.

This is open infrastructure: permissionless, composable, verifiable. The protocol is MIT-licensed. The attestation format is public. Any operator can run a cluster. Any consumer can read the chain.

---

## The Thesis

> *Everyone solves the answer. Nobody solves how much to trust it.*
>
> *EPP makes AI models argue under controlled conditions, measures the quality of their disagreement with proper scoring rules, records the full methodology, and anchors the proof on Solana — permanently. One protocol. Any domain. Any model. Verifiable by anyone.*
>
> *The oracle that doesn't trust itself.*
