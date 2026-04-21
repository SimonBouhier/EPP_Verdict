import { z } from 'zod';
import {
  ClaimTypeSchema,
  type ScenarioRun,
  ScenarioRunSchema,
  VerdictSchema,
} from '@/domain';

/**
 * Raw shape emitted by `demos/scenario_flywheel_v2.py` (ADR-018).
 *
 * Carries the rich set of flywheel-specific fields (baseline_*, delta,
 * flywheel_*) that the dedicated flywheel split feature will consume from
 * the preserved `raw` payload.
 */
const RawFlywheelV2ClaimSchema = z.object({
  id: z.string(),
  claim: z.string(),
  category: z.string(),
  claim_type: ClaimTypeSchema,
  verify_verdict: VerdictSchema,
  verify_score: z.number(),
  vote_entropy: z.number().nullable(),
  duration_s: z.number(),

  baseline_verify_score: z.number().nullish(),
  baseline_verify_verdict: VerdictSchema.nullish(),
  delta: z.number().nullish(),

  flywheel_anchors_found: z.number().int().nullish(),
  flywheel_sources_injected: z.array(z.string()).nullish(),
  flywheel_enabled: z.boolean().nullish(),

  expected_verdict: VerdictSchema.nullish(),
  verdict_ok: z.boolean().nullish(),

  errors: z.string().nullish(),
  verify_errors: z.string().nullish(),
});

const RawFlywheelV2RunSchema = z.object({
  scenario: z.literal('scenario_flywheel_v2'),
  timestamp: z.string(),
  models: z.array(z.string()),
  adr: z.string().optional(),
  claims: z.array(RawFlywheelV2ClaimSchema),
});

export function flywheelV2Adapter(raw: unknown): ScenarioRun {
  const parsed = RawFlywheelV2RunSchema.parse(raw);
  return ScenarioRunSchema.parse({
    scenario: parsed.scenario,
    timestamp: parsed.timestamp,
    models: parsed.models,
    adr: parsed.adr,
    claims: parsed.claims.map((c) => ({
      id: c.id,
      text: c.claim,
      category: c.category,
      claimType: c.claim_type,
      verdict: c.verify_verdict,
      consensusScore: c.verify_score,
      voteEntropy: c.vote_entropy,
      modelsAgreed: null,
      modelsTotal: null,
      durationS: c.duration_s,
      expectedVerdict: c.expected_verdict ?? null,
      verdictOk: c.verdict_ok ?? null,
      errors: c.errors ?? c.verify_errors ?? '',
    })),
    raw,
  });
}
