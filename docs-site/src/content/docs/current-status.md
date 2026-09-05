---
title: "EPP — current scope and evidence"
editUrl: false
---

**Reviewed: 5 September 2026.** This is the current status reference.
[ADR-021](/adrs/adr-021-github-governance/) and
[ADR-022](/adrs/adr-022-post-blockchain-refocus/) govern this scope.
Historical documents describe their own period, not the current roadmap.

## Purpose

EPP is a local, personal engine for deliberation and epistemic attestation.
It records claims, model disagreement, methodology and provenance in portable
artifacts. Its intended consumer is Lyra, through a future, separately validated
interface. The two projects remain independent.

An attestation describes a process and its result. A hash establishes content
integrity, not the truth of a claim. A Git merge records project acceptance,
separately from epistemic confidence.

## What exists

| Surface | Current state | Evidence |
|---|---|---|
| Deliberation | Python ESMM pipeline with EXPLORE and VERIFY modes | `services/esmm/pipeline.py`, `services/esmm/orchestrator.py` |
| Source-backed paths | Deterministic adapters and source-context injection into VERIFY | `services/sources/adapters/`, ADR-012, ADR-018 |
| Attestations | Portable JSON, hashes, model votes and five-dimensional signatures | `services/esmm/attestation.py` |
| Persistence | SQLite execution state, attestations and provenance | `database/` |
| Metrology | Versioned frames in the core, independent of publication | `services/metrology.py` |
| Governance | Deterministic proposals, evidence validation and Git/PR promotion boundary | `services/governance/proposal.py`, `scripts/validate_proposals.py` |
| Formal specification | Lean specification and Python conformance tests | `Formal/`, ADR-020; no proof of the entire runtime |
| Documentation portal | Current descriptions plus labelled historical records | `docs-site/` |
| Dashboard | Read-only historical benchmark archive | `ui/`; no live model execution |

An adapter's presence does not demonstrate that its remote service or
credentials work today. Source availability and model quality need separately
scoped validation.

## Closed and pending work

- **Blockchain is retired**, following the August 2026 decision in ADR-022.
  Solana code is frozen historical material, no longer maintained, with no new
  publication in scope. The twelve recorded devnet attestations are historical
  evidence, not a live service commitment.
- The former cluster, staking, tokenomics and on-chain benchmark roadmap is
  historical, not scheduled development.
- The **Lyra–EPP attestation bridge is pending validation**. The Vigie quarantine
  sidecar exists at commit `3a274cd` on the separate
  `fix/td-002-graph-seeder-adapter` line; it is absent from `main` at `84879d2`.
  This does not authorize integrating that branch or changing a frozen checkout.
- The canonical `governance/proposals/` directory contained no proposal JSON
  at review. Validator tests establish fixture behavior, not a completed
  real-world promotion lifecycle.
- PR #2, the former analytics installation proposal, was still open on
  5 September 2026. ADR-022 licenses its closure; that separate repository
  action has not been performed by this documentation update.

## Verification snapshot

On **5 September 2026**, **131 targeted Python tests passed** locally, covering
governance, proposal validation, Lean conformance, attestations, source anchors,
the mocked pipeline and the flywheel. This was not a new full-suite run,
external-source check, live-model qualification or Lean rebuild.

From the EPP repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_adr021_github_governance.py tests/test_adr021_proposal_validator.py tests/test_lean_conformance.py tests/test_lean_conformance_property.py tests/test_phase03_attestation.py tests/test_adr012_source_anchor.py tests/test_phase3_pipeline.py tests/test_adr018_flywheel.py
```

Earlier full-suite counts belong to their dated records. They are not displayed
as a continuously current badge. Site builds and synchronization checks are
separate from Python behavior and scientific performance.

## Place in the triptych

- **Lyra:** P6 is the main effort; local session persistence is implemented.
  Conversational context, restored exchange display and durable user feedback
  remain incomplete. P7 is an instrument-development workshop; H11 is `UNTESTED`.
- **Origami:** v4–v7 is closed. The recorded v7 result is 0/6 under its frozen
  protocol. The current Fisher bridge remains closed; this is not a general
  impossibility claim about epistemic geometry.
- **EPP:** maintain attestation and provenance contracts; validate any future
  bridge before adopting it.

Lyra facts refer to local revision `d7353d4` (not yet pushed at review), and
Origami facts to `1dfa008`. This is a dated orientation, not a synchronized feed.
