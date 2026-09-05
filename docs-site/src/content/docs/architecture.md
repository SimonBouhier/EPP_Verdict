---
title: "EPP — current code map"
editUrl: false
---

**Reviewed: 5 September 2026, Python baseline `84879d2`.** This map separates
maintained local scope, historical surfaces and branch-specific work.
The previous detailed inventory is
[preserved here](/history/2026-09-05/architecture/).

## Main path

```text
CLI / caller
    → metrological frame + declared input
    → ESMM deliberation or deterministic source path
    → portable attestation + provenance
    → SQLite execution state
    → reviewable proposal
    → Git checks and authorized merge (external acceptance boundary)
```

Source context can also feed VERIFY through the flywheel. Git acceptance and
epistemic confidence remain separate.

## Maintained surfaces

| Location | Responsibility |
|---|---|
| `cli/epp_cli.py` | Local commands: ask, query, frames, source verification and audit |
| `services/esmm/pipeline.py` | Pipeline orchestration and result assembly |
| `services/esmm/orchestrator.py`, `cycle_manager.py` | EXPLORE / VERIFY runs and model cycles |
| `services/esmm/consensus_engine.py`, `triplet_extractor.py` | Extraction and consensus |
| `services/esmm/attestation.py` | Attestation model, crystallization, serialization |
| `services/providers/` | Provider interfaces and implementations |
| `services/sources/adapters/`, `services/esmm/source_anchor_builder.py` | Source observations and anchors |
| `services/metrology.py` | Frames, canonical hashes and predefined registry |
| `database/` | SQLite storage, source snapshots, attestations and run state |
| `services/governance/proposal.py` | Canonical proposals and evidence references |
| `scripts/validate_proposals.py` | No-network proposal and local-evidence validation |
| `governance/proposals/` | Canonical proposal directory; no proposal JSON at review |
| `Formal/` | Lean specification of selected invariants |
| `tests/test_lean_conformance*.py` | Empirical Python/specification conformance |

The [verification snapshot](/current-status/#verification-snapshot) states
which checks were rerun. This inventory does not qualify every provider,
source, command or model live today.

## Static sites

| Location | Role |
|---|---|
| `docs-site/` | Astro/Starlight: current documents, decisions, labelled history |
| `docs-site/scripts/sync-docs.mjs` | Generates and checks portal content against sources |
| `ui/` | React/Vite viewer of historical benchmarks |
| `ui/public/data/` | Committed archive snapshot, no automatic refresh |
| `demos/benchmark_runs/`, `data/devnet_pushed.json` | Historical evidence, unchanged |

Neither site is the Python service or the Lyra application.
Source changes, local builds and public deployment are separate states.
See [publishing and maintenance](/publishing/).

## Retired and separate code

- `services/solana/`, `programs/epp/`, Anchor/Rust publication scripts and
  former on-chain commands are historical under ADR-022. Compatibility imports
  do not reopen publication.
- The conversational shim and Vigie sidecar live on
  `fix/td-002-graph-seeder-adapter`, not this `main` baseline. The sidecar was
  introduced at `3a274cd`.
- The future Lyra attestation bridge is not implemented and validated on
  `main`. Documentation maintenance does not change frozen campaign checkouts.
- Origami's Fisher bridge remains closed for the v4–v7 series.

## Evidence boundaries

The validator verifies local bytes and only declares external URLs.
Conformance tests do not prove the complete runtime. Historical benchmarks do
not measure current systems. Source adapters do not guarantee universal source
authority or freshness.
