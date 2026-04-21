import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { loadManifest } from '@/data/loader';
import type { RunManifestEntry } from '@/domain';
import { FamilyTabs } from '@/features/family-tabs';
import {
  ALL_FAMILY_ID,
  familyForRun,
  filterRunsByFamily,
} from '@/services/families';
import { Card, CardContent } from '@/ui/Card';

function formatTimestamp(iso: string): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toISOString().slice(0, 16).replace('T', ' ');
  } catch {
    return iso;
  }
}

export default function HomePage() {
  const [params] = useSearchParams();
  const familyId = params.get('family') ?? ALL_FAMILY_ID;

  const { data, isLoading, error } = useQuery({
    queryKey: ['manifest'],
    queryFn: loadManifest,
  });

  const filtered = useMemo(
    () => (data ? filterRunsByFamily(data.runs, familyId) : []),
    [data, familyId],
  );

  return (
    <div>
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Epistemic Proof Program</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Verifiable AI consensus on Solana. Browse benchmark runs from{' '}
          <code className="font-mono text-xs">demos/benchmark_runs/</code>.
        </p>
      </header>

      {isLoading ? <p className="text-sm text-muted-foreground">Loading manifest…</p> : null}
      {error ? (
        <Card className="border-rose-500/30 bg-rose-500/5">
          <CardContent>
            <p className="text-sm text-rose-400">{(error as Error).message}</p>
          </CardContent>
        </Card>
      ) : null}

      {data ? (
        <>
          <FamilyTabs runs={data.runs} />

          <div className="mb-3 flex items-baseline justify-between">
            <p className="text-sm text-muted-foreground">
              {filtered.length} run{filtered.length === 1 ? '' : 's'}
            </p>
          </div>

          {filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground">No runs in this family.</p>
          ) : (
            <ul className="grid gap-2">
              {filtered.map((run) => (
                <li key={run.filename}>
                  <RunCard run={run} />
                </li>
              ))}
            </ul>
          )}
        </>
      ) : null}
    </div>
  );
}

interface RunCardProps {
  run: RunManifestEntry;
}

function RunCard({ run }: RunCardProps) {
  const family = familyForRun(run.scenario);
  return (
    <Link
      to={`/claims?run=${encodeURIComponent(run.filename)}`}
      className="block rounded-md border border-border bg-card px-4 py-3 transition-colors hover:border-cyan/40 hover:bg-accent/30"
    >
      <div className="flex items-baseline justify-between gap-4">
        <span className="font-mono text-sm">{run.scenario}</span>
        <span className="font-mono text-xs text-muted-foreground tabular-nums">
          {formatTimestamp(run.timestamp)}
        </span>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
        <span>
          {run.claimsCount} claim{run.claimsCount === 1 ? '' : 's'}
        </span>
        {run.adr ? (
          <>
            <span aria-hidden="true">·</span>
            <span>{run.adr}</span>
          </>
        ) : null}
        {family ? (
          <>
            <span aria-hidden="true">·</span>
            <span className="text-cyan">{family.label}</span>
          </>
        ) : null}
      </div>
    </Link>
  );
}
