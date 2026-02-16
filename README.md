# EPP_Verdict

[![License: CC BY-NC-ND 4.0](https://licensebuttons.net/l/by-nc-nd/4.0/88x31.png)](https://creativecommons.org/licenses/by-nc-nd/4.0/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**Oracle epistemique decentralise** : des LLMs debattent en local, un consensus signe est ancre on-chain sur Solana.

Herite de Lyra ACE. Combine **trajectoires de Bezier** pour controler les parametres LLM, **3 niveaux de conscience** et le protocole **ESMM** (Exploration Semantique Multi-Modeles) pour construire un graphe de connaissances par consensus.

## Table des matieres

- [Concepts cles](#concepts-cles)
- [Prerequis](#prerequis)
- [Installation](#installation)
- [Demarrage](#demarrage)
- [API](#api)
- [ESMM](#esmm)
- [Structure](#structure)
- [Tests](#tests)
- [Documentation](#documentation)
- [Licence](#licence)

## Concepts cles

- **Physique Bezier** : Parametres LLM (temperature, penalties) controles par courbes cubiques
- **3 niveaux de conscience** : Passif -> Adaptatif -> Memoire semantique
- **ESMM** : Orchestration multi-modeles pour extraction de triplets et construction de 0-cochaine epistemique
- **Attestation on-chain** : Consensus signe ancre sur Solana via programme Anchor (Phase 1 MVP)

## Prerequis

- Python 3.11+
- [Ollama](https://ollama.ai/) installe et fonctionnel
- Au moins un modele Ollama telecharge (ex: `gpt-oss:20b`, `mistral`, `llama3.1:8b`)
- SQLite (inclus avec Python)
- **Solana (optionnel, pour ancrage on-chain)** :
  - [Solana CLI](https://docs.solana.com/cli/install-solana-cli-tools) 3.0+
  - [Anchor](https://www.anchor-lang.com/) 0.32+
  - [Rust](https://rustup.rs/) 1.70+
  - Sur Windows : ces outils doivent etre installes dans WSL

## Installation

```bash
# Cloner
git clone https://github.com/SimonBouhier/EPP_Verdict.git
cd EPP_Verdict

# Environnement virtuel
python -m venv .venv

# Activation (Windows)
.venv\Scripts\activate
# Activation (Linux/macOS)
source .venv/bin/activate

pip install -r requirements.txt

# Telecharger un modele Ollama
ollama pull gpt-oss:20b
```

## Demarrage

```bash
# Windows - Demarrer un modele Ollama
start_gptoss.bat        # GPT-OSS 20B (recommande)
start_mistral.bat       # Mistral 7B
start_llama3.bat        # Llama 3.1 8B
start_deepseek.bat      # DeepSeek R1
start_gemma3.bat        # Gemma 3
start_granite.bat       # Granite

# Demarrer le serveur FastAPI
start_server.bat
# ou manuellement :
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interface web : <http://localhost:8000>
API docs (Swagger) : <http://localhost:8000/docs>

## Variables d'environnement

| Variable | Defaut | Description |
|----------|--------|-------------|
| `LYRA_MODEL` | gpt-oss:20b | Modele Ollama |
| `LYRA_OLLAMA_URL` | http://localhost:11434 | URL serveur Ollama |
| `LYRA_NUM_CTX` | 8192 | Taille contexte (tokens) |

## API

```bash
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Explique-moi les courbes de Bezier",
    "consciousness_level": 2,
    "enable_context": true
  }'
```

Endpoints principaux :

- `POST /chat/message` — Conversation avec LLM
- `POST /chat/batch` — Batch multi-modeles
- `POST /graph/delta` — Mutation atomique du graphe
- `POST /graph/esmm-run` — Lancer un run ESMM
- `GET /graph/coverage/metrics` — Metriques de couverture

## ESMM

### Scripts Windows

```bash
# Run interactif
run_esmm.bat

# Run rapide (1 cycle par type)
run_esmm_quick.bat

# Run complet
run_esmm_full.bat

# Verifier le statut
check_esmm_status.bat

# Metriques
esmm_metrics.bat

# Controle (pause/reprise)
esmm_control.bat
```

### CLI Python

```bash
python scripts/esmm_cli.py run --quick
python scripts/esmm_cli.py run --full --watch
python scripts/esmm_cli.py status <run_id>
python scripts/esmm_cli.py metrics
python scripts/esmm_cli.py gaps --type bridge
```

## Structure

```
EPP_Verdict/
├── app/                    # FastAPI + API endpoints
│   ├── api/chat.py         # Endpoint conversation
│   ├── api/graph.py        # Mutations graphe + ESMM
│   └── static/index.html   # Interface web
├── services/
│   ├── consciousness/      # Metriques, adaptation, memoire
│   ├── esmm/               # Protocole ESMM Phase 1-3
│   ├── providers/          # Abstraction multi-providers (Ollama, Anthropic, OpenAI)
│   └── solana/             # Integration Solana (config, bridge, client, frame)
├── programs/
│   └── epp/                # Programme Anchor (Rust) — attestations on-chain
│       └── programs/epp/src/  # lib.rs, state.rs, errors.rs, constants.rs
├── cli/
│   └── epp_cli.py          # CLI EPP (ask, submit, query, frame, graph)
├── database/
│   ├── engine.py           # ISpaceDB (~80 methodes)
│   ├── pool.py             # Pool connexions async, cache LRU, concurrency limiter
│   ├── graph_delta.py      # GraphDelta + KappaCalculator (Ollivier + Jaccard)
│   └── schema.sql          # 23 tables SQLite
├── core/physics/bezier.py  # Moteur trajectoires
├── scripts/esmm_cli.py     # CLI ESMM
├── tools/                  # Utilitaires (hydrate/migrate embeddings)
├── tests/                  # Tests unitaires + integration
└── docs/                   # Documentation
```

## EPP CLI

```bash
# Poser une question multi-modeles
python -m cli.epp_cli ask "Bitcoin est-il une monnaie ?"

# Soumettre une attestation on-chain (devnet)
python -m cli.epp_cli submit <claim_hash> --devnet

# Interroger les attestations
python -m cli.epp_cli query <subject>

# Lister les cadres metrologiques
python -m cli.epp_cli frame list

# Statistiques du graphe
python -m cli.epp_cli graph stats
```

## Tests

**548 passed, 0 failed, 11 skipped** (16 fevrier 2026)

```bash
# Executer tous les tests
pytest tests/ -v

# Tests par phase
pytest tests/test_providers.py tests/test_rotator.py -v     # Phase 0.1 — Providers
pytest tests/test_phase02_*.py -v                            # Phase 0.2 — Embeddings
pytest tests/test_phase03_*.py -v                            # Phase 0.3 — Cristallisation
pytest tests/test_phase1_*.py -v                             # Phase 1 — Solana
pytest tests/test_phase2_*.py -v                             # Phase 2 — Robustesse
pytest tests/test_phase3_*.py -v                             # Phase 3 — Pipeline E2E
pytest tests/test_graph_delta.py -v                          # Graph delta + rollback
pytest tests/test_esmm_phase1.py -v                          # ESMM integration

# Tests Anchor (necessite WSL + Solana)
# wsl bash -lc "cd programs/epp && anchor test"
```

## Documentation

- **[Architecture technique](docs/ARCHITECTURE.md)** — Etat vivant du code, composants fonctionnels
- **[Changelog](docs/fr/CHANGELOG.md)** — Journal factuel des modifications
- **[Phase 1 Instructions](docs/To_do_list/PHASE_1_INSTRUCTIONS.md)** — Specifications couche Solana
- **[Plan MVP](docs/To_do_list/EPP_PLAN_MVP.md)** — Roadmap vers l'ancrage Solana
- **[API Swagger](http://localhost:8000/docs)** — Reference API auto-generee

## Licence

CC BY-NC 4.0 - [Simon Bouhier](https://github.com/SimonBouhier)
