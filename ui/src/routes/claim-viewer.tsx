import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { loadOnChainManifest, loadRun } from '@/data/loader';
import { ClaimList } from '@/features/claim-viewer';
import { buildOnChainIndex } from '@/services/onchain';
import { Card, CardContent } from '@/ui/Card';

export default function ClaimViewerPage() {
  const [params] = useSearchParams();
  const run = params.get('run');

  if (!run) {
    return (
      <div>
        <p className="text-sm text-muted-foreground">
          No run selected.{' '}
          <Link to="/" className="underline underline-offset-2">
            Pick one from the list.
          </Link>
        </p>
      </div>
    );
  }

  return <RunView filename={run} />;
}

interface RunViewProps {
  filename: string;
}

function RunView({ filename }: RunViewProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['run', filename],
    queryFn: () => loadRun(filename),
  });

  const { data: onChainManifest } = useQuery({
    queryKey: ['onchain'],
    queryFn: loadOnChainManifest,
  });
  const onChainIndex = useMemo(
    () => (onChainManifest ? buildOnChainIndex(onChainManifest) : undefined),
    [onChainManifest],
  );

  return (
    <div>
      <Link
        to="/"
        className="text-xs text-muted-foreground underline-offset-2 hover:underline"
      >
        ← all runs
      </Link>

      <header className="mb-6 mt-2 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-mono text-2xl font-semibold tracking-tight">
            {data?.scenario ?? filename}
          </h1>
          {data ? (
            <p className="mt-1 text-xs text-muted-foreground">
              {new Date(data.timestamp).toISOString()}
              {data.models.length > 0 ? ` · ${data.models.join(', ')}` : ''}
            </p>
          ) : null}
        </div>
        {data?.scenario === 'scenario_flywheel_v2' ? (
          <Link
            to={`/flywheel?run=${encodeURIComponent(filename)}`}
            className="inline-flex items-center gap-1.5 rounded-md border border-cyan/40 bg-cyan/10 px-3 py-1.5 text-sm text-cyan transition-colors hover:bg-cyan/20"
          >
            <span aria-hidden="true">⇄</span>
            <span>Flywheel split</span>
          </Link>
        ) : null}
      </header>

      {isLoading ? <p className="text-sm text-muted-foreground">Loading run…</p> : null}
      {error ? (
        <Card className="border-rose-500/30 bg-rose-500/5">
          <CardContent>
            <p className="text-sm text-rose-400">{(error as Error).message}</p>
          </CardContent>
        </Card>
      ) : null}

      {data ? <ClaimList claims={data.claims} onChainIndex={onChainIndex} /> : null}
    </div>
  );
}
