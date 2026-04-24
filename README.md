# EPP — Epistemic Proof Program

**Verifiable AI Consensus on Solana.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-852%20passed-brightgreen)](tests/)
[![ADRs](https://img.shields.io/badge/ADRs-20-blue)](docs/adr/)
[![Solana Devnet](https://img.shields.io/badge/Solana-devnet-9945FF)](https://epp-verdict.vercel.app/onchain)
[![Dashboard](https://img.shields.io/badge/dashboard-live-06b6d4)](https://epp-verdict.vercel.app)

> *"The oracle problem is not just technical but epistemological."*
> — Caldarelli, 2025 · Bank for International Settlements, 2023

---

## ⚠️ Proofs of process, not verdicts on truth

EPP produces cryptographic measurements of multi-LLM deliberation under specified metrological frames. These attestations record *what was deliberated, by whom, and how*. They are **not** legal verdicts, regulatory decisions, or substitutes for human or institutional adjudication.

Per the *UNESCO Recommendation on the Ethics of Artificial Intelligence* (193 Member States, 2021), ultimate ethical and legal responsibility for any decision based on an AI output remains with the natural or legal persons consuming it. EPP supports human oversight; it does not replace it.

The full liability framing — and the alignment with UNESCO §3/§5/§11 plus the emerging legal recognition of blockchain evidence (Tribunal judiciaire de Marseille 2025, CJUE *DigitalArt GmbH* 2024, Luxembourg Code civil 2024) — is in [`WHITEPAPER.md` → Liability & Scope](WHITEPAPER.md#liability--scope).

---

## Live Dashboard

**[https://epp-verdict.vercel.app](https://epp-verdict.vercel.app)** — verifiable dashboard reading the project's benchmark JSONs and **12 attestations published to Solana devnet** under program `9QtybfyZQFhra1D6S3NtD6jD4z2Z3wcYmf4YXETq8bSD`. Click any ⛓ badge or the `/onchain` page to open the corresponding transaction on Solana Explorer.

> **Hackathon deployment workaround — not a recommended pattern.** `ui/public/data/` (24 benchmark JSONs + on-chain manifest, ~700 KB) is committed to git as a build input, because Vercel's "Root Directory = `ui/`" mode does not give the build context access to sibling folders such as `../demos/`. This introduces duplication between the source of truth (`demos/benchmark_runs/`, written by the Python pipeline) and the deployed copy. Post-Colosseum refactor options documented at the original commit `0c2e9d6`.

---

## What is EPP?

EPP is a consensus protocol for knowledge claims, anchored on Solana. Multiple architecturally distinct AI models deliberate through structured adversarial cycles, and the protocol produces a cryptographic attestation recording *what* was concluded, *how*, *by whom*, *under what methodology*, and *with what degree of agreement*.

Every attestation carries a **5-dimensional epistemic signature** (agreement, consistency, centrality, stability, diversity) produced under a versioned **metrological frame** and stored as a **462-byte PDA** on Solana devnet. Same kernel, same on-chain format, regardless of domain — what changes per domain is an adapter (fetches external data) and a frame (defines the measurement methodology).

Three operational paths:

| Path | When | Example |
|:-----|:-----|:--------|
| **VERIFY** | Multi-model deliberation needed | *"Solana effective TPS exceeds 3000"* |
| **DETERMINISTIC** | Authoritative source exists | *"Entity X is on the OFAC sanctions list"* |
| **FLYWHEEL** | Both — verified data injected into AI reasoning | *"Trump won the 2024 election"* (0.43 CONTESTED → 0.89 SUPPORTED, +0.46 delta) |

**For the full architectural and epistemological narrative** → [`WHITEPAPER.md`](WHITEPAPER.md).
**For the 3-minute pitch** → [`PITCH.md`](PITCH.md).

---

## Quick Start

### Prerequisites

```
Python 3.11+
Ollama (≥ 2 models: mistral + llama3.1 recommended)
SQLite (included with Python)
Node 20+ (for the ui/ dashboard)

# For on-chain anchoring (optional, devnet only):
Solana CLI 3.0+  |  Anchor 0.32+  |  Rust 1.70+  (WSL on Windows)
```

### Install

```bash
git clone https://github.com/SimonBouhier/EPP_Verdict.git
cd EPP_Verdict
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate (Windows)
pip install -r requirements.txt
```

### Run a scenario

```bash
# Flywheel demonstration (Trump + Wikidata + controls)
python demos/scenario_flywheel.py

# Geopolitical assessment (Jiang predictions + controls)
python demos/scenario_jiang.py

# Epistemic edge cases (14 claims: opinions, absurdities, biased framings)
python demos/scenario_6_1_edge_cases.py
```

### CLI

```bash
# Epistemic deliberation (VERIFY mode)
python -m cli.epp_cli ask "Solana effective TPS exceeds 3000" --frame blockchain_tps_v1.0

# Deterministic verification (DETERMINISTIC mode)
python -m cli.epp_cli verify-rwa --source opensanctions --entity "Acme Corp" \
  --frame compliance_sanctions_v1.0

# Smart contract audit
python -m cli.epp_cli audit contracts/vulnerable.sol --frame smartcontract_audit_v1.0

# Query existing attestations
python -m cli.epp_cli query "solana" --min-confidence 0.8

# On-chain push to devnet (curated batch, 8 general_knowledge + 4 smartcontract_audit)
# Note: cli.epp_cli:submit only marks DB status; this script is what actually pushes.
python scripts/push_to_devnet.py [--dry-run | --general-count N | --audit-count N]

# Model performance dashboard
python -m cli.epp_cli models stats
```

### Dashboard (local dev)

```bash
# Windows: double-click start-ui.bat from the repo root, OR:
cd ui && npm install && npm run dev
# → http://localhost:5173
```

### Tests

```bash
pytest tests/ -v                              # Full suite (852 tests)
pytest tests/test_adr018_flywheel.py -v       # Flywheel
pytest tests/test_adr014_audit_runner.py -v   # Smart contract audit
pytest tests/test_adr020_*.py -v              # Lean 4 conformance
```

---

## Architecture at a glance

```
EPP_Verdict/
├── services/
│   ├── esmm/             # ESMM dual-mode protocol (orchestrator, pipeline, consensus, attestation)
│   ├── sources/adapters/ # OFAC, OpenSanctions, EU CFSP, Verra VCS, ACLED, Wikidata, NIST
│   ├── providers/        # Ollama, OpenAI-compat, Anthropic
│   ├── solana/           # Bridge, client, metrological frames
│   └── audit/            # Smart contract audit kernel (ADR-014)
├── programs/epp/         # Anchor/Rust on-chain program (submit_attestation, state, errors)
├── database/             # ISpaceDB (async SQLite, WAL, ~100 methods)
├── Formal/               # Lean 4 formal verification (11 theorems, 6 red tests, ADR-020)
├── cli/epp_cli.py        # CLI surface (ask, query, frame, audit, verify-rwa)
├── scripts/
│   └── push_to_devnet.py # Curated batch push to Solana devnet
├── ui/                   # Vite + React 19 + Tailwind v4 dashboard — epp-verdict.vercel.app
│   ├── src/{domain,data,services,features,ui,routes}/
│   ├── public/data/      # Committed benchmark JSONs + on-chain manifest (see Vercel note above)
│   └── scripts/copy-data.mjs
├── demos/                # Scenario scripts + benchmark_runs/ (timestamped JSON)
├── docs/
│   ├── adr/              # 20 ADRs
│   ├── ARCHITECTURE.md   # Living structural document
│   ├── positioning/      # Internal strategic material (NOT public vitrine)
│   └── fr/CHANGELOG.md   # Chronological journal
└── tests/                # 852 tests — RED-GREEN-FIX strict protocol
```

**Full component-by-component map** → [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Current Status

| Metric | Value |
|:-------|:------|
| Tests | **852 passed**, 10 skipped, 0 failed |
| Architecture decisions | **20 ADRs** |
| AI models tested | 6 (Mistral, Llama 3.1, Gemma 3, DeepSeek-R1, phi4-reasoning, gpt-oss:20b) |
| Deterministic sources | 7 integrated |
| Pipeline modes | EXPLORE + VERIFY + DETERMINISTIC + FLYWHEEL |
| Solana program | `9QtybfyZQFhra1D6S3NtD6jD4z2Z3wcYmf4YXETq8bSD` (devnet, slot 450099166) |
| On-chain attestations | **12** pushed ([data/devnet_pushed.json](data/devnet_pushed.json)) |
| Flywheel delta demonstrated | **+0.46** (0.43 → 0.89) |
| Formal verification | Lean 4 — **11 theorems proven**, 6 red tests (ADR-020) |

---

## Environment Variables

| Variable | Default | Description |
|:---------|:--------|:------------|
| `EPP_OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `EPP_MODEL` | `mistral:latest` | Default Ollama model |
| `EPP_NUM_CTX` | `8192` | Context window (tokens) |
| `EPP_EMBEDDING_MODEL` | `mxbai-embed-large` | Embedding model |
| `EPP_ALLOWED_ORIGINS` | `http://localhost:{3000,8000}` (+ 127.0.0.1) | CORS allow-list — wildcard `*` rejected (S7-001) |
| `OPENSANCTIONS_ENDPOINT` | `http://localhost:8080` | yente server |
| `OFAC_API_KEY` | — | OFAC SDN (never in `config.yaml`) |
| `ACLED_EMAIL` / `ACLED_PASSWORD` | — | ACLED API credentials |

---

## Learn More

- **[`WHITEPAPER.md`](WHITEPAPER.md)** — Full architectural and epistemological narrative: ESMM deliberation, metrological frames, flywheel, formal verification, cluster vision, references.
- **[`PITCH.md`](PITCH.md)** — 3-minute pitch: three acts, three primitives nobody implements, the five axioms, the verdict that survives the counterpoint stress-test.
- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** — Living component-by-component map.
- **[`docs/adr/`](docs/adr/)** — 20 Architecture Decision Records.
- **[`docs/positioning/`](docs/positioning/)** — Internal strategic material (competitive scan, counterpoint responses, formal methods landscape, track strategy, *the negative space* essay). Not public vitrine — source material informing the public docs.
- **[`docs/fr/CHANGELOG.md`](docs/fr/CHANGELOG.md)** — Chronological journal of significant changes.

---

## License & Contributing

MIT. The codebase contains `COMMUNITY_DECISION_REQUIRED` markers at open governance points — treatment of CONTESTED consensus, scope of language neutrality (ADR-009), cluster slashing conditions. These decisions are deliberately left to the open-source community rather than the founding team.

**Built by one person in sixteen months on a consumer GPU. Ready for a team.**
