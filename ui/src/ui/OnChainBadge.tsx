import type { OnChainAttestation } from '@/domain';
import { cn } from '@/lib/cn';

interface Props {
  attestation: OnChainAttestation;
  /** Override label (default: "on-chain"). */
  label?: string;
  className?: string;
}

/**
 * Cyan chain-link badge that links to the Solana Explorer for the
 * attestation. Used wherever a claim row matches an on-chain push.
 *
 * Click stops propagation so the badge can sit inside a Link without
 * triggering the parent navigation.
 */
export function OnChainBadge({ attestation, label = 'on-chain', className }: Props) {
  if (!attestation.explorer_url) {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1 rounded-md bg-cyan/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-cyan ring-1 ring-cyan/30',
          className,
        )}
        title={`PDA ${attestation.pda ?? '—'} · ${attestation.metrological_frame}`}
      >
        <span aria-hidden="true">⛓</span>
        {label}
      </span>
    );
  }

  const slotHint = attestation.slot != null ? `slot ${attestation.slot}` : '';
  const tooltip = [
    `tx ${attestation.tx_signature?.slice(0, 16)}…`,
    `frame ${attestation.metrological_frame}`,
    slotHint,
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <a
      href={attestation.explorer_url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => e.stopPropagation()}
      title={tooltip}
      className={cn(
        'inline-flex items-center gap-1 rounded-md bg-cyan/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-cyan ring-1 ring-cyan/30 transition-colors hover:bg-cyan/20',
        className,
      )}
    >
      <span aria-hidden="true">⛓</span>
      {label}
    </a>
  );
}
