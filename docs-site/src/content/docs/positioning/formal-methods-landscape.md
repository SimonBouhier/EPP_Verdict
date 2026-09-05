---
title: "State of Formal Methods in Crypto Smart Contracts (2025-2026)"
editUrl: false
---

> **Historical material.** Preserved in its original context. Former blockchain, cluster and sprint claims do not define the current project. Read the [current scope](/current-status/) and [ADR-022](/adrs/adr-022-post-blockchain-refocus/).

> Justifies the rarity of EPP's Lean 4 layer (3 / 5,400 Colosseum projects).
>
> *Originally compiled in the sprint working dir. Migrated 2026-04-23.*

## Production Tools — What Exists Today

### Tier 1: Battle-tested, actively used on Solana

**Certora Prover** — The 800-pound gorilla. Open-sourced Feb 2025.
Supports EVM, Solana (sBPF), and Stellar (WASM). Has secured $100B+ TVL
across protocols including Solana Foundation, Kamino, Squads, Jito, and
Manifest. Takes Rust contracts + developer-defined specifications and
automatically proves correctness or produces counterexamples. Formally
verified Solana Token Extensions (SPL Token-2022). Seven years in
development.

**OtterSec / Kani framework** — OtterSec built a prototype for formally
verifying Anchor programs using bounded model checking via the Kani
Rust Verifier. Case study: Squads Multisig v4 (Jan 2023). Integrates
with `anchor-lang`, provides APIs to specify invariants, autogenerates
proof harnesses. Uses SMT solvers (z3) under the hood. Squads v4 has
dual formal verification — both OtterSec and Certora independently
verified it.

### Tier 2: Emerging, proof-of-concept stage

- **Inferara (Coq-based)** — Research group exploring formalizing Solana program specifications in Coq. Responded to the Solana Foundation's Feb 2024 RFP for Program Verification Tooling.
- **ChronosVault (Lean 4)** — Formally verified 33 smart contracts across 3 chains (Arbitrum, Solana, TON) using Lean 4, proving 100+ theorems covering consensus safety, solvency invariants, and quantum resistance. Trinity Protocol uses 2-of-3 consensus with 35 verified theorems. Found a subtle HTLC race condition before deployment. **Most advanced Lean 4 application to blockchain contracts that exists publicly.**
- **Nethermind / Clear (Lean)** — Using Lean for smart contract verification. Also partnered with RISC Zero to formally verify zkVM circuits against RISC-V semantics. Proof-of-concept stage.
- **Formal Land (Rocq/Coq)** — Uses the Rocq proof system (formerly Coq) for smart contract verification. Active blog with educational content.
- **KMIR / Runtime Verification (K Framework)** — Encodes Rust's MIR semantics in the K Framework. Academic/research tool.

### Tier 3: zkVM verification (adjacent)

- **CertiK** — Achieved world's first complete formal verification of a zkVM (zkWasm circuits).
- **Veridise** — Reviewed RISC Zero zkVM code using fuzz-testing + formal verification.
- **a16z / Justin Thaler** — Using ACL2 automated theorem prover for Jolt zkVM formal verification. Published research on *"the path to secure and efficient zkVMs"* (Mar 2025).

## Colosseum Hackathon Projects

Only 3 projects in the entire 5,400+ project corpus touch formal verification:

| Project | Hackathon | Approach | Prize |
|:--------|:----------|:---------|:------|
| **Wybe** | Breakout Apr 2025 | Dijkstra's predicate calculus for smart contract verification. Solo builder | None |
| **Excalead** | Cypherpunk Sep 2025 | AI + formal verification hybrid for automated Solana audits. Subscription model | Honorable Mention Infrastructure |
| **Gluon Stablecoin** | Cypherpunk Sep 2025 | *"Formally verified autonomous stablecoin protocol."* Lists FV as core differentiator | None |

**That's it. 3 out of 5,400+. Formal verification is the single rarest technical primitive in the entire Colosseum corpus.**

