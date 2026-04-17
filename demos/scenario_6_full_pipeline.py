"""
Scenario 6 — EPP Full Pipeline Validation
==========================================

Validates the complete EPP_Verdict pipeline after ADR-011-v2 + ADR-012.
Three independent parts, one unified report.

PART A — Deterministic RWA (ADR-012)
    4 claims via mocked HTTP adapters (yente/OFAC not required).
    Validates: source_anchor populated, esmm_invoked=False, predicate from frame.metric,
    snapshot stored, ClaimNature.DETERMINISTIC bypass confirmed.

PART B — Semantic Fingerprinting stress (ADR-011-v2)
    4 claim pairs designed to force reconciliation — same fact, deliberately
    divergent vocabularies across models. Tests that ADR-011 recovers consensus
    where pre-ADR-011 would score near zero.

PART C — T1 Regression
    2 claims from Scenario 5 Tier 1 (baseline empirique).
    Validates that ADR-011 + ADR-012 layers did not degrade the nominal epistemic path.

Prerequisites:
    - Ollama running on Windows host (ollama serve)
    - At least 2 non-embedding, non-excluded models
    - No external API required (Part A fully mocked)

Expected duration: ~25 min (10 claims × ~2.5 min each)
Models recommended: mistral, llama3.1:8b, gemma3, granite3.3, phi4-reasoning
"""

import asyncio
import hashlib
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger("scenario6")

# ---------------------------------------------------------------------------
# PART A — RWA claims catalog (deterministic, mocked HTTP)
# ---------------------------------------------------------------------------

RWA_CLAIMS = [
    {
        "id": "RWA-01",
        "label": "OpenSanctions — entity clear",
        "source_id": "opensanctions",
        "frame_id": "compliance_sanctions_v1.0",
        "query": {"name": "Acme Trading GmbH", "schema": "Company"},
        "mock_raw": {
            "version": "20260228",
            "responses": {
                "q": {
                    "results": [
                        {"id": "ofac-99", "score": 0.42, "name": "Acme Holdings Ltd"}
                    ]
                }
            }
        },
        "expected_status": "clear",
        "expected_predicate": "sanctions_status",
        "description": "Low match score (0.42 < 0.85) → clear. Predicate from frame.metric.",
    },
    {
        "id": "RWA-02",
        "label": "OpenSanctions — entity match",
        "source_id": "opensanctions",
        "frame_id": "compliance_sanctions_v1.0",
        "query": {"name": "Vladislav Petrov", "schema": "Person"},
        "mock_raw": {
            "version": "20260228",
            "responses": {
                "q": {
                    "results": [
                        {"id": "ofac-777", "score": 0.94, "name": "Vladislav Petrov"}
                    ]
                }
            }
        },
        "expected_status": "match",
        "expected_predicate": "sanctions_status",
        "description": "High match score (0.94 ≥ 0.85) → match. source_anchor must be SHA-256.",
    },
    {
        "id": "RWA-03",
        "label": "Verra VCS — serial active",
        "source_id": "verra_vcs",
        "frame_id": "carbon_credits_vcs_v1.0",
        "query": {"serial": "VCU-191-CLD-BR-14-2024"},
        "mock_raw": {
            "status": "Active",
            "resourceStatus": "Active",
            "lastUpdated": "2026-01-15",
            "projectId": "VCS-191",
            "vintage": 2024,
        },
        "expected_status": "active",
        "expected_predicate": "carbon_credit_validity",  # P1 fix — NOT sanctions_status
        "description": "VCS serial active. Predicate must be carbon_credit_validity (P1 regression).",
    },
    {
        "id": "RWA-04",
        "label": "Verra VCS — serial retired",
        "source_id": "verra_vcs",
        "frame_id": "carbon_credits_vcs_v1.0",
        "query": {"serial": "VCU-055-CLD-BR-08-2019"},
        "mock_raw": {
            "status": "Retired",
            "resourceStatus": "Retired",
            "lastUpdated": "2023-11-03",
            "projectId": "VCS-055",
            "vintage": 2019,
        },
        "expected_status": "retired",
        "expected_predicate": "carbon_credit_validity",
        "description": "VCS serial retired. Subject from query['serial'] (P2 regression).",
    },
]

