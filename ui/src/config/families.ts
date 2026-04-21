/**
 * Declarative taxonomy: which scenarios belong to which family.
 *
 * Adding a new family or moving a scenario between families = edit this file
 * and commit. No other code changes required. Keep this list pitch-narrative
 * driven: each family should answer "what does this prove about EPP?".
 */
export interface Family {
  /** URL-safe identifier — appears in `?family=X`. Stable; renames break shareable links. */
  id: string;
  /** Human-readable tab label. */
  label: string;
  /** Short pitch sentence shown as tooltip / sub-header. */
  tagline: string;
  /** Exact scenario names (the JSON `scenario` field) that belong to this family. */
  scenarios: readonly string[];
}

export const FAMILIES: readonly Family[] = [
  {
    id: 'flywheel',
    label: 'Flywheel',
    tagline: 'Self-improving consensus via deterministic source injection (ADR-018).',
    scenarios: ['scenario_flywheel', 'scenario_flywheel_v2', 'flywheel_v2_baseline'],
  },
  {
    id: 'deterministic',
    label: 'Sources déterministes',
    tagline: 'Verifiable facts bypass ESMM (ADR-012). Wikidata, OFAC, EU CFSP, Verra.',
    scenarios: ['scenario_deterministic_sources'],
  },
  {
    id: 'geopolitics',
    label: 'Géopolitique',
    tagline: 'Forecast claims tested against real-world events (Jiang Xueqin theses).',
    scenarios: ['scenario_jiang'],
  },
  {
    id: 'edge-cases',
    label: 'Edge cases',
    tagline: 'Normative claims, biased framing, qualifier sensitivity (scenario 6).',
    scenarios: [
      'scenario_6_1_edge_cases',
      'scenario_6_2_qualifier_sensitivity',
      'scenario_6_2b_qualifier_sensitivity_big_models',
    ],
  },
  {
    id: 'pipeline',
    label: 'Pipeline',
    tagline: 'End-to-end pipeline benchmarks and graph seeding.',
    scenarios: ['scenario_6_full_pipeline', 'graph_seeder_blockchain'],
  },
] as const;
