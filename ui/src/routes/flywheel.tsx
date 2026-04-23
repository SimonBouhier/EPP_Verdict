import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { loadOnChainManifest, loadRun } from '@/data/loader';
import {
  FlywheelSplit,
  parseFlywheelClaims,
  summarizeFlywheelSplit,
} from '@/features/flywheel-split';
import { buildOnChainIndex } from '@/services/onchain';
import { Card, CardContent } from '@/ui/Card';

export default function FlywheelPage() {
  const [params] = useSearchParams();
  const run = params.get('run');

  if (!run) {
    return (
      <p className="text-sm text-muted-foreground">
        No run selected.{' '}
        <Link to="/?family=flywheel" className="underline underline-offset-2">
          Pick a flywheel run.
        </Link>
      </p>
    );
  }

  return <FlywheelView filename={run} />;
}

interface ViewProps {
  filename: string;
}

function FlywheelView({ filename }: ViewProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['run', filename],
    queryFn: () => loadRun(filename),
  });

  const flywheelData = useMemo(() => {
    if (!data || data.scenario !== 'scenario_flywheel_v2') return null;
    const claims = parseFlywheelClaims(data.raw);
    return {
      claims,
      summary: summarizeFlywheelSplit(claims),
    };
  }, [data]);

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
        to={`/claims?run=${encodeURIComponent(filename)}`}
        className="text-xs text-muted-foreground underline-offset-2 hover:underline"
      >
        ← list view
      </Link>

      <header className="mb-6 mt-2">
        <div className="flex items-baseline gap-2">
          <span aria-hidden="true" className="size-2 rounded-full bg-cyan shadow-[0_0_12px_var(--color-cyan)]" />
          <h1 className="font-mono text-2xl font-semibold tracking-tight">
            Flywheel split
          </h1>
        </div>
        {data ? (
          <p className="mt-1 text-xs text-muted-foreground">
            {data.scenario} · {new Date(data.timestamp).toISOString()}
          </p>
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
      {data && data.scenario !== 'scenario_flywheel_v2' ? (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <CardContent>
            <p className="text-sm text-amber-300">
              Flywheel split requires a <code className="font-mono">scenario_flywheel_v2</code>{' '}
              run. This run is <code className="font-mono">{data.scenario}</code>.
            </p>
          </CardContent>
        </Card>
      ) : null}
      {flywheelData ? (
        <FlywheelSplit
          claims={flywheelData.claims}
          summary={flywheelData.summary}
          onChainIndex={onChainIndex}
        />
      ) : null}
    </div>
  );
}
