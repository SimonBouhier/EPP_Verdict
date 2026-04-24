# ADR-015: The Great Decoupling — Tripartite Kernel / Adapters / Domains architecture

**Date**: 2026-03-09
**Status**: Deferred (post-Colosseum hackathon)
**Author**: Sim (architect) + Opus (gatekeeper)
**Dependencies**: ADR-001 (model obsolescence), ADR-012 (authoritative sources), ADR-014 (audit pattern)

---

## 1. Context

EPP grew organically: ESMM pipeline inherited from Lyra, then smart contract audit (ADR-014), then deterministic sources (ADR-012), then geopolitics (ADR-016). Each addition works, but the physical directory structure does not reflect the logical separation that already exists in the code.

The risk: presenting a "gas factory" instead of a "modular framework".

The reality: the functional decoupling is already in place. The Kernel (`cycle_manager`, `consensus_engine`, `pipeline`) knows nothing about Solidity or ACLED. Audit is a consumer of the pipeline (ADR-014 §5.1). ACLED is a `SourceAdapter` like any other (ADR-012). What's missing is the physical materialization of this separation.

---

## 2. Decision

Restructure the directories into three explicit layers without modifying the existing logic. This is a surface refactor (moves + imports), not a rewrite.

### A. The EPP Kernel (domain-agnostic)

Everything related to the mechanics of debate. Must contain NO reference to Solidity, ACLED, SWC, or any specific domain.

```
services/esmm/                    # Unchanged — already the Kernel
    orchestrator.py               # Pilots ESMM runs
    cycle_manager.py              # Cycle execution
    cycle_prompts.py              # EXPLORE + VERIFY templates (generic)
    consensus_engine.py           # Vote, normalization, fingerprinting
    triplet_extractor.py          # Extraction + parsing
    verdict_encoder.py            # Verdict → triplets
    pipeline.py                   # Bridge orchestrator → crystallize
    attestation.py                # Crystallization
    ...
```

**Golden rule**: if `cycle_manager.py` contains an `if "SWC-107" in claim`, modularity is broken. The Kernel deals with text and probabilities.

### B. The Adapters layer (translators of the real world)

Transforms external data into formats the Kernel can process.

```
services/sources/                 # Already exists (ex-services/rwa/)
    adapters/
        base.py                   # ABC SourceAdapter
        opensanctions.py          # Sanctions
        ofac.py                   # OFAC
        eu_cfsp.py                # EU
        verra_vcs.py              # Carbon
        acled.py                  # ADR-016 — Armed conflicts
        slither_adapter.py        # ADR-014 — Solidity static analysis
        __init__.py               # _REGISTRY + get_adapter()
```

Each adapter has a single responsibility: fetch + normalize + version.
The Kernel does not know which adapter is being used.

### C. The Domains layer (knowledge plugins)

Each application domain holds its taxonomies, specialized prompts, benchmark scripts, and runners. A domain is a CONSUMER of the Kernel.

```
domains/
    smartcontracts/               # ADR-014
        swc_taxonomy.py           # 33 SWC + 8 ToB classes
        contract_slicer.py        # Solidity slicing
        audit_runner.py           # Orchestration slice → pipeline
        audit_prompts.py          # ASSESS_AUDIT / CHALLENGE_AUDIT / ADJUDICATE_AUDIT
        benchmark_config.py       # Ground truth, fixtures
    geopolitics/                  # ADR-016
        jiang_claims.py           # Claim catalog
        scenario_jiang.py         # Dual-path script
        geopolitical_prompts.py   # Specialized prompts (if needed)
    # Future domains:
    # legal/                      # Legal diagnostics
    # medical/                    # Medical diagnostics
    # defi/                       # DeFi protocols audit
```

**Why**: adding a new domain = create a directory + a few files. Zero Kernel modification. This is the scalability Colosseum wants to see.

---

## 3. What changes (physically)

| Current | Target | Type |
|:---|:---|:---|
| `services/audit/` | `domains/smartcontracts/` | git mv |
| `services/audit/swc_taxonomy.py` | `domains/smartcontracts/swc_taxonomy.py` | git mv |
| `services/audit/contract_slicer.py` | `domains/smartcontracts/contract_slicer.py` | git mv |
| `services/audit/audit_runner.py` | `domains/smartcontracts/audit_runner.py` | git mv |
| `demos/scenario_jiang.py` | `domains/geopolitics/scenario_jiang.py` | git mv |
| `cycle_prompts.py` (AUDIT prompts) | Extracted to `domains/smartcontracts/audit_prompts.py` | Extraction |
| Imports in CLI, tests, scripts | Updated | grep + sed |

