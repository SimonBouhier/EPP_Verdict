# EPP — deliberation, attestation and provenance

**Current-scope edition — 5 September 2026.** This edition describes the
post-blockchain project. The previous whitepaper is
[preserved verbatim](docs/history/2026-09-05/WHITEPAPER.md), including its
original arguments, references and roadmap. It is historical context.

## Purpose

EPP is a local, personal engine for examining knowledge claims and preserving
how their assessment was obtained. It combines structured model deliberation,
source observations, metrological frames and portable attestations.

EPP remains independent of Lyra. A future bridge may let Lyra request an
attestation and retain its evidence, scope and uncertainty. That bridge requires
separate validation; the codebases are not currently an integrated attestation
product. [Current status](docs/CURRENT_STATUS.md) identifies implemented and
branch-specific work.

## Deliberation and source paths

ESMM supports open exploration (EXPLORE) and structured assessment (VERIFY).
VERIFY organizes assessment, challenge and adjudication. The sequence makes
outputs and disagreement inspectable; correlated agreement does not become
independent evidence.

A declared deterministic source path can bypass deliberation. Source snapshots
and hashes record the observation used. The flywheel can inject source context
into VERIFY. An adapter's existence does not establish the current availability,
authority or freshness of each response. Those conditions belong to the
particular run and its evidence. Relevant decisions: ADR-011, ADR-012, ADR-018.

## Metrological frames

Frames describe the methodology under which a result was produced; canonical
hashes bind the referenced content. Methodology changes remain visible.
Scores from different frames are not automatically comparable.

The current implementation is in `services/metrology.py`. Historical imports
under `services/solana/` are compatibility surfaces, not a blockchain
dependency of metrology.

## Attestation contract

The portable record contains the claim, model votes, consensus score,
classification, provenance and a five-dimensional signature: agreement,
semantic consistency, graph centrality, stability and relation diversity.

These are protocol measurements. Names and numeric ranges do not establish
truth, calibrated confidence or statistically independent judgments.
Performance claims require a suitable evaluation with its own declared scope.

The claim hash identifies canonical claim content and its frame. The proposal
hash binds the wider review envelope. Integrity does not prove the enclosed
assertion correct.

## Persistence and acceptance

SQLite holds execution state, attestations and provenance. The deterministic
proposal envelope references review evidence. Its decision stays `proposed`;
the producing model cannot encode project acceptance.

The no-network validator checks structure, canonical hashes and local evidence
bytes. HTTPS references are declared, not fetched or verified by that gate.
An authorized merge under repository governance records acceptance separately
from the attestation's epistemic tier.
[ADR-021](docs/adr/ADR-021-gouvernance-github.md) defines this boundary.

## Formal specification and limits

Lean expresses selected invariants. Python conformance tests exercise the
connection to the implementation. This is an empirical bridge, not a verified
derivation of the whole runtime. Model answers, network sources, storage and
the interface do not inherit an end-to-end proof from the Lean files.
See ADR-020 and `TECH_DEBT.md` (TD-005).

## Liability & Scope

EPP records a process and its result. It does not issue legal, regulatory or
institutional decisions. Historical domain examples do not establish
suitability for operational compliance, medical use or security certification.
The operator decides how to use a record and must examine its sources and limits.

The former blockchain-evidence legal argument remains only in the historical
whitepaper, outside the present proposition.

## Historical surfaces

[ADR-022](docs/adr/ADR-022-recentrage-post-blockchain.md) records retirement of
blockchain publication. Solana and Anchor code is frozen, unmaintained history;
no new on-chain publication belongs to current scope. Cluster staking,
tokenomics and the former on-chain benchmark roadmap are historical directions.

The public dashboard reads stored benchmark JSON and former devnet records.
It runs no model, does not query current source services and does not demonstrate
current performance. Historical deltas describe their particular experiment,
not a general accuracy improvement.

## Development direction

Lyra P6 is the triptych's principal application effort. Its everyday use may
eventually supply native feedback for instrument development. P7 remains a
metrological workshop; H11 is `UNTESTED`. Origami v4–v7 is closed and its Fisher
signal is not imported into Lyra or EPP.

EPP's immediate work is scope coherence and maintenance of local attestation
contracts. A future bridge needs explicit inputs, outputs, uncertainty handling
and validation evidence before adoption.

## Reading and evidence

- [Current status and verification snapshot](docs/CURRENT_STATUS.md)
- [Code map](docs/ARCHITECTURE.md)
- [ADR-021: GitHub governance](docs/adr/ADR-021-gouvernance-github.md)
- [ADR-022: post-blockchain scope](docs/adr/ADR-022-recentrage-post-blockchain.md)
- [Historical narrative and source references](docs/history/README.md)

This edition makes no new literature, legal-precedent or competitor claim.
Historical references remain attributed in the archive; they are not a refreshed
literature review.
