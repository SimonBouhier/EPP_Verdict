"""
Property-based tests using hypothesis (Phase 4.7 — Bloc E).

Tests:
  1. float↔u16 roundtrip (ADR-001): tolerance 1e-4
  2. compute_claim_hash determinism (ADR-006): 64 hex chars, deterministic
"""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from services.solana.bridge import (
    float_to_u16, u16_to_float,
    CONFIDENCE_TIER_MAP, CONFIDENCE_TIER_REVERSE,
)
from services.esmm.attestation import compute_claim_hash


class TestFloatU16Roundtrip:
    """ADR-001: float↔u16 roundtrip with tolerance 1e-4."""

    @given(f=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=200)
    def test_roundtrip_tolerance(self, f: float):
        """∀ f ∈ [0.0, 1.0] : |u16_to_float(float_to_u16(f)) - f| < 1e-4"""
        encoded = float_to_u16(f)
        decoded = u16_to_float(encoded)
        assert abs(decoded - f) < 1e-4, f"Roundtrip error: {f} -> {encoded} -> {decoded}"

    @given(f=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=200)
    def test_encoded_range(self, f: float):
        """∀ f ∈ [0.0, 1.0] : float_to_u16(f) ∈ [0, 10000]"""
        encoded = float_to_u16(f)
        assert 0 <= encoded <= 10000


class TestClaimHashDeterminism:
    """ADR-006: compute_claim_hash is deterministic and produces 64 hex chars."""

    @given(
        s=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"))),
        p=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"))),
        o=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"))),
        frame=st.text(min_size=0, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"))),
    )
    @settings(max_examples=200)
    def test_deterministic_64_hex(self, s: str, p: str, o: str, frame: str):
        """∀ (s, p, o) : compute_claim_hash(s,p,o,frame) is deterministic and 64 hex chars."""
        h1 = compute_claim_hash(s, p, o, frame if frame else None)
        h2 = compute_claim_hash(s, p, o, frame if frame else None)
        assert h1 == h2, f"Non-deterministic hash for ({s}, {p}, {o}, {frame})"
        assert len(h1) == 64, f"Hash length {len(h1)} != 64"
        assert all(c in "0123456789abcdef" for c in h1), f"Non-hex chars in hash: {h1}"


class TestConfidenceTierRoundtrip:
    """ADR-005: confidence tier mapping roundtrip Python ↔ Solana u8."""

    CANONICAL_TIERS = ["sandbox", "proposition", "validated", "verified"]

    @pytest.mark.parametrize("tier,expected_u8", [
        ("sandbox", 0),
        ("proposition", 1),
        ("validated", 2),
        ("verified", 3),
    ])
    def test_canonical_tier_roundtrip(self, tier: str, expected_u8: int):
        """∀ tier ∈ {sandbox,proposition,validated,verified} : REVERSE[MAP[tier]] == tier"""
        u8_val = CONFIDENCE_TIER_MAP[tier]
        assert u8_val == expected_u8
        roundtripped = CONFIDENCE_TIER_REVERSE[u8_val]
        assert roundtripped == tier

    def test_all_canonical_tiers_in_map(self):
        """Les 4 tiers canoniques sont dans CONFIDENCE_TIER_MAP."""
        for tier in self.CANONICAL_TIERS:
            assert tier in CONFIDENCE_TIER_MAP, f"Missing tier: {tier}"

    def test_reverse_maps_to_canonical_only(self):
        """CONFIDENCE_TIER_REVERSE ne produit que des tiers canoniques."""
        for u8_val, tier in CONFIDENCE_TIER_REVERSE.items():
            assert tier in self.CANONICAL_TIERS, f"Reverse maps {u8_val} to non-canonical '{tier}'"



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
