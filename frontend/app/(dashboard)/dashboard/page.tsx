'use client';

import {
  Calendar, CalendarCheck, Image as ImageIcon, Users, Download, HardDrive,
  Upload, User, Settings, UploadCloud, FolderSync,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { StatGrid } from '@/components/dashboard/stat-grid';
import { MetricCard, MetricCardSkeleton } from '@/components/dashboard/metric-card';
import { DashboardSection } from '@/components/dashboard/dashboard-section';
import { QuickActionCard, type QuickAction } from '@/components/dashboard/quick-action-card';
import { EventFormDialog } from '@/components/events/event-form-dialog';
import { EventStatusBadge } from '@/components/events/event-status-badge';
import { EmptyState, ErrorState } from '@/components/feedback/states';
import { useStudioMetrics } from '@/lib/hooks/studio';
import { deriveStatus } from '@/lib/event-status';
import { formatDate } from '@/lib/format';

const dash = (v: number | null) => (v == null ? '—' : v);

const QUICK_ACTIONS: QuickAction[] = [
  { label: 'My Events', description: 'View and manage events', href: '/events', icon: Calendar },
  { label: 'Upload Photos', description: 'Open an event to upload', href: '/events', icon: Upload },
  { label: 'Profile', description: 'Account details', href: '/profile', icon: User },
  { label: 'Settings', description: 'Preferences', href: '/settings', icon: Settings },
];

export default function StudioDashboardPage() {
  const { metrics, events, isLoading, isError, refetch } = useStudioMetrics();
  const recent = [...events]
    .sort((a, b) => new Date(b.event_date).getTime() - new Date(a.event_date).getTime())
    .slice(0, 5);

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <PageHeader
        title="Dashboard"
        description="Your wedding events at a glance."
        actions={<EventFormDialog />}
      />

      {isError ? (
        <ErrorState description="Couldn’t load your dashboard." onRetry={() => refetch()} />
      ) : (
        <StatGrid>
          {isLoading ? (
            Array.from({ length: 6 }).map((_, i) => <MetricCardSkeleton key={i} />)
          ) : (
            <>
              <MetricCard label="Total Events" value={metrics.events} icon={Calendar} />
              <MetricCard label="Active Events" value={metrics.activeEvents} icon={CalendarCheck} hint="upcoming or today" />
              <MetricCard label="Photos Uploaded" value={dash(metrics.photos)} icon={ImageIcon} hint="per-event totals soon" />
              <MetricCard label="Guests Matched" value={dash(metrics.guests)} icon={Users} hint="aggregate soon" />
              <MetricCard label="Downloads" value={dash(metrics.downloads)} icon={Download} hint="aggregate soon" />
              <MetricCard label="Storage Used" value={dash(metrics.storageUsedMb)} icon={HardDrive} hint="aggregate soon" />
            </>
          )}
        </StatGrid>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <DashboardSection title="Recent Events" action={{ label: 'All events', href: '/events' }} className="lg:col-span-2">
          {isLoading ? null : recent.length ? (
            <ul className="divide-y">
              {recent.map((e) => (
                <li key={e.id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{e.title}</p>
                    <p className="text-xs text-muted-foreground">{formatDate(e.event_date)}</p>
                  </div>
                  <EventStatusBadge status={deriveStatus(e.event_date)} />
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon={Calendar} title="No events yet" description="Create your first event to get started." action={<EventFormDialog />} />
          )}
        </DashboardSection>

        <div className="space-y-6">
          <DashboardSection title="Upload Queue">
            <div className="flex items-center gap-3 py-2 text-sm text-muted-foreground">
              <UploadCloud className="h-5 w-5" aria-hidden />
              <span>No active uploads. Open an event to upload photos.</span>
            </div>
          </DashboardSection>
          <DashboardSection title="Folder Watch">
            <div className="flex items-center gap-3 py-2 text-sm text-muted-foreground">
              <FolderSync className="h-5 w-5" aria-hidden />
              <span>Folder watch &amp; the desktop agent are configured by your studio admin.</span>
            </div>
          </DashboardSection>
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Quick Actions</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {QUICK_ACTIONS.map((a) => <QuickActionCard key={a.label} {...a} />)}
        </div>
      </div>
    </div>
  );
}
