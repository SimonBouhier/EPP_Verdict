# Technical Debt — EPP_Verdict

This file centralizes deliberate, conscious technical debts taken during
the Colosseum sprint. Each item is a compromise, not a bug. Each item has
a planned resolution.

Last updated: 2026-05-01

---

## TD-001 — Benchmark JSONs duplicated under `ui/public/data/`

**Status:** active
**Since:** 2026-04-23 (commits `fix(ui): commit public/data/...`)
**Scope:** `ui/public/data/*.json` mirrors `demos/benchmark_runs/*.json`

### What
The Vite/React dashboard reads benchmark JSONs from `ui/public/data/`,
which are committed to the repo and bundled by Vercel at build time.
The canonical source remains `demos/benchmark_runs/`. A `copy-data`
script keeps them in sync at build time but tolerates `demos/` being
absent from the build context.

### Why this is debt
- Two sources of truth that must be kept aligned.
- A run produced locally is not visible on the live dashboard until
  the JSON is committed and pushed.
- Storage duplication (~24 JSONs as of 2026-04-26).

### Why it was accepted
- Vercel build context cannot read `../demos/` outside the `ui/` root.
- Solo sprint, hackathon timeline. A backend reading runs at runtime
  was out of scope for Phase 2.
- Files are small (< 1 MB total).

### Planned resolution
- Post-hackathon: move benchmark runs to a small read-only API
  (S3, Cloudflare R2, or a tiny FastAPI endpoint) and remove
  `ui/public/data/` from version control.
- Until then: enforce parity in CI (script that fails if any JSON
  diverges between `demos/benchmark_runs/` and `ui/public/data/`).

### Verified parity (2026-04-26 audit)
24 / 24 JSONs identical between the two locations.

---

## TD-002 — `graph_seeder_blockchain` scenario without UI adapter

**Status:** active, slated W4
**Since:** 2026-03-02 (JSON exists, no adapter wired)

### What
`ui/public/data/graph_seeder_blockchain_20260302_143728.json` is
referenced in `ui/src/config/families.ts` (family `pipeline`) but
no entry exists in the `ADAPTERS` registry. Clicking it in the
dashboard surfaces an explicit error:
`No adapter registered for scenario "graph_seeder_blockchain".`

5 of the 12 on-chain attestations matching a benchmark JSON come
exclusively from this file.

### Why this is debt
The /onchain page lists those 5 attestations without a corresponding
claim viewer. The error is visible, not silent — but the UX is incomplete.

### Why it was accepted
Scenario was a graph-seeding test, not a presentation deliverable.
Decision (2026-04-26 audit): adapter to be written in W4, not now.

### Planned resolution
W4: write `graph_seeder_blockchain` adapter following the pattern of
the 4 existing adapters (`flywheel_v2_baseline`, `scenario_6_1_*`,
`scenario_6_2_*`, `scenario_jiang`).

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
