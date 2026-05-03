# ADR-020: Formal Specification Layer — Lean 4 invariants for the on-chain attestation contract

**Date**: 2026-04-17
**Status**: Active (v1 — closing the first Lean session) ; scope clarified 2026-05-02
**Dependencies**: ADR-001 (float↔u16 encoding), ADR-005 (multi-criteria tiers), ADR-006 (deterministic claim hash), ADR-012 (deterministic bifurcation), ADR-017 (cluster network), ADR-019 (on-chain Enum V2)
**Axioms invoked**: 3 (regression-cut transparency), 4 (local computation, on-chain proof)

> **Scope clarification — 2026-05-02.** The current public framing —
> "Formal Specification Layer" — supersedes the earlier "Dual-Trust"
> wording kept in the body of this ADR for historical accuracy.
> The formal layer documents the on-chain attestation contract; the
> empirical layer measures AI calibration. The bridge between the two
> is human-maintained, not mechanical: see WHITEPAPER §"Formal
> Specification Layer (ADR-020)" for current framing, and
> `TECH_DEBT.md::TD-005` for the planned mechanical Python ↔ Lean
> conformance bridge. This note does not amend the decisions taken
> on 2026-04-17; it documents how those decisions were re-framed once
> the modesty of the actual deliverable was assessed.

---

## 1. Context

### 1.1 — The epistemic stake

EPP_Verdict claims to be a **formally verifiable** AI consensus protocol. This claim is ambiguous if not qualified. The implicit standard for the technical audience is that of formal verification of smart contracts (Certora, K Framework, ChronosVault): all program instructions are proven, absence of panic is guaranteed, global invariants hold under all reachable states.

This standard is **not** the one reached here, and cannot be with the tools available in April 2026: automatic Rust → Lean 4 translation (Aeneas, hax) remains experimental, and Certora does not support Anchor 0.32. Over-promising "formally verified program" would be misleading.

### 1.2 — The over-promise trap

The `LEAN4_RESEARCH_BRIEF.md` documents four traps to avoid, the most credibility-costly being:

> **Trap #4 — Academic over-promise.** Saying "formally verified" when only three lemmas on u16 encoding are proven is misleading. Honesty > impressive.

This ADR formalizes the defensible position: **the abstract epistemic protocol** has a set of invariants formally proven in Lean 4. The link between these proofs and the runtime code (Python, Rust) is documented, verified by observation, but **not mechanically guaranteed**. This distinction is structural, not temporary.

### 1.3 — The discovery of 2026-04-17 that forces rigor

During the 2026-04-17 session, three structural problems were unearthed in the existing proof infrastructure:

1. The `tier_verified_implies_conditions` theorem (INV-4) was **incomplete** — its proof did not compile.
2. The `RedTests.lean` file was **not included** in the default `lake build` because `Main.lean` did not import the `Formal` library.
3. The Lean CI (`lean_action_ci.yml`) ran the default target, hence compiled neither the lib nor the red tests.

Consequence: for about five weeks, the project documentation claimed "three invariants proven with non-tautology red tests" while (a) one of the three invariants was not actually proven and (b) the red tests were not exercised by the CI. This was not a lie — it was a guardrail blind spot.

This discovery gives strength to what follows: the requirements of this ADR are not theoretical. They respond to an observed failure mode.

---

## 2. Decision — Formal Specification Layer (originally framed as "Dual-Trust", see scope clarification above)

### 2.1 — Two complementary layers of trust

EPP_Verdict rests on **two distinct layers of trust** that must not be conflated:

| Layer | Source of trust | Guarantee | Limit |
|:---|:---|:---|:---|
| **Empirical** (runtime) | Multi-LLM consensus + deterministic sources | Observable convergence, Brier scores, 5D signature | Statistical, not mathematical confidence. Depends on models and sources. |
| **Mathematical** (specification) | Lean 4 proofs over the abstract protocol | Invariants formally proven on a model | The model is not the code. The model↔code link is human. |

The two layers **do not oppose** and **do not substitute for** each other. They cover different risks:

