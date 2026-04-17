"""Tests Phase 1.4 -- CLI EPP."""

import pytest
from unittest.mock import AsyncMock, patch
from click.testing import CliRunner

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from cli.epp_cli import cli, get_frame, PREDEFINED_FRAMES
from services.esmm.pipeline import PipelineResult


def _mock_pipeline_result(question="test"):
    """Create a mock PipelineResult with no attestations."""
    return PipelineResult(
        run_id=1,
        question=question,
        attestations=[],
        triplets_extracted=0,
        triplets_attested=0,
        triplets_injected=0,
        duration_ms=100.0,
        errors=[],
    )


class TestCLIParsing:
    """Tests parsing des commandes CLI."""

    def test_cli_help(self):
        """--help fonctionne."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "EPP - Epistemic Proof Program CLI" in result.output

    def test_cli_version(self):
        """--version fonctionne."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_ask_help(self):
        """ask --help fonctionne."""
        runner = CliRunner()
        result = runner.invoke(cli, ["ask", "--help"])
        assert result.exit_code == 0
        assert "Run ESMM pipeline" in result.output

    def test_submit_help(self):
        """submit --help fonctionne."""
        runner = CliRunner()
        result = runner.invoke(cli, ["submit", "--help"])
        assert result.exit_code == 0
        assert "devnet" in result.output

    def test_query_help(self):
        """query --help fonctionne."""
        runner = CliRunner()
        result = runner.invoke(cli, ["query", "--help"])
        assert result.exit_code == 0
        assert "Search attestations" in result.output

    def test_graph_stats_help(self):
        """graph stats --help fonctionne."""
        runner = CliRunner()
        result = runner.invoke(cli, ["graph", "stats", "--help"])
        assert result.exit_code == 0

    def test_frame_list_help(self):
        """frame list --help fonctionne."""
        runner = CliRunner()
        result = runner.invoke(cli, ["frame", "list", "--help"])
        assert result.exit_code == 0


class TestAskCommand:
    """Tests commande ask."""

    @patch("cli.epp_cli._run_ask", new_callable=AsyncMock)
    def test_ask_basic(self, mock_ask):
        """ask basique fonctionne."""
        mock_ask.return_value = _mock_pipeline_result("Is Solana fast?")
        runner = CliRunner()
        result = runner.invoke(cli, ["ask", "Is Solana fast?"])
        assert result.exit_code == 0
        assert "Question: Is Solana fast?" in result.output
        assert "No attestations produced" in result.output or "Attestation" in result.output

    @patch("cli.epp_cli._run_ask", new_callable=AsyncMock)
    def test_ask_with_models(self, mock_ask):
        """ask avec --models fonctionne."""
        mock_ask.return_value = _mock_pipeline_result()
        runner = CliRunner()
        result = runner.invoke(cli, ["ask", "Test question", "--models", "5"])
        assert result.exit_code == 0
        assert "Models to consult: 5" in result.output

    @patch("cli.epp_cli._run_ask", new_callable=AsyncMock)
    def test_ask_with_frame(self, mock_ask):
        """ask avec --frame fonctionne."""
        mock_ask.return_value = _mock_pipeline_result()
        runner = CliRunner()
        result = runner.invoke(cli, [
            "ask", "Test question",
            "--frame", "blockchain_tps_v1.0"
        ])
        assert result.exit_code == 0
        assert "Frame: blockchain_tps_v1.0" in result.output

    def test_ask_invalid_frame(self):
        """ask avec frame invalide echoue proprement."""
        runner = CliRunner()
        result = runner.invoke(cli, [
            "ask", "Test question",
            "--frame", "invalid_frame"
        ])
        assert result.exit_code != 0
        assert "Unknown frame" in result.output

    @patch("cli.epp_cli._run_ask", new_callable=AsyncMock)
    def test_ask_json_output(self, mock_ask):
        """ask avec --output json fonctionne."""
        mock_ask.return_value = _mock_pipeline_result()
        runner = CliRunner()
        result = runner.invoke(cli, [
            "ask", "Test question",
            "--output", "json"
        ])
        assert result.exit_code == 0
        assert "claim_hash" in result.output or "No attestations produced" in result.output


