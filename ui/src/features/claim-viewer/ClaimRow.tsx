import type { ClaimVerdict, OnChainAttestation } from '@/domain';
import { OnChainBadge } from '@/ui/OnChainBadge';
import { VerdictBadge } from '@/ui/VerdictBadge';

interface Props {
  claim: ClaimVerdict;
  onChain?: OnChainAttestation | null;
}

export function ClaimRow({ claim, onChain }: Props) {
  return (
    <article className="flex items-start gap-4 px-4 py-3">
      <div className="w-20 shrink-0 font-mono text-xs text-muted-foreground">{claim.id}</div>
      <div className="min-w-0 flex-1">
        <p className="text-sm leading-snug">{claim.text}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
          <span>{claim.category}</span>
          <span aria-hidden="true">·</span>
          <span>{claim.claimType}</span>
          {claim.modelsAgreed !== null && claim.modelsTotal !== null ? (
            <>
              <span aria-hidden="true">·</span>
              <span>
                {claim.modelsAgreed}/{claim.modelsTotal} models
              </span>
            </>
          ) : null}
          {claim.voteEntropy !== null ? (
            <>
              <span aria-hidden="true">·</span>
              <span>H={claim.voteEntropy.toFixed(3)}</span>
            </>
          ) : null}
        </div>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1">
        <VerdictBadge verdict={claim.verdict} />
        <span className="font-mono text-xs tabular-nums">{claim.consensusScore.toFixed(3)}</span>
        {onChain ? <OnChainBadge attestation={onChain} /> : null}
      </div>
    </article>
  );
}
