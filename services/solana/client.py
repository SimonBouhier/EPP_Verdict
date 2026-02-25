"""
Solana client for EPP -- transaction building and submission.

# AUDIT_REQUIRED: This entire module handles blockchain transactions.
# Every function that signs, sends, or reads on-chain data must be
# reviewed by a qualified Solana developer before mainnet.
#
# SECURITY INVARIANTS:
# 1. NEVER sends transactions to mainnet (devnet guard in config.py)
# 2. NEVER stores private keys in code or logs
# 3. ALL transactions are logged with tx signature for audit
# 4. PDA derivation uses CANONICAL seeds only
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from services.solana.config import SolanaConfig, SolanaCluster, validate_cluster
from services.solana.bridge import (
    AnchorAttestationArgs,
    attestation_to_anchor_args,
    anchor_data_to_attestation_summary,
    MAX_SUBJECT_LEN,
)
from services.esmm.attestation import EpistemicAttestation

logger = logging.getLogger("epp.solana.client")

# Attempt to import Solana libraries
# If not available, provide stubs for testing
_SOLANA_AVAILABLE = False
try:
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    from solders.system_program import ID as SYSTEM_PROGRAM_ID
    from solders.hash import Hash
    from solana.rpc.async_api import AsyncClient
    from solana.rpc.commitment import Confirmed
    _SOLANA_AVAILABLE = True
except ImportError:
    logger.warning("Solana libraries not installed. Client will operate in mock mode.")
    Keypair = None
    Pubkey = None
    AsyncClient = None


# === CONSTANTS ===
ATTESTATION_SEED = b"attestation"
ACCOUNT_DISCRIMINATOR_SIZE = 8


def derive_attestation_pda(
    program_id: str,
    submitter: str,
    claim_hash: bytes,
) -> Tuple[str, int]:
    """
    Derive the PDA for an attestation.

    Seeds: [b"attestation", submitter_pubkey, claim_hash]

    # AUDIT_REQUIRED: PDA derivation must match the Anchor program exactly.

    Args:
        program_id: The program ID (base58 string)
        submitter: The submitter's public key (base58 string)
        claim_hash: The claim hash (32 bytes)

    Returns:
        Tuple of (PDA address as base58, bump seed)
    """
    if not _SOLANA_AVAILABLE:
        # Mock for testing without Solana
        mock_pda = hashlib.sha256(
            ATTESTATION_SEED + submitter.encode() + claim_hash
        ).hexdigest()[:44]
        return (mock_pda, 255)

    program_pubkey = Pubkey.from_string(program_id)
    submitter_pubkey = Pubkey.from_string(submitter)

    seeds = [ATTESTATION_SEED, bytes(submitter_pubkey), claim_hash]
    pda, bump = Pubkey.find_program_address(seeds, program_pubkey)

    return (str(pda), bump)


class EppSolanaClient:
    """
    Client Solana pour EPP.

    # AUDIT_REQUIRED: All methods.

    Responsabilites :
    1. Deriver les PDAs d'attestation
    2. Construire les transactions submit_attestation
    3. Signer et envoyer les transactions
    4. Lire les attestations on-chain (getProgramAccounts)
    5. Mettre a jour la DB locale avec la signature tx

    Usage:
        config = SolanaConfig(cluster=SolanaCluster.DEVNET)
        client = EppSolanaClient(config)
        tx_sig = await client.submit_attestation(attestation, frame_hash)
    """

    def __init__(self, config: SolanaConfig):
        """
        Initialize the Solana client.

        # AUDIT_REQUIRED: Validate config, load keypair safely.
        """
        # AUDIT[A10-008] 🟡 FRAGILE: devnet guard contournable via URL RPC directe.
        validate_cluster(config.cluster)  # Devnet guard
        self.config = config
        self._program_id = config.program_id
        self._keypair: Optional[Any] = None
        self._client: Optional[Any] = None
        self._idl: Optional[Dict] = None

        # Load keypair if path is provided
        if config.keypair_path and _SOLANA_AVAILABLE:
            self._load_keypair()

    # AUDIT[A10-009] 🟡 FRAGILE: clé privée chargée depuis JSON non chiffré.
    def _load_keypair(self) -> None:
        """Load keypair from file. NEVER log the private key."""
        if not self.config.keypair_path:
            return

        path = Path(self.config.keypair_path)
        if not path.exists():
            logger.warning(f"Keypair file not found: {path}")
            return

        try:
            with open(path, "r") as f:
                secret_key = json.load(f)
            self._keypair = Keypair.from_bytes(bytes(secret_key))
            # AUDIT[A10-021] 🟢 ACCEPTED: seule la pubkey est loguée — clé privée jamais exposée.
            logger.info(f"Loaded keypair: {self._keypair.pubkey()}")
        except Exception as e:
            logger.error(f"Failed to load keypair: {e}")

    def _load_idl(self, idl_path: Optional[str] = None) -> None:
        """Load Anchor IDL for instruction building."""
        if idl_path is None:
            # Default path relative to project root
            idl_path = "target/idl/epp.json"

        path = Path(idl_path)
        if not path.exists():
            logger.warning(f"IDL file not found: {path}")
            return

        try:
            with open(path, "r") as f:
                self._idl = json.load(f)
            logger.info(f"Loaded IDL: {self._idl.get('name', 'unknown')}")
        except Exception as e:
            logger.error(f"Failed to load IDL: {e}")

    @property
    def is_ready(self) -> bool:
        """Check if client is ready to submit transactions."""
        return (
            _SOLANA_AVAILABLE
            and self._keypair is not None
            and self._program_id is not None
        )

    @property
    def submitter_pubkey(self) -> Optional[str]:
        """Get the submitter's public key."""
        if self._keypair is None:
            return None
        return str(self._keypair.pubkey())

    async def connect(self) -> None:
        """Connect to the Solana cluster."""
        if not _SOLANA_AVAILABLE:
            logger.warning("Solana not available, operating in mock mode")
            return

        self._client = AsyncClient(self.config.rpc_url)
        logger.info(f"Connected to {self.config.cluster.name}: {self.config.rpc_url}")

    async def disconnect(self) -> None:
        """Disconnect from the Solana cluster."""
        if self._client:
            await self._client.close()
            self._client = None

    async def submit_attestation(
        self,
        attestation: EpistemicAttestation,
        frame_hash: Optional[str] = None,
        is_challenge: bool = False,
        challenged_pda: Optional[str] = None,
    ) -> str:
        """
        Submit an attestation on-chain.

        Returns: Transaction signature (base58 string).

        # AUDIT_REQUIRED: PDA derivation, transaction construction, signing.
        """
        # 1. Convert to Anchor args via bridge
        args = attestation_to_anchor_args(
            attestation,
            frame_hash=frame_hash,
            is_challenge=is_challenge,
            challenged_attestation_pubkey=bytes.fromhex(challenged_pda) if challenged_pda else None,
        )

        # 2. Derive PDA (uses mock derivation if solders not available)
        submitter = self.submitter_pubkey or "mock_submitter"
        program_id = self._program_id or "mock_program"
        pda_address, bump = derive_attestation_pda(
            program_id, submitter, args.claim_hash,
        )
        logger.info(f"Derived PDA: {pda_address} (bump={bump})")

        # 3-5. Build, sign, and send transaction
        if not _SOLANA_AVAILABLE or self._client is None:
            # Mock mode — return deterministic fake signature
            mock_sig = hashlib.sha256(
                args.claim_hash + str(attestation.timestamp).encode()
            ).hexdigest()[:88]
            logger.info(f"MOCK: Would submit attestation. Mock sig: {mock_sig}")
            return mock_sig

        # Real mode — requires keypair and connection
        if not self.is_ready:
            raise RuntimeError(
                "Client not ready. Check: Solana libs installed, keypair loaded, program_id set."
            )

        # AUDIT[A10-003] 🔴→✅ FIXED Phase 4.6: transaction building via solders.
        return await self._build_and_send_submit_tx(args, pda_address, bump)

    async def _build_and_send_submit_tx(
        self,
        args: "AnchorAttestationArgs",
        pda_address: str,
        bump: int,
    ) -> str:
        """
        Build, sign, and send the submit_attestation instruction.

        Uses solders for manual instruction building (no anchorpy dependency).
        Anchor discriminator = SHA-256("global:submit_attestation")[:8].

        # AUDIT_REQUIRED: Borsh serialization order MUST match lib.rs.
        """
        import struct

        # Anchor instruction discriminator
        ix_discriminator = hashlib.sha256(
            b"global:submit_attestation"
        ).digest()[:8]

        # Borsh-serialize instruction data (order matches lib.rs)
        ix_data = ix_discriminator
        ix_data += args.claim_hash                              # [u8; 32]
        ix_data += args.subject                                 # [u8; 64]
        ix_data += args.predicate                               # [u8; 64]
        ix_data += args.object_field                            # [u8; 128]
        ix_data += struct.pack("<H", args.consensus_score)      # u16 LE
        ix_data += struct.pack("<B", args.models_consulted)     # u8
        ix_data += struct.pack("<B", args.models_agreeing)      # u8
        ix_data += struct.pack("<H", args.sig_agreement)        # u16 LE
        ix_data += struct.pack("<H", args.sig_semantic_consistency)
        ix_data += struct.pack("<H", args.sig_centrality)
        ix_data += struct.pack("<H", args.sig_stability)
        ix_data += struct.pack("<H", args.sig_relation_diversity)
        ix_data += struct.pack("<B", args.epistemic_type)       # u8
        ix_data += struct.pack("<B", args.confidence_tier)      # u8
        ix_data += args.frame_hash                              # [u8; 32]
        ix_data += args.source_anchor                           # [u8; 32]
        ix_data += struct.pack("<q", args.timestamp)            # i64 LE
        ix_data += struct.pack("<H", args.validation_count)     # u16 LE
        ix_data += struct.pack("<H", args.protocol_version)     # u16 LE
        ix_data += struct.pack("<B", 1 if args.is_challenge else 0)  # bool
        ix_data += args.challenged_attestation                  # [u8; 32]

        # Account metas
        from solders.instruction import Instruction, AccountMeta

        program_pubkey = Pubkey.from_string(self._program_id)
        pda_pubkey = Pubkey.from_string(pda_address)

        accounts = [
            AccountMeta(pda_pubkey, is_signer=False, is_writable=True),
            AccountMeta(self._keypair.pubkey(), is_signer=True, is_writable=True),
            AccountMeta(SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
        ]

        instruction = Instruction(program_pubkey, ix_data, accounts)

        # Build, sign, send
        from solders.transaction import Transaction
        from solders.message import Message

        blockhash_resp = await self._client.get_latest_blockhash()
        recent_blockhash = blockhash_resp.value.blockhash

        msg = Message.new_with_blockhash(
            [instruction], self._keypair.pubkey(), recent_blockhash
        )
        tx = Transaction.new_unsigned(msg)
        tx.sign([self._keypair], recent_blockhash)

        result = await self._client.send_transaction(tx)
        tx_sig = str(result.value)

        logger.info(f"Transaction submitted: {tx_sig}")
        logger.info(f"Explorer: {self.get_explorer_url(tx_sig)}")

        return tx_sig

    # === PDA existence check (Phase 4.6.2) ===

    async def check_pda_exists(
        self,
        submitter_pubkey: str,
        claim_hash: str,
    ) -> bool:
        """
        Check if a PDA account already exists on-chain.

        Phase 4.6.2 — prevents double-submission.
        Returns False in mock mode or if account does not exist.
        """
        if not _SOLANA_AVAILABLE or self._client is None:
            return False

        claim_hash_bytes = bytes.fromhex(claim_hash)
        pda_address, _ = derive_attestation_pda(
            self._program_id, submitter_pubkey, claim_hash_bytes
        )

        pda_pubkey = Pubkey.from_string(pda_address)
        resp = await self._client.get_account_info(pda_pubkey)
        return resp.value is not None

    async def get_attestation(
        self,
        submitter_pubkey: str,
        claim_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Read a single attestation by (submitter, claim_hash).

        # AUDIT_REQUIRED: PDA derivation must match submit.
        """
        if not self._program_id:
            raise RuntimeError("Program ID not set")

        claim_hash_bytes = bytes.fromhex(claim_hash)
        pda_address, _ = derive_attestation_pda(
            self._program_id,
            submitter_pubkey,
            claim_hash_bytes,
        )

        if not _SOLANA_AVAILABLE or self._client is None:
            logger.info(f"MOCK: Would fetch attestation from PDA: {pda_address}")
            return None

        pda_pubkey = Pubkey.from_string(pda_address)
        resp = await self._client.get_account_info(pda_pubkey)
        if resp.value is None:
            return None

        # Deserialize account data (skip 8-byte discriminator)
        data = resp.value.data
        return self._deserialize_attestation_account(data[ACCOUNT_DISCRIMINATOR_SIZE:])

    def _deserialize_attestation_account(self, data: bytes) -> Dict[str, Any]:
        """Deserialize an on-chain attestation account (Borsh layout)."""
        import struct
        from services.solana.bridge import (
            u16_to_float,
            EPISTEMIC_TYPE_REVERSE,
            CONFIDENCE_TIER_REVERSE,
            MAX_SUBJECT_LEN,
            MAX_PREDICATE_LEN,
            MAX_OBJECT_LEN,
        )

        offset = 0

        def read(n: int) -> bytes:
            nonlocal offset
            chunk = data[offset:offset + n]
            offset += n
            return chunk

        bump = struct.unpack("<B", read(1))[0]
        submitter = read(32)
        claim_hash = read(32)
        subject = read(MAX_SUBJECT_LEN).rstrip(b"\x00").decode("utf-8", errors="replace")
        predicate = read(MAX_PREDICATE_LEN).rstrip(b"\x00").decode("utf-8", errors="replace")
        object_field = read(MAX_OBJECT_LEN).rstrip(b"\x00").decode("utf-8", errors="replace")
        consensus_score = struct.unpack("<H", read(2))[0]
        models_consulted = struct.unpack("<B", read(1))[0]
        models_agreeing = struct.unpack("<B", read(1))[0]
        sig_agreement = struct.unpack("<H", read(2))[0]
        sig_semantic_consistency = struct.unpack("<H", read(2))[0]
        sig_centrality = struct.unpack("<H", read(2))[0]
        sig_stability = struct.unpack("<H", read(2))[0]
        sig_relation_diversity = struct.unpack("<H", read(2))[0]
        epistemic_type = struct.unpack("<B", read(1))[0]
        confidence_tier = struct.unpack("<B", read(1))[0]
        frame_hash = read(32)
        source_anchor = read(32)
        timestamp = struct.unpack("<q", read(8))[0]
        last_revalidated = struct.unpack("<q", read(8))[0]
        validation_count = struct.unpack("<H", read(2))[0]
        protocol_version = struct.unpack("<H", read(2))[0]
        is_challenge = struct.unpack("<B", read(1))[0] != 0
        challenged_attestation = read(32)

        if offset != len(data):
            raise ValueError(
                f"Deserialization offset mismatch: consumed {offset} bytes, "
                f"buffer has {len(data)} bytes"
            )

        return {
            "bump": bump,
            "submitter": submitter.hex(),
            "claim_hash": claim_hash.hex(),
            "subject": subject,
            "predicate": predicate,
            "object": object_field,
            "consensus_score": u16_to_float(consensus_score),
            "models_consulted": models_consulted,
            "models_agreeing": models_agreeing,
            "signature_5d": {
                "agreement": u16_to_float(sig_agreement),
                "semantic_consistency": u16_to_float(sig_semantic_consistency),
                "centrality": u16_to_float(sig_centrality),
                "stability": u16_to_float(sig_stability),
                "relation_diversity": u16_to_float(sig_relation_diversity),
            },
            "epistemic_type": EPISTEMIC_TYPE_REVERSE.get(epistemic_type, "unknown"),
            "confidence_tier": CONFIDENCE_TIER_REVERSE.get(confidence_tier, "unknown"),
            "frame_hash": frame_hash.hex(),
            "source_anchor": source_anchor.hex(),
            "timestamp": timestamp,
            "last_revalidated": last_revalidated,
            "validation_count": validation_count,
            "protocol_version": protocol_version,
            "is_challenge": is_challenge,
            "challenged_attestation": challenged_attestation.hex(),
        }

    async def query_attestations_by_claim(
        self,
        claim_hash: str,
        min_consensus: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Query all attestations for a given claim_hash.
        Uses getProgramAccounts with memcmp filter on claim_hash offset.

        # AUDIT_CLEARED 2026-02-23 — CLAIM_HASH_OFFSET=41 vérifié vs state.rs (disc8+bump1+submitter32)
        """
        if not _SOLANA_AVAILABLE or self._client is None:
            logger.info(f"MOCK: Would query attestations for claim: {claim_hash[:16]}...")
            return []

        # Offset: discriminator (8) + bump (1) + submitter (32) = 41 bytes
        CLAIM_HASH_OFFSET = ACCOUNT_DISCRIMINATOR_SIZE + 1 + 32

        from solana.rpc.types import MemcmpOpts

        program_pubkey = Pubkey.from_string(self._program_id)
        filters = [MemcmpOpts(offset=CLAIM_HASH_OFFSET, bytes=claim_hash)]
        resp = await self._client.get_program_accounts(
            program_pubkey, filters=filters
        )

        results = []
        for account_info in resp.value:
            data = account_info.account.data
            parsed = self._deserialize_attestation_account(
                data[ACCOUNT_DISCRIMINATOR_SIZE:]
            )
            if parsed["consensus_score"] >= min_consensus:
                results.append(parsed)

        return results

    async def query_attestations_by_subject(
        self,
        subject: str,
        min_consensus: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Query attestations whose subject field matches.
        Uses getProgramAccounts with memcmp filter on subject offset.

        # AUDIT_CLEARED 2026-02-23 — SUBJECT_OFFSET=73 vérifié vs state.rs (disc8+bump1+submitter32+hash32)
        """
        if not _SOLANA_AVAILABLE or self._client is None:
            logger.info(f"MOCK: Would query attestations for subject: {subject}")
            return []

        # Offset: discriminator (8) + bump (1) + submitter (32) + claim_hash (32) = 73
        SUBJECT_OFFSET = ACCOUNT_DISCRIMINATOR_SIZE + 1 + 32 + 32

        from solana.rpc.types import MemcmpOpts
        from services.solana.bridge import string_to_fixed_bytes

        subject_bytes = string_to_fixed_bytes(subject, MAX_SUBJECT_LEN)
        program_pubkey = Pubkey.from_string(self._program_id)
        filters = [MemcmpOpts(offset=SUBJECT_OFFSET, bytes=subject_bytes.hex())]
        resp = await self._client.get_program_accounts(
            program_pubkey, filters=filters
        )

        results = []
        for account_info in resp.value:
            data = account_info.account.data
            parsed = self._deserialize_attestation_account(
                data[ACCOUNT_DISCRIMINATOR_SIZE:]
            )
            if parsed["consensus_score"] >= min_consensus:
                results.append(parsed)

        return results

    def get_explorer_url(self, tx_signature: str) -> str:
        """Get the Solana Explorer URL for a transaction."""
        cluster_param = ""
        if self.config.cluster == SolanaCluster.DEVNET:
            cluster_param = "?cluster=devnet"
        elif self.config.cluster == SolanaCluster.LOCALNET:
            cluster_param = "?cluster=custom&customUrl=http://127.0.0.1:8899"

        return f"https://explorer.solana.com/tx/{tx_signature}{cluster_param}"
