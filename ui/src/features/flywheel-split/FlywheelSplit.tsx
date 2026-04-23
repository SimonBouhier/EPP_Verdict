import type { OnChainAttestation } from '@/domain';
import { cn } from '@/lib/cn';
import { lookupOnChain } from '@/services/onchain';
import { FlywheelRow } from './FlywheelRow';
import {
  type FlywheelClaimDetail,
  type FlywheelSplitSummary,
} from './parseFlywheelClaims';

interface Props {
  claims: readonly FlywheelClaimDetail[];
  summary: FlywheelSplitSummary;
  onChainIndex?: Map<string, OnChainAttestation>;
}

export function FlywheelSplit({ claims, summary, onChainIndex }: Props) {
  return (
    <div>
      <SummaryStrip summary={summary} />
      {claims.length === 0 ? (
        <p className="text-sm text-muted-foreground">No claims in this run.</p>
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-md border border-border">
          {claims.map((c) => (
            <li key={c.id}>
              <FlywheelRow claim={c} onChain={lookupOnChain(onChainIndex, c.text)} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SummaryStrip({ summary }: { summary: FlywheelSplitSummary }) {
  const improvedRatio =
    summary.claimsMigrated === 0
      ? null
      : summary.claimsImproved / summary.claimsMigrated;

  return (
    <dl className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Stat label="Total claims" value={summary.claimsTotal.toString()} />
      <Stat
        label="Migrated"
        value={summary.claimsMigrated.toString()}
        hint="have baseline comparison"
      />
      <Stat
        label="Improved"
        value={
          improvedRatio === null
            ? '—'
            : `${summary.claimsImproved}/${summary.claimsMigrated}`
        }
        hint={
          improvedRatio === null
            ? undefined
            : `${(improvedRatio * 100).toFixed(0)}% of migrated`
        }
        accent={improvedRatio !== null && improvedRatio > 0.5 ? 'cyan' : undefined}
      />
      <Stat
        label="Avg Δ"
        value={summary.averageDelta === null ? '—' : formatSignedDelta(summary.averageDelta)}
        accent={
          summary.averageDelta !== null && summary.averageDelta > 0 ? 'cyan' : undefined
        }
      />
    </dl>
  );
}

function formatSignedDelta(value: number): string {
  const sign = value > 0 ? '+' : value < 0 ? '' : ' ';
  return `${sign}${value.toFixed(3)}`;
}

interface StatProps {
  label: string;
  value: string;
  hint?: string;
  accent?: 'cyan';
}

function Stat({ label, value, hint, accent }: StatProps) {
  return (
    <div className="rounded-md border border-border bg-card px-4 py-3">
      <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </dt>
      <dd
        className={cn(
          'mt-1 font-mono text-2xl font-semibold tabular-nums',
          accent === 'cyan' && 'text-cyan',
        )}
      >
        {value}
      </dd>
      {hint ? <dd className="mt-0.5 text-[11px] text-muted-foreground">{hint}</dd> : null}
    </div>
  );
}
