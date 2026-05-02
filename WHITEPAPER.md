# EPP — Epistemic Proof Program
## Whitepaper

> **Verifiable AI Consensus on Solana.**
>
> This document is the long-form architectural and epistemological
> narrative. For the shippable pitch see [`PITCH.md`](PITCH.md). For
> practical install/run instructions see [`README.md`](README.md). For
> the internal strategic material (competitive landscape, counterpoint
> responses, formal methods panorama, track positioning) see
> [`docs/positioning/`](docs/positioning/).

---

## Liability & Scope

EPP outputs **proofs of process, not verdicts on truth.** Each attestation is a cryptographic record of *which models deliberated, under what metrological frame, what their independent verdicts were, what 5-dimensional epistemic signature they produced, what authoritative sources (if any) anchored the deliberation, and what consensus emerged*. The protocol does not assert that the consensus is *correct* — only that it was *measured* under the declared conditions.

**Alignment with international ethical frameworks.** This positioning is consistent with the *UNESCO Recommendation on the Ethics of Artificial Intelligence* (adopted by 193 Member States, November 2021):

- *"Ultimate responsibility and accountability must always lie with natural or legal persons and AI systems should not be given legal personality themselves"* (§11).
- *"Both technical and institutional designs should ensure auditability and traceability of (the working of) AI systems"* (§5).
- *"AI actors… should respect, protect and promote human rights and fundamental freedoms… The ethical responsibility and liability for the decisions and actions based on an AI system should always ultimately be attributable to AI actors corresponding to their role in the life cycle of the AI system"* (§3).

EPP's design — methodology traceability via `consensus_meta` (ADR-010), append-only on-chain attestations, declared metrological frames, explicit refusal to attest normative or speculative claims — implements those auditability and traceability principles at the protocol level. It does **not** transfer ethical or legal accountability *away from* the consumer of the attestation. Operators, integrators, and end-users remain the *AI actors* to whom UNESCO §11 attributes ultimate responsibility.

**Operational implications.** Protocols, institutions, and individuals consuming EPP attestations (DeFi contracts, compliance systems, prediction markets, governance contracts, research workflows) remain responsible for:

- Setting their own thresholds, escalation rules, and human-in-the-loop review points.
- Conducting their own Ethical Impact Assessments (EIA — UNESCO Recommendation tool) when attestations feed consequential decisions about persons.
- Compliance with sector-specific regulation (banking, healthcare, judicial, electoral) that EPP itself does not satisfy.

The protocol explicitly refuses to adjudicate opinions (normative claims), unfalsifiable assertions (speculative claims), or claims outside its declared metrological frames. **Refusal is itself an attestation**, recorded with the same provenance as any other.

---

## The Stakes: The Trust Gap No Oracle Has Filled

Blockchain technology promises systems where blind trust is no longer necessary. But it depends on *oracles* to import information about the real world. Today's oracles handle numerical data — a token price, a timestamp, a sports score. When it comes to adjudicating complex claims or verifying facts, no protocol today produces a reliable, transparent, verifiable proof of *how much the answer should be trusted*.

In 2022 alone, DeFi protocols lost **$403 million to oracle manipulation**. The Bank for International Settlements identifies this as an epistemological gap, not a technical one. Caldarelli (2025) asks whether AI can solve the blockchain oracle problem — his answer: no, but it can help mitigate it.

There are 121 oracle and AI products on Solana. Several anchor AI-assisted resolution or confidence metrics on-chain. Pyth publishes confidence intervals on price feeds. UMA resolves qualitative claims via optimistic dispute on Ethereum. Supra's Threshold AI Oracles use multi-agent LLM committees with BLS threshold signatures.

None of them measure the *calibration quality* of AI consensus. None record the full methodology that produced a verdict. None treat the pattern of disagreement as a signal worth preserving on-chain. Every system treats consensus as binary — threshold reached or not, dispute resolved or not, confidence within bounds or not.

**The gap is not "qualitative claims on-chain." The gap is epistemic calibration as an on-chain primitive.**

EPP fills that gap.

---

## The Solution: A Machine for Manufacturing Verifiable Trust

EPP is a verifiable AI consensus engine. Multiple AI models independently assess a claim through structured adversarial deliberation, and the protocol anchors the result — including the full methodology that produced it — as a cryptographic attestation on Solana.

The output is not a vote count or a probability. It is an **epistemic measurement**: a 5-dimensional signature capturing agreement, consistency, centrality, stability, and diversity — with the complete audit trail of how it was produced.

Instead of blindly trusting a single AI, EPP:

- **Orchestrates structured adversarial deliberation** where architecturally diverse AI models evaluate independently, challenge each other's reasoning under epistemic isolation, and reach consensus through a three-phase protocol (ASSESS → CHALLENGE → ADJUDICATE).
- **Measures the quality of disagreement** using proper scoring rules (Brier scores, Shannon entropy, vote dispersion) that incentivize honest probability estimates.
- **Anchors the result on Solana** as a 462-byte PDA carrying the full epistemic signature, methodology metadata, and metrological frame hash — cryptographic, immutable, verifiable by anyone with a blockchain explorer.
- **Makes the entire deliberation auditable.** Every attestation records which models were used (IDs, versions, architecture families), what parameters were applied (temperature, system prompt, framing), the metrological frame, individual model outputs, and the complete consensus metadata.

