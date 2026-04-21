import type { ScenarioRun } from '@/domain';
import { jiangAdapter } from './jiang';

export type Adapter = (raw: unknown) => ScenarioRun;

/**
 * Registry: scenario name (from JSON `scenario` field) → normalizing adapter.
 * Adding a new scenario shape means adding one file in this folder and
 * one entry here. Nothing else needs to change.
 */
const ADAPTERS: Record<string, Adapter> = {
  scenario_jiang: jiangAdapter,
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
    throw new Error(
      `No adapter registered for scenario "${scenario}". ` +
        `Known: ${Object.keys(ADAPTERS).join(', ') || '(none)'}`,
    );
  }
  return adapter;
}

export { jiangAdapter };
