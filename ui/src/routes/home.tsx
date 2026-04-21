import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { loadManifest } from '@/data/loader';
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
  const { data, isLoading, error } = useQuery({
    queryKey: ['manifest'],
    queryFn: loadManifest,
  });

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
        <section>
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">
            {data.runs.length} run{data.runs.length === 1 ? '' : 's'} available
          </h2>
          <ul className="grid gap-2">
            {data.runs.map((run) => (
              <li key={run.filename}>
                <Link
                  to={`/claims?run=${encodeURIComponent(run.filename)}`}
                  className="block rounded-md border border-border bg-card px-4 py-3 transition-colors hover:bg-accent/30"
                >
                  <div className="flex items-baseline justify-between gap-4">
                    <span className="font-mono text-sm">{run.scenario}</span>
                    <span className="font-mono text-xs text-muted-foreground tabular-nums">
                      {formatTimestamp(run.timestamp)}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {run.claimsCount} claim{run.claimsCount === 1 ? '' : 's'}
                    {run.adr ? ` · ${run.adr}` : ''}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
