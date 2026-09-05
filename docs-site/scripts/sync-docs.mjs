#!/usr/bin/env node
/** Generate the portal from repository sources; verify committed copies with --check. */
import { createHash } from 'node:crypto';
import { mkdir, readFile, readdir, unlink, writeFile } from 'node:fs/promises';
import { dirname, join, posix, resolve, relative, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '../..');
const CONTENT = resolve(HERE, '../src/content/docs');
const MANIFEST = resolve(HERE, '../content-manifest.json');
const sha = (value) => createHash('sha256').update(value).digest('hex');
const canonicalText = (value) => value.replace(/\r\n/g, '\n');
const github = 'https://github.com/SimonBouhier/EPP_Verdict/blob/main/';

async function readOptional(path) {
  try { return canonicalText(await readFile(path, 'utf8')); }
  catch (error) { if (error.code === 'ENOENT') return null; throw error; }
}
async function markdownFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name, 'en'))) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(path));
    else if (entry.isFile() && /\.mdx?$/.test(entry.name)) files.push(path);
  }
  return files;
}
function route(dest) {
  const slug = dest.replace(/\.mdx?$/, '').replace(/(^|\/)index$/, '$1').replace(/\/$/, '');
  return slug ? '/' + slug + '/' : '/';
}
function title(raw, fallback) {
  return raw.match(/^#\s+(.+)$/m)?.[1]?.trim() || fallback;
}
function inside(directory, name) {
  const target = resolve(directory, name);
  const rel = relative(directory, target);
  if (!rel || rel.startsWith('..') || isAbsolute(rel)) throw new Error('Unsafe generated path: ' + name);
  return target;
}
export function rewriteLinks(raw, source, routes) {
  const resolveHref = (href) => {
    if (/^(?:[a-z]+:|\/|#)/i.test(href)) return href;
    const [path, hash = ''] = href.split('#', 2);
    const target = posix.normalize(posix.join(posix.dirname(source), path));
    const destination = routes.get(target);
    if (destination) return (hash ? destination.split('#')[0] + '#' + hash : destination);
    // Keep historical links inspectable in their repository context.
    const base = path.endsWith('/') ? github.replace('/blob/', '/tree/') : github;
    return base + target + (hash ? '#' + hash : '');
  };
  return raw
    .replace(/(\[!\[[^\]]*\]\([^)]+\)\])\(([^)\s]+)\)/g,
      (_whole, badge, href) => badge + '(' + resolveHref(href) + ')')
    .replace(/(!?\[[^\]]*\])\(([^)\s]+)(\s+"[^"]*")?\)/g,
      (_whole, label, href, title = '') => label + '(' + resolveHref(href) + title + ')')
    .replace(/(<a\b[^>]*\bhref=)(["'])([^"']+)\2/gi,
      (_whole, prefix, quote, href) => prefix + quote + resolveHref(href) + quote);
}
export async function buildPages(root) {
  const entries = [
    ['docs/PORTAL_INDEX.mdx', 'index.mdx', 'raw'],
    ['docs/CURRENT_STATUS.md', 'current-status.md'],
    ['PITCH.md', 'pitch.md'], ['WHITEPAPER.md', 'whitepaper.md'],
    ['docs/ARCHITECTURE.md', 'architecture.md'],
    ['docs/PUBLISHING.md', 'publishing.md'], ['TECH_DEBT.md', 'tech-debt.md'],
    ['docs/fr/CHANGELOG.md', 'changelog.md'],
  ].map(([src, dest, kind]) => ({ src, dest, kind }));
  for (const [folder, destRoot, kind] of [
    ['docs/adr-en', 'adrs', 'adr'],
    ['docs/positioning', 'positioning', 'history'],
    ['docs/history', 'history', 'history'],
  ]) {
    for (const path of await markdownFiles(join(root, folder))) {
      const src = relative(root, path).split('\\').join('/');
      const suffix = relative(join(root, folder), path).split('\\').join('/');
      const dest = destRoot + '/' + suffix.toLowerCase().replace(/_/g, '-').replace(/(^|\/)readme\.md$/, '$1index.md');
      entries.push({ src, dest, kind });
    }
  }
  const routes = new Map(entries.map(({ src, dest }) => [src, route(dest)]));
  routes.set('README.md', 'https://github.com/SimonBouhier/EPP_Verdict#readme');
  for (const name of await readdir(join(root, 'docs/adr'))) {
    const number = name.match(/^ADR-(\d+)/)?.[1];
    const english = entries.find((entry) => entry.src.startsWith('docs/adr-en/ADR-' + number + '-')
      || entry.src === 'docs/adr-en/ADR-' + number + '.md');
    if (english) routes.set('docs/adr/' + name, route(english.dest));
  }
  const pages = new Map();
  const sources = {};
  for (const entry of entries) {
    const raw = canonicalText(await readFile(join(root, entry.src), 'utf8'));
    sources[entry.src] = sha(raw);
    if (entry.kind === 'raw') {
      pages.set(entry.dest, raw);
      continue;
    }
    const headline = title(raw, entry.dest);
    const frontmatter = '---\ntitle: ' + JSON.stringify(headline) +
      '\neditUrl: false\n---\n\n';
    let notice = '';
    if (entry.kind === 'history') {
      notice = '> **Historical material.** Preserved in its original context. Former blockchain, cluster and sprint claims do not define the current project. Read the [current scope](/current-status/) and [ADR-022](/adrs/adr-022-post-blockchain-refocus/).\n\n';
    } else if (entry.kind === 'adr' && Number(entry.src.match(/ADR-(\d+)/)[1]) < 21) {
      notice = '> **Decision record in its original context.** The local governance and maintained scope are now defined by [ADR-021](/adrs/adr-021-github-governance/) and [ADR-022](/adrs/adr-022-post-blockchain-refocus/). Earlier blockchain provisions are historical; this record is preserved.\n\n';
    }
    // Archived copies retain the original source directory for relative links.
    const sourceContext = entry.src.startsWith('docs/history/2026-09-05/')
      ? (entry.src.endsWith('/ARCHITECTURE.md') ? 'docs/ARCHITECTURE.md' : posix.basename(entry.src))
      : entry.src;
    const body = rewriteLinks(raw.replace(/^#\s+.+\r?\n\r?\n?/, ''), sourceContext, routes);
    pages.set(entry.dest, frontmatter + notice + body);
  }
  const manifest = {
    schemaVersion: 1,
    textNormalization: 'LF',
    sources,
    outputs: Object.fromEntries([...pages].map(([name, content]) => [name, sha(content)])),
  };
  return { pages, manifest };
}
export async function verifySnapshot(contentDir, manifestPath) {
  const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
  if (manifest.schemaVersion !== 1 || manifest.textNormalization !== 'LF' || !manifest.outputs || Object.keys(manifest.outputs).length === 0) {
    throw new Error('Missing or empty content manifest');
  }
  for (const [name, expected] of Object.entries(manifest.outputs)) {
    const content = canonicalText(await readFile(inside(contentDir, name), 'utf8'));
    if (sha(content) !== expected) throw new Error('Generated page hash mismatch: ' + name);
  }
  const actual = (await markdownFiles(contentDir)).map((p) => relative(contentDir, p).split('\\').join('/'));
  if (actual.some((name) => !(name in manifest.outputs))) throw new Error('Unlisted generated page');
}
export async function sync({ root = ROOT, contentDir = CONTENT, manifestPath = MANIFEST, check = false } = {}) {
  if (await readOptional(join(root, 'WHITEPAPER.md')) === null) {
    if (await readOptional(join(root, 'docs/PORTAL_INDEX.mdx')) !== null) {
      throw new Error('Required source missing: WHITEPAPER.md');
    }
    if (check) throw new Error('Source verification requires the repository root');
    await verifySnapshot(contentDir, manifestPath);
    console.log('[sync-docs] Parent sources unavailable; committed snapshot integrity verified.');
    return;
  }
  // Read all sources and render all output before any mutation.
  const { pages, manifest } = await buildPages(root);
  const manifestText = JSON.stringify(manifest, null, 2) + '\n';
  const existing = await readOptional(manifestPath);
  let actual = [];
  try { actual = await markdownFiles(contentDir); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  const stale = actual.filter((p) => !pages.has(relative(contentDir, p).split('\\').join('/')));
  const changed = [];
  for (const [name, content] of pages) {
    if (await readOptional(inside(contentDir, name)) !== content) changed.push(name);
  }
  if (check) {
    if (changed.length || stale.length || existing !== manifestText) {
      throw new Error('Portal differs from sources. Run npm run sync and include generated output. Changed: ' + changed.join(', '));
    }
    console.log('[sync-docs] ' + pages.size + ' pages match their sources.');
    return;
  }
  for (const [name, content] of pages) {
    const path = inside(contentDir, name);
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, content);
  }
  for (const path of stale) await unlink(inside(contentDir, relative(contentDir, path)));
  await writeFile(manifestPath, manifestText);
  console.log('[sync-docs] Generated ' + pages.size + ' pages and integrity manifest.');
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  sync({ check: process.argv.includes('--check') }).catch((error) => {
    console.error('[sync-docs] failed:', error.message);
    process.exitCode = 1;
  });
}
