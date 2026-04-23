import { useQuery } from '@tanstack/react-query';
import { loadOnChainManifest } from '@/data/loader';
import type { OnChainAttestation } from '@/domain';
import { cn } from '@/lib/cn';
import { Card, CardContent } from '@/ui/Card';
import { VerdictBadge } from '@/ui/VerdictBadge';

export default function OnChainPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['onchain'],
    queryFn: loadOnChainManifest,
  });

  return (
    <div>
      <header className="mb-8">
        <div className="flex items-baseline gap-2">
          <span
            aria-hidden="true"
            className="size-2 rounded-full bg-cyan shadow-[0_0_12px_var(--color-cyan)]"
          />
          <h1 className="text-2xl font-semibold tracking-tight">On-chain attestations</h1>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          EPP attestations submitted to Solana devnet via{' '}
          <code className="font-mono text-xs">scripts/push_to_devnet.py</code>. Click any
          row to open the transaction on Solana Explorer.
        </p>
      </header>

      {isLoading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
      {error ? (
        <Card className="border-rose-500/30 bg-rose-500/5">
          <CardContent>
            <p className="text-sm text-rose-400">{(error as Error).message}</p>
          </CardContent>
        </Card>
      ) : null}

      {data ? <ManifestView manifest={data} /> : null}
    </div>
  );
}

interface ManifestViewProps {
  manifest: NonNullable<ReturnType<typeof loadOnChainManifest> extends Promise<infer T> ? T : never>;
}

function ManifestView({ manifest }: ManifestViewProps) {
  const okAttestations = manifest.attestations.filter((a) => a.status === 'ok');

  if (okAttestations.length === 0) {
    return (
      <Card>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No attestations on-chain yet. Run{' '}
            <code className="font-mono">python scripts/push_to_devnet.py</code> from the
            project root to populate this view.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <ProgramSummary manifest={manifest} okCount={okAttestations.length} />
      <h2 className="mb-3 mt-6 text-sm font-medium text-muted-foreground">
        {okAttestations.length} attestation{okAttestations.length === 1 ? '' : 's'}
      </h2>
      <ul className="divide-y divide-border overflow-hidden rounded-md border border-border">
        {okAttestations.map((att) => (
          <li key={att.claim_hash}>
            <AttestationRow attestation={att} />
          </li>
        ))}
      </ul>
    </>
  );
}

interface ProgramSummaryProps {
  manifest: ManifestViewProps['manifest'];
  okCount: number;
}

function ProgramSummary({ manifest, okCount }: ProgramSummaryProps) {
  return (
    <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <SummaryCard label="Cluster" value={manifest.cluster} mono />
      <SummaryCard label="Program ID" value={manifest.programId} mono truncate />
      <SummaryCard label="Submitter" value={manifest.submitter} mono truncate />
      <SummaryCard label="Pushed" value={`${okCount} / ${manifest.summary.total_entries}`} accent />
      <SummaryCard label="Failed" value={manifest.summary.failed.toString()} />
      <SummaryCard label="Generated at" value={formatTimestamp(manifest.generatedAt)} />
    </dl>
  );
}

interface SummaryCardProps {
  label: string;
  value: string;
  mono?: boolean;
  truncate?: boolean;
  accent?: boolean;
}

function SummaryCard({ label, value, mono, truncate, accent }: SummaryCardProps) {
  return (
    <div className="rounded-md border border-border bg-card px-4 py-3">
      <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd
        className={cn(
          'mt-1 text-sm',
          mono && 'font-mono',
          truncate && 'truncate',
          accent && 'text-cyan font-semibold',
        )}
        title={truncate ? value : undefined}
      >
        {value || '—'}
      </dd>
    </div>
  );
}

function AttestationRow({ attestation }: { attestation: OnChainAttestation }) {
  const Inner = (
    <article className="grid grid-cols-1 gap-3 px-4 py-4 md:grid-cols-[minmax(0,1fr)_auto_auto] md:items-center md:gap-4">
      <div className="min-w-0">
        <p className="truncate text-sm" title={attestation.question ?? attestation.subject}>
          {attestation.question ?? `${attestation.subject} · ${attestation.predicate} · ${attestation.object}`}
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
          <span className="font-mono">{attestation.metrological_frame}</span>
          <span aria-hidden="true">·</span>
          <span>{attestation.epistemic_type}</span>
          <span aria-hidden="true">·</span>
          <span>{attestation.confidence_tier}</span>
          {attestation.slot != null ? (
            <>
              <span aria-hidden="true">·</span>
              <span className="font-mono">slot {attestation.slot}</span>
            </>
          ) : null}
        </div>
        <div className="mt-1 font-mono text-[10px] text-muted-foreground">
          claim_hash {attestation.claim_hash.slice(0, 16)}… · pda{' '}
          {attestation.pda?.slice(0, 16) ?? '—'}…
        </div>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1">
        {attestation.verdict ? <VerdictBadge verdict={attestation.verdict} /> : null}
        <span className="font-mono text-xs tabular-nums">
          {attestation.consensus_score.toFixed(3)}
        </span>
      </div>
      <div className="flex shrink-0 items-center text-xs text-cyan">
        <span aria-hidden="true">→</span>
      </div>
    </article>
  );

  if (!attestation.explorer_url) return Inner;
  return (
    <a
      href={attestation.explorer_url}
      target="_blank"
      rel="noopener noreferrer"
      className="block transition-colors hover:bg-accent/30"
      title={`tx ${attestation.tx_signature?.slice(0, 16)}…`}
    >
      {Inner}
    </a>
  );
}

function formatTimestamp(iso: string): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toISOString().slice(0, 16).replace('T', ' ');
  } catch {
    return iso;
  }
}
