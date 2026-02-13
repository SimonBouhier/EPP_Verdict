"""
Tests de compatibilité bridge Python <-> Solana.
Phase 4.0.2 — Smoke test précoce.

Vérifient que les types sérialisés côté Python sont cohérents
avec les types attendus côté Anchor.
À exécuter dès le début — pas en Phase 4.6.
"""

import re
import pytest


def test_score_scale_matches_anchor():
    """SCORE_SCALE Python == SCORE_SCALE Rust."""
    from services.solana.bridge import SCORE_SCALE

    with open("programs/epp/programs/epp/src/constants.rs") as f:
        rust_code = f.read()
    match = re.search(r"SCORE_SCALE.*?=\s*(\d+)", rust_code)
    assert match, "SCORE_SCALE not found in constants.rs"
    assert int(match.group(1)) == SCORE_SCALE, (
        f"Python SCORE_SCALE={SCORE_SCALE} != Rust SCORE_SCALE={match.group(1)}"
    )


def test_max_lengths_match_anchor():
    """MAX_*_LEN Python == Rust constants."""
    from services.solana.bridge import MAX_SUBJECT_LEN, MAX_PREDICATE_LEN, MAX_OBJECT_LEN

    with open("programs/epp/programs/epp/src/constants.rs") as f:
        rust_code = f.read()

    for name, py_val in [
        ("MAX_SUBJECT_LEN", MAX_SUBJECT_LEN),
        ("MAX_PREDICATE_LEN", MAX_PREDICATE_LEN),
        ("MAX_OBJECT_LEN", MAX_OBJECT_LEN),
    ]:
        match = re.search(rf"{name}.*?=\s*(\d+)", rust_code)
        assert match, f"{name} not found in constants.rs"
        assert int(match.group(1)) == py_val, (
            f"Python {name}={py_val} != Rust {name}={match.group(1)}"
        )


def test_float_roundtrip_boundary_values():
    """Valeurs limites du roundtrip float <-> u16."""
    from services.solana.bridge import float_to_u16, u16_to_float

    for f in [0.0, 0.0001, 0.5, 0.9999, 1.0]:
        encoded = float_to_u16(f)
        assert 0 <= encoded <= 65535, f"u16 overflow: {encoded}"
        decoded = u16_to_float(encoded)
        assert abs(decoded - f) < 1e-4, (
            f"Roundtrip failed: {f} -> {encoded} -> {decoded}"
        )


def test_float_to_u16_rejects_out_of_range():
    """float_to_u16 refuse les valeurs hors [0.0, 1.0]."""
    from services.solana.bridge import float_to_u16

    with pytest.raises(ValueError):
        float_to_u16(-0.1)
    with pytest.raises(ValueError):
        float_to_u16(1.1)


def test_claim_hash_size_matches_anchor():
    """Le claim_hash Python produit 32 bytes, comme attendu par [u8; 32] Anchor."""
    from services.esmm.attestation import compute_claim_hash

    h = compute_claim_hash("sun", "is", "star", "frame_v1")
    h_bytes = bytes.fromhex(h)
    assert len(h_bytes) == 32, f"Expected 32 bytes, got {len(h_bytes)}"


def test_string_encoding_fixed_bytes():
    """Les strings encodées tiennent dans les champs Anchor."""
    from services.solana.bridge import string_to_fixed_bytes

    for s in ["hello", "a" * 200]:
        encoded = string_to_fixed_bytes(s, 64)
        assert len(encoded) == 64, f"Expected 64 bytes, got {len(encoded)}"

    # Unicode multi-byte
    for s in ["test unicode", "entropy"]:
        encoded = string_to_fixed_bytes(s, 128)
        assert len(encoded) == 128, f"Expected 128 bytes, got {len(encoded)}"


def test_string_roundtrip():
    """Encodage + décodage string préserve le contenu (si pas tronqué)."""
    from services.solana.bridge import string_to_fixed_bytes, fixed_bytes_to_string

    for s in ["hello", "solana", "entropy", "consensus"]:
        encoded = string_to_fixed_bytes(s, 64)
        decoded = fixed_bytes_to_string(encoded)
        assert decoded == s, f"Roundtrip failed: '{s}' -> '{decoded}'"
