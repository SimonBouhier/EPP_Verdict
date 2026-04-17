"""
Scenario Deterministic Sources — ADR-012 Live Validation
========================================================

Prouve le chemin déterministe (ADR-012) bout en bout sur 4 sources réelles :
Wikidata, Verra VCS, EU CFSP (sanctions.io), OpenSanctions (yente).

Pour chaque claim répondu, 5 vérifications sont appliquées :
  1. source_anchor est un SHA-256 non-nul (64 hex chars)
  2. epistemic_type == "deterministic"
  3. consensus_meta.methodology.consensus_method == "deterministic_source_v1"
  4. Snapshot présent dans `source_anchor_snapshots` (get_snapshot_by_anchor)
  5. consensus_score respecte le plafond de la source (Wikidata ≤ 0.85)

Une source inaccessible (timeout, ConnectError, 404) est skippée proprement —
le script ne crashe jamais sur l'indisponibilité d'une API externe.

Usage:
    python demos/scenario_deterministic_sources.py

Output:
    - Tableau ASCII récapitulatif sur stdout
    - JSON horodaté dans demos/benchmark_runs/deterministic_sources_<ts>.json

Dépend de : ADR-012 (chemin déterministe), adapters services/sources/adapters/.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger("scenario_deterministic_sources")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_ENDPOINTS: dict[str, str] = {
    "wikidata": "https://query.wikidata.org/",
    "verra_vcs": "https://registry.verra.org/",
    "eu_cfsp": "https://www.sanctions.io/",
    "opensanctions": os.getenv("OPENSANCTIONS_ENDPOINT", "http://localhost:8080"),
}

# Plafonds de score par source (cf. adapters)
# - Wikidata : MAX_CONFIDENCE = 0.85 (source éditable publiquement)
# - Verra    : 1.0 pour active/retired, 0.5 sinon
# - EU CFSP / OpenSanctions : 1.0 théorique (score match ≥ 0.85, clear = 0.0)
SCORE_CAPS: dict[str, float] = {
    "wikidata": 0.85,
    "verra_vcs": 1.0,
    "eu_cfsp": 1.0,
    "opensanctions": 1.0,
}

ANCHOR_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

# ---------------------------------------------------------------------------
# Claims catalog — faits stables, vérifiables publiquement
# ---------------------------------------------------------------------------
# Les 2 premières requêtes Wikidata sont identiques à scenario_flywheel_v2.py
# (déjà validées manuellement sur query.wikidata.org).
# ---------------------------------------------------------------------------

CLAIMS: list[dict[str, Any]] = [
    # ----- Wikidata (2) -----
    {
        "id": "DET-WD-01",
        "source": "wikidata",
        "question": "Joe Biden was the 46th President of the United States",
        "frame": "general_knowledge_v1.0",
        "query": {
            "sparql": (
                "SELECT ?posLabel ?ordinal WHERE { "
                "wd:Q6279 p:P39 ?stmt . "
                "?stmt ps:P39 ?pos . "
                "OPTIONAL { ?stmt pq:P1545 ?ordinal . } "
                "SERVICE wikibase:label { bd:serviceParam wikibase:language \"en\" . } "
                "} LIMIT 10"
            ),
        },
    },
    {
        "id": "DET-WD-02",
        "source": "wikidata",
        "question": "Donald Trump won the 2024 US presidential election",
        "frame": "general_knowledge_v1.0",
        "query": {
            "sparql": (
                "SELECT ?winnerLabel WHERE { "
                "wd:Q101110072 wdt:P991 ?winner . "
                "SERVICE wikibase:label { bd:serviceParam wikibase:language \"en\" . } "
                "} LIMIT 5"
            ),
        },
    },
    # ----- Verra VCS (2) -----
    {
        "id": "DET-VER-01",
        "source": "verra_vcs",
        "question": "Verra VCS project #985 (Rimba Raya Biodiversity Reserve)",
        "frame": "general_knowledge_v1.0",
        "query": {"project_id": "985"},
    },
    {
        "id": "DET-VER-02",
        "source": "verra_vcs",
        "question": "Verra VCS project #1477 (Katingan Mentaya peatland)",
        "frame": "general_knowledge_v1.0",
        "query": {"project_id": "1477"},
    },
    # ----- EU CFSP / sanctions.io (2) -----
    {
        "id": "DET-EU-01",
        "source": "eu_cfsp",
        "question": "Vladimir Putin appears on the EU CFSP sanctions list",
        "frame": "general_knowledge_v1.0",
        "query": {"name": "Vladimir Putin"},
    },
    {
        "id": "DET-EU-02",
        "source": "eu_cfsp",
        "question": "The name 'Jane Smith Nonexistent 42' is not on the EU CFSP list",
        "frame": "general_knowledge_v1.0",
        "query": {"name": "Jane Smith Nonexistent 42"},
    },
    # ----- OpenSanctions / yente (2) — local endpoint, probablement indispo -----
    {
        "id": "DET-OS-01",
        "source": "opensanctions",
        "question": "Kim Jong Un appears on OpenSanctions",
        "frame": "general_knowledge_v1.0",
        "query": {"schema": "Person", "name": "Kim Jong Un"},
    },
    {
        "id": "DET-OS-02",
        "source": "opensanctions",
        "question": "The name 'John Q. Public Random Unknown' is not on OpenSanctions",
        "frame": "general_knowledge_v1.0",
        "query": {"schema": "Person", "name": "John Q. Public Random Unknown"},
    },
]


# ---------------------------------------------------------------------------
# Pre-check d'accessibilité (informatif seulement — ne bloque pas le run)
# ---------------------------------------------------------------------------

async def precheck_sources() -> dict[str, str]:
    """Ping léger de chaque endpoint (timeout 5s). Retourne un statut lisible."""
    results: dict[str, str] = {}
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        for source, url in SOURCE_ENDPOINTS.items():
            try:
                resp = await client.get(url)
                if resp.status_code < 500:
                    results[source] = f"reachable (HTTP {resp.status_code})"
                else:
                    results[source] = f"unreachable: HTTP {resp.status_code}"
            except Exception as exc:
                results[source] = f"unreachable: {type(exc).__name__}"
    return results


# ---------------------------------------------------------------------------
# Core : exécuter une claim via le pipeline déterministe, valider
# ---------------------------------------------------------------------------

async def run_claim(entry: dict[str, Any]) -> dict[str, Any]:
    """Exécute le chemin ADR-012 pour une claim, applique les 5 checks."""
    # Imports tardifs — sys.path est injecté en tête de module
    from database.engine import ISpaceDB
    from database.pool import close_pool
    from services.esmm.orchestrator import ClaimNature, ESMMRunConfig
    from services.esmm.pipeline import PipelineConfig, run_pipeline
    from services.esmm.source_anchor_builder import SourceAnchorSpec

    cid = entry["id"]
    source = entry["source"]
    question = entry["question"]
    frame = entry["frame"]
    query = entry["query"]

    row: dict[str, Any] = {
        "id": cid,
        "source": source,
        "question": question,
        "frame": frame,
        "query": query,
        "skipped": False,
        "skip_reason": None,
        "source_anchor": None,
        "source_anchor_length": 0,
        "epistemic_type": None,
        "consensus_method": None,
        "esmm_invoked": None,
        "consensus_score": None,
        "snapshot_stored": False,
        "status": None,
        "source_version": None,
        "checks": {},
        "duration_s": 0.0,
        "errors": "",
    }

    fd, db_path = tempfile.mkstemp(suffix=f"_det_{cid}.db")
    os.close(fd)

    start = time.time()
    try:
        db = ISpaceDB(db_path=db_path)
        await db.initialize()

        spec = SourceAnchorSpec(
            source_id=source,
            frame_id=frame,
            query=query,
        )
        config = PipelineConfig(
            metrological_frame=frame,
            use_cache=False,
        )
        esmm_config = ESMMRunConfig(
            models=[],
            claim_nature=ClaimNature.DETERMINISTIC,
            source_anchor_spec=spec,
        )

        result = await run_pipeline(
            question=question,
            db=db,
            config=config,
            providers={},
            models=[],
            esmm_config=esmm_config,
        )

        # Une exception adapter (timeout, 404, ConnectError) est remontée
        # dans result.errors par _run_deterministic_pipeline — pas de crash.
        if result.errors and not result.attestations:
            row["skipped"] = True
            row["skip_reason"] = result.errors[0][:200]
            row["errors"] = "; ".join(result.errors)
            return row

        if not result.attestations:
            row["skipped"] = True
            row["skip_reason"] = "no_attestation_returned"
            return row

        att = result.attestations[0]

        # consensus_meta peut être dict (en mémoire) ou str JSON (portable)
        meta = getattr(att, "consensus_meta", {}) or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}

        methodology = meta.get("methodology", {}) or {}
        diagnostics = meta.get("diagnostics", {}) or {}
        source_meta = meta.get("source_anchor_meta", {}) or {}

        row["source_anchor"] = getattr(att, "source_anchor", None)
        row["source_anchor_length"] = len(row["source_anchor"]) if row["source_anchor"] else 0
        row["epistemic_type"] = getattr(att, "epistemic_type", None)
        row["consensus_method"] = methodology.get("consensus_method")
        row["esmm_invoked"] = methodology.get("esmm_invoked")
        row["consensus_score"] = getattr(att, "consensus_score", None)
        row["status"] = diagnostics.get("result")
        row["source_version"] = source_meta.get("source_version")

        # Vérification snapshot en DB
        snapshot_stored = False
        if row["source_anchor"]:
            getter = getattr(db, "get_snapshot_by_anchor", None)
            if getter is not None:
                try:
                    snap = await getter(row["source_anchor"])
                    snapshot_stored = snap is not None
                except Exception as exc:
                    logger.warning(
                        "get_snapshot_by_anchor failed for %s: %s", cid, exc
                    )
        row["snapshot_stored"] = snapshot_stored

        if result.errors:
            row["errors"] = "; ".join(result.errors)

        # Les 5 checks auditeur
        cap = SCORE_CAPS.get(source, 1.0)
        score_val = row["consensus_score"] if row["consensus_score"] is not None else 0.0
        row["checks"] = {
            "anchor_format": bool(
                row["source_anchor"] and ANCHOR_HEX_RE.match(row["source_anchor"])
            ),
            "epistemic_type": row["epistemic_type"] == "deterministic",
            "consensus_method": row["consensus_method"] == "deterministic_source_v1",
            "snapshot_stored": snapshot_stored,
            "score_within_cap": score_val <= cap + 1e-9,
        }

    except Exception as exc:
        row["skipped"] = True
        row["skip_reason"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        row["errors"] = str(exc)
    finally:
        row["duration_s"] = round(time.time() - start, 2)
        try:
            await close_pool()
        except Exception:
            pass
        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except OSError:
                pass

    return row


# ---------------------------------------------------------------------------
# Affichage et persistance
# ---------------------------------------------------------------------------

def _fmt_checks(row: dict[str, Any]) -> str:
    if row["skipped"] or not row["checks"]:
        return "  -  "
    passed = sum(1 for v in row["checks"].values() if v)
    total = len(row["checks"])
    return f"{passed}/{total}"


def render_recap(rows: list[dict[str, Any]]) -> None:
    print("\n" + "=" * 86)
    print("ADR-012 DETERMINISTIC SOURCES — RESULTS")
    print("=" * 86)

    header = (
        f"  {'':<4}{'ID':<12}{'Source':<14}"
        f"{'Status':<11}{'Score':>7}{'Anchor':>16}{'Checks':>8}{'Time':>8}"
    )
    print("\n" + header)
    print("  " + "-" * (len(header) - 2))

    for r in rows:
        cid = r["id"]
        src = r["source"]
        dur = f"{r['duration_s']:.1f}s"
        if r["skipped"]:
            icon = "--"
            status = "SKIPPED"
            score = "   -"
            anchor_short = "       -"
            checks_str = "  -  "
        else:
            all_pass = all(r["checks"].values())
            icon = "OK" if all_pass else "XX"
            status = (r["status"] or "-")[:10]
            score = f"{r['consensus_score']:.2f}" if r["consensus_score"] is not None else "   -"
            anchor = r["source_anchor"] or ""
            anchor_short = (anchor[:12] + "..") if anchor else "       -"
            checks_str = _fmt_checks(r)

        print(
            f"  {icon:<4}{cid:<12}{src:<14}"
            f"{status:<11}{score:>7}{anchor_short:>16}{checks_str:>8}{dur:>8}"
        )

        if r["skipped"]:
            print(f"          -> {(r['skip_reason'] or '')[:70]}")
        else:
            failed = [k for k, v in r["checks"].items() if not v]
            if failed:
                print(f"          -> failed: {', '.join(failed)}")

    total = len(rows)
    responded = sum(1 for r in rows if not r["skipped"])
    skipped = total - responded
    all_passed = sum(
        1 for r in rows if not r["skipped"] and all(r["checks"].values())
    )

    print("\n  " + "-" * (len(header) - 2))
    print(
        f"  Totals: {total} claims | {responded} responded "
        f"| {skipped} skipped | {all_passed} all-checks-passed"
    )
    print("=" * 86)


def write_report(
    rows: list[dict[str, Any]], precheck: dict[str, str]
) -> Path:
    out_dir = Path(__file__).parent / "benchmark_runs"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"deterministic_sources_{ts}.json"

    total = len(rows)
    responded = sum(1 for r in rows if not r["skipped"])
    all_passed = sum(
        1 for r in rows if not r["skipped"] and all(r["checks"].values())
    )
    any_failed = sum(
        1 for r in rows if not r["skipped"] and not all(r["checks"].values())
    )

    report = {
        "scenario": "scenario_deterministic_sources",
        "adr": "ADR-012",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "precheck": precheck,
        "score_caps": SCORE_CAPS,
        "claims": rows,
        "summary": {
            "total": total,
            "responded": responded,
            "skipped": total - responded,
            "all_checks_passed": all_passed,
            "any_check_failed": any_failed,
        },
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str, ensure_ascii=False)
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    print("=" * 86)
    print(
        "EPP SCENARIO — ADR-012 Deterministic Sources "
        "(Wikidata / Verra VCS / EU CFSP / OpenSanctions)"
    )
    print("=" * 86)

    print(
        "\n  [PRECHECK] Pinging public endpoints "
        "(5s timeout, informational only)..."
    )
    precheck = await precheck_sources()
    for source, status in precheck.items():
        icon = "OK" if status.startswith("reachable") else "--"
        print(f"    {icon}  {source:<14} -> {status}")

    print(
        f"\n  Running {len(CLAIMS)} claim(s). "
        "Sources unreachable will be skipped gracefully.\n"
    )

    rows: list[dict[str, Any]] = []
    for i, entry in enumerate(CLAIMS, 1):
        short_q = entry["question"]
        if len(short_q) > 60:
            short_q = short_q[:57] + "..."
        print(
            f"  [{i:02d}/{len(CLAIMS):02d}] {entry['id']} "
            f"[{entry['source']}] \"{short_q}\""
        )
        row = await run_claim(entry)
        if row["skipped"]:
            print(f"           SKIPPED: {(row['skip_reason'] or '')[:70]}")
        else:
            checks = row["checks"]
            passed = sum(1 for v in checks.values() if v)
            total_c = len(checks)
            icon = "OK" if passed == total_c else "XX"
            score = row["consensus_score"] if row["consensus_score"] is not None else 0.0
            print(
                f"           {icon} status={row['status']} "
                f"score={score:.2f} checks={passed}/{total_c} "
                f"| {row['duration_s']:.1f}s"
            )
        rows.append(row)

    render_recap(rows)
    path = write_report(rows, precheck)
    print(f"\n  Report: {path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
