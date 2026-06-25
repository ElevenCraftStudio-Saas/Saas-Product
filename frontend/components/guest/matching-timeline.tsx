'use client';

import { Check, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export const MATCH_STAGES = [
  'Uploading selfie',
  'Detecting face',
  'Generating embedding',
  'Searching event photos',
  'Preparing gallery',
] as const;

/** Animated lifecycle. The backend exposes a single call, so stages are
 *  simulated client-side while the request is in flight; `done` snaps all
 *  complete on success. */
export function MatchingTimeline({ current, done }: { current: number; done: boolean }) {
  return (
    <ul className="space-y-3">
      {MATCH_STAGES.map((stage, i) => {
        const complete = done || i < current;
        const active = !done && i === current;
        return (
          <li key={stage} className="flex items-center gap-3">
            <span
              className={cn(
                'flex h-7 w-7 items-center justify-center rounded-full transition-colors',
                complete ? 'bg-emerald-500 text-white' : active ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground',
              )}
            >
              {complete ? <Check className="h-4 w-4" /> : active ? <Loader2 className="h-4 w-4 animate-spin" /> : <span className="text-xs">{i + 1}</span>}
            </span>
            <span className={cn('text-sm transition-colors', complete || active ? 'text-foreground' : 'text-muted-foreground', active && 'font-medium')}>
              {stage}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
