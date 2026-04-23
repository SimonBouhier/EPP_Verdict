#!/usr/bin/env node
/**
 * Copies project data into ui/public/data/ for the dashboard:
 *   - demos/benchmark_runs/*.json  → individual run files + manifest.json
 *   - data/devnet_pushed.json      → on-chain attestation manifest (Phase C.2)
 *
 * Runs as predev / prebuild npm hook. Both inputs are optional — missing
 * files emit a warning but don't fail the build.
 */
import { copyFile, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..', '..');
const RUNS_SRC = resolve(REPO_ROOT, 'demos', 'benchmark_runs');
const ONCHAIN_SRC = resolve(REPO_ROOT, 'data', 'devnet_pushed.json');
const DEST = resolve(__dirname, '..', 'public', 'data');

async function copyBenchmarkRuns() {
  const entries = await readdir(RUNS_SRC, { withFileTypes: true });
  const jsonFiles = entries.filter((e) => e.isFile() && e.name.endsWith('.json'));

  const runs = [];
  for (const entry of jsonFiles) {
    const filename = entry.name;
    const srcPath = join(RUNS_SRC, filename);
    const destPath = join(DEST, filename);
    await copyFile(srcPath, destPath);

    try {
      const raw = JSON.parse(await readFile(srcPath, 'utf8'));
      runs.push({
        filename,
        scenario: typeof raw?.scenario === 'string' ? raw.scenario : 'unknown',
        timestamp: typeof raw?.timestamp === 'string' ? raw.timestamp : '',
        claimsCount: Array.isArray(raw?.claims) ? raw.claims.length : 0,
        ...(typeof raw?.adr === 'string' ? { adr: raw.adr } : {}),
      });
    } catch (err) {
      console.warn(`[copy-data] could not parse ${filename}: ${err.message}`);
    }
  }

  // Most recent first.
  runs.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));

  const manifest = {
    generatedAt: new Date().toISOString(),
    sourceDir: 'demos/benchmark_runs',
    runs,
  };
  await writeFile(join(DEST, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);

  console.log(
    `[copy-data] copied ${jsonFiles.length} run files, manifest lists ${runs.length} runs`,
  );
}

async function copyOnChainManifest() {
  try {
    await copyFile(ONCHAIN_SRC, join(DEST, 'devnet_pushed.json'));
    const raw = JSON.parse(await readFile(ONCHAIN_SRC, 'utf8'));
    const total = Array.isArray(raw?.attestations) ? raw.attestations.length : 0;
    const okCount = Array.isArray(raw?.attestations)
      ? raw.attestations.filter((a) => a?.status === 'ok').length
      : 0;
    console.log(
      `[copy-data] copied devnet_pushed.json (${okCount}/${total} on-chain)`,
    );
  } catch (err) {
    if (err.code === 'ENOENT') {
      console.warn(
        '[copy-data] data/devnet_pushed.json not found — run scripts/push_to_devnet.py first to populate it. Dashboard will show empty on-chain section.',
      );
    } else {
      console.warn(`[copy-data] could not copy devnet_pushed.json: ${err.message}`);
    }
  }
}

async function main() {
  await rm(DEST, { recursive: true, force: true });
  await mkdir(DEST, { recursive: true });
  await copyBenchmarkRuns();
  await copyOnChainManifest();
}

main().catch((err) => {
  console.error('[copy-data] failed:', err);
  process.exit(1);
});
