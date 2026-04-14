"""
RED tests for S1-003 — string_to_fixed_bytes UTF-8 truncation safety.

Current state (RED):
    services/solana/bridge.py:137 — `s.encode("utf-8")[:max_len]` slices the
    encoded bytes without regard for codepoint boundaries. A multi-byte
    character (é, 中, 😀, ...) at the boundary can be split mid-codepoint,
    producing invalid UTF-8 that `.decode("utf-8")` rejects with
    UnicodeDecodeError. This corrupts on-chain fields whose content is
    read back (subject, predicate, object).

Expected state after GREEN:
    string_to_fixed_bytes truncates on a codepoint boundary. The resulting
    bytes are always valid UTF-8 when decoded.
"""
from __future__ import annotations

import pytest

from services.solana.bridge import string_to_fixed_bytes, fixed_bytes_to_string


class TestS1_003_MultiByteBoundary:
    def test_accented_string_at_odd_boundary_stays_valid_utf8(self) -> None:
        """`é` is 2 UTF-8 bytes; truncating at an odd length mid-char must not corrupt."""
        s = "é" * 32           # 64 bytes encoded
        max_len = 63            # forces a cut in the middle of the last `é`
        b = string_to_fixed_bytes(s, max_len)
        assert len(b) == max_len
        # Strip trailing zero padding before decoding.
        stripped = b.rstrip(b"\x00")
        # RED: current impl yields a mid-codepoint cut → UnicodeDecodeError.
        decoded = stripped.decode("utf-8")
        # All remaining characters must be complete `é` (no orphan byte).
        assert set(decoded) == {"é"}, f"Got unexpected chars: {set(decoded)!r}"

    def test_cjk_character_at_boundary(self) -> None:
        """Chinese ideogram `中` is 3 UTF-8 bytes."""
        s = "中" * 10           # 30 bytes encoded
        max_len = 29            # one byte shy of the last full char
        b = string_to_fixed_bytes(s, max_len)
        stripped = b.rstrip(b"\x00")
        decoded = stripped.decode("utf-8")
        assert set(decoded) == {"中"}

    def test_emoji_at_boundary(self) -> None:
        """Emoji `😀` is 4 UTF-8 bytes."""
        s = "😀" * 8            # 32 bytes encoded
        max_len = 30            # cuts mid-emoji
        b = string_to_fixed_bytes(s, max_len)
        stripped = b.rstrip(b"\x00")
        decoded = stripped.decode("utf-8")
        assert set(decoded) == {"😀"}


class TestS1_003_RoundTrip:
    def test_roundtrip_mixed_multibyte_safe(self) -> None:
        """Round-trip through fixed_bytes_to_string must always succeed."""
        s = "café 中国 😀 naïve résumé"
        # Try several truncation lengths, including odd ones.
        for max_len in (10, 15, 20, 25, 30, 64):
            b = string_to_fixed_bytes(s, max_len)
            recovered = fixed_bytes_to_string(b)
            # Recovered string must be a valid prefix (in character-count sense)
            # of the original, never raise, and decode to a valid UTF-8 str.
            assert isinstance(recovered, str)
            assert s.startswith(recovered), (
                f"Recovered {recovered!r} is not a prefix of {s!r} at max_len={max_len}"
            )


class TestS1_003_ShortPaths:
    """Behaviours that must NOT regress."""

    def test_empty_string(self) -> None:
        assert string_to_fixed_bytes("", 16) == b"\x00" * 16

    def test_exact_fit_ascii(self) -> None:
        assert string_to_fixed_bytes("abcd", 4) == b"abcd"

    def test_shorter_than_max_is_zero_padded(self) -> None:
        b = string_to_fixed_bytes("hi", 8)
        assert b == b"hi\x00\x00\x00\x00\x00\x00"
