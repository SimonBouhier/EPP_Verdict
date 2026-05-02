"""
RED test for S6-002 — ISpaceDB.__init__ must require db_path explicitly.

Current state (RED):
    database/engine.py:50 declares `def __init__(self, db_path: str = "data/ispace.db")`.
    The default points to `data/ispace.db`, which is INCONSISTENT with
    config.yaml (which uses `data/epp_devnet.db`) and misleading: an
    accidentally parameter-less call silently produces an ISpaceDB bound
    to the wrong file.

Expected state after GREEN:
    The constructor raises `TypeError: missing 1 required positional
    argument: 'db_path'` when called without a path.
"""
from __future__ import annotations
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


import pytest

from database.engine import ISpaceDB


class TestS6_002_DbPathIsMandatory:
    def test_construction_without_path_raises_typeerror(self) -> None:
        # RED: currently returns an instance bound to "data/ispace.db".
        # GREEN: must raise TypeError for the missing required argument.
        with pytest.raises(TypeError) as excinfo:
            ISpaceDB()
        msg = str(excinfo.value)
        assert "db_path" in msg, (
            f"TypeError should mention 'db_path', got: {msg!r}"
        )

    def test_explicit_path_still_works(self, tmp_path) -> None:
        """GREEN-side: providing a path must remain valid."""
        db = ISpaceDB(str(tmp_path / "explicit.db"))
        # Construction must not raise; path must be stored as given.
        assert str(db.db_path).endswith("explicit.db")

    def test_keyword_path_still_works(self, tmp_path) -> None:
        """GREEN-side: kwarg form must remain valid."""
        db = ISpaceDB(db_path=str(tmp_path / "kwarg.db"))
        assert str(db.db_path).endswith("kwarg.db")


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
