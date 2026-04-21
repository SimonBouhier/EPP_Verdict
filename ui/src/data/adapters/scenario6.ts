import { z } from 'zod';
import {
  ClaimTypeSchema,
  type ScenarioRun,
  ScenarioRunSchema,
  VerdictSchema,
} from '@/domain';

/**
 * Raw shape for the "scenario 6" family: edge cases and qualifier sensitivity.
 * Three variants (6_1, 6_2, 6_2b) share the same per-claim schema — they only
 * differ in top-level metadata (qualifier_deltas, baseline_scenario...) which is
 * preserved inside `raw` for scenario-specific features to read later.
 */
// Claims that errored mid-pipeline can have null verdict / score / claim_type
// — accept those at the boundary, then filter them out in the adapter.
const RawScenario6ClaimSchema = z.object({
  id: z.string(),
  category: z.string(),
  claim: z.string(),
  note: z.string().nullish(),
  pair_with: z.string().nullish(),
  verdict: VerdictSchema.nullable(),
  consensus_score: z.number().nullable(),
  dissent: z.string().nullish(),
  dissent_score: z.number().nullish(),
  vote_entropy: z.number().nullable(),
  claim_type: ClaimTypeSchema.nullable(),
  decidability_penalty: z.number().nullish(),
  models_agreed: z.number().int().nullable(),
  models_total: z.number().int().nullable(),
  triplets_extracted: z.number().int().nullish(),
  duration_s: z.number(),
  expected_verdict: VerdictSchema.nullable(),
  expected_claim_type: ClaimTypeSchema.nullish(),
  expected_verdict_not: VerdictSchema.nullish(),
  verdict_ok: z.boolean().nullable(),
  claim_type_ok: z.boolean().nullish(),
  errors: z.string(),
});

const RawScenario6RunSchema = z.object({
  scenario: z.enum([
    'scenario_6_1_edge_cases',
    'scenario_6_2_qualifier_sensitivity',
    'scenario_6_2b_qualifier_sensitivity_big_models',
  ]),
  timestamp: z.string(),
  models: z.array(z.string()),
  claims: z.array(RawScenario6ClaimSchema),
});

export function scenario6Adapter(raw: unknown): ScenarioRun {
  const parsed = RawScenario6RunSchema.parse(raw);
  // Drop claims that errored before producing a verdict — they have nothing
  // meaningful to render. The full payload is preserved in `raw` for any
  // feature that wants to surface failure rates.
  const claims = parsed.claims.flatMap((c) => {
    if (c.verdict === null || c.consensus_score === null || c.claim_type === null) {
      return [];
    }
    return [
      {
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
      },
    ];
  });
  return ScenarioRunSchema.parse({
    scenario: parsed.scenario,
    timestamp: parsed.timestamp,
    models: parsed.models,
    claims,
    raw,
  });
}
