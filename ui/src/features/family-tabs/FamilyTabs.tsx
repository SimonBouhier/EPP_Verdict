import { Link, useSearchParams } from 'react-router-dom';
import type { RunManifestEntry } from '@/domain';
import { cn } from '@/lib/cn';
import {
  ALL_FAMILY_ID,
  UNCLASSIFIED_FAMILY_ID,
  countUnclassified,
  listFamiliesWithCounts,
} from '@/services/families';

interface Props {
  runs: readonly RunManifestEntry[];
}

interface TabDef {
  id: string;
  label: string;
  count: number;
  tagline?: string;
}

export function FamilyTabs({ runs }: Props) {
  const [params] = useSearchParams();
  const active = params.get('family') ?? ALL_FAMILY_ID;

  const families = listFamiliesWithCounts(runs);
  const unclassified = countUnclassified(runs);

  const tabs: TabDef[] = [
    { id: ALL_FAMILY_ID, label: 'All', count: runs.length },
    ...families.map((f) => ({
      id: f.id,
      label: f.label,
      count: f.count,
      tagline: f.tagline,
    })),
    ...(unclassified > 0
      ? [{ id: UNCLASSIFIED_FAMILY_ID, label: 'Unclassified', count: unclassified }]
      : []),
  ];

  return (
    <nav
      aria-label="Filter runs by family"
      className="-mx-4 mb-6 overflow-x-auto px-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      <ul className="flex min-w-max gap-1 border-b border-border">
        {tabs.map((tab) => (
          <li key={tab.id}>
            <FamilyTab tab={tab} isActive={tab.id === active} />
          </li>
        ))}
      </ul>
    </nav>
  );
}

interface TabProps {
  tab: TabDef;
  isActive: boolean;
}

function FamilyTab({ tab, isActive }: TabProps) {
  // The "All" tab clears the family param entirely so its URL stays clean.
  const search =
    tab.id === ALL_FAMILY_ID ? '' : `?family=${encodeURIComponent(tab.id)}`;

  return (
    <Link
      to={{ pathname: '/', search }}
      title={tab.tagline}
      aria-current={isActive ? 'page' : undefined}
      className={cn(
        '-mb-px inline-flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-sm transition-colors',
        isActive
          ? 'border-cyan text-foreground'
          : 'border-transparent text-muted-foreground hover:border-border hover:text-foreground',
      )}
    >
      <span>{tab.label}</span>
      <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
        {tab.count}
      </span>
    </Link>
  );
}
