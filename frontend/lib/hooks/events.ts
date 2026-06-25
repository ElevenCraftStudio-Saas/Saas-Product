'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { listEvents, getEvent, createEvent, deleteEvent } from '@/services/events';
import type { ApiError } from '@/lib/errors';
import type { EventCreateInput } from '@/types/models';

export const eventKeys = {
  all: ['events'] as const,
  detail: (id: number) => ['event', id] as const,
};

export function useEvents() {
  return useQuery({ queryKey: eventKeys.all, queryFn: listEvents });
}

export function useEvent(id: number) {
  return useQuery({ queryKey: eventKeys.detail(id), queryFn: () => getEvent(id), enabled: Number.isFinite(id) });
}

export function useCreateEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: EventCreateInput) => createEvent(input),
    onSuccess: () => {
      toast.success('Event created');
      void qc.invalidateQueries({ queryKey: eventKeys.all });
    },
    onError: (e: ApiError) => toast.error(e.message || 'Failed to create event'),
  });
}

export function useDeleteEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteEvent(id),
    onSuccess: () => {
      toast.success('Event deleted');
      void qc.invalidateQueries({ queryKey: eventKeys.all });
    },
    onError: (e: ApiError) => toast.error(e.message || 'Failed to delete event'),
  });
}