- The empirical layer manages the risk "the model is wrong about the world".
- The mathematical layer manages the risk "the protocol is wrong about itself".

### 2.2 — What the Lean 4 layer proves

The Lean 4 layer proves that **the protocol**, defined as a mathematical specification, has the desired structural properties. It does not prove:

- That SHA-256 is secure (cryptography, out of scope).
- That the Python implementation respects the specification (semantic gap, §5).
- That the Rust implementation respects the specification (semantic gap, §5).
- That no implementation bug exists at runtime.

It proves that **if** the runtime code faithfully implements the specification, **then** the properties hold necessarily.

### 2.3 — Why it is useful despite these limits

1. **Executable documentation.** A Lean theorem is a specification that cannot silently drift. If someone modifies `assignTier` to lower a threshold one day, the TierBoundary theorem fails to compile. That is a guardrail prose comments cannot provide.

2. **Auditable reading.** An external auditor (hackathon reviewer, academic, AI agent picking up the repo) can read `Formal/` in ten minutes and know exactly which properties are guaranteed. Without ADR-020 and `Formal/`, this understanding would require a full read of the Python and Rust code.

3. **Preparation for Phase 3.** When Rust↔Lean tools mature (Aeneas, hax, others), the gap can be bridged mechanically. The current proofs are the foundation upon which this future extraction will rest.

---

## 3. Inventory of proven invariants (2026-04-17)

Eleven theorems are currently proven and compiled in the Lean lib, spread across five modules. The default `lake build` compiles the entirety (18 jobs).

### 3.1 — Module `Formal/Encoding.lean` — INV-1

| Theorem | Property proven |
|:---|:---|
| `score_bounded` | Every constructed `Score` has `val ≤ 10000`. |
| `zero_score_valid` | Score 0 is valid and decodable. |
| `max_score_valid` | Score 10000 is valid and decodable. |
| `score_roundtrip_bounded` | Any encoded then decoded score stays within `[0, SCORE_SCALE]`. |

**Code correspondence**: `bridge.py::float_to_u16` and `bridge.py::u16_to_float`.

### 3.2 — Module `Formal/TierBoundary.lean` — INV-4

| Theorem | Property proven |
|:---|:---|
| `tier_verified_implies_conditions` | If `assignTier` returns `verified`, then `score ≥ 8500 ∧ (models ≥ 3 ∨ hasAnchor)`. |

**Code correspondence**: `attestation.py` (tier-assignment logic).

**Associated red tests** (in `RedTests.lean`):

| Test | Property proven |
|:---|:---|
| `red_tier_1_low_score_not_verified` | score 5000, 5 models, anchor ⇒ **NOT** verified. |
| `red_tier_2_no_anchor_few_models_not_verified` | score 8500, 1 model, no anchor ⇒ **NOT** verified. |
| `green_tier_1_high_score_many_models_verified` | score 8500, 3 models ⇒ verified (passing case). |
| `green_tier_2_high_score_with_anchor_verified` | score 8500, anchor ⇒ verified (passing case). |

### 3.3 — Module `Formal/SourceAnchor.lean` — INV-6

| Theorem | Property proven |
|:---|:---|
| `deterministic_requires_anchor` | Well-formed attestation + deterministic type ⇒ source_anchor non-null. |
| `deterministic_without_anchor_not_wellformed` | Corollary: deterministic without anchor ⇒ not well-formed. |

**Code correspondence**: ADR-012 (deterministic bifurcation), `services/sources/adapters/`.

### 3.4 — Module `Formal/ClaimHash.lean` — INV-2

| Theorem | Property proven |
|:---|:---|
| `claim_hash_purity` | Two attestations with identical canonical core have the same hash. |
| `claim_hash_timestamp_independent` | Timestamp does not enter into the identity of a claim. |
| `claim_hash_submitter_independent` | Submitter does not enter into the identity of a claim. |

**Code correspondence**: `services/esmm/attestation.py::compute_claim_hash` (lines 183-210).

**Associated red tests**:

| Test | Property proven |
|:---|:---|
| `red_hash_1_timestamp_independence` | Different timestamps, same core ⇒ same hash. |
| `red_hash_2_submitter_independence` | Different submitters, same core ⇒ same hash. |

