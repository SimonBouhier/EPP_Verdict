import type { ScenarioRun } from '@/domain';
import { deterministicSourcesAdapter } from './deterministic-sources';
import { flywheelBaselineAdapter } from './flywheel-baseline';
import { flywheelV2Adapter } from './flywheel-v2';
import { jiangAdapter } from './jiang';
import { scenario6Adapter } from './scenario6';

export type Adapter = (raw: unknown) => ScenarioRun;

/**
 * Registry: scenario name (from JSON `scenario` field) → normalizing adapter.
 * Adding a new scenario shape means adding one file in this folder and
 * one entry here. Nothing else needs to change.
 */
const ADAPTERS: Record<string, Adapter> = {
  scenario_jiang: jiangAdapter,
  scenario_flywheel_v2: flywheelV2Adapter,
  flywheel_v2_baseline: flywheelBaselineAdapter,
  scenario_6_1_edge_cases: scenario6Adapter,
  scenario_6_2_qualifier_sensitivity: scenario6Adapter,
  scenario_6_2b_qualifier_sensitivity_big_models: scenario6Adapter,
  scenario_deterministic_sources: deterministicSourcesAdapter,
};

export function detectAdapter(raw: unknown): Adapter {
  if (typeof raw !== 'object' || raw === null) {
    throw new Error('Invalid run payload: expected an object at the top level');
  }
  const scenario = (raw as { scenario?: unknown }).scenario;
  if (typeof scenario !== 'string') {
    throw new Error('Invalid run payload: missing or non-string `scenario` field');
  }
  const adapter = ADAPTERS[scenario];
  if (!adapter) {
    const known = Object.keys(ADAPTERS).sort().join(', ');
    throw new Error(
      `No adapter registered for scenario "${scenario}". ` +
        `Add one in src/data/adapters/. Known so far: ${known || '(none)'}.`,
    );
  }
  return adapter;
}

export {
  deterministicSourcesAdapter,
  flywheelBaselineAdapter,
  flywheelV2Adapter,
  jiangAdapter,
  scenario6Adapter,
};
