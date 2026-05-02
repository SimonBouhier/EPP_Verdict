"""
RED tests for S1-005 — AUDIT[A10-007] marker is obsolete.

Context:
    services/solana/bridge.py:111 carries the marker
        `# AUDIT[A10-007] 🟡 FRAGILE: valeur > 1.0 (ex: 1.000049) arrondie à
        10000 — acceptée sans erreur.`
    This claim is FALSE at current HEAD: float_to_u16() guards the input with
    `if not 0.0 <= value <= 1.0: raise ValueError`, so 1.000049 raises instead
    of being silently rounded.

    The marker must therefore be reclassified to `🟡→✅ RESOLVED` per the
    project's marker conventions (see other `🟡→✅` / `🔴→✅` instances, e.g.
    pipeline.py::AUDIT[A8-001]).

RED (inspection) — the marker must carry the RESOLVED sigil.
RED (behaviour) — the bug the marker described must actually be absent
(guards the reclassification from being cosmetic).
"""
from __future__ import annotations
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


from pathlib import Path

import pytest

from services.solana.bridge import float_to_u16, SCORE_SCALE


BRIDGE_PATH = Path(__file__).resolve().parents[1] / "services" / "solana" / "bridge.py"


class TestS1_005_MarkerReclassified:
    def test_a10_007_no_longer_flagged_fragile(self) -> None:
        """RED: AUDIT[A10-007] must not carry the 🟡 FRAGILE sigil anymore."""
        src = BRIDGE_PATH.read_text(encoding="utf-8")
        # Locate the A10-007 line.
        lines = [ln for ln in src.splitlines() if "AUDIT[A10-007]" in ln]
        assert lines, "AUDIT[A10-007] marker not found in bridge.py"
        marker = lines[0]
        assert "🟡 FRAGILE" not in marker, (
            f"AUDIT[A10-007] still flagged 🟡 FRAGILE, but the bug described "
            f"(1.000049 silently accepted) is absent. Marker line:\n{marker}"
        )

    def test_a10_007_carries_resolved_sigil(self) -> None:
        """GREEN-side: marker must use the project's '✅ RESOLVED' convention."""
        src = BRIDGE_PATH.read_text(encoding="utf-8")
        lines = [ln for ln in src.splitlines() if "AUDIT[A10-007]" in ln]
        assert lines, "AUDIT[A10-007] marker not found in bridge.py"
        marker = lines[0]
        assert (
            "✅ RESOLVED" in marker or "→✅" in marker
        ), (
            f"AUDIT[A10-007] should be reclassified to ✅ RESOLVED "
            f"per repo conventions (see other 🔴→✅ / 🟡→✅ markers). "
            f"Current line:\n{marker}"
        )


class TestS1_005_BehaviouralJustification:
    """These tests must PASS before AND after the marker reclassification —
    they prove the claim in the old marker was already false, which is the
    precondition for legitimately downgrading 🟡 FRAGILE to ✅ RESOLVED."""

    def test_value_just_above_one_is_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
            float_to_u16(1.000049)

    def test_value_far_above_one_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            float_to_u16(1.5)

    def test_negative_value_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            float_to_u16(-0.001)

    def test_exact_one_maps_to_scale(self) -> None:
        assert float_to_u16(1.0) == SCORE_SCALE

    def test_exact_zero_maps_to_zero(self) -> None:
        assert float_to_u16(0.0) == 0


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