## Archive Evidence — Solana Ecosystem

- **Solana Foundation RFP** (Feb 2024) — Explicitly solicited *"program verification tooling"* including scoring, attestations, and APIs. Inferara (Coq), OtterSec (Kani), and Certora responded.
- **OtterSec Case Study** (Jan 2023) — Detailed technical post on formally verifying Squads Multisig using bounded model checking. Solana's account model creates unique verification complexity vs. EVM.
- **Squads Documentation** — Squads v3 and v4 both underwent formal verification. v4 has two independent formal verifications (OtterSec + Certora) — the gold standard for Solana program security.
- **a16z Research** (Mar 2025) — Justin Thaler's *"The path to secure and efficient zkVMs"* identifies formal verification as the critical path to Stage 2-3 security.

## Proof Assistants in Crypto — The Breakdown

| Prover | Used By | Target | Maturity in Crypto |
|:-------|:--------|:-------|:-------------------|
| **Lean 4** | ChronosVault, Nethermind, academic researchers | Multi-chain contracts, zkVM circuits, consensus algorithms | Emerging — 100+ theorems proven, growing fast, no production-scale adoption yet |
| **Coq / Rocq** | Inferara, Formal Land, academic | EVM contracts, Solana specs (exploratory) | Research stage for Solana — mature for EVM (e.g., DeepSEA) |
| **Isabelle** | TU Munich and similar | Protocol-level proofs, consensus | Academic only — no production blockchain tooling |
| **ACL2** | a16z (Jolt), academic | zkVM verification | Specialized — used for specific proof systems |
| **K Framework** | Runtime Verification (KMIR) | Rust MIR semantics | Infrastructure — enables other tools |
| **Kani (BMC)** | OtterSec, AWS | Rust programs (including Anchor) | Production — most practical Solana FV tool after Certora |
| **SMT solvers (z3)** | Certora, OtterSec backends | Automated proving under the hood | Production — engine behind most tools |

## The Formal Verification Gap for Oracles and AI Inference

A targeted search for formal methods applied to oracle protocols or AI
inference verification returned:

- **Zero formal verification of any oracle protocol.** Pyth, Switchboard, Chainlink — none have published formal proofs of their aggregation logic, dispute mechanisms, or data integrity guarantees.
- **Zero formal verification of AI inference pipelines.** zkML uses ZK proofs to prove computation, but nobody has formally verified the correctness of the ZK circuit that verifies the ML inference. CertiK's zkWasm verification is the closest — proving the VM is correct, not the AI output.
- **a16z's zkVM verification work** establishes that formal verification of proof systems is feasible and important, but it's focused on general-purpose VMs, not oracle-specific or AI-specific properties.

This is a massive gap. **A formally verified epistemic oracle would be**:

- The first formally verified oracle protocol on Solana.
- The first formally verified AI consensus mechanism *anywhere*.
- A direct answer to the Solana Foundation's RFP for program verification tooling.

## What This Means for EPP

The formal verification landscape creates a unique opportunity:

- **Certora Prover** is the practical choice — open-source, supports Solana/Anchor, used by Squads and Jito. Could formally verify EPP's Anchor program (attestation storage, PDA derivation, access control) with Certora specs.
- **Lean 4** is the ambitious choice — already in use (ADR-020). ChronosVault's 100+ theorem precedent shows it's feasible for multi-chain protocols. EPP could prove properties of the epistemic consensus algorithm itself — Brier score aggregation is well-defined mathematics, highly amenable to formal proof.
- **The rarity signal is powerful.** 3 out of 5,400 hackathon projects. Excalead won Honorable Mention just for combining AI with formal verification. A formally verified epistemic oracle would be genuinely novel across the entire crypto ecosystem.

The data says: nobody has done it for oracles, nobody has done it for
AI consensus, and the tooling exists. EPP's ADR-020 formal specification
layer (Lean 4 invariants on the on-chain attestation contract, with
empirical Brier calibration on the AI side) is the path forward.
