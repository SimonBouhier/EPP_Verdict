// AUDIT_REQUIRED: All size constants affect rent costs and account validation.

/// Maximum length for subject field (UTF-8 bytes, zero-padded)
pub const MAX_SUBJECT_LEN: usize = 64;

/// Maximum length for predicate field
pub const MAX_PREDICATE_LEN: usize = 64;

/// Maximum length for object field
pub const MAX_OBJECT_LEN: usize = 128;

/// Maximum length for protocol version string
pub const MAX_PROTOCOL_VERSION_LEN: usize = 8;

/// Discriminator size (Anchor standard)
pub const DISCRIMINATOR_SIZE: usize = 8;

/// Scale factor for float->u16 conversion (0.0-1.0 -> 0-10000)
pub const SCORE_SCALE: u16 = 10000;

/// PDA seed prefix
pub const ATTESTATION_SEED: &[u8] = b"attestation";

/// Challenge PDA seed prefix
pub const CHALLENGE_SEED: &[u8] = b"challenge";
