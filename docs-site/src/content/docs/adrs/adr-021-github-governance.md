---
title: "ADR-021: GitHub governance and promotion boundary"
description: "EPP deliberates, GitHub governs promotion, and Solana remains optional."
---

**Date**: 2026-08-12
**Status**: Active

EPP's distinctive work happens before publication: ESMM deliberation,
crystallization, provenance, SQLite storage, and production of a portable
attestation. Solana remains a useful devnet publication adapter, but it is no
longer an internal dependency or governance authority.

## Decision

- **EPP deliberates** and produces attestations plus evidence.
- **SQLite executes and retains** debates, runs, graphs, and intermediate state.
- **GitHub governs** proposal, review, checks, and promotion through pull requests.
- **Solana may publish** a promoted artifact through its optional adapter.

A protected merge records acceptance into the project registry. It does not
turn a proposal into truth or replace its epistemic confidence tier.

## Proposal artifact

`services/governance/proposal.py::AttestationProposal` carries the full
attestation, exact frame hash, content-addressed evidence references, target
branch, and a deterministic integrity hash. Its decision is always
`proposed`: only the external authorized merge represents acceptance.

CI scans `governance/proposals/**/*.json`, checks each artifact and verifies
repository-local evidence byte for byte. HTTPS references are never fetched by
the merge job; their acquisition remains outside the trusted boundary.

## Security boundary

A pull request is a **promotion boundary, not an ingestion bus**. Untrusted
sources are processed in quarantine without secrets or write credentials.
Only a structured proposal reaches a branch. CI and human review precede a
manual merge, and downstream consumers read merged artifacts only.

The target default-branch rules require PRs, prevent force-push and deletion,
require Python and Lean checks, and require conversation resolution. The solo
phase uses zero formal approvals because authors cannot approve their own PRs;
the merge remains manual.

GitHub is centralized and does not provide blockchain immutability. Rulesets,
signed tags, and backups mitigate—but do not eliminate—administrator and
account-compromise risks. This is proportionate to the project's current
internal governance needs.
