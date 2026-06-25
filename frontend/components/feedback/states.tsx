'use client';

import { Loader2, AlertTriangle, Inbox, type LucideIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/** Centered spinner — inline or full-height section. */
export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <div className={cn('flex items-center justify-center gap-2 text-muted-foreground', className)}>
      <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
      {label ? <span className="text-sm">{label}</span> : <span className="sr-only">Loading</span>}
    </div>
  );
}

export function PageSpinner({ label = 'Loading…' }: { label?: string }) {
  return <Spinner className="min-h-[40vh]" label={label} />;
}

interface StateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

/** Empty state — no data yet. */
export function EmptyState({ icon: Icon = Inbox, title, description, action, className }: StateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center rounded-xl border border-dashed bg-card/50 py-16 text-center', className)}>
      <Icon className="mb-4 h-10 w-10 text-muted-foreground/60" aria-hidden />
      <h3 className="text-lg font-medium">{title}</h3>
      {description ? <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p> : null}
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}

/** Error state with optional retry. */
export function ErrorState({
  title = 'Something went wrong',
  description,
  onRetry,
  className,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div className={cn('flex flex-col items-center justify-center rounded-xl border border-destructive/30 bg-destructive/5 py-16 text-center', className)}>
      <AlertTriangle className="mb-4 h-10 w-10 text-destructive" aria-hidden />
      <h3 className="text-lg font-medium">{title}</h3>
      {description ? <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p> : null}
      {onRetry ? (
        <Button variant="outline" className="mt-6" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}
