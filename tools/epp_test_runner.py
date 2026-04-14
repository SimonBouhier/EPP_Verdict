#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
EPP_Verdict Test Runner v1 — Wrapper passif pour pytest.

Exécute pytest et capture les artefacts exploitables :
- console.txt      : sortie complète (stdout/stderr)
- summary.json     : résumé du run (métriques, proof_usable, notes)
- results.jsonl    : 1 ligne JSON par test (avec phase, adr auto-détectés)
- command.txt      : commande exacte exécutée
- report.md        : résumé lisible markdown

Approche :
- Zéro instrumentation intrusive (conftest, fixtures)
- Passif : ne modifie pas le comportement des tests
- Générique : fonctionne avec n'importe quel subset de tests

Usage CMD :
    python tools\epp_test_runner.py -- tests\ -v
    python tools\epp_test_runner.py -- tests\test_adr010_consensus_meta.py -v
    python tools\epp_test_runner.py --label "audit-p0-fixes" -- tests\ -k "created_at or message_count"
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import re
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


# =========================
# Phase / ADR Detection
# =========================

def extract_phase(nodeid: str) -> Optional[str]:
    """
    Détecte la phase depuis le nodeid.
    Patterns : test_phase1_, test_phase2_, test_phase03_, test_phase3_, etc.
    Retourne : "phase1", "phase2", "phase3", "phase4", ou None
    """
    match = re.search(r'test_phase(\d+)', nodeid)
    if match:
        phase_num = match.group(1).lstrip("0") or "0"
        if phase_num == "0":
            return None
        return f"phase{phase_num}"
    return None


def extract_adr(nodeid: str) -> Optional[str]:
    """
    Détecte l'ADR depuis le nodeid.
    Patterns : test_adr010_, test_adr011_, test_adr018_, etc.
    Retourne : "adr010", "adr011", ..., ou None
    """
    match = re.search(r'test_(adr\d{3})', nodeid)
    if match:
        return match.group(1)
    return None


class Tee:
    """Duplique stdout/stderr vers la console ET vers un fichier."""

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


# =========================
# Test Record
# =========================

@dataclass
class TestRecord:
    """Enregistrement d'un test individuel."""
    nodeid: str
    phases: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    final_outcome: Optional[str] = None
    duration_total: float = 0.0
    longrepr: Optional[str] = None
    keywords: List[str] = field(default_factory=list)

    # V1 enrichissements : auto-détection passive
    phase: Optional[str] = None
    adr: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodeid": self.nodeid,
            "final_outcome": self.final_outcome,
            "duration_total": round(self.duration_total, 6),
            "phases": self.phases,
            "longrepr": self.longrepr,
            "keywords": self.keywords,
            "phase": self.phase,
            "adr": self.adr,
        }


# =========================
# Recorder Plugin
# =========================

