'use client';

import {
  Calendar, Image as ImageIcon, Users, Download, HardDrive,
  KeyRound, ScrollText, BarChart3,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { StatGrid } from '@/components/dashboard/stat-grid';
import { MetricCard, MetricCardSkeleton } from '@/components/dashboard/metric-card';
import { DashboardSection } from '@/components/dashboard/dashboard-section';
import { ActivityList } from '@/components/dashboard/activity-list';
import { QuickActionCard, type QuickAction } from '@/components/dashboard/quick-action-card';
import { EmptyState, ErrorState, Spinner } from '@/components/feedback/states';
import { useDashboardMetrics, useActivity } from '@/lib/hooks/admin';

function fmtStorage(mb: number): string {
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb} MB`;
}

// Admin-scoped quick actions (our RBAC keeps event creation/upload on the
// studio-user dashboard — see the report's recommendations).
const QUICK_ACTIONS: QuickAction[] = [
  { label: 'Manage Users', description: 'Roles, event & storage limits', href: '/admin/users', icon: Users },
  { label: 'Agent Tokens', description: 'Create & revoke desktop-agent keys', href: '/admin/tokens', icon: KeyRound },
  { label: 'Audit Log', description: 'Review system activity', href: '/admin/audit', icon: ScrollText },
  { label: 'Analytics', description: 'Per-event scans, matches, downloads', href: '/admin/analytics', icon: BarChart3 },
];

export default function AdminDashboardPage() {
  const { metrics, perEvent, isLoading, isError, refetch } = useDashboardMetrics();
  const activity = useActivity(8);

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <PageHeader title="Dashboard" description="Overview of your studio’s activity." />

      {/* KPIs */}
      {isError ? (
        <ErrorState description="Couldn’t load dashboard metrics." onRetry={refetch} />
      ) : (
        <StatGrid>
          {isLoading || !metrics ? (
            Array.from({ length: 5 }).map((_, i) => <MetricCardSkeleton key={i} />)
          ) : (
            <>
              <MetricCard label="Total Events" value={metrics.events} icon={Calendar} />
              <MetricCard label="Total Photos" value={metrics.photos} icon={ImageIcon} />
              <MetricCard label="Guests" value={metrics.guests} icon={Users} hint="consented" />
              <MetricCard label="Downloads" value={metrics.downloads} icon={Download} />
              <MetricCard label="Storage Used" value={fmtStorage(metrics.storageUsedMb)} icon={HardDrive} />
            </>
          )}
        </StatGrid>
      )}

      {/* Recent events + activity */}
      <div className="grid gap-6 lg:grid-cols-2">
        <DashboardSection title="Recent Events" action={{ label: 'View analytics', href: '/admin/analytics' }}>
          {isLoading ? (
            <Spinner className="py-8" />
          ) : perEvent.length ? (
            <ul className="divide-y">
              {perEvent.slice(0, 5).map((e) => (
                <li key={e.event_id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{e.title || `Event #${e.event_id}`}</p>
                    <p className="text-xs text-muted-foreground">{e.photos} photos · {e.matches} matches</p>
                  </div>
                  <span className="shrink-0 text-xs text-muted-foreground">{e.downloads} downloads</span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon={Calendar} title="No events yet" description="Events created by your studios will appear here." />
          )}
        </DashboardSection>

        <DashboardSection title="Recent Activity" action={{ label: 'View all', href: '/admin/audit' }}>
          {activity.isLoading ? (
            <Spinner className="py-8" />
          ) : activity.isError ? (
            <ErrorState description="Couldn’t load activity." onRetry={() => activity.refetch()} />
          ) : activity.data?.length ? (
            <ActivityList items={activity.data} />
          ) : (
            <EmptyState icon={ScrollText} title="No activity yet" />
          )}
        </DashboardSection>
      </div>

      {/* Quick actions */}
      <div>
        <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Quick Actions</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {QUICK_ACTIONS.map((a) => <QuickActionCard key={a.href} {...a} />)}
        </div>
      </div>
    </div>
  );
}
