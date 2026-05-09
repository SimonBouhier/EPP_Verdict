import { z } from 'zod';

/**
 * Canonical verdict labels emitted by the EPP pipeline.
 * Mirrors the Python `Verdict` enum.
 */
export const VerdictSchema = z.enum([
  'SUPPORTED',
  'CONTESTED',
  'INSUFFICIENT_EVIDENCE',
  'REFUTED',
]);
export type Verdict = z.infer<typeof VerdictSchema>;

/**
 * Epistemic nature of a claim — drives how the pipeline scores it.
 * - empirical: verifiable against evidence
 * - normative: opinion / value judgement (system should refuse to rule)
 * - deterministic: bypasses ESMM, resolved by an authoritative source (ADR-012)
 * - speculative: forward-looking / not-yet-verifiable forecast
 * - foundational: bedrock domain claim used to seed the graph; verdict is
 *   produced by the pipeline at attestation time (matches on-chain
 *   `epistemic_type` u8=0, see programs/epp/src/state.rs::epistemic_type_to_u8)
 * - security_audit: audit-time check against a code/spec input (ADR-014;
 *   matches on-chain `epistemic_type` u8=2)
 */
export const ClaimTypeSchema = z.enum([
  'empirical',
  'normative',
  'deterministic',
  'speculative',
  'foundational',
  'security_audit',
]);
export type ClaimType = z.infer<typeof ClaimTypeSchema>;

/**
 * Common, scenario-agnostic shape of a single claim verdict.
 * Adapters normalize raw scenario JSONs into this shape so features stay generic.
 */
export const ClaimVerdictSchema = z.object({
  id: z.string(),
  text: z.string(),
  category: z.string(),
  claimType: ClaimTypeSchema,
  verdict: VerdictSchema,
  consensusScore: z.number().min(0).max(1),
  voteEntropy: z.number().nullable(),
  modelsAgreed: z.number().int().nullable(),
  modelsTotal: z.number().int().nullable(),
  durationS: z.number().nonnegative(),
  expectedVerdict: VerdictSchema.nullable(),
  verdictOk: z.boolean().nullable(),
  errors: z.string(),
});
export type ClaimVerdict = z.infer<typeof ClaimVerdictSchema>;