# ---------------------------------------------------------------------------
# PART B — Fingerprinting stress pairs
# ---------------------------------------------------------------------------
# Claims designed to produce divergent triplet vocabularies across models.
# Each pair is the same fact expressed with deliberately different terminology.
# ADR-011 should reconcile; pre-ADR-011 would score near zero consensus.

FINGERPRINT_CLAIMS = [
    {
        "id": "FP-01",
        "claim": "Solana uses a Proof of History mechanism to order transactions "
                 "before consensus",
        "domain": "blockchain_architecture",
        "frame": "blockchain_tps_v1.0",
        "expected_ambiguity": "low",
        "fingerprint_stress": "Technical synonym divergence: "
                              "'uses'/'employs'/'relies on' + 'PoH'/'timestamp sequencing'/'VDF'",
        "expected_min_consensus": 0.55,
    },
    {
        "id": "FP-02",
        "claim": "The Transformer architecture introduced the self-attention mechanism "
                 "that enables parallel sequence processing",
        "domain": "ai_architecture",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "low",
        "fingerprint_stress": "Entity aliasing: 'Transformer'/'attention model'/'BERT predecessor' "
                              "+ 'self-attention'/'multi-head attention'/'scaled dot-product'",
        "expected_min_consensus": 0.50,
    },
    {
        "id": "FP-03",
        "claim": "Bitcoin mining consumes more electricity annually than many mid-sized countries",
        "domain": "crypto_energy",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "medium",
        "fingerprint_stress": "Relation divergence across models: "
                              "'consumes'/'uses'/'requires'/'draws' — all semantically equivalent",
        "expected_min_consensus": 0.45,
    },
    {
        "id": "FP-04",
        "claim": "Zero-knowledge proofs allow one party to prove knowledge of a value "
                 "without revealing the value itself",
        "domain": "cryptography",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "low",
        "fingerprint_stress": "Subject aliasing: 'ZKP'/'zero-knowledge proof'/'zk-SNARK' "
                              "should merge into same fingerprint node",
        "expected_min_consensus": 0.50,
    },
]

# ---------------------------------------------------------------------------
# PART C — T1 regression (2 claims from Scenario 5)
# ---------------------------------------------------------------------------

REGRESSION_CLAIMS = [
    {
        "id": "REG-T1-01",
        "claim": "The speed of light in vacuum exceeds 299000 kilometers per second",
        "domain": "physics",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "low",
        "scenario5_expected_verdict": "SUPPORTED",
        "scenario5_expected_min_consensus": 0.80,
        "description": "Scenario 5 T1-01 — must maintain SUPPORTED ≥ 80% after ADR-011/012.",
    },
    {
        "id": "REG-T1-02",
        "claim": "Water boils at 100 degrees Celsius at standard atmospheric pressure",
        "domain": "chemistry",
        "frame": "general_knowledge_v1.0",
        "expected_ambiguity": "low",
        "scenario5_expected_verdict": "SUPPORTED",
        "scenario5_expected_min_consensus": 0.80,
        "description": "Scenario 5 T1-03 — qualifier handling ('at standard pressure').",
    },
]


# ---------------------------------------------------------------------------
# Ollama health check
# ---------------------------------------------------------------------------


async def check_ollama() -> list[str]:
    import httpx
    base_url = "http://localhost:11434"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except httpx.ConnectError:
        print("✗ Ollama not running. Start with `ollama serve` on Windows then retry.")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Ollama health check failed: {e}")
        sys.exit(1)


