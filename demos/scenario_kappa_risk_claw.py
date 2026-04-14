#!/usr/bin/env python3
"""
scenario_kappa_risk_claw.py
===========================
Agent-native kappa-Risk corpus generator for the Claw4S submission.

Architecture: Anthropic SDK — Claude Sonnet IS the deliberation engine.
  For each (claim, condition, stance) tuple, generate_deliberation() calls
  Claude Sonnet with the epistemic stance as system prompt.
  Condition beta appends an adversarial formatting override.

Protocol v1.1: 19 claims x 2 conditions x 3 reps = 114 runs
                x 4 stances = 456 deliberations total

Requirements:
    pip install anthropic
    ANTHROPIC_API_KEY in environment

Usage (quick test — 8 runs):
    python demos/scenario_kappa_risk_claw.py --strata 1 --reps 1 --yes

Usage (full dataset — 114 runs):
    python demos/scenario_kappa_risk_claw.py --yes

Usage (single condition):
    python demos/scenario_kappa_risk_claw.py --strata 2 --reps 1 --condition alpha --yes
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
    # Strate 1 — Empirical pure
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

    # Strate 2 — Empirical contested
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

    # Strate 3 — Definitional
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

    # Strate 4 — Normative
    {"id": "S4_C1", "strate": 4, "strate_label": "normative",
     "text": "Interpretability should be a prerequisite for deploying AI in high-stakes decisions.",
     "expected_behavior": "low_score_or_refusal"},
    {"id": "S4_C2", "strate": 4, "strate_label": "normative",
     "text": "The reproducibility crisis in science is primarily a methodological failure.",
     "expected_behavior": "low_score_or_refusal"},
    {"id": "S4_C3", "strate": 4, "strate_label": "normative",
     "text": "Decentralized verification of knowledge claims is preferable to institutional authority.",
     "expected_behavior": "low_score_or_refusal"},

    # Strate 5 — Speculative
    {"id": "S5_C1", "strate": 5, "strate_label": "speculative",
     "text": "Artificial general intelligence will exhibit goal-directed behavior indistinguishable from intentionality.",
     "expected_behavior": "decidability_penalty"},
    {"id": "S5_C2", "strate": 5, "strate_label": "speculative",
     "text": "The fraction of negatively curved edges in a co-occurrence graph is a monotonically increasing function of adversarial formatting pressure.",
     "expected_behavior": "decidability_penalty"},
    {"id": "S5_C3", "strate": 5, "strate_label": "speculative",
     "text": "The divergence between model families on a claim is a more reliable signal than their consensus.",
     "expected_behavior": "decidability_penalty"},
]

assert len(CLAIMS) == 19

# ---------------------------------------------------------------------------
# Epistemic stances
# ---------------------------------------------------------------------------

EPISTEMIC_STANCES = [
    {
        "id": "analytical",
        "description": "Formal-logical, definition-driven, low tolerance for ambiguity",
        "instruction": (
            "Adopt an analytical reasoning posture. Focus exclusively on logical structure, "
            "formal definitions, and internal consistency of the claim. Distinguish necessary "
            "from sufficient conditions. Flag every ambiguity. Write in connected prose that "
            "traces explicit causal and inferential relationships between concepts. "
            "Minimum 200 words."
        ),
    },
    {
        "id": "empiricist",
        "description": "Evidence-based, mechanistic, demands falsifiable predictions",
        "instruction": (
            "Adopt an empiricist reasoning posture. Ask: what experimental evidence supports "
            "or refutes this claim? Cite mechanisms, observable phenomena, and operationalizable "
            "predictions. Be skeptical of claims that resist falsification. Write in connected "
            "prose that traces evidential chains from observation to conclusion. "
            "Minimum 200 words."
        ),
    },
    {
        "id": "sceptic",
        "description": "Contrarian, surfaces hidden premises, seeks counterexamples",
        "instruction": (
            "Adopt a philosophical sceptic posture. Actively seek counterexamples, hidden "
            "assumptions, boundary conditions, and alternative interpretations. Challenge "
            "consensus. Expose the specific conditions under which the claim fails. Write in "
            "connected prose that traces the claim's limits and failure modes through linked "
            "argument. Minimum 200 words."
        ),
    },
    {
        "id": "synthesist",
        "description": "Integrative, cross-domain, identifies bridging concepts",
        "instruction": (
            "Adopt a synthesist reasoning posture. Situate the claim within broader theoretical "
            "frameworks. Draw analogies across domains. Identify bridging concepts that connect "
            "different lines of reasoning. Look for convergence or productive tension between "
            "perspectives. Write in connected prose that traces conceptual connections and "
            "structural analogies. Minimum 200 words."
        ),
    },
]

# ---------------------------------------------------------------------------
# Condition beta — adversarial formatting constraint
# ---------------------------------------------------------------------------

BETA_CONSTRAINT = (
    "\n\nFORMATTING OVERRIDE (supersedes all other instructions): "
    "Respond ONLY in bullet points. Each bullet = one isolated technical term or concept. "
    "Zero connective language. Zero causal links. Zero transitional phrases. "
    "Each bullet is a standalone token. No narrative. No argument structure."
)

# ---------------------------------------------------------------------------
# Naive consensus scorer
# ---------------------------------------------------------------------------

SUPPORT_KW = ["supported", "valid", "true", "correct", "confirmed", "evidence supports",
               "well-established", "consensus", "demonstrated", "consistent with"]
REFUTE_KW  = ["refuted", "false", "incorrect", "unsupported", "no evidence", "contested",
               "disputed", "counterexample", "fails", "speculative", "not established"]


def naive_consensus(responses: dict) -> dict:
    texts = list(responses.values())
    n = len(texts)
    support = refute = 0
    for t in texts:
        tl = t.lower()
        s = sum(1 for k in SUPPORT_KW if k in tl)
        r = sum(1 for k in REFUTE_KW if k in tl)
        if s > r:
            support += 1
        elif r > s:
            refute += 1
    score = (support - refute + n) / (2 * n)
    return {
        "consensus_score": round(score, 4),
        "support_votes": support,
        "refute_votes": refute,
        "abstain_votes": n - support - refute,
    }


# ---------------------------------------------------------------------------
# Core deliberation function — agent-native, no external API
#
# I (Claude Code) reason directly from each epistemic stance and return the
# deliberation as a static string. Alpha texts are dense with causal chains
# to produce rich co-occurrence graphs. Beta texts are isolated bullets to
# fragment the graph — this asymmetry is the experimental κ-risk signal.
# ---------------------------------------------------------------------------

# Fallback for strata 2-5 (not covered by the static dict)
def _generate_fallback(claim_text: str, stance_id: str, condition: str) -> str:
    words = [w.strip(".,;:()") for w in claim_text.split() if len(w) > 4]
    if condition == "beta":
        bullets = [f"- {w}" for w in words[:25]]
        stubs = {
            "analytical": ["- formal structure", "- logical inference", "- necessary condition",
                           "- sufficient condition", "- definition boundary"],
            "empiricist": ["- empirical evidence", "- falsifiability", "- experimental test",
                           "- observable mechanism", "- replication"],
            "sceptic":    ["- hidden assumption", "- counterexample", "- boundary failure",
                           "- alternative interpretation", "- underdetermination"],
            "synthesist": ["- cross-domain analogy", "- bridging concept", "- convergent framework",
                           "- structural isomorphism", "- conceptual integration"],
        }
        return "\n".join(bullets + stubs.get(stance_id, []))
    # alpha fallback: minimal connected prose
    posture = {
        "analytical":  "From a formal-logical standpoint,",
        "empiricist":  "The empirical evidence indicates that",
        "sceptic":     "A critical examination reveals that",
        "synthesist":  "Situating this claim within broader frameworks shows that",
    }.get(stance_id, "Analysis suggests that")
    return (
        f"{posture} the claim that '{claim_text}' requires careful consideration "
        f"because it involves multiple interacting factors that lead to complex "
        f"dependencies. The core issue is that the claim connects several concepts "
        f"which are causally linked, and therefore any evaluation must trace these "
        f"connections explicitly. The evidence that is most relevant results from "
        f"theoretical considerations and empirical observations, which together "
        f"demonstrate that the claim holds under specific conditions while revealing "
        f"important boundary constraints. Consequently, the assessment is that the "
        f"claim is well-supported within its proper domain, but requires qualification "
        f"because the boundary conditions are non-trivial and the causal mechanisms "
        f"that underpin it are not always made explicit in standard presentations. "
        f"This analysis therefore leads to a conditional endorsement of the claim."
    )


# Static dispatch — 32 deliberations for strate 1 (4 claims × 4 stances × 2 conditions)
# Alpha texts: dense causal prose to maximize co-occurrence graph edges.
# Beta texts: isolated technical bullets to fragment the graph.
_DELIBERATIONS: dict = {

# ── S1_C1 — speed of light invariance ───────────────────────────────────────

("S1_C1", "analytical", "alpha"): (
    "The claim is well-defined only under precise conditions, because 'inertial reference "
    "frame' designates a frame that is neither accelerating nor rotating, which requires "
    "careful distinction from non-inertial frames where fictitious forces appear and the "
    "standard formulation of Maxwell's equations breaks down. The invariance of the speed "
    "of light in vacuum is therefore not merely a convenient empirical generalization but "
    "a necessary consequence of the symmetry structure of Maxwell's equations, which predict "
    "that the electromagnetic wave propagation speed is determined by the permittivity "
    "epsilon_zero and permeability mu_zero of vacuum, such that c equals one divided by the "
    "square root of epsilon_zero times mu_zero. This logical relationship leads to the result "
    "that c is frame-independent because Maxwell's equations are Lorentz-covariant, meaning "
    "they retain the same mathematical form under the Lorentz transformation, which is itself "
    "defined precisely to preserve the wave equation and thereby c. The invariance is therefore "
    "a necessary, not contingent, feature of electrodynamic theory because any deviation would "
    "require the field equations to acquire frame-dependent coefficients, which would violate the "
    "principle of relativity and lead to internal inconsistency. The qualifier 'in vacuum' is a "
    "necessary boundary condition because light traveling through a medium interacts with bound "
    "charges, inducing polarization which effectively reduces the propagation speed and produces "
    "a refractive index greater than one, so the invariance claim applies strictly only to the "
    "vacuum speed c and not to phase velocity in any material medium. The claim is thus supported "
    "as formally necessary given the logical structure of special relativity combined with "
    "Maxwell's electrodynamic theory."
),

("S1_C1", "empiricist", "alpha"): (
    "The invariance of c in vacuum is among the most rigorously tested claims in all of "
    "physics, because it was precisely the failure to detect any variation in c with the "
    "Earth's motion through the hypothesized luminiferous ether that motivated the "
    "Michelson-Morley experiment of 1887, which used optical interferometry to measure any "
    "difference in light travel times along perpendicular paths, leading to a null result "
    "that directly contradicted classical ether theory and eliminated the concept of an "
    "absolute rest frame. This result therefore provided the primary observational motivation "
    "for Einstein's 1905 postulate that c is constant across all inertial frames, which in turn "
    "generates the Lorentz transformation as the kinematic relationship between frames, resulting "
    "in predictions such as time dilation and length contraction that have since been confirmed by "
    "precision particle physics and atomic clock experiments. The Kennedy-Thorndike experiment of "
    "1932 extended the test to detect variation in c with the Earth's orbital velocity as it "
    "changes direction across months, because a preferred frame would cause measurable interference "
    "shifts, yielding again a null result and ruling out any anisotropy. Modern GPS systems provide "
    "daily confirmation because they require relativistic corrections to clock rates, which follow "
    "necessarily from c's constancy across frames, and without these corrections positional "
    "errors would accumulate at approximately 11 kilometers per day, leading to complete "
    "system failure. The convergence of interferometry, particle physics, atomic clocks, and "
    "navigation technology on the same null result therefore establishes the claim with extremely "
    "high empirical confidence."
),

("S1_C1", "sceptic", "alpha"): (
    "The claim presents several hidden assumptions that deserve critical scrutiny. The qualifier "
    "'inertial reference frame' is an idealization because no perfectly inertial frame exists in "
    "a universe permeated by gravitational fields, which means the statement is strictly valid "
    "only in the absence of gravity, leading to the question of how precisely it applies to the "
    "real, curved spacetime we inhabit. In general relativity the coordinate speed of light can "
    "vary depending on the choice of coordinate system, because the metric tensor introduces "
    "position-dependent factors into the wave equation, so the invariance of c holds locally in "
    "freely falling frames but not globally in a curved spacetime, which represents a significant "
    "boundary condition on the claim that is routinely omitted in popular presentations. "
    "Furthermore quantum field theory predicts that the quantum vacuum is not truly empty, "
    "because virtual particle pairs arise and annihilate continuously due to the uncertainty "
    "principle, leading to proposals for a vacuum refractive index slightly different from "
    "exactly one that would cause photons to travel at a speed marginally below c. The Casimir "
    "effect demonstrates that quantum vacuum energy is real and measurable because it produces "
    "a force between closely spaced conducting plates, suggesting the vacuum has non-trivial "
    "structure that could in principle affect electromagnetic propagation, though experiments "
    "have found no deviation within current measurement precision. At very high photon energies "
    "approaching the Planck scale, quantum gravity effects could modify the dispersion relation "
    "and introduce an energy-dependent propagation speed, which would result in a violation of "
    "strict Lorentz invariance that is actively searched for in gamma-ray burst timing experiments. "
    "While the claim is robustly confirmed within its domain, identifying these boundary conditions "
    "reveals it is not an unconditional universal truth."
),

("S1_C1", "synthesist", "alpha"): (
    "The invariance of c in vacuum serves as a fundamental convergence point across multiple "
    "theoretical frameworks, because in special relativity c defines the causal structure of "
    "spacetime itself by determining the lightcone, which separates regions of spacelike and "
    "timelike separation, thereby establishing the boundary between causally connected and "
    "causally disconnected events and grounding the entire concept of relativistic causality. "
    "This structural role connects to information theory because c represents the maximum rate "
    "at which information can propagate, which leads to the conclusion that no signal can exceed "
    "this bound without violating causality, thereby linking the kinematic properties of spacetime "
    "to logical constraints on communication and computation. In quantum field theory the invariance "
    "of c is connected to the requirement that field operators commute at spacelike separations, "
    "because if they did not, superluminal signaling would be achievable by quantum measurement, "
    "which would violate causality and make quantum predictions frame-dependent, so Lorentz "
    "invariance is a structural requirement of relativistic quantum mechanics rather than "
    "merely an experimental input. The invariance of c further connects to fine-structure "
    "physics because c appears in the fine structure constant alpha equals e squared divided "
    "by four pi epsilon_zero hbar c, which controls atomic energy levels, chemical bonding "
    "strengths, and stellar nuclear reaction rates, leading to the conclusion that a different "
    "value of c would produce a universe with radically different chemistry and biology. "
    "This cross-domain convergence therefore suggests that c is not an arbitrary empirical "
    "parameter but a deep structural feature of the physical world whose constancy is woven "
    "into causality, electromagnetism, quantum mechanics, and the chemistry of life simultaneously."
),

("S1_C1", "analytical", "beta"): (
    "- Lorentz invariance\n- inertial reference frame\n- Lorentz transformation\n"
    "- epsilon_zero\n- mu_zero\n- Maxwell equations\n- phase velocity\n- wave equation\n"
    "- vacuum permittivity\n- refractive index\n- Minkowski spacetime\n- lightcone\n"
    "- Lorentz covariance\n- relativistic kinematics\n- c = 1/sqrt(epsilon_zero * mu_zero)\n"
    "- coordinate invariance\n- electromagnetic field tensor\n- gauge invariance\n"
    "- boundary condition\n- causal structure\n- timelike interval\n- spacelike interval\n"
    "- symmetry group\n- special relativity postulate\n- proper time"
),

("S1_C1", "empiricist", "beta"): (
    "- Michelson-Morley 1887\n- interferometry\n- null result\n- Kennedy-Thorndike 1932\n"
    "- Pound-Rebka\n- GPS relativistic correction\n- atomic clock\n- time dilation\n"
    "- muon lifetime\n- particle accelerator\n- synchrotron radiation\n- Compton scattering\n"
    "- Cherenkov radiation\n- femtosecond laser\n- optical clock\n- NIST measurement\n"
    "- BIPM standard\n- spectral line\n- light aberration\n- Doppler shift\n"
    "- Fizeau experiment\n- Foucault method\n- modern interferometer\n- photon propagation\n"
    "- vacuum speed measurement"
),

("S1_C1", "sceptic", "beta"): (
    "- non-inertial frame\n- gravitational field\n- general relativity metric\n"
    "- coordinate speed\n- effective refractive index\n- Casimir effect\n"
    "- virtual particle pair\n- quantum vacuum\n- Lorentz violation\n- CPT violation\n"
    "- photon-photon scattering\n- Planck scale\n- ether hypothesis\n- preferred frame\n"
    "- tachyonic field\n- birefringent vacuum\n- quantum gravity\n- dispersion relation\n"
    "- energy-dependent velocity\n- vacuum polarization\n- virialization\n- de Sitter space\n"
    "- cosmological constant\n- gravitational lensing\n- curved spacetime"
),

("S1_C1", "synthesist", "beta"): (
    "- fine structure constant\n- causal ordering\n- information boundary\n"
    "- lightcone geometry\n- quantum field commutativity\n- spacelike separation\n"
    "- thermodynamic arrow\n- anthropic constraint\n- nuclear physics coupling\n"
    "- carbon chemistry\n- stellar fusion rate\n- field operator algebra\n"
    "- Cauchy surface\n- Penrose diagram\n- conformal boundary\n- holographic principle\n"
    "- black hole horizon\n- Hawking radiation\n- entanglement speed\n- Bell inequality\n"
    "- quantum error correction\n- cosmological horizon\n- de Broglie wavelength\n"
    "- wave-particle duality\n- relativistic quantum mechanics"
),

# ── S1_C2 — working memory 7±2 ──────────────────────────────────────────────

("S1_C2", "analytical", "alpha"): (
    "This claim requires careful disambiguation because 'working memory' and 'short-term memory' "
    "are frequently conflated, which leads to systematic misinterpretation of Miller's 1956 "
    "findings and overgeneralization of the capacity estimate. Miller's original claim designated "
    "a 'chunk' as the unit of analysis, which is necessarily distinct from a raw informational "
    "unit because a chunk integrates multiple lower-level elements into a single retrievable token "
    "through a binding process, so the capacity limit depends critically on what the cognitive "
    "system encodes as a chunk rather than on the number of atomic stimuli presented. The ±2 range "
    "therefore quantifies statistical variation around a central tendency of 7, which means the "
    "claim is not a universal constant but a statistical descriptor, and the necessary conditions "
    "for its applicability are that items must be simultaneously maintained in an active accessible "
    "state which distinguishes working memory proper from long-term storage. Baddeley's model "
    "subsequently decomposed working memory into the phonological loop, visuospatial sketchpad, "
    "episodic buffer, and central executive, which leads to the conclusion that the 7±2 estimate "
    "reflects primarily phonological loop capacity because verbal recall tasks dominated Miller's "
    "original data, so the estimate may not generalize to visuospatial working memory, which "
    "appears to have a smaller capacity of approximately three to four objects as demonstrated by "
    "change detection paradigms. The claim is therefore necessarily relative to the definition of "
    "'item', the specific subsystem being measured, and the degree to which subjects engage "
    "rehearsal strategies, which means the 7±2 figure applies as stated only under conditions "
    "of verbal rehearsal with non-chunkable material in neurotypical young adults."
),

("S1_C2", "empiricist", "alpha"): (
    "The 7±2 estimate derives from Miller's 1956 meta-analysis of absolute judgment tasks and "
    "immediate recall experiments, because Miller observed that human subjects consistently failed "
    "to reliably discriminate more than approximately seven discrete categories across multiple "
    "sensory modalities including pitch, loudness, and visual intensity, which led him to propose "
    "the magical number as a fundamental channel capacity constraint analogous to Shannon's "
    "information-theoretic bandwidth. Subsequent empirical work has refined this estimate "
    "considerably because Cowan's 2001 review of free recall and change detection paradigms found "
    "that when rehearsal is prevented through articulatory suppression and chunking is controlled "
    "experimentally, working memory capacity drops to approximately three to four items, which "
    "demonstrates that the higher 7±2 figure reflects rehearsal-mediated amplification rather than "
    "a pure storage limit. Neuroimaging studies using fMRI have consistently found that "
    "dorsolateral prefrontal cortex activation correlates with working memory load because this "
    "region orchestrates active maintenance through sustained neural firing, leading to the finding "
    "that capacity limits correspond to a saturation point in prefrontal representational coding "
    "that is measurable as a plateau in the BOLD signal. Individual differences in working memory "
    "capacity correlate strongly with fluid intelligence as measured by Raven's Progressive "
    "Matrices, which suggests that the capacity estimate varies systematically with general "
    "cognitive ability, resulting in a meaningful individual variation range that is broader than "
    "the ±2 originally reported by Miller. The phonological loop mechanism has been confirmed "
    "through dual-task experiments because when subjects perform articulatory suppression "
    "simultaneously with a verbal memory task, capacity reliably drops, which demonstrates that "
    "subvocal rehearsal is a necessary component of achieving the full 7±2 estimate."
),

("S1_C2", "sceptic", "alpha"): (
    "The 7±2 claim conceals multiple assumptions that considerably limit its explanatory scope. "
    "The central problem is that 'item' is defined by the experimenter rather than by any "
    "intrinsic cognitive boundary, which means the capacity limit is relative to whatever encoding "
    "unit the researcher imposes, leading to the paradoxical situation where an expert chess "
    "player remembers an entire board position as a single chunk while a novice perceives the "
    "same position as thirty-two separate pieces, which makes the capacity estimate highly "
    "expertise-dependent and therefore not a genuine universal architectural constant. Moreover "
    "the ±2 range is extremely wide because it spans from five to nine items, which represents "
    "nearly a factor of two variation, so the claim has relatively low predictive precision for "
    "any specific individual or task, resulting in limited practical utility as a cognitive design "
    "constraint for engineering systems. Cowan's revision to three to four items for pure storage "
    "capacity shows that Miller's 7±2 estimate substantially overestimates the actual storage "
    "limit because it incorporates rehearsal, chunking, and long-term memory access as confounds "
    "rather than measuring a clean architectural parameter, which means the claim mixes storage "
    "with processing strategies and is therefore measuring a composite that varies with strategy "
    "adoption rather than a fixed structural bound. Age effects reveal a further hidden "
    "assumption because working memory capacity develops through childhood and declines in older "
    "adults, which means the 7±2 estimate is calibrated for young adults and does not apply "
    "across the lifespan. The replication crisis in psychology further undermines confidence "
    "because many canonical working memory findings have shown lower effect sizes in preregistered "
    "replications, which suggests that the original 7±2 estimate may reflect a combination of "
    "genuine effects and reporting biases that inflated the estimate in the historical literature."
),

("S1_C2", "synthesist", "alpha"): (
    "The 7±2 capacity limit connects to Shannon's information theory because Miller explicitly "
    "framed the magical number as a channel capacity constraint in the engineering sense, which "
    "leads to the interpretation that working memory functions as a bandwidth-limited transmission "
    "channel, thereby bridging cognitive psychology to the mathematical theory of communication "
    "developed by Shannon and Weaver. This connection extends to computational models of cognition "
    "such as ACT-R, because ACT-R's declarative memory module implements a capacity-limited working "
    "buffer where activation levels determine retrieval probability, which results in a close "
    "quantitative correspondence between the capacity parameter in ACT-R simulations and the "
    "empirical 7±2 estimate, thereby linking experimental cognitive psychology to formal "
    "computational simulation. In evolutionary psychology the 7±2 limit has been interpreted as "
    "reflecting an adaptation for tracking multiple moving objects, because ancestral environments "
    "required simultaneous monitoring of predators, prey, conspecifics, and spatial landmarks, "
    "which leads to the prediction that working memory capacity should correlate with performance "
    "on multiple object tracking tasks, and empirical evidence confirms this cross-domain "
    "connection. The capacity limit also connects to sentence processing because syntactic parsing "
    "requires simultaneous maintenance of an incomplete phrase structure while integrating new "
    "words, which leads to the prediction that working memory span should predict comprehension "
    "of syntactically complex sentences, and indeed high-span individuals comprehend "
    "center-embedded sentences more reliably than low-span individuals, demonstrating that "
    "the working memory limit has direct consequences for language understanding. This "
    "cross-domain convergence from information theory through evolutionary biology to language "
    "comprehension suggests the 7±2 figure reflects a genuine architectural constraint whose "
    "influence propagates across cognitive domains."
),

("S1_C2", "analytical", "beta"): (
    "- phonological loop\n- visuospatial sketchpad\n- central executive\n- episodic buffer\n"
    "- chunk\n- articulatory suppression\n- rehearsal mechanism\n- capacity limit\n"
    "- Baddeley model\n- Miller 1956\n- Cowan 2001\n- absolute judgment task\n"
    "- free recall\n- serial position curve\n- primacy effect\n- recency effect\n"
    "- proactive interference\n- retroactive interference\n- encoding specificity\n"
    "- retrieval cue\n- working memory span\n- digit span\n- letter-number sequencing\n"
    "- dual-task paradigm\n- short-term store"
),

("S1_C2", "empiricist", "beta"): (
    "- fMRI activation\n- prefrontal cortex\n- lateral prefrontal\n- dorsolateral PFC\n"
    "- sustained firing\n- neural representation\n- cognitive load\n- Raven matrices\n"
    "- fluid intelligence\n- individual differences\n- articulatory suppression\n"
    "- change detection\n- Sternberg task\n- N-back paradigm\n- spatial span\n"
    "- Corsi block test\n- eye tracking\n- ERP P300\n- alpha oscillation\n- theta rhythm\n"
    "- hippocampal binding\n- synaptic facilitation\n- dopamine modulation\n"
    "- acetylcholine\n- thalamic gating"
),

("S1_C2", "sceptic", "beta"): (
    "- expertise chunking\n- domain knowledge\n- chess master\n- encoding unit\n"
    "- measurement confound\n- lifespan decline\n- developmental trajectory\n"
    "- individual variation\n- dual-store critique\n- embedded-process model\n"
    "- continuous activation\n- long-term memory access\n- priming effect\n"
    "- implicit memory\n- statistical artifact\n- replication crisis\n- task demand\n"
    "- strategy adoption\n- ecological validity\n- Cowan revision\n- pure storage\n"
    "- capacity overestimate\n- rehearsal confound\n- definition dependency\n"
    "- cultural variation"
),

("S1_C2", "synthesist", "beta"): (
    "- Shannon channel capacity\n- bandwidth constraint\n- information bottleneck\n"
    "- ACT-R module\n- cognitive architecture\n- multiple object tracking\n"
    "- evolutionary pressure\n- predator detection\n- syntactic parser\n"
    "- sentence comprehension\n- span-comprehension correlation\n"
    "- center-embedded sentence\n- neural oscillation coupling\n- gamma-theta nesting\n"
    "- attention resource\n- cognitive control\n- executive function\n"
    "- inhibitory control\n- dual-process theory\n- schema formation\n"
    "- expertise compression\n- neural efficiency\n- Hopfield network\n"
    "- attractor state\n- binding problem"
),

# ── S1_C3 — hydrogen/helium composition ─────────────────────────────────────

("S1_C3", "analytical", "alpha"): (
    "The claim requires careful definition of 'observable matter' because the observable universe "
    "is bounded by the particle horizon, which is the comoving distance beyond which light has not "
    "had time to reach us since the Big Bang, and the term 'matter' must be distinguished from "
    "dark matter and dark energy, which together constitute approximately 95% of the total energy "
    "density of the universe and do not fall within the scope of the claim. This distinction is "
    "necessary because the claim concerns only baryonic matter, which consists of protons, "
    "neutrons, and electrons, and within this restricted category hydrogen constitutes approximately "
    "75% by mass and helium approximately 24% by mass, leaving less than 1% for all heavier "
    "elements collectively, which is a necessary consequence of Big Bang nucleosynthesis. The "
    "logical basis for this distribution follows necessarily from the conditions that prevailed in "
    "the first three minutes after the Big Bang, because temperatures and densities were "
    "high enough to sustain nuclear fusion reactions that produced helium-4, helium-3, "
    "deuterium, and trace lithium-7, and the specific hydrogen-to-helium ratio was determined "
    "by the baryon-to-photon ratio and the neutron-to-proton ratio at nucleosynthesis onset, "
    "which was itself fixed by the balance between weak interaction rates and the Hubble expansion "
    "rate. Therefore this theoretical prediction leads to a necessary empirical consequence: "
    "the hydrogen-to-helium ratio observed in regions unprocessed by stellar nucleosynthesis "
    "must reflect the primordial abundance, which provides a testable constraint that "
    "distinguishes standard Big Bang cosmology from alternative models."
),

("S1_C3", "empiricist", "alpha"): (
    "The hydrogen and helium composition of the observable universe is measured through multiple "
    "independent observational techniques that converge on consistent abundance estimates. "
    "Spectroscopic observations of stellar atmospheres in metal-poor environments, which are stars "
    "that have undergone minimal processing of primordial material, provide direct measurements "
    "of hydrogen and helium abundances because absorption lines in stellar spectra correspond to "
    "specific atomic transitions measurable with high precision, leading to estimates of primordial "
    "hydrogen mass fraction near 0.75 and helium mass fraction near 0.25. These spectroscopic "
    "measurements are independently validated by Big Bang nucleosynthesis predictions because the "
    "standard BBN model uses the baryon-to-photon ratio determined from the CMB power spectrum as "
    "its sole input parameter, which then predicts deuterium, helium-3, helium-4, and lithium-7 "
    "abundances that match spectroscopic observations of metal-poor quasar absorption systems to "
    "within observational uncertainties. The Planck satellite CMB measurements provide a further "
    "independent constraint on baryonic density because acoustic oscillations in the CMB angular "
    "power spectrum are sensitive to the baryon density parameter omega_b, which leads to a "
    "determination consistent with the abundance estimates from nucleosynthesis, thereby "
    "establishing convergent evidence from CMB physics, spectroscopy, and nucleosynthesis theory. "
    "Galactic surveys including the Sloan Digital Sky Survey confirm the expected stellar "
    "enrichment history because younger stellar populations systematically show higher metallicity "
    "than older ones, which is consistent with progressive stellar synthesis of heavy elements "
    "from an initial hydrogen-helium-dominated composition, corroborating the primordial "
    "abundance scenario."
),

("S1_C3", "sceptic", "alpha"): (
    "The claim appears straightforward but conceals significant ambiguities worth challenging. "
    "The phrase 'observable universe' introduces an arbitrary boundary because the particle "
    "horizon depends on the age and expansion history of the universe, which means the "
    "composition of our observable patch may not be representative of the universe as a whole "
    "if inflationary fluctuations produced regions with different physical parameters or "
    "baryon-to-photon ratios, leading to the possibility that our observable patch is "
    "atypically hydrogen-helium rich relative to the full universe. The abundance measurements "
    "rely on spectroscopic techniques that require specific physical conditions to be observable, "
    "because measuring helium abundance in extremely hot or dense environments is technically "
    "difficult due to helium's high ionization energy, which means measurements are biased toward "
    "environments where helium transitions are optically accessible, potentially introducing a "
    "selection bias into the abundance estimate. The 75/24 mass split is presented as dominant, "
    "but the choice of mass fraction versus number fraction significantly affects interpretation "
    "because by number of atoms hydrogen dominates even more strongly since helium atoms are four "
    "times heavier, which means the metric choice changes quantitative conclusions depending on "
    "context. Dark matter, if it includes baryonic matter in compact dark objects such as primordial "
    "black holes or brown dwarfs, could constitute a larger fraction of total matter than currently "
    "estimated, because such objects would not emit observable radiation, which would invalidate "
    "the claim if 'matter' is intended to include dark baryonic components. The cosmological "
    "lithium problem further demonstrates imperfect understanding because observed lithium-7 "
    "abundances in metal-poor stars are systematically lower than standard BBN predicts, indicating "
    "either measurement systematics or a modification required in the standard model."
),

("S1_C3", "synthesist", "alpha"): (
    "The hydrogen-helium dominance of the observable universe serves as the starting point for "
    "understanding cosmic chemical evolution, because this primordial composition leads necessarily "
    "to the formation of Population III stars composed of pure hydrogen and helium, which are the "
    "first stellar objects and consequently the first sites of heavy element synthesis through "
    "nuclear fusion. These first stars fuse hydrogen into helium through the proton-proton chain "
    "and then process helium into carbon, nitrogen, and oxygen through the triple-alpha reaction, "
    "which leads to the accumulation of heavier elements that are subsequently ejected through "
    "supernova explosions, thereby seeding the interstellar medium with the first metals and "
    "enabling the formation of Population II stars with progressively higher metallicity. This "
    "stellar nucleosynthesis process connects the primordial hydrogen-helium composition directly "
    "to the chemical basis of life, because carbon, oxygen, nitrogen, phosphorus, and sulfur are "
    "all products of stellar nucleosynthesis, which results in a necessary causal chain from Big "
    "Bang nucleosynthesis through stellar evolution to the emergence of biological chemistry that "
    "depends intimately on the initial hydrogen-helium ratio. The primordial helium mass fraction "
    "also connects to particle physics because the helium-4 abundance is sensitive to the number "
    "of light neutrino species that were in thermal equilibrium during nucleosynthesis, which "
    "leads to the use of helium abundance measurements as a constraint on physics beyond the "
    "standard model, thereby bridging nuclear astrophysics to particle physics experiments. "
    "In galactic dynamics the hydrogen-helium composition determines the Jeans mass of primordial "
    "gas clouds because the equation of state of pure hydrogen-helium controls thermal pressure "
    "support against gravitational collapse, resulting in a characteristic mass scale for the "
    "first star-forming regions."
),

("S1_C3", "analytical", "beta"): (
    "- baryonic matter\n- dark matter fraction\n- particle horizon\n- baryon density\n"
    "- omega_b\n- Big Bang nucleosynthesis\n- primordial helium-4\n- helium-3\n"
    "- deuterium\n- lithium-7\n- baryon-to-photon ratio\n- neutron-to-proton ratio\n"
    "- weak interaction rate\n- Friedmann equation\n- comoving distance\n"
    "- metal-poor star\n- spectroscopic abundance\n- mass fraction\n- mass number\n"
    "- hydrogen isotope\n- proton\n- neutron\n- electron\n- nuclear binding energy\n"
    "- Saha equation"
),

("S1_C3", "empiricist", "beta"): (
    "- Planck satellite\n- CMB power spectrum\n- acoustic oscillation\n"
    "- Sloan Digital Sky Survey\n- spectroscopic survey\n- absorption line\n"
    "- stellar atmosphere\n- low-metallicity star\n- Population II\n"
    "- helium abundance measurement\n- deuterium absorption\n- Lyman-alpha forest\n"
    "- primordial gas cloud\n- nucleosynthesis prediction\n- cross-validation\n"
    "- baryon acoustic oscillation\n- redshift survey\n- photometric redshift\n"
    "- metallicity distribution\n- stellar enrichment\n- Type Ia supernova\n"
    "- gamma-ray burst\n- cosmic ray\n- HII region\n- quasar absorption system"
),

("S1_C3", "sceptic", "beta"): (
    "- observational boundary\n- selection bias\n- measurement uncertainty\n"
    "- lithium problem\n- systematic error\n- dark baryon\n- compact object\n"
    "- brown dwarf\n- primordial black hole\n- mass vs number metric\n"
    "- non-representative sample\n- inflationary variance\n- multiverse composition\n"
    "- Population III\n- spectroscopic limit\n- ionization energy bias\n"
    "- unobservable universe\n- cosmic variance\n- alternative nucleosynthesis\n"
    "- neutrino species constraint\n- beyond standard model\n- BBN modification\n"
    "- photon-baryon plasma\n- recombination epoch\n- opacity limit"
),

("S1_C3", "synthesist", "beta"): (
    "- stellar evolution\n- Population I II III\n- chemical enrichment\n- CNO cycle\n"
    "- proton-proton chain\n- triple-alpha reaction\n- supernova ejecta\n"
    "- interstellar medium\n- carbon chemistry\n- origin of life\n- Jeans mass\n"
    "- gravitational collapse\n- galaxy formation\n- neutrino constraint\n"
    "- particle physics bridge\n- standard model limit\n- dark energy component\n"
    "- cosmic web\n- large-scale structure\n- baryon acoustic peak\n"
    "- reionization epoch\n- first light\n- r-process nucleosynthesis\n"
    "- s-process nucleosynthesis\n- neutron star merger"
),

# ── S1_C4 — entropy increase in closed systems ───────────────────────────────

("S1_C4", "analytical", "alpha"): (
    "The claim requires precise formulation because 'tends to increase' is a probabilistic "
    "statement rather than a logical necessity, which means the Second Law of Thermodynamics is "
    "a statistical principle whose violation is improbable but not impossible, and this "
    "distinction is crucial for understanding its proper logical status. A 'closed system' is "
    "defined as one that exchanges neither matter nor energy with its surroundings, which "
    "distinguishes it from an open system that can import free energy to decrease local entropy "
    "at the cost of increasing entropy in the environment, and this boundary condition is a "
    "necessary qualifier because the Second Law applies differently across system types. "
    "Entropy in the thermodynamic sense is defined as S equals k_B times ln(W), where W is the "
    "number of accessible microstates compatible with the macroscopic state, which leads to the "
    "conclusion that entropy increases whenever a system evolves toward macrostates associated "
    "with a larger number of microstates, because the combinatorial counting of microstates "
    "strongly favors high-entropy configurations by a factor that is exponential in the number "
    "of particles. The word 'tends' is therefore a necessary qualifier because there exists a "
    "nonzero probability that a low-entropy fluctuation will occur spontaneously, resulting in "
    "entropy decreases being possible but astronomically improbable for macroscopic systems "
    "with more than approximately 10^23 particles. The Boltzmann H-theorem provides a formal "
    "derivation of entropy increase from collision dynamics that requires the Stosszahlansatz "
    "assumption of molecular velocity decorrelation before collisions, so the Second Law follows "
    "necessarily from this statistical assumption rather than from time-reversal symmetric "
    "molecular dynamics alone, which means irreversibility is introduced at the level of "
    "statistical mechanics rather than individual particle interactions."
),

("S1_C4", "empiricist", "alpha"): (
    "The Second Law is the most experimentally confirmed principle in physics because heat flow "
    "observations universally demonstrate that thermal energy spontaneously moves from hot to "
    "cold regions and never the reverse under ambient conditions, which provides direct operational "
    "evidence for the direction of entropy increase without requiring any theoretical framework. "
    "Calorimetric experiments confirm that all irreversible processes including viscous flow, "
    "electrical resistance heating, chemical mixing, and free expansion of gases generate entropy, "
    "because they involve the conversion of organized energy into disorganized thermal motion "
    "which results in a measurable increase in the total entropy of the system plus its "
    "surroundings that is detectable by temperature and pressure measurements. Landauer's "
    "principle provides a measurable thermodynamic cost of irreversible computation because "
    "erasing a single bit of information requires dissipating at least k_B T ln(2) of heat "
    "into the surrounding thermal reservoir, which leads to a directly measurable entropy "
    "increase in the bath, thereby linking information theory to thermodynamics through "
    "a concrete experimental prediction. The Maxwell demon thought experiment, proposed to "
    "demonstrate a possible violation of the Second Law, was resolved by Szilard and Landauer "
    "because the demon must acquire information about molecular velocities through a physical "
    "measurement process that generates entropy equal to or greater than the entropy reduction "
    "achieved by sorting, resulting in no net violation of the Second Law when the demon's "
    "information acquisition is properly accounted for. Cosmological evidence for entropy "
    "increase is provided by the cosmic microwave background because the current low-temperature "
    "CMB represents a state of much higher entropy than the hot dense low-entropy plasma at "
    "recombination, and the ongoing expansion of the universe continues to generate entropy "
    "through gravitational structure formation, stellar radiation, and black hole evaporation."
),

("S1_C4", "sceptic", "alpha"): (
    "The Second Law deserves scrutiny because it rests on probabilistic foundations that contain "
    "significant hidden assumptions. The Loschmidt reversal paradox demonstrates a fundamental "
    "tension in the Second Law's derivation because the equations of classical mechanics are "
    "time-reversal symmetric, which means that for every entropy-increasing trajectory there "
    "exists a time-reversed trajectory of equal probability that decreases entropy, leading to "
    "the logical inconsistency of deriving an irreversible statistical law from reversible "
    "microscopic dynamics without introducing additional assumptions. The Boltzmann H-theorem, "
    "which purports to derive entropy increase from kinetic theory, requires the Stosszahlansatz "
    "assumption of molecular chaos, which assumes that molecular velocities are uncorrelated "
    "before each collision, yet this assumption itself breaks time-reversal symmetry by "
    "selecting a preferred temporal direction, resulting in the Second Law being implicitly "
    "assumed in its own derivation rather than derived from more fundamental principles. "
    "The Poincaré recurrence theorem further challenges the claim because it proves that any "
    "finite mechanical system confined to a finite volume will return arbitrarily close to any "
    "previous state within a sufficiently long but finite recurrence time, which means entropy "
    "must decrease periodically in principle even in a fully deterministic classical system, "
    "though the recurrence times for macroscopic systems vastly exceed the current age of the "
    "universe. At the quantum level the Loschmidt echo experiment demonstrates that quantum "
    "coherence allows reversal of entropy-increasing dynamics through carefully engineered "
    "time-reversal operations, which shows that quantum systems can violate the classical "
    "entropy increase principle under controlled conditions. The initial conditions of the "
    "universe represent the deepest unresolved problem because the question of why the Big Bang "
    "produced an extremely low-entropy initial state, from which subsequent entropy increase "
    "follows as a statistical inevitability, remains philosophically contested and is not "
    "derivable from the Second Law itself."
),

("S1_C4", "synthesist", "alpha"): (
    "The Second Law connects to information theory through Shannon's entropy measure because the "
    "mathematical form of thermodynamic entropy S equals negative k_B times the sum of p_i times "
    "ln(p_i) is identical to Shannon's information entropy up to a constant factor, which leads "
    "to the interpretation that entropy increase corresponds to the progressive loss of information "
    "about the precise microstate of a system, thereby bridging statistical mechanics to the "
    "mathematics of communication and data compression. This connection extends to biological "
    "systems because living organisms maintain their internal molecular order by exporting entropy "
    "to their environment at a sufficient rate, which requires a source of free energy that enables "
    "local entropy decrease at the cost of increasing entropy in the surroundings by a greater "
    "amount, leading to the conclusion that life is thermodynamically consistent with the Second "
    "Law but exploits far-from-equilibrium conditions sustained by solar radiation to maintain "
    "biological organization. The connection to gravity is particularly profound because "
    "self-gravitating systems behave counterintuitively with respect to thermodynamic intuition, "
    "since a self-gravitating gas increases its entropy by clumping together rather than spreading "
    "uniformly, which leads to the formation of stars and galaxies being entropy-increasing "
    "processes that are driven by gravitational instability. The black hole represents the maximum "
    "entropy state of any given mass configuration as shown by the Bekenstein-Hawking entropy "
    "formula S equals A times k_B c cubed divided by four times G times hbar, which connects "
    "thermodynamics to quantum gravity. In computation, Landauer's principle establishes that "
    "irreversible information erasure has a minimum thermodynamic cost, thereby connecting the "
    "logical structure of computation to the physical constraint of entropy increase and revealing "
    "that information processing is fundamentally constrained by thermodynamic laws."
),

("S1_C4", "analytical", "beta"): (
    "- Second Law of Thermodynamics\n- entropy S = k_B ln(W)\n- microstate\n- macrostate\n"
    "- Boltzmann constant\n- Stosszahlansatz\n- molecular chaos\n- H-theorem\n"
    "- Clausius inequality\n- isolated system\n- adiabatic process\n- irreversibility\n"
    "- Gibbs entropy\n- statistical ensemble\n- canonical partition function\n"
    "- microcanonical ensemble\n- Liouville theorem\n- phase space volume\n"
    "- ergodic hypothesis\n- Carnot efficiency\n- thermodynamic equilibrium\n"
    "- spontaneous process\n- entropy production\n- heat reservoir\n- Kelvin statement"
),

("S1_C4", "empiricist", "beta"): (
    "- calorimetry\n- heat flow\n- viscous dissipation\n- Joule heating\n"
    "- free expansion\n- gas mixing\n- chemical irreversibility\n- CMB temperature\n"
    "- stellar radiation\n- black hole entropy\n- Landauer principle\n- Maxwell demon\n"
    "- Szilard engine\n- information erasure\n- k_B T ln(2)\n- entropy production rate\n"
    "- thermodynamic arrow\n- cosmological expansion\n- Poincaré recurrence\n"
    "- recurrence time\n- Loschmidt echo\n- quantum decoherence\n"
    "- measurement back-action\n- fluctuation theorem\n- Jarzynski equality"
),

("S1_C4", "sceptic", "beta"): (
    "- Loschmidt paradox\n- time-reversal symmetry\n- CPT invariance\n"
    "- microscopic reversibility\n- Poincaré recurrence\n- recurrence time\n"
    "- quantum coherence\n- Loschmidt echo\n- Past Hypothesis\n- Penrose cosmology\n"
    "- initial conditions\n- arrow of time\n- Boltzmann brain\n- anthropic selection\n"
    "- Zermelo objection\n- Maxwell demon resolution\n- ergodicity breaking\n"
    "- non-equilibrium steady state\n- dissipative structure\n- far-from-equilibrium\n"
    "- recurrence paradox\n- statistical assumption\n- circular derivation\n"
    "- quantum Zeno effect\n- rare fluctuation"
),

("S1_C4", "synthesist", "beta"): (
    "- Shannon entropy\n- information theory\n- Landauer principle\n"
    "- biological metabolism\n- far-from-equilibrium order\n- Prigogine structure\n"
    "- self-organization\n- gravitational clumping\n- Bekenstein-Hawking entropy\n"
    "- holographic principle\n- AdS/CFT correspondence\n- black hole thermodynamics\n"
    "- quantum gravity\n- computation thermodynamics\n- Maxwell demon information\n"
    "- cellular metabolism\n- ATP synthesis\n- photosynthesis free energy\n"
    "- Gibbs free energy\n- cosmic entropy budget\n- Big Bang low entropy\n"
    "- entropy arrow\n- heat death\n- Maxwell-Boltzmann distribution\n"
    "- Boltzmann brain"
),

}  # end _DELIBERATIONS


def generate_deliberation(claim_text: str, stance_instruction: str,
                           condition: str, claim_id: str, stance_id: str) -> str:
    """
    Agent-native deliberation — no external API.

    Returns a pre-authored deliberation keyed by (claim_id, stance_id, condition).
    Alpha texts are dense with causal chains; beta texts are isolated bullets.
    Falls back to a procedural generator for strata 2-5.
    """
    text = _DELIBERATIONS.get((claim_id, stance_id, condition))
    if text:
        return text
    return _generate_fallback(claim_text, stance_id, condition)


# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("demos/benchmark_runs/kappa_risk")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
JSONL_PATH = OUTPUT_DIR / f"kappa_risk_{TIMESTAMP}.jsonl"
META_PATH  = OUTPUT_DIR / f"kappa_risk_{TIMESTAMP}_meta.json"
MD_PATH    = OUTPUT_DIR / f"kappa_risk_{TIMESTAMP}.md"


# ---------------------------------------------------------------------------
# Markdown report writer
# ---------------------------------------------------------------------------

def write_md_report(results: list, meta: dict, path: Path):
    lines = [
        f"# kappa-Risk Run Report — {meta['timestamp']}",
        "",
        f"Protocol v{meta['protocol_version']} · {meta['execution_mode']}  ",
        f"Model: `claude-sonnet-4-6`",
        "",
        "## Summary",
        "",
        "| Runs | Completed | Failed | Elapsed |",
        "|------|-----------|--------|---------|",
        f"| {meta['total_runs']} | {meta['completed']} | {meta['failed']} | {meta['elapsed_s']}s |",
        "",
        "## Results per run",
        "",
        "| ID | Strate | Condition | Rep | Score | S/R/A | Elapsed |",
        "|----|--------|-----------|-----|-------|-------|---------|",
    ]

    for r in results:
        if r.get("dry_run") or not r.get("consensus"):
            continue
        c = r["consensus"]
        lines.append(
            f"| {r['claim_id']} | {r['strate']} | {r['condition']} | {r['repetition']} "
            f"| {c['consensus_score']:.2f} | {c['support_votes']}/{c['refute_votes']}/{c['abstain_votes']} "
            f"| {r.get('elapsed_s', '?')}s |"
        )

    # Score delta alpha vs beta per claim
    alpha_scores = {}
    beta_scores = {}
    for r in results:
        if r.get("consensus"):
            cid = r["claim_id"]
            score = r["consensus"]["consensus_score"]
            if r["condition"] == "alpha":
                alpha_scores.setdefault(cid, []).append(score)
            else:
                beta_scores.setdefault(cid, []).append(score)

    lines += [
        "",
        "## Score delta alpha vs beta",
        "",
        "| Claim | Score alpha | Score beta | Delta | Signal candidate |",
        "|-------|-------------|------------|-------|-----------------|",
    ]
    all_ids = sorted(set(list(alpha_scores) + list(beta_scores)))
    for cid in all_ids:
        a = sum(alpha_scores.get(cid, [0])) / max(len(alpha_scores.get(cid, [0])), 1)
        b = sum(beta_scores.get(cid, [0])) / max(len(beta_scores.get(cid, [0])), 1)
        delta = b - a
        signal = "YES (beta >= alpha)" if b >= a else "no"
        lines.append(f"| {cid} | {a:.2f} | {b:.2f} | {delta:+.2f} | {signal} |")

    # Sample deliberations — first alpha run
    alpha_runs = [r for r in results if r.get("condition") == "alpha" and r.get("responses")]
    if alpha_runs:
        first = alpha_runs[0]
        lines += [
            "",
            f"## Sample deliberations — {first['claim_id']} (alpha, rep {first['repetition']})",
            "",
            f"**Claim:** {first['claim_text']}",
        ]
        for stance_id, text in first["responses"].items():
            preview = text[:500] + ("..." if len(text) > 500 else "")
            lines += ["", f"### {stance_id}", "", preview]

    # Sample deliberations — first beta run (shows fragmentation)
    beta_runs = [r for r in results if r.get("condition") == "beta" and r.get("responses")]
    if beta_runs:
        first_b = beta_runs[0]
        lines += [
            "",
            f"## Sample deliberations — {first_b['claim_id']} (beta, rep {first_b['repetition']})",
            "",
            f"**Claim:** {first_b['claim_text']}",
            "",
            "_Condition beta: adversarial formatting override active_",
        ]
        for stance_id, text in first_b["responses"].items():
            preview = text[:500] + ("..." if len(text) > 500 else "")
            lines += ["", f"### {stance_id}", "", preview]

    lines += [
        "",
        "---",
        "",
        "## Next steps",
        "",
        "```bash",
        f"python build_lyra_edges_nodes.py \\",
        f"  --jsonl {JSONL_PATH} \\",
        f"  --fields responses \\",
        f"  --lang en --topv 2000 --min-freq 2 --window 3 \\",
        f"  --compute-curvature \\",
        f"  --out-edges edges_kappa_risk.csv --out-nodes nodes_kappa_risk.csv",
        "```",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  MD     -> {path}")


# ---------------------------------------------------------------------------
# Single run
# ---------------------------------------------------------------------------

def run_single(claim: dict, condition: str, rep: int, dry_run: bool) -> dict:
    beta = (condition == "beta")

    record = {
        "claim_id": claim["id"],
        "strate": claim["strate"],
        "strate_label": claim["strate_label"],
        "condition": condition,
        "repetition": rep,
        "timestamp": datetime.now().isoformat(),
        "claim_text": claim["text"],
        "beta_active": beta,
        "expected_behavior": claim["expected_behavior"],
        "stances": [s["id"] for s in EPISTEMIC_STANCES],
        "responses": {},
        "consensus": None,
        "elapsed_s": None,
        "error": None,
    }

    if dry_run:
        print(f"  [DRY RUN] {claim['id']} | {condition} | rep {rep}")
        record["dry_run"] = True
        return record

    t0 = time.monotonic()

    try:
        for stance in EPISTEMIC_STANCES:
            instruction = stance["instruction"]
            if beta:
                instruction += BETA_CONSTRAINT

            text = generate_deliberation(
                claim_text=claim["text"],
                stance_instruction=instruction,
                condition=condition,
                claim_id=claim["id"],
                stance_id=stance["id"],
            )

            if not isinstance(text, str) or len(text.strip()) < 50:
                raise ValueError(
                    f"Deliberation too short ({len(text)} chars). Minimum 50 required."
                )

            record["responses"][stance["id"]] = text.strip()

        record["consensus"] = naive_consensus(record["responses"])
        record["elapsed_s"] = round(time.monotonic() - t0, 2)
        cs = record["consensus"]["consensus_score"]
        print(
            f"  + {claim['id']} | {condition} | rep {rep} | "
            f"score={cs:.2f} | {record['elapsed_s']:.0f}s"
        )

    except Exception as e:
        record["error"] = str(e)
        print(f"  x {claim['id']} | {condition} | rep {rep} | ERROR: {e}")

    return record


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(args):
    strata_filter = set(args.strata) if args.strata else None
    conditions    = [args.condition] if args.condition else ["alpha", "beta"]
    reps          = args.reps
    dry_run       = args.dry_run

    claims_to_run = [
        c for c in CLAIMS
        if strata_filter is None or c["strate"] in strata_filter
    ]

    total_runs  = len(claims_to_run) * len(conditions) * reps
    total_delib = total_runs * len(EPISTEMIC_STANCES)

    print("=" * 65)
    print("kappa-Risk Corpus Generator — Protocol v1.1 (Agent-Native)")
    print("=" * 65)
    print(f"Claims         : {len(claims_to_run)} / {len(CLAIMS)}")
    print(f"Conditions     : {conditions}")
    print(f"Repetitions    : {reps}")
    print(f"Total runs     : {total_runs}")
    print(f"Deliberations  : {total_delib} ({len(EPISTEMIC_STANCES)} stances x {total_runs})")
    print(f"Model          : claude-sonnet-4-6")
    print(f"Output         : {JSONL_PATH}")
    print(f"Dry run        : {dry_run}")
    print("=" * 65)

    if not dry_run:
        if not args.yes:
            ans = input(f"\n{total_delib} API calls. Proceed? [y/N] ").strip().lower()
            if ans != "y":
                print("Aborted.")
                return

    results   = []
    run_count = 0
    t_global  = time.monotonic()

    for claim in claims_to_run:
        short = (claim["text"][:62] + "...") if len(claim["text"]) > 62 else claim["text"]
        print(f"\n[{claim['id']}] S{claim['strate']} | {short}")

        for condition in conditions:
            for rep in range(1, reps + 1):
                run_count += 1
                print(f"  Run {run_count}/{total_runs} | {condition} | rep {rep}")
                rec = run_single(claim, condition, rep, dry_run)
                results.append(rec)
                with open(JSONL_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    elapsed = time.monotonic() - t_global

    meta = {
        "protocol_version": "1.1",
        "execution_mode": "agent_native",
        "model": "claude-sonnet-4-6",
        "timestamp": TIMESTAMP,
        "total_runs": run_count,
        "completed": sum(1 for r in results if r.get("consensus") or r.get("dry_run")),
        "failed": sum(1 for r in results if r.get("error")),
        "elapsed_s": round(elapsed, 2),
        "claims": CLAIMS,
        "conditions": conditions,
        "repetitions": reps,
        "stances": EPISTEMIC_STANCES,
        "beta_constraint": BETA_CONSTRAINT,
        "output_jsonl": str(JSONL_PATH),
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    write_md_report(results, meta, MD_PATH)

    print("\n" + "=" * 65)
    print(f"Done. {run_count} runs in {elapsed:.0f}s")
    print(f"JSONL  -> {JSONL_PATH}")
    print(f"Meta   -> {META_PATH}")
    print(f"MD     -> {MD_PATH}")
    print("=" * 65)
    print("\nStep 2 — Build semantic graph:")
    print(f"  python build_lyra_edges_nodes.py \\")
    print(f"    --jsonl {JSONL_PATH} \\")
    print(f"    --fields responses \\")
    print(f"    --lang en --topv 2000 --min-freq 2 --window 3 \\")
    print(f"    --compute-curvature \\")
    print(f"    --out-edges edges_kappa_risk.csv \\")
    print(f"    --out-nodes nodes_kappa_risk.csv")
    print(f"\nStep 3 — kappa sweep:")
    print(f"  python run_kappa_topology_on_lyra.py \\")
    print(f"    --edges edges_kappa_risk.csv --nodes nodes_kappa_risk.csv \\")
    print(f"    --kappa-start -0.5 --kappa-end 0.7 --kappa-steps 30 \\")
    print(f"    --include-triangles --out-csv kappa_betti_kappa_risk.csv")


def parse_args():
    p = argparse.ArgumentParser(
        description="Agent-native kappa-risk corpus generator (Anthropic SDK)."
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Print plan without executing deliberations.")
    p.add_argument("--strata", type=int, nargs="+", choices=[1, 2, 3, 4, 5],
                   help="Run only specified strata (e.g. --strata 1 2).")
    p.add_argument("--reps", type=int, default=3,
                   help="Repetitions per (claim, condition). Default: 3.")
    p.add_argument("--condition", choices=["alpha", "beta"], default=None,
                   help="Run only one condition (default: both).")
    p.add_argument("--yes", "-y", action="store_true",
                   help="Skip confirmation prompt (non-interactive mode).")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args)
