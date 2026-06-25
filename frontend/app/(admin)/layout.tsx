'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { useAuth } from '@/lib/auth-context';
import { useMe } from '@/lib/hooks/me';
import { AppShell } from '@/components/layout/app-shell';
import { adminNav } from '@/components/layout/nav-config';
import { PageSpinner } from '@/components/feedback/states';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, loading } = useAuth();
  const { data: me, isLoading } = useMe();

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login');
      return;
    }
    if (me && me.role !== 'admin') router.replace('/dashboard');
  }, [loading, user, me, router]);

  // Loading screen while auth/role resolves — prevents an unauthorized flash.
  if (loading || !user || isLoading || !me) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <PageSpinner label="Loading…" />
      </div>
    );
  }
  if (me.role !== 'admin') return null; // redirecting

  return (
    <AppShell nav={adminNav} appName="WedFind Admin">
      {children}
    </AppShell>
  );
}
