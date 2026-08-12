#!/usr/bin/env python
"""
Push curated EPP attestations to Solana devnet.

Reads attestations from local SQLite DBs (data/epp_devnet.db,
data/epp_audit_devnet.db), pushes them via the existing
EppSolanaClient.submit_attestation() API, and writes a manifest at
data/devnet_pushed.json that the UI dashboard (Phase C.2) consumes.

Default mix: 8 general_knowledge + 4 smartcontract_audit attestations.

Idempotent: re-running skips claim_hashes already listed in the manifest
with a non-error tx_signature. Failure-tolerant: per-attestation
exceptions are recorded in the manifest, never abort the whole batch.
Crash-safe: manifest is flushed atomically after every successful push.

Usage:
    python scripts/push_to_devnet.py --dry-run      # preview only
    python scripts/push_to_devnet.py                # real push
    python scripts/push_to_devnet.py -v             # verbose
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Project root on path so this script runs standalone from anywhere.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.engine import ISpaceDB
from services.esmm.attestation import EpistemicAttestation
from services.solana.client import EppSolanaClient, derive_attestation_pda
from services.solana.config import SolanaCluster, SolanaConfig
from services.metrology import PREDEFINED_FRAMES

logger = logging.getLogger("push_to_devnet")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CandidateRow:
    """A row pulled from the attestations table that's a candidate for push."""

    claim_hash: str
    portable_json: str
    metrological_frame: str
    consensus_score: float
    question: Optional[str]
    db_path: str  # which DB it came from, for write-back routing


@dataclass
class PushOutcome:
    """Result of attempting to push one attestation."""

    claim_hash: str
    status: str  # "ok" | "error"
    tx_signature: Optional[str]
    pda: Optional[str]
    slot: Optional[int]
    explorer_url: Optional[str]
    error: Optional[str]
    pushed_at: str
    # Pre-fetched fields used for the manifest entry
    subject: str
    predicate: str
    object_: str  # 'object' would shadow the builtin
    consensus_score: float
    confidence_tier: str
    epistemic_type: str
    metrological_frame: str
    frame_hash: str
    question: Optional[str]
    verdict: Optional[str]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Push curated EPP attestations to Solana devnet.",
    )
    p.add_argument(
        "--manifest",
        default="data/devnet_pushed.json",
        help="Output manifest path (default: %(default)s).",
    )
    p.add_argument(
        "--general-db",
        default="data/epp_devnet.db",
        help="DB containing general_knowledge attestations (default: %(default)s).",
    )
    p.add_argument(
        "--general-frame",
        default="general_knowledge_v1.0",
        help="Frame ID for the general bucket (default: %(default)s).",
    )
    p.add_argument(
        "--general-count",
        type=int,
        default=8,
        help="Number of general attestations to push (default: %(default)s).",
    )
    p.add_argument(
        "--audit-db",
        default="data/epp_audit_devnet.db",
        help="DB containing smart-contract audit attestations (default: %(default)s).",
    )
    p.add_argument(
        "--audit-frame",
        default="smartcontract_audit_v1.0",
        help="Frame ID for the audit bucket (default: %(default)s).",
    )
    p.add_argument(
        "--audit-count",
        type=int,
        default=4,
        help="Number of audit attestations to push (default: %(default)s).",
    )
    p.add_argument(
        "--min-score",
        type=float,
        default=0.7,
        help="Skip attestations below this consensus_score (default: %(default)s).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print candidates and exit without submitting.",
    )
    p.add_argument(
        "--keypair",
        default=None,
        help="Override keypair path (default: ~/.config/solana/id.json).",
    )
    p.add_argument(
        "--no-update-db",
        action="store_true",
        help="Skip writing solana_tx_signature back to SQLite.",
    )
    p.add_argument(
        "--no-slot",
        action="store_true",
        help="Skip getSignatureStatuses lookup (faster, leaves slot=null).",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args()


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=level,
    )


# ---------------------------------------------------------------------------
# DB read / manifest read
# ---------------------------------------------------------------------------


