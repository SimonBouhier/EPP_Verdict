// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://epp-verdict-docs.vercel.app',
  integrations: [
    starlight({
      title: 'EPP',
      tagline: 'Local deliberation · Portable attestations · Provenance',
      description:
        'Current scope and evidence for EPP, with clearly labelled historical records.',
      logo: {
        src: './src/assets/opal.svg',
        alt: 'EPP — opal emblem',
        replacesTitle: false,
      },
      customCss: ['./src/styles/custom.css'],
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/SimonBouhier/EPP_Verdict',
        },
      ],
      // Generated pages must not offer edits to generated paths or infer a
      // review date from the last commit touching their earlier content.
      lastUpdated: false,
      pagination: true,
      sidebar: [
        {
          label: 'Overview',
          items: [
            { label: 'Introduction', slug: 'index' },
            { label: 'Current scope & evidence', slug: 'current-status' },
          ],
        },
        {
          label: 'The project',
          items: [
            { label: 'Project overview', slug: 'pitch' },
            { label: 'Whitepaper', slug: 'whitepaper' },
            {
              label: 'Historical benchmark archive ↗',
              link: 'https://epp-verdict.vercel.app',
              attrs: { target: '_blank', rel: 'noopener noreferrer' },
            },
          ],
        },
        {
          label: 'Reference',
          items: [
            { label: 'Architecture', slug: 'architecture' },
            { label: 'Changelog', slug: 'changelog' },
            { label: 'Publishing & maintenance', slug: 'publishing' },
            { label: 'Technical debt', slug: 'tech-debt' },
            {
              label: 'Architecture Decision Records',
              autogenerate: { directory: 'adrs' },
              collapsed: true,
            },
          ],
        },
        {
          label: 'Historical positioning',
          collapsed: true,
          items: [
            { label: 'About this section', slug: 'positioning' },
            { label: 'Competitive landscape', slug: 'positioning/competitive-landscape' },
            { label: 'Counterpoints & responses', slug: 'positioning/counterpoints-and-responses' },
            { label: 'Formal methods landscape', slug: 'positioning/formal-methods-landscape' },
            { label: 'Colosseum track strategy', slug: 'positioning/colosseum-track-strategy' },
            { label: 'The negative space', slug: 'positioning/the-negative-space' },
          ],
        },
        {
          label: 'Earlier project documents',
          autogenerate: { directory: 'history' },
          collapsed: true,
        },
      ],
      components: {
        Head: './src/components/Head.astro',
        Hero: './src/components/OpalHero.astro',
        ThemeProvider: './src/components/OpalThemeProvider.astro',
        ThemeSelect: './src/components/OpalThemeSelect.astro',
      },
    }),
  ],
  // Vercel auto-detects Astro; no adapter needed for static SSG.
  output: 'static',
});
