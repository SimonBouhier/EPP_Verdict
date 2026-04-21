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
 */
export const ClaimTypeSchema = z.enum([
  'empirical',
  'normative',
  'deterministic',
  'speculative',
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
