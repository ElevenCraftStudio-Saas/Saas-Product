'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  getWatchFolders,
  addWatchFolder,
  removeWatchFolder,
  rescanFolder,
  rescanAllFolders,
} from '@/services/events';
import { photoKeys } from '@/lib/hooks/photos';
import type { ApiError } from '@/lib/errors';

export const watchFolderKeys = {
  forEvent: (eventId: number) => ['watch-folders', eventId] as const,
};

export function useWatchFolders(eventId: number) {
  return useQuery({
    queryKey: watchFolderKeys.forEvent(eventId),
    queryFn: () => getWatchFolders(eventId),
    enabled: Number.isFinite(eventId),
  });
}

export function useAddWatchFolder(eventId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (folderPath: string) => addWatchFolder(eventId, folderPath),
    onSuccess: () => {
      toast.success('Folder added — watching for new photos');
      void qc.invalidateQueries({ queryKey: watchFolderKeys.forEvent(eventId) });
    },
    onError: (e: ApiError) => toast.error(e.message || 'Failed to add folder'),
  });
}

export function useRemoveWatchFolder(eventId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (watchId: number) => removeWatchFolder(eventId, watchId),
    onSuccess: () => {
      toast.success('Folder removed');
      void qc.invalidateQueries({ queryKey: watchFolderKeys.forEvent(eventId) });
    },
    onError: (e: ApiError) => toast.error(e.message || 'Failed to remove folder'),
  });
}

/** Rescan one folder or (watchId omitted) all folders for the event. */
export function useRescan(eventId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (watchId?: number) =>
      watchId === undefined ? rescanAllFolders(eventId) : rescanFolder(eventId, watchId),
    onSuccess: (res) => {
      toast.success(res.uploaded ? `${res.uploaded} photo${res.uploaded === 1 ? '' : 's'} imported` : 'No new photos found');
      void qc.invalidateQueries({ queryKey: watchFolderKeys.forEvent(eventId) });
      void qc.invalidateQueries({ queryKey: photoKeys.forEvent(eventId) });
    },
    onError: (e: ApiError) => toast.error(e.message || 'Rescan failed'),
  });
}
