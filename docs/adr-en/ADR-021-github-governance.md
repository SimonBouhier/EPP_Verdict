# ADR-021 — GitHub as the governance and promotion boundary

**Date**: 2026-08-12
**Status**: Active
**Dependencies**: ADR-006 (claim hash), ADR-007 (append-only), ADR-012 (deterministic sources), ADR-020 (formal specification)

## 1. Context

EPP was presented around Solana anchoring even though its distinctive work
happens upstream: ESMM deliberation, crystallization, provenance, SQLite
storage, and production of a portable attestation. The blockchain remains a
useful publication demonstration, but it is not required for reasoning,
measurement, or the internal governance of a GitHub-hosted project.

That apparent centrality blurred three boundaries: publication could look like
epistemic authority, generic metrological frames lived under the Solana
package, and human acceptance was less explicit than technical submission.

## 2. Decision

EPP adopts the following separation:

- **EPP deliberates**: ESMM produces attestations and evidence;
- **SQLite executes and retains**: debates, runs, graphs, and intermediate state;
- **GitHub governs**: branches, pull requests, checks, and merges represent
  proposal, review, and promotion;
- **Solana may publish**: its bridge and client remain optional devnet adapters
  with no dependency from the core.

A merge commit on the protected branch records acceptance into the project
registry. It does not turn a proposal into truth or replace its epistemic
confidence tier.

### 2.1 Canonical proposal artifact

`services/governance/proposal.py::AttestationProposal` wraps the complete
portable attestation, exact metrological frame hash, SHA-256-addressed evidence
references, target branch, and a deterministic `proposal_hash` verified on
read.

Its `decision` field only accepts `proposed`. An agent cannot write `accepted`
into its own artifact; acceptance is the external authorized merge event.
Evidence order is canonicalized and any undetected content change causes hash
validation to fail.

CI scans `governance/proposals/**/*.json`, validates each artifact, and checks
repository-local evidence byte for byte. It never downloads HTTPS references;
acquisition stays outside the merge job and its permissions.

Historical `FrameGovernance` values remain inside frame hashes so published
attestations keep the same methodology identity. They describe the amendment
process imagined when a frame was created; they grant no promotion authority,
which now belongs to the protected merge.

### 2.2 Security boundary

A pull request is a **promotion boundary**, not an ingestion bus.

```text
untrusted source
    -> quarantine / isolated job without secrets
    -> ESMM + deterministic checks
    -> structured proposal on a branch
    -> CI and review
    -> human merge to main
    -> Lyra consumption or optional publication
```

Raw sources and PR comments do not become canonical merely by being present.
The proposal producer cannot merge or write directly to `main`. Jobs processing
untrusted content receive no secrets, write token, or deployment environment.
Consumers only read reviewed, merged artifacts. `pull_request_target` must not
execute untrusted code or content.

## 3. Target GitHub rules

After the Python controls are stable and green, the default-branch ruleset
should require pull requests, block deletion and force-push, require the
`Python governance gate` and `Lean formal gate` checks, require conversation
resolution, and retain a manual merge identity distinct from the producing
job.

The initial solo workflow requires zero formal approvals because GitHub does
not allow authors to approve their own pull requests. Merge remains manual. A
required approval should be added when a second human reviewer is available.

## 4. Consequences

The project gains inexpensive, diffable, testable governance and separates
epistemic scoring from promotion authority. Solana support stays available
without imposing its dependencies on the core. GitHub is centralized and its
history is not blockchain-immutable; administrator access and account
compromise remain threats mitigated by rulesets, signed tags, and backups.

## 5. Migration

1. move generic metrology to `services/metrology.py`;
2. retain `services/solana/metrological_frame.py` as an import shim;
3. add the proposal envelope and integrity tests;
4. add Python CI and the no-network proposal validator;
5. open a dedicated PR and enable rules only after green checks;
6. retain the Solana program and devnet push as opt-in publication.

Deleting Solana code, migrating the SQLite schema, and refactoring Lyra are out
of scope for this ADR.
