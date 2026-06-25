'use client';

import { useEvents } from '@/lib/hooks/events';
import { deriveStatus } from '@/lib/event-status';

export interface StudioMetrics {
  events: number;
  activeEvents: number;
  // Placeholders: no studio-scoped aggregate endpoints yet. Wire to a future
  // GET /events/summary without touching the dashboard UI.
  photos: number | null;
  guests: number | null;
  downloads: number | null;
  storageUsedMb: number | null;
}

export function useStudioMetrics() {
  const events = useEvents();
  const list = events.data ?? [];
  const metrics: StudioMetrics = {
    events: list.length,
    activeEvents: list.filter((e) => deriveStatus(e.event_date) !== 'past').length,
    photos: null,
    guests: null,
    downloads: null,
    storageUsedMb: null,
  };
  return {
    metrics,
    events: list,
    isLoading: events.isLoading,
    isError: events.isError,
    refetch: events.refetch,
  };
}
