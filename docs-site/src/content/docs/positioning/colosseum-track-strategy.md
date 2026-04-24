---
title: "Colosseum Track and Prize Strategy"
description: "The pattern is clear: technical primitives win in Infrastructure. AI products win in AI. EPP is a primitive, not a product."
---
> Track and prize positioning: Infrastructure primary + Public Goods Award secondary,
> framing per audience.
>
> *Originally compiled in the sprint working dir. Migrated 2026-04-23.*

## Where EPP's Cousins Won Prizes

| Project | Prize | Track | Hackathon | Why it matters |
|:--------|:------|:------|:----------|:---------------|
| **Flowgate** (on-chain oracle) | HM Infrastructure | Infrastructure | Renaissance Mar 2024 | Oracle primitive won in Infrastructure |
| **Attest Protocol** (on-chain attestations) | Public Goods Award $10K | Infrastructure + DAOs | Radar Sep 2024 | Attestation infra won a special award |
| **Excalead** (AI + formal verification) | HM Infrastructure | Infrastructure | Cypherpunk Sep 2025 | AI verification won in Infrastructure |
| **Project Plutus** (AI agent deployment) | 2nd Place AI $20K | AI + DeFi | Breakout Apr 2025 | AI platform won in AI track |
| **Forge AI** (AI agent testing) | HM AI $5K | AI + Consumer + Gaming | Breakout Apr 2025 | AI evaluation won in AI track |
| **Shadow Book** (FHE for SVM) | HM Infrastructure $5K | AI + DeFi + Infrastructure | Breakout Apr 2025 | Cryptographic primitive won in Infrastructure |

**The pattern is clear: technical primitives win in Infrastructure. AI products win in AI. EPP is a primitive, not a product.**

---

## The Four Positioning Options, Ranked

### 1. Infrastructure (Primary) + Public Goods Award play — **the move**

- **Attest Protocol** is the direct precedent. It won Public Goods for building *"unified trust and reputation infrastructure for on-chain attestations"* — that's almost EPP's one-liner with "epistemic" prepended. Judges have already validated this category of submission.
- **Infrastructure is where primitives survive crowding.** Cypherpunk Infrastructure had 570 submissions (36% share) — less than Consumer Apps (1,090) or DeFi (752). Competition is other infra builders, not "another AI chatbot."
- **Oracle wins happen here.** Flowgate won HM Infrastructure. Excalead (AI + formal verification) won HM Infrastructure. The judges have pattern-matched "novel verification primitive" → Infrastructure.
- **EPP's narrative fits Infrastructure**: *"A new oracle primitive that produces epistemic calibration as an on-chain signal — any protocol can consume it."*

**Framing**: *"Epistemic oracle infrastructure"* — not "AI tool," not "DeFi app." A primitive that other protocols compose with, like Pyth or Switchboard. The demo shows a protocol consuming EPP attestations, not a standalone UI.

### 2. AI (strong alternative if the hackathon has an AI track)

Only Breakout (Apr 2025) had a dedicated AI track (501 submissions). If the next hackathon has one:

- EPP would be the most differentiated AI submission. The AI track is drowning in agent assistants (270 in the "AI-Powered DeFi Assistants" cluster alone). A submission that *evaluates* AI outputs instead of being an AI assistant stands out.
- Project Plutus won 2nd Place AI ($20K) for AI deployment infra — not for being an agent, but for enabling agents. EPP follows this pattern.
- **Risk**: AI track judges may expect a demo that "does something with AI" in a consumer-visible way. EPP's value proposition is more subtle — *"the oracle doesn't trust itself"* requires explanation.

**Framing if AI track**: *"The AI track's missing layer — not another agent, but the verification layer that proves agents are trustworthy."*

### 3. DeSci — **skip this**

DeSci is not a track at any Colosseum hackathon. DeSci projects (Baseroot, ProofSci, openQuanta, DeSci Reviews — 7 found in the corpus) are scattered across Infrastructure, Consumer Apps, AI, and RWAs tracks. None won prizes.

Positioning EPP as DeSci:

- Forces judges to understand a niche framing ("epistemic proofs for science") that narrows the market.
- Competes with peer review platforms that solve a more legible problem.
- Misses EPP's core value — it's not for science specifically, it's a general epistemic primitive that *could* be used for science.

DeSci is a use case, not a positioning. Mention it in the demo (*"here's how DeSci protocols could use this"*) but don't lead with it.

### 4. Multi-track submission (Infrastructure + DeFi or Infrastructure + RWAs)

Colosseum allows submitting to multiple tracks. Winners often do this:

- Shadow Book: AI + DeFi + Infrastructure → won in Infrastructure
- Forge AI: AI + Consumer + Gaming → won in AI
- Predict Link Oracle: Infrastructure + RWAs → no prize

**Recommendation**: Submit Infrastructure + RWAs (if Cypherpunk-style) or Infrastructure + AI (if Breakout-style). Infrastructure is the primary; the second track is surface area.

---

## How to Frame It for Each Audience

| Audience | Frame | One-liner |
|:---------|:------|:----------|
| **Infrastructure judges** | Oracle primitive | *"Epistemic oracle that measures how much AI models disagree, not just what they agree on — a new on-chain signal any protocol can consume."* |
| **AI judges** | Verification layer | *"Multi-model consensus with calibration scoring — the missing trust layer for autonomous AI agents on Solana."* |
| **DeFi judges** | Risk primitive | *"Qualitative risk oracle — like Pyth for prices, but for subjective claims: regulatory interpretations, protocol risk assessments, governance decisions."* |
| **Public Goods Award** | Neutral infrastructure | *"Open, permissionless epistemic attestation service — any protocol can verify AI consensus quality without trusting a single model or operator."* |

---

## Bottom Line

**Lead with Infrastructure. Target Public Goods Award. Add a secondary track for surface area.**

The Public Goods play is the wedge. Attest Protocol proved judges
reward attestation infrastructure in this category. The pitch: EPP is
a public good for AI trust — open protocol, permissionless verification,
composable attestations. Anyone can use it, nobody controls it. That's
the narrative that won $10K for Attest Protocol, and EPP has a stronger
technical story (Brier scores, multi-model calibration, methodology
traceability vs. generic attestation schemas).

**The one thing to nail in the demo**: show a protocol consuming an EPP
attestation and making a better decision because of the calibration
metadata. Don't just show *"we ran 5 models."* Show *"here's what
happens when the models disagree a lot vs. a little, and here's how the
consuming protocol reacts differently."* That's what makes EPP an
Infrastructure primitive and not an AI science project.
