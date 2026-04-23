import type { OnChainAttestation } from '@/domain';
import { cn } from '@/lib/cn';
import { OnChainBadge } from '@/ui/OnChainBadge';
import { VerdictBadge } from '@/ui/VerdictBadge';
import type { FlywheelClaimDetail } from './parseFlywheelClaims';

interface Props {
  claim: FlywheelClaimDetail;
  onChain?: OnChainAttestation | null;
}

export function FlywheelRow({ claim, onChain }: Props) {
  return (
    <article className="grid grid-cols-1 gap-3 px-4 py-4 md:grid-cols-[5rem_minmax(0,1fr)_auto_auto_auto] md:items-center md:gap-4">
      {/* ID + origin */}
      <div className="flex items-center gap-2 md:flex-col md:items-start md:gap-1">
        <div className="font-mono text-xs text-muted-foreground">{claim.id}</div>
        <OriginBadge origin={claim.origin} />
        {onChain ? <OnChainBadge attestation={onChain} /> : null}
      </div>

      {/* Claim text + metadata */}
      <div className="min-w-0">
        <p className="text-sm leading-snug">{claim.text}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
          <span>{claim.category}</span>
          {claim.anchorsFound !== null ? (
            <>
              <span aria-hidden="true">·</span>
              <span>
                {claim.anchorsFound} anchor{claim.anchorsFound === 1 ? '' : 's'}
              </span>
            </>
          ) : null}
          {claim.sourcesInjected.length > 0 ? (
            <>
              <span aria-hidden="true">·</span>
              <span className="font-mono">
                {claim.sourcesInjected.join(', ')}
              </span>
            </>
          ) : null}
        </div>
      </div>

      {/* Baseline column */}
      <ScoreColumn
        label="Baseline"
        verdict={claim.baselineVerdict}
        score={claim.baselineScore}
      />

      {/* Arrow */}
      <div
        aria-hidden="true"
        className="hidden text-muted-foreground md:block"
      >
        →
      </div>

      {/* Flywheel column */}
      <ScoreColumn
        label="Flywheel"
        verdict={claim.flywheelVerdict}
        score={claim.flywheelScore}
        delta={claim.delta}
        highlight
      />
    </article>
  );
}

interface ScoreColumnProps {
  label: string;
  verdict: FlywheelClaimDetail['flywheelVerdict'] | null;
  score: number | null;
  delta?: number | null;
  highlight?: boolean;
}

function ScoreColumn({ label, verdict, score, delta, highlight }: ScoreColumnProps) {
  if (verdict === null || score === null) {
    return (
      <div className="flex flex-col items-end gap-1 md:min-w-[7rem]">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <span className="font-mono text-xs text-muted-foreground">—</span>
      </div>
    );
  }
  return (
    <div
      className={cn(
        'flex flex-col items-end gap-1 md:min-w-[7rem]',
        highlight && 'md:pr-1',
      )}
    >
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <VerdictBadge verdict={verdict} />
      <span className="font-mono text-xs tabular-nums">{score.toFixed(3)}</span>
      {delta !== undefined && delta !== null ? <DeltaBadge delta={delta} /> : null}
    </div>
  );
}

function DeltaBadge({ delta }: { delta: number }) {
  if (delta === 0) {
    return <span className="font-mono text-[11px] text-muted-foreground">Δ 0.000</span>;
  }
  const positive = delta > 0;
  return (
    <span
      className={cn(
        'font-mono text-[11px] tabular-nums',
        positive ? 'text-cyan' : 'text-rose-400',
      )}
    >
      {positive ? 'Δ +' : 'Δ '}
      {delta.toFixed(3)}
    </span>
  );
}

function OriginBadge({ origin }: { origin: FlywheelClaimDetail['origin'] }) {
  if (origin === 'new') {
    return (
      <span className="inline-flex items-center rounded-sm bg-gold/10 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-gold ring-1 ring-gold/30">
        new
      </span>
    );
  }
  return null;
}