**Architectural importance**: INV-2 is the condition of possibility of ADR-017 (cluster network). Without this property, two clusters could not produce comparable attestations on the same claim.

---

## 4. Non-tautology methodology

### 4.1 — The double-falsification protocol

Every delivered invariant must be accompanied by at least one red test that **fails** if the invariant is broken. The validation procedure is:

1. **GREEN**: `lake build` passes with the invariant in place.
2. **RED**: temporarily falsify the invariant's definition (e.g., by lowering a threshold or weakening a constraint), rebuild, the build **must** fail.
3. **RESTORE**: restore the original definition, rebuild, build passes again.

If the RED step does not fail, the invariant is **tautological** — its proof does not depend on the property it claims to establish. It must be reformulated.

### 4.2 — Why this requirement is non-negotiable

The 2026-04-17 discovery revealed a concrete case of an apparent but actually defective invariant (incomplete TierBoundary, masked by an orphan RedTests). Without systematic double falsification, these false positives can traverse the project lifecycle for months.

The marginal cost of a manual falsification is 5 minutes. The cost of a regression detected in production (or worse: undetected) is incomparable.

### 4.3 — What CI now guarantees

Since the 2026-04-17 commit (`import Formal` in `Main.lean`), default `lake build` — the command run by `leanprover/lean-action@v1` in CI — compiles the **entire** lib, i.e. 18 jobs including all Lean modules and all red tests.

Any future regression breaking an invariant or a red test will be caught at the next push. This is a magnitude-of-order change: before, CI compiled an `exe main` that imported no Lean module.

---

## 5. Model ↔ code conformance — honest limits

### 5.1 — The semantic gap (trap #3 of the brief)

Lean 4 proofs bear on a **model** of the protocol, not on the code that implements it. This distinction is permanent with current tools: there is no automatic and reliable extraction from Rust to Lean 4 in April 2026. The link between Lean definitions and Python/Rust functions is **human**.

Practical consequences:

- A Lean proof remains valid if the model is correct. If the model diverges from the code, the proof is **worthless for runtime**, even if it remains formally correct.
- The responsibility to maintain the model↔code link rests on contributors (humans and AI agents). This responsibility must be explicitly recognized, not assumed.

### 5.2 — Current conformance verifications

For each delivered invariant, conformance to the runtime code was verified by **direct observation** at the time of writing:

| Invariant | Conformance verification | Result |
|:---|:---|:---|
| INV-1 (Encoding) | `TestInv1Encoding` conformance tests in `tests/test_lean_conformance.py` | ✅ 8 GREEN tests + falsification proven |
| INV-4 (TierBoundary) | `TestInv4TierBoundary` tests exercising `derive_confidence_tier` | ✅ 7 GREEN tests. Python stricter than Lean (architecture_families ≥ 2) |
| INV-6 (SourceAnchor) | Pydantic `model_validator` in `EpistemicAttestation` + `TestInv6DeterministicAnchorStrict` tests | ✅ Runtime-enforced. Initial discovery: rule absent, added 2026-04-18 |
| INV-2 (ClaimHash) | `TestInv2ClaimHashPurity` tests exercising `compute_claim_hash` | ✅ 8 GREEN tests, including Python normalization (lower/strip) |

These verifications are **point-in-time observations**, not continuous guarantees. A future modification of Python or Rust code could introduce a divergence without the Lean proofs detecting it.

### 5.3 — Known and documented gap: INV-2 normalization

The Python `compute_claim_hash` code applies `.lower().strip()` to each field before concatenation (lines 205-210). The Lean 4 model does not model this normalization — it concatenates strings as-is.

Consequence:

- The Python code satisfies a **stronger** property than the Lean model: "claims identical after normalization → same hash".
- The Lean model proves: "claims literally identical → same hash".
- The two properties are compatible: the Python property implies the Lean property. No security divergence.
- A future version of the Lean model could include normalization to tighten the correspondence.

### 5.4 — Rust gap: not closed, documented

