"""ADR-014 Lot 1 — Tests: Frame smartcontract_audit_v1.0."""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib

from services.solana.metrological_frame import PREDEFINED_FRAMES, MetrologicalFrame


def test_smartcontract_audit_frame_in_predefined():
    assert "smartcontract_audit_v1.0" in PREDEFINED_FRAMES


def test_smartcontract_audit_frame_is_callable():
    factory = PREDEFINED_FRAMES.get("smartcontract_audit_v1.0")
    assert callable(factory)


def test_smartcontract_audit_frame_domain():
    frame = PREDEFINED_FRAMES["smartcontract_audit_v1.0"]()
    assert frame.domain == "smart_contract_security"


def test_smartcontract_audit_frame_severity_taxonomy():
    frame = PREDEFINED_FRAMES["smartcontract_audit_v1.0"]()
    assert frame.parameters["severity_taxonomy"] == "tob_4level"


def test_smartcontract_audit_frame_hash_deterministic():
    frame1 = PREDEFINED_FRAMES["smartcontract_audit_v1.0"]()
    frame2 = PREDEFINED_FRAMES["smartcontract_audit_v1.0"]()
    assert frame1.compute_frame_hash() == frame2.compute_frame_hash()


def test_smartcontract_audit_frame_returns_metrological_frame():
    frame = PREDEFINED_FRAMES["smartcontract_audit_v1.0"]()
    assert isinstance(frame, MetrologicalFrame)


def test_smartcontract_audit_frame_metric():
    frame = PREDEFINED_FRAMES["smartcontract_audit_v1.0"]()
    assert frame.metric == "vulnerability_presence"


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
