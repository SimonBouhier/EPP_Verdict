# EPP — Epistemic Proof Protocol
## Pitch Vision v3

---

### The Stakes: The Trust Gap No Oracle Has Filled

Blockchain technology promises systems where blind trust is no longer necessary. But it depends on "oracles" to import information about the real world. Today's oracles handle numerical data — a token price, a timestamp, a sports score. When it comes to adjudicating complex claims or verifying facts, no protocol today produces a reliable, transparent, verifiable proof of *how much the answer should be trusted*.

In 2022 alone, DeFi protocols lost $403 million to oracle manipulation. The Bank for International Settlements identifies this as an epistemological gap, not a technical one. Caldarelli (2025) asks whether AI can solve the blockchain oracle problem — his answer: no, but it can help mitigate it.

There are 121 oracle and AI products on Solana. Several anchor AI-assisted resolution or confidence metrics on-chain. Pyth publishes confidence intervals on price feeds. UMA resolves qualitative claims via optimistic dispute on Ethereum. Supra's Threshold AI Oracles use multi-agent LLM committees with BLS threshold signatures.

None of them measure the *calibration quality* of AI consensus. None record the full methodology that produced a verdict. None treat the pattern of disagreement as a signal worth preserving on-chain. Every system treats consensus as binary — threshold reached or not, dispute resolved or not, confidence within bounds or not.

The gap is not "qualitative claims on-chain." The gap is **epistemic calibration as an on-chain primitive.**

EPP fills that gap.

---

### The Solution: A Machine for Manufacturing Verifiable Trust

EPP is a verifiable AI consensus engine. Multiple AI models independently assess a claim through structured adversarial deliberation, and the protocol anchors the result — including the full methodology that produced it — as a cryptographic attestation on Solana.

The output is not a vote count or a probability. It is an *epistemic measurement*: a 5-dimensional signature capturing agreement, consistency, centrality, stability, and diversity — with the complete audit trail of how it was produced.

Instead of blindly trusting a single AI, EPP:

- **Orchestrates structured adversarial deliberation** where architecturally diverse AI models evaluate independently, challenge each other's reasoning under epistemic isolation, and reach consensus through a three-phase protocol (ASSESS → CHALLENGE → ADJUDICATE).

- **Measures the quality of disagreement** using proper scoring rules (Brier scores, Shannon entropy, vote dispersion) that incentivize honest probability estimates — not just what the models concluded, but how calibrated and how diverse their path to that conclusion was.

- **Anchors the result on Solana** as a 462-byte PDA carrying the full epistemic signature, methodology metadata, and metrological frame hash — cryptographic, immutable, and verifiable by anyone with a blockchain explorer.

- **Makes the entire deliberation auditable.** Every attestation records which models were used (IDs, versions, architecture families), what parameters were applied (temperature, system prompt, framing), the metrological frame, individual model outputs, and the complete consensus metadata. This transforms AI from a black box into an independently reproducible process.

The system also knows what it *doesn't* know. An opinion ("pineapple on pizza is delicious") is detected as normative and scored at 0.29 — the protocol refuses to adjudicate taste. An absurdity ("the Moon is made of cheese") produces zero attestations — graceful refusal. A historical myth (Napoleon's height) exposes shared training bias across all models, producing it as measurable data rather than hiding it.

---

### The ESMM Deliberation Architecture

Most multi-agent debate frameworks (Du et al. 2023, LLM-Agora, A-HMAD) operate as open forums: every model sees every other model's response, leading to what Choi et al. (2025) identify as "conformity-driven collapse" — agents converge toward the dominant opinion regardless of its correctness.

ESMM (Epistemic Structured Multi-Model) takes a different approach: **structured adversarial deliberation with epistemic isolation.**

Three sequential phases, each with distinct prompts and objectives:

**1 — ASSESS.** Each model evaluates the claim independently. No model sees any peer output. Responses are SHA-256 committed before proceeding (commit-reveal protocol). This establishes a clean baseline — each model's judgment exists before it can be contaminated by social proof.

