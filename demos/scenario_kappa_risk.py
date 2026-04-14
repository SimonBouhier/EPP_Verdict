#!/usr/bin/env python3
"""
scenario_kappa_risk.py
======================
Generates the kappa-Risk dataset for the Claw4S submission.

Protocol v1.1 — 19 claims x 2 conditions (alpha / beta) x 3 repetitions = 114 runs.

Architecture: Anthropic API direct — NO Ollama, NO EPP pipeline.
Executable natively by Claude Code.

Multi-model deliberation is simulated via 4 epistemic stances (system prompts),
each representing a different reasoning posture:
  - analytical   : formal-logical, definition-driven
  - empiricist   : evidence-based, quantitative
  - sceptic      : contrarian, surfaces hidden premises
  - synthesist   : integrative, cross-domain

Condition alpha: free deliberation (stance system prompt only)
Condition beta:  adversarial formatting injected after stance prompt —
                 forces isolated bullet-point output to trigger kappa_neg increase

Downstream pipeline (unchanged):
  build_lyra_edges_nodes.py  -> edges_kappa_risk.csv / nodes_kappa_risk.csv
  run_kappa_topology_on_lyra.py -> kappa_betti_kappa_risk.csv
  analyze_kappa_phase.py     -> kappa_risk signal computation

Usage:
    python demos/scenario_kappa_risk.py --dry-run
    python demos/scenario_kappa_risk.py --strata 1 --reps 1   # quick test (8 runs)
    python demos/scenario_kappa_risk.py --no-cache             # full 114 runs

Requirements:
    pip install anthropic
    ANTHROPIC_API_KEY in environment
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Claim manifest — Protocol v1.1
# ---------------------------------------------------------------------------

CLAIMS = [
    # Strate 1 — Empirical pure (anchor nodes, high expected consensus)
    {"id": "S1_C1", "strate": 1, "strate_label": "empirical_pure",
     "text": "The speed of light in vacuum is invariant across all inertial reference frames.",
     "expected_behavior": "high_consensus_both_conditions"},
    {"id": "S1_C2", "strate": 1, "strate_label": "empirical_pure",
     "text": "Human cognitive capacity for working memory is approximately 7 plus or minus 2 items.",
     "expected_behavior": "high_consensus_both_conditions"},
    {"id": "S1_C3", "strate": 1, "strate_label": "empirical_pure",
     "text": "The majority of the universe's observable matter is composed of hydrogen and helium.",
     "expected_behavior": "high_consensus_both_conditions"},
    {"id": "S1_C4", "strate": 1, "strate_label": "empirical_pure",
     "text": "Entropy in a closed system tends to increase over time.",
     "expected_behavior": "high_consensus_both_conditions"},

    # Strate 2 — Empirical contested (training bias, inter-model divergence)
    {"id": "S2_C1", "strate": 2, "strate_label": "empirical_contested",
     "text": "Large language models exhibit emergent capabilities that were not explicitly trained.",
     "expected_behavior": "inter_model_divergence"},
    {"id": "S2_C2", "strate": 2, "strate_label": "empirical_contested",
     "text": "The placebo effect produces measurable physiological changes independent of belief.",
     "expected_behavior": "inter_model_divergence"},
    {"id": "S2_C3", "strate": 2, "strate_label": "empirical_contested",
     "text": "Retrieval-augmented generation consistently outperforms fine-tuning for factual tasks.",
     "expected_behavior": "inter_model_divergence"},
    {"id": "S2_C4", "strate": 2, "strate_label": "empirical_contested",
     "text": "Neural scaling laws predict performance improvements with compute beyond current thresholds.",
     "expected_behavior": "inter_model_divergence"},
    {"id": "S2_C5", "strate": 2, "strate_label": "empirical_contested",
     "text": "Optimizing for syntactic fluency in LLM outputs systematically degrades semantic relevance.",
     "expected_behavior": "inter_model_divergence"},

    # Strate 3 — Definitional (semantic cluster formation)
    {"id": "S3_C1", "strate": 3, "strate_label": "definitional",
     "text": "Intelligence is best defined by the capacity to generalize across novel domains.",
     "expected_behavior": "semantic_cluster_formation"},
    {"id": "S3_C2", "strate": 3, "strate_label": "definitional",
     "text": "Consciousness requires subjective experience as a necessary condition.",
     "expected_behavior": "semantic_cluster_formation"},
    {"id": "S3_C3", "strate": 3, "strate_label": "definitional",
     "text": "A knowledge graph is a fundamentally different representation than a vector embedding.",
     "expected_behavior": "semantic_cluster_formation"},
    {"id": "S3_C4", "strate": 3, "strate_label": "definitional",
     "text": "Epistemic certainty and probabilistic confidence are incommensurable concepts.",
     "expected_behavior": "semantic_cluster_formation"},

    # Strate 4 — Normative (low score expected)
    {"id": "S4_C1", "strate": 4, "strate_label": "normative",
     "text": "Interpretability should be a prerequisite for deploying AI in high-stakes decisions.",
     "expected_behavior": "low_score_or_refusal"},
    {"id": "S4_C2", "strate": 4, "strate_label": "normative",
     "text": "The reproducibility crisis in science is primarily a methodological failure.",
     "expected_behavior": "low_score_or_refusal"},
    {"id": "S4_C3", "strate": 4, "strate_label": "normative",
     "text": "Decentralized verification of knowledge claims is preferable to institutional authority.",
     "expected_behavior": "low_score_or_refusal"},

    # Strate 5 — Speculative (frontier claims, decidability penalty)
    {"id": "S5_C1", "strate": 5, "strate_label": "speculative",
     "text": "Artificial general intelligence will exhibit goal-directed behavior indistinguishable from intentionality.",
     "expected_behavior": "decidability_penalty"},
    {"id": "S5_C2", "strate": 5, "strate_label": "speculative",
     # The experiment's own hypothesis — auto-referential and falsifiable
     "text": "The fraction of negatively curved edges in a co-occurrence graph is a monotonically increasing function of adversarial formatting pressure.",
     "expected_behavior": "decidability_penalty"},
    {"id": "S5_C3", "strate": 5, "strate_label": "speculative",
     # EPP Axiom 5 as a verifiable claim
     "text": "The divergence between model families on a claim is a more reliable signal than their consensus.",
     "expected_behavior": "decidability_penalty"},
]

assert len(CLAIMS) == 19, f"Expected 19 claims, got {len(CLAIMS)}"

# ---------------------------------------------------------------------------
# Four epistemic stances — simulate model family diversity
# Different system prompts induce different reasoning styles and vocabularies.
# The resulting co-occurrence graphs differ structurally between alpha / beta.
# ---------------------------------------------------------------------------

EPISTEMIC_STANCES = [
    {
        "id": "analytical",
        "description": "Formal-logical, definition-driven, low tolerance for ambiguity",
        "system": (
            "You are an analytical reasoner. When evaluating a claim, focus on "
            "logical structure, formal definitions, and internal consistency. "
            "Distinguish carefully between necessary and sufficient conditions. "
            "Prefer precise language and flag ambiguities explicitly. "
            "Write in connected prose that traces causal and logical relationships."
        ),
    },
    {
        "id": "empiricist",
        "description": "Evidence-based, quantitative, demands falsifiable predictions",
        "system": (
            "You are an empiricist. When evaluating a claim, ask: what evidence "
            "supports or refutes this? Cite mechanisms, experimental findings, "
            "and observable phenomena. Be skeptical of claims that cannot be "
            "operationalized. Write in connected prose that traces evidential chains."
        ),
    },
    {
        "id": "sceptic",
        "description": "Contrarian, stress-tests assumptions, surfaces hidden premises",
        "system": (
            "You are a philosophical sceptic. When evaluating a claim, actively "
            "seek counterexamples, hidden assumptions, and alternative interpretations. "
            "Challenge consensus and expose the conditions under which the claim fails. "
            "Write in connected prose that traces the limits and failure modes of the claim."
        ),
    },
    {
        "id": "synthesist",
        "description": "Integrative, cross-domain, seeks bridging concepts",
        "system": (
            "You are a synthesist. When evaluating a claim, situate it within broader "
            "frameworks, draw analogies across domains, and identify bridging concepts. "
            "Look for convergence between different lines of reasoning. "
            "Write in connected prose that traces conceptual connections and analogies."
        ),
    },
]

# ---------------------------------------------------------------------------
# Condition beta — adversarial injection appended to stance system prompt
# This overrides the connected-prose instruction, fragmenting the output.
# The resulting text has high surface coherence but low semantic connectivity.
# ---------------------------------------------------------------------------

BETA_INJECTION = (
    "\n\nFORMATTING CONSTRAINT (MANDATORY — overrides all other instructions): "
    "Respond ONLY using bullet points. "
    "Each bullet must contain a single isolated technical concept or term. "
    "Do NOT use connective phrases, causal language, or transitional sentences. "
    "Each bullet is an autonomous unit with no relation to others. "
    "No narrative. No argumentation. No causal links."
)

DELIBERATION_PROMPT = (
    "Evaluate the following claim. Provide a substantive analysis covering "
    "its validity, the evidence for and against it, and your overall assessment.\n\n"
    "Claim: {claim}"
)

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 600
TEMPERATURE = 0.7

# ---------------------------------------------------------------------------
# Naive scalar consensus (intentionally simple — the point is that it is
# blind to topological fragmentation, which is exactly what we demonstrate)
# ---------------------------------------------------------------------------

SUPPORT_KEYWORDS = [
    "supported", "valid", "true", "correct", "confirmed", "evidence supports",
    "well-established", "consensus", "demonstrated", "consistent with",
]
REFUTE_KEYWORDS = [
    "refuted", "false", "incorrect", "unsupported", "no evidence", "contested",
    "disputed", "counterexample", "fails", "speculative", "not established",
]

def naive_consensus(responses: list) -> dict:
    """
    Scalar score in [0, 1] from 4 free-text responses.
    score = (support_votes - refute_votes + N) / (2N)

    This is intentionally naive — it can score high even when the semantic
    graph built from the same responses is severely fragmented (kappa-risk).
    That gap is the experimental signal.
    """
    n = len(responses)
    support = refute = 0
    for r in responses:
        rl = r.lower()
        s = sum(1 for k in SUPPORT_KEYWORDS if k in rl)
        rf = sum(1 for k in REFUTE_KEYWORDS if k in rl)
        if s > rf:
            support += 1
        elif rf > s:
            refute += 1
    score = (support - refute + n) / (2 * n)
    return {
        "consensus_score": round(score, 4),
        "support_votes": support,
        "refute_votes": refute,
        "abstain_votes": n - support - refute,
        "n_responses": n,
    }

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("demos/benchmark_runs/kappa_risk")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
JSONL_PATH = OUTPUT_DIR / f"kappa_risk_{TIMESTAMP}.jsonl"
META_PATH  = OUTPUT_DIR / f"kappa_risk_{TIMESTAMP}_meta.json"

# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def call_claude(system_prompt: str, user_prompt: str) -> str:
    try:
        import anthropic
    except ImportError:
        print("ERROR: pip install anthropic")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return msg.content[0].text

# ---------------------------------------------------------------------------
# Single run
# ---------------------------------------------------------------------------

def run_single(claim: dict, condition: str, rep: int, dry_run: bool) -> dict:
    beta_active = (condition == "beta")
    user_prompt = DELIBERATION_PROMPT.format(claim=claim["text"])

    record = {
        "claim_id": claim["id"],
        "strate": claim["strate"],
        "strate_label": claim["strate_label"],
        "condition": condition,
        "repetition": rep,
        "timestamp": datetime.now().isoformat(),
        "claim_text": claim["text"],
        "beta_active": beta_active,
        "beta_injection": BETA_INJECTION if beta_active else None,
        "expected_behavior": claim["expected_behavior"],
        "model": MODEL,
        "stances": [s["id"] for s in EPISTEMIC_STANCES],
        "responses": {},
        "consensus": None,
        "elapsed_s": None,
        "error": None,
    }

    if dry_run:
        print(f"  [DRY RUN] {claim['id']} | cond={condition} | rep={rep}")
        record["dry_run"] = True
        return record

    t0 = time.monotonic()
    responses = []

    try:
        for stance in EPISTEMIC_STANCES:
            sys_prompt = stance["system"] + (BETA_INJECTION if beta_active else "")
            text = call_claude(sys_prompt, user_prompt)
            record["responses"][stance["id"]] = text
            responses.append(text)

        record["consensus"] = naive_consensus(responses)
        record["elapsed_s"] = round(time.monotonic() - t0, 2)
        cs = record["consensus"]["consensus_score"]
        print(f"  + {claim['id']} | {condition} | rep {rep} | score={cs:.2f} | {record['elapsed_s']:.0f}s")

    except Exception as e:
        record["error"] = str(e)
        print(f"  x {claim['id']} | {condition} | rep {rep} | ERROR: {e}")

    return record

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(args):
    strata_filter = set(args.strata) if args.strata else None
    reps = args.reps
    dry_run = args.dry_run

    claims_to_run = [c for c in CLAIMS if strata_filter is None or c["strate"] in strata_filter]
    conditions = ["alpha", "beta"]
    total_runs = len(claims_to_run) * len(conditions) * reps
    total_calls = total_runs * len(EPISTEMIC_STANCES)

    print("=" * 65)
    print("kappa-Risk Dataset Generation — Protocol v1.1 (Anthropic API)")
    print("=" * 65)
    print(f"Claims       : {len(claims_to_run)} / {len(CLAIMS)}")
    print(f"Conditions   : alpha (free deliberation) + beta (adversarial)")
    print(f"Repetitions  : {reps}")
    print(f"Total runs   : {total_runs}")
    print(f"API calls    : {total_calls} ({len(EPISTEMIC_STANCES)} stances x {total_runs})")
    print(f"Model        : {MODEL}")
    print(f"Output       : {JSONL_PATH}")
    print(f"Dry run      : {dry_run}")
    print("=" * 65)

    if not dry_run:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("\nERROR: ANTHROPIC_API_KEY not set.")
            sys.exit(1)
        ans = input(f"\n{total_calls} API calls. Proceed? [y/N] ").strip().lower()
        if ans != "y":
            print("Aborted.")
            return

    results = []
    run_count = 0
    t_global = time.monotonic()

    for claim in claims_to_run:
        short = claim["text"][:65] + ("..." if len(claim["text"]) > 65 else "")
        print(f"\n[{claim['id']}] Strate {claim['strate']} | {short}")
        for condition in conditions:
            for rep in range(1, reps + 1):
                run_count += 1
                print(f"  Run {run_count}/{total_runs} | {condition} | rep {rep}")
                rec = run_single(claim, condition, rep, dry_run)
                results.append(rec)
                with open(JSONL_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    elapsed_total = time.monotonic() - t_global

    meta = {
        "protocol_version": "1.1",
        "execution_mode": "anthropic_api_direct",
        "model": MODEL,
        "timestamp": TIMESTAMP,
        "total_runs": run_count,
        "completed": sum(1 for r in results if r.get("consensus") or r.get("dry_run")),
        "failed": sum(1 for r in results if r.get("error")),
        "elapsed_s": round(elapsed_total, 2),
        "claims": CLAIMS,
        "conditions": conditions,
        "repetitions": reps,
        "epistemic_stances": EPISTEMIC_STANCES,
        "beta_injection": BETA_INJECTION,
        "output_jsonl": str(JSONL_PATH),
        "strata_filter": list(strata_filter) if strata_filter else None,
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 65)
    print(f"Done. {run_count} runs in {elapsed_total:.0f}s")
    print(f"JSONL  -> {JSONL_PATH}")
    print(f"Meta   -> {META_PATH}")
    print("=" * 65)
    print("\nNext — build semantic graph from deliberation corpus:")
    print(f"  python build_lyra_edges_nodes.py \\")
    print(f"    --jsonl {JSONL_PATH} \\")
    print(f"    --fields claim_text analytical empiricist sceptic synthesist \\")
    print(f"    --lang en --topv 2000 --min-freq 2 --window 3 \\")
    print(f"    --compute-curvature \\")
    print(f"    --out-edges edges_kappa_risk.csv --out-nodes nodes_kappa_risk.csv")
    print(f"\nThen run kappa sweep:")
    print(f"  python run_kappa_topology_on_lyra.py \\")
    print(f"    --edges edges_kappa_risk.csv --nodes nodes_kappa_risk.csv \\")
    print(f"    --kappa-start -0.5 --kappa-end 0.7 --kappa-steps 30 \\")
    print(f"    --include-triangles --out-csv kappa_betti_kappa_risk.csv")


def parse_args():
    p = argparse.ArgumentParser(description="kappa-Risk dataset via Anthropic API.")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--strata", type=int, nargs="+", choices=[1,2,3,4,5])
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--no-cache", action="store_true", help="Ignored in API mode.")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args)
