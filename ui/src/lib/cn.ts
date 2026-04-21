import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Class name merger: combines clsx (conditional classes) with tailwind-merge
 * (resolves conflicting Tailwind utilities — e.g. `px-2 px-4` collapses to `px-4`).
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
