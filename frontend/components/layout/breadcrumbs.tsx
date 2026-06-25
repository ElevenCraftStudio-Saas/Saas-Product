'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ChevronRight } from 'lucide-react';

const LABELS: Record<string, string> = {
  admin: 'Admin',
  dashboard: 'Dashboard',
  users: 'Users',
  tokens: 'Agent Tokens',
  audit: 'Audit Log',
  analytics: 'Analytics',
  events: 'Events',
  settings: 'Settings',
  profile: 'Profile',
};

function titleize(segment: string): string {
  return LABELS[segment] ?? segment.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Auto breadcrumbs derived from the path. Numeric ids render as "#id". */
export function Breadcrumbs() {
  const pathname = usePathname();
  const segments = pathname.split('/').filter(Boolean);
  if (segments.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className="hidden items-center gap-1 text-sm text-muted-foreground md:flex">
      {segments.map((seg, i) => {
        const href = '/' + segments.slice(0, i + 1).join('/');
        const last = i === segments.length - 1;
        const label = /^\d+$/.test(seg) ? `#${seg}` : titleize(seg);
        return (
          <span key={href} className="flex items-center gap-1">
            {i > 0 && <ChevronRight className="h-3.5 w-3.5" aria-hidden />}
            {last ? (
              <span className="font-medium text-foreground" aria-current="page">{label}</span>
            ) : (
              <Link href={href} className="transition-colors hover:text-foreground">{label}</Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
