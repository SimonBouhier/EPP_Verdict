import { z } from 'zod';
import {
  ClaimTypeSchema,
  type ScenarioRun,
  ScenarioRunSchema,
  VerdictSchema,
} from '@/domain';

/**
 * Raw shape emitted by `demos/scenario_jiang.py` runs.
 * Mirrors the JSON exactly — snake_case, scenario-specific fields kept.
 */
const RawJiangClaimSchema = z.object({
  id: z.string(),
  category: z.string(),
  claim: z.string(),
  source_thesis: z.string().nullish(),
  frame: z.string().nullish(),
  verdict: VerdictSchema,
  consensus_score: z.number(),
  vote_entropy: z.number().nullable(),
  claim_type: ClaimTypeSchema,
  models_agreed: z.number().int().nullable(),
  models_total: z.number().int().nullable(),
  duration_s: z.number(),
  expected_verdict: VerdictSchema.nullable(),
  verdict_ok: z.boolean().nullable(),
  errors: z.string(),
});

const RawJiangRunSchema = z.object({
  scenario: z.literal('scenario_jiang'),
  timestamp: z.string(),
  models: z.array(z.string()),
  claims: z.array(RawJiangClaimSchema),
});

export function jiangAdapter(raw: unknown): ScenarioRun {
  const parsed = RawJiangRunSchema.parse(raw);
  return ScenarioRunSchema.parse({
    scenario: parsed.scenario,
    timestamp: parsed.timestamp,
    models: parsed.models,
    claims: parsed.claims.map((c) => ({
      id: c.id,
      text: c.claim,
      category: c.category,
      claimType: c.claim_type,
      verdict: c.verdict,
      consensusScore: c.consensus_score,
      voteEntropy: c.vote_entropy,
      modelsAgreed: c.models_agreed,
      modelsTotal: c.models_total,
      durationS: c.duration_s,
      expectedVerdict: c.expected_verdict,
      verdictOk: c.verdict_ok,
      errors: c.errors,
    })),
    raw,
  });
}
