import { Clock, Loader2, CheckCircle2, XCircle, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ProcessingStatus } from '@/types/models';

// Server-side photo lifecycle: Queued → Processing (detect + embed) → Ready.
// Reused anywhere photos are shown (workspace, future photo management).
const MAP: Record<ProcessingStatus, { label: string; cls: string; Icon: LucideIcon; spin?: boolean }> = {
  pending: { label: 'Queued', cls: 'bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-400', Icon: Clock },
  processing: { label: 'Processing', cls: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400', Icon: Loader2, spin: true },
  completed: { label: 'Ready', cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400', Icon: CheckCircle2 },
  failed: { label: 'Failed', cls: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400', Icon: XCircle },
};

export function ProcessingBadge({ status, className }: { status: ProcessingStatus; className?: string }) {
  const { label, cls, Icon, spin } = MAP[status] ?? MAP.pending;
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', cls, className)}>
      <Icon className={cn('h-3 w-3', spin && 'animate-spin')} aria-hidden />
      {label}
    </span>
  );
}