**2 — CHALLENGE.** Circular adversarial rotation. Model[i] sees *only* Model[(i+1) mod N]'s verdict and must contest it. This prevents cascade conformism while forcing each model to engage with exactly one opposing perspective. The rotation is circular, not random — every model both challenges and is challenged, with no privileged position.

**3 — ADJUDICATE.** Weighted synthesis. All evidence from ASSESS and CHALLENGE feeds into collective adjudication. The output is a 5-dimensional epistemic signature:
- **Agreement** — how strongly the models converge
- **Consistency** — how stable their positions are across phases
- **Centrality** — how close each model is to the aggregate position
- **Stability** — how much positions shifted between ASSESS and ADJUDICATE
- **Diversity** — how architecturally heterogeneous the deliberating panel is

Vote entropy serves as an explicit anti-conformism metric: high entropy means genuine disagreement, not groupthink.

**Key architectural differences from existing frameworks:**

- **Epistemic isolation**: no model ever sees all peers' outputs simultaneously. This is the structural guarantee against conformity-driven collapse.
- **Heterogeneous models enforced**: minimum 2 architecture families required (e.g., Mistral + Llama, not 3× GPT-4). Architectural monoculture is treated as a methodological flaw, not a configuration choice.
- **Claim classification**: empirical, definitional, speculative, and normative claims are auto-detected and scored with different thresholds. The protocol does not pretend all claims are equal.
- **Commit-reveal**: initial responses are cryptographically committed before the debate phase begins. This makes post-hoc rationalization detectable.
- **On-chain anchoring**: the full consensus metadata — not just the verdict — is stored with the attestation, making the deliberation process independently auditable by anyone reading the blockchain.

The result is not a probability or a vote count — it is a structured epistemic attestation with traceable methodology, stored permanently on Solana.

### Three Modes, One Protocol

**EXPLORE** — Open-ended knowledge extraction. Models build a semantic knowledge graph through divergent, debate, and meta-reflection cycles. Each extracted triplet (subject-predicate-object) is weighted by structural consensus: Brier scores, diversity bonuses, semantic fingerprinting. The graph persists across sessions and model generations.

**VERIFY** — Factual claim verification. A claim enters the ASSESS → CHALLENGE → ADJUDICATE pipeline and produces a signed 5-dimensional epistemic attestation. This is EPP's core mode for producing verifiable verdicts.

**DETERMINISTIC** (ADR-012) — For facts that don't need debate. Sanctions screening (OFAC, OpenSanctions, EU CFSP), carbon credit validation (Verra VCS), institutional registries. EPP queries the authoritative external source, hashes the raw API response, and produces a traceable attestation without invoking LLMs — because adding uncertainty to a binary fact is not epistemology, it is noise.

---

### What Makes EPP Different: Three Primitives Nobody Implements

A thorough competitive scan — across the Colosseum hackathon corpus (5,400+ projects), funded competitors (ORA at $20M, Ritual at $25M, Allora on Cosmos), academic research, and the broader oracle ecosystem — confirms that EPP's specific combination is a genuine gap. Here is what differentiates it on each dimension:

**1. Calibration Quality as Primary Output**

Every existing system treats consensus as binary. Pyth's confidence interval is statistical spread of publisher prices — not epistemic calibration. UMA's dispute resolution is pass/fail: was the proposer correct? Supra's threshold BLS signature says "quorum agreed" — not how well-calibrated the agreement was, or how much the individual agents disagreed before signing.

EPP uses Brier scores and proper scoring rules that *incentivize honest probability estimates*. The degree and quality of disagreement — not just its existence — is the primary on-chain signal. A claim with 0.89 consensus from 3 models that genuinely debated is epistemically different from 0.89 from 3 models that copied each other. EPP measures and preserves that difference.

**2. Full Methodology Traceability**