def load_existing_manifest(path: Path) -> Dict[str, Dict[str, Any]]:
    """Returns {claim_hash: entry} for entries with a real tx_signature.

    Used for idempotent skip — the script will not re-push anything that
    already has a successful entry in the manifest.
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not parse existing manifest (%s); starting fresh.", exc)
        return {}
    by_hash: Dict[str, Dict[str, Any]] = {}
    for entry in data.get("attestations", []):
        if entry.get("status") == "ok" and entry.get("tx_signature"):
            by_hash[entry["claim_hash"]] = entry
    return by_hash


def load_candidates(
    db_path: str,
    frame_id: str,
    limit: int,
    min_score: float,
    skip_hashes: Set[str],
) -> List[CandidateRow]:
    """Pull top-N attestations matching frame, sorted by consensus_score desc."""
    if not Path(db_path).exists():
        logger.warning("DB not found: %s — skipping bucket", db_path)
        return []
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT claim_hash, portable_json, metrological_frame,
                   consensus_score, question
            FROM attestations
            WHERE solana_tx_signature IS NULL
              AND metrological_frame = ?
              AND consensus_score >= ?
            ORDER BY consensus_score DESC, timestamp DESC
            """,
            (frame_id, min_score),
        ).fetchall()
    finally:
        conn.close()
    candidates: List[CandidateRow] = []
    seen_in_bucket: Set[str] = set()
    for r in rows:
        # Dedupe both against externally pushed claims and within the bucket:
        # the DB allows multiple rows per claim_hash (re-validations) but the
        # on-chain PDA is unique per (submitter, claim_hash), so a second push
        # of the same hash would fail Anchor's `init` constraint.
        if r[0] in skip_hashes or r[0] in seen_in_bucket:
            continue
        seen_in_bucket.add(r[0])
        candidates.append(
            CandidateRow(
                claim_hash=r[0],
                portable_json=r[1],
                metrological_frame=r[2],
                consensus_score=r[3],
                question=r[4],
                db_path=db_path,
            ),
        )
        if len(candidates) >= limit:
            break
    return candidates


def rehydrate(row: CandidateRow) -> EpistemicAttestation:
    return EpistemicAttestation.model_validate_json(row.portable_json)


# ---------------------------------------------------------------------------
# Push primitives
# ---------------------------------------------------------------------------


async def fetch_slot(client: EppSolanaClient, tx_sig: str) -> Optional[int]:
    """Best-effort slot lookup via getSignatureStatuses. Returns None on failure."""
    try:
        from solders.signature import Signature  # type: ignore[import-not-found]

        sig_obj = Signature.from_string(tx_sig)
        # mypy/lint: client._client is the underlying AsyncClient set in connect().
        rpc = client._client  # type: ignore[union-attr]
        if rpc is None:
            return None
        resp = await rpc.get_signature_statuses([sig_obj])
        if resp and getattr(resp, "value", None) and resp.value[0]:
            return resp.value[0].slot
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.debug("slot fetch failed for %s…: %s", tx_sig[:12], exc)
    return None


def derive_verdict_from_object(obj: str) -> Optional[str]:
    """Best-effort verdict extraction.

    Many attestations encode the verdict as the triplet `object` (e.g.
    'SUPPORTED', 'CONTESTED'). When that's not the case, we return None and
    the UI will simply not show a verdict label for that on-chain badge.
    """
    upper = obj.upper().strip()
    for v in ("SUPPORTED", "CONTESTED", "INSUFFICIENT_EVIDENCE", "REFUTED"):
        if v in upper:
            return v
    return None


async def push_one(
    client: EppSolanaClient,
    db: Optional[ISpaceDB],
    candidate: CandidateRow,
    frame_hash_hex: str,
    program_id: str,
    submitter_pubkey: str,
    fetch_slot_after: bool,
) -> PushOutcome:
    """Submit one attestation, optionally enrich with slot, optionally write back."""
    pushed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Stage 1: rehydrate.
    try:
        att = rehydrate(candidate)
    except Exception as exc:  # noqa: BLE001
        return PushOutcome(
            claim_hash=candidate.claim_hash,
            status="error",
            tx_signature=None,
            pda=None,
            slot=None,
            explorer_url=None,
            error=f"rehydrate_failed: {exc}",
            pushed_at=pushed_at,
            subject="",
            predicate="",
            object_="",
            consensus_score=candidate.consensus_score,
            confidence_tier="",
            epistemic_type="",
            metrological_frame=candidate.metrological_frame,
            frame_hash=frame_hash_hex,
            question=candidate.question,
            verdict=None,
        )

    # Stage 2: pre-derive PDA so we can include it even on failure.
    pda: Optional[str]
    try:
        pda, _bump = derive_attestation_pda(
            program_id, submitter_pubkey, bytes.fromhex(att.claim_hash),
        )
    except Exception:  # noqa: BLE001
        pda = None

    # Stage 3: submit.
    try:
        tx_sig = await client.submit_attestation(att, frame_hash=frame_hash_hex)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "submit_attestation failed for %s…: %s", candidate.claim_hash[:12], exc,
        )
        return PushOutcome(
            claim_hash=candidate.claim_hash,
            status="error",
            tx_signature=None,
            pda=pda,
            slot=None,
            explorer_url=None,
            error=f"submit_failed: {exc}",
            pushed_at=pushed_at,
            subject=att.subject,
            predicate=att.predicate,
            object_=att.object,
            consensus_score=att.consensus_score,
            confidence_tier=att.confidence_tier,
            epistemic_type=att.epistemic_type,
            metrological_frame=att.metrological_frame or candidate.metrological_frame,
            frame_hash=frame_hash_hex,
            question=att.question or candidate.question,
            verdict=derive_verdict_from_object(att.object),
        )

    # Stage 4: enrich (slot) + side-effects (DB write-back). Both best-effort:
    # neither failure invalidates the on-chain push that already succeeded.
    slot = await fetch_slot(client, tx_sig) if fetch_slot_after else None
    explorer_url = client.get_explorer_url(tx_sig)

    if db is not None:
        try:
            await db.update_attestation_solana_tx(att.claim_hash, tx_sig, slot)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "DB write-back failed for %s…: %s", att.claim_hash[:12], exc,
            )

    return PushOutcome(
        claim_hash=att.claim_hash,
        status="ok",
        tx_signature=tx_sig,
        pda=pda,
        slot=slot,
        explorer_url=explorer_url,
        error=None,
        pushed_at=pushed_at,
        subject=att.subject,
        predicate=att.predicate,
        object_=att.object,
        consensus_score=att.consensus_score,
        confidence_tier=att.confidence_tier,
        epistemic_type=att.epistemic_type,
        metrological_frame=att.metrological_frame or candidate.metrological_frame,
        frame_hash=frame_hash_hex,
        question=att.question or candidate.question,
        verdict=derive_verdict_from_object(att.object),
    )


