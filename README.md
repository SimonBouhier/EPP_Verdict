# EPP — Epistemic Proof Protocol

**Verifiable AI Consensus on Solana**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-809%20passed-brightgreen)](tests/)
[![ADRs](https://img.shields.io/badge/ADRs-18-blue)](docs/adr/)
[![Solana Devnet](https://img.shields.io/badge/Solana-devnet-9945FF)](https://solana.com)

> *"The oracle problem is not just technical but epistemological."*
> — Caldarelli, 2025 · Bank for International Settlements, 2023

---

## What is EPP?

EPP is a consensus engine for knowledge claims, anchored on Solana. Multiple AI models deliberate through structured debate cycles to reach consensus on factual assertions, producing cryptographically verifiable attestations stored on-chain.

Existing oracles solve the data feed problem — prices, timestamps, scores. **EPP solves the truth problem** — Is this claim factually supported? Does the evidence agree? Is this entity compliant?

The result is an attestation that says not just *what* was concluded, but *how*, *by whom*, and *under what conditions* — permanently, verifiably, without a single point of trust.

---

## The Epistemic Flywheel (ADR-018)

LLMs are structurally blind to events after their training cutoff. EPP exploits this limitation instead of suffering it.

| Stage | Score | Verdict | Time | Compute |
|:------|:------|:--------|:-----|:--------|
| LLMs alone | 0.43 | CONTESTED | 105s | 3 models |
| + Flywheel (Wikidata injected) | **0.89** | **SUPPORTED** | 110s | 3 models |
| Subsequent queries (cache) | **0.89** | **SUPPORTED** | **<1ms** | **Zero** |

**Claim:** "Donald Trump won the 2024 US presidential election"
**Delta: +0.46.** Same models. Same claim. No retraining. The graph learned by itself.

Three orders of magnitude in cost reduction for a more reliable answer. The graph becomes more intelligent with each cycle without retraining any model.

---

## Three Paths, One Protocol

**EXPLORE** (Divergent → Debate → Meta) — Open-ended knowledge extraction. Models build a semantic knowledge graph through divergent exploration, dialectic debate, and meta-reflection. Each triplet is weighted by structural consensus (Brier scores, diversity bonuses, semantic fingerprinting).

**VERIFY** (ASSESS → CHALLENGE → ADJUDICATE) — Structured factual verification with epistemic isolation. Each model evaluates independently, challenges its neighbor in circular rotation (model[i] sees only model[(i+1)%N]), then collective weighted adjudication. The output is a signed 5-dimensional epistemic signature.

**DETERMINISTIC** (ADR-012) — For facts that don't need debate. Sanctions screening, carbon credit validation, physical constants. EPP queries authoritative sources, hashes the raw response (SHA-256), and produces a traceable attestation without invoking LLMs — because adding uncertainty to a binary fact is not epistemology, it's noise.

---

## Empirical Results

### Flywheel Effect (ADR-018)
| Claim | Without Flywheel | With Flywheel | Delta |
|:------|:-----------------|:--------------|:------|
| Trump won 2024 election | 0.43 CONTESTED | 0.89 SUPPORTED | **+0.46** |

### Geopolitical Assessment (ADR-016)
| Claim | LLM Verdict | Score | Deterministic Source |
|:------|:------------|:------|:---------------------|
| Yemen active conflict 2025 | SUPPORTED | 0.96 | ACLED: ready |
| Switzerland active conflict | CONTESTED | 0.62 | — |
| Iran proxy escalation | CONTESTED | 0.42 | ACLED: ready |

### Smart Contract Audit (ADR-014)
| Function | Vulnerable? | Light (7B) | Heavy (20B+) |
|:---------|:------------|:-----------|:-------------|
| withdrawBalance (SWC-107) | YES | 0.55 CONTESTED | 0.46 CONTESTED |
| addToBalance | No | 0.79 SUPPORTED | 0.74 SUPPORTED |
| getBalance | No | 0.79 SUPPORTED | 0.41 CONTESTED |

**Finding:** reasoning models over-contest uniformly (~0.45). Smaller 7B models discriminate better. The divergence between model families IS the signal.

### Epistemic Edge Cases
| Claim | Type Detected | Score | Signal |
|:------|:-------------|:------|:-------|
| Pineapple on pizza is delicious | Normative | 0.29 | Refuses to adjudicate |
| Moon is made of cheese | — | 0 attestations | Graceful refusal |
| Bitcoin replaces fiat in 10 years | Speculative | 0.40 | Penalty 0.75 applied |
| Earth orbits Sun in 365.25 days | Empirical | 0.99 | Baseline anchor |
| Napoleon was shorter than average | Empirical | 0.96 SUPPORTED ✗ | Shared training bias exposed |

---

## Five Founding Axioms

1. **Model Obsolescence** — Models are consumables, not infrastructure. Any LLM can enter or leave the system.
2. **Graph Survival** — Knowledge graph data survives all system changes. Data is sovereign.
3. **Transparent Regression Cuts** — Every methodology change is versioned. Attestations produced under different conditions are explicitly non-comparable.
4. **Local Computation, On-Chain Proof** — AI runs locally (privacy, cost control). Only the cryptographic proof goes on-chain.
5. **Divergence is the Signal** — Disagreement between model families is more epistemically valuable than a unanimous verdict. Uniformity is a failure mode, not a feature.

---

## On-Chain

Solana program deployed on devnet: `98Fc2oL2cKsTDGYi3GifggzkQkEQSRn2oTgg8HsaVa3C`

Each attestation occupies **462 bytes** as a PDA. It carries: claim hash, epistemic signature (5 dimensions × u16), confidence tier, metrological frame hash, source anchor, protocol version.

Four confidence tiers (ADR-005):

| Tier | Threshold | Conditions |
|:-----|:----------|:-----------|
| Sandbox | < 0.40 | No additional requirements |
| Proposition | ≥ 0.40 | + ≥ 2 models consulted |
| Validated | ≥ 0.70 | + ≥ 3 models + ≥ 2 architecture families |
| Verified | ≥ 0.85 | + source anchor OR validation count ≥ 3 |

---

## Architecture

```
EPP_Verdict/
├── services/
│   ├── esmm/                    # ESMM dual-mode protocol
│   │   ├── orchestrator.py      # ESMMRunConfig, ClaimNature, cycle dispatch
│   │   ├── pipeline.py          # run_pipeline() — unified entry point + Flywheel (ADR-018)
│   │   ├── attestation.py       # EpistemicAttestation, Signature5D, crystallize()
│   │   ├── consensus_engine.py  # Brier scores, diversity bonus, semantic merge
│   │   ├── fingerprint_*.py     # ADR-011: semantic reconciliation (4 modules)
│   │   ├── cycle_prompts.py     # Dual-mode prompt templates (EXPLORE + VERIFY)
│   │   ├── cycle_manager.py     # Cycle execution, model queries, retry logic
│   │   └── source_anchor_builder.py  # ADR-012: deterministic path
│   ├── sources/adapters/        # OFAC, OpenSanctions, EU CFSP, Verra VCS, ACLED, Wikidata
│   ├── providers/               # Ollama, OpenAI-compat, Anthropic (base.py interface)
│   └── solana/                  # Bridge, client, metrological frames
├── services/audit/              # ADR-014: smart contract audit (slicer, runner, SWC taxonomy)
├── programs/epp/                # Anchor/Rust — lib.rs, state.rs, errors.rs, constants.rs
├── database/
│   ├── engine.py                # ISpaceDB — async, ~100 methods
│   ├── schema.sql               # 25+ tables
│   └── pool.py                  # Connection pool, LRU cache
├── cli/epp_cli.py               # ask, submit, query, frame, verify-rwa, audit
├── demos/                       # Scenario scripts + benchmark_runs/ (timestamped JSON)
├── docs/
│   ├── adr/                     # ADR-001 through ADR-018
│   ├── ARCHITECTURE.md          # Living document, updated with each structural change
│   └── CHANGELOG.md             # Authoritative chronological journal
└── tests/                       # 809 tests — RED-GREEN-FIX strict protocol
```

---

## Deterministic Sources

Seven authoritative data sources integrated:

| Source | Domain | Status |
|:-------|:-------|:-------|
| OFAC SDN | US Treasury sanctions | Integrated |
| OpenSanctions | Open-source sanctions/PEP | Integrated |
| EU CFSP | European Union sanctions | Integrated |
| Verra VCS | Carbon credit registry | Integrated |
| ACLED | Armed conflict events | Integrated (pending data API access) |
| Wikidata | Structured knowledge base | Integrated (Flywheel demonstrated) |
| NIST | Physical constants | In development |

Each adapter implements `fetch()`, `normalize()`, `get_source_version()`. A new source can be integrated in a single day.

---

## Current Status (March 2026)

| Metric | Value |
|:-------|:------|
| Test suite | **809 passed**, 14 skipped, 0 failed |
| Architecture decisions | **18 ADRs** |
| AI models tested | 6: Mistral, Llama 3.1, Gemma 3, DeepSeek-R1, phi4-reasoning, gpt-oss:20b |
| Pipeline modes | EXPLORE + VERIFY + DETERMINISTIC + **FLYWHEEL** |
| Deterministic sources | 7 integrated |
| Operational domains | 3: epistemic exploration, smart contract audit, geopolitical assessment |
| Benchmark datasets | 7, with 37+ claims evaluated |
| Flywheel effect | **+0.46 demonstrated** (0.43 → 0.89) |
| Solana program | Anchor/Rust, deployed on devnet, PDA-based |
| Security | Commit-reveal, response deduplication, devnet-only guards |

---

## Quick Start

### Prerequisites

```
Python 3.11+
Ollama (≥ 2 models: mistral + llama3.1 recommended)
SQLite (included with Python)

# For on-chain anchoring (optional, devnet):
Solana CLI 3.0+  |  Anchor 0.32+  |  Rust 1.70+
```

### Installation

```bash
git clone https://github.com/SimonBouhier/EPP_Verdict.git
cd EPP_Verdict
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate (Windows)
pip install -r requirements.txt
```

### Run a Scenario

```bash
# Flywheel demonstration (Trump + Wikidata + controls)
python demos/scenario_flywheel.py

# Geopolitical assessment (Jiang predictions + controls)
python demos/scenario_jiang.py

# Epistemic edge cases (14 claims: opinions, absurdities, bias)
python demos/scenario_6_1_edge_cases.py
```

### CLI

```bash
# Epistemic deliberation
python -m cli.epp_cli ask "Solana effective TPS exceeds 3000" --frame blockchain_tps_v1.0

# Deterministic verification
python -m cli.epp_cli verify-rwa --source opensanctions --entity "Acme Corp" \
  --frame compliance_sanctions_v1.0

# Smart contract audit
python -m cli.epp_cli audit contracts/vulnerable.sol --frame smart_contract_audit_v1.0

# On-chain submission (devnet)
python -m cli.epp_cli submit <claim_hash> --devnet

# Available metrological frames
python -m cli.epp_cli frame list
```

### Tests

```bash
pytest tests/ -v                              # Full suite (809 tests)
pytest tests/test_adr018_flywheel.py -v       # Flywheel tests
pytest tests/test_adr014_audit_runner.py -v   # Smart contract audit
pytest tests/test_adr012_source_anchor.py -v  # Deterministic sources
```

---

## Environment Variables

| Variable | Default | Description |
|:---------|:--------|:------------|
| `EPP_OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `EPP_MODEL` | `mistral:latest` | Default Ollama model |
| `EPP_NUM_CTX` | `8192` | Context window (tokens) |
| `EPP_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `OPENSANCTIONS_ENDPOINT` | `http://localhost:8080` | yente server |
| `OFAC_API_KEY` | — | OFAC SDN API key (never in config.yaml) |
| `ACLED_EMAIL` | — | ACLED API credentials |

---

## Architecture Decision Records

18 ADRs document every critical design choice:

| ADR | Decision |
|:----|:---------|
| ADR-001 | Float → u16 [0, 10000] encoding for Solana |
| ADR-005 | Multi-criteria confidence tiers (sandbox → verified) |
| ADR-006 | Claim hash = SHA-256(subject \| predicate \| object \| frame) — immutable |
| ADR-010 | Methodology traceability — consensus_meta mandatory at crystallization |
| ADR-011 | Semantic reconciliation via structural fingerprinting |
| ADR-012 | Deterministic/epistemic bifurcation — authoritative source integration |
| ADR-013 | Persistent graph + epistemic cache-hit |
| ADR-014 | Smart contract security audit pipeline |
| ADR-016 | Geopolitical oracle — ACLED + Wikidata dual-path |
| ADR-017 | Epistemic Cluster network architecture (proposed) |
| ADR-018 | **Epistemic Flywheel — self-improving knowledge graph** |

---

## The Cluster Vision (ADR-017)

EPP was designed as a network protocol of which only one node exists today. The unit of decentralization is the **Epistemic Cluster** — an autonomous instance with its own models, sources, and metrological frames. Trust emerges from cumulative Brier track records, calculable by anyone directly from the blockchain.

Each cluster publishes its configuration. Verification happens through results, not promises. When two clusters attest the same claim differently, the divergence captures methodology differences — it is measurement, not redundancy.

---

## From Intuition to Infrastructure

Before a single line of Python was written, EPP existed as handwritten mappings between attention mechanisms and what its creator called "vibratory weights." Concepts like divergence as signal, multi-agent deliberation, and bidirectional knowledge transfer were sketched in metaphor before becoming Architecture Decision Records and pytest assertions.

The path from there to here — 809 tests, 18 ADRs, 6 AI models deliberating on Solana devnet, a measurable +0.46 flywheel delta — was walked by one person with no technical background, a consumer GPU, and a belief that making AI models disagree on purpose would produce something more honest than making them agree.

This is what one person built in sixteen months. The question is what becomes possible when a team carries it forward.

---

## References

1. Egberts, A. (2017). The Oracle Problem. SSRN.
2. Chainalysis (2023). Oracle manipulation attacks rising.
3. Duley et al. (2023). The oracle problem and the future of DeFi. BIS Bulletin No. 76.
4. Caldarelli, G. (2025). Can AI solve the blockchain oracle problem? arXiv:2507.02125.
5. Xian et al. (2024). Connecting LLMs with Blockchain. arXiv:2412.02263.
6. Zintus-Art et al. (2025). Empirical Evidence in AI Oracle Development. Chainlink Research.
7. Wu et al. (2025). Vulnerabilities in Solana Smart Contracts. arXiv:2504.07419.
8. Zhang & Zhao (2026). Formalized scientific methodology for AI research. bioRxiv:2026.03.02.709102.

---

## Built With

Python · Rust/Anchor · Solana · Ollama · SQLite · Claude Code + Claude Opus (adversarial audit)

**Hardware:** Intel i5-14600K · NVIDIA RTX 4090 24GB · 64GB DDR5 — everything runs on one machine.

---

## Author

**Simon Bouhier** — Solo builder · Paris

[Website](https://epp-verdict.carrd.co) · [X](https://x.com/SimonOrdos) · [Email](mailto:simon.bouhier@proton.me)

---

## License

[MIT](LICENSE)
