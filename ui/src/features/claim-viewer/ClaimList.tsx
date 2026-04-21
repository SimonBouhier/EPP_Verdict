import type { ClaimVerdict } from '@/domain';
import { ClaimRow } from './ClaimRow';

interface Props {
  claims: ClaimVerdict[];
}

export function ClaimList({ claims }: Props) {
  if (claims.length === 0) {
    return <p className="text-sm text-muted-foreground">No claims in this run.</p>;
  }
  return (
    <ul className="divide-y divide-border overflow-hidden rounded-md border border-border">
      {claims.map((c) => (
        <li key={c.id}>
          <ClaimRow claim={c} />
        </li>
      ))}
    </ul>
  );
}
