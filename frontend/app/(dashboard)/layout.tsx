'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { useAuth } from '@/lib/auth-context';
import { useMe } from '@/lib/hooks/me';
import { AppShell } from '@/components/layout/app-shell';
import { studioNav } from '@/components/layout/nav-config';
import { PageSpinner } from '@/components/feedback/states';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, loading } = useAuth();
  const { data: me, isLoading } = useMe();

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login');
      return;
    }
    if (me && me.role !== 'user') router.replace('/admin');
  }, [loading, user, me, router]);

  if (loading || !user || isLoading || !me) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <PageSpinner label="Loading…" />
      </div>
    );
  }
  if (me.role !== 'user') return null; // redirecting

  return (
    <AppShell nav={studioNav} appName="WedFind Studio">
      {children}
    </AppShell>
  );
}
