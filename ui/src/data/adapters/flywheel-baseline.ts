import { z } from 'zod';
import {
  ClaimTypeSchema,
  type ScenarioRun,
  ScenarioRunSchema,
  VerdictSchema,
} from '@/domain';

/**
 * Raw shape for `flywheel_v2_baseline` runs — the control runs taken with
 * `flywheel_enabled=false` to provide the comparison anchor.
 *
 * Much sparser than the flywheel runs themselves: just verify_verdict /
 * verify_score / vote_entropy. No category, no models_agreed.
 */
const RawBaselineClaimSchema = z.object({
  id: z.string(),
  claim: z.string(),
  verify_verdict: VerdictSchema,
  verify_score: z.number(),
  vote_entropy: z.number().nullable(),
  claim_type: ClaimTypeSchema,
  errors: z.string().nullish(),
  duration_s: z.number(),
});

const RawBaselineRunSchema = z.object({
  scenario: z.literal('flywheel_v2_baseline'),
  timestamp: z.string(),
  models: z.array(z.string()),
  flywheel_enabled: z.boolean().optional(),
  claims: z.array(RawBaselineClaimSchema),
});

export function flywheelBaselineAdapter(raw: unknown): ScenarioRun {
  const parsed = RawBaselineRunSchema.parse(raw);
  return ScenarioRunSchema.parse({
    scenario: parsed.scenario,
    timestamp: parsed.timestamp,
    models: parsed.models,
    claims: parsed.claims.map((c) => ({
      id: c.id,
      text: c.claim,
      category: 'baseline',
      claimType: c.claim_type,
      verdict: c.verify_verdict,
      consensusScore: c.verify_score,
      voteEntropy: c.vote_entropy,
      modelsAgreed: null,
      modelsTotal: null,
      durationS: c.duration_s,
      expectedVerdict: null,
      verdictOk: null,
      errors: c.errors ?? '',
    })),
    raw,
  });
}
