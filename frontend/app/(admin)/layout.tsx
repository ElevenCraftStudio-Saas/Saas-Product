'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import Link from 'next/link';
import { ShieldCheck, LogOut, Users, KeyRound, ScrollText, BarChart3 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth-context';
import { useMe } from '@/lib/hooks/me';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, loading, signOut } = useAuth();
  const { data: me, isLoading } = useMe();

  useEffect(() => {
    if (!loading && !user) { router.push('/login'); return; }
    if (me && me.role !== 'admin') router.push('/dashboard');
  }, [loading, user, me, router]);

  if (loading || !user || isLoading || !me || me.role !== 'admin') return null;

  const items = [
    { href: '/admin/users', icon: Users, label: 'Users' },
    { href: '/admin/tokens', icon: KeyRound, label: 'Agent Tokens' },
    { href: '/admin/audit', icon: ScrollText, label: 'Audit Log' },
    { href: '/admin/analytics', icon: BarChart3, label: 'Analytics' },
  ];
  return (
    <div className="flex h-screen bg-slate-50">
      <aside className="w-64 bg-white border-r hidden md:flex flex-col">
        <div className="p-6 border-b flex items-center gap-2">
          <ShieldCheck className="w-7 h-7 text-primary" />
          <span className="text-xl font-bold">WedFind Admin</span>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          {items.map((it) => (
            <Link key={it.href} href={it.href}>
              <Button variant="ghost" className="w-full justify-start gap-2">
                <it.icon className="w-5 h-5" /> <span>{it.label}</span>
              </Button>
            </Link>
          ))}
        </nav>
        <div className="p-4 border-t">
          <Button
            variant="ghost"
            className="w-full justify-start gap-2 text-red-500 hover:text-red-600 hover:bg-red-50"
            onClick={async () => { await signOut(); router.push('/login'); }}
          >
            <LogOut className="w-5 h-5" /> <span>Logout</span>
          </Button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto p-6 md:p-8">{children}</main>
    </div>
  );
}