The correspondence Lean model ↔ Rust code (Solana program) is **not** verified in this version. The current Rust program does not compute `claim_hash` — it receives it as a parameter and stores it. INV-4 and INV-6 invariants, were they to be enforced on-chain in a future version, would require either adding corresponding `require!` in `lib.rs`, or external verification (Certora or equivalent).

This limitation is accepted and documented. It will be lifted when:
- Rust↔Lean tools mature (Aeneas, hax), **or**
- Certora adds stable Anchor 0.32 support, **or**
- The concerned invariants are manually ported to `require!` with on-chain RED test (as done for Enum V2 in ADR-019).

### 5.5 — Conformance tests: the empirical bridge between specification and runtime

The architecture (§2.1) describes two layers: empirical (runtime) and the formal specification (Lean). The 2026-04-18 session formalized the **observable link** between the two, via the `tests/test_lean_conformance.py` suite: 26 tests that exercise the Python code against the rules specified in Lean.

These tests are not a mechanical extraction (Rust↔Lean remains beyond 2026 tools), but an **observable guardrail**: if the runtime code drifts from a proven rule, the corresponding test fails in CI.

Methodologically, this suite **immediately revealed a concrete gap**: INV-6 was proven in Lean but not enforced in Python (an `epistemic_type=deterministic` attestation could be built without a `source_anchor`). The fix was applied in the same session (Pydantic `model_validator`), and the test became GREEN. Without this suite, the gap would have stayed latent.

This discovery empirically validates the usefulness of the approach — ADR §5 no longer speaks of the "risk of divergence" hypothetically, but of an observed, documented, and closed divergence.

---

## 6. What is acquired — and for what

### 6.1 — Relative to the roadmap

| Invariant | Direct utility for the project |
|:---|:---|
| INV-1 (Encoding) | Guarantees consistency of float↔u16 conversions used everywhere: consensus_score, 5D signature, on-chain encoding. |
| INV-4 (TierBoundary) | Makes the `verified` tier formally characterized. A tier displayed as `verified` necessarily satisfies the promotion conditions. |
| INV-6 (SourceAnchor) | Formally documents the `deterministic` semantics (ADR-012): a deterministic attestation necessarily has an authoritative source. |
| INV-2 (ClaimHash) | **Condition of possibility of ADR-017.** Two independent clusters produce the same `claim_hash` for the same claim, which makes cross-cluster queries possible. |

### 6.2 — For an external auditor

A reviewer who consults `Formal/` can affirm without risk:

- The abstract protocol has 11 formally proven theorems.
- The proofs are exercised by CI on every push.
- Red tests prove the invariants are not tautological.
- The link between proofs and runtime code is documented and verified by observation, not mechanically guaranteed.

This level of guarantee is **higher** than that of most existing oracles and AI consensus protocols, which have no formal specification. It is **lower** than that of ChronosVault (100+ theorems) or a Certora-verified smart contract.

---

## 7. What is not proven (out of hackathon scope)

### 7.1 — Identified but not proven invariants

| Invariant | Difficulty | Reason for exclusion |
|:---|:---|:---|
| INV-3 (PDA uniqueness) | Tier 1 | Guaranteed by Solana mechanics itself; a Lean proof would be redundant and purely didactic. |
| INV-5 (Regression cut isolation) | Tier 2 | Vacuously true in the current architecture — no instruction compares two attestations. Useful if a future comparison instruction is added. |
| INV-7 (Brier proper scoring) | Tier 3 | Requires `mathlib` (measure theory). Estimated 2-4 weeks for a beginning prover. Out of hackathon scope. |
| INV-8 (Consensus convergence) | Tier 3 | Requires axioms about conditional model independence. Decision-theory theorem. Out of scope. |

### 7.2 — Properties that remain conjectural

- Absence of panic in Rust code (would need Certora or Aeneas).
- Absence of arithmetic overflow on `u16`/`u8` Rust-side.
- Inter-frame coherence: two attestations of the same claim with two different frames are not directly comparable. Enforced by design (frame enters claim_hash), not formally proven.

These properties may become later ADR-021+, depending on project evolution and available tools.

---

## 8. Acceptance criteria for future invariants

