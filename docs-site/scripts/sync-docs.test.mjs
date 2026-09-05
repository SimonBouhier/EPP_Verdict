import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { sync, verifySnapshot, rewriteLinks } from './sync-docs.mjs';

async function fixture(t) {
  const root = await mkdtemp(join(tmpdir(), 'epp-doc-sync-'));
  if (!resolve(root).startsWith(resolve(tmpdir()) + sep + 'epp-doc-sync-')) {
    throw new Error('Unexpected test workspace');
  }
  t.after(() => rm(root, { recursive: true, force: true }));
  const docs = {
    'docs/PORTAL_INDEX.mdx': '---\ntitle: EPP\n---\nCurrent project.\n',
    'docs/CURRENT_STATUS.md': '# Status\n\n[Decision](adr/ADR-022-recentrage-post-blockchain.md)\n',
    'PITCH.md': '# Overview\n\nCurrent personal scope.\n',
    'WHITEPAPER.md': '# Whitepaper\n\nCurrent design.\n',
    'docs/ARCHITECTURE.md': '# Architecture\n\nLocal code.\n',
    'docs/PUBLISHING.md': '# Publishing\n\nSource maintenance.\n',
    'TECH_DEBT.md': '# Debt\n\nDated records.\n',
    'docs/fr/CHANGELOG.md': '# Changes\n\nHistory.\n',
    'docs/adr/ADR-022-recentrage-post-blockchain.md': '# French decision\n',
    'docs/adr-en/ADR-022-post-blockchain-refocus.md': '# Current decision\n',
    'docs/positioning/README.md': '# Positioning\n\nFormer scope.\n',
    'docs/history/README.md': '# Historical texts\n\nOriginal material.\n',
  };
  for (const [name, content] of Object.entries(docs)) {
    const path = join(root, name);
    await mkdir(join(path, '..'), { recursive: true });
    await writeFile(path, content);
  }
  const options = { root, contentDir: join(root, 'output'), manifestPath: join(root, 'manifest.json') };
  return options;
}
test('source drift fails a read-only check and resync resolves it', async (t) => {
  const options = await fixture(t);
  await sync(options);
  await sync({ ...options, check: true });
  const originalOutput = await readFile(join(options.contentDir, 'pitch.md'), 'utf8');
  await writeFile(join(options.root, 'PITCH.md'), '# Overview\n\nChanged scope.\n');
  await assert.rejects(sync({ ...options, check: true }), /differs from sources/);
  assert.equal(await readFile(join(options.contentDir, 'pitch.md'), 'utf8'), originalOutput);
  await sync(options);
  assert.match(await readFile(join(options.contentDir, 'pitch.md'), 'utf8'), /Changed scope/);
  await sync({ ...options, check: true });
});
test('isolated builds detect tampered content instead of silently trusting it', async (t) => {
  const options = await fixture(t);
  await sync(options);
  await verifySnapshot(options.contentDir, options.manifestPath);
  await writeFile(join(options.contentDir, 'pitch.md'), 'Reintroduced stale claims');
  await assert.rejects(verifySnapshot(options.contentDir, options.manifestPath), /hash mismatch/);
});
test('a missing required source does not destroy existing pages', async (t) => {
  const options = await fixture(t);
  await sync(options);
  const prior = await readFile(join(options.contentDir, 'pitch.md'), 'utf8');
  await rm(join(options.root, 'PITCH.md'));
  await assert.rejects(sync(options), /ENOENT/);
  assert.equal(await readFile(join(options.contentDir, 'pitch.md'), 'utf8'), prior);
  await rm(join(options.root, 'WHITEPAPER.md'));
  await assert.rejects(sync(options), /Required source missing/);
  assert.equal(await readFile(join(options.contentDir, 'pitch.md'), 'utf8'), prior);
});
test('French source ADR links resolve to published English routes; archives have context', async (t) => {
  const options = await fixture(t);
  await sync(options);
  assert.match(await readFile(join(options.contentDir, 'current-status.md'), 'utf8'),
    /\[Decision\]\(\/adrs\/adr-022-post-blockchain-refocus\/\)/);
  assert.match(await readFile(join(options.contentDir, 'positioning/index.md'), 'utf8'),
    /Historical material/);
});
test('Windows and Unix text checkouts produce the same source and page hashes', async (t) => {
  const options = await fixture(t);
  await sync(options);
  const source = join(options.root, 'WHITEPAPER.md');
  await writeFile(source, (await readFile(source, 'utf8')).replace(/\n/g, '\r\n'));
  const page = join(options.contentDir, 'whitepaper.md');
  await writeFile(page, (await readFile(page, 'utf8')).replace(/\n/g, '\r\n'));
  await sync({ ...options, check: true });
  await verifySnapshot(options.contentDir, options.manifestPath);
});
test('historical HTML badges link to repository directories and mapped fragments remain valid', () => {
  const raw = '<a href="tests/">Tests</a> [Readme](README.md#scope "Scope") [![Tests](https://example.com/badge)](tests/)';
  const result = rewriteLinks(raw, 'README.md', new Map([
    ['README.md', 'https://github.com/SimonBouhier/EPP_Verdict#readme'],
  ]));
  assert.match(result, /href="https:\/\/github.com\/SimonBouhier\/EPP_Verdict\/tree\/main\/tests\/"/);
  assert.match(result, /\[Readme\]\(https:\/\/github.com\/SimonBouhier\/EPP_Verdict#scope "Scope"\)/);
  assert.ok(result.endsWith('[![Tests](https://example.com/badge)](https://github.com/SimonBouhier/EPP_Verdict/tree/main/tests/)'));
});
