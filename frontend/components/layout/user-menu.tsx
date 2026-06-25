'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { LogOut, User as UserIcon, ChevronDown } from 'lucide-react';
import { useAuth } from '@/lib/auth-context';
import { useMe } from '@/lib/hooks/me';
import { useClickOutside } from '@/lib/hooks/use-click-outside';
import { cn } from '@/lib/utils';

function initials(name: string | null, email: string | null): string {
  const src = name?.trim() || email?.split('@')[0] || 'U';
  const parts = src.split(/[.\s_-]+/).filter(Boolean);
  return (parts[0]?.[0] ?? 'U').concat(parts[1]?.[0] ?? '').toUpperCase();
}

export function UserMenu() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { signOut } = useAuth();
  const { data: me } = useMe();
  const ref = useClickOutside<HTMLDivElement>(() => setOpen(false));

  const label = me?.name || me?.email || 'Account';

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-full p-1 pr-2 text-sm transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
          {initials(me?.name ?? null, me?.email ?? null)}
        </span>
        <span className="hidden max-w-[12rem] truncate font-medium sm:inline">{label}</span>
        <ChevronDown className="hidden h-4 w-4 text-muted-foreground sm:inline" aria-hidden />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-56 overflow-hidden rounded-xl border bg-popover p-1 text-popover-foreground shadow-lg"
        >
          <div className="px-3 py-2">
            <p className="truncate text-sm font-medium">{me?.name || 'Studio'}</p>
            <p className="truncate text-xs text-muted-foreground">{me?.email}</p>
            {me?.role ? (
              <span className={cn(
                'mt-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide',
                me.role === 'admin' ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400' : 'bg-primary/10 text-primary',
              )}>
                {me.role}
              </span>
            ) : null}
          </div>
          <div className="my-1 h-px bg-border" />
          <button
            role="menuitem"
            onClick={() => { setOpen(false); router.push('/profile'); }}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-accent"
          >
            <UserIcon className="h-4 w-4" aria-hidden /> Profile
          </button>
          <button
            role="menuitem"
            onClick={async () => { setOpen(false); await signOut(); router.replace('/login'); }}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
          >
            <LogOut className="h-4 w-4" aria-hidden /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}
