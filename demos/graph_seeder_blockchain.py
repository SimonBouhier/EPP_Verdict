#!/usr/bin/env python3
"""
EPP Graph Seeder — Blockchain / Solana / Crypto
================================================
Nourrit data/epp_devnet.db avec des attestations épistémiques
sur le domaine blockchain/Solana/crypto.

Utilise use_cache=True : les claims déjà délibérées sont récupérées
en 0ms depuis le graphe persistant (ADR-013).

Usage :
    python demos/graph_seeder_blockchain.py

Durée estimée : ~2h30 (30 claims × 5 modèles × ~300s)
GPU : RTX 4090 — Ollama models chargés séquentiellement
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.engine import ISpaceDB
from services.esmm.pipeline import PipelineConfig, run_pipeline

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MODÈLES — 5 architectures distinctes
# ---------------------------------------------------------------------------
MODELS = [
    "phi4-reasoning:latest",
    "gemma3:latest",
    "granite3.3:latest",
    "mistral:latest",
    "llama3.1:8b",
]

# ---------------------------------------------------------------------------
# CLAIMS — 30 claims blockchain/Solana/crypto
# Organisées en 6 catégories de 5 claims chacune
# ---------------------------------------------------------------------------
CLAIMS = [

    # -- CATÉGORIE 1 : Architecture Solana ----------------------------------
    {
        "id": "SOL-01",
        "category": "solana_architecture",
        "claim": "Solana uses a Proof of History mechanism to order transactions before consensus",
        "frame": "blockchain_tps_v1.0",
        "note": "Fondamental — PoH est l'innovation différenciante de Solana",
    },
    {
        "id": "SOL-02",
        "category": "solana_architecture",
        "claim": "Solana achieves transaction finality in under one second under normal network conditions",
        "frame": "blockchain_tps_v1.0",
        "note": "Claim de performance — vérifiable, sujette à nuance (normal conditions)",
    },
    {
        "id": "SOL-03",
        "category": "solana_architecture",
        "claim": "Solana validators must stake SOL tokens to participate in block production",
        "frame": "blockchain_tps_v1.0",
        "note": "Mécanique de staking — factuel",
    },
    {
        "id": "SOL-04",
        "category": "solana_architecture",
        "claim": "The Solana runtime executes smart contracts called programs stored on-chain",
        "frame": "blockchain_tps_v1.0",
        "note": "Terminologie Solana — programs vs smart contracts (Ethereum)",
    },
    {
        "id": "SOL-05",
        "category": "solana_architecture",
        "claim": "Solana uses a Tower BFT consensus mechanism built on top of Proof of History",
        "frame": "blockchain_tps_v1.0",
        "note": "Couche consensus — Tower BFT au-dessus de PoH",
    },

    # -- CATÉGORIE 2 : Comparaisons blockchain ------------------------------
    {
        "id": "COMP-01",
        "category": "blockchain_comparison",
        "claim": "Ethereum processes significantly fewer transactions per second than Solana under comparable load",
        "frame": "blockchain_tps_v1.0",
        "note": "Comparaison TPS — sujette à contexte (mainnet vs théorique)",
    },
    {
        "id": "COMP-02",
        "category": "blockchain_comparison",
        "claim": "Bitcoin does not support Turing-complete smart contracts natively",
        "frame": "general_knowledge_v1.0",
        "note": "Limite Bitcoin — factuel (Script n'est pas Turing-complete)",
    },
    {
        "id": "COMP-03",
        "category": "blockchain_comparison",
        "claim": "Proof of Stake consensus mechanisms consume significantly less energy than Proof of Work",
        "frame": "general_knowledge_v1.0",
        "note": "PoS vs PoW énergie — largement accepté, nuancé par impl",
    },
    {
        "id": "COMP-04",
        "category": "blockchain_comparison",
        "claim": "Ethereum transitioned from Proof of Work to Proof of Stake in September 2022",
        "frame": "general_knowledge_v1.0",
        "note": "The Merge — date précise, factuel",
    },
    {
        "id": "COMP-05",
        "category": "blockchain_comparison",
        "claim": "Layer 2 solutions on Ethereum inherit the security guarantees of the Ethereum base layer",
        "frame": "blockchain_tps_v1.0",
        "note": "L2 security — nuancé selon le type de L2 (optimistic vs ZK)",
    },

    # -- CATÉGORIE 3 : Cryptographie fondamentale --------------------------─
    {
        "id": "CRYP-01",
        "category": "cryptography",
        "claim": "Zero-knowledge proofs allow one party to prove knowledge of a value without revealing the value itself",
        "frame": "general_knowledge_v1.0",
        "note": "ZKP définition — déjà dans le graphe si scenario 6 a tourné",
    },
    {
        "id": "CRYP-02",
        "category": "cryptography",
        "claim": "SHA-256 is a one-way cryptographic hash function that produces a fixed 256-bit output",
        "frame": "general_knowledge_v1.0",
        "note": "SHA-256 — fondamental pour EPP lui-même",
    },
    {
        "id": "CRYP-03",
        "category": "cryptography",
        "claim": "Elliptic curve cryptography provides equivalent security to RSA with shorter key lengths",
        "frame": "general_knowledge_v1.0",
        "note": "ECC vs RSA — factuel, pertinent pour wallets blockchain",
    },
    {
        "id": "CRYP-04",
        "category": "cryptography",
        "claim": "A Merkle tree allows efficient and secure verification of large data sets using hash functions",
        "frame": "general_knowledge_v1.0",
        "note": "Merkle trees — fondamental blockchain",
    },
    {
        "id": "CRYP-05",
        "category": "cryptography",
        "claim": "Digital signatures in blockchain transactions prove ownership of a private key without revealing it",
        "frame": "general_knowledge_v1.0",
        "note": "Signatures numériques — lien avec ZKP conceptuellement",
    },

    # -- CATÉGORIE 4 : DeFi et oracles --------------------------------------
    {
        "id": "DEFI-01",
        "category": "defi_oracles",
        "claim": "Decentralized oracles are necessary because smart contracts cannot natively access off-chain data",
        "frame": "general_knowledge_v1.0",
        "note": "Oracle problem — fondement de la proposition de valeur EPP",
    },
    {
        "id": "DEFI-02",
        "category": "defi_oracles",
        "claim": "Automated market makers replace traditional order books with liquidity pools and mathematical formulas",
        "frame": "general_knowledge_v1.0",
        "note": "AMM — DeFi fondamental",
    },
    {
        "id": "DEFI-03",
        "category": "defi_oracles",
        "claim": "Flash loans allow uncollateralized borrowing of crypto assets within a single transaction block",
        "frame": "general_knowledge_v1.0",
        "note": "Flash loans — DeFi primitif avancé",
    },
    {
        "id": "DEFI-04",
        "category": "defi_oracles",
        "claim": "Price oracle manipulation attacks have caused significant losses in DeFi protocols",
        "frame": "general_knowledge_v1.0",
        "note": "Oracle attacks — directement pertinent pour EPP risk model",
    },
    {
        "id": "DEFI-05",
        "category": "defi_oracles",
        "claim": "Chainlink uses a decentralized network of node operators to aggregate data from multiple sources",
        "frame": "general_knowledge_v1.0",
        "note": "Chainlink — concurrent direct, modèle de référence",
    },

    # -- CATÉGORIE 5 : Bitcoin fondamentaux --------------------------------─
    {
        "id": "BTC-01",
        "category": "bitcoin_fundamentals",
        "claim": "Bitcoin has a hard cap of 21 million coins that can ever be created",
        "frame": "general_knowledge_v1.0",
        "note": "Supply cap — factuel, fondamental",
    },
    {
        "id": "BTC-02",
        "category": "bitcoin_fundamentals",
        "claim": "Bitcoin mining difficulty adjusts automatically to maintain an average block time of 10 minutes",
        "frame": "general_knowledge_v1.0",
        "note": "Difficulty adjustment — mécanique fondamentale",
    },
    {
        "id": "BTC-03",
        "category": "bitcoin_fundamentals",
        "claim": "The Bitcoin halving event reduces the block reward by 50 percent approximately every four years",
        "frame": "general_knowledge_v1.0",
        "note": "Halving — factuel, dates précises connues",
    },
    {
        "id": "BTC-04",
        "category": "bitcoin_fundamentals",
        "claim": "Bitcoin transactions are irreversible once confirmed by sufficient blocks in the chain",
        "frame": "general_knowledge_v1.0",
        "note": "Immutabilité — fondamental, nuancé par 51% attack",
    },
    {
        "id": "BTC-05",
        "category": "bitcoin_fundamentals",
        "claim": "The Lightning Network enables near-instant Bitcoin payments through off-chain payment channels",
        "frame": "general_knowledge_v1.0",
        "note": "Lightning — L2 Bitcoin, pertinent comparaison scaling",
    },

    # -- CATÉGORIE 6 : Claims contestées / nuancées ------------------------─
    {
        "id": "CONT-01",
        "category": "contested",
        "claim": "Blockchain technology will fundamentally transform traditional financial infrastructure within a decade",
        "frame": "general_knowledge_v1.0",
        "note": "Spéculatif — entropy élevée attendue",
    },
    {
        "id": "CONT-02",
        "category": "contested",
        "claim": "Decentralized finance can provide equivalent security guarantees to regulated traditional finance",
        "frame": "general_knowledge_v1.0",
        "note": "DeFi vs TradFi sécurité — contesté, phi4 doit nuancer",
    },
    {
        "id": "CONT-03",
        "category": "contested",
        "claim": "Non-fungible tokens have demonstrated lasting utility beyond speculative investment",
        "frame": "general_knowledge_v1.0",
        "note": "NFT utility — très contesté, divergence inter-modèles attendue",
    },
    {
        "id": "CONT-04",
        "category": "contested",
        "claim": "Proof of Work mining provides stronger security guarantees than Proof of Stake validation",
        "frame": "blockchain_tps_v1.0",
        "note": "PoW vs PoS sécurité — débat ouvert, entropie attendue",
    },
    {
        "id": "CONT-05",
        "category": "contested",
        "claim": "Central bank digital currencies represent a threat to the decentralization principles of blockchain",
        "frame": "general_knowledge_v1.0",
        "note": "CBDC vs blockchain — normative/empirique mixte",
    },
]

# ---------------------------------------------------------------------------
# RUNNER
# ---------------------------------------------------------------------------

async def run_claim(claim_entry: dict, db: ISpaceDB) -> dict:
    """Exécute un claim via run_pipeline() avec cache activé."""
    start = time.time()
    result = {
        "id": claim_entry["id"],
        "category": claim_entry["category"],
        "claim": claim_entry["claim"],
        "frame": claim_entry["frame"],
        "note": claim_entry["note"],
        "verdict": None,
        "consensus_score": None,
        "claim_type": None,
        "vote_entropy": None,
        "models_agreed": None,
        "models_total": len(MODELS),
        "triplets_extracted": 0,
        "from_cache": False,
        "duration_s": 0.0,
        "errors": "",
    }

    try:
        from services.esmm.orchestrator import ESMMRunConfig

        config = PipelineConfig(
            metrological_frame=claim_entry["frame"],
            # use_cache=True par défaut — ADR-013
        )
        esmm_config = ESMMRunConfig(
            models=MODELS,
            input_mode="verify",
            original_claim=claim_entry["claim"],
            max_duration_hours=400 / 3600,  # 400s — marge pour phi4-reasoning
        )

        pipeline_result = await run_pipeline(
            question=claim_entry["claim"],
            db=db,
            config=config,
            models=MODELS,
            esmm_config=esmm_config,
        )

        result["from_cache"] = getattr(pipeline_result, "from_cache", False)
        result["triplets_extracted"] = len(pipeline_result.attestations)

        if pipeline_result.attestations:
            best = max(
                pipeline_result.attestations,
                key=lambda a: a.consensus_score or 0.0,
            )
            result["verdict"] = best.verdict if hasattr(best, "verdict") else None
            result["consensus_score"] = round(best.consensus_score or 0.0, 4)
            result["claim_type"] = best.epistemic_type if hasattr(best, "epistemic_type") else None
            result["vote_entropy"] = round(
                getattr(best, "vote_entropy", 0.0) or 0.0, 6
            )
            result["models_agreed"] = getattr(best, "models_agreeing", None)

    except Exception as exc:
        result["errors"] = str(exc)

    result["duration_s"] = round(time.time() - start, 1)
    return result


async def main():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "demos",
        "benchmark_runs",
        f"graph_seeder_blockchain_{timestamp}.json",
    )
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    print("=" * 65)
    print("EPP GRAPH SEEDER — Blockchain / Solana / Crypto")
    print("=" * 65)
    print(f"Models ({len(MODELS)}): {', '.join(MODELS)}")
    print(f"Claims ({len(CLAIMS)}): {', '.join(c['id'] for c in CLAIMS)}")
    print(f"Cache : ACTIVÉ (ADR-013) — claims déjà délibérées -> 0ms")
    print(f"DB    : data/epp_devnet.db")
    print()

    # DB persistante (pas de tempfile — c'est le but)
    from services.config_loader import get_section
    db_path = get_section("database", {}).get("path", "data/epp_devnet.db")

    db = ISpaceDB(db_path)

    results = []
    total_start = time.time()

    categories = {}
    for c in CLAIMS:
        categories.setdefault(c["category"], []).append(c)

    claim_num = 0
    for category, claims in categories.items():
        print(f"\n-- {category.upper().replace('_', ' ')} ({len(claims)} claims) --")
        for claim_entry in claims:
            claim_num += 1
            short = claim_entry["claim"][:55] + "..."
            print(f"\n  [{claim_num:02d}/{len(CLAIMS)}] {claim_entry['id']}")
            print(f"         \"{short}\"")
            print(f"         i {claim_entry['note']}")

            result = await run_claim(claim_entry, db)
            results.append(result)

            cache_tag = " *CACHE" if result["from_cache"] else ""
            if result["errors"]:
                print(f"         -> ERR: {result['errors'][:80]} | {result['duration_s']}s")
            else:
                print(
                    f"         -> {result['verdict'] or '?'} "
                    f"({int((result['consensus_score'] or 0) * 100)}%) "
                    f"type={result['claim_type'] or '?'} "
                    f"entropy={result['vote_entropy'] or 0:.2f} "
                    f"| {result['duration_s']}s{cache_tag}"
                )

    total_duration = time.time() - total_start

    # -- SUMMARY ----------------------------------------------------------
    print("\n" + "=" * 65)
    print("SUMMARY")
    print("=" * 65)

    cache_hits = sum(1 for r in results if r["from_cache"])
    errors = sum(1 for r in results if r["errors"])
    deliberated = len(results) - cache_hits - errors

    print(f"\n  Délibérations complètes : {deliberated}")
    print(f"  Cache-hits (ADR-013)    : {cache_hits} *")
    print(f"  Erreurs                 : {errors}")
    print(f"\n  Durée totale : {int(total_duration // 60)}m {int(total_duration % 60)}s")

    # Verdicts par catégorie
    print("\n  [VERDICTS PAR CATÉGORIE]")
    for category in categories:
        cat_results = [r for r in results if r["category"] == category]
        for r in cat_results:
            status = "*" if r["from_cache"] else ("ERR" if r["errors"] else "")
            score = int((r["consensus_score"] or 0) * 100)
            print(
                f"    {r['id']:8s} -> {r['verdict'] or 'ERR':25s} "
                f"({score:3d}%) entropy={r['vote_entropy'] or 0:.2f} {status}"
            )

    # Insights épistémiques
    valid = [r for r in results if not r["errors"] and r["consensus_score"]]
    if valid:
        high_consensus = [r for r in valid if (r["consensus_score"] or 0) >= 0.85]
        contested = [r for r in valid if (r["consensus_score"] or 0) < 0.6]
        high_entropy = [r for r in valid if (r["vote_entropy"] or 0) >= 0.98]

        print("\n  [INSIGHTS ÉPISTÉMIQUES]")
        print(f"    Consensus fort (>=85%)  : {len(high_consensus)} claims")
        print(f"    Contestées (<60%)      : {len(contested)} claims")
        print(f"    Entropie maximale      : {len(high_entropy)} claims")

        if contested:
            print("\n    Claims les plus contestées :")
            for r in sorted(contested, key=lambda x: x["consensus_score"] or 0):
                print(f"      {r['id']} — {r['claim'][:60]}...")
                print(f"             consensus={int((r['consensus_score'] or 0)*100)}% entropy={r['vote_entropy']:.2f}")

    # Sauvegarde JSON
    report = {
        "scenario": "graph_seeder_blockchain",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "models": MODELS,
        "model_count": len(MODELS),
        "total_claims": len(CLAIMS),
        "cache_hits": cache_hits,
        "deliberated": deliberated,
        "errors": errors,
        "total_duration_s": round(total_duration, 1),
        "claims": results,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n  Report: {report_path}")
    print("=" * 65)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())