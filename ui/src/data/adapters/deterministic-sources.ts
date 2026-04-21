import { z } from 'zod';
import {
  type ScenarioRun,
  ScenarioRunSchema,
  type Verdict,
} from '@/domain';

/**
 * Raw shape for `scenario_deterministic_sources` (ADR-012).
 *
 * Deterministic runs bypass ESMM entirely — they don't use LLMs, so there
 * are no `models_agreed`/`vote_entropy` etc. The `status` field carries the
 * outcome semantics: "found" / "verification approved" / "verification
 * approval requested" / etc.
 */
// Skipped claims (e.g. when a source endpoint is unreachable per the run's
// precheck) carry null for most analysis fields. The schema is permissive at
// the boundary; the adapter projects them into our domain as
// INSUFFICIENT_EVIDENCE with the skip reason surfaced in `errors`.
const RawDeterministicClaimSchema = z.object({
  id: z.string(),
  source: z.string(),
  question: z.string(),
  frame: z.string().nullish(),
  skipped: z.boolean(),
  skip_reason: z.string().nullish(),
  source_anchor: z.string().nullish(),
  source_anchor_length: z.number().int().nullish(),
  epistemic_type: z.string().nullish(),
  consensus_method: z.string().nullish(),
  esmm_invoked: z.boolean().nullish(),
  consensus_score: z.number().min(0).max(1).nullish(),
  snapshot_stored: z.boolean(),
  status: z.string().nullish(),
  source_version: z.string().nullish(),
  duration_s: z.number().nonnegative(),
  errors: z.string(),
});

const RawDeterministicRunSchema = z.object({
  scenario: z.literal('scenario_deterministic_sources'),
  timestamp: z.string(),
  adr: z.string().optional(),
  claims: z.array(RawDeterministicClaimSchema),
});

/**
 * Maps the free-text `status` field to our four-verdict domain.
 * Preserves the original string in `raw` for features that want to surface it.
 */
function statusToVerdict(status: string, skipped: boolean): Verdict {
  if (skipped) return 'INSUFFICIENT_EVIDENCE';
  const s = status.toLowerCase();
  if (s.includes('not found') || s.includes('not_found') || s.includes('refused')) {
    return 'REFUTED';
  }
  if (s.includes('requested') || s.includes('pending')) {
    return 'CONTESTED';
  }
  if (s.includes('found') || s.includes('approved')) {
    return 'SUPPORTED';
  }
  return 'INSUFFICIENT_EVIDENCE';
}

export function deterministicSourcesAdapter(raw: unknown): ScenarioRun {
  const parsed = RawDeterministicRunSchema.parse(raw);
  return ScenarioRunSchema.parse({
    scenario: parsed.scenario,
    timestamp: parsed.timestamp,
    // No LLMs involved — models array stays empty to signal that clearly.
    models: [],
    adr: parsed.adr,
    claims: parsed.claims.map((c) => ({
      id: c.id,
      text: c.question,
      category: c.source,
      claimType: 'deterministic' as const,
      verdict: statusToVerdict(c.status ?? '', c.skipped),
      consensusScore: c.consensus_score ?? 0,
      voteEntropy: null,
      modelsAgreed: null,
      modelsTotal: null,
      durationS: c.duration_s,
      expectedVerdict: null,
      verdictOk: null,
      errors: c.skipped && c.skip_reason ? `skipped: ${c.skip_reason}` : c.errors,
    })),
    raw,
  });
}
