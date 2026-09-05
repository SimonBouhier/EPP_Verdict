# EPP — Epistemic Proof Program

**Local deliberation, portable attestations, traceable provenance.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](requirements.txt)

EPP is a personal epistemic attestation engine. It organizes model deliberation
and source-backed observations, records disagreement and methodology, and
produces reviewable artifacts. Its intended consumer is Lyra, through a future
validated interface. Each project works independently.

**Current scope, reviewed 5 September 2026:** [status and evidence](docs/CURRENT_STATUS.md).
Blockchain publication is **retired** under
[ADR-022](docs/adr/ADR-022-recentrage-post-blockchain.md).
The existing dashboard is a **historical benchmark archive**.

## What an attestation means

An attestation records a claim, the assessment process, participants, agreement
and provenance. Hashes establish integrity, not truth. GitHub review and an
authorized merge record project acceptance, separately from epistemic confidence.

## Read the project

- [Current status](docs/CURRENT_STATUS.md) — implemented surfaces, limitations,
  branch-specific work and dated checks.
- [Project overview](PITCH.md) — purpose and scope in a few minutes.
- [Whitepaper](WHITEPAPER.md) — present design and epistemic limits.
- [Architecture](docs/ARCHITECTURE.md) — code locations and boundaries.
- [Documentation portal](https://epp-verdict-docs.vercel.app) — published documentation;
  its deployed revision may lag the working tree.
- [Historical dashboard](https://epp-verdict.vercel.app) — saved benchmark runs
  and former devnet records, not a live evaluation service.
- [Historical texts](docs/history/README.md) — the earlier narrative, preserved verbatim.

## Local setup

Python 3.11 or later is required. Live deliberation also requires Ollama and
selected installed models. Source-backed runs may require source-specific
access. Node is needed only for the static sites. Solana, Anchor and Rust
are not prerequisites for the current local workflow.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m cli.epp_cli --help
.\.venv\Scripts\python.exe -m cli.epp_cli frame list
```

Model-dependent examples are deliberate runs, not installation checks:

```powershell
.\.venv\Scripts\python.exe -m cli.epp_cli ask "Assess this claim under a declared frame" --frame general_knowledge_v1.0
.\.venv\Scripts\python.exe -m cli.epp_cli query "subject" --min-confidence 0.8
```

Legacy publication commands remain for historical compatibility, outside the
maintained workflow. Secrets belong in environment variables, never in code.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m scripts.validate_proposals
```

The [dated snapshot](docs/CURRENT_STATUS.md#verification-snapshot) distinguishes
targeted checks from earlier full-suite runs. A successful validator on an empty
proposal directory does not prove real-world usage or a promoted attestation.

## Documentation and historical dashboard

From `docs-site/`, run `npm run sync`, `npm run check:sync`, then `npm run build`.
Current prose is maintained in root documents and `docs/`; generated portal
content is checked against these sources. See [publishing](docs/PUBLISHING.md).

From `ui/`, run `npm run dev` or `npm run build`. These commands read the
committed historical dataset without refreshing it from new local runs.
The archive executes no model and publishes no attestation.

Code: **MIT**, © 2026 Simon Bouhier. Historical third-party references retain
their original attribution.