class RecorderPlugin:
    """Plugin pytest pour capturer les résultats."""

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
        self.collected_total = int(getattr(session, "testscollected", 0) or 0)
        self.selected_total = len(getattr(session, "items", []) or [])

        for item in getattr(session, "items", []):
            record = self._get_record(item.nodeid)

            # Auto-detect phase and adr
            record.phase = extract_phase(item.nodeid)
            record.adr = extract_adr(item.nodeid)

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
        Déterminer l'outcome final d'un test.

        Priorité (inclusive, i.e., teardown failed > call passed) :
        1. setup failed → le reste n'est pas atteint
        2. teardown failed → override call passed
        3. call outcome (passed/failed)
        4. setup/teardown skipped/xfailed
        5. unknown
        """
        setup = record.phases.get("setup")
        call = record.phases.get("call")
        teardown = record.phases.get("teardown")

        # Setup failure = test ne s'est pas lancé
        if setup and setup["outcome"] == "failed":
            return "failed"
        if setup and setup["outcome"] in {"skipped", "xfailed", "xpassed"}:
            return setup["outcome"]

        # Teardown failure override le call (même si call passed)
        if teardown and teardown["outcome"] == "failed":
            return "failed"

        # Call outcome (si présent)
        if call:
            return call["outcome"]

        # Fallback : teardown skipped/xfailed
        if teardown and teardown["outcome"] in {"skipped", "xfailed", "xpassed"}:
            return teardown["outcome"]

        return "unknown"

    def build_summary(self, pytest_args: List[str], run_id: str, wrapper_error: Optional[str] = None) -> Dict[str, Any]:
        outcome_counts = Counter(
            record.final_outcome or "unknown" for record in self.tests.values()
        )

        proof_usable = True
        proof_notes: List[str] = []

        if self.selected_total == 0:
            proof_usable = False
            proof_notes.append("0 tests selected: run non-probant")

        if self.collection_errors:
            proof_usable = False
            proof_notes.append("collection errors detected")

        if self.internal_errors:
            proof_usable = False
            proof_notes.append("pytest internal errors detected")

        if wrapper_error:
            proof_usable = False
            proof_notes.append(f"wrapper error: {wrapper_error.split(chr(10))[0]}")

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
            "wrapper_error": wrapper_error,
        }


# =========================
# Report Generation
# =========================

def build_markdown_report(
    summary: Dict[str, Any],
    tests: Dict[str, TestRecord]
) -> str:
    """Génère un rapport Markdown lisible."""

    lines = []

    # Calculate duration
    try:
        from datetime import datetime
        start_dt = datetime.fromisoformat(summary['started_at'].replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(summary['finished_at'].replace('Z', '+00:00'))
        duration = (end_dt - start_dt).total_seconds()
        duration_str = f"{duration:.1f}s"
    except Exception:
        duration_str = "(calculation error)"

    # Header
    lines.append("# EPP_Verdict Test Report")
    lines.append(f"\n**Run ID:** `{summary['run_id']}`")
    lines.append(f"**Started:** {summary['started_at']}")
    lines.append(f"**Duration:** {duration_str}")

    # Proof usability warning
    if not summary["proof_usable"]:
        lines.append("\n⚠️ **WARNING: Run non-probant**")
        for note in summary["proof_notes"]:
            lines.append(f"  - {note}")
    else:
        lines.append("\n✅ Run probant")

    # Global metrics
    lines.append("\n## Summary")
    lines.append(f"- **Collected:** {summary['collected_total']} tests")
    lines.append(f"- **Selected:** {summary['selected_total']} tests")
    lines.append(f"- **Deselected:** {summary['deselected_total']} tests")
    lines.append(f"- **Exit code:** {summary['exit_code']}")

    outcomes = summary.get("test_outcomes", {})
    lines.append("\n### Outcomes")
    for outcome, count in sorted(outcomes.items()):
        symbol = "✅" if outcome == "passed" else "❌" if outcome == "failed" else "⏭️" if outcome in ("skipped", "xfailed") else "❓"
        lines.append(f"- {symbol} **{outcome.upper()}:** {count}")

    # Command
    lines.append("\n## Command Executed")
    lines.append(f"\n```cmd\npytest {' '.join(summary['pytest_args'])}\n```")

    # Phase breakdown
    phases = {}
    for record in tests.values():
        if record.phase:
            if record.phase not in phases:
                phases[record.phase] = {"passed": 0, "failed": 0, "skipped": 0, "xfailed": 0, "total": 0}
            phases[record.phase]["total"] += 1
            outcome = record.final_outcome or "unknown"
            if outcome in phases[record.phase]:
                phases[record.phase][outcome] += 1

    if phases:
        lines.append("\n## Phase Breakdown")
        lines.append("\n| Phase | Total | Passed | Failed | Skipped | Pass Rate |")
        lines.append("|-------|-------|--------|--------|---------|-----------|")
        for phase in sorted(phases.keys()):
            stats = phases[phase]
            passed = stats["passed"]
            total = stats["total"]
            fail = stats["failed"]
            skip = stats["skipped"]
            rate = f"{100*passed/total:.1f}%" if total > 0 else "N/A"
            lines.append(f"| {phase} | {total} | {passed} | {fail} | {skip} | {rate} |")

    # ADR breakdown
    adrs = {}
    for record in tests.values():
        if record.adr:
            if record.adr not in adrs:
                adrs[record.adr] = {"passed": 0, "failed": 0, "skipped": 0, "xfailed": 0, "total": 0}
            adrs[record.adr]["total"] += 1
            outcome = record.final_outcome or "unknown"
            if outcome in adrs[record.adr]:
                adrs[record.adr][outcome] += 1

    if adrs:
        lines.append("\n## ADR Breakdown")
        lines.append("\n| ADR | Total | Passed | Failed | Skipped | Pass Rate |")
        lines.append("|-----|-------|--------|--------|---------|-----------|")
        for adr in sorted(adrs.keys()):
            stats = adrs[adr]
            passed = stats["passed"]
            total = stats["total"]
            fail = stats["failed"]
            skip = stats["skipped"]
            rate = f"{100*passed/total:.1f}%" if total > 0 else "N/A"
            lines.append(f"| {adr} | {total} | {passed} | {fail} | {skip} | {rate} |")

    # Failed tests
    failed_tests = [r for r in tests.values() if r.final_outcome == "failed"]
    if failed_tests:
        lines.append("\n## Failed Tests")
        for record in sorted(failed_tests, key=lambda r: r.nodeid):
            lines.append(f"\n### {record.nodeid}")
            if record.longrepr:
                lines.append(f"\n```\n{record.longrepr[:500]}...\n```")

    # Skipped/Xfailed tests
    skipped_tests = [r for r in tests.values() if r.final_outcome in ("skipped", "xfailed")]
    if skipped_tests:
        lines.append("\n## Skipped / XFailed Tests")
        for record in sorted(skipped_tests, key=lambda r: r.nodeid):
            lines.append(f"- {record.nodeid} ({record.final_outcome})")

    # Environment
    lines.append("\n## Environment")
    env = summary["environment"]
    lines.append(f"- **Python:** {env['python'].split()[0]}")
    lines.append(f"- **Platform:** {env['platform']}")
    lines.append(f"- **CWD:** {env['cwd']}")

    return "\n".join(lines)


# =========================
# I/O
# =========================

def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


# =========================
# Main
# =========================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="EPP_Verdict Test Runner v1 — Wrapper passif pour pytest."
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
        print(r"Exemple: python tools\epp_test_runner.py -- tests\ -v")
        return 2

    stamp = local_run_stamp()
    label = safe_slug(args.label) if args.label else ""
    run_dir_name = f"{stamp}_{label}" if label else stamp
    run_dir = Path(args.results_root) / run_dir_name
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"ERREUR: Le répertoire {run_dir} existe déjà. Écrasement silencieux interdit.")
        print(f"         Purger manuellement ou utiliser un autre label.")
        return 2

    console_path = run_dir / "console.txt"
    summary_path = run_dir / "summary.json"
    results_path = run_dir / "results.jsonl"
    command_path = run_dir / "command.txt"
    report_path = run_dir / "report.md"

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
        print("EPP_VERDICT TEST RUNNER v1")
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

    summary = plugin.build_summary(pytest_args=pytest_args, run_id=run_id, wrapper_error=unexpected_error)

    if summary["selected_total"] == 0 and not args.allow_zero_selected:
        summary["wrapper_exit_code"] = 10
        final_exit_code = 10
    else:
        summary["wrapper_exit_code"] = exit_code
        final_exit_code = exit_code

    rows = []
    for nodeid in sorted(plugin.tests.keys()):
        record = plugin.tests[nodeid]
        row = record.to_dict()
        row["run_id"] = run_id
        row["timestamp"] = summary["finished_at"]
        rows.append(row)

    write_json(summary_path, summary)
    write_jsonl(results_path, rows)

    # Generate markdown report
    markdown_report = build_markdown_report(summary, plugin.tests)
    write_text(report_path, markdown_report)

    print(f"\n[✅ OK] Artefacts écrits dans : {run_dir}")
    print(f"     - {console_path.name}")
    print(f"     - {summary_path.name}")
    print(f"     - {results_path.name}")
    print(f"     - {command_path.name}")
    print(f"     - {report_path.name}")

    if not summary["proof_usable"]:
        print(f"\n[⚠️ WARNING] Run non-probant :")
        for note in summary["proof_notes"]:
            print(f"    - {note}")

    return final_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
