"""
Serialization bridge: Python EpistemicAttestation <-> Anchor program.

Converts between:
- Python floats [0.0, 1.0] -> Rust u16 [0, 10000]
- Python strings -> Fixed-size byte arrays (zero-padded UTF-8)
- Python hex strings -> Raw bytes [u8; 32]
- Python enum strings -> Rust u8 enum values

# AUDIT_REQUIRED: This entire module is security-critical.
# Any serialization bug means corrupted on-chain data.
# Must be reviewed by a Solana developer before mainnet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

# Import depuis attestation.py (Phase 0.3)
from services.esmm.attestation import EpistemicAttestation, Signature5D


# === CONSTANTS (must match programs/epp/src/constants.rs) ===
MAX_SUBJECT_LEN = 64
MAX_PREDICATE_LEN = 64
MAX_OBJECT_LEN = 128
SCORE_SCALE = 10000

# === ENUM MAPPINGS (must match programs/epp/src/state.rs) ===
# AUDIT[A10-016,A10-022] 🟢 ACCEPTED: mappings enum Python↔Rust cohérents — testés.
# S1-001 / S1-002 fix (HYBRIDE V2) : projection des 8 types métier Python vers
# 3 catégories on-chain formellement vérifiables (préparation invariants Lean 4).
#   0 = empirical      (consensus multi-LLM : foundational, bridge, specialized,
#                       generalist, hybrid, verdict)
#   1 = deterministic  (source autoritaire externe, ADR-012)
#   2 = assessed       (audit dirigé, ADR-014)
EPISTEMIC_TYPE_MAP = {
    # Catégorie 0 — empirical
    "foundational": 0,
    "bridge": 0,
    "specialized": 0,
    "generalist": 0,
    "hybrid": 0,
    "verdict": 0,
    # Catégorie 1 — deterministic (ADR-012)
    "deterministic": 1,
    # Catégorie 2 — assessed (ADR-014)
    "security_audit": 2,
}

CONFIDENCE_TIER_MAP = {
    "sandbox": 0,
    "proposition": 1,
    "validated": 2,
    "verified": 3,
}

# Reverse maps for deserialization.
# V2 : la projection provoque des collisions côté "empirical" (plusieurs clés
# Python → 0), donc le reverse doit être défini explicitement sur les 3
# catégories on-chain — pas un simple dict comprehension.
EPISTEMIC_TYPE_REVERSE = {
    0: "empirical",
    1: "deterministic",
    2: "assessed",
}
CONFIDENCE_TIER_REVERSE = {
    0: "sandbox",
    1: "proposition",
    2: "validated",
    3: "verified",
}


@dataclass
class AnchorAttestationArgs:
    """
    Arguments prets pour l'instruction Anchor submit_attestation.

    Chaque champ correspond EXACTEMENT a un parametre de l'instruction Rust.
    Les types sont ceux attendus par anchorpy/solders.

    # AUDIT_REQUIRED: Field order and types must match lib.rs instruction signature.
    """
    claim_hash: bytes          # [u8; 32]
    subject: bytes             # [u8; 64] zero-padded
    predicate: bytes           # [u8; 64] zero-padded
    object_field: bytes        # [u8; 128] zero-padded (renamed to avoid Python keyword)
    consensus_score: int       # u16 [0, 10000]
    models_consulted: int      # u8
    models_agreeing: int       # u8
    sig_agreement: int         # u16
    sig_semantic_consistency: int  # u16
    sig_centrality: int        # u16
    sig_stability: int         # u16
    sig_relation_diversity: int   # u16
    epistemic_type: int        # u8
    confidence_tier: int       # u8
    frame_hash: bytes          # [u8; 32]
    source_anchor: bytes       # [u8; 32]
    timestamp: int             # i64
    validation_count: int      # u16
    protocol_version: int      # u16
    is_challenge: bool         # bool
    challenged_attestation: bytes  # Pubkey as 32 bytes


# === ENCODING FUNCTIONS ===

# AUDIT[A10-007] 🟡→✅ RESOLVED S1-005: la guard `0.0 <= value <= 1.0` rejette
# toute valeur > 1.0 (ex. 1.000049) avec ValueError. Le commentaire antérieur
# décrivait un comportement qui n'existe pas — marker reclassé par cohérence
# avec les conventions du repo (cf. AUDIT[A8-001] 🔴→✅ FIXED, etc.).
def float_to_u16(value: float) -> int:
    """
    Encode float [0.0, 1.0] -> u16 [0, 10000].

    # AUDIT_REQUIRED: Precision loss -- 4 decimal places max.
    """
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"Float must be in [0.0, 1.0], got {value}")
    return min(int(round(value * SCORE_SCALE)), SCORE_SCALE)


def u16_to_float(value: int) -> float:
    """Decode u16 [0, 10000] -> float [0.0, 1.0]."""
    if not 0 <= value <= SCORE_SCALE:
        raise ValueError(f"u16 must be in [0, {SCORE_SCALE}], got {value}")
    return value / SCORE_SCALE


# AUDIT[A10-006] 🟡→✅ RESOLVED S1-003: troncature alignée sur frontière de codepoint UTF-8.
def string_to_fixed_bytes(s: str, max_len: int) -> bytes:
    """
    Encode string -> fixed-size bytes (UTF-8, zero-padded, truncated if needed).

    # AUDIT_REQUIRED: Truncation silently loses data. Log a warning?
    """
    encoded = s.encode("utf-8")
    if len(encoded) <= max_len:
        return encoded.ljust(max_len, b"\x00")
    # Tronquer codepoint par codepoint jusqu'à passer sous max_len
    truncated = s
    while len(truncated.encode("utf-8")) > max_len:
        truncated = truncated[:-1]
    return truncated.encode("utf-8").ljust(max_len, b"\x00")


def fixed_bytes_to_string(b: bytes) -> str:
    """Decode fixed-size bytes -> string (strip trailing zeros)."""
    return b.rstrip(b'\x00').decode("utf-8", errors="replace")


# AUDIT[A10-011] 🟡 FRAGILE: ne valide pas la longueur du hex string avant parsing.
def hex_to_bytes32(hex_str: Optional[str]) -> bytes:
    """
    Encode hex string -> [u8; 32]. Returns 32 zero bytes if None/empty.

    # AUDIT_REQUIRED: Validate hex input length.
    """
    if not hex_str:
        return b'\x00' * 32
    raw = bytes.fromhex(hex_str)
    if len(raw) != 32:
        raise ValueError(f"Expected 32 bytes, got {len(raw)} from hex '{hex_str[:16]}...'")
    return raw


# AUDIT[A10-012] 🟡 FRAGILE: protocol version "100.0" → overflow u16 silencieux.
def protocol_version_to_u16(version_str: str) -> int:
    """
    Encode version string -> u16. "0.3" -> 3, "1.0" -> 100, "1.2" -> 120.
    Format: major * 100 + minor.
    """
    parts = version_str.split(".")
    if len(parts) != 2:
        raise ValueError(f"Version must be 'major.minor', got '{version_str}'")
    major, minor = int(parts[0]), int(parts[1])
    return major * 100 + minor


def u16_to_protocol_version(value: int) -> str:
    """Decode u16 -> version string."""
    return f"{value // 100}.{value % 100}"


# === MAIN BRIDGE FUNCTIONS ===

def attestation_to_anchor_args(
    attestation: EpistemicAttestation,
    frame_hash: Optional[str] = None,
    is_challenge: bool = False,
    challenged_attestation_pubkey: Optional[bytes] = None,
) -> AnchorAttestationArgs:
    """
    Convert a Python EpistemicAttestation to Anchor instruction arguments.

    Args:
        attestation: The crystallized attestation from the ESMM pipeline.
        frame_hash: SHA-256 hex of the MetrologicalFrame (compute_frame_hash()).
                    If None and attestation.metrological_frame exists, uses claim_hash logic.
        is_challenge: Whether this attestation challenges another.
        challenged_attestation_pubkey: 32-byte Pubkey of the challenged PDA.

    Returns:
        AnchorAttestationArgs ready for transaction building.

    # AUDIT_REQUIRED: Verify field mapping completeness and correctness.
    """
    sig = attestation.signature_5d

    return AnchorAttestationArgs(
        claim_hash=hex_to_bytes32(attestation.claim_hash),
        subject=string_to_fixed_bytes(attestation.subject, MAX_SUBJECT_LEN),
        predicate=string_to_fixed_bytes(attestation.predicate, MAX_PREDICATE_LEN),
        object_field=string_to_fixed_bytes(attestation.object, MAX_OBJECT_LEN),
        consensus_score=float_to_u16(attestation.consensus_score),
        models_consulted=attestation.models_consulted,
        models_agreeing=attestation.models_agreeing,
        sig_agreement=float_to_u16(sig.agreement),
        sig_semantic_consistency=float_to_u16(sig.semantic_consistency),
        sig_centrality=float_to_u16(sig.centrality),
        sig_stability=float_to_u16(sig.stability),
        sig_relation_diversity=float_to_u16(sig.relation_diversity),
        epistemic_type=EPISTEMIC_TYPE_MAP[attestation.epistemic_type],
        confidence_tier=CONFIDENCE_TIER_MAP[attestation.confidence_tier],
        frame_hash=hex_to_bytes32(frame_hash),
        source_anchor=hex_to_bytes32(attestation.source_anchor),
        timestamp=int(attestation.timestamp),
        validation_count=attestation.validation_count,
        protocol_version=protocol_version_to_u16(attestation.protocol_version),
        is_challenge=is_challenge,
        challenged_attestation=challenged_attestation_pubkey or (b'\x00' * 32),
    )


def anchor_data_to_attestation_summary(
    data: dict,
) -> dict:
    """
    Convert on-chain account data (from getProgramAccounts) back to
    a human-readable summary dict.

    This is the reverse bridge -- used by `epp query` to display results.

    Args:
        data: Raw account data deserialized from Anchor IDL.

    Returns:
        Dict with human-readable field values.

    # AUDIT_REQUIRED: Verify deserialization matches serialization.
    """
    return {
        "claim_hash": data["claim_hash"].hex() if isinstance(data["claim_hash"], bytes) else data["claim_hash"],
        "subject": fixed_bytes_to_string(bytes(data["subject"])) if isinstance(data["subject"], (list, bytes)) else data["subject"],
        "predicate": fixed_bytes_to_string(bytes(data["predicate"])) if isinstance(data["predicate"], (list, bytes)) else data["predicate"],
        "object": fixed_bytes_to_string(bytes(data["object"])) if isinstance(data["object"], (list, bytes)) else data["object"],
        "consensus_score": u16_to_float(data["consensus_score"]),
        "models_consulted": data["models_consulted"],
        "models_agreeing": data["models_agreeing"],
        "signature_5d": {
            "agreement": u16_to_float(data["sig_agreement"]),
            "semantic_consistency": u16_to_float(data["sig_semantic_consistency"]),
            "centrality": u16_to_float(data["sig_centrality"]),
            "stability": u16_to_float(data["sig_stability"]),
            "relation_diversity": u16_to_float(data["sig_relation_diversity"]),
        },
        "epistemic_type": EPISTEMIC_TYPE_REVERSE.get(data["epistemic_type"], f"unknown({data['epistemic_type']})"),
        "confidence_tier": CONFIDENCE_TIER_REVERSE.get(data["confidence_tier"], f"unknown({data['confidence_tier']})"),
        "frame_hash": bytes(data["frame_hash"]).hex() if isinstance(data["frame_hash"], (list, bytes)) else data["frame_hash"],
        "timestamp": data["timestamp"],
        "validation_count": data["validation_count"],
        "protocol_version": u16_to_protocol_version(data["protocol_version"]),
        "is_challenge": data.get("is_challenge", False),
    }
