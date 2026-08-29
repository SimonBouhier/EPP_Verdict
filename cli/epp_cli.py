"""
EPP CLI -- Command-line interface for the Epistemic Proof Program.

Usage:
    epp ask "question" --models N --frame ID
    epp submit --devnet
    epp query "subject" --min-confidence X
    epp graph stats
    epp frame list
    epp frame show ID
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click

# Add project root to path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from services.metrology import (
    MetrologicalFrame,
    PREDEFINED_FRAMES,
)
from services.esmm.attestation import (
    EpistemicAttestation, Signature5D, ModelVote, crystallize,
)



def get_frame(frame_id: str) -> Optional[MetrologicalFrame]:
    """Get a predefined frame by ID."""
    factory = PREDEFINED_FRAMES.get(frame_id)
    if factory:
        return factory()
    return None


# === SECURITY WARNING ===
DEVNET_WARNING = """
WARNING: DEVNET ONLY
This is an experimental sandbox. Not for production use.
See AUDIT_REQUIRED markers in the codebase.
"""


@click.group()
@click.version_option(version="0.1.0", prog_name="epp")
def cli():
    """EPP - Epistemic Proof Program CLI.

    Submit questions to the ESMM pipeline, post attestations on-chain,
    and query existing attestations.
    """
    pass


@cli.command()
@click.argument("question")
@click.option("--models", "-m", default=3, help="Number of models to consult")
@click.option("--frame", "-f", default="general_knowledge_v1.0", help="Metrological frame ID")
@click.option("--output", "-o", type=click.Choice(["json", "text"]), default="text")
def ask(question: str, models: int, frame: str, output: str):
    """Run ESMM pipeline on a question.

    Example:
        epp ask "Solana effective TPS exceeds 3000" --models 3 --frame blockchain_tps_v1.0
    """
    click.echo(f"Question: {question}")
    click.echo(f"Models to consult: {models}")
    click.echo(f"Frame: {frame}")
    click.echo()

    # Validate frame
    met_frame = get_frame(frame)
    if met_frame is None:
        click.echo(f"Error: Unknown frame '{frame}'", err=True)
        click.echo(f"Available frames: {', '.join(PREDEFINED_FRAMES.keys())}", err=True)
        sys.exit(1)

    click.echo(f"Frame hash: {met_frame.compute_frame_hash()[:16]}...")
    click.echo()

    # Run the actual pipeline
    result = asyncio.run(_run_ask(question, models, frame))

    if result.errors:
        click.echo(f"Pipeline completed with {len(result.errors)} error(s):", err=True)
        for err in result.errors:
            click.echo(f"  - {err}", err=True)

    if not result.attestations:
        click.echo("No attestations produced.")
        click.echo("(This may mean no providers are configured, or consensus was too low.)")
        return

    for att in result.attestations:
        if output == "json":
            click.echo(att.to_portable_json())
        else:
            click.echo(f"Attestation [{att.confidence_tier.upper()}]:")
            click.echo(f"  Claim: {att.subject} -> {att.predicate} -> {att.object}")
            click.echo(f"  Hash: {att.claim_hash[:16]}...")
            click.echo(f"  Consensus: {att.consensus_score:.2%}")
            click.echo(f"  Models: {att.models_agreeing}/{att.models_consulted}")
            click.echo(f"  Tier: {att.confidence_tier}")
            click.echo()

    click.echo(f"Pipeline: {result.triplets_extracted} extracted -> "
               f"{result.triplets_attested} attested -> "
               f"{result.triplets_injected} injected to graph")
    click.echo(f"Duration: {result.duration_ms:.0f}ms")
    click.echo()
    click.echo("Use 'epp submit --devnet' to anchor on-chain.")


async def _run_ask(question: str, models: int, frame: str):
    """Helper async pour exécuter le pipeline."""
    from database.engine import get_db
    from services.esmm.pipeline import run_pipeline, PipelineConfig
    from services.esmm.orchestrator import ESMMRunConfig
    from services.config_loader import get_section

    selected_models = get_section("esmm", {}).get(
        "models", ["mistral:7b", "llama3.1:8b", "qwen2.5:7b"]
    )[:models]
    esmm_config = ESMMRunConfig(
        models=selected_models,
        input_mode="verify",
        original_claim=question,
    )

    db = await get_db()
    config = PipelineConfig(metrological_frame=frame)
    return await run_pipeline(
        question=question,
        db=db,
        config=config,
        esmm_config=esmm_config,
    )


@cli.command()
@click.option("--devnet", is_flag=True, required=True, help="Required flag to confirm devnet submission")
@click.option("--claim-hash", help="Claim hash to submit (from last 'epp ask')")
@click.option("--dry-run", is_flag=True, help="Simulate without actual submission")
def submit(devnet: bool, claim_hash: Optional[str], dry_run: bool):
    """Post an attestation on-chain (devnet only).

    Example:
        epp submit --devnet
        epp submit --devnet --claim-hash abc123...
    """
    if not devnet:
        click.echo("Error: --devnet flag is required for submission", err=True)
        sys.exit(1)

    click.echo(DEVNET_WARNING)

    if dry_run:
        click.echo("[DRY RUN] Would submit attestation to devnet")
        click.echo("[DRY RUN] No actual transaction sent")
        return

    att, error = asyncio.run(_run_submit(claim_hash))
    if error:
        click.echo(f"Error: {error}", err=True)
        sys.exit(1)

    click.echo("Attestation queued for on-chain anchoring.")
    click.echo(f"  Claim hash: {att['claim_hash']}")
    click.echo(f"  Subject: {att.get('subject', 'N/A')}")
    click.echo(f"  Consensus: {att.get('consensus_score', 0):.2%}")
    click.echo(f"  Tier: {att.get('confidence_tier', 'N/A')}")
    click.echo(f"  Status: queued")


async def _run_submit(claim_hash=None):
    """Load attestation from DB and queue for submission."""
    from database.engine import get_db

    db = await get_db()
    if claim_hash is None:
        att = await db.get_latest_attestation()
        if att is None:
            return None, "No attestation found"
        claim_hash = att["claim_hash"]

    att = await db.get_attestation_by_hash(claim_hash)
    if att is None:
        return None, f"Attestation {claim_hash} not found"

    await db.update_attestation_submission_status(claim_hash, "queued")
    return att, None


@cli.command()
@click.argument("subject")
@click.option("--min-confidence", "-c", default=0.0, type=float, help="Minimum consensus score (0-1)")
@click.option("--on-chain", is_flag=True, help="Search on-chain (devnet)")
@click.option("--local", is_flag=True, default=True, help="Search local DB")
@click.option("--output", "-o", type=click.Choice(["json", "text"]), default="text")
def query(subject: str, min_confidence: float, on_chain: bool, local: bool, output: str):
    """Search attestations by subject.

    Example:
        epp query "solana" --min-confidence 0.8
        epp query "blockchain" --on-chain
    """
    click.echo(f"Querying attestations for subject: {subject}")
    click.echo(f"Minimum confidence: {min_confidence:.0%}")
    click.echo(f"Search: {'on-chain + local' if on_chain else 'local only'}")
    click.echo()

    attestations = asyncio.run(_run_query(subject, min_confidence))

    if not attestations:
        click.echo("No attestations found matching criteria.")
        return

    click.echo(f"Found {len(attestations)} attestation(s):")
    click.echo()
    for att in attestations:
        if output == "json":
            click.echo(json.dumps(att, default=str, indent=2))
        else:
            click.echo(f"  [{att.get('confidence_tier', 'N/A').upper()}] "
                       f"{att.get('subject', '')} -> {att.get('predicate', '')} -> {att.get('object', '')}")
            click.echo(f"    Consensus: {att.get('consensus_score', 0):.2%}")
            click.echo(f"    Hash: {att.get('claim_hash', '')[:16]}...")
            click.echo()


async def _run_query(subject, min_confidence):
    """Query attestations from DB."""
    from database.engine import get_db

    db = await get_db()
    return await db.get_attestations_by_subject(subject, min_confidence)


@cli.group()
def graph():
    """Graph operations and statistics."""
    pass


@graph.command("stats")
def graph_stats():
    """Display knowledge graph statistics.

    Example:
        epp graph stats
    """
    click.echo("Knowledge Graph Statistics")
    click.echo("=" * 40)
    click.echo()

    stats = asyncio.run(_run_graph_stats())

    click.echo(f"  Total concepts: {stats.get('concepts', 0)}")
    click.echo(f"  Total relations: {stats.get('relations', 0)}")
    click.echo(f"  Total attestations: {stats.get('attestations', 0)}")
    click.echo(f"  Anchored on-chain: {stats.get('attestations_anchored', 0)}")
    click.echo()
    click.echo(f"  ESMM runs: {stats.get('esmm_runs', 0)}")
    click.echo(f"  Cochain entries: {stats.get('cochain_entries', 0)}")
    click.echo(f"  DB size: {stats.get('db_size_mb', 0):.2f} MB")


async def _run_graph_stats():
    """Get graph stats from DB."""
    from database.engine import get_db

    db = await get_db()
    stats = await db.get_stats()
    attestation_count = await db.get_attestation_count()
    stats["attestations"] = attestation_count
    return stats


@cli.group()
def models():
    """Model performance and statistics."""
    pass


@models.command("stats")
def models_stats():
    """Display model Brier scores and computed weights.

    Example:
        epp models stats
    """
    click.echo("Model Performance Dashboard")
    click.echo("=" * 72)
    click.echo()

    stats = asyncio.run(_run_models_stats())

    if not stats:
        click.echo("  No resolved predictions yet. Models start with weight 1.0 (cold start).")
        click.echo()
        return

    # Table header
    click.echo(f"  {'Model':<25} | {'Predictions':>11} | {'Resolved':>8} | {'Avg Brier':>9} | {'Weight':>6}")
    click.echo(f"  {'-'*25}-+-{'-'*11}-+-{'-'*8}-+-{'-'*9}-+-{'-'*6}")

    for s in stats:
        model_display = s["model_id"][:25]
        click.echo(
            f"  {model_display:<25} | {s['total_predictions']:>11} | "
            f"{s['resolved_predictions']:>8} | {s['avg_brier_score']:>9.4f} | "
            f"{s['weight']:>6.2f}"
        )

    click.echo()


async def _run_models_stats():
    """Get all model Brier stats from DB."""
    from database.engine import get_db

    db = await get_db()
    return await db.get_all_model_brier_scores()


@cli.group()
def frame():
    """Metrological frame management."""
    pass


@frame.command("list")
def frame_list():
    """List available metrological frames.

    Example:
        epp frame list
    """
    click.echo("Available Metrological Frames")
    click.echo("=" * 40)
    click.echo()

    for frame_id, factory in PREDEFINED_FRAMES.items():
        f = factory()
        click.echo(f"  {frame_id}")
        click.echo(f"    Domain: {f.domain}")
        click.echo(f"    Metric: {f.metric}")
        click.echo(f"    Hash: {f.compute_frame_hash()[:16]}...")
        click.echo()


@frame.command("show")
@click.argument("frame_id")
@click.option("--output", "-o", type=click.Choice(["json", "text"]), default="text")
def frame_show(frame_id: str, output: str):
    """Display a metrological frame in detail.

    Example:
        epp frame show blockchain_tps_v1.0
    """
    f = get_frame(frame_id)
    if f is None:
        click.echo(f"Error: Unknown frame '{frame_id}'", err=True)
        click.echo(f"Available frames: {', '.join(PREDEFINED_FRAMES.keys())}", err=True)
        sys.exit(1)

    if output == "json":
        click.echo(f.to_canonical_json())
    else:
        click.echo(f"Metrological Frame: {f.frame_id}")
        click.echo("=" * 40)
        click.echo()
        click.echo(f"  Version: {f.version}")
        click.echo(f"  Domain: {f.domain}")
        click.echo(f"  Metric: {f.metric}")
        click.echo(f"  Required sources: {f.required_sources}")
        click.echo()
        click.echo(f"  Description:")
        click.echo(f"    {f.description}")
        click.echo()
        click.echo(f"  Parameters:")
        for k, v in f.parameters.items():
            click.echo(f"    {k}: {v}")
        click.echo()
        click.echo(f"  Governance:")
        click.echo(f"    Current authority: {f.governance.current_authority}")
        click.echo(f"    Target authority: {f.governance.target_authority}")
        click.echo()
        click.echo(f"  Frame hash: {f.compute_frame_hash()}")


@cli.command("verify-rwa")
@click.option(
    "--source",
    required=True,
    type=click.Choice(["opensanctions", "ofac_sdn", "eu_cfsp", "verra_vcs"]),
    help="Source autoritaire à interroger (ADR-012)",
)
@click.option("--entity", required=True, help="Entité à vérifier (nom ou numéro de série)")
@click.option(
    "--frame",
    required=True,
    type=click.Choice([
        "compliance_sanctions_v1.0",
        "carbon_credits_vcs_v1.0",
        "rwa_identity_v1.0",
    ]),
    help="Frame métrologique applicable",
)
@click.pass_context
def verify_rwa(ctx: click.Context, source: str, entity: str, frame: str) -> None:
    """
    Vérification déterministe d'un claim via source autoritaire externe (ADR-012).

    Bypass complet de l'ESMM — la source fait foi.
    Le source_anchor (SHA-256 de la réponse brute) est ancré on-chain.

    \b
    Exemples :
      epp verify-rwa --source opensanctions --entity "Acme Corp" --frame compliance_sanctions_v1.0
      epp verify-rwa --source verra_vcs --entity "VCU-123456" --frame carbon_credits_vcs_v1.0
    """
    asyncio.run(_run_verify_rwa(ctx, source, entity, frame))


async def _run_verify_rwa(
    ctx: click.Context, source: str, entity: str, frame: str
) -> None:
    from database.engine import ISpaceDB
    from database.pool import ConnectionPool
    from services.esmm.pipeline import run_pipeline
    from services.esmm.orchestrator import ESMMRunConfig, ClaimNature
    from services.esmm.source_anchor_builder import SourceAnchorSpec

    db_path = ctx.obj.get("db_path", "data/epp.db") if ctx.obj else "data/epp.db"

    # Construire query selon la source
    query: dict = {"name": entity}
    if source == "verra_vcs":
        # serial ou project_id selon le format de l'entité
        if entity.upper().startswith("VCU-"):
            query = {"serial": entity}
        else:
            query = {"project_id": entity}

    spec = SourceAnchorSpec(
        source_id=source,
        frame_id=frame,
        query=query,
    )
    esmm_config = ESMMRunConfig(
        models=[],
        claim_nature=ClaimNature.DETERMINISTIC,
        source_anchor_spec=spec,
    )

    click.echo(f"[verify-rwa] Source: {source} | Entity: {entity} | Frame: {frame}")
    click.echo("[verify-rwa] Fetching from authoritative source...")

    try:
        async with ISpaceDB(db_path) as db:
            result = await run_pipeline(
                question=entity,
                db=db,
                esmm_config=esmm_config,
                metrological_frame=frame,
            )

        if result.attestations:
            att = result.attestations[0]
            click.echo(f"\n[verify-rwa] Result: {att.object} (score: {att.consensus_score:.3f})")
            click.echo(f"[verify-rwa] Source anchor: {att.source_anchor}")
            click.echo(f"[verify-rwa] Confidence tier: {att.confidence_tier}")
        else:
            click.echo("[verify-rwa] No attestation produced.")
            if result.errors:
                for err in result.errors:
                    click.echo(f"  Error: {err}", err=True)
    except Exception as exc:
        click.echo(f"[verify-rwa] Failed: {exc}", err=True)
        raise SystemExit(1)


@cli.command("audit")
@click.argument("contract_path", type=click.Path(exists=True))
@click.option("--frame", "-f", default="smartcontract_audit_v1.0", help="Metrological frame ID")
@click.option("--models", "-m", default=3, help="Number of models")
@click.option("--slither/--no-slither", default=False, help="Use Slither for static pre-analysis")
@click.option("--output", "-o", type=click.Choice(["json", "text"]), default="text")
def audit(contract_path: str, frame: str, models: int, slither: bool, output: str):
    """Run epistemic audit on a smart contract.

    Example:
        epp audit contracts/TokenVault.sol --models 3
    """
    from services.config_loader import get_value

    enabled = get_value("audit", "enabled", True)
    if not enabled:
        click.echo("Error: audit is disabled in config.yaml (audit.enabled: false)", err=True)
        sys.exit(1)

    result = asyncio.run(_run_audit(contract_path, frame, models, slither, output))

    if output == "json":
        import dataclasses
        click.echo(json.dumps({
            "contract_path": result.contract_path,
            "contract_hash": result.contract_hash,
            "contract_name": result.contract_name,
            "aggregate_severity": result.aggregate_severity,
            "aggregate_consensus": result.aggregate_consensus,
            "total_vulnerabilities": result.total_vulnerabilities,
            "total_units_audited": result.total_units_audited,
            "total_units_skipped": result.total_units_skipped,
            "duration_ms": result.duration_ms,
            "errors": result.errors,
        }, indent=2))
    else:
        click.echo(f"Contract: {result.contract_name} ({result.contract_hash[:8]}...)")
        click.echo(
            f"Aggregate severity: {result.aggregate_severity.upper()} "
            f"| Consensus: {result.aggregate_consensus:.2f}"
        )
        click.echo(
            f"Audited: {result.total_units_audited} units "
            f"| Skipped: {result.total_units_skipped}"
        )
        click.echo(f"Vulnerabilities: {result.total_vulnerabilities}")
        click.echo(f"Duration: {result.duration_ms:.0f}ms")
        click.echo()
        click.echo("Units:")
        for r in result.unit_results:
            unit = r["unit"]
            severity = r["severity"]
            pipeline_res = r["pipeline_result"]
            consensus = (
                pipeline_res.attestations[0].consensus_score
                if pipeline_res.attestations else 0.0
            )
            click.echo(
                f"  [{severity.upper():>13}] {unit.unit_name:<30} "
                f"— confidence: {consensus:.2f}"
            )


async def _run_audit(
    contract_path: str,
    frame: str,
    models: int,
    slither: bool,
    output: str,
):
    """Helper async pour exécuter l'audit."""
    from database.engine import ISpaceDB
    from services.audit.audit_runner import run_audit
    from services.config_loader import get_section, get_value

    # DB isolée (jamais le singleton get_db() !)
    audit_db_path = get_value("audit", "db_path", "data/epp_audit_devnet.db")
    db = ISpaceDB(audit_db_path)
    await db.initialize()

    selected_models = get_section("esmm", {}).get(
        "models", ["mistral:7b", "llama3.1:8b", "qwen2.5:7b"]
    )[:models]

    return await run_audit(
        contract_path=contract_path,
        db=db,
        models=selected_models,
        frame=frame,
        use_slither=slither,
        use_cache=True,
    )


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
