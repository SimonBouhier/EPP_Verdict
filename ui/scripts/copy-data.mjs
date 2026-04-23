#!/usr/bin/env node
/**
 * Refreshes ui/public/data/ from the project's local sources:
 *   - demos/benchmark_runs/*.json  → individual run files + manifest.json
 *   - data/devnet_pushed.json      → on-chain attestation manifest (Phase C.2)
 *
 * Runs as predev / prebuild npm hook.
 *
 * On Vercel (or any environment where the source dirs are not accessible —
 * e.g. monorepo deployments where Root Directory = "ui/" cuts off the rest
 * of the repo), the script is a no-op: the committed contents of
 * ui/public/data/ are used as-is. This is why public/data/ is tracked in git.
 *
 * Local workflow when adding a new scenario:
 *   1. Run the Python pipeline → writes new JSON to demos/benchmark_runs/
 *   2. Run `npm run dev` (or `npm run prebuild`) → refreshes ui/public/data/
 *   3. `git add ui/public/data/` → commit → push → Vercel re-deploys
 */
import { copyFile, mkdir, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..', '..');
const RUNS_SRC = resolve(REPO_ROOT, 'demos', 'benchmark_runs');
const ONCHAIN_SRC = resolve(REPO_ROOT, 'data', 'devnet_pushed.json');
const DEST = resolve(__dirname, '..', 'public', 'data');

async function pathExists(p) {
  try {
    await stat(p);
    return true;
  } catch (err) {
    if (err.code === 'ENOENT') return false;
    throw err;
  }
}

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
  if (!(await pathExists(ONCHAIN_SRC))) {
    console.warn(
      '[copy-data] data/devnet_pushed.json not found — keeping any existing copy in public/data/. ' +
        'Run scripts/push_to_devnet.py to populate it.',
    );
    return;
  }
  await copyFile(ONCHAIN_SRC, join(DEST, 'devnet_pushed.json'));
  const raw = JSON.parse(await readFile(ONCHAIN_SRC, 'utf8'));
  const total = Array.isArray(raw?.attestations) ? raw.attestations.length : 0;
  const okCount = Array.isArray(raw?.attestations)
    ? raw.attestations.filter((a) => a?.status === 'ok').length
    : 0;
  console.log(`[copy-data] copied devnet_pushed.json (${okCount}/${total} on-chain)`);
}

async function main() {
  // If the project sources aren't accessible (typical Vercel monorepo case),
  // skip the entire copy and rely on the committed contents of public/data/.
  // The check on RUNS_SRC is sufficient — if the repo root is missing, both
  // sources are missing.
  const sourcesAccessible = await pathExists(RUNS_SRC);
  if (!sourcesAccessible) {
    console.log(
      `[copy-data] ${RUNS_SRC} not accessible — skipping refresh, using committed public/data/.`,
    );
    return;
  }

  await mkdir(DEST, { recursive: true });
  // Wipe DEST only when we're about to refresh from source — never on the
  // "no source" path above, otherwise we'd nuke the committed files Vercel
  // depends on.
  await rm(DEST, { recursive: true, force: true });
  await mkdir(DEST, { recursive: true });

  await copyBenchmarkRuns();
  await copyOnChainManifest();
}

main().catch((err) => {
  console.error('[copy-data] failed:', err);
  process.exit(1);
});