No oracle — Pyth, Switchboard, Chainlink, Supra, UMA — records per-attestation: which specific models assessed the claim (IDs, versions, architecture families), what parameters were used (temperature, system prompt, framing), what metrological frame was applied (how the question was posed), individual model outputs alongside the aggregate, and the full consensus metadata including vote entropy and diversity scores.

Every EPP attestation carries all of this. Two independent observers reading the same blockchain can identify the exact conditions that produced a verdict — and determine whether those conditions were methodologically sound. The deliberation is not just recorded; it is independently auditable.

**3. Diversity as Signal, Not Noise**

Existing systems penalize disagreement. Pyth rejects outlier publishers. Switchboard slashes deviants. UMA treats disputes as friction to minimize. The implicit assumption everywhere: disagreement is a problem to be eliminated.

EPP inverts this. Architectural diversity is *rewarded* because epistemically diverse panels are empirically better-calibrated. The protocol enforces minimum 2 architecture families, measures diversity as one of the 5 signature dimensions, and applies a diversity bonus in scoring. When models from different architecture families (Mistral vs. Llama vs. Gemma) reach the same conclusion independently, that convergence carries more epistemic weight than three instances of the same model agreeing with themselves.

**The closest conceptual neighbor** in the Colosseum corpus is Epistemia (Cypherpunk Sep 2025) — a decentralized knowledge protocol where 10+ independent AI models each produce evidence-backed versions of knowledge, with revisions stored on-chain. But Epistemia uses a wagering mechanism (users bet on which AI-generated version is correct); EPP measures calibration quality directly via Brier scores. Epistemia asks "which version wins the bet?" — EPP asks "how well-calibrated is the consensus and how much do they genuinely disagree?" The first is a market mechanism. The second is an instrument of measurement.

---

### The Innovation Engine: The Epistemic Flywheel

AI models have a structural limitation: they know nothing about events that occurred after their training data was compiled. This is not a bug — it is a fundamental property of statistical language models.

EPP does not suffer this limitation. It exploits it.

The protocol connects AI deliberation to authoritative, verifiable data sources — scientific databases (NIST), institutional registries (OFAC, EU sanctions), knowledge bases (Wikidata), conflict event data (ACLED). When a verified data point exists for a claim, the Epistemic Flywheel automatically injects it into the AI models' reasoning context during the VERIFY pass — not as a directive, but as factual evidence they are free to contest.

**The result is measurable.** On the claim "Donald Trump won the 2024 US presidential election":

| Stage | Score | Verdict | Cost | Time |
|:------|:------|:--------|:-----|:-----|
| LLMs alone (no context) | 0.43 | CONTESTED | 3 models × full deliberation | ~105s |
| + Flywheel (Wikidata injected) | 0.89 | SUPPORTED | 3 models × full deliberation | ~110s |
| Subsequent queries (graph cache) | 0.89 | SUPPORTED | Zero compute | **<1ms** |

Same models. Same claim. No retraining. **+0.46 score delta from injecting one verified fact.** The graph learned by itself.

The trajectory of a claim through EPP tells a story: from expensive hallucination (three models deliberating for two minutes to produce a wrong answer) to flywheel-corrected truth (same cost, right answer) to instant verified knowledge (zero cost, immediate). **Three orders of magnitude in cost reduction for a more reliable answer.**

And because every stage is attested on-chain with full methodology metadata, a consumer reading the blockchain can trace the entire epistemic journey — when the models didn't know, when the data corrected them, and when the system learned.

The next step — already architected — is closing the feedback loop: the corrected attestation feeds back into model evaluation (Brier scoring), so the protocol learns not just *what* is true, but *which models* are most reliable on *which domains*. The flywheel doesn't just correct facts. It calibrates trust.

---

### Domain Generality — Demonstrated

EPP is not a single-purpose tool. The protocol is domain-agnostic by design. Each domain is a configuration of the same kernel — different metrological frames, different deterministic sources, same consensus engine.

