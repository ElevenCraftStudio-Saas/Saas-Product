import { cn } from '@/lib/utils';

/** Responsive grid wrapper for MetricCards (1→2→3→5 columns). */
export function StatGrid({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5', className)}>
      {children}
    </div>
  );
}
