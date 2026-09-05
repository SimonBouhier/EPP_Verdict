---
title: "EPP — a reviewable record of model deliberation"
editUrl: false
---

EPP helps its operator inspect how a knowledge claim was assessed: which models
participated, where they disagreed, which sources were consulted, and under
which methodology the result was produced.

The project is a **local, personal attestation engine** within the triptych.
Lyra is its intended future consumer. That interface remains a separate
validation task, not an existing integrated product.

## The working loop

1. Declare a claim and its metrological frame.
2. Run structured deliberation, use a deterministic source path, or provide
   source context to deliberation where the configured path allows it.
3. Preserve the claim, votes, disagreement, methodology and provenance.
4. Package evidence for review. An authorized Git merge records project
   acceptance; the producer cannot declare its own proposal accepted.

## What the record can establish

Portable attestations and hashes make the recorded process inspectable.
They help locate disagreement and compare results within methodological limits.
They do not guarantee correctness, independent errors or calibrated confidence.
Acceptance by the project and truth remain separate questions.

## Where the project stands

Python deliberation, attestation, SQLite and governance components exist.
Their [current status and dated checks](/current-status/) describe the
scope inspected. The Lean layer specifies selected invariants and is connected
to Python by conformance tests, not an end-to-end correctness proof.

Blockchain publication was retired in August 2026 under
[ADR-022](/adrs/adr-022-post-blockchain-refocus/).
The [dashboard](https://epp-verdict.vercel.app) preserves historical
demonstrations. Its results describe saved runs, not today's models or services.

## Next work

Keep the maintained scope legible, preserve attestation and provenance
contracts, and validate a small Lyra interface when that work is opened.
The cluster and on-chain roadmap belongs to the
[historical pitch](/history/2026-09-05/pitch/).

Read the [whitepaper](/whitepaper/) for the present design and its limits.
