use anchor_lang::prelude::*;

// AUDIT_REQUIRED: Error codes must cover all validation failures.

#[error_code]
pub enum EppError {
    #[msg("Subject exceeds maximum length")]
    SubjectTooLong,

    #[msg("Predicate exceeds maximum length")]
    PredicateTooLong,

    #[msg("Object exceeds maximum length")]
    ObjectTooLong,

    #[msg("Consensus score must be between 0 and 10000")]
    InvalidConsensusScore,

    #[msg("Signature 5D values must be between 0 and 10000")]
    InvalidSignatureValue,

    #[msg("Models agreeing cannot exceed models consulted")]
    InvalidModelCount,

    #[msg("Invalid epistemic type")]
    InvalidEpistemicType,

    #[msg("Invalid confidence tier")]
    InvalidConfidenceTier,

    #[msg("Attestation already exists for this submitter and claim")]
    AttestationAlreadyExists,

    #[msg("Challenge references a non-existent attestation")]
    ChallengedAttestationNotFound,

    #[msg("Cannot challenge your own attestation")]
    SelfChallengeNotAllowed,

    // FUTURE: stake mechanism errors
    // #[msg("Insufficient stake for challenge")]
    // InsufficientStake,
}
