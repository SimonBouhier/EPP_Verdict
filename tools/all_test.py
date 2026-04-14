# tools/run_pytest_capture.py
# -*- coding: utf-8 -*-
"""
Wrapper générique pour exécuter pytest et enregistrer des artefacts exploitables.

Artefacts produits par run :
- console.txt      : sortie console complète (stdout/stderr)
- summary.json     : résumé du run
- results.jsonl    : 1 ligne JSON par test (agrégé par nodeid)
- command.txt      : commande / arguments utilisés

Usage CMD :
    python tools\run_pytest_capture.py -- tests\ -v
    python tools\run_pytest_capture.py -- tests\ -k latest_attestation -v
    python tools\run_pytest_capture.py -- tests\test_adr018_flywheel.py -v

Notes :
- Ce squelette exécute pytest IN-PROCESS via pytest.main(..., plugins=[...]).
- C'est pratique pour brancher un plugin d'enregistrement sans dépendance externe.
- Si tu veux une parité stricte avec "python -m pytest", Claude pourra l'adapter
  en mode subprocess + plugin dédié. Mais pour verrouiller la forme des artefacts,
  ce squelette est suffisant.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import traceback
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest


# =========================
# Helpers
# =========================

def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def local_run_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def safe_slug(value: str) -> str:
    cleaned = []
    for ch in value:
        if ch.isalnum() or ch in ("-", "_"):
            cleaned.append(ch)
        elif ch in (" ", ".", ":", "\\", "/"):
            cleaned.append("_")
    result = "".join(cleaned).strip("_")
    return result or "run"


class Tee:
    """
    Duplique stdout/stderr vers la console ET vers un fichier.
    """

    def __init__(self, *streams):
        self.streams = streams
        self.encoding = getattr(streams[0], "encoding", "utf-8")

    def write(self, data: str) -> int:
        for stream in self.streams:
            stream.write(data)
            stream.flush()
        return len(data)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()

    def isatty(self) -> bool:
        return False


@dataclass
class TestRecord:
    nodeid: str
    phases: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    final_outcome: Optional[str] = None
    duration_total: float = 0.0
    longrepr: Optional[str] = None
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodeid": self.nodeid,
            "final_outcome": self.final_outcome,
            "duration_total": round(self.duration_total, 6),
            "phases": self.phases,
            "longrepr": self.longrepr,
            "keywords": self.keywords,
        }


# =========================
# Plugin pytest
# =========================

class RecorderPlugin:
    def __init__(self) -> None:
        self.run_started_at = utc_now_iso()
        self.run_finished_at: Optional[str] = None
        self.exit_code: Optional[int] = None

        self.collected_total = 0
        self.selected_total = 0
        self.deselected_total = 0

        self.collection_errors: List[str] = []
        self.internal_errors: List[str] = []

        self.tests: Dict[str, TestRecord] = {}
        self.deselected_nodeids: List[str] = []

    def _get_record(self, nodeid: str) -> TestRecord:
        if nodeid not in self.tests:
            self.tests[nodeid] = TestRecord(nodeid=nodeid)
        return self.tests[nodeid]

    @pytest.hookimpl
    def pytest_collection_finish(self, session) -> None:
        # session.testscollected = total collecté avant deselection
        # session.items = tests réellement sélectionnés pour exécution
        self.collected_total = int(getattr(session, "testscollected", 0) or 0)
        self.selected_total = len(getattr(session, "items", []) or [])

        for item in getattr(session, "items", []):
            record = self._get_record(item.nodeid)
            try:
                record.keywords = sorted(
                    [k for k, v in item.keywords.items() if v is True and "::" not in k]
                )
            except Exception:
                record.keywords = []

    @pytest.hookimpl
    def pytest_deselected(self, items) -> None:
        self.deselected_total += len(items)
        self.deselected_nodeids.extend([item.nodeid for item in items])

    @pytest.hookimpl
    def pytest_collectreport(self, report) -> None:
        if getattr(report, "failed", False):
            self.collection_errors.append(str(report.longrepr))

    @pytest.hookimpl
    def pytest_internalerror(self, excrepr, excinfo) -> None:
        self.internal_errors.append(str(excrepr))

    @pytest.hookimpl
    def pytest_runtest_logreport(self, report) -> None:
        record = self._get_record(report.nodeid)

        outcome = report.outcome
        if hasattr(report, "wasxfail"):
            if report.outcome == "skipped":
                outcome = "xfailed"
            elif report.outcome == "passed":
                outcome = "xpassed"

        phase_payload = {
            "outcome": outcome,
            "duration": round(float(getattr(report, "duration", 0.0) or 0.0), 6),
        }

        if report.failed:
            phase_payload["longrepr"] = str(report.longrepr)
            record.longrepr = str(report.longrepr)

        record.phases[report.when] = phase_payload
        record.duration_total += float(getattr(report, "duration", 0.0) or 0.0)

    @pytest.hookimpl
    def pytest_sessionfinish(self, session, exitstatus) -> None:
        self.exit_code = int(exitstatus)
        self.run_finished_at = utc_now_iso()

        for record in self.tests.values():
            record.final_outcome = self._compute_final_outcome(record)

    def _compute_final_outcome(self, record: TestRecord) -> str:
        """
        Priorité simple :
        - setup failed/xfailed/xpassed/skipped
        - call outcome si présent
        - teardown failed
        - sinon unknown
        """
        setup = record.phases.get("setup")
        call = record.phases.get("call")
        teardown = record.phases.get("teardown")

        if setup and setup["outcome"] in {"failed", "skipped", "xfailed", "xpassed"}:
            return setup["outcome"]

        if call:
            return call["outcome"]

        if teardown and teardown["outcome"] in {"failed", "skipped", "xfailed", "xpassed"}:
            return teardown["outcome"]

        return "unknown"

    def build_summary(self, pytest_args: List[str], run_id: str) -> Dict[str, Any]:
        outcome_counts = Counter(
            record.final_outcome or "unknown" for record in self.tests.values()
        )

        proof_usable = True
        proof_notes: List[str] = []

        if self.selected_total == 0:
            proof_usable = False
            proof_notes.append("0 selected: run non probant")

        if self.collection_errors:
            proof_usable = False
            proof_notes.append("collection errors present")

        if self.internal_errors:
            proof_usable = False
            proof_notes.append("pytest internal errors present")

        return {
            "run_id": run_id,
            "started_at": self.run_started_at,
            "finished_at": self.run_finished_at,
            "pytest_args": pytest_args,
            "exit_code": self.exit_code,
            "collected_total": self.collected_total,
            "selected_total": self.selected_total,
            "deselected_total": self.deselected_total,
            "test_outcomes": dict(outcome_counts),
            "collection_errors_count": len(self.collection_errors),
            "internal_errors_count": len(self.internal_errors),
            "proof_usable": proof_usable,
            "proof_notes": proof_notes,
            "environment": {
                "python": sys.version,
                "python_executable": sys.executable,
                "platform": platform.platform(),
                "cwd": str(Path.cwd()),
                "pytest_version": getattr(pytest, "__version__", "unknown"),
            },
        }


# =========================
# I/O
# =========================

def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


# =========================
# Main
# =========================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exécute pytest et capture des artefacts exploitables."
    )
    parser.add_argument(
        "--results-root",
        default="test_results",
        help="Dossier racine des résultats (défaut: test_results)",
    )
    parser.add_argument(
        "--label",
        default="",
        help="Label optionnel pour suffixer le dossier de run",
    )
    parser.add_argument(
        "--allow-zero-selected",
        action="store_true",
        help="Ne force pas un code de sortie spécial si 0 test sélectionné",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Arguments passés à pytest après --",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    pytest_args = list(args.pytest_args)
    if pytest_args and pytest_args[0] == "--":
        pytest_args = pytest_args[1:]

    if not pytest_args:
        print("ERREUR: aucun argument pytest fourni.")
        print(r"Exemple CMD: python tools\run_pytest_capture.py -- tests\ -v")
        return 2

    stamp = local_run_stamp()
    label = safe_slug(args.label) if args.label else ""
    run_dir_name = f"{stamp}_{label}" if label else stamp
    run_dir = Path(args.results_root) / run_dir_name
    run_dir.mkdir(parents=True, exist_ok=False)

    console_path = run_dir / "console.txt"
    summary_path = run_dir / "summary.json"
    results_path = run_dir / "results.jsonl"
    command_path = run_dir / "command.txt"

    run_id = run_dir_name

    plugin = RecorderPlugin()

    command_payload = {
        "run_id": run_id,
        "timestamp": utc_now_iso(),
        "equivalent_command": f"pytest {' '.join(pytest_args)}",
        "pytest_args": pytest_args,
    }
    write_json(command_path, command_payload)

    original_stdout = sys.stdout
    original_stderr = sys.stderr

    exit_code = 1
    unexpected_error: Optional[str] = None

    with console_path.open("w", encoding="utf-8", newline="\n") as console_file:
        sys.stdout = Tee(original_stdout, console_file)
        sys.stderr = Tee(original_stderr, console_file)

        print("=" * 80)
        print("PYTEST CAPTURE RUN")
        print(f"run_id      : {run_id}")
        print(f"started_at  : {utc_now_iso()}")
        print(f"cwd         : {Path.cwd()}")
        print(f"pytest_args : {pytest_args}")
        print("=" * 80)

        try:
            exit_code = pytest.main(pytest_args, plugins=[plugin])
        except Exception:
            unexpected_error = traceback.format_exc()
            print("\n[WRAPPER ERROR]")
            print(unexpected_error)
            exit_code = 1
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

    summary = plugin.build_summary(pytest_args=pytest_args, run_id=run_id)
    summary["wrapper_error"] = unexpected_error

    # Marque spéciale pour les runs non probants
    if summary["selected_total"] == 0 and not args.allow_zero_selected:
        # code wrapper distinct pour "run non probant"
        # laisse trace claire sans masquer le fait que pytest lui-même a pu sortir 0
        summary["wrapper_exit_code"] = 10
        final_exit_code = 10
    else:
        summary["wrapper_exit_code"] = exit_code
        final_exit_code = exit_code

    rows = []
    for nodeid in sorted(plugin.tests.keys()):
        record = plugin.tests[nodeid].to_dict()
        record["run_id"] = run_id
        record["timestamp"] = summary["finished_at"]
        rows.append(record)

    write_json(summary_path, summary)
    write_jsonl(results_path, rows)

    print(f"[OK] Artefacts écrits dans : {run_dir}")
    print(f"     - {console_path}")
    print(f"     - {summary_path}")
    print(f"     - {results_path}")
    print(f"     - {command_path}")

    return final_exit_code


if __name__ == "__main__":
    raise SystemExit(main())