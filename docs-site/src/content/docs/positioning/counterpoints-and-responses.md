---
title: "Counterpoints and Surviving Thesis"
description: "Every Pyth price feed includes a confidence interval — not just a price,"
---
> Stress-test of the EPP positioning against the strongest counter-arguments.
> The five points that survive the challenge constitute the defensible thesis.
>
> *Originally compiled as `5 Counterpoints That Weaken Full Gap.md` in the
> sprint working dir. Migrated 2026-04-23.*

## Five Counterpoints That Weaken "Full Gap"

### 1. Pyth already publishes uncertainty on-chain

Every Pyth price feed includes a confidence interval — not just a price,
but a measure of publisher disagreement/uncertainty. Smart contracts can
already halt operations when confidence > threshold. Pyth's own blog
calls this *"the only oracle solution offering a confidence interval
metric for every data feed."* This is epistemic uncertainty on-chain,
today, on Solana.

**Damage to thesis**: the claim "nobody is anchoring epistemic uncertainty on-chain" is technically false. Pyth does it for prices.

### 2. Switchboard Functions + SAIL can run arbitrary inference with TEE attestation

Switchboard's SAIL (Switch Forward Attestation Inference Layer) runs
arbitrary code inside TEEs with on-chain attestation that the code
executed as intended. You could build EPP's multi-model pipeline as a
Switchboard Function today — run 3 LLMs, compare outputs, publish
results, with hardware-attested proof. 6,000+ custom data feeds already
exist. Switchboard explicitly positions itself as *"not just an oracle —
programmable data infrastructure."*

**Damage to thesis**: the infrastructure to do what EPP does already exists as a platform on Solana. The "nobody can do this" framing is wrong — nobody has chosen to build this specific product on top of available infra.

### 3. UMA already resolves qualitative claims with LLM assistance

UMA's optimistic oracle handles explicitly subjective/intersubjective
data — "Did this protocol get hacked?", "Who won the election?", "Should
this governance action execute?" It's Polymarket's resolution backbone.
And as of H1 2025, UMA started using LLMs to propose and dispute claims,
automating what was previously human-only. The Managed Optimistic Oracle
V2 (MOOV2) adds proposer whitelisting for quality control.

**Damage to thesis**: qualitative claim verification on-chain exists and is battle-tested at scale (Polymarket volume: $27.9B+). The claim "nobody does qualitative" is wrong. UMA does it, albeit on Ethereum, not Solana.

### 4. Supra Threshold AI Oracles do multi-LLM consensus for qualitative events

Announced May 2025 with a whitepaper. Multiple domain-specialist LLM
agents deliberate in committees, assess contextual data from diverse
sources, and produce a threshold BLS signature when quorum is reached.
Handles questions like "Did this regulatory change really occur?" and
"Should this liquidation execute given current market sentiment?"

**Damage to thesis**: the strongest counterpoint. Supra is building multi-LLM consensus for qualitative events with on-chain proof. The "nobody is doing this" claim faces a funded, shipped competitor.

### 5. Chainlink Functions + DECO = programmable AI oracle with attestation

Chainlink Functions lets smart contracts call arbitrary APIs (including
LLM endpoints) across DON nodes that independently execute and aggregate
results. DECO adds privacy-preserving attestation proving data
provenance without revealing underlying data. Combined, a developer
could build "call 5 LLMs, aggregate, attest methodology" today.
Chainlink has even blogged about *"proof of thought"* attestations for
LLM outputs.

**Damage to thesis**: the building blocks exist in production at the dominant oracle provider.

---

## What Survives the Challenge

Here's what's still true after stress-testing:

### A. Nobody measures the *quality* of consensus

Every system above treats consensus as binary: threshold reached or not,
dispute resolved or not, confidence within bounds or not.

- Pyth's confidence interval is statistical spread, not epistemic calibration.
- UMA's dispute resolution is pass/fail — *"was the proposer correct?"*
- Supra's threshold signature says *"quorum agreed"* — not *"how much did they agree, and how well-calibrated were they?"*
- None use proper scoring rules (Brier scores, log-scoring) that incentivize honest probability estimates.

**EPP's insight that the degree and calibration of disagreement is itself a valuable signal has zero implementation anywhere.**

### B. Nobody does methodology traceability

None of the above record:

- Which specific models assessed the claim (model IDs, versions, weights).
- What parameters were used (temperature, system prompt, framing).
- What frame was applied (how the question was posed to each model).
- Individual model outputs alongside the aggregate.

Supra produces a threshold signature — you know the quorum agreed, but
you can't audit *why*. UMA records the proposal and dispute, not the
reasoning. Pyth records the aggregate, not publisher-level rationale.

### C. Nobody rewards diversity

Existing systems penalize disagreement (outlier rejection in Pyth,
disputes as friction in UMA, slashing deviants in Switchboard). EPP's
diversity bonus — rewarding model heterogeneity because epistemically
diverse panels are better-calibrated — inverts the standard assumption.

### D. The Solana-native gap is real for non-price data

UMA is Ethereum-only. Supra is on its own L1. Chainlink Functions is
EVM-first. On Solana specifically, oracles handle prices (Pyth,
Switchboard, Chainlink) or VRF (ORAO). There is no native Solana oracle
for qualitative claim assessment.

### E. "AI oracle" ≠ "epistemic oracle"

Every competitor uses AI as a *better data pipe* — faster proposing
(Predict Link), smarter aggregation (APRO), automated disputes
(UMA+LLM). Nobody uses AI to produce *epistemic metadata* — calibration
scores, disagreement distributions, diversity measurements — as the
primary output. The oracle output everywhere else is "the answer."
EPP's output is *"the answer + how much we should trust it + why."*

---

## Revised Thesis

**Original** (over-claims):
> *"Nobody is anchoring the epistemic uncertainty of AI model outputs on-chain with methodology traceability"*

**More honest version** (defensible):
> *"Several projects anchor some form of AI-assisted resolution or confidence metrics on-chain. But nobody measures the calibration quality of multi-model consensus, nobody records full methodology traceability (model IDs + parameters + frames), and nobody treats disagreement as a first-class epistemic signal rather than noise to be eliminated. The gap isn't 'qualitative claims on-chain' — it's 'epistemic calibration as an on-chain primitive.'"*

That's a narrower claim, but a more defensible one — and arguably more
interesting because it positions EPP not as filling an empty category,
but as building a novel primitive (calibrated epistemic measurement)
that sits *on top of* the existing oracle landscape.