The system also knows what it *doesn't* know. An opinion (*"pineapple on pizza is delicious"*) is detected as normative and scored at 0.29 — the protocol refuses to adjudicate taste. An absurdity (*"the Moon is made of cheese"*) produces zero attestations — graceful refusal. A historical myth (Napoleon's height) exposes shared training bias across all models, producing it as measurable data rather than hiding it.

---

## The ESMM Deliberation Architecture

Most multi-agent debate frameworks (Du et al. 2023, LLM-Agora, A-HMAD) operate as open forums: every model sees every other model's response, leading to what Choi et al. (2025) identify as **"conformity-driven collapse"** — agents converge toward the dominant opinion regardless of its correctness.

ESMM (Epistemic Structured Multi-Model) takes a different approach: **structured adversarial deliberation with epistemic isolation.**

Three sequential phases, each with distinct prompts and objectives:

**1 — ASSESS.** Each model evaluates the claim independently. No model sees any peer output. Responses are SHA-256 committed before proceeding (commit-reveal protocol). This establishes a clean baseline — each model's judgment exists before it can be contaminated by social proof.

**2 — CHALLENGE.** Circular adversarial rotation. Model *i* sees *only* Model *(i+1) mod N*'s verdict and must contest it. This prevents cascade conformism while forcing each model to engage with exactly one opposing perspective. The rotation is circular, not random — every model both challenges and is challenged, with no privileged position.

**3 — ADJUDICATE.** Weighted synthesis. All evidence from ASSESS and CHALLENGE feeds into collective adjudication. The output is a 5-dimensional epistemic signature:

- **Agreement** — how strongly the models converge.
- **Consistency** — how stable their positions are across phases.
- **Centrality** — how close each model is to the aggregate position.
- **Stability** — how much positions shifted between ASSESS and ADJUDICATE.
- **Diversity** — how architecturally heterogeneous the deliberating panel is.

Vote entropy serves as an explicit anti-conformism metric: high entropy means genuine disagreement, not groupthink.

**Key architectural differences from existing frameworks:**

- **Epistemic isolation**: no model ever sees all peers' outputs simultaneously. Structural guarantee against conformity-driven collapse.
- **Heterogeneous models enforced**: minimum 2 architecture families required (e.g., Mistral + Llama, not 3× GPT-4). Architectural monoculture is treated as a methodological flaw, not a configuration choice.
- **Claim classification**: empirical, definitional, speculative, and normative claims are auto-detected and scored with different thresholds. The protocol does not pretend all claims are equal.
- **Commit-reveal**: initial responses are cryptographically committed before the debate phase begins. Post-hoc rationalization is detectable.
- **On-chain anchoring**: the full consensus metadata — not just the verdict — is stored with the attestation, making deliberation independently auditable.

---

## Three Modes, One Protocol

**EXPLORE** — Open-ended knowledge extraction. Models build a semantic knowledge graph through divergent, debate, and meta-reflection cycles. Each extracted triplet (subject-predicate-object) is weighted by structural consensus: Brier scores, diversity bonuses, semantic fingerprinting. The graph persists across sessions and model generations.

**VERIFY** — Factual claim verification. A claim enters the ASSESS → CHALLENGE → ADJUDICATE pipeline and produces a signed 5-dimensional epistemic attestation. EPP's core mode for producing verifiable verdicts.

**DETERMINISTIC** (ADR-012) — For facts that don't need debate. Sanctions screening (OFAC, OpenSanctions, EU CFSP), carbon credit validation (Verra VCS), institutional registries, physical constants (NIST). EPP queries the authoritative external source, hashes the raw API response, and produces a traceable attestation without invoking LLMs — because adding uncertainty to a binary fact is not epistemology, it is noise.

---

## Claim Classification & Decidability

Before any evaluation, the protocol auto-classifies every claim into one of four types: **empirical** (verifiable against data), **definitional** (depends on term definitions), **normative** (value judgment — no objective answer), or **speculative** (unfalsifiable). This classification drives a double penalty system that adjusts scores before crystallization:

| Verdict | Penalty | | Claim Type | Penalty |
|:--------|:--------|---|:-----------|:--------|
| SUPPORTED | ×1.0 | | empirical | ×1.0 |
| CONTESTED | ×0.65 | | definitional | ×0.90 |
| INSUFFICIENT_EVIDENCE | ×0.45 | | normative | ×0.70 |
| | | | speculative | ×0.75 |
| | | | security_audit | ×1.0 |

*"Pineapple on pizza is delicious"* scores 0.29 (normative × insufficient evidence); *"Earth orbits the Sun in 365.25 days"* scores 0.99 (empirical × supported). The protocol knows what it cannot adjudicate.

---

## The Consensus Engine — Three Layers

