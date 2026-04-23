import type { ClaimVerdict, OnChainAttestation } from '@/domain';
import { lookupOnChain } from '@/services/onchain';
import { ClaimRow } from './ClaimRow';

interface Props {
  claims: ClaimVerdict[];
  onChainIndex?: Map<string, OnChainAttestation>;
}

export function ClaimList({ claims, onChainIndex }: Props) {
  if (claims.length === 0) {
    return <p className="text-sm text-muted-foreground">No claims in this run.</p>;
  }
  return (
    <ul className="divide-y divide-border overflow-hidden rounded-md border border-border">
      {claims.map((c) => (
        <li key={c.id}>
          <ClaimRow claim={c} onChain={lookupOnChain(onChainIndex, c.text)} />
        </li>
      ))}
    </ul>
  );
}
