#!/usr/bin/env node
/**
 * Syncs source-of-truth Markdown into docs-site/src/content/docs/.
 *
 * Sources (relative to repo root):
 *   PITCH.md                 → src/content/docs/pitch.md
 *   WHITEPAPER.md            → src/content/docs/whitepaper.md
 *   docs/ARCHITECTURE.md     → src/content/docs/architecture.md
 *   docs/fr/CHANGELOG.md     → src/content/docs/changelog.md
 *   docs/positioning/*.md    → src/content/docs/positioning/
 *   docs/adr/ADR-*.md        → src/content/docs/adrs/
 *
 * For each copied file the script prepends a Starlight frontmatter block
 * derived from the first H1 (title) so Starlight indexes it correctly.
 *
 * On Vercel (Root Directory = docs-site/ — siblings of docs-site/ are
 * not in the build sandbox) the sources may be absent. In that case the
 * script no-ops and relies on the committed contents of src/content/docs/.
 * Same pattern as ui/scripts/copy-data.mjs.
 *
 * Runs as predev / prebuild npm hook.
 */
import { copyFile, mkdir, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..', '..');
const DOCS_DIR = resolve(__dirname, '..', 'src', 'content', 'docs');

async function pathExists(p) {
  try {
    await stat(p);
    return true;
  } catch (err) {
    if (err.code === 'ENOENT') return false;
    throw err;
  }
}

function deriveTitle(raw, fallback) {
  const h1 = raw.match(/^#\s+(.+?)\s*$/m);
  if (!h1) return fallback;
  // Strip trailing markdown emphasis / em-dashes.
  return h1[1].replace(/^[\s—–-]+|[\s—–-]+$/g, '').trim();
}

function deriveDescription(raw) {
  // First non-heading, non-blockquote paragraph, truncated to 200 chars.
  const lines = raw.split(/\r?\n/);
  for (const line of lines) {
    const t = line.trim();
    if (!t) continue;
    if (t.startsWith('#')) continue;
    if (t.startsWith('>')) continue;
    if (t.startsWith('---')) continue;
    if (t.startsWith('[!')) continue;
    if (t.startsWith('|')) continue;
    // Clean markdown emphasis for description.
    const cleaned = t
      .replace(/\*\*/g, '')
      .replace(/\*/g, '')
      .replace(/`/g, '')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
    if (cleaned.length > 20) {
      return cleaned.length > 200 ? `${cleaned.slice(0, 197)}…` : cleaned;
    }
  }
  return undefined;
}

function makeFrontmatter({ title, description, editUrl }) {
  const lines = ['---'];
  lines.push(`title: ${JSON.stringify(title)}`);
  if (description) lines.push(`description: ${JSON.stringify(description)}`);
  if (editUrl === false) lines.push('editUrl: false');
  lines.push('---', '');
  return lines.join('\n');
}

/**
 * Strip an existing top H1 so Starlight's page title (from frontmatter)
 * doesn't duplicate with a body H1 of the same text.
 */
function stripLeadingH1(body) {
  return body.replace(/^#\s+.+?\r?\n\r?\n?/, '');
}

/**
 * Rewrites internal markdown links from their source-tree paths to their
 * Starlight URLs. Examples:
 *   [Whitepaper](WHITEPAPER.md)                    → [Whitepaper](/whitepaper/)
 *   [§scope](WHITEPAPER.md#liability--scope)       → [§scope](/whitepaper/#liability--scope)
 *   [essay](docs/positioning/the_negative_space.md)→ [essay](/positioning/the-negative-space/)
 *   [ADR-020](docs/adr/ADR-020.md)                 → [ADR-020](/adrs/adr-020/)
 *   [ARCH](docs/ARCHITECTURE.md)                   → [ARCH](/architecture/)
 *   [positioning](docs/positioning/)               → [positioning](/positioning/)
 *   [README](README.md)                            → [README] on GitHub (no docs portal page)
 *
 * External links (http/https) and in-page anchors (starting with #) pass
 * through untouched.
 */
function rewriteLinks(body) {
  return (
    body
      // README.md → point back to GitHub (no README in the docs portal).
      .replace(
        /\]\(\.?\/?README\.md(#[^)]*)?\)/g,
        '](https://github.com/SimonBouhier/EPP_Verdict#readme)',
      )
      // Root-level docs.
      .replace(/\]\(\.?\/?WHITEPAPER\.md(#[^)]*)?\)/g, '](/whitepaper/$1)')
      .replace(/\]\(\.?\/?PITCH\.md(#[^)]*)?\)/g, '](/pitch/$1)')
      // docs/ subtree.
      .replace(/\]\(\.?\/?docs\/ARCHITECTURE\.md(#[^)]*)?\)/g, '](/architecture/$1)')
      .replace(/\]\(\.?\/?docs\/fr\/CHANGELOG\.md(#[^)]*)?\)/g, '](/changelog/$1)')
      // positioning files (underscores → hyphens).
      .replace(
        /\]\(\.?\/?docs\/positioning\/([a-zA-Z0-9_-]+)\.md(#[^)]*)?\)/g,
        (_m, slug, hash) =>
          `](/positioning/${slug.toLowerCase().replace(/_/g, '-')}/${hash || ''})`,
      )
      // positioning README.md → section landing.
      .replace(
        /\]\(\.?\/?docs\/positioning\/(README\.md)?(#[^)]*)?\)/g,
        '](/positioning/$2)',
      )
      // ADRs (lowercase slug, preserve any English suffix like "-deferred" / "-future").
      // Both French (docs/adr/) and English (docs/adr-en/) source paths are
      // remapped to the same /adrs/<slug>/ portal route.
      .replace(
        /\]\(\.?\/?docs\/adr(?:-en)?\/(ADR-[\wàâéèêëîïôûùüÿñæœ-]+)\.md(#[^)]*)?\)/gi,
        (_m, adr, hash) => `](/adrs/${adr.toLowerCase()}/${hash || ''})`,
      )
  );
}

async function copyOne(srcPath, destPath, fallbackTitle, { editUrl = true } = {}) {
  const raw = await readFile(srcPath, 'utf8');
  const title = deriveTitle(raw, fallbackTitle);
  const description = deriveDescription(raw);
  const body = rewriteLinks(stripLeadingH1(raw));
  const content = makeFrontmatter({ title, description, editUrl: editUrl ? undefined : false }) + body;
  await mkdir(dirname(destPath), { recursive: true });
  await writeFile(destPath, content);
  return { title, destPath };
}

async function copyDir(srcDir, destDir, { flattenNames = null } = {}) {
  if (!(await pathExists(srcDir))) return [];
  await mkdir(destDir, { recursive: true });
  const entries = await readdir(srcDir, { withFileTypes: true });
  const results = [];
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    if (!entry.name.endsWith('.md')) continue;
    if (entry.name.toLowerCase() === 'readme.md') continue; // handled separately
    const destName = flattenNames ? flattenNames(entry.name) : entry.name.toLowerCase();
    const out = await copyOne(
      join(srcDir, entry.name),
      join(destDir, destName),
      entry.name.replace(/\.md$/i, ''),
    );
    results.push(out);
  }
  return results;
}

async function main() {
  // Gatekeeper: if the root is not accessible (Vercel monorepo isolation),
  // preserve whatever is already committed in src/content/docs/.
  if (!(await pathExists(join(REPO_ROOT, 'WHITEPAPER.md')))) {
    console.log(
      '[sync-docs] Source .md files not accessible at REPO_ROOT — skipping sync, using committed src/content/docs/.',
    );
    return;
  }

  // Clean dest (we know sources are accessible, full refresh is safe).
  await rm(DOCS_DIR, { recursive: true, force: true });
  await mkdir(DOCS_DIR, { recursive: true });

  // index.mdx is hand-written and not synced — write it once below.
  await writeIndexMdx();

  // Core project docs.
  const copied = [];
  copied.push(
    await copyOne(
      join(REPO_ROOT, 'PITCH.md'),
      join(DOCS_DIR, 'pitch.md'),
      'Pitch',
    ),
  );
  copied.push(
    await copyOne(
      join(REPO_ROOT, 'WHITEPAPER.md'),
      join(DOCS_DIR, 'whitepaper.md'),
      'Whitepaper',
    ),
  );
  copied.push(
    await copyOne(
      join(REPO_ROOT, 'docs', 'ARCHITECTURE.md'),
      join(DOCS_DIR, 'architecture.md'),
      'Architecture',
    ),
  );
  copied.push(
    await copyOne(
      join(REPO_ROOT, 'docs', 'fr', 'CHANGELOG.md'),
      join(DOCS_DIR, 'changelog.md'),
      'Changelog',
    ),
  );

  // Positioning section — includes its own README as the section landing.
  const positioningSrc = join(REPO_ROOT, 'docs', 'positioning');
  const positioningDest = join(DOCS_DIR, 'positioning');
  if (await pathExists(positioningSrc)) {
    await mkdir(positioningDest, { recursive: true });
    if (await pathExists(join(positioningSrc, 'README.md'))) {
      copied.push(
        await copyOne(
          join(positioningSrc, 'README.md'),
          join(positioningDest, 'index.md'),
          'Positioning — working material',
        ),
      );
    }
    // Normalize underscores in filenames to hyphens for prettier URLs.
    const positioningResults = await copyDir(positioningSrc, positioningDest, {
      flattenNames: (name) => name.toLowerCase().replace(/_/g, '-'),
    });
    copied.push(...positioningResults);
  }

  // ADRs — public English versions live at docs/adr-en/ (FR originals at
  // docs/adr/ stay private to the maintainer). 20 files, flat. Sort
  // numerically in sidebar via filename.
  const adrSrc = join(REPO_ROOT, 'docs', 'adr-en');
  const adrDest = join(DOCS_DIR, 'adrs');
  if (await pathExists(adrSrc)) {
    const adrResults = await copyDir(adrSrc, adrDest);
    copied.push(...adrResults);
  }

  console.log(`[sync-docs] synced ${copied.length} files into ${DOCS_DIR}`);
}

async function writeIndexMdx() {
  // Landing page. Hand-written, not derived from any source .md.
  const indexPath = join(DOCS_DIR, 'index.mdx');
  const content = `---
title: "EPP — Epistemic Proof Program"
description: "Verifiable AI consensus on Solana. Multiple architecturally distinct LLMs deliberate under structured adversarial cycles; the result is a cryptographic attestation with methodology traceability."
template: splash
hero:
  tagline: "The oracle that doesn't trust itself."
  actions:
    - text: Read the pitch (3 min)
      link: /pitch/
      icon: right-arrow
      variant: primary
    - text: Open the live dashboard ↗
      link: https://epp-verdict.vercel.app
      icon: external
      variant: secondary
    - text: See the code on GitHub ↗
      link: https://github.com/SimonBouhier/EPP_Verdict
      icon: external
      variant: minimal
---

import { Card, CardGrid, LinkCard } from '@astrojs/starlight/components';

## What this portal contains

<CardGrid>
  <LinkCard
    title="Pitch (3 minutes)"
    description="Three acts, three primitives nobody implements, the defensible thesis that survives the counterpoint stress-test."
    href="/pitch/"
  />
  <LinkCard
    title="Whitepaper"
    description="The long-form architectural and epistemological narrative. ESMM deliberation, metrological frames, the flywheel, formal verification, why blockchain, cluster vision."
    href="/whitepaper/"
  />
  <LinkCard
    title="Architecture (living)"
    description="Component-by-component map of the codebase. Updated whenever the structure changes."
    href="/architecture/"
  />
  <LinkCard
    title="ADRs"
    description="20 Architecture Decision Records covering encoding, schema, consensus, flywheel, formal invariants, and open governance."
    href="/adrs/adr-001/"
  />
</CardGrid>

## How to read this

> **⚠ Proofs of process, not verdicts on truth.** EPP produces cryptographic measurements of multi-LLM deliberation under specified metrological frames. These attestations record *what was deliberated, by whom, and how* — they are **not** legal verdicts, regulatory decisions, or substitutes for human or institutional adjudication. Per the [UNESCO Recommendation on the Ethics of AI](https://en.unesco.org/artificial-intelligence/ethics) (193 Member States, 2021), ultimate responsibility for any decision based on an AI output remains with the natural or legal persons consuming it. Full framing in the [Whitepaper — Liability & Scope](/whitepaper/#liability--scope).

EPP is a **solo open-source build**, formally started at commit [\`f12a922\`](https://github.com/SimonBouhier/EPP_Verdict/commit/f12a922) (2026-02-13) within the Colosseum sprint eligibility window, MIT-licensed. The public narrative (Pitch, Whitepaper, Architecture) is the official project position. The [Positioning section](/positioning/) exposes the working material behind that narrative — competitive scans, counterpoint stress-tests, formal methods landscape, Colosseum track strategy, and the conceptual essay *The Negative Space of Machine Knowledge*. It's public because the reasoning leading to the public claims is itself part of the record.

## Current state (verifiable)

- **908 passing tests** · **20 ADRs** · **12 attestations live on Solana devnet**
- Program ID \`9QtybfyZQFhra1D6S3NtD6jD4z2Z3wcYmf4YXETq8bSD\` (devnet, deployed at slot 450099166)
- **6 substantive Lean 4 theorems** (4 \`iff\` characterising the four confidence tiers + 2 stratification cumulativity) + 7 regression tests + 2 type-level invariants — see audit P1–P4 under [\`docs/audit/\`](https://github.com/SimonBouhier/EPP_Verdict/tree/main/docs/audit)
- **+0.46 flywheel delta** demonstrated end-to-end (0.43 → 0.89 on the 2024 election claim)
- Live dashboard at [epp-verdict.vercel.app](https://epp-verdict.vercel.app) — auto-redeploy on each \`git push\` to main
`;
  await mkdir(dirname(indexPath), { recursive: true });
  await writeFile(indexPath, content);
}

main().catch((err) => {
  console.error('[sync-docs] failed:', err);
  process.exit(1);
});
