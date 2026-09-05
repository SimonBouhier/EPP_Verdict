# Technical Debt — EPP_Verdict

This file centralizes deliberate, conscious technical debts taken during
the Colosseum sprint. Each item is a compromise, not a bug. Each item has
a planned resolution.

Last reviewed: 2026-09-05 (TD-001 updated; later entries retain their original dates).

Blockchain, cluster and publication references in older entries are historical
under ADR-022. The current maintained scope is in [CURRENT_STATUS](docs/CURRENT_STATUS.md).

---

## TD-001 — Historical dashboard snapshot

**Status:** resolved by scope reduction in source, 2026-09-05 (ADR-022).
Public deployment is a separate promotion step.

The dashboard now preserves the committed `ui/public/data/` snapshot.
Build and development commands verify its hashes without refreshing it from
`demos/benchmark_runs/`. The legacy copy script refuses execution.

No new read-only API is planned. The former requirement to synchronize a live
benchmark feed is closed. Historical files remain in both locations as evidence;
this is a fixed archive, not two competing current datasets.

`ui/archive-manifest.json` binds the archived text with LF-normalized line endings. An intentional future
archive update would require a separately reviewed change of this manifest.
Original TD-001 discussion remains in Git at `84879d2`.

---

## TD-002 — `graph_seeder_blockchain` scenario without UI adapter

**Status:** resolved
**Since:** 2026-03-02 (JSON exists, no adapter wired)
**Resolved:** 2026-05-09

### What (original)
`ui/public/data/graph_seeder_blockchain_20260302_143728.json` was
referenced in `ui/src/config/families.ts` (family `pipeline`) but
no entry existed in the `ADAPTERS` registry. Clicking it in the
dashboard surfaced an explicit error:
`No adapter registered for scenario "graph_seeder_blockchain".`

5 of the 12 on-chain attestations matching a benchmark JSON came
exclusively from this file.

### Resolution applied (2026-05-09)
- New adapter `ui/src/data/adapters/graph-seeder-blockchain.ts`. The
  seeder JSON publishes claims with `verdict: null` (verdicts are
  produced later, when claims are pushed on-chain), so the adapter
  joins the seeder payload with `devnet_pushed.json` by `question`
  text and surfaces only the claims that have a matching
  attestation — picking up the verdict from there. The 5 on-chain
  attestations now have a corresponding claim viewer entry.
- `Adapter` type extended with an optional second parameter
  (`onchain?: OnChainManifest`) so adapters that need on-chain
  context can join it in. Existing adapters ignore the parameter
  and remain source-compatible.
- `loadRun` (`ui/src/data/loader.ts`) fetches the run payload and
  the on-chain manifest in parallel and forwards both to the
  selected adapter.
- `ClaimTypeSchema` extended to include `'foundational'` and
  `'security_audit'` — both already present in on-chain
  attestations (`epistemic_type` u8=0 and u8=2 respectively, see
  `programs/epp/src/state.rs::epistemic_type_to_u8`).
- Vitest test `ui/src/data/adapters/graph-seeder-blockchain.test.ts`
  (4 cases, RED-GREEN-FIX): joins by question text, drops claims
  without a matching attestation, returns zero claims when no
  on-chain manifest is provided, preserves the raw payload.

### Validation
`vitest run` → 4 / 4 passed. `tsc --noEmit` → clean.

---

## TD-003 — Test count drift between live and documentation

**Status:** resolved
**Since:** noticed 2026-04-26 audit
**Resolved:** 2026-05-01 (consolidation sweep with audit P1–P4 docs update)

### What
- Local `pytest tests/ -q` (post-audit P1–P4): **908 passed, 11 skipped**.
- README badge, PITCH "What Exists Today", WHITEPAPER closing line all
  aligned to 908 in the same sweep.

### Resolution applied (2026-05-01)
Single sweep across `README.md`, `PITCH.md`, `WHITEPAPER.md`. Verified
count: `python -m pytest tests/ --tb=short -q` → `908 passed, 11 skipped,
1 warning`. The lone warning (`invalid escape sequence '\ '` in
`tests/test_phase4_runtime_fixes.py`) is pre-existing and unrelated.

