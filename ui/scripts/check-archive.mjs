#!/usr/bin/env node
/** Verify the fixed archive without copying, regenerating or publishing data. */
import { createHash } from 'node:crypto';
import { readFile, readdir } from 'node:fs/promises';
import { dirname, resolve, relative, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';
const ui = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const directory = resolve(ui, 'public/data');
const manifest = JSON.parse(await readFile(resolve(ui, 'archive-manifest.json'), 'utf8'));
if (manifest.schemaVersion !== 1 || manifest.textNormalization !== 'LF' || Object.keys(manifest.files || {}).length === 0) {
  throw new Error('Missing historical archive manifest');
}
for (const [name, hash] of Object.entries(manifest.files)) {
  const path = resolve(directory, name);
  const rel = relative(directory, path);
  if (!rel || rel.startsWith('..') || isAbsolute(rel)) throw new Error('Unsafe archive path');
  const text = (await readFile(path, 'utf8')).replace(/\r\n/g, '\n');
  if (createHash('sha256').update(text).digest('hex') !== hash) {
    throw new Error('Historical archive changed: ' + name);
  }
}
const actual = (await readdir(directory)).filter((name) => name.endsWith('.json'));
if (actual.some((name) => !(name in manifest.files))) throw new Error('Unlisted archive data');
console.log('[archive] ' + actual.length + ' historical JSON files verified; no data refreshed.');
