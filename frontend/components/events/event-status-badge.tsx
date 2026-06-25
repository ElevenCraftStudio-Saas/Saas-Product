import { cn } from '@/lib/utils';
import { STATUS_LABEL, type EventStatus } from '@/lib/event-status';

const STYLES: Record<EventStatus, string> = {
  upcoming: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400',
  active: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400',
  past: 'bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-400',
};

export function EventStatusBadge({ status }: { status: EventStatus }) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', STYLES[status])}>
      {STATUS_LABEL[status]}
    </span>
  );
}
