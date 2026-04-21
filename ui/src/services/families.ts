import { type Family, FAMILIES } from '@/config/families';
import type { RunManifestEntry } from '@/domain';

/** Sentinel id for the "All" tab — shows every run regardless of family. */
export const ALL_FAMILY_ID = 'all' as const;

/** Sentinel id for runs whose scenario isn't listed in any family. */
export const UNCLASSIFIED_FAMILY_ID = 'unclassified' as const;

export interface FamilyWithCount extends Family {
  count: number;
}

export function familyForRun(scenario: string): Family | null {
  return FAMILIES.find((f) => f.scenarios.includes(scenario)) ?? null;
}

export function filterRunsByFamily(
  runs: readonly RunManifestEntry[],
  familyId: string,
): RunManifestEntry[] {
  if (familyId === ALL_FAMILY_ID) return [...runs];
  if (familyId === UNCLASSIFIED_FAMILY_ID) {
    return runs.filter((r) => familyForRun(r.scenario) === null);
  }
  const family = FAMILIES.find((f) => f.id === familyId);
  if (!family) return [];
  return runs.filter((r) => family.scenarios.includes(r.scenario));
}

export function listFamiliesWithCounts(
  runs: readonly RunManifestEntry[],
): FamilyWithCount[] {
  return FAMILIES.map((f) => ({
    ...f,
    count: runs.filter((r) => f.scenarios.includes(r.scenario)).length,
  }));
}

export function countUnclassified(runs: readonly RunManifestEntry[]): number {
  return runs.filter((r) => familyForRun(r.scenario) === null).length;
}
