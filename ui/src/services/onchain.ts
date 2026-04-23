import type { OnChainAttestation, OnChainManifest } from '@/domain';

/**
 * Index on-chain attestations by their original `question` text so each
 * dashboard claim row can do an O(1) lookup. We only index successful
 * pushes — failed entries shouldn't badge UI rows as "on-chain".
 *
 * If the same question was pushed twice (shouldn't happen given the
 * script's idempotency guard, but defensive), the most recent push wins.
 */
export function buildOnChainIndex(
  manifest: OnChainManifest,
): Map<string, OnChainAttestation> {
  const index = new Map<string, OnChainAttestation>();
  for (const att of manifest.attestations) {
    if (att.status !== 'ok' || !att.question || !att.tx_signature) continue;
    const existing = index.get(att.question);
    if (!existing || att.pushed_at > existing.pushed_at) {
      index.set(att.question, att);
    }
  }
  return index;
}

/** Lookup helper. Returns null if the claim text isn't on-chain. */
export function lookupOnChain(
  index: Map<string, OnChainAttestation> | undefined,
  claimText: string,
): OnChainAttestation | null {
  if (!index) return null;
  return index.get(claimText) ?? null;
}
