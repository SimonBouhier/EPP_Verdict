import { z } from 'zod';
import {
  ClaimTypeSchema,
  type OnChainManifest,
  type ScenarioRun,
  ScenarioRunSchema,
  VerdictSchema,
} from '@/domain';

/**
 * Raw shape for `graph_seeder_blockchain` runs (TD-002).
 *
 * The seeder publishes claims with `verdict: null` and a non-standard
 * `claim_type: "foundational"`. Verdicts are produced by the pipeline
 * later, when claims are pushed on-chain. This adapter joins the seeder
 * payload with the on-chain manifest (`devnet_pushed.json`) and surfaces
 * only the claims that have a matching attestation — picking up the
 * verdict from there.
 *
 * Claims in the seeder JSON without an on-chain attestation are dropped;
 * the full payload remains available via `raw` for any feature that wants
 * to surface seeding-only metrics.
 */
const RawSeederClaimSchema = z.object({
  id: z.string(),
  category: z.string(),
  claim: z.string(),
  frame: z.string(),
  note: z.string().nullish(),
  verdict: VerdictSchema.nullable(),
  consensus_score: z.number(),
  claim_type: ClaimTypeSchema,
  vote_entropy: z.number().nullable(),
  models_agreed: z.number().int().nullable(),
  models_total: z.number().int().nullable(),
  triplets_extracted: z.number().int().nullish(),
  from_cache: z.boolean().nullish(),
  duration_s: z.number(),
  errors: z.string(),
});

const RawSeederRunSchema = z.object({
  scenario: z.literal('graph_seeder_blockchain'),
  timestamp: z.string(),
  models: z.array(z.string()),
  claims: z.array(RawSeederClaimSchema),
});

export function graphSeederBlockchainAdapter(
  raw: unknown,
  onchain?: OnChainManifest,
): ScenarioRun {
  const parsed = RawSeederRunSchema.parse(raw);

  // Index on-chain attestations by question text for O(1) lookup.
  // The seeder stores the original claim text in `claim`; the on-chain
  // attestation stores it (verbatim) in `question`.
  const byQuestion = new Map<string, OnChainManifest['attestations'][number]>();
  if (onchain) {
    for (const att of onchain.attestations) {
      if (att.question !== null) {
        byQuestion.set(att.question, att);
      }
    }
  }

  // Drop claims without an on-chain attestation; pick up verdict from
  // the matching attestation when present.
  const claims = parsed.claims.flatMap((c) => {
    const att = byQuestion.get(c.claim);
    if (!att || att.verdict === null) {
      return [];
    }
    return [
      {
        id: c.id,
        text: c.claim,
        category: c.category,
        claimType: c.claim_type,
        verdict: att.verdict,
        consensusScore: c.consensus_score,
        voteEntropy: c.vote_entropy,
        modelsAgreed: c.models_agreed,
        modelsTotal: c.models_total,
        durationS: c.duration_s,
        expectedVerdict: null,
        verdictOk: null,
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
