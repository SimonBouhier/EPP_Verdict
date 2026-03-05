# EPP_Verdict — Epistemic Proof Protocol

[![License: CC BY-NC-ND 4.0](https://licensebuttons.net/l/by-nc-nd/4.0/88x31.png)](https://creativecommons.org/licenses/by-nc-nd/4.0/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-701%20passed-brightgreen)](tests/)
[![Solana Devnet](https://img.shields.io/badge/Solana-devnet-9945FF)](https://solana.com)

---

**EPP is a blockchain oracle that doesn't trust itself.**

Most oracles push data on-chain and ask you to trust the source.
EPP forces multiple AI models to debate a claim independently, measures their epistemic disagreement, and anchors a cryptographic proof of the resulting consensus on Solana — along with the exact methodology that produced it.

The result is an attestation that says not just *what* was concluded, but *how*, *by whom*, and *under what conditions* — permanently, on-chain, without a single point of trust.

What accumulates from these deliberations is something new: not a database of facts, but a map of epistemic uncertainty over time. Each claim leaves a trace — not just a verdict, but a distribution of disagreement across architecturally distinct models. Run the same claim six months later with a new model generation, and the delta tells you something real: did the uncertainty collapse? Did it shift? Did a contested domain suddenly converge?

These uncertainty deltas are where the signal lives — in research, in model evaluation, at the frontier of what can be verified.

The protocol does not resolve these questions. It makes them measurable, traceable, and comparable across time.

---

## Two modes, one protocol

**EXPLORE** — Open-ended knowledge extraction. Models build a semantic knowledge graph through divergent, debate, and meta-reflection cycles. Each extracted triplet is weighted by structural consensus (Brier scores, diversity bonuses, semantic fingerprinting).

**VERIFY** — Factual claim verification. A claim enters a structured adversarial pipeline: independent assessment (ASSESS), cross-examination (CHALLENGE), and final weighted adjudication (ADJUDICATE). The output is a signed 5-dimensional epistemic signature anchored on-chain.

**DETERMINISTIC** (ADR-012) — For facts that don't need debate. Sanctions screening, carbon credit validation, regulatory compliance. EPP queries authoritative external sources (OFAC, OpenSanctions, Verra VCS, EU CFSP), hashes the raw API response, and produces a traceable attestation without invoking LLMs — because adding uncertainty to a binary fact is not epistemology, it's noise.

---

## On-chain

Programme deployed on Solana devnet:
`98Fc2oL2cKsTDGYi3GifggzkQkEQSRn2oTgg8HsaVa3C`

Each attestation occupies **462 bytes** as a PDA. It carries: claim hash, epistemic signature (5 dimensions × u16), confidence tier, metrological frame hash, source anchor, protocol version. Everything that matters fits in a single account. The full deliberation lives off-chain in SQLite, linked by SHA-256.

---

## What is actually running

On 2 March 2026, this happened on a local machine:

```
Question: Water boils at 100 degrees Celsius
Models: mistral:latest, llama3.1:8b, gemma3:latest

→ Attestation [PROPOSITION]
  Claim: Water boils at 100 degrees Celsius → verdict → SUPPORTED
  Consensus: 98.67% | Models: 3/3 | Duration: 100s

→ Same question, second run:
  Duration: 0ms  ← retrieved from persistent epistemic graph
```

Three architecturally distinct AI models debated independently.
Their agreement was measured, weighted, and crystallized into a signed attestation.
That attestation now lives in a persistent graph — retrieved instantly on any future query,
without consulting the models again.

The graph currently holds **56 attestations** across 32 unique claims, spanning blockchain
architecture, cryptography, DeFi, and contested domains. The most contested claim in the
graph: *"Central bank digital currencies represent a threat to decentralization"* — consensus
17–25% across five independent runs. The models refuse to decide. That refusal is the data.

---

## Key figures (2 March 2026)

| Indicator | Value |
|:---|:---|
| Tests | **701 passed, 11 skipped, 0 failed** |
| ADRs | **13** — all architectural decisions documented |
| SQLite tables | **25** — including `source_anchor_snapshots` (ADR-012) |
| Metrological frames | **5** — `blockchain_tps`, `general_knowledge`, `compliance_sanctions`, `carbon_credits_vcs`, `rwa_identity` |
| Solana programme | Anchor 0.32.1, deployed devnet, 462 bytes/attestation |
| RWA adapters | OpenSanctions, OFAC SDN, EU CFSP, Verra VCS |
| Graph | 56 attestations, 101 ESMM runs, 580 knowledge gaps detected |

---

## Architecture

```
EPP_Verdict/
├── services/
│   ├── esmm/               # ESMM dual-mode protocol (EXPLORE + VERIFY)
│   │   ├── orchestrator.py # ESMMRunConfig, ClaimNature, cycles
│   │   ├── pipeline.py     # run_pipeline() — unified entry point
│   │   ├── attestation.py  # EpistemicAttestation, Signature5D, crystallize()
│   │   ├── consensus_engine.py  # Brier scores, diversity bonus, semantic merge
│   │   ├── fingerprint_*.py     # ADR-011: semantic reconciliation (4 modules)
│   │   └── source_anchor_builder.py  # ADR-012: deterministic RWA path
│   ├── rwa/adapters/       # OpenSanctions, OFAC, EU CFSP, Verra VCS
│   └── solana/             # Config, Python↔Anchor bridge, client, frames
├── programs/epp/           # Anchor programme (Rust) — lib.rs, state.rs
├── database/
│   ├── engine.py           # ISpaceDB — ~100 async methods
│   ├── schema.sql          # 25 SQLite tables
│   └── pool.py             # Connection pool, LRU cache
├── cli/epp_cli.py          # ask, submit, query, frame, verify-rwa
└── tests/                  # 701 tests — strict RED-GREEN-FIX
```

---

## The four founding axioms

1. **Model obsolescence** — No model name hardcoded. The architecture survives complete LLM replacement.
2. **Graph survival** — Data persists across provider, schema, and consensus strategy changes.
3. **Methodology transparency** — Every threshold, method, and version is explicit and versioned in `consensus_meta`. An attestation is reproducible or it is not valid.
4. **Local computation, on-chain proof** — Models run locally via Ollama. Only the cryptographic hash goes on-chain.

---

## Security

Threat model and red team findings documented in `docs/security/`.
Known attack surfaces: Sybil attacks on model panels, cache poisoning, black-box verifiability.
Mitigation roadmap: commit-reveal protocol → TEE/ZK verification.

---

## Prerequisites

```
Python 3.11+
Ollama (≥ 1 model: mistral, llama3.1, gemma3 recommended)
SQLite (bundled with Python)

# For on-chain anchoring (optional, devnet):
Solana CLI 3.0+  |  Anchor 0.32.1+  |  Rust 1.93+
# On Windows: via WSL
```

## Installation

```bash
git clone https://github.com/SimonBouhier/EPP_Verdict.git
cd EPP_Verdict
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate (Windows)
pip install -r requirements.txt
```

## CLI

```bash
# Multi-model epistemic deliberation
python -m cli.epp_cli ask "Solana effective TPS exceeds 3000" --frame blockchain_tps_v1.0

# Deterministic RWA verification
python -m cli.epp_cli verify-rwa --source opensanctions --entity "Acme Corp" \
  --frame compliance_sanctions_v1.0

python -m cli.epp_cli verify-rwa --source verra_vcs --entity "VCU-123456" \
  --frame carbon_credits_vcs_v1.0

# On-chain anchoring (devnet)
python -m cli.epp_cli submit <claim_hash> --devnet

# List available metrological frames
python -m cli.epp_cli frame list

# Knowledge graph stats
python -m cli.epp_cli graph stats
```

## Environment variables

| Variable | Default | Description |
|:---|:---|:---|
| `OPENSANCTIONS_ENDPOINT` | `http://localhost:8080` | Local yente server |
| `OFAC_API_KEY` | — | OFAC SDN API key (never in config.yaml) |
| `EPP_OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `EPP_NUM_CTX` | `8192` | Context size (tokens) |
| `EPP_EMBEDDING_MODEL` | `nomic-embed-text` | Embeddings model |

## Tests

```bash
pytest tests/ -v                              # Full suite
pytest tests/test_rwa_source_anchor.py -v    # ADR-012 RWA
pytest tests/test_adr011_*.py -v             # Semantic Fingerprinting
pytest tests/test_phase1_*.py -v             # Solana layer

# Anchor tests (requires WSL + solana-test-validator)
# anchor test
```

---

## Architectural decisions

Thirteen ADRs document the evolution of the protocol:

| ADR | Decision |
|:---|:---|
| ADR-001 | Float → u16 [0, 10000] encoding for Solana |
| ADR-005 | Multi-criteria confidence tiers (sandbox → proposition → validated → verified) |
| ADR-006 | Claim hash = SHA-256(subject \| predicate \| object \| frame) — immutable |
| ADR-010 | Methodology traceability — `consensus_meta` mandatory at crystallization |
| ADR-011-v2 | Semantic reconciliation via structural fingerprinting |
| ADR-012 | Deterministic / epistemic bifurcation — RWA source integration |
| ADR-013 | Persistent graph & epistemic cache-hit — reuse of past deliberations |

---

## License

[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) — [Simon Bouhier](https://github.com/SimonBouhier)