# ---------------------------------------------------------------------------
# Manifest serialization
# ---------------------------------------------------------------------------


def outcome_to_entry(o: PushOutcome) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "claim_hash": o.claim_hash,
        "subject": o.subject,
        "predicate": o.predicate,
        "object": o.object_,
        "question": o.question,
        "verdict": o.verdict,
        "consensus_score": o.consensus_score,
        "confidence_tier": o.confidence_tier,
        "epistemic_type": o.epistemic_type,
        "metrological_frame": o.metrological_frame,
        "frame_hash": o.frame_hash,
        "tx_signature": o.tx_signature,
        "pda": o.pda,
        "slot": o.slot,
        "explorer_url": o.explorer_url,
        "pushed_at": o.pushed_at,
        "status": o.status,
    }
    if o.error:
        entry["error"] = o.error
    return entry


def write_manifest_atomic(
    path: Path,
    program_id: str,
    cluster: str,
    rpc_url: str,
    submitter: str,
    entries: List[Dict[str, Any]],
) -> None:
    """Atomic write: tmp file in same dir + os.replace. Avoids partial writes."""
    pushed = sum(1 for e in entries if e.get("status") == "ok")
    failed = sum(1 for e in entries if e.get("status") == "error")
    manifest = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "programId": program_id,
        "cluster": cluster,
        "rpcUrl": rpc_url,
        "submitter": submitter,
        "scriptVersion": "1",
        "summary": {
            "pushed": pushed,
            "failed": failed,
            "total_entries": len(entries),
        },
        "attestations": entries,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(manifest, tmp, indent=2, ensure_ascii=False)
            tmp.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        # Best-effort cleanup if rename failed.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Dry-run printer
# ---------------------------------------------------------------------------


