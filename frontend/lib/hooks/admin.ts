'use client';

import { useQuery } from '@tanstack/react-query';
import { getAnalytics, listUsers, getActivity } from '@/services/admin';

export const adminKeys = {
  analytics: ['admin', 'analytics'] as const,
  users: ['admin', 'users'] as const,
  activity: (limit: number) => ['admin', 'activity', limit] as const,
};

export function useAnalytics() {
  return useQuery({ queryKey: adminKeys.analytics, queryFn: getAnalytics });
}

export function useAdminUsers() {
  return useQuery({ queryKey: adminKeys.users, queryFn: listUsers });
}

export function useActivity(limit = 100) {
  return useQuery({ queryKey: adminKeys.activity(limit), queryFn: () => getActivity(limit) });
}

export interface DashboardMetrics {
  events: number;
  photos: number;
  guests: number;
  downloads: number;
  storageUsedMb: number;
}

/**
 * Composed dashboard metrics. KPI cards consume THIS hook, never the raw
 * endpoints — so the data source can change (e.g. a future dedicated
 * /admin/dashboard endpoint) without touching any UI component.
 *
 * Today: events/photos/guests/downloads from /admin/analytics; storage summed
 * from /admin/users (no storage field on the analytics summary yet).
 */
export function useDashboardMetrics() {
  const analytics = useAnalytics();
  const users = useAdminUsers();

  const storageUsedMb = (users.data ?? []).reduce((sum, u) => sum + (u.storage_used_mb ?? 0), 0);

  const metrics: DashboardMetrics | null = analytics.data
    ? {
        events: analytics.data.total_events,
        photos: analytics.data.total_photos,
        guests: analytics.data.total_consents,
        downloads: analytics.data.total_downloads,
        storageUsedMb,
      }
    : null;

  return {
    metrics,
    perEvent: analytics.data?.per_event ?? [],
    isLoading: analytics.isLoading || users.isLoading,
    isError: analytics.isError || users.isError,
    refetch: () => {
      void analytics.refetch();
      void users.refetch();
    },
  };
}
