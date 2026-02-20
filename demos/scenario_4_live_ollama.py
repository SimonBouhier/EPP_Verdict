"""
Scenario 4 -- Live ESMM deliberation with Ollama models.

Executes the FULL ESMM pipeline with REAL local models via Ollama.
This is the definitive demo — shows actual multi-model debate.

Prerequisites:
    - Ollama running (ollama serve)
    - At least 2 models: ollama pull mistral:7b && ollama pull llama3.1:8b

Expected duration: 5-6 minutes (deliberative, not real-time — this is by design)
Expected result: Attestation with real consensus from contested model debate.
"""

import asyncio
import sys
import tempfile
import os
import logging
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger("demo.scenario_4")

# Embedding-only models (support /api/embeddings but NOT /api/chat).
# Any model whose name contains one of these substrings is excluded
# from deliberation. Covers prefixed variants like hellord/mxbai-embed-large-v1:f16.
EMBEDDING_PATTERNS = ["embed"]


def _is_embedding_model(name: str) -> bool:
    """True if model name matches a known embedding-only pattern."""
    return any(pat in name.lower() for pat in EMBEDDING_PATTERNS)


def _model_base_name(name: str) -> str:
    """Extract base name without tag: 'mistral:7b' → 'mistral'."""
    return name.split(":")[0].lower()


async def check_ollama() -> list[str]:
    """
    Health check Ollama. Returns list of available model names.
    Raises SystemExit with clear message if Ollama is unreachable.
    """
    import httpx

    base_url = "http://localhost:11434"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            return models
    except httpx.ConnectError:
        print("Ollama not running. Start with `ollama serve` then retry.")
        sys.exit(1)
    except Exception as e:
        print(f"Ollama health check failed: {e}")
        sys.exit(1)