**Geopolitical Intelligence.** Yemen conflict: 0.96 SUPPORTED. Switzerland conflict: 0.62 CONTESTED. Stable across multiple independent runs with different model combinations. Connected to ACLED conflict event data as a deterministic source. The divergence between Yemen and Switzerland is not an error — it is the protocol correctly measuring that armed conflict in Switzerland is a contested proposition while armed conflict in Yemen is empirically documented.

**Smart Contract Security.** Reentrancy vulnerability (SWC-107): detected at 0.55 CONTESTED. Safe functions correctly identified at 0.79 SUPPORTED. Claims auto-classified by vulnerability type (33 SWC categories + 8 Trail of Bits classes). The ESMM kernel runs the same ASSESS → CHALLENGE → ADJUDICATE pipeline on code analysis claims as on geopolitical ones.

**Compliance & Anti-Money Laundering.** Four sanctions adapters integrated and tested: OFAC, OpenSanctions, EU CFSP, Verra VCS. Deterministic mode — zero LLM compute, cryptographic hash of source API response, traceable attestation. A compliance firm consuming EPP attestations can verify not just the result but the exact source query and response that produced it.

**Physical Sciences.** NIST adapter for fundamental constants (speed of light, Boltzmann constant, Planck constant). The Flywheel corrects AI hallucinations on physical claims against authoritative measurements in real time. A claim about the speed of light through glass (not a constant — it varies by medium) is correctly contested when NIST data for the vacuum constant is injected.

**Edge Cases.** "Pineapple on pizza is delicious": 0.29, flagged normative — the protocol refuses to adjudicate taste. "The Moon is made of cheese": zero attestations, graceful refusal — the protocol refuses to attest absurdities. Napoleon's height myth: exposes shared training bias across all models as measurable data rather than hiding it. These are not failures — they are the protocol demonstrating epistemic self-awareness.

---

### The Potential: A Network of Specialized Epistemic Clusters

EPP is designed as a network, not a tool. The unit of decentralization is the **Epistemic Cluster** — an autonomous instance of the protocol operated by an identifiable Solana keypair, with its own models, its own data sources, and its own metrological frames.

Trust is not declared. It **emerges** from the cumulative track record, calculable by anyone directly from the blockchain. No reputation oracle needed — the attestation history *is* the reputation. Two independent observers reading the same chain compute the same reputation score for the same cluster.

**Real-world applications at scale:**

**Compliance & AML.** A compliance firm operates a cluster connected to OFAC, EU CFSP, and OpenSanctions. Financial institutions subscribe to its attestations for automated KYC/AML verification. The cluster's value is its Brier accuracy score on sanctions screening — measurable, auditable, improvable over time. *Already built: four sanctions adapters integrated and tested.*

**Biomedical Research.** A research group connects a cluster to WHO databases, PubMed, and ClinicalTrials.gov. Pharmaceutical companies and regulators verify drug efficacy claims against published evidence. The Brier score on resolved clinical trials becomes the trust metric — a cluster that consistently predicts trial outcomes correctly earns a measurable track record.

**Geopolitical Intelligence.** A research institute deploys a cluster with ACLED conflict data, UCDP, and SIPRI as deterministic sources. Governments, insurers, and NGOs consume conflict assessments anchored on verifiable event data. *Already demonstrated: Yemen 0.96 SUPPORTED, Switzerland 0.62 CONTESTED — stable across multiple independent runs.*

**Smart Contract Security.** A DeFi security team runs a cluster specialized in Solidity audit with code decomposition and vulnerability detection. DAOs and launchpads consume its attestations before listing new protocols. *Already demonstrated: reentrancy detection, vulnerability classification across 33 SWC categories.*

**Physical Sciences.** A cluster connected to NIST fundamental constants provides verified reference data. The flywheel corrects AI hallucinations on physical claims in real time. *In development: NIST adapter for speed of light, Boltzmann constant, Planck constant.*

Each cluster publishes its configuration via a signed ClusterManifest. Verification happens through results, not promises. When two clusters attest the same claim with different results, the divergence is not a problem — it is a **cross-cluster measurement** that captures differences in methodology, sources, and model selection. The best estimate of truth emerges from the competition, not from any single operator's authority.

