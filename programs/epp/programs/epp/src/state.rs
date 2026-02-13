use anchor_lang::prelude::*;
use crate::constants::*;

// AUDIT_REQUIRED: Account struct layout directly affects PDA derivation,
// rent costs, and data integrity. Review all field sizes and types.

/// Epistemic attestation stored on-chain.
///
/// This is the compact projection of a full EpistemicAttestation (Python/off-chain).
/// The complete data (model_votes, portable_json) lives in SQLite off-chain.
/// The claim_hash links on-chain <-> off-chain deterministically.
///
/// PDA seeds: [b"attestation", submitter, claim_hash]
#[account]
pub struct EpistemicAttestation {
    // === PDA METADATA ===
    /// PDA bump seed
    pub bump: u8,                                // 1 byte

    // === IDENTITY ===
    /// Submitter (operator running the ESMM pipeline)
    pub submitter: Pubkey,                       // 32 bytes
    /// SHA-256 of (subject|predicate|object|frame) -- deterministic
    pub claim_hash: [u8; 32],                    // 32 bytes

    // === CONTENT (fixed-size, zero-padded UTF-8) ===
    /// Triplet subject (e.g., "solana")
    pub subject: [u8; MAX_SUBJECT_LEN],          // 64 bytes
    /// Triplet predicate (e.g., "has_tps")
    pub predicate: [u8; MAX_PREDICATE_LEN],      // 64 bytes
    /// Triplet object (e.g., "exceeds 3000")
    pub object: [u8; MAX_OBJECT_LEN],            // 128 bytes

    // === CONSENSUS ===
    /// Consensus score x 10000 (0-10000 maps to 0.0-1.0)
    pub consensus_score: u16,                    // 2 bytes
    /// Number of models consulted in the ESMM run
    pub models_consulted: u8,                    // 1 byte
    /// Number of models that agreed
    pub models_agreeing: u8,                     // 1 byte

    // === EPISTEMIC SIGNATURE 5D (0-cochain) ===
    /// Agreement dimension x 10000
    pub sig_agreement: u16,                      // 2 bytes
    /// Semantic consistency dimension x 10000
    pub sig_semantic_consistency: u16,            // 2 bytes
    /// Centrality dimension x 10000
    pub sig_centrality: u16,                     // 2 bytes
    /// Stability dimension x 10000
    pub sig_stability: u16,                      // 2 bytes
    /// Relation diversity dimension x 10000
    pub sig_relation_diversity: u16,             // 2 bytes

    // === CLASSIFICATION ===
    /// 0=Foundational, 1=Bridge, 2=Specialized, 3=Generalist, 4=Hybrid
    pub epistemic_type: u8,                      // 1 byte
    /// 0=Low, 1=Medium, 2=High, 3=Verified
    pub confidence_tier: u8,                     // 1 byte

    // === METROLOGICAL REFERENCE ===
    /// SHA-256 of the MetrologicalFrame JSON (0x00..00 if no frame)
    pub frame_hash: [u8; 32],                    // 32 bytes
    /// SHA-256 of external verifiable source (0x00..00 if none)
    pub source_anchor: [u8; 32],                 // 32 bytes

    // === TEMPORAL ===
    /// Unix timestamp of crystallization
    pub timestamp: i64,                          // 8 bytes
    /// Unix timestamp of last revalidation (= timestamp if first)
    pub last_revalidated: i64,                   // 8 bytes
    /// Number of validations (1 = first, >1 = revalidated)
    pub validation_count: u16,                   // 2 bytes

    // === PROTOCOL ===
    /// Protocol version as packed u16 (e.g., 100 = v1.0.0)
    pub protocol_version: u16,                   // 2 bytes

    // === CHALLENGE ===
    /// Whether this is a challenge to another attestation
    pub is_challenge: bool,                      // 1 byte
    /// Pubkey of the challenged attestation PDA (Pubkey::default() if not a challenge)
    pub challenged_attestation: Pubkey,          // 32 bytes
    // FUTURE: stake mechanism -- see PHASE_3_DESIGN.md
    // pub stake_amount: u64,
    // pub arbitration_status: u8,
}

impl EpistemicAttestation {
    /// Total space needed for this account (including Anchor discriminator).
    pub const SIZE: usize = DISCRIMINATOR_SIZE  // 8
        + 1                                     // bump
        + 32                                    // submitter
        + 32                                    // claim_hash
        + MAX_SUBJECT_LEN                       // subject (64)
        + MAX_PREDICATE_LEN                     // predicate (64)
        + MAX_OBJECT_LEN                        // object (128)
        + 2                                     // consensus_score
        + 1                                     // models_consulted
        + 1                                     // models_agreeing
        + 2 * 5                                 // sig_5d (10)
        + 1                                     // epistemic_type
        + 1                                     // confidence_tier
        + 32                                    // frame_hash
        + 32                                    // source_anchor
        + 8                                     // timestamp
        + 8                                     // last_revalidated
        + 2                                     // validation_count
        + 2                                     // protocol_version
        + 1                                     // is_challenge
        + 32;                                   // challenged_attestation
    // Total: 8 + 1 + 32 + 32 + 64 + 64 + 128 + 2 + 1 + 1 + 10 + 1 + 1
    //        + 32 + 32 + 8 + 8 + 2 + 2 + 1 + 32 = 462 bytes
}

// === HELPER: Enum mappings ===

/// Maps epistemic_type string to u8.
pub fn epistemic_type_to_u8(t: &str) -> Result<u8> {
    match t {
        "foundational" => Ok(0),
        "bridge" => Ok(1),
        "specialized" => Ok(2),
        "generalist" => Ok(3),
        "hybrid" => Ok(4),
        _ => err!(crate::errors::EppError::InvalidEpistemicType),
    }
}

/// Maps confidence_tier string to u8.
pub fn confidence_tier_to_u8(t: &str) -> Result<u8> {
    match t {
        "low" => Ok(0),
        "medium" => Ok(1),
        "high" => Ok(2),
        "verified" => Ok(3),
        _ => err!(crate::errors::EppError::InvalidConfidenceTier),
    }
}