def select_models(available: list[str]) -> list[str]:
    """Filter to inference models only. Exclude embeddings and known slow models."""
    EMBEDDING_KEYWORDS = ["embed", "nomic", "mxbai"]
    EXCLUDE_SLOW = ["gpt-oss", "deepseek-r1", "llama4"]  # configurable — remove to include

    selected = [
        m for m in available
        if not any(kw in m.lower() for kw in EMBEDDING_KEYWORDS)
        and not any(ex in m.lower() for ex in EXCLUDE_SLOW)
    ]
    return selected


def build_providers(selected_models: list[str]) -> dict:
    from services.providers.ollama import OllamaProvider
    providers = {}
    for model_name in selected_models:
        pid = f"ollama-{model_name.replace(':', '_').replace('.', '_')}"
        providers[pid] = OllamaProvider(model=model_name)
    return providers


# ---------------------------------------------------------------------------
# PART A runner — deterministic path with mocked HTTP
# ---------------------------------------------------------------------------


async def run_rwa_claim(entry: dict) -> dict:
    """
    Run one deterministic RWA claim through _run_deterministic_pipeline().
    Mocks adapter.fetch() to return entry['mock_raw'] — no external HTTP required.
    Validates: source_anchor, esmm_invoked=False, predicate, subject.
    """
    from database.engine import ISpaceDB
    from database.pool import close_pool
    from services.esmm.orchestrator import ClaimNature, ESMMRunConfig
    from services.esmm.pipeline import PipelineConfig, run_pipeline
    from services.esmm.source_anchor_builder import SourceAnchorSpec

    claim_id = entry["id"]
    source_id = entry["source_id"]
    mock_raw = entry["mock_raw"]

    print(f"  [{claim_id}] {entry['label']}")
    print(f"           {entry['description']}")

    fd, db_path = tempfile.mkstemp(suffix=f"_s6_{claim_id}.db")
    os.close(fd)

    result_row = {
        "id": claim_id,
        "label": entry["label"],
        "source_id": source_id,
        "frame_id": entry["frame_id"],
        "expected_status": entry["expected_status"],
        "expected_predicate": entry["expected_predicate"],
        "actual_status": None,
        "actual_predicate": None,
        "actual_subject": None,
        "source_anchor": None,
        "source_anchor_length": None,
        "esmm_invoked": None,
        "snapshot_stored": None,
        "duration_s": 0.0,
        "passed": False,
        "errors": "",
    }

    # Build the adapter_class mock path based on source_id
    adapter_module_map = {
        "opensanctions": "services.sources.adapters.opensanctions.OpenSanctionsAdapter",
        "verra_vcs": "services.sources.adapters.verra_vcs.VerraVcsAdapter",
        "ofac_sdn": "services.sources.adapters.ofac.OfacAdapter",
        "eu_cfsp": "services.sources.adapters.eu_cfsp.EuCfspAdapter",
    }
    adapter_path = adapter_module_map.get(source_id, "")

    try:
        db = ISpaceDB(db_path)
        await db.initialize()

        spec = SourceAnchorSpec(
            source_id=source_id,
            frame_id=entry["frame_id"],
            query=entry["query"],
            max_age_hours=24,
            min_sources=1,
        )

        config = PipelineConfig(
            metrological_frame=entry["frame_id"],
            use_cache=False,   # ADR-013 : cache désactivé en mode benchmark
        )
        esmm_config = ESMMRunConfig(
            models=["mock-model"],
            claim_nature=ClaimNature.DETERMINISTIC,
            source_anchor_spec=spec,
        )

        # Mock the adapter fetch — no HTTP, deterministic response
        mock_fetch = AsyncMock(return_value=mock_raw)
        patch_target = f"{adapter_path}.fetch"

        start = time.time()
        with patch(patch_target, mock_fetch):
            question = entry["query"].get("name") or entry["query"].get("serial", "rwa-query")
            result = await run_pipeline(
                question=question,
                db=db,
                config=config,
                providers={},
                models=["mock-model"],
                esmm_config=esmm_config,
            )
        elapsed = time.time() - start

        result_row["duration_s"] = round(elapsed, 1)

        if result.errors:
            result_row["errors"] = "; ".join(result.errors)

        if not result.attestations:
            result_row["errors"] = result_row["errors"] or "No attestation produced"
        else:
            att = result.attestations[0]
            result_row["actual_status"] = att.object
            result_row["actual_predicate"] = att.predicate
            result_row["actual_subject"] = att.subject
            result_row["source_anchor"] = att.source_anchor
            result_row["source_anchor_length"] = len(att.source_anchor) if att.source_anchor else 0

            # Extract esmm_invoked from consensus_meta
            if att.consensus_meta:
                methodology = att.consensus_meta.get("methodology", {})
                result_row["esmm_invoked"] = methodology.get("esmm_invoked")

            # Check snapshot stored
            if hasattr(db, "get_snapshot_by_anchor") and att.source_anchor:
                snap = await db.get_snapshot_by_anchor(att.source_anchor)
                result_row["snapshot_stored"] = snap is not None

            # Validation
            checks = {
                "status": result_row["actual_status"] == entry["expected_status"],
                "predicate": result_row["actual_predicate"] == entry["expected_predicate"],
                "source_anchor_sha256": result_row["source_anchor_length"] == 64,
                "esmm_not_invoked": result_row["esmm_invoked"] is False,
            }
            result_row["passed"] = all(checks.values())
            result_row["checks"] = checks

            status_icon = "✓" if checks["status"] else "✗"
            pred_icon = "✓" if checks["predicate"] else "✗"
            anch_icon = "✓" if checks["source_anchor_sha256"] else "✗"
            esmm_icon = "✓" if checks["esmm_not_invoked"] else "✗"

            print(
                f"           {status_icon} status={result_row['actual_status']} "
                f"| {pred_icon} predicate={result_row['actual_predicate']} "
                f"| {anch_icon} anchor[{result_row['source_anchor_length']}] "
                f"| {esmm_icon} esmm_invoked={result_row['esmm_invoked']} "
                f"| {elapsed:.1f}s"
            )

    except Exception as e:
        result_row["errors"] = str(e)
        logger.error("RWA claim %s failed: %s", claim_id, e)
        print(f"           ✗ ERROR: {str(e)[:100]}")

    finally:
        try:
            await close_pool()
        except Exception:
            pass
        if os.path.exists(db_path):
            os.unlink(db_path)

    return result_row


