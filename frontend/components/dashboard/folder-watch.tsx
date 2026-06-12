'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { FolderSync, Play, Square, RefreshCw, Loader2, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';

interface WatchStatus {
  id: number;
  event_id: number;
  folder_path: string;
  enabled: boolean;
  watching: boolean;
  last_scan_at: string | null;
  photo_count: number;
}

export function FolderWatch({ eventId }: { eventId: string | number }) {
  const qc = useQueryClient();
  const [path, setPath] = useState('');

  const { data: watch, isLoading } = useQuery<WatchStatus | null>({
    queryKey: ['watch-folder', eventId],
    queryFn: async () => {
      try {
        return (await api.get(`/events/${eventId}/watch-folder`)).data;
      } catch (e: unknown) {
        if ((e as { response?: { status?: number } }).response?.status === 404) return null;
        throw e;
      }
    },
    refetchInterval: 5000, // live status + photo count
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['watch-folder', eventId] });
    qc.invalidateQueries({ queryKey: ['photos', eventId] });
  };

  const start = useMutation({
    mutationFn: async (folder_path: string) =>
      (await api.post(`/events/${eventId}/watch-folder`, { folder_path })).data,
    onSuccess: () => { toast.success('Watching folder'); setPath(''); invalidate(); },
    onError: (e: unknown) =>
      toast.error((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to start watching'),
  });

  const stop = useMutation({
    mutationFn: async () => api.delete(`/events/${eventId}/watch-folder`),
    onSuccess: () => { toast.success('Stopped watching'); invalidate(); },
    onError: () => toast.error('Failed to stop'),
  });

  const rescan = useMutation({
    mutationFn: async () => (await api.post(`/events/${eventId}/rescan`)).data,
    onSuccess: (d: { uploaded: number }) => { toast.success(`Rescan: ${d.uploaded} new file(s)`); invalidate(); },
    onError: () => toast.error('Rescan failed'),
  });

  return (
    <Card className="lg:col-span-3">
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <FolderSync className="w-5 h-5" />
          <span>Auto Folder Upload</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <Loader2 className="w-5 h-5 animate-spin" />
        ) : watch ? (
          <div className="space-y-3">
            <div className="text-sm">
              <span className="text-slate-500">Current Folder:</span>{' '}
              <span className="font-mono break-all">{watch.folder_path}</span>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <span className="flex items-center gap-1">
                {watch.watching ? (
                  <><CheckCircle2 className="w-4 h-4 text-green-600" /> <b>Watching</b></>
                ) : (
                  <><Square className="w-4 h-4 text-slate-400" /> Stopped</>
                )}
              </span>
              <span className="text-slate-500">Photos: {watch.photo_count}</span>
              <span className="text-slate-400">
                Last scan: {watch.last_scan_at ? new Date(watch.last_scan_at).toLocaleString() : '—'}
              </span>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => rescan.mutate()} disabled={rescan.isPending}>
                {rescan.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                <span className="ml-1">Rescan Folder</span>
              </Button>
              <Button size="sm" variant="destructive" onClick={() => stop.mutate()} disabled={stop.isPending}>
                <Square className="w-4 h-4 mr-1" /> Stop Watching
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-slate-500">
              Paste the full local folder path on the machine running the backend
              (e.g. <span className="font-mono">D:\Wedding Photos\Event1</span>). New photos are
              uploaded and processed automatically.
            </p>
            <div className="flex gap-2">
              <Input
                placeholder="D:\Wedding Photos\Event1"
                value={path}
                onChange={(e) => setPath(e.target.value)}
              />
              <Button onClick={() => start.mutate(path)} disabled={!path || start.isPending}>
                {start.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                <span className="ml-1">Start Watching</span>
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
