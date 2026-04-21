import { cva } from 'class-variance-authority';
import type { Verdict } from '@/domain';
import { cn } from '@/lib/cn';

const verdictBadge = cva(
  'inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1',
  {
    variants: {
      verdict: {
        SUPPORTED: 'bg-emerald-500/10 text-emerald-400 ring-emerald-500/30',
        CONTESTED: 'bg-amber-500/10 text-amber-400 ring-amber-500/30',
        INSUFFICIENT_EVIDENCE: 'bg-zinc-500/10 text-zinc-400 ring-zinc-500/30',
        REFUTED: 'bg-rose-500/10 text-rose-400 ring-rose-500/30',
      },
    },
  },
);

interface Props {
  verdict: Verdict;
  className?: string;
}

export function VerdictBadge({ verdict, className }: Props) {
  return <span className={cn(verdictBadge({ verdict }), className)}>{verdict}</span>;
}
