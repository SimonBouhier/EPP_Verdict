# Opal / 01 — presentation study

Prepared on 5 September 2026 from Simon's Opal Gardener V3 reference files.
The request is to try the aesthetic on the existing documentation website.
This is a presentation experiment; the supplied skill has not been installed,
and no live WorldState adapter or agent instrumentation has been added.

## Visual choices

- Ivory, sage and lilac in light mode; deep green and pearl in dark mode.
- Dark is the first-visit default, independent of the system theme. An explicit
  Light or System choice remains available and is preserved across visits.
- System typography and Georgia: no font request to a third-party service.
- An inline SVG Brume landscape with transparent forms, roots and plant matter.
- The same palette and reading typography on the documentation pages.
- Original project facts remain in the source documents and dated status page.

## Meaning and interaction

Brume is the sole illustration, following Simon's final design choice.
It shows dispersed transparent forms. There is no material selector and no
mapping to measured system states.

There is no numerical mapping to Opal's six dimensions, because this static
portal has no corresponding measurements. No OpalEvent is fabricated or logged.
The inspector explains this boundary and links to the actual project status.

Two groups drift slowly as decorative ambience.
The pause control stops that drift. Reduced-motion preferences disable both
drift, and disable the redundant pause control. Without
JavaScript, the Brume illustration, content and links remain available.

## Files and reuse

- `src/components/OpalLandscape.astro`: deterministic illustration, no measurements.
- `src/components/OpalHero.astro`: source-based copy and presentation controls.
- `src/styles/custom.css`: responsive light and dark styling.
- `../docs/PORTAL_INDEX.mdx`: maintained homepage content, copied by the generator.

The interaction module is scoped to this hero. Reference pages do not load it.
No JavaScript dependency was added. A future Lyra adaptation can reuse the
renderer, but any real state projection needs a separately defined and validated
mapping. Nothing in this study authorizes deployment or a research campaign.

The historical dashboard uses the same dark palette and emblem, plus a static
export of the Brume illustration in `../ui/src/assets/opal-garden.svg`.
Its recorded data and semantic verdict colors retain their original meaning.