def print_dry_run(buckets: List[List[CandidateRow]]) -> None:
    print("\n=== Push candidates (dry-run) ===\n")
    n = 0
    for bucket in buckets:
        for c in bucket:
            n += 1
            q = (c.question or "").replace("\n", " ").strip()
            print(
                f"{n:>3}. [{c.metrological_frame:<28}] "
                f"score={c.consensus_score:.3f}  "
                f"hash={c.claim_hash[:12]}…  "
                f"q={q[:60]}",
            )
    print(f"\nTotal: {n} attestations would be pushed.\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def amain() -> int:
    args = parse_args()
    setup_logging(args.verbose)

    manifest_path = Path(args.manifest)
    pushed_set = load_existing_manifest(manifest_path)
    skip_hashes = set(pushed_set.keys())
    if skip_hashes:
        logger.info(
            "Found %d already-pushed attestations in manifest; will skip them.",
            len(skip_hashes),
        )

    # Build candidate buckets — the curated mix. Dedupe across buckets too:
    # a hash picked by the general bucket must not be re-picked by the audit
    # bucket (would collide on the same on-chain PDA).
    general = load_candidates(
        args.general_db,
        args.general_frame,
        args.general_count,
        args.min_score,
        skip_hashes,
    )
    skip_for_audit = skip_hashes | {c.claim_hash for c in general}
    audit = load_candidates(
        args.audit_db,
        args.audit_frame,
        args.audit_count,
        args.min_score,
        skip_for_audit,
    )
    buckets: List[List[CandidateRow]] = [general, audit]
    total_candidates = sum(len(b) for b in buckets)

    if total_candidates == 0:
        logger.info("No candidates to push (everything is already on-chain or filtered out).")
        return 0

    if args.dry_run:
        print_dry_run(buckets)
        return 0

    # Resolve frame hashes once (frames in the registry are factories).
    frame_hash_cache: Dict[str, str] = {}
    for frame_id in {args.general_frame, args.audit_frame}:
        if frame_id not in PREDEFINED_FRAMES:
            logger.error(
                "Unknown frame: %s. Known frames: %s",
                frame_id, sorted(PREDEFINED_FRAMES.keys()),
            )
            return 2
        frame = PREDEFINED_FRAMES[frame_id]()
        frame_hash_cache[frame_id] = frame.compute_frame_hash()
        logger.debug("Frame %s → hash %s", frame_id, frame_hash_cache[frame_id][:16])

    # Build Solana client. Refuse to silently mock — we want real pushes only.
    keypair_path = args.keypair or str(Path.home() / ".config" / "solana" / "id.json")
    if not Path(keypair_path).exists():
        logger.error(
            "Keypair not found at %s. Set up devnet wallet first.", keypair_path,
        )
        return 3
    config = SolanaConfig(cluster=SolanaCluster.DEVNET, keypair_path=keypair_path)
    client = EppSolanaClient(config)
    if not client.is_ready:
        logger.error(
            "Client not ready (Solana SDK or keypair missing). Refusing to silently mock. "
            "Install solana / solders / anchorpy and retry.",
        )
        return 4
    submitter_pubkey = client.submitter_pubkey
    program_id = config.program_id
    if submitter_pubkey is None or program_id is None:
        logger.error("Missing submitter pubkey or program id after client init.")
        return 4

    await client.connect()
    logger.info(
        "Connected. Submitter=%s  Program=%s  Cluster=%s",
        submitter_pubkey, program_id, SolanaCluster.DEVNET.name,
    )

    # Open DBs for write-back (best-effort; one DB per bucket).
    db_handles: Dict[str, ISpaceDB] = {}
    if not args.no_update_db:
        for db_path in {args.general_db, args.audit_db}:
            if not Path(db_path).exists():
                continue
            db = ISpaceDB(db_path)
            try:
                await db.initialize()
                db_handles[db_path] = db
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Could not open DB %s for write-back (%s); continuing.", db_path, exc,
                )

    existing_entries: List[Dict[str, Any]] = list(pushed_set.values())
    new_entries: List[Dict[str, Any]] = []

    try:
        for bucket in buckets:
            for candidate in bucket:
                db = db_handles.get(candidate.db_path)
                outcome = await push_one(
                    client=client,
                    db=db,
                    candidate=candidate,
                    frame_hash_hex=frame_hash_cache[candidate.metrological_frame],
                    program_id=program_id,
                    submitter_pubkey=submitter_pubkey,
                    fetch_slot_after=not args.no_slot,
                )
                new_entries.append(outcome_to_entry(outcome))
                # Crash-safe: flush after every push so we never lose paid SOL.
                write_manifest_atomic(
                    manifest_path,
                    program_id,
                    "devnet",
                    SolanaCluster.DEVNET.value,
                    submitter_pubkey,
                    existing_entries + new_entries,
                )
                if outcome.status == "ok":
                    sig_short = (outcome.tx_signature or "")[:16]
                    logger.info(
                        "OK  %s…  sig=%s…  slot=%s  %s",
                        candidate.claim_hash[:12],
                        sig_short,
                        outcome.slot,
                        outcome.explorer_url,
                    )
                else:
                    logger.error(
                        "ERR %s…: %s", candidate.claim_hash[:12], outcome.error,
                    )
    finally:
        await client.disconnect()
        # ISpaceDB has no explicit close — connection pool is GC-managed.

    # Final summary.
    ok_count = sum(1 for e in new_entries if e["status"] == "ok")
    err_count = sum(1 for e in new_entries if e["status"] == "error")
    skipped = len(skip_hashes)
    print()
    print(
        f"Summary: pushed={ok_count}, failed={err_count}, "
        f"skipped_existing={skipped}, manifest={manifest_path}",
    )
    if ok_count > 0:
        first_url = next(
            (e["explorer_url"] for e in new_entries if e.get("explorer_url")), None,
        )
        if first_url:
            print(f"Open: {first_url}")
    return 0 if err_count == 0 else 1


def main() -> int:
    try:
        return asyncio.run(amain())
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