**What the code already supports:**

| Existing component | Role in the cluster network |
|:---|:---|
| `submitter: Pubkey` in `EpistemicAttestation` | Cluster operator identity |
| PDA seeds `[b"attestation", submitter, claim_hash]` | Natural per-cluster isolation — 2 clusters produce 2 distinct PDAs for the same claim |
| `is_challenge` + `challenged_attestation` | Inter-cluster contestation mechanism |
| `consensus_meta` (ADR-010) | Each cluster's methodological fingerprint |
| `model_track_record` + Brier scores | Seed of the reputation system |
| `infer_architecture_family()` | Intra-cluster diversity measurement |
| `response_deduplicator.py` | Sybil detection (embedding cosine ≥ 0.95) |
| `COMMUNITY_DECISION_REQUIRED` markers | Governance questions explicitly flagged for community input |

EPP was not designed as a tool that could become a network. It was designed as a network protocol of which only one node exists today.

---

### The Long-Term Vision: A Self-Reinforcing Epistemic Ecosystem

**A Living Knowledge Graph.** Each attested claim enriches a persistent knowledge base. This base serves as verified context for future queries — through the Flywheel mechanism already demonstrated. The more claims the system processes, the smarter it becomes. Not through retraining, but through accumulation of verified evidence. The graph survives model obsolescence: when a better model generation arrives, it inherits the graph and starts from a higher baseline. The knowledge is decoupled from the models that produced it.

**The On-Chain LiveBench.** Every attestation is a benchmark data point with full provenance. EPP becomes the reference infrastructure for evaluating AI model performance in a fully transparent, domain-specific, adversarial setting. The best-performing clusters gain measurable reputation, attracting more consumers, creating more incentive to specialize and challenge, fueling a virtuous cycle. Unlike centralized benchmarks (MMLU, HellaSwag, LiveBench) that go stale and can be gamed, EPP's benchmark is alive — updated with every attestation, across every domain, by every cluster. And because the benchmark is on-chain, the evaluation itself is auditable.

**Progressive Decentralization.** Phase 1 (complete): one cluster proves the protocol works across five domains. Phase 2 (planned): 3–10 clusters prove the network works, with inter-cluster contestation as a first-order signal. Phase 3 (vision): DAO governance over protocol parameters, TEE/ZKP for cryptographic model verification, staking with slashing on bad attestations. The architecture is ready — only one node exists today, but every on-chain field was designed for a multi-cluster world.

---

### Formal Verification Vision: Dual-Trust Architecture

EPP maintains a strict architectural boundary between the probabilistic nature of AI deliberations (empirical, measurable, inherently fallible) and the deterministic nature of the cryptographic infrastructure that anchors them. These are two distinct, non-substitutable layers of trust: one empirical (the AI verdict), one mathematical (the protocol itself).

The production smart contract is written in Rust via Anchor on Solana. The long-term vision adds a **Dual-Trust layer** where the core epistemic axioms are formally verified using theorem provers — ensuring that the protocol's mathematical guarantees are not just tested but *proven*.

**Target invariants:**

- **Regression Cut Isolation (Axiom 3)**: Two attestations sharing the same claim hash but different metrological frames can never be evaluated as comparable by any smart contract function. This prevents cross-methodology contamination.

- **Claim Hash Purity (ADR-006)**: The hash function accepts only (subject, predicate, object, frame) as inputs — never methodology metadata. This guarantees that the identity of a claim is independent of who assessed it or how.

- **Tier Boundary Enforcement (ADR-005)**: The program cannot grant the "Verified" tier unless score ≥ 0.85 AND either a deterministic source anchor exists or ≥ 3 independent validations from ≥ 2 architecture families are recorded. This prevents unearned confidence.

**Why this matters — the landscape data:**

