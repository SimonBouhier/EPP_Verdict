import {
  EMPTY_ONCHAIN_MANIFEST,
  type OnChainManifest,
  OnChainManifestSchema,
  type RunManifest,
  RunManifestSchema,
  type ScenarioRun,
} from '@/domain';
import { detectAdapter } from './adapters';

/**
 * Single I/O boundary for the UI. All data-fetching code goes through here.
 * Today: fetches static JSON from /data/. Tomorrow: could hit Solana RPC,
 * an HTTP API, or IndexedDB — feature code never has to know.
 */
async function fetchJson(path: string): Promise<unknown> {
  const res = await fetch(path, { headers: { Accept: 'application/json' } });
  if (!res.ok) {
    throw new Error(`Failed to load ${path}: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function loadManifest(): Promise<RunManifest> {
  const raw = await fetchJson('/data/manifest.json');
  return RunManifestSchema.parse(raw);
}

export async function loadRun(filename: string): Promise<ScenarioRun> {
  // Guard against path traversal — only allow flat filenames.
  if (filename.includes('/') || filename.includes('\\') || filename.includes('..')) {
    throw new Error(`Invalid run filename: ${filename}`);
  }
  const raw = await fetchJson(`/data/${encodeURIComponent(filename)}`);
  const adapter = detectAdapter(raw);
  return adapter(raw);
}

/**
 * Loads the on-chain attestation manifest produced by
 * scripts/push_to_devnet.py. Returns an empty manifest if the file
 * doesn't exist yet (graceful UI degradation before the first push).
 */
export async function loadOnChainManifest(): Promise<OnChainManifest> {
  try {
    const raw = await fetchJson('/data/devnet_pushed.json');
    return OnChainManifestSchema.parse(raw);
  } catch (err) {
    // Distinguish "not yet pushed" (404) from real errors.
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes(' 404 ')) {
      return EMPTY_ONCHAIN_MANIFEST;
    }
    throw err;
  }
}
