// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://epp-verdict-docs.vercel.app',
  integrations: [
    starlight({
      title: 'EPP',
      tagline: 'Epistemic Proof Program · Verifiable AI Consensus on Solana',
      description:
        'Public documentation for EPP — pitch, whitepaper, architecture, ADRs, and positioning material.',
      logo: {
        src: './src/assets/lighthouse.svg',
        alt: 'EPP lighthouse emblem',
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
      editLink: {
        baseUrl: 'https://github.com/SimonBouhier/EPP_Verdict/edit/main/',
      },
      lastUpdated: true,
      pagination: true,
      sidebar: [
        {
          label: 'Overview',
          items: [{ label: 'Introduction', slug: 'index' }],
        },
        {
          label: 'The project',
          items: [
            { label: 'Pitch (3 min)', slug: 'pitch' },
            { label: 'Whitepaper', slug: 'whitepaper' },
            {
              label: 'Live dashboard ↗',
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
            {
              label: 'Architecture Decision Records',
              autogenerate: { directory: 'adrs' },
              collapsed: true,
            },
          ],
        },
        {
          label: 'Positioning (working material)',
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
      ],
      components: {
        // Default Starlight components — override here if needed later.
      },
    }),
  ],
  // Vercel auto-detects Astro; no adapter needed for static SSG.
  output: 'static',
});