Across the entire Colosseum hackathon corpus (5,400+ projects), only 3 touch formal verification — making it the rarest technical primitive in the ecosystem. Zero oracle protocols (Pyth, Switchboard, Chainlink) have published formal proofs of their aggregation logic, dispute mechanisms, or data integrity guarantees. Zero AI inference pipelines have been formally verified anywhere.

The tooling exists. Certora Prover — open-sourced February 2025, supporting Solana/Anchor, used by Squads, Jito, and the Solana Foundation — can verify EPP's Anchor program (attestation storage, PDA derivation, access control). Lean 4 — demonstrated by ChronosVault with 100+ theorems across 33 contracts on 3 chains — can prove properties of the epistemic consensus algorithm itself (Brier score aggregation is well-defined mathematics, highly amenable to formal proof).

A formally verified epistemic oracle would be:
- The first formally verified oracle protocol on Solana
- The first formally verified AI consensus mechanism anywhere
- A direct answer to the Solana Foundation's February 2024 RFP for program verification tooling

**Current status:** the Rust smart contract is deployed on devnet and the invariants are enforced by code and validated by tests. The formal verification layer is on the post-hackathon roadmap — it requires dedicated expertise in proof assistants and represents a natural call for collaboration. The architecture was designed with formal verification in mind; the properties to prove are identified; the tools to prove them exist. What remains is the work.

---

### What Has Been Built (5 weeks, solo builder)

| Metric | Value |
|:-------|:------|
| Test suite | [VERIFY: run `pytest tests/ -q` for current count] |
| Architecture decisions | 18 ADRs |
| AI models tested | 6 (Mistral, Llama 3.1, Gemma 3, DeepSeek-R1, phi4-reasoning, granite3.3) |
| Deterministic sources | 7 integrated (OFAC, OpenSanctions, EU CFSP, Verra, ACLED, Wikidata, NIST) |
| Domains demonstrated | 5 (epistemic, audit, geopolitics, compliance, physics) |
| Pipeline modes | EXPLORE + VERIFY + DETERMINISTIC + FLYWHEEL |
| Benchmark claims evaluated | 37+ across 7 datasets |
| Flywheel effect | +0.46 demonstrated (0.43 → 0.89) |
| Solana program | Anchor/Rust, deployed on devnet |
| On-chain footprint | 462-byte PDA per attestation |

Everything runs locally on a consumer GPU (RTX 4090) with open-source models via Ollama. No API keys. No cloud dependency. No vendor lock-in.

---

### From Intuition to Infrastructure

Before a single line of Python was written, EPP existed as something else — a set of handwritten mappings between attention mechanisms and what a self-taught poet called "vibratory weights." Concepts like divergence as signal, multi-agent deliberation, and bidirectional knowledge transfer between models were sketched not in code but in metaphor, months before they became Architecture Decision Records and pytest assertions.

The path from there to here — 18 ADRs, 6 AI models deliberating on Solana devnet, a measurable +0.46 flywheel delta, five operational domains — was walked by one person with no technical background, a consumer GPU, and a belief that making AI models disagree on purpose would produce something more honest than making them agree.

This is what one person built in sixteen months. The protocol is proven. The architecture scales. The question is no longer whether it works — the data answers that. The question is what becomes possible when a team carries it forward.

---

### The Thesis

The Bank for International Settlements asks: can DeFi extend beyond cryptoassets? Their answer: not without solving the epistemological trust gap.

Caldarelli asks: can AI solve the blockchain oracle problem? His answer: no, but it can help mitigate it.

**EPP is the infrastructure for that answer.**

> *Everyone solves the answer. Nobody solves how much to trust it.*
>
> *EPP makes AI models argue under controlled conditions, measures the quality of their disagreement with proper scoring rules, records the full methodology, anchors the result on verified data, and stores the proof on Solana — permanently. One protocol. Any domain. Any model. Verifiable by anyone.*
>
> *And then the graph remembers — so the next question is answered faster, cheaper, and more reliably than the last.*
>
> *The oracle that doesn't trust itself.*