`docs-site/` not re-synced as part of this resolution — sync via
`node docs-site/scripts/sync-docs.mjs` is a separate maintenance task.

---

## TD-004 — Git author drift on commit `f12a922`

**Status:** noted, no action planned
**Since:** 2026-02-13

### What
The Colosseum eligibility anchor commit `f12a922` is authored as
`Fractal Fox <simon.bouhier@proton.me>`. Subsequent commits use
`Simon Bouhier <simon.bouhier@proton.me>`. Email is identical.

### Why this is debt
None operational — Colosseum eligibility is verified on email
identity, not git pseudonym.

### Why it was accepted
Cosmetic. Rewriting git history would invalidate the anchor commit
hash itself, defeating the purpose.

### Planned resolution
None. Document in the Colosseum submission form if a "git author
discrepancy" question is asked.

---

## TD-005 — Lean spec ↔ Python/Rust drift not mechanically guarded

**Status:** active, prioritised next (audit P4.1 prereq)
**Since:** documented 2026-04-30 (audit P3 closure) ; reaffirmed
2026-05-01 (audit P4.2 closure)

### What
The `Formal/` Lean 4 spec proves invariants on an abstract model of the
protocol (`EpistemicType`, `ConfidenceTier`, `Score`, `SourceAnchor`,
`Attestation`). The runtime systems live in Python (`services/esmm/`,
`services/solana/bridge.py`) and Rust (`programs/epp/`). The link between
the Lean model and the runtime code is **human-maintained**, observed
by a conformance test suite (`tests/test_lean_conformance.py`,
`tests/test_lean_conformance_property.py` — 26 unit tests + 16 property
tests with up to 10 000 inputs each), but **not mechanically guaranteed**.

ADR-020 §5 documents this gap explicitly. Audit P4 proved 5 structural
theorems (4 `iff` on tiers + 1 corollary) and aligned Python ↔ Lean on
the `SourceAnchor` contract (P4.2: `pattern=r"^[0-9a-f]{64}$"`), but
did not close the structural gap — only narrowed it.

### Why this is debt
- A future modification to `services/esmm/attestation.py::compute_claim_hash`
  could silently diverge from the Lean `claimHash` definition. The
  property test would catch most cases (5 INV-2 properties × 10 000
  inputs), but coverage is empirical, not formal.
- The Rust gap is wider still — `programs/epp/src/lib.rs` has no
  conformance harness against the Lean spec at all. Anchor instructions
  enforce `epistemic_type <= 2` at the byte level (ADR-019) but not the
  full inter-field invariants (e.g. `epistemic_type=1 ⇒ source_anchor ≠ [0; 32]`).
- A LLM agent or human contributor working on either side can break
  the alignment without the build catching it.

### Why it was accepted
- Mechanical extraction Rust → Lean (Aeneas, hax) is not production-ready
  in April 2026.
- Certora support for Anchor 0.32 is not stable.
- The empirical conformance suite is honest and observable: when a
  divergence appears, it tends to surface as a failing test (cf. P4.2
  alignment, where the suite immediately exposed the 4 sites where
  Python had been more permissive than Lean).

### Planned resolution

**P4.1 (recommended next chantier — see `docs/audit/SESSION_AUDIT_FORMAL_P4.md` §8.1)** :
property-based testing croisé Python ↔ Lean. Implementation sketch:

1. Reimplement `assignTier` and `compute_claim_hash` in Python as `lean_oracle_*`
   functions that mirror the Lean spec exactly.
2. Use Hypothesis to generate 10 000 random `(score, models, has_anchor)`
   triplets and `(s, p, o, f, timestamp, submitter)` tuples.
3. Assert per-input equality between the production function and the
   oracle. Any divergence is a hard failure in CI.

Estimated cost: 2-3 days. Highest leverage of all post-audit P4 chantiers
because it converts an *affirmation* of fidelity into an *empirical
guarantee* over a large sample.

**Beyond P4.1** :
- Strengthen the Rust ↔ Lean link when Aeneas/hax mature, or via
  Certora when Anchor 0.32 support is stable.
- Add INV-7 (Brier proper scoring, binary case) — see
  `docs/research/RESEARCH_B_lean4_inv7_brier.md`. Estimated 12-19h
  for a 6th structural theorem.