Any new invariant added to `Formal/` must satisfy:

1. **Theorem proven without `sorry`, `admit`, or ad-hoc axiom.**
2. **At least one associated red test** that fails if the invariant is broken (protocol §4.1).
3. **Red test included in `lake build`** via import from `Formal.lean` (RedTests-orphan lesson learned).
4. **Conformance verification**: the corresponding Python and/or Rust code is identified by grep or explicit reference, and any discrepancies are documented.
5. **Reference to an ADR** (existing or new) that contextualizes the invariant in the project architecture.
6. **Python conformance test** associated with the invariant, living in `tests/test_lean_conformance.py`. The test must fail if the Python code drifts from the rule. If the invariant concerns a rule not enforced in Python, the test written GREEN must become a discovery to fix (validator addition, function modification), not an `xfail`.

An invariant that does not satisfy these criteria cannot be presented as "proven" in the documentation.

---

## 9. References

### Internal

- **LEAN4_RESEARCH_BRIEF.md** — Founding research note. Documents the traps and the difficulty tiers.
- **ADR-001** — float→u16 encoding (runtime correspondence of INV-1).
- **ADR-005** — Multi-criteria confidence tiers (runtime correspondence of INV-4).
- **ADR-006** — Deterministic claim hash (runtime correspondence of INV-2).
- **ADR-012** — Deterministic bifurcation (runtime correspondence of INV-6).
- **ADR-017** — Epistemic cluster network (consumer of INV-2).
- **ADR-019** — On-chain Enum V2 projection (prepares Lean 4).

### Producing commits

- `1d703fd` (2026-04-15) — Lean 4 install + first three invariants (INV-1, INV-4 partial, INV-6) + initial RedTests.
- `86539e7` (2026-04-17) — Anchor.toml localnet fix + on-chain `epp_enum_v2_guard.ts` test.
- `07ae3e8` (2026-04-17) — Documentation sync CHANGELOG/README/ARCHITECTURE.
- RedTests + TierBoundary + Main wiring fix (2026-04-17) — CI infrastructure repaired, INV-4 completed, double-falsification introduced.
- INV-2 ClaimHash Purity (2026-04-17) — 3 theorems + 2 red tests + Attestation extension.
- Conformance commit (2026-04-18) — `tests/test_lean_conformance.py` (26 tests) + `EpistemicAttestation.validate_deterministic_requires_anchor` (Pydantic model_validator). Discovery and closure of the INV-6 Python↔Lean gap.

### Codebase — anchor points

- `Formal/lean-toolchain` — Lean version pinned to `leanprover/lean4:v4.29.1`.
- `Formal/Main.lean` — entry point that imports the whole lib (fix 2026-04-17).
- `Formal/Formal/*.lean` — the five proof modules.
- `.github/workflows/lean_action_ci.yml` — CI that runs default `lake build`.
- `services/esmm/attestation.py:183-210` — runtime implementation of INV-2.
- `bridge.py::float_to_u16` and `u16_to_float` — runtime implementation of INV-1.

### External dependencies

- Lean 4: [https://lean-lang.org/](https://lean-lang.org/)
- Lake (build system): [https://github.com/leanprover/lean4/tree/master/src/lake](https://github.com/leanprover/lean4/tree/master/src/lake)
- `leanprover/lean-action@v1` (CI GitHub Action): [https://github.com/leanprover/lean-action](https://github.com/leanprover/lean-action)

---

## 10. Closing remarks

This ADR closes the project's first structured formal-verification session. Eleven theorems proven, CI that bites, red tests exercised, code correspondence documented. This is a substantial achievement for an infrastructure initially set up in a few days.

The ADR also acknowledges its limits. State-of-the-art formal verification (Certora-grade) remains a distant goal, conditioned on the maturation of external tools. The present corpus of proofs does not pretend to it.

The honesty of this document is itself a commitment: any AI auditing this project in the future, any human contributor, any academic reviewer, must be able to read this ADR and calibrate **exactly** their level of trust. No more, no less.

This is what the EPP protocol claims for its epistemic attestations. It would be incoherent to apply a lower standard to its own documentation.
