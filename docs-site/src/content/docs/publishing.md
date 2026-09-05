---
title: "Documentation and static-site maintenance"
editUrl: false
---

## Sources and destinations

| Source | Generated portal page |
|---|---|
| `docs/PORTAL_INDEX.mdx` | Home |
| `docs/CURRENT_STATUS.md` | Current scope and dated verification |
| `PITCH.md`, `WHITEPAPER.md` | Overview and current whitepaper |
| `docs/ARCHITECTURE.md` | Code map |
| `docs/PUBLISHING.md`, `TECH_DEBT.md` | Maintenance references |
| `docs/fr/CHANGELOG.md` | Dated history |
| `docs/adr-en/` | Original decision records; earlier scope contextualized |
| `docs/positioning/`, `docs/history/` | Labelled historical material |

Edit sources, not `docs-site/src/content/docs/`. The generator contains no
independent project pitch or test counts. It resolves links to the generated
routes, including French-to-English ADR filenames.

## Before promotion

From `docs-site/`:

```text
npm run sync
npm run check:sync
npm test
npm run build
```

The synchronization check fails if committed pages differ from source output.
A generated manifest binds source and output text with LF-normalized line endings
so Git checkouts on Windows and Linux agree. When an isolated build
cannot access parent sources, it verifies the committed output against that
manifest instead of silently trusting arbitrary content. Such a build cannot
check inaccessible parent sources; the repository check remains necessary.

The generator reads every source before writing any output. It does not
recursively clear the content directory.

From `ui/`:

```text
npm test
npm run build
```

The dashboard is a fixed historical snapshot. Development and build commands
do not refresh `ui/public/data/`. No API is planned to make this archive live.
The legacy `copy-data.mjs` has been retired and refuses execution.
Its integrity manifest also normalizes line endings to LF; no JSON fields are changed.
The Vercel configuration includes the [documented Vite SPA rewrite](https://vercel.com/docs/frameworks/frontend/vite#using-vite-to-make-spas)
so direct links to `/claims`, `/flywheel` and `/onchain` reach the viewer.
Verify these direct links on the preview deployment before promotion.

## Publication boundary

The existing targets are the documentation portal
(`epp-verdict-docs.vercel.app`, project directory `docs-site/`) and the historical
dashboard (`epp-verdict.vercel.app`, project directory `ui/`).

A successful local build does not mean either target has been updated.
Promotion follows ADR-021: reviewed changes, checks and an authorized merge.
Any direct Vercel publication must identify its project, current deployment and
rollback target before execution; never infer production permission from a build.

The future Lyra page is a separate design and publication task. This
realignment does not create it or choose its design.
