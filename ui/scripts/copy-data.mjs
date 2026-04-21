#!/usr/bin/env node
/**
 * Copies demos/benchmark_runs/*.json to ui/public/data/ and emits a manifest.
 * The manifest gives the UI an index of available runs without browser-side directory listing.
 * Runs as predev / prebuild npm hook.
 */
import { copyFile, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(__dirname, '..', '..', 'demos', 'benchmark_runs');
const DEST = resolve(__dirname, '..', 'public', 'data');

async function main() {
  await rm(DEST, { recursive: true, force: true });
  await mkdir(DEST, { recursive: true });

  const entries = await readdir(SRC, { withFileTypes: true });
  const jsonFiles = entries.filter((e) => e.isFile() && e.name.endsWith('.json'));

  const runs = [];
  for (const entry of jsonFiles) {
    const filename = entry.name;
    const srcPath = join(SRC, filename);
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
    `[copy-data] copied ${jsonFiles.length} files, manifest lists ${runs.length} runs`,
  );
}

main().catch((err) => {
  console.error('[copy-data] failed:', err);
  process.exit(1);
});