### What does NOT change

- `services/esmm/` — the Kernel stays put
- `services/sources/` — adapters stay put
- `services/solana/` — the transport layer stays put
- `services/providers/` — LLM providers stay put
- `database/` — storage stays put
- `programs/epp/` — the Rust program stays put

---

## 4. Migration steps

### Step 1 — Normalize the input interface

Verify that the Kernel contains no direct reference to the domains:

```bash
grep -rn "SWC\|swc_taxonomy\|contract_slicer\|audit_runner\|ACLED\|acled\|jiang" \
    services/esmm/ --include="*.py"
```

If references exist in `cycle_prompts.py` (AUDIT templates), extract them to the relevant domain with an injection mechanism:

```python
# Kernel (cycle_prompts.py):
# Base EXPLORE + VERIFY templates stay here.
# Domain templates are injected by the domain at runtime.

def register_domain_templates(templates: Dict[CycleType, List[str]]) -> None:
    """Allows a domain to register its specialized templates."""
    for cycle_type, tmpl_list in templates.items():
        CYCLE_TEMPLATES[cycle_type].extend(tmpl_list)
```

### Step 2 — Create the domains/ structure

```bash
mkdir -p domains/smartcontracts domains/geopolitics
```

### Step 3 — Move the files

Atomic migration with full C1 audit:

```bash
# 1. Pre-migration diagnostic
grep -rn "services/audit\|services.audit\|from.*audit" --include="*.py" .

# 2. Move
git mv services/audit/ domains/smartcontracts/

# 3. Update imports
# Dedicated Python script (like the rwa → sources migration)

# 4. Post-migration C1 audit
grep -rn "services/audit" --include="*.py" .
# Must return 0 results

# 5. Non-regression
pytest tests/ -q
```

### Step 4 — Externalize AUDIT prompts

Extract from `cycle_prompts.py` the templates ASSESS_AUDIT, CHALLENGE_AUDIT, ADJUDICATE_AUDIT into `domains/smartcontracts/audit_prompts.py`.

The domain registers itself at startup:

```python
# domains/smartcontracts/__init__.py
from services.esmm.cycle_prompts import register_domain_templates
from .audit_prompts import AUDIT_TEMPLATES

register_domain_templates(AUDIT_TEMPLATES)
```

### Step 5 — The Solana Bridge in "Fire and Forget" mode (optional)

Currently, the pipeline waits for the Solana response. Decouple:

```python
# services/solana/anchor_daemon.py
class AnchorDaemon:
    """
    Watches new attestations in DB and submits them on-chain.
    Async queue. The pipeline does not block.
    """
    async def watch_and_submit(self):
        while True:
            pending = await db.get_pending_attestations()
            for att in pending:
                try:
                    tx = await client.submit_attestation(att)
                    await db.update_attestation_solana_tx(att, tx)
                except Exception:
                    await db.mark_submission_failed(att)
            await asyncio.sleep(10)
```

This avoids a 30-minute benchmark crashing because of an RPC timeout.

---

## 5. Risks

| Risk | Probability | Mitigation |
|:---|:---|:---|
| Broken imports post-migration | High | Diagnostic script + C1 + pytest baseline |
| Tests referencing the old paths | High | Exhaustive grep + update |
| `cycle_prompts.py` too coupled to domains | Medium | `register_domain_templates` mechanism |
| Regression on the deterministic path | Low | `source_anchor_builder.py` already decoupled |

---

## 6. Benefits for Colosseum

- **Maintainability**: survives model evolution (ADR-001)
- **Scalability**: 10 new languages = 10 domains, 0 Kernel modifications
- **Professionalism**: system architect, not sloppy coder
- **Visual pitch**: a single slide with 3 boxes (Kernel / Adapters / Domains) is worth more than 100 lines of code

---

## 7. Timing

**Deferred to post-hackathon.** Reasons:

1. The functional decoupling already exists — the Kernel knows nothing about the domains
2. A physical refactor risks breaking the baseline (791 tests)
3. The 5 fixes from Lot A + ADR-016 are more impactful for the demo
4. The pitch can describe the tripartite architecture without it being physically materialized in the directories

The Great Decoupling will be the first post-Colosseum chantier.
