---
title: "ADR-022 — Post-blockchain refocus: EPP as a personal attestation organ"
description: "Dependencies: ADR-007 (append-only), ADR-021 (GitHub governance)"
---
**Date**: 2026-08-29
**Status**: Active
**Dependencies**: ADR-007 (append-only), ADR-021 (GitHub governance)

## 1. Context

ADR-021 had already demoted Solana to an "optional devnet adapter": EPP
deliberates, SQLite stores, GitHub governs, Solana optionally publishes.

Since then, actual use has settled the question. EPP serves as a **personal
attestation organ** within the triptych (the organs-and-bridges doctrine of
`lyra_reborn`): its intended consumer is Lyra, through a thin bridge unfrozen
only upon validation — not an external audience. The decision has been made
(Simon, 2026-08) to **abandon the blockchain path** altogether, not merely to
keep it optional.

Yet the surface inherited from the Colosseum sprint still says otherwise:
README and badges advertise Solana devnet, twelve on-chain attestations and a
public dashboard; the WHITEPAPER argues the legal recognition of blockchain
evidence; TD-001 maintains a data duplication whose sole purpose is that
dashboard. This contradiction between documents and reality is exactly the
kind of debt the triptych forbids itself.

## 2. Decision

1. **Identity.** EPP is a **local, personal** epistemic attestation engine:
   multi-model deliberation, crystallization, provenance, portable
   attestations. An independent organ, never a dependency — eventually
   consumed by `lyra_reborn` through a thin bridge.

2. **Retirement of the blockchain layer.** The Solana bridge, its client and
   any on-chain publication move from "optional" to **retired**: code frozen
   as-is, unmaintained, no new publication. The twelve existing devnet
   attestations remain historical artifacts — the freeze is not debt, it is a
   closure (in the sense of the Origami v7 closure).

3. **Single trust anchor.** Accepting a proposal is a Git event: protected
   branch, pull request, authorized merge (ADR-021). No other registry is
   authoritative.

4. **Licensed pruning.** This refocus authorizes, without a further ADR:
   realigning README, badges and WHITEPAPER (removing on-chain promises,
   reframing the showcase as a historical demo); demoting the public dashboard
   to a demonstration artifact; resolving TD-001 by simplification (the
   `ui/public/data/` duplication no longer needs serving) rather than by the
   previously envisioned API; closing PR #2 (Vercel analytics).

## 3. Consequences

### Positive

- Documents tell the truth again: advertised surface = maintained surface.
- Reduced maintenance load (Anchor/Cargo, dashboard, data parity).
- The clarified identity simplifies the future Lyra ↔ EPP bridge: a thin
  contract between two local organs, with no detour through a public registry.

### Accepted limits

- Loss of the public showcase and of the "third-party verifiable anchoring"
  argument. Should a need for external publication arise again, it will be a
  new, explicitly pre-registered effort — not a silent reactivation.
- The frozen Solana code will age unmaintained; this is accepted.

## 4. Migration

The pruning actions of §2.4 are follow-up work (see the triptych's central
TODO, section B); they go through ADR-021 governance like any promotion. This
ADR executes none of them: it licenses them.

## 5. Non-goals

- No historical evidence is deleted (ADR-007 remains sovereign).
- The deliberation core, the attestation format and the formal layer
  (ADR-020) are unchanged.
- This ADR does not reopen the blockchain debate: it records its closure.
