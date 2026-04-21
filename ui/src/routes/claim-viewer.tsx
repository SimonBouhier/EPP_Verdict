import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { loadRun } from '@/data/loader';
import { ClaimList } from '@/features/claim-viewer';
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

  return (
    <div>
      <Link
        to="/"
        className="text-xs text-muted-foreground underline-offset-2 hover:underline"
      >
        ← all runs
      </Link>

      <header className="mb-6 mt-2">
        <h1 className="font-mono text-2xl font-semibold tracking-tight">
          {data?.scenario ?? filename}
        </h1>
        {data ? (
          <p className="mt-1 text-xs text-muted-foreground">
            {new Date(data.timestamp).toISOString()} · {data.models.join(', ')}
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

      {data ? <ClaimList claims={data.claims} /> : null}
    </div>
  );
}