class TestSubmitCommand:
    """Tests commande submit."""

    def test_submit_requires_devnet_flag(self):
        """submit echoue sans --devnet."""
        runner = CliRunner()
        result = runner.invoke(cli, ["submit"])
        assert result.exit_code != 0

    @patch("cli.epp_cli._run_submit", new_callable=AsyncMock)
    def test_submit_with_devnet(self, mock_submit):
        """submit avec --devnet fonctionne."""
        mock_submit.return_value = (
            {"claim_hash": "abc123", "subject": "Solana", "consensus_score": 0.85, "confidence_tier": "validated"},
            None,
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["submit", "--devnet"])
        assert result.exit_code == 0
        assert "DEVNET ONLY" in result.output
        assert "Attestation queued" in result.output

    def test_submit_dry_run(self):
        """submit --dry-run ne soumet pas."""
        runner = CliRunner()
        result = runner.invoke(cli, ["submit", "--devnet", "--dry-run"])
        assert result.exit_code == 0
        assert "DRY RUN" in result.output


class TestQueryCommand:
    """Tests commande query."""

    @patch("cli.epp_cli._run_query", new_callable=AsyncMock)
    def test_query_basic(self, mock_query):
        """query basique fonctionne."""
        mock_query.return_value = []
        runner = CliRunner()
        result = runner.invoke(cli, ["query", "solana"])
        assert result.exit_code == 0
        assert "Querying attestations" in result.output

    @patch("cli.epp_cli._run_query", new_callable=AsyncMock)
    def test_query_with_min_confidence(self, mock_query):
        """query avec --min-confidence fonctionne."""
        mock_query.return_value = []
        runner = CliRunner()
        result = runner.invoke(cli, ["query", "solana", "--min-confidence", "0.8"])
        assert result.exit_code == 0
        assert "80%" in result.output


class TestFrameCommands:
    """Tests commandes frame."""

    def test_frame_list(self):
        """frame list affiche les frames."""
        runner = CliRunner()
        result = runner.invoke(cli, ["frame", "list"])
        assert result.exit_code == 0
        assert "blockchain_tps_v1.0" in result.output
        assert "general_knowledge_v1.0" in result.output

    def test_frame_show_valid(self):
        """frame show avec ID valide fonctionne."""
        runner = CliRunner()
        result = runner.invoke(cli, ["frame", "show", "blockchain_tps_v1.0"])
        assert result.exit_code == 0
        assert "blockchain_metrics" in result.output
        assert "transactions_per_second" in result.output

    def test_frame_show_invalid(self):
        """frame show avec ID invalide echoue proprement."""
        runner = CliRunner()
        result = runner.invoke(cli, ["frame", "show", "invalid_frame"])
        assert result.exit_code != 0
        assert "Unknown frame" in result.output

    def test_frame_show_json(self):
        """frame show --output json fonctionne."""
        runner = CliRunner()
        result = runner.invoke(cli, ["frame", "show", "blockchain_tps_v1.0", "-o", "json"])
        assert result.exit_code == 0
        assert '"frame_id"' in result.output


class TestGraphCommands:
    """Tests commandes graph."""

    @patch("cli.epp_cli._run_graph_stats", new_callable=AsyncMock)
    def test_graph_stats(self, mock_stats):
        """graph stats fonctionne."""
        mock_stats.return_value = {
            "concepts": 10, "relations": 5, "attestations": 3,
            "attestations_anchored": 0, "esmm_runs": 1,
            "cochain_entries": 2, "db_size_mb": 0.1,
        }
        runner = CliRunner()
        result = runner.invoke(cli, ["graph", "stats"])
        assert result.exit_code == 0
        assert "Knowledge Graph Statistics" in result.output


class TestHelpers:
    """Tests fonctions utilitaires."""

    def test_get_frame_valid(self):
        """get_frame retourne un frame valide."""
        frame = get_frame("blockchain_tps_v1.0")
        assert frame is not None
        assert frame.frame_id == "blockchain_tps_v1.0"

    def test_get_frame_invalid(self):
        """get_frame retourne None pour frame invalide."""
        frame = get_frame("invalid_frame")
        assert frame is None

    def test_predefined_frames_not_empty(self):
        """PREDEFINED_FRAMES n'est pas vide."""
        assert len(PREDEFINED_FRAMES) >= 2