Consensus is computed in three complementary passes, each catching what the previous one missed:

**Layer 0 — Normalize** (`normalize_triplet()`) — Static dictionary of known synonyms (11 canonical relation groups, abbreviation expansion, whitespace normalization). Cost: O(1).

**Layer 1 — Semantic Fingerprinting** (ADR-011) — Each model generates a micro-graph of neighbors for each term (EXPAND phase). Terms whose neighborhood structures overlap above a threshold are identified as synonyms and merged via an alignment table (MATCH + APPLY phases). Uses Jaro-Winkler similarity + embedding cosine as a waterfall cascade. Cost: O(n² × k).

**Layer 2 — Semantic Merge** (`_semantic_merge()`) — Residual clustering by embedding cosine similarity for cases Layer 1 misses. Cost: O(n² × d).

Order is strict: L0 → L1 → hash (SHA-256) → L2. If Layer 1 is disabled or times out, Layers 0 and 2 ensure baseline coverage.

---

## Metrological Frames

Every attestation is produced under a versioned metrological frame — a structured specification of the measurement methodology. The frame hash is included in the claim hash (ADR-006), making attestations produced under different frames **explicitly non-comparable**.

Seven predefined frames:

| Frame ID | Domain |
|:---------|:-------|
| `general_knowledge_v1.0` | Default epistemic evaluation |
| `blockchain_tps_v1.0` | Blockchain performance claims |
| `compliance_sanctions_v1.0` | AML/KYC sanctions screening |
| `carbon_credits_vcs_v1.0` | Verra VCS carbon credit validation |
| `rwa_identity_v1.0` | RWA identity verification |
| `smartcontract_audit_v1.0` | Smart contract security (SWC + Trail of Bits) |
| `geopolitical_forecast_v1.0` | ACLED-based conflict assessment |

Each frame specifies: domain, metric, parameters, required sources, governance authority, deterministic hash. Custom frames can be created for any domain.

---

## The Epistemic Flywheel (ADR-018)

AI models have a structural limitation: they know nothing about events that occurred after their training data was compiled. This is not a bug — it is a fundamental property of statistical language models.

EPP does not suffer this limitation. It exploits it.

The protocol connects AI deliberation to authoritative, verifiable data sources — scientific databases (NIST), institutional registries (OFAC, EU sanctions), knowledge bases (Wikidata), conflict event data (ACLED). When a verified data point exists for a claim, the Flywheel automatically injects it into the AI models' reasoning context during the VERIFY pass — not as a directive, but as **factual evidence they are free to contest**.

**The result is measurable.** On the claim *"Donald Trump won the 2024 US presidential election"*:

| Stage | Score | Verdict | Cost | Time |
|:------|:------|:--------|:-----|:-----|
| LLMs alone | 0.43 | CONTESTED | 3 models × full deliberation | ~105s |
| + Flywheel (Wikidata injected) | 0.89 | SUPPORTED | 3 models × full deliberation | ~110s |
| Subsequent queries (cache) | 0.89 | SUPPORTED | **Zero compute** | **< 1 ms** |

Same models. Same claim. No retraining. **+0.46 score delta from injecting one verified fact.** The graph learned by itself.

The trajectory of a claim tells a story: from expensive hallucination (three models deliberating for two minutes to produce a wrong answer), to flywheel-corrected truth (same cost, right answer), to instant verified knowledge (zero cost, immediate). **Three orders of magnitude in cost reduction for a more reliable answer.**

Because every stage is attested on-chain with full methodology metadata, a consumer can trace the entire epistemic journey: when the models didn't know, when the data corrected them, and when the system learned.

---

## Epistemic Cache (ADR-013)

Before launching a costly multi-model run, the pipeline checks the persistent graph for an existing attestation matching the claim hash with a valid TTL (default 7 days). If found, the cached result is returned at zero compute cost. This is what produces the `< 1 ms` response time on subsequent queries in the Flywheel table above.

---

## Empirical Results

### Flywheel Effect (ADR-018)

| Claim | Without Flywheel | With Flywheel | Delta |
|:------|:-----------------|:--------------|:------|
| Trump won 2024 election | 0.43 CONTESTED | 0.89 SUPPORTED | **+0.46** |

### Geopolitical Assessment (ADR-016)

| Claim | LLM Verdict | Score | Deterministic Source |
|:------|:------------|:------|:---------------------|
| Yemen active conflict 2025 | SUPPORTED | 0.96 | ACLED: ready |
| Switzerland active conflict | CONTESTED | 0.62 | — |
| Iran proxy escalation | CONTESTED | 0.42 | ACLED: ready |

### Smart Contract Audit (ADR-014)

| Function | Vulnerable? | Light (7B) | Heavy (20B+) |
|:---------|:------------|:-----------|:-------------|
| `withdrawBalance` (SWC-107) | YES | 0.55 CONTESTED | 0.46 CONTESTED |
| `addToBalance` | No | 0.79 SUPPORTED | 0.74 SUPPORTED |
| `getBalance` | No | 0.79 SUPPORTED | 0.41 CONTESTED |

