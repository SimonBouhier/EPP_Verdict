"""Tests Phase 3 — CLI DB integration (query, graph stats, submit)."""
# AUTO — permet `python tests/test_X.py` direct (cf. tests/_runner.py).
import sys as _epp_sys
import pathlib as _epp_pathlib
_epp_sys.path.insert(0, str(_epp_pathlib.Path(__file__).resolve().parent.parent))
del _epp_sys, _epp_pathlib


import pytest
from unittest.mock import AsyncMock, patch
from click.testing import CliRunner

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from cli.epp_cli import cli


class TestAskCommandExists:

    def test_ask_command_exists(self):
        """The 'ask' command is registered in the CLI group."""
        assert "ask" in cli.commands

    def test_query_command_exists(self):
        """The 'query' command is registered."""
        assert "query" in cli.commands

    def test_submit_command_exists(self):
        """The 'submit' command is registered."""
        assert "submit" in cli.commands


class TestQueryReadsDB:

    @patch("cli.epp_cli._run_query", new_callable=AsyncMock)
    def test_query_reads_db(self, mock_query):
        """query returns attestations from the DB."""
        mock_query.return_value = [
            {
                "claim_hash": "abc123def456",
                "subject": "Solana",
                "predicate": "has_tps",
                "object": "65000",
                "consensus_score": 0.85,
                "confidence_tier": "validated",
            }
        ]
        runner = CliRunner()
        result = runner.invoke(cli, ["query", "Solana"])
        assert result.exit_code == 0
        assert "Found 1 attestation(s)" in result.output
        assert "Solana" in result.output

    @patch("cli.epp_cli._run_query", new_callable=AsyncMock)
    def test_query_empty_results(self, mock_query):
        """query with no results shows appropriate message."""
        mock_query.return_value = []
        runner = CliRunner()
        result = runner.invoke(cli, ["query", "unknown"])
        assert result.exit_code == 0
        assert "No attestations found" in result.output


class TestGraphStatsReturnsNumbers:

    @patch("cli.epp_cli._run_graph_stats", new_callable=AsyncMock)
    def test_graph_stats_returns_numbers(self, mock_stats):
        """graph stats returns counters from DB."""
        mock_stats.return_value = {
            "concepts": 42, "relations": 18, "attestations": 5,
            "attestations_anchored": 1, "esmm_runs": 3,
            "cochain_entries": 10, "db_size_mb": 0.25,
        }
        runner = CliRunner()
        result = runner.invoke(cli, ["graph", "stats"])
        assert result.exit_code == 0
        assert "42" in result.output
        assert "18" in result.output
        assert "5" in result.output


class TestSubmitQueuesAttestation:

    @patch("cli.epp_cli._run_submit", new_callable=AsyncMock)
    def test_submit_queues_attestation(self, mock_submit):
        """submit updates status to 'queued'."""
        mock_submit.return_value = (
            {
                "claim_hash": "abc123def456",
                "subject": "Solana",
                "consensus_score": 0.9,
                "confidence_tier": "validated",
            },
            None,
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["submit", "--devnet"])
        assert result.exit_code == 0
        assert "queued" in result.output

    @patch("cli.epp_cli._run_submit", new_callable=AsyncMock)
    def test_submit_without_hash_uses_latest(self, mock_submit):
        """submit without --claim-hash uses latest attestation."""
        mock_submit.return_value = (
            {
                "claim_hash": "latest_hash_xyz",
                "subject": "Bitcoin",
                "consensus_score": 0.75,
                "confidence_tier": "proposition",
            },
            None,
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["submit", "--devnet"])
        assert result.exit_code == 0
        assert "latest_hash_xyz" in result.output

    @patch("cli.epp_cli._run_submit", new_callable=AsyncMock)
    def test_submit_no_attestation_error(self, mock_submit):
        """submit with no attestation found shows error."""
        mock_submit.return_value = (None, "No attestation found")
        runner = CliRunner()
        result = runner.invoke(cli, ["submit", "--devnet"])
        assert result.exit_code != 0


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
