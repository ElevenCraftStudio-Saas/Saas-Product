'use client';

import { useQuery } from '@tanstack/react-query';
import { listEventPhotos } from '@/services/photos';
import type { PhotoItem } from '@/types/models';

export const photoKeys = {
  forEvent: (eventId: number) => ['event-photos', eventId] as const,
};

/** Photos for an event. Polls every 4s WHILE any photo is still
 *  pending/processing, then stops — no idle refetch storm. */
export function useEventPhotos(eventId: number) {
  return useQuery({
    queryKey: photoKeys.forEvent(eventId),
    queryFn: () => listEventPhotos(eventId),
    enabled: Number.isFinite(eventId),
    refetchInterval: (query) => {
      const data = query.state.data as PhotoItem[] | undefined;
      const busy = data?.some((p) => p.processing_status === 'pending' || p.processing_status === 'processing');
      return busy ? 4000 : false;
    },
  });
}
