import Link from 'next/link';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface QuickAction {
  label: string;
  description: string;
  href: string;
  icon: LucideIcon;
}

/** Clickable action tile for the dashboard "Quick Actions" block. */
export function QuickActionCard({ label, description, href, icon: Icon }: QuickAction) {
  return (
    <Link
      href={href}
      className={cn(
        'group flex items-start gap-3 rounded-xl border bg-card p-4 transition-all',
        'hover:border-primary/40 hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
      )}
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
        <Icon className="h-5 w-5" aria-hidden />
      </span>
      <div className="min-w-0">
        <p className="font-medium">{label}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </Link>
  );
}