**Finding:** reasoning models over-contest uniformly (~0.45). Smaller 7B models discriminate better. **The divergence between model families IS the signal.**

### Epistemic Edge Cases

| Claim | Type Detected | Score | Signal |
|:------|:--------------|:------|:-------|
| Pineapple on pizza is delicious | Normative | 0.29 | Refuses to adjudicate |
| Moon is made of cheese | — | 0 attestations | Graceful refusal |
| Bitcoin replaces fiat in 10 years | Speculative | 0.40 | Penalty ×0.75 applied |
| Earth orbits Sun in 365.25 days | Empirical | 0.99 | Baseline anchor |
| Napoleon was shorter than average | Empirical | 0.96 SUPPORTED ✗ | Shared training bias exposed |

---

## Five Founding Axioms

1. **Model Obsolescence** — Models are consumables, not infrastructure. Any LLM can enter or leave the system without breaking the protocol.
2. **Metrological Sovereignty** — Every attestation declares its measurement frame. No frame, no comparison. Different methodologies produce explicitly non-comparable results.
3. **Regression Cut Transparency** — Every methodology change is versioned. Attestations produced under different conditions are explicitly non-comparable.
4. **Local Computation, On-Chain Proof** — AI runs locally (privacy, cost control, no vendor lock-in). Only the cryptographic proof goes on-chain.
5. **Divergence is the Signal** — Disagreement between model families is more epistemically valuable than a unanimous verdict. Uniformity is a failure mode, not a feature.

---

## Why Blockchain (and not just a signed ledger)?

A signed JSON dump on a public server provides authenticity — anyone can verify the signature and detect tampering after the fact. EPP needs three additional properties that only an append-only public chain provides.

**(1) Resistance to LLM-auditor collusion.** EPP measures disagreement between heterogeneous AI models. The signal is only meaningful if past deliberations cannot be silently rewritten. If an operator could selectively prune attestations where their preferred models disagreed with ground truth, the calibration record becomes worthless and the diversity bonus becomes a marketing claim. On-chain attestations are content-addressed (PDA derived from `submitter` + `claim_hash`) and append-only by program design. The history of a cluster's verdicts is structurally fixed.

**(2) Public non-repudiation of epistemic verdicts.** A submitter who pushes an attestation under their keypair commits to it. They cannot later claim *"those weren't my models"*, *"that wasn't my methodology"*, or *"that attestation never happened."* The keypair signs the transaction, the program ID verifies the methodology was the published one, the slot anchors the moment. Brier track records — the foundation of inter-cluster trust in ADR-017 — only carry weight if no cluster can quietly disown its bad predictions.

This property has emerging legal recognition. The *Tribunal judiciaire de Marseille* (March 2025) attributed *valeur probante* (evidentiary weight) to a blockchain timestamp in a copyright case concerning Albert Elbaz. Similar recognition exists with the U.S. Copyright Office, the Cour populaire de Hangzhou in China, and notably the Luxembourg Code civil (2024 amendment) which treats blockchain records as *"preuve présumée fiable sauf contestation motivée"* (presumed reliable evidence unless motivated contestation). The Court of Justice of the European Union (*DigitalArt GmbH*, 2024) granted a *"présomption de fiabilité"* specifically to **public** blockchains, distinguishing them from permissioned ledgers. EPP's choice of a public Solana program — not a permissioned ledger — places its attestations in this evolving evidentiary regime.

The doctrine emerging from these decisions is consistent: **blockchain proof is necessary but not sufficient.** It must sit inside a *constellation probatoire* (evidentiary constellation) combining blockchain timestamp + signed methodology + verifiable source anchors + identifiable submitter. EPP is designed exactly as such a constellation: claim hash + signature 5D + frame hash + source anchor + submitter pubkey, all cryptographically linked.

**(3) Permissionless reading by any composing agent.** A protocol that wants to consume EPP attestations — an insurance smart contract, a prediction market resolver, a DAO governance vote — queries the chain directly via `getProgramAccounts` with a `memcmp` filter on `claim_hash`. No API key. No rate limit. No operator permission. No business relationship. The attestations are structurally available to any agent that knows the program ID.

