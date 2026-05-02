"""
RED tests for S1-001 + S1-002 — Enum épistémique V2 (HYBRIDE).

Current state (RED):
    - services/solana/bridge.py::EPISTEMIC_TYPE_MAP lacks "deterministic" and
      "verdict" keys -> attestation_to_anchor_args() raises KeyError on any
      attestation crystallized by _run_deterministic_pipeline() (ADR-012)
      or by the verify flywheel (ADR-014).
    - EPISTEMIC_TYPE_MAP maps security_audit -> 5, but programs/epp/src/lib.rs:61
      enforces require!(epistemic_type <= 4, ...) -> any security_audit
      attestation (ADR-014 audit runner) is rejected on-chain.

Expected state after GREEN (HYBRIDE V2):
    - 8 Python epistemic_type values are all accepted by EPISTEMIC_TYPE_MAP.
    - They project into 3 on-chain categories: empirical=0, deterministic=1,
      assessed=2.
    - Rust lib.rs: require!(epistemic_type <= 2, ...).
    - EPISTEMIC_TYPE_REVERSE decodes {0, 1, 2} -> {"empirical", "deterministic",
      "assessed"}.
    - security_audit (→2) passes the V2 Rust guard.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.solana.bridge import (
    EPISTEMIC_TYPE_MAP,
    EPISTEMIC_TYPE_REVERSE,
    attestation_to_anchor_args,
)
from services.esmm.attestation import (
    EpistemicAttestation,
    Signature5D,
    ModelVote,
    crystallize,
)


def _make_attestation(epistemic_type: str) -> EpistemicAttestation:
    """Build an attestation with a custom epistemic_type.

    INV-6 (ADR-020) : le type `deterministic` exige un `source_anchor`
    non-nul. On en fournit un par défaut pour que le helper reste
    utilisable avec tous les types épistémiques.
    """
    return crystallize(
        subject="solana",
        predicate="has_tps",
        object_="exceeds 3000",
        consensus_score=0.85,
        model_votes=[
            ModelVote(model_id="test::a", provider_id="test", agreed=True, confidence=0.9),
            ModelVote(model_id="test::b", provider_id="test", agreed=True, confidence=0.8),
            ModelVote(model_id="test::c", provider_id="test", agreed=False, confidence=0.3),
        ],
        signature_5d=Signature5D(
            agreement=0.85,
            semantic_consistency=0.72,
            centrality=0.45,
            stability=0.90,
            relation_diversity=0.60,
        ),
        epistemic_type=epistemic_type,
        metrological_frame="blockchain_tps_v1.0",
        architecture_families=2,
        source_anchor="a" * 64,
    )


class TestS1_002_NoKeyErrorForPipelineTypes:
    """S1-002: attestation_to_anchor_args must not KeyError on valid Python types."""

    def test_deterministic_type_does_not_keyerror(self) -> None:
        att = _make_attestation("deterministic")
        args = attestation_to_anchor_args(att)
        assert args.epistemic_type == 1, (
            f"Expected deterministic -> 1, got {args.epistemic_type}"
        )

    def test_verdict_type_does_not_keyerror(self) -> None:
        att = _make_attestation("verdict")
        args = attestation_to_anchor_args(att)
        assert args.epistemic_type == 0, (
            f"Expected verdict -> 0 (empirical), got {args.epistemic_type}"
        )


class TestS1_001_SecurityAuditUnderRustGuard:
    """S1-001: security_audit must map to a value <= Rust's max (V2 = 2)."""

    # Simulates the Rust require!(epistemic_type <= MAX_ON_CHAIN, ...)
    RUST_MAX_ON_CHAIN = 2

    def test_security_audit_passes_rust_guard_v2(self) -> None:
        att = _make_attestation("security_audit")
        args = attestation_to_anchor_args(att)
        assert args.epistemic_type <= self.RUST_MAX_ON_CHAIN, (
            f"security_audit u8={args.epistemic_type} exceeds Rust V2 max "
            f"{self.RUST_MAX_ON_CHAIN} -> on-chain require! will reject."
        )
        assert args.epistemic_type == 2, (
            f"Expected security_audit -> 2 (assessed), got {args.epistemic_type}"
        )


class TestV2ProjectionAllEightTypes:
    """GREEN: all 8 Python types project correctly into {0, 1, 2}."""

    EMPIRICAL_TYPES = [
        "foundational", "bridge", "specialized", "generalist", "hybrid", "verdict"
    ]

    @pytest.mark.parametrize("t", EMPIRICAL_TYPES)
    def test_empirical_types_project_to_zero(self, t: str) -> None:
        att = _make_attestation(t)
        args = attestation_to_anchor_args(att)
        assert args.epistemic_type == 0, (
            f"{t!r} should project to 0 (empirical), got {args.epistemic_type}"
        )

    def test_deterministic_projects_to_one(self) -> None:
        att = _make_attestation("deterministic")
        args = attestation_to_anchor_args(att)
        assert args.epistemic_type == 1

    def test_security_audit_projects_to_two(self) -> None:
        att = _make_attestation("security_audit")
        args = attestation_to_anchor_args(att)
        assert args.epistemic_type == 2


class TestV2ReverseMapSemantics:
    """GREEN: reverse map exposes the 3 on-chain categories."""

    def test_reverse_zero_is_empirical(self) -> None:
        assert EPISTEMIC_TYPE_REVERSE.get(0) == "empirical"

    def test_reverse_one_is_deterministic(self) -> None:
        assert EPISTEMIC_TYPE_REVERSE.get(1) == "deterministic"

    def test_reverse_two_is_assessed(self) -> None:
        assert EPISTEMIC_TYPE_REVERSE.get(2) == "assessed"

    def test_reverse_rejects_legacy_values(self) -> None:
        """Values 3, 4, 5 (old map) must no longer map to known categories."""
        for old_u8 in (3, 4, 5):
            assert EPISTEMIC_TYPE_REVERSE.get(old_u8) is None, (
                f"V2 reverse must not expose legacy u8={old_u8}"
            )


class TestV2RoundTripExplicit:
    """GREEN (explicit): Python source -> u8 -> on-chain category.

    Projection collapses sub-types (foundational, verdict, ...) into empirical.
    This is the intended semantic change of V2.
    """

    def test_roundtrip_foundational_becomes_empirical(self) -> None:
        u8 = EPISTEMIC_TYPE_MAP["foundational"]
        assert u8 == 0
        assert EPISTEMIC_TYPE_REVERSE[u8] == "empirical"

    def test_roundtrip_verdict_becomes_empirical(self) -> None:
        u8 = EPISTEMIC_TYPE_MAP["verdict"]
        assert u8 == 0
        assert EPISTEMIC_TYPE_REVERSE[u8] == "empirical"

    def test_roundtrip_deterministic_invariant(self) -> None:
        u8 = EPISTEMIC_TYPE_MAP["deterministic"]
        assert u8 == 1
        assert EPISTEMIC_TYPE_REVERSE[u8] == "deterministic"

    def test_roundtrip_security_audit_becomes_assessed(self) -> None:
        u8 = EPISTEMIC_TYPE_MAP["security_audit"]
        assert u8 == 2
        assert EPISTEMIC_TYPE_REVERSE[u8] == "assessed"


# ─────────────────────────────────────────────────────────────────────────
# Single-file runner — `python tests/<this_file>.py`
# Génère un rapport horodaté dans `test_results/individual/`.
# Cf. `tests/_runner.py::run_self` pour le détail.
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from tests._runner import run_self
    raise SystemExit(run_self(__file__))
