'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Camera, Menu, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ModeToggle } from '@/components/ui/mode-toggle';
import { SidebarNav } from './sidebar-nav';
import { Breadcrumbs } from './breadcrumbs';
import { UserMenu } from './user-menu';
import type { NavItem } from './nav-config';

interface AppShellProps {
  nav: NavItem[];
  appName: string;
  children: React.ReactNode;
}

function Brand({ appName }: { appName: string }) {
  return (
    <Link href="/" className="flex items-center gap-2 px-5 py-4">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Camera className="h-5 w-5" />
      </span>
      <span className="text-base font-semibold tracking-tight">{appName}</span>
    </Link>
  );
}

export function AppShell({ nav, appName, children }: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();

  // Close the mobile drawer whenever the route changes. Synchronizing UI state
  // to the external router is a legitimate effect; the rule's heuristic flags
  // the synchronous setState, which is the intended one-shot reset here.
  // eslint-disable-next-line react-hooks/set-state-in-effect -- route-driven drawer reset
  useEffect(() => setMobileOpen(false), [pathname]);

  return (
    <div className="flex min-h-screen bg-muted/30">
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r bg-card md:flex">
        <Brand appName={appName} />
        <SidebarNav items={nav} />
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
            aria-hidden
          />
          <aside className="absolute left-0 top-0 flex h-full w-72 flex-col border-r bg-card shadow-xl">
            <div className="flex items-center justify-between pr-2">
              <Brand appName={appName} />
              <button
                onClick={() => setMobileOpen(false)}
                aria-label="Close menu"
                className="rounded-lg p-2 text-muted-foreground hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <SidebarNav items={nav} onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur md:px-6">
          <button
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
            className={cn('rounded-lg p-2 text-muted-foreground hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:hidden')}
          >
            <Menu className="h-5 w-5" />
          </button>
          <Breadcrumbs />
          <div className="flex-1" />
          <ModeToggle />
          <UserMenu />
        </header>

        <main className="flex-1 p-4 md:p-8">{children}</main>
      </div>
    </div>
  );
}
