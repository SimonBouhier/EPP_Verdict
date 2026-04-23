import { z } from 'zod';
import { VerdictSchema } from './claim';

/**
 * One on-chain attestation entry from data/devnet_pushed.json.
 * Schema mirrors scripts/push_to_devnet.py's outcome_to_entry() output.
 */
export const OnChainAttestationSchema = z.object({
  claim_hash: z.string(),
  subject: z.string(),
  predicate: z.string(),
  object: z.string(),
  question: z.string().nullable(),
  verdict: VerdictSchema.nullable(),
  consensus_score: z.number(),
  confidence_tier: z.string(),
  epistemic_type: z.string(),
  metrological_frame: z.string(),
  frame_hash: z.string(),
  tx_signature: z.string().nullable(),
  pda: z.string().nullable(),
  slot: z.number().int().nullable(),
  explorer_url: z.string().url().nullable(),
  pushed_at: z.string(),
  status: z.enum(['ok', 'error']),
  error: z.string().optional(),
});
export type OnChainAttestation = z.infer<typeof OnChainAttestationSchema>;

export const OnChainManifestSchema = z.object({
  generatedAt: z.string(),
  programId: z.string(),
  cluster: z.string(),
  rpcUrl: z.string(),
  submitter: z.string(),
  scriptVersion: z.string(),
  summary: z.object({
    pushed: z.number().int(),
    failed: z.number().int(),
    total_entries: z.number().int(),
  }),
  attestations: z.array(OnChainAttestationSchema),
});
export type OnChainManifest = z.infer<typeof OnChainManifestSchema>;

/**
 * Empty manifest used as a safe fallback when devnet_pushed.json doesn't
 * exist yet (e.g. before the first push). Lets the UI render gracefully.
 */
export const EMPTY_ONCHAIN_MANIFEST: OnChainManifest = {
  generatedAt: '',
  programId: '',
  cluster: 'devnet',
  rpcUrl: '',
  submitter: '',
  scriptVersion: '0',
  summary: { pushed: 0, failed: 0, total_entries: 0 },
  attestations: [],
};
