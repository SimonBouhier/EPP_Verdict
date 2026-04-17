use anchor_lang::prelude::*;

mod constants;
mod errors;
mod state;

use constants::*;
use errors::*;
use state::*;

// AUDIT_REQUIRED: This is the core Solana program.
// Every instruction, PDA derivation, and validation must be reviewed
// by a qualified Solana developer before mainnet deployment.

declare_id!("9QtybfyZQFhra1D6S3NtD6jD4z2Z3wcYmf4YXETq8bSD");

#[program]
pub mod epp {
    use super::*;

    /// Submit a new epistemic attestation on-chain.
    ///
    /// PDA: [b"attestation", submitter, claim_hash]
    ///
    /// # AUDIT_REQUIRED
    /// - Validate all input ranges
    /// - Verify PDA derivation is canonical
    /// - Ensure no reentrancy
    pub fn submit_attestation(
        ctx: Context<SubmitAttestation>,
        claim_hash: [u8; 32],
        subject: [u8; MAX_SUBJECT_LEN],
        predicate: [u8; MAX_PREDICATE_LEN],
        object: [u8; MAX_OBJECT_LEN],
        consensus_score: u16,
        models_consulted: u8,
        models_agreeing: u8,
        sig_agreement: u16,
        sig_semantic_consistency: u16,
        sig_centrality: u16,
        sig_stability: u16,
        sig_relation_diversity: u16,
        epistemic_type: u8,
        confidence_tier: u8,
        frame_hash: [u8; 32],
        source_anchor: [u8; 32],
        timestamp: i64,
        validation_count: u16,
        protocol_version: u16,
        is_challenge: bool,
        challenged_attestation: Pubkey,
    ) -> Result<()> {
        // === VALIDATION ===
        require!(consensus_score <= SCORE_SCALE, EppError::InvalidConsensusScore);
        require!(sig_agreement <= SCORE_SCALE, EppError::InvalidSignatureValue);
        require!(sig_semantic_consistency <= SCORE_SCALE, EppError::InvalidSignatureValue);
        require!(sig_centrality <= SCORE_SCALE, EppError::InvalidSignatureValue);
        require!(sig_stability <= SCORE_SCALE, EppError::InvalidSignatureValue);
        require!(sig_relation_diversity <= SCORE_SCALE, EppError::InvalidSignatureValue);
        require!(models_agreeing <= models_consulted, EppError::InvalidModelCount);
        // Epistemic type V2 — 3 catégories formellement vérifiables (préparation Lean 4).
        //   0 = empirical      (consensus multi-LLM)
        //   1 = deterministic  (source autoritaire, ADR-012)
        //   2 = assessed       (audit dirigé, ADR-014)
        // Invariants Lean 4 cibles (à implémenter ultérieurement, non bloquants ici) :
        //   - empirical       : tier verified ⇒ consensus_score ≥ 0.85 ∧ models_consulted ≥ 3
        //   - deterministic   : source_anchor ≠ [0u8; 32]
        //   - assessed        : domaine-spécifique (spec à définir par ADR dédié)
        require!(epistemic_type <= 2, EppError::InvalidEpistemicType);
        require!(confidence_tier <= 3, EppError::InvalidConfidenceTier);

        // === POPULATE ACCOUNT ===
        let attestation = &mut ctx.accounts.attestation;
        attestation.bump = ctx.bumps.attestation;
        attestation.submitter = ctx.accounts.submitter.key();
        attestation.claim_hash = claim_hash;
        attestation.subject = subject;
        attestation.predicate = predicate;
        attestation.object = object;
        attestation.consensus_score = consensus_score;
        attestation.models_consulted = models_consulted;
        attestation.models_agreeing = models_agreeing;
        attestation.sig_agreement = sig_agreement;
        attestation.sig_semantic_consistency = sig_semantic_consistency;
        attestation.sig_centrality = sig_centrality;
        attestation.sig_stability = sig_stability;
        attestation.sig_relation_diversity = sig_relation_diversity;
        attestation.epistemic_type = epistemic_type;
        attestation.confidence_tier = confidence_tier;
        attestation.frame_hash = frame_hash;
        attestation.source_anchor = source_anchor;
        attestation.timestamp = timestamp;
        attestation.last_revalidated = timestamp;
        attestation.validation_count = validation_count;
        attestation.protocol_version = protocol_version;
        attestation.is_challenge = is_challenge;
        attestation.challenged_attestation = challenged_attestation;

        msg!("EPP: Attestation submitted. claim_hash={:?}", &claim_hash[..8]);
        Ok(())
    }

    /// Query attestations by claim_hash (off-chain via getProgramAccounts).
    /// This instruction is a no-op placeholder -- queries happen client-side.
    /// Kept as documentation of the query pattern.
    ///
    /// Client-side: Use memcmp filter on claim_hash offset to find all
    /// attestations for a given claim.
    pub fn ping(ctx: Context<Ping>) -> Result<()> {
        msg!("EPP: Program is alive. Program ID: {}", crate::ID);
        Ok(())
    }
}

// === ACCOUNT CONTEXTS ===

#[derive(Accounts)]
#[instruction(claim_hash: [u8; 32])]
pub struct SubmitAttestation<'info> {
    /// The attestation PDA to create.
    /// AUDIT_CLEARED 2026-02-23 — PDA seeds [b"attestation", submitter, claim_hash] vérifiés vs client.py:derive_attestation_pda
    #[account(
        init,
        payer = submitter,
        space = EpistemicAttestation::SIZE,
        seeds = [ATTESTATION_SEED, submitter.key().as_ref(), &claim_hash],
        bump
    )]
    pub attestation: Account<'info, EpistemicAttestation>,

    /// The submitter (pays for account creation).
    #[account(mut)]
    pub submitter: Signer<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Ping<'info> {
    pub signer: Signer<'info>,
}
