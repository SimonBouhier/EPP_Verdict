import { z } from 'zod';
import { type Verdict, VerdictSchema } from '@/domain';

/**
 * Extracts flywheel-specific details (baseline comparison, anchors, sources)
 * from the raw JSON of a `scenario_flywheel_v2` run.
 *
 * Lives here rather than in the adapter because only the flywheel-split
 * feature needs these fields. Keeping the common ClaimVerdict lean is what
 * lets new scenarios slot in without bloating every view.
 */
const RawFlywheelClaimRefSchema = z.object({
  id: z.string(),
  claim: z.string(),
  category: z.string(),
  verify_verdict: VerdictSchema,
  verify_score: z.number(),
  baseline_verify_score: z.number().nullish(),
  baseline_verify_verdict: VerdictSchema.nullish(),
  delta: z.number().nullish(),
  flywheel_anchors_found: z.number().int().nullish(),
  flywheel_sources_injected: z.array(z.string()).nullish(),
  origin: z.string().nullish(),
  expected_verdict: VerdictSchema.nullish(),
  verdict_ok: z.boolean().nullish(),
});

const RawFlywheelRunRefSchema = z.object({
  claims: z.array(RawFlywheelClaimRefSchema),
});

export type FlywheelOrigin = 'migrated' | 'new';

export interface FlywheelClaimDetail {
  id: string;
  text: string;
  category: string;
  origin: FlywheelOrigin;
  flywheelVerdict: Verdict;
  flywheelScore: number;
  baselineVerdict: Verdict | null;
  baselineScore: number | null;
  delta: number | null;
  anchorsFound: number | null;
  sourcesInjected: string[];
  expectedVerdict: Verdict | null;
  verdictOk: boolean | null;
}

export interface FlywheelSplitSummary {
  claimsTotal: number;
  claimsMigrated: number;
  claimsNew: number;
  claimsImproved: number;
  averageDelta: number | null;
}

export function parseFlywheelClaims(raw: unknown): FlywheelClaimDetail[] {
  const parsed = RawFlywheelRunRefSchema.parse(raw);
  return parsed.claims.map((c) => {
    const hasBaseline =
      c.baseline_verify_score !== null && c.baseline_verify_score !== undefined;
    return {
      id: c.id,
      text: c.claim,
      category: c.category,
      origin: hasBaseline ? 'migrated' : 'new',
      flywheelVerdict: c.verify_verdict,
      flywheelScore: c.verify_score,
      baselineVerdict: c.baseline_verify_verdict ?? null,
      baselineScore: c.baseline_verify_score ?? null,
      delta: c.delta ?? null,
      anchorsFound: c.flywheel_anchors_found ?? null,
      sourcesInjected: c.flywheel_sources_injected ?? [],
      expectedVerdict: c.expected_verdict ?? null,
      verdictOk: c.verdict_ok ?? null,
    };
  });
}

export function summarizeFlywheelSplit(
  claims: readonly FlywheelClaimDetail[],
): FlywheelSplitSummary {
  const migrated = claims.filter((c) => c.origin === 'migrated');
  const improved = migrated.filter((c) => (c.delta ?? 0) > 0);
  const deltas = migrated.map((c) => c.delta).filter((d): d is number => d !== null);
  const averageDelta =
    deltas.length === 0
      ? null
      : deltas.reduce((sum, d) => sum + d, 0) / deltas.length;

  return {
    claimsTotal: claims.length,
    claimsMigrated: migrated.length,
    claimsNew: claims.length - migrated.length,
    claimsImproved: improved.length,
    averageDelta,
  };
}
