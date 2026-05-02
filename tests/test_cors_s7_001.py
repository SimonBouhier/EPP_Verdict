"""
RED test for S7-001 — CORS middleware allows any origin with credentials.

Current state (RED):
    app/main.py:171-178 configures CORSMiddleware with
    allow_origins=["*"] and allow_credentials=True. Per the CORS spec,
    when credentials are allowed, the server cannot answer with
    Access-Control-Allow-Origin: * — FastAPI instead echoes the request
    Origin header. This accepts ANY site as a credentialed origin,
    opening CSRF / credential-leak vectors.

Expected state after GREEN:
    - Malicious origin (https://evil.example) is NOT echoed in ACAO.
    - Legitimate dev origin (http://localhost:3000) IS echoed.
"""
from __future__ import annotations
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_cors_rejects_malicious_origin(client: TestClient) -> None:
    """RED: https://evil.example must not be accepted as a CORS origin."""
    response = client.get(
        "/health",
        headers={"Origin": "https://evil.example"},
    )
    acao = response.headers.get("access-control-allow-origin")
    assert acao != "https://evil.example", (
        "CORS echoed a malicious origin — credentialed CSRF vector. "
        f"Got ACAO={acao!r}"
    )
    assert acao != "*", (
        "CORS returned wildcard with credentials — spec-violating and unsafe."
    )


def test_cors_accepts_localhost_dev_origin(client: TestClient) -> None:
    """GREEN-side: legitimate dev origin must remain accepted."""
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"},
    )
    acao = response.headers.get("access-control-allow-origin")
    assert acao == "http://localhost:3000", (
        f"Expected localhost:3000 to be echoed, got ACAO={acao!r}"
    )


def test_cors_preflight_rejects_malicious_origin(client: TestClient) -> None:
    """RED: OPTIONS preflight from evil.example must not return credentials clearance."""
    response = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    acao = response.headers.get("access-control-allow-origin")
    assert acao != "https://evil.example", (
        f"Preflight echoed malicious origin. Got ACAO={acao!r}"
    )


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