async def main():
    print("=" * 60)
    print("SCENARIO 4: Live ESMM deliberation (Ollama)")
    print("=" * 60)
    print()

    # 1. Health check
    all_models = await check_ollama()
    print(f"  Ollama is running. Available models: {len(all_models)}")
    for m in all_models:
        print(f"    - {m}")
    print()

    # Filter embedding-only models (they don't support /api/chat)
    available_models = [m for m in all_models if not _is_embedding_model(m)]
    if len(available_models) < len(all_models):
        filtered = [m for m in all_models if _is_embedding_model(m)]
        print(f"  Filtered {len(filtered)} embedding-only model(s): {filtered}")
        print()

    if len(available_models) < 2:
        print("  Need at least 2 chat models for ESMM deliberation.")
        print("  Install with: ollama pull mistral && ollama pull llama3.1:8b")
        sys.exit(1)

    # Select models (prefer known good families, fallback to whatever is available)
    # deepseek-r1 excluded: quantized version too unstable (empty responses, retry loops)
    preferred = ["mistral:latest", "llama3.1:8b", "gemma3:latest", "granite3.3:latest", "qwen2.5:7b"]
    available_bases = {_model_base_name(m): m for m in available_models}
    selected = []
    for p in preferred:
        base = _model_base_name(p)
        if base in available_bases and available_bases[base] not in selected:
            selected.append(available_bases[base])
    if len(selected) < 2:
        # Fallback: use whatever chat models are available
        selected = available_models[:3]
    print(f"  Selected models: {selected}")
    print()

    # 2. Setup
    from database.engine import ISpaceDB
    from database.pool import close_pool
    from services.esmm.pipeline import run_pipeline, PipelineConfig
    from services.providers.ollama import OllamaProvider

    fd, db_path = tempfile.mkstemp(suffix="_demo_s4_live.db")
    os.close(fd)

    try:
        db = ISpaceDB(db_path)
        await db.initialize()

        question = "Solana effective TPS exceeds 3000"
        config = PipelineConfig(metrological_frame="blockchain_tps_v1.0")

        print(f"  Question: \"{question}\"")
        print(f"  Frame: {config.metrological_frame}")
        print()

        # Build real providers — keys MUST match cycle_manager convention
        def _provider_id(model: str) -> str:
            return f"ollama-{model.replace(':', '_').replace('.', '_')}"

        providers = {}
        for model_name in selected:
            providers[_provider_id(model_name)] = OllamaProvider(model=model_name)
        print(f"  Provider IDs: {list(providers.keys())}")

        # 3. Run REAL pipeline (NO mocks, NO patches)
        print("Starting ESMM deliberation (this takes ~5 minutes)...")
        print()

        start = time.time()
        result = await run_pipeline(
            question=question,
            db=db,
            config=config,
            providers=providers,
            models=selected,
        )
        elapsed = time.time() - start

        # 4. Detect mode and display accordingly
        verify_meta = None
        if result.attestations:
            meta = getattr(result.attestations[0], "consensus_meta", None)
            if meta and "verify" in meta:
                verify_meta = meta

        if verify_meta:
            # ============ VERIFY MODE DISPLAY ============
            v = verify_meta["verify"]
            methodology = verify_meta.get("methodology", {})
            conditions = verify_meta.get("conditions", {})
            diagnostics = verify_meta.get("diagnostics", {})

            print()
            print("=" * 60)
            print("VERIFY MODE — Claim Evaluation")
            print("=" * 60)
            print(f'  Claim: "{v.get("original_claim", question)}"')
            print(f"  Frame: {config.metrological_frame}")
            print()

            # Phase summary
            cycles = conditions.get("cycles_completed", "?")
            print(f"  Phases completed: {cycles}")
            print(f"    Phase 1 — ASSESS (independent evaluation)")
            print(f"    Phase 2 — CHALLENGE (adversarial review, isolated)")
            print(f"    Phase 3 — ADJUDICATE (final judgment)")
            print()

            # Verdict box
            final_verdict = v.get("final_verdict", "N/A")
            verdict_conf = v.get("verdict_confidence")
            conf_str = f"{verdict_conf:.0%}" if verdict_conf else "?"

            # Count verdict split from attestations
            verdict_counts = {}
            for att in result.attestations:
                if att.predicate == "verdict":
                    verdict_counts[att.object] = verdict_counts.get(att.object, 0) + 1

            split_parts = [f"{cnt} {vname}" for vname, cnt in sorted(
                verdict_counts.items(), key=lambda x: -x[1]
            )]
            split_str = " / ".join(split_parts) if split_parts else "N/A"

            box_line = f"  FINAL VERDICT: {final_verdict} ({conf_str} consensus)"
            box_width = max(len(box_line) + 4, 50)
            print(f"  {'┌' + '─' * (box_width - 2) + '┐'}")
            print(f"  │{box_line.ljust(box_width - 2)}│")
            if len(verdict_counts) > 1:
                dissent = [f"{att.object} ({att.consensus_score:.0%})"
                           for att in result.attestations
                           if att.predicate == "verdict" and att.object != final_verdict]
                if dissent:
                    dissent_line = f"  Dissent: {', '.join(dissent)}"
                    print(f"  │{dissent_line.ljust(box_width - 2)}│")
            split_line = f"  Split: {split_str}"
            print(f"  │{split_line.ljust(box_width - 2)}│")
            print(f"  {'└' + '─' * (box_width - 2) + '┘'}")
            print()

            # Formal attestations
            print(f"  Formal attestations ({len(result.attestations)}):")
            for att in result.attestations:
                tier = att.confidence_tier.upper()
                print(f"    [{tier}] {att.subject} -> {att.predicate} -> {att.object}"
                      f"  ({att.consensus_score:.0%})")
            print()

            # Evidence corpus (sub-consensus)
            evidence = v.get("evidence_corpus", [])
            evidence_total = v.get("evidence_total", len(evidence))
            if evidence:
                shown = min(len(evidence), 10)
                print(f"  Supporting evidence ({shown}/{evidence_total} sub-consensus):")
                for ev in evidence[:10]:
                    models_str = f"{len(ev.get('models', []))} model(s)" if ev.get("models") else ""
                    score_str = f"{ev['consensus_score']:.0%}" if ev.get("consensus_score") else ""
                    detail = f" ({models_str}, {score_str})" if models_str or score_str else ""
                    print(f"    - {ev['subject']} -> {ev['predicate']} -> {ev['object']}{detail}")
                print()

            # Methodology
            method = methodology.get("consensus_method", "N/A")
            mode = methodology.get("pipeline_mode", "explore")
            entropy = diagnostics.get("vote_entropy", "?")
            print(f"  Methodology: {method}")
            print(f"  Pipeline mode: {mode} | Vote entropy: {entropy}")
            print(f"  Duration: {elapsed:.1f}s | {len(selected)} models | "
                  f"{result.triplets_extracted} triplets extracted | "
                  f"{result.triplets_attested} attested")

        else:
            # ============ EXPLORE MODE DISPLAY (unchanged) ============
            print()
            print(f"  [ESMM] {len(selected)} models consulted | "
                  f"{result.triplets_extracted} triplets extracted")
            print(f"  [CONSENSUS] {result.triplets_attested} attestations | "
                  f"{result.triplets_injected} graph injections")
            print(f"  Run ID: {result.run_id}")
            print(f"  Duration: {elapsed:.1f}s ({result.duration_ms:.0f}ms)")
            print()

            if result.attestations:
                for att in result.attestations:
                    tier_label = att.confidence_tier.upper()
                    print(f"  [{tier_label}] {att.subject} -> {att.predicate} -> {att.object}")
                    print(f"    Consensus: {att.consensus_score:.2%}")
                    print(f"    Hash: {att.claim_hash[:16]}...")
                    print(f"    Models: {att.models_agreeing}/{att.models_consulted}")

                    if hasattr(att, "signature_5d") and att.signature_5d:
                        sig = att.signature_5d
                        print(f"    5D Signature: agreement={sig.agreement:.2f} "
                              f"semantic={sig.semantic_consistency:.2f} "
                              f"centrality={sig.centrality:.2f} "
                              f"stability={sig.stability:.2f} "
                              f"diversity={sig.relation_diversity:.2f}")

                    if hasattr(att, "consensus_meta") and att.consensus_meta:
                        meta = att.consensus_meta
                        method = meta.get("methodology", {}).get("consensus_method", "N/A")
                        mode = meta.get("methodology", {}).get("pipeline_mode", "explore")
                        cycles = meta.get("conditions", {}).get("cycles_completed", "?")
                        entropy = meta.get("diagnostics", {}).get("vote_entropy", "?")
                        print(f"    Consensus meta: method={method}, mode={mode}, "
                              f"cycles={cycles}, entropy={entropy}")

                    print()
            else:
                print("  No attestations produced.")
                if result.errors:
                    print(f"  Errors: {result.errors}")
                print()

        # Graph stats
        stats = await db.get_stats()
        print(f"  Graph: {stats.get('concepts', 0)} concepts, "
              f"{stats.get('relations', 0)} relations")
        print(f"  ESMM Runs: {stats.get('esmm_runs', 0)}")
        print(f"  Attestations in DB: {stats.get('attestations', 0)}")
        print()
        print("=" * 60)
        print("Scenario 4 complete — live ESMM deliberation finished.")
        print("=" * 60)

        # Cleanup providers
        for provider in providers.values():
            if hasattr(provider, "close"):
                await provider.close()

    finally:
        await close_pool()
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    asyncio.run(main())