This is what the UNESCO transparency principles (Principles #10-13 of the *Internet Platform Companies Transparency* framework) require of consequential AI decision systems: risk assessments and algorithmic disclosure available to any concerned party. A permissioned API can be revoked, throttled, or selectively served. A public chain cannot.

A signed ledger gives you (1) authenticity. The blockchain gives you (1) + (2) + (3) — the conditions necessary for an epistemic primitive that other protocols can autonomously compose with, without trusting EPP itself.

---

## On-Chain

Solana program deployed on devnet: **`9QtybfyZQFhra1D6S3NtD6jD4z2Z3wcYmf4YXETq8bSD`** (deployed slot 450099166, authority `DRAQ7ZppvzUdASF9jR218aPutsirUFwt2ePr6f9n9rJw`).

Each attestation occupies **462 bytes** as a PDA. It carries: claim hash (32 B), epistemic signature (5 dimensions × u16), confidence tier, metrological frame hash, source anchor, protocol version, challenge metadata.

Four confidence tiers (ADR-005):

| Tier | Threshold | Additional conditions |
|:-----|:----------|:----------------------|
| Sandbox | < 0.40 | None |
| Proposition | ≥ 0.40 | + ≥ 2 models consulted |
| Validated | ≥ 0.70 | + ≥ 3 models + ≥ 2 architecture families |
| Verified | ≥ 0.85 | + source anchor OR validation count ≥ 3 |

The **5-dimensional epistemic signature** captures: agreement (how strongly the models converge), consistency (how stable positions are across phases), centrality (how close each model is to the aggregate), stability (how much positions shifted between ASSESS and ADJUDICATE), and diversity (how architecturally heterogeneous the panel is).

---

## Formal Verification — Dual-Trust Architecture (ADR-020)

EPP maintains a strict architectural boundary between the probabilistic nature of AI deliberations (empirical, measurable, inherently fallible) and the deterministic nature of the cryptographic infrastructure that anchors them. These are two distinct, non-substitutable layers of trust: one empirical (the AI verdict), one mathematical (the protocol itself).

### What Lean 4 specifies (and what it doesn't)

The `Formal/` directory contains a Lean 4 specification of the on-chain attestation contract — confidence tier assignment, claim hash identity, source anchor well-formedness — audited line-by-line over four phases between 2026-04-30 and 2026-05-01 (full reports under [`docs/audit/`](docs/audit/), original review in [`docs/To_do_list/Formal_Review_EPP.md`](docs/To_do_list/Formal_Review_EPP.md)). The specification distinguishes three categories of statements with deliberately distinct epistemic weights:

**1. Substantive characterization (6 theorems, `Formal/Formal/TierBoundary.lean`).** The function `assignTier` mapping `(score, models, hasAnchor, validationCount)` to one of four confidence tiers is fully characterized by **four `iff` theorems** (one per tier — `verified`, `validated`, `proposition`, `sandbox`). These close the soundness/completeness asymmetry that an earlier directional version left open: a trivial implementation that never returned `verified` would have satisfied the directional theorem vacuously. Two additional theorems prove **stratification cumulativity** — `assignTier = verified ⇒ conditions of validated hold ⇒ conditions of proposition hold` — which corrects a real design bug in the pre-2026-05-01 code (`verified` was reachable with one model + anchor, breaking the cumulative ordering that the tier names suggest).

**2. Type-level contracts (2 theorems, `Formal/Formal/SourceAnchor.lean`).** The Lean type `SourceAnchor` is non-constructible with an empty hash (P3.A refactor). The two theorems on `wellFormed` for `deterministic` attestations are tautologies in proof — they unfold the definition — but the *invariant* they document is enforced by the type system, not by a runtime check on a Boolean flag. The same contract is enforced in Python via a Pydantic regex `^[0-9a-f]{64}$` aligned with the Lean type definition (P4.2 alignment, `services/esmm/attestation.py:89-100`).

**3. Regression tests (7 unit-style theorems, `Formal/Formal/RedTests.lean`).** Five tier-boundary cases (3 RED + 2 GREEN, exercising both the anchor and validation-count paths and an anti-cumulativity case) and two claim hash invariance checks (timestamp-independence and submitter-independence — the latter being the structural condition for cross-cluster comparability of the same claim, ADR-017). Each red test is designed to fail compilation if the underlying definition is mutated (falsification protocol C6).

A single definitional lemma, `claim_hash_purity` in `Formal/Formal/ClaimHash.lean`, documents that the claim hash projection touches only the canonical four-tuple `(subject, predicate, object, frame)`. Its proof is `unfold; rw`; its function is regression protection on the `toClaimCore` projection, not the demonstration of an emergent invariant.

### What Lean does *not* prove

Honesty about scope is part of the architecture, not a footnote:

1. **The bridge between the Lean specification and the Python/Rust runtime is human-maintained, not mechanically extracted.** When `services/esmm/attestation.py::derive_confidence_tier` evolves, the corresponding Lean `assignTier` definition does not follow automatically. A conformance suite (`tests/test_lean_conformance.py` + `tests/test_lean_conformance_property.py` — 26 unit tests + 16 property-based tests, configurable up to 10 000 random inputs per property) bridges the gap empirically but does not replace mechanical correspondence. This is documented as `TD-005` in `TECH_DEBT.md`. The candidate resolution is a Hypothesis-based differential fuzzer that runs `assignTier` Python against a Python oracle that mirrors the Lean spec — planned, not yet implemented.

2. **SHA-256 is modeled as canonical concatenation.** The Lean definition `claimHashCore (c : ClaimCore) : String := c.subject ++ "|" ++ c.predicate ++ "|" ++ c.object ++ "|" ++ c.frame` is a structural placeholder. Cryptographic properties of SHA-256 (preimage resistance, collision resistance) are assumed by external trust, not derived inside Lean.

3. **The Anchor program (Rust) is not in scope for the current Lean layer.** `programs/epp/src/lib.rs` enforces `epistemic_type ≤ 2` at the byte level (ADR-019) but has no formal verification harness. Cross-field invariants (e.g. `epistemic_type = 1 ⇒ source_anchor ≠ [0; 32]` on-chain) are documented in ADR-019 §3 but not enforced by Lean nor by `require!` clauses. Eventual paths — Rust→Lean extraction (Aeneas, hax) and Certora — are not production-ready for Anchor 0.32 as of May 2026.

### What the formal layer is for

The formal layer's job is to make the chaos inside the frame *measurable honestly*, not to eliminate it. It guarantees that a `verified` tier published on Solana satisfies a precisely characterized condition (cumulativity included), that two independent operators producing the same claim hash queried the same canonical four-tuple, and that a `deterministic` attestation cannot be constructed without a non-empty source hash. None of this proves the underlying claim is *true*. Truth comes from the empirical layer — Brier scores against ground truth, divergence between architecturally heterogeneous models, source-anchor concordance — and remains permanently fallible. The formal and empirical layers verify each other without either being sufficient alone.

### Implementation

Lean 4 `v4.29.1`, no `mathlib` dependency. `lake clean && lake build` compiles 16 jobs with zero warnings. CI runs on each push via `leanprover/lean-action@v1` (`.github/workflows/lean_action_ci.yml`). Position relative to peers: a publicly-traceable Lean 4 specification of an oracle protocol's on-chain contract is uncommon in the current crypto ecosystem, but the comparison field is moving and we make no claim to be the first or only — readers interested in the broader landscape can consult [`docs/positioning/formal_methods_landscape.md`](docs/positioning/formal_methods_landscape.md).

---

## Security & Integrity

**Anti-Sybil** — `infer_architecture_family()` enforces minimum 2 distinct architecture families per deliberation panel. Three instances of the same model architecture do not count as diverse consensus.

**Prompt Injection Defense** — XML boundary delimiters (`<system_instruction>`, `<user_query>`) isolate trusted prompts from user input. `_sanitize_concept()` strips control characters and enforces `MAX_QUESTION_LENGTH=5000`.

**Devnet-Only Guard** — The `SolanaCluster` enum intentionally has no `MAINNET` value. `validate_cluster()` blocks any attempt to submit to mainnet. Mainnet requires a full security audit first.

**Keypair Security** — Private keys are never logged (ADR-008). Only the public key appears in logs and attestations.

**Commit-Reveal** (R-2.2.3) — Initial model responses during ASSESS are SHA-256 committed before CHALLENGE begins. After adjudication, commits are verified against reveals. Post-hoc rationalization is detectable.

**Response Deduplication** (R-2.2.2) — Before consensus computation, near-duplicate responses are filtered by embedding cosine similarity. A model producing multiple paraphrases of the same answer cannot inflate its vote count.

---

## Deterministic Sources

Seven authoritative data sources integrated:

| Source | Domain | Adapter | Status |
|:-------|:-------|:--------|:-------|
| OFAC SDN | US Treasury sanctions | `ofac.py` | Integrated |
| OpenSanctions | Open-source sanctions/PEP | `opensanctions.py` | Integrated |
| EU CFSP | European Union sanctions | `eu_cfsp.py` | Integrated |
| Verra VCS | Carbon credit registry | `verra_vcs.py` | Integrated |
| ACLED | Armed conflict events | `acled.py` | Integrated (pending API access) |
| Wikidata | Structured knowledge base (CC-0) | `wikidata.py` | Integrated (Flywheel demonstrated) |
| NIST | Physical constants | `nist_codata.py` | In development |

Each adapter implements the `SourceAdapter` interface: `fetch()`, `normalize()`, `get_source_version()`. A new source can be integrated in a single day.

Wikidata scores are capped at 0.85 (never 1.0) because it is publicly editable. NIST constants receive 1.0 as a primary authoritative source. **This confidence ceiling is a design choice, not a limitation.**

---

## Smart Contract Audit (ADR-014)

The ESMM kernel treats code analysis claims identically to any other domain. The `services/audit/` module decomposes Solidity contracts into per-function units (`contract_slicer.py`), classifies vulnerabilities against dual taxonomies (33 SWC categories + 8 Trail of Bits classes via `swc_taxonomy.py`), and runs each unit through the full ASSESS → CHALLENGE → ADJUDICATE pipeline (`audit_runner.py`).

Optional Slither integration provides a deterministic pre-analysis via the `SlitherAdapter` (ADR-012 pattern). When both paths run, a concordance check compares static analysis results against epistemic consensus.

---

## The Negative Space of Machine Knowledge

> *The conceptual kernel of EPP. Extended essay at [`docs/positioning/the_negative_space.md`](docs/positioning/the_negative_space.md).*

Everyone builds AI systems to produce answers. Better answers. Faster answers. More confident answers. EPP produces **disagreement** — not as a failure mode, but as the primary output.

When three models look at the same claim and return 0.9, 0.4, and 0.7, the conventional reading is: the system is uncertain, we need a better model. Our reading: the system just told you something no single model could. The *shape* of that disagreement — which architectures diverge, on which domains, by how much, and whether external data collapses or preserves the spread — is a measurement of epistemic difficulty that exists nowhere else in the world.

No benchmark captures this. MMLU measures what models get right. **EPP measures where models break differently.**

### The graph is not a knowledge base

Every attestation carries a score between 0 and 1, but the score is the shadow, not the substance. The substance lives in the 5-dimensional signature and in the pattern those dimensions form across claims, across models, across time.

A claim where all five dimensions are high and all models agree is boring. It tells you the sky is blue. A claim where agreement is high but stability is low tells you something fragile — the models agree today but might not tomorrow. A claim where centrality is high but semantic consistency is low tells you something structurally ambiguous — the concept matters but the models can't agree on what it means.

These patterns are the **topology of machine epistemology**. And topology is invariant under transformation — it survives model changes, prompt changes, language changes. It is the thing that remains when everything else shifts. The graph stores this topology as its primary structure.

### The flywheel is not about correction

The flywheel demo shows a score going from 0.43 to 0.89. That looks like error correction. It is not.

What actually happens: a model trained before the 2024 election cannot know who won. It produces a low score. Then Wikidata provides the answer. The score jumps. The conventional reading: the system corrected the model's ignorance. Any RAG system does this.

The EPP reading: the system measured the *distance between model knowledge and ground truth* for this specific claim, under controlled conditions, with a cryptographic anchor that proves the measurement happened. The delta (+0.46) is not a correction. It is a **measurement of model obsolescence on this claim**, now permanently on-chain, linked to the specific models, the specific Wikidata query, the specific moment in time.

Accumulate ten thousand of these measurements across seven domains and six model architectures and you have something that does not exist anywhere: a **calibrated map of where AI knowledge ends**, domain by domain, model by model, updated with every new attestation.

### The model that trains on the negative

Imagine a model trained not on the attestations but on the *structure of the graph itself*. Not *"Solana TPS exceeds 3000" → 0.85*, but *"Claims about blockchain performance metrics" → {divergence pattern: low across 7B models, high between 7B and reasoning models, collapses with deterministic source injection, stable across languages, unstable across prompt variations}*.

This model would learn the **meta-structure of epistemic difficulty**. It would know, before any evaluation, that a normative claim will produce high-variance low-stability patterns, that a post-cutoff empirical claim will produce a specific flywheel-sensitive signature, that a code vulnerability claim will discriminate between model families in a predictable way.

It would be a model of how models fail. And because the graph is built on divergence — not on consensus — the training data is structurally pure. There is no majority vote to overfit on. There is no "correct answer" to memorize. Only the topology of disagreement, invariant under the kind of gaming that plagues conventional benchmarks.

This is the dataset no one is building. Because everyone is building systems that converge. EPP built the system that measures the divergence — **the shadow that reveals the shape of the light**.

---

## The Cluster Vision (ADR-017)

EPP is designed as a network, not a tool. The unit of decentralization is the **Epistemic Cluster** — an autonomous instance operated by an identifiable Solana keypair, with its own models, its own data sources, and its own metrological frames.

Trust is not declared. It **emerges** from the cumulative track record, calculable by anyone directly from the blockchain. No reputation oracle needed — the attestation history *is* the reputation. Two independent observers reading the same chain compute the same reputation score for the same cluster.

**Real-world applications at scale:**

- **Compliance & AML.** A firm operates a cluster connected to OFAC, EU CFSP, and OpenSanctions. Financial institutions subscribe for KYC/AML verification. The cluster's value is its Brier accuracy score on sanctions screening — measurable, auditable.
- **Biomedical research.** A group connects a cluster to WHO databases, PubMed, ClinicalTrials.gov. Pharmaceutical companies and regulators verify drug efficacy claims. The Brier score on resolved clinical trials becomes the trust metric.
- **Geopolitical intelligence.** An institute deploys a cluster with ACLED, UCDP, SIPRI as deterministic sources. Governments, insurers, NGOs consume conflict assessments anchored on verifiable event data.
- **Smart contract security.** A DeFi security team runs a cluster specialized in Solidity audit. DAOs and launchpads consume its attestations before listing new protocols.
- **Physical sciences.** A cluster connected to NIST fundamental constants provides verified reference data. The flywheel corrects AI hallucinations on physical claims in real time.

Each cluster publishes its configuration via a signed ClusterManifest. Verification happens through results, not promises. When two clusters attest the same claim with different results, the divergence is not a problem — it is a **cross-cluster measurement** capturing differences in methodology, sources, and model selection. The best estimate of truth emerges from the competition, not from any single operator's authority.

**What the code already supports**: `submitter: Pubkey` in `EpistemicAttestation` as cluster operator identity; PDA seeds `[b"attestation", submitter, claim_hash]` naturally isolate clusters; `is_challenge` + `challenged_attestation` enable inter-cluster contestation; `consensus_meta` (ADR-010) carries each cluster's methodological fingerprint; `model_track_record` + Brier scores seed the reputation system; `infer_architecture_family()` measures intra-cluster diversity; `response_deduplicator.py` detects Sybil attempts.

**EPP was not designed as a tool that could become a network. It was designed as a network protocol of which only one node exists today.**

---

## Open Governance

Several design decisions are intentionally left open for the community. The codebase contains `COMMUNITY_DECISION_REQUIRED` markers at decision points including:

- Treatment of CONTESTED consensus (cap tier? reduce diversity bonus? require additional debate cycles?)
- Scope of ADR-009 (language neutrality in ESMM protocol)
- Slashing conditions for clusters with persistent Brier drift
- Minimum stake / bond for publishing attestations under a cluster identity

These decisions should be made by the open-source community, not by the founding team.

---

## Post-Hackathon Roadmap

**Immediate (weeks):**
- Interactive dashboard submission flow — form → live pipeline → on-chain push.
- `/onchain` feed extended beyond the initial 12 curated attestations.
- Additional deterministic source integrations (EU CFSP endpoint migration, OpenSanctions cloud).

**Medium-term (months):**
- Remaining formal invariants: INV-3 (PDA uniqueness), INV-5 (regression cut isolation), INV-7 (Brier proper scoring), INV-8 (consensus convergence) — Lean 4 proofs per ADR-020 roadmap.
- Epistemic Cluster network (ADR-017) — second node operating independently, inter-cluster contestation as first-order signal.
- Community governance of `COMMUNITY_DECISION_REQUIRED` markers.

**Long-term vision:**
- Progressive decentralization — Phase 1 (complete): one cluster proves the protocol works across five domains. Phase 2 (planned): 3–10 clusters prove the network works. Phase 3 (vision): DAO governance over protocol parameters, TEE/ZKP for cryptographic model verification, staking with slashing on bad attestations.
- **LiveBench on-chain** — every attestation a benchmark data point with full provenance. Unlike centralized benchmarks (MMLU, HellaSwag, LiveBench) that go stale and can be gamed, EPP's benchmark is alive, updated with every attestation, across every domain, by every cluster. The evaluation itself is auditable.
- **The graph that trains models on disagreement** — see *The Negative Space* above and the extended essay in `docs/positioning/`.

---

## From Intuition to Infrastructure

Before a single line of EPP-specific Python was written, the kernel concepts — divergence as signal, multi-agent deliberation under epistemic isolation, bidirectional knowledge transfer between models — had been explored over months of casual LLM-orchestration tinkering, with no project, no codebase, no architecture. EPP itself begins on **2026-02-13** with commit [`f12a922`](https://github.com/SimonBouhier/EPP_Verdict/commit/f12a922) (*"Phase 0.1-4.6: provider layer, ESMM pipeline, Solana bridge, 470 tests"*), forking that prior exploration into a Solana-anchored protocol within the Colosseum sprint eligibility window.

The path from that commit to today — 908 tests, 20 ADRs, 6 AI models deliberating on Solana devnet, a measurable +0.46 flywheel delta, five operational domains, 12 attestations live on-chain, a Lean 4 spec audited line-by-line over four phases (6 substantive theorems including tier cumulativity, 7 regression tests, 2 type-level invariants) — was walked by one person with no formal CS or math background, on a consumer GPU, with a logical mind, scientific transparency, and a belief that making AI models disagree on purpose would produce something more honest than making them agree.

This is what one person built during a hackathon sprint, on top of a prior personal exploration of LLM orchestration. The protocol is proven within its declared window — the commit history is the record. The architecture scales. The question is no longer whether it works. The question is what becomes possible when a team carries it forward.

---

## The Thesis

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

---

## References

1. Egberts, A. (2017). *The Oracle Problem.* SSRN.
2. Chainalysis (2023). *Oracle manipulation attacks rising.*
3. Duley et al. (2023). *The oracle problem and the future of DeFi.* BIS Bulletin No. 76.
4. Caldarelli, G. (2025). *Can AI solve the blockchain oracle problem?* arXiv:2507.02125.
5. Xian et al. (2024). *Connecting LLMs with Blockchain.* arXiv:2412.02263.
6. Zintus-Art et al. (2025). *Multi-Agent Argumentation for Trustworthy AI.*
7. Lin, Li et al. (2026). *Does Socialization Emerge in AI Agent Society?* arXiv:2602.14299.
8. UNESCO (2021). *Recommendation on the Ethics of Artificial Intelligence.* 193 Member States. https://en.unesco.org/artificial-intelligence/ethics
9. UNESCO (2021). *Letting the Sun Shine In: Transparency and Accountability in the Digital Age.* (26 high-level transparency principles for internet platform companies.)
10. Cahen, M. (2025). *La blockchain comme preuve : une révolution pour le droit d'auteur.* [Case law survey — Marseille, Milan, Luxembourg, CJUE, U.S. Copyright Office, Hangzhou.]
11. Soklakov, A. *Economics of disagreement.* arXiv.
12. Choi et al. (2025). *Conformity-driven collapse in multi-agent LLM debate.*