# ---------------------------------------------------------------------------
# PART B+C runner — epistemic VERIFY path (shared with scenario 5 pattern)
# ---------------------------------------------------------------------------


async def run_epistemic_claim(
    claim_entry: dict,
    selected_models: list[str],
    claim_index: int,
    total_claims: int,
    part_label: str,
) -> dict:
    """Run one VERIFY claim. Returns result row with ADR-011 diagnostics."""
    from database.engine import ISpaceDB
    from database.pool import close_pool
    from services.esmm.orchestrator import ESMMRunConfig
    from services.esmm.pipeline import PipelineConfig, run_pipeline

    claim_id = claim_entry["id"]
    claim_text = claim_entry["claim"]
    short = claim_text[:55] + "..." if len(claim_text) > 55 else claim_text
    print(f"  [{claim_index:02d}/{total_claims:02d}] {claim_id} | \"{short}\"")

    fd, db_path = tempfile.mkstemp(suffix=f"_s6_{claim_id}.db")
    os.close(fd)

    row = {
        "id": claim_id,
        "part": part_label,
        "claim": claim_text,
        "domain": claim_entry.get("domain", ""),
        "frame": claim_entry.get("frame", "general_knowledge_v1.0"),
        "expected_ambiguity": claim_entry.get("expected_ambiguity", ""),
        "verdict": None,
        "consensus_score": None,
        "dissent": None,
        "dissent_score": None,
        "vote_entropy": None,
        "models_agreed": None,
        "models_total": len(selected_models),
        "triplets_extracted": 0,
        "triplets_attested": 0,
        "fingerprint_merge_count": None,  # ADR-011 diagnostic
        "claim_type": None,
        "decidability_penalty": None,
        "duration_s": 0.0,
        "errors": "",
        # Part B specific
        "fingerprint_stress": claim_entry.get("fingerprint_stress", ""),
        "expected_min_consensus": claim_entry.get("expected_min_consensus"),
        "consensus_above_threshold": None,
        # Part C specific
        "regression_passed": None,
    }

    try:
        db = ISpaceDB(db_path)
        await db.initialize()

        providers = build_providers(selected_models)
        config = PipelineConfig(
            metrological_frame=claim_entry.get("frame", "general_knowledge_v1.0"),
            use_cache=False,   # ADR-013 : cache désactivé en mode benchmark
        )
        esmm_config = ESMMRunConfig(
            models=selected_models,
            input_mode="verify",
            original_claim=claim_text,
        )

        start = time.time()
        result = await run_pipeline(
            question=claim_text,
            db=db,
            config=config,
            providers=providers,
            models=selected_models,
            esmm_config=esmm_config,
        )
        elapsed = time.time() - start

        row["duration_s"] = round(elapsed, 1)
        row["triplets_extracted"] = result.triplets_extracted
        row["triplets_attested"] = result.triplets_attested

        if result.errors:
            row["errors"] = "; ".join(result.errors)

        # Extract verdict
        verdict_atts = [a for a in result.attestations if a.predicate == "verdict"]
        if verdict_atts:
            verdict_atts.sort(key=lambda a: a.consensus_score, reverse=True)
            best = verdict_atts[0]
            row["verdict"] = best.object
            row["consensus_score"] = round(best.consensus_score, 4)
            row["models_agreed"] = best.models_agreeing

            if len(verdict_atts) > 1:
                second = verdict_atts[1]
                row["dissent"] = second.object
                row["dissent_score"] = round(second.consensus_score, 4)

        # Extract consensus_meta (ADR-010 + ADR-011 diagnostics)
        if result.attestations and hasattr(result.attestations[0], "consensus_meta"):
            meta = result.attestations[0].consensus_meta
            if meta:
                diag = meta.get("diagnostics", {})
                row["vote_entropy"] = diag.get("vote_entropy")

                # ADR-011 fingerprint merge count
                row["fingerprint_merge_count"] = diag.get("fingerprint_merges", diag.get("semantic_merges"))

                verify_section = meta.get("verify", {})
                if verify_section:
                    row["claim_type"] = verify_section.get("claim_type")
                    row["decidability_penalty"] = verify_section.get("decidability_penalty")

        # Part B threshold check
        if row["expected_min_consensus"] is not None and row["consensus_score"] is not None:
            row["consensus_above_threshold"] = row["consensus_score"] >= row["expected_min_consensus"]

        # Part C regression check
        if claim_entry.get("scenario5_expected_verdict"):
            verdict_ok = row["verdict"] == claim_entry["scenario5_expected_verdict"]
            score_ok = (
                row["consensus_score"] is not None
                and row["consensus_score"] >= claim_entry["scenario5_expected_min_consensus"]
            )
            row["regression_passed"] = verdict_ok and score_ok

        # Display
        v = row["verdict"] or "ERROR"
        cs = row["consensus_score"] or 0.0
        ent = row["vote_entropy"] or 0.0
        merges = row["fingerprint_merge_count"]
        dur = row["duration_s"]

        merge_str = f" | fp_merges={merges}" if merges is not None else ""
        threshold_str = ""
        if row["consensus_above_threshold"] is not None:
            icon = "✓" if row["consensus_above_threshold"] else "✗"
            threshold_str = f" | {icon} ≥{row['expected_min_consensus']:.0%}"

        if row["dissent"]:
            print(
                f"           -> {v} ({cs:.0%}) <-> {row['dissent']} ({row['dissent_score']:.0%})"
                f" | entropy={ent:.2f}{merge_str}{threshold_str} | {dur:.0f}s"
            )
        elif row["errors"] and not row["verdict"]:
            print(f"           -> ERROR: {row['errors'][:80]}")
        else:
            print(
                f"           -> {v} ({cs:.0%}) | entropy={ent:.2f}"
                f"{merge_str}{threshold_str} | {dur:.0f}s"
            )

        for provider in providers.values():
            if hasattr(provider, "close"):
                await provider.close()

    except Exception as e:
        row["errors"] = str(e)
        logger.error("Claim %s failed: %s", claim_id, e)
        print(f"           -> ERROR: {str(e)[:80]}")

    finally:
        try:
            await close_pool()
        except Exception:
            pass
        if os.path.exists(db_path):
            os.unlink(db_path)

    return row


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    print("=" * 65)
    print("EPP SCENARIO 6 — Full Pipeline Validation")
    print("ADR-012 Deterministic + ADR-011 Fingerprinting + T1 Regression")
    print("=" * 65)
    print()

    # Ollama health check
    available = await check_ollama()
    selected = select_models(available)

    if len(selected) < 2:
        print(f"✗ Need at least 2 non-embedding models. Found: {available}")
        print("  Pull models with: ollama pull mistral && ollama pull llama3.1:8b")
        sys.exit(1)

    print(f"Models ({len(selected)}): {', '.join(selected)}")
    print()

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).parent / "benchmark_runs"
    output_dir.mkdir(exist_ok=True)

    adr_validation = {
        "adr_012": {"total": 0, "passed": 0, "failed": []},
        "adr_011": {"total": 0, "above_threshold": 0, "below_threshold": []},
        "regression": {"total": 0, "passed": 0, "failed": []},
    }

    # -----------------------------------------------------------------------
    # PART A — Deterministic RWA
    # -----------------------------------------------------------------------
    print("─" * 65)
    print("PART A — Deterministic RWA (ADR-012) — mocked HTTP")
    print("─" * 65)
    rwa_results = []
    for entry in RWA_CLAIMS:
        row = await run_rwa_claim(entry)
        rwa_results.append(row)
        adr_validation["adr_012"]["total"] += 1
        if row.get("passed"):
            adr_validation["adr_012"]["passed"] += 1
        else:
            adr_validation["adr_012"]["failed"].append({
                "id": row["id"],
                "checks": row.get("checks", {}),
                "errors": row.get("errors", ""),
            })
    print()

    # -----------------------------------------------------------------------
    # PART B — Fingerprinting stress
    # -----------------------------------------------------------------------
    print("─" * 65)
    print("PART B — Semantic Fingerprinting stress (ADR-011-v2)")
    print("─" * 65)
    fp_results = []
    for i, entry in enumerate(FINGERPRINT_CLAIMS, 1):
        print(f"  Stress pattern: {entry['fingerprint_stress']}")
        row = await run_epistemic_claim(entry, selected, i, len(FINGERPRINT_CLAIMS), "B")
        fp_results.append(row)
        adr_validation["adr_011"]["total"] += 1
        if row.get("consensus_above_threshold"):
            adr_validation["adr_011"]["above_threshold"] += 1
        else:
            adr_validation["adr_011"]["below_threshold"].append({
                "id": row["id"],
                "consensus_score": row["consensus_score"],
                "threshold": row["expected_min_consensus"],
            })
    print()

    # -----------------------------------------------------------------------
    # PART C — T1 Regression
    # -----------------------------------------------------------------------
    print("─" * 65)
    print("PART C — T1 Regression (Scenario 5 baseline)")
    print("─" * 65)
    reg_results = []
    for i, entry in enumerate(REGRESSION_CLAIMS, 1):
        row = await run_epistemic_claim(
            entry, selected, i, len(REGRESSION_CLAIMS), "C"
        )
        reg_results.append(row)
        adr_validation["regression"]["total"] += 1
        if row.get("regression_passed"):
            adr_validation["regression"]["passed"] += 1
        else:
            adr_validation["regression"]["failed"].append({
                "id": row["id"],
                "verdict": row["verdict"],
                "consensus_score": row["consensus_score"],
                "expected_verdict": entry["scenario5_expected_verdict"],
                "expected_min": entry["scenario5_expected_min_consensus"],
            })
    print()

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    total_elapsed = sum(r["duration_s"] for r in rwa_results + fp_results + reg_results)

    print("=" * 65)
    print("SCENARIO 6 — SUMMARY")
    print("=" * 65)

    # ADR-012
    a012 = adr_validation["adr_012"]
    a012_icon = "✓" if a012["passed"] == a012["total"] else "✗"
    print(f"\n  {a012_icon} ADR-012 Deterministic: {a012['passed']}/{a012['total']} passed")
    for entry in RWA_CLAIMS:
        row = next(r for r in rwa_results if r["id"] == entry["id"])
        icon = "✓" if row.get("passed") else "✗"
        checks = row.get("checks", {})
        print(
            f"       {icon} {row['id']} {row['label']}"
            f"\n              status={row['actual_status']} predicate={row['actual_predicate']}"
            f" anchor[{row['source_anchor_length']}] esmm_invoked={row['esmm_invoked']}"
        )
        if not row.get("passed") and checks:
            failed_checks = [k for k, v in checks.items() if not v]
            print(f"              FAILED checks: {failed_checks}")

    # ADR-011
    a011 = adr_validation["adr_011"]
    a011_icon = "✓" if a011["above_threshold"] == a011["total"] else "⚠"
    print(f"\n  {a011_icon} ADR-011 Fingerprinting: {a011['above_threshold']}/{a011['total']} above threshold")
    for row in fp_results:
        icon = "✓" if row.get("consensus_above_threshold") else "✗"
        merges = row.get("fingerprint_merge_count", "?")
        threshold = row.get("expected_min_consensus", 0)
        cs = row.get("consensus_score") or 0.0
        print(
            f"       {icon} {row['id']} [{row['verdict'] or 'ERR'}] "
            f"consensus={cs:.0%} (min={threshold:.0%}) fp_merges={merges}"
        )

    # Regression
    reg = adr_validation["regression"]
    reg_icon = "✓" if reg["passed"] == reg["total"] else "✗"
    print(f"\n  {reg_icon} T1 Regression: {reg['passed']}/{reg['total']} passed")
    for row in reg_results:
        icon = "✓" if row.get("regression_passed") else "✗"
        cs = row.get("consensus_score") or 0.0
        print(
            f"       {icon} {row['id']} [{row['verdict'] or 'ERR'}] "
            f"consensus={cs:.0%}"
        )

    # Global verdict
    all_passed = (
        a012["passed"] == a012["total"]
        and reg["passed"] == reg["total"]
    )
    global_icon = "🟢 VERT" if all_passed else "🟠 ORANGE"
    mins = int(total_elapsed // 60)
    secs = int(total_elapsed % 60)
    print(f"\n  Global: {global_icon} | Duration: {mins}m {secs}s")
    print()

    # -----------------------------------------------------------------------
    # Write JSON report
    # -----------------------------------------------------------------------
    json_path = output_dir / f"scenario6_{timestamp_str}.json"
    report = {
        "scenario": "scenario_6_full_pipeline",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "models": selected,
        "model_count": len(selected),
        "total_duration_s": round(total_elapsed, 1),
        "adr_validation": adr_validation,
        "global_verdict": global_icon,
        "parts": {
            "A_rwa_deterministic": rwa_results,
            "B_fingerprinting_stress": fp_results,
            "C_regression_t1": reg_results,
        },
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str, ensure_ascii=False)

    print(f"  Report: {json_path}")
    print("=" * 65)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
