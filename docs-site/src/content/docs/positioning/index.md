---
title: "Historical positioning material"
editUrl: false
---

> **Historical material.** Preserved in its original context. Former blockchain, cluster and sprint claims do not define the current project. Read the [current scope](/current-status/) and [ADR-022](/adrs/adr-022-post-blockchain-refocus/).

> **Historical context, classified 2026-09-05.** These sprint-era documents
> retain their original arguments and comparisons. Their blockchain, cluster
> and Colosseum assumptions are not the current roadmap. Read
> [CURRENT_STATUS](/current-status/) and ADR-021/022 for the maintained scope.

These documents are the **working material** behind the project's
public narrative (`README.md`, `PITCH.md`, `WHITEPAPER.md`). They are
tracked in git, and therefore public on GitHub, because the project is
an open-source solo build and the reasoning leading to the public
claims is itself part of the record. A reader wondering *"how was the
defensible thesis arrived at?"* or *"how does EPP position against
Supra / UMA / Pyth?"* should be able to see the work.

They are **not normative**. The README, PITCH, and WHITEPAPER are the
official project narrative; these documents are the scaffolding that
produced them. If this folder contradicts the public docs, the public
docs win.

| File | Purpose |
|:-----|:--------|
| [`competitive_landscape.md`](/positioning/competitive-landscape/) | Tier-by-tier scan of EPP-adjacent projects (Epistemia, Predict Link, Edge Bounty, ORA, Ritual, Supra, etc.) and verdict on the gap |
| [`counterpoints_and_responses.md`](/positioning/counterpoints-and-responses/) | Stress-test of the EPP positioning against the strongest counter-arguments (Pyth confidence intervals, UMA optimistic disputes, Switchboard SAIL, Supra Threshold AI, Chainlink Functions+DECO). The five points that survive the challenge are the defensible thesis. |
| [`formal_methods_landscape.md`](/positioning/formal-methods-landscape/) | Panorama of formal verification in crypto smart contracts (Certora, Lean 4, Coq, Kani) — justifies the rarity of EPP's Lean 4 layer (3 / 5,400 Colosseum projects) |
| [`colosseum_track_strategy.md`](/positioning/colosseum-track-strategy/) | Track and prize positioning for Colosseum: Infrastructure primary + Public Goods Award secondary, framing per audience (Infrastructure / AI / DeFi / Public Goods judges) |
| [`the_negative_space.md`](/positioning/the-negative-space/) | Conceptual essay — EPP as a measurement of the *negative* of knowledge (the topology of disagreement). Source material for the philosophical sections of WHITEPAPER.md |

## Conventions

- **Public docs cite primary sources, not this folder.** README,
  WHITEPAPER, and PITCH cite UNESCO, BIS, Caldarelli, jurisprudence,
  ADRs — not internal strategy memos. The material here informs the
  public docs; it does not appear *in* them as authority.
- **No marketing claims.** Honest assessment. The counterpoints file
  exists precisely to prevent EPP from over-claiming in the pitch.
- **Update over fragment.** When new strategic material is produced,
  edit an existing file rather than spawning new ones — this folder
  should stay readable as a whole.

Initially populated 2026-04-23 from sprint working documents at
`Work_in_Progress/sprint/SPRINT/audit_concu/` and
`Work_in_Progress/sprint/SPRINT/THE_NEGATIVE_SPACE.md`.
