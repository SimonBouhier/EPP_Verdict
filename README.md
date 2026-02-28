# EPP_Verdict — Epistemic Proof Protocol

[![License: CC BY-NC-ND 4.0](https://licensebuttons.net/l/by-nc-nd/4.0/88x31.png)](https://creativecommons.org/licenses/by-nc-nd/4.0/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-697%20passed-brightgreen)](tests/)
[![Solana Devnet](https://img.shields.io/badge/Solana-devnet-9945FF)](https://solana.com)

---

## What it does

**EPP is a blockchain oracle that doesn't trust itself.**

Most oracles push data on-chain and ask you to trust the source.  
EPP forces multiple AI models to debate a claim independently, measures their epistemic disagreement, and anchors a cryptographic proof of the resulting consensus on Solana — along with the exact methodology that produced it.

The result is an attestation that says not just *what* was concluded, but *how*, *by whom*, and *under what conditions* — permanently, verifiably, without a single point of trust.

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

## État du projet

> *Détails techniques en français — la langue dans laquelle ce projet a été conçu.*

### Chiffres clés (25 février 2026)

| Indicateur | Valeur |
|:---|:---|
| Tests | **697 passed, 11 skipped, 0 failed** |
| ADRs | **12** — toutes les décisions architecturales documentées |
| Tables SQLite | **25** — dont `source_anchor_snapshots` (ADR-012) |
| Frames métrologiques | **5** — `blockchain_tps`, `general_knowledge`, `compliance_sanctions`, `carbon_credits_vcs`, `rwa_identity` |
| Programme Solana | Anchor 0.32, deploye devnet, 462 bytes/attestation |
| Adaptateurs RWA | OpenSanctions, OFAC SDN, EU CFSP, Verra VCS |

### Architecture

```
EPP_Verdict/
├── services/
│   ├── esmm/               # Protocole ESMM dual-mode (EXPLORE + VERIFY)
│   │   ├── orchestrator.py # ESMMRunConfig, ClaimNature, cycles
│   │   ├── pipeline.py     # run_pipeline() — point d'entrée unifié
│   │   ├── attestation.py  # EpistemicAttestation, Signature5D, crystallize()
│   │   ├── consensus_engine.py  # Brier scores, diversity bonus, semantic merge
│   │   ├── fingerprint_*.py     # ADR-011 : réconciliation sémantique (4 modules)
│   │   └── source_anchor_builder.py  # ADR-012 : chemin déterministe RWA
│   ├── rwa/adapters/       # OpenSanctions, OFAC, EU CFSP, Verra VCS
│   └── solana/             # Config, bridge Python↔Anchor, client, frames
├── programs/epp/           # Programme Anchor (Rust) — lib.rs, state.rs
├── database/
│   ├── engine.py           # ISpaceDB — ~100 méthodes async
│   ├── schema.sql          # 25 tables SQLite
│   └── pool.py             # Pool connexions, cache LRU
├── cli/epp_cli.py          # ask, submit, query, frame, verify-rwa
└── tests/                  # 697 tests — RED-GREEN-FIX strict
```

## Long-term Vision — The Epistemic Flywheel

 Today EPP_Verdict is an oracle that doesn’t trust itself.  
 Tomorrow, it will be the decentralized verifiable truth layer the AI and RWA ecosystem needs.

 Every attestation produced (5D epistemic signature, metrological frame, source anchor) becomes a node in a growing **decentralized weighted consensus graph**.
 Over thousands, then millions of attestations, this graph forms a living map of human knowledge: every triplet, every verification, every debate is weighted by real-world Brier score, semantic diversity, and historical reliability.

 Because the architecture is model-agnostic and obsolescence-proof, any LLM (local via Ollama or via xAI, OpenAI, Anthropic, Grok, Claude, Gemini APIs…) can join the protocol. Each participant brings its own “brand” and is publicly scored on epistemic performance. The best naturally gain more weight in future consensus; the others are incentivized to improve or specialize.

 This creates a true **self-improving virtuous cycle**:

1. Models debate and produce higher-quality attestations.  
2. The graph grows richer with verified, structured, traceable data.  
3. This data enables distillation of ultra-clean synthetic datasets to train the next generation of models.  
4. New, more powerful and more honest models join the protocol… and the cycle continues.

In the long run, EPP_Verdict becomes:
 - **The decentralized reliable source** for anything that must be proven (RWA, regulatory compliance, real-time claim verification on X, anti-deepfake fact-checking, carbon validation, digital identity, etc.).

 - **The permanent public benchmark** for future AI models: a living, transparent, on-chain epistemic leaderboard.

 - **The truth infrastructure** that super-apps (X Money, future Grok agents, etc.) will be able to call natively so they never again have to say “trust me”.

 We didn’t build just another oracle.  
We built the engine that forces collective artificial intelligence to become, by design, more and more worthy of trust.

 And it all starts with 462 bytes on Solana.

### Les 4 axiomes fondateurs

1. **Obsolescence des modèles** — Aucun nom de modèle hardcodé. L'architecture survit au remplacement complet des LLMs.
2. **Survie du graphe** — Les données persistent à travers les changements de provider, de schéma, et de stratégie de consensus.
3. **Transparence des coupures** — Chaque seuil, chaque méthode, chaque version est explicite et versionné dans `consensus_meta`. Une attestation est reproductible ou elle n'est pas valide.
4. **Computation locale, preuve on-chain** — Les modèles tournent en local (Ollama). Seul le hash cryptographique part sur la blockchain.

---

## Prérequis

```
Python 3.11+
Ollama (≥ 1 modèle : mistral, llama3.1, deepseek-r1 recommandés)
SQLite (inclus avec Python)

# Pour l'ancrage on-chain (optionnel, devnet) :
Solana CLI 3.0+  |  Anchor 0.32+  |  Rust 1.70+
# Sur Windows : via WSL
```

## Installation

```bash
git clone https://github.com/SimonBouhier/EPP_Verdict.git
cd EPP_Verdict
python -m venv .venv && source .venv/bin/activate  # ou .venv\Scripts\activate (Windows)
pip install -r requirements.txt
```

## CLI

```bash
# Délibération épistémique multi-modèles
python -m cli.epp_cli ask "Solana effective TPS exceeds 3000" --frame blockchain_tps_v1.0

# Vérification RWA déterministe
python -m cli.epp_cli verify-rwa --source opensanctions --entity "Acme Corp" \
  --frame compliance_sanctions_v1.0

python -m cli.epp_cli verify-rwa --source verra_vcs --entity "VCU-123456" \
  --frame carbon_credits_vcs_v1.0

# Ancrage on-chain (devnet)
python -m cli.epp_cli submit <claim_hash> --devnet

# Consulter les frames métrologiques disponibles
python -m cli.epp_cli frame list

# Stats du graphe de connaissances
python -m cli.epp_cli graph stats
```

## Variables d'environnement

| Variable | Défaut | Description |
|:---|:---|:---|
| `OPENSANCTIONS_ENDPOINT` | `http://localhost:8080` | Serveur yente local |
| `OFAC_API_KEY` | — | Clé API OFAC SDN (jamais en config.yaml) |
| `EPP_OLLAMA_URL` | `http://localhost:11434` | Serveur Ollama |
| `EPP_MODEL` | `gpt-oss:20b` | Modèle Ollama par défaut |
| `EPP_NUM_CTX` | `8192` | Taille contexte (tokens) |
| `EPP_EMBEDDING_MODEL` | `nomic-embed-text` | Modèle d'embeddings |

## Tests

```bash
pytest tests/ -v                              # Suite complète
pytest tests/test_rwa_source_anchor.py -v    # ADR-012 RWA
pytest tests/test_adr011_*.py -v             # Semantic Fingerprinting
pytest tests/test_phase1_*.py -v             # Couche Solana

# Ancre Solana (nécessite WSL + solana-test-validator)
# anchor test
```

---

## Décisions architecturales

Douze ADRs documentent l'évolution du protocole. Les plus structurantes :

| ADR | Décision |
|:---|:---|
| ADR-001 | Encodage float → u16 [0, 10000] pour Solana |
| ADR-005 | Tiers de confiance multi-critères (sandbox → proposition → validated → verified) |
| ADR-006 | Claim hash = SHA-256(subject \| predicate \| object \| frame) — immuable |
| ADR-010 | Traçabilité méthodologique — `consensus_meta` obligatoire à la cristallisation |
| ADR-011-v2 | Réconciliation sémantique par empreinte structurelle (Semantic Fingerprinting) |
| ADR-012 | Bifurcation déterministe / épistémique — intégration sources RWA |

---

## Licence

[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) — [Simon Bouhier](https://github.com/SimonBouhier)
