import { describe, expect, it } from 'vitest';
import type { OnChainManifest } from '@/domain';
import { graphSeederBlockchainAdapter } from './graph-seeder-blockchain';

/**
 * RED test for TD-002: `graph_seeder_blockchain` adapter.
 *
 * The seeder JSON publishes claims with `verdict: null` and
 * `claim_type: "foundational"`. The pipeline materialises a verdict
 * later, when claims are pushed on-chain. This adapter joins the
 * two — it surfaces only the claims that have an on-chain attestation,
 * picking up the verdict from there.
 */

const seederRaw = {
  scenario: 'graph_seeder_blockchain',
  timestamp: '2026-03-02T14:42:39+00:00',
  models: ['phi4-reasoning:latest', 'mistral:latest'],
  model_count: 2,
  total_claims: 2,
  cache_hits: 0,
  deliberated: 2,
  errors: 0,
  total_duration_s: 100,
  claims: [
    {
      id: 'A',
      category: 'solana_architecture',
      claim: 'Solana uses a Proof of History mechanism',
      frame: 'blockchain_tps_v1.0',
      note: 'foundational claim',
      verdict: null,
      consensus_score: 0.98,
      claim_type: 'foundational',
      vote_entropy: 0,
      models_agreed: 5,
      models_total: 5,
      triplets_extracted: 1,
      from_cache: true,
      duration_s: 0,
      errors: '',
    },
    {
      id: 'B',
      category: 'cryptography',
      claim: 'No on-chain attestation for this one',
      frame: 'blockchain_tps_v1.0',
      note: 'should be dropped — never pushed',
      verdict: null,
      consensus_score: 0.5,
      claim_type: 'foundational',
      vote_entropy: 0,
      models_agreed: 3,
      models_total: 5,
      triplets_extracted: 1,
      from_cache: false,
      duration_s: 0,
      errors: '',
    },
  ],
};

const onchain: OnChainManifest = {
  generatedAt: '2026-03-02T15:00:00+00:00',
  programId: '9QtybfyZQFhra1D6S3NtD6jD4z2Z3wcYmf4YXETq8bSD',
  cluster: 'devnet',
  rpcUrl: 'https://api.devnet.solana.com',
  submitter: 'test-submitter',
  scriptVersion: '1.0',
  summary: { pushed: 1, failed: 0, total_entries: 1 },
  attestations: [
    {
      claim_hash: 'a'.repeat(64),
      subject: 'Solana',
      predicate: 'verdict',
      object: 'SUPPORTED',
      question: 'Solana uses a Proof of History mechanism',
      verdict: 'SUPPORTED',
      consensus_score: 0.98,
      confidence_tier: 'proposition',
      epistemic_type: 'foundational',
      metrological_frame: 'blockchain_tps_v1.0',
      frame_hash: 'b'.repeat(64),
      tx_signature: 'sig123',
      pda: 'pda123',
      slot: 1,
      explorer_url: 'https://explorer.solana.com/tx/sig123?cluster=devnet',
      pushed_at: '2026-03-02T15:00:00+00:00',
      status: 'ok',
    },
  ],
};

describe('graphSeederBlockchainAdapter', () => {
  it('joins seeder claims with on-chain attestations by question text', () => {
    const result = graphSeederBlockchainAdapter(seederRaw, onchain);

    expect(result.scenario).toBe('graph_seeder_blockchain');
    expect(result.timestamp).toBe('2026-03-02T14:42:39+00:00');
    expect(result.models).toEqual(['phi4-reasoning:latest', 'mistral:latest']);
    expect(result.claims).toHaveLength(1);

    const claim = result.claims[0];
    expect(claim.id).toBe('A');
    expect(claim.text).toBe('Solana uses a Proof of History mechanism');
    expect(claim.category).toBe('solana_architecture');
    expect(claim.claimType).toBe('foundational');
    expect(claim.verdict).toBe('SUPPORTED');
    expect(claim.consensusScore).toBe(0.98);
    expect(claim.modelsAgreed).toBe(5);
    expect(claim.modelsTotal).toBe(5);
  });

  it('drops seeder claims that have no matching on-chain attestation', () => {
    const result = graphSeederBlockchainAdapter(seederRaw, onchain);
    const ids = result.claims.map((c) => c.id);
    expect(ids).not.toContain('B');
  });

  it('returns zero claims when no on-chain manifest is provided', () => {
    const result = graphSeederBlockchainAdapter(seederRaw);
    expect(result.claims).toHaveLength(0);
  });

  it('preserves the raw payload for downstream features', () => {
    const result = graphSeederBlockchainAdapter(seederRaw, onchain);
    expect(result.raw).toEqual(seederRaw);
  });
});
