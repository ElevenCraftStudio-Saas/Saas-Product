'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { FolderSync, Plus, Trash2, RefreshCw, Loader2, CheckCircle2, Square } from 'lucide-react';
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

  const { data: watches, isLoading } = useQuery<WatchStatus[]>({
    queryKey: ['watch-folders', eventId],
    queryFn: async () => (await api.get(`/events/${eventId}/watch-folders`)).data,
    refetchInterval: 5000, // live status + photo counts
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['watch-folders', eventId] });
    qc.invalidateQueries({ queryKey: ['photos', eventId] });
  };

  const add = useMutation({
    mutationFn: async (folder_path: string) =>
      (await api.post(`/events/${eventId}/watch-folders`, { folder_path })).data,
    onSuccess: () => { toast.success('Folder added'); setPath(''); invalidate(); },
    onError: (e: unknown) =>
      toast.error((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to add folder'),
  });

  const remove = useMutation({
    mutationFn: async (watchId: number) => api.delete(`/events/${eventId}/watch-folders/${watchId}`),
    onSuccess: () => { toast.success('Folder removed'); invalidate(); },
    onError: () => toast.error('Failed to remove'),
  });

  const rescan = useMutation({
    mutationFn: async (watchId: number) =>
      (await api.post(`/events/${eventId}/watch-folders/${watchId}/rescan`)).data,
    onSuccess: (d: { uploaded: number }) => { toast.success(`Rescan: ${d.uploaded} new file(s)`); invalidate(); },
    onError: () => toast.error('Rescan failed'),
  });

  const rescanAll = useMutation({
    mutationFn: async () => (await api.post(`/events/${eventId}/rescan-all`)).data,
    onSuccess: (d: { uploaded: number }) => { toast.success(`Rescan all: ${d.uploaded} new file(s)`); invalidate(); },
    onError: () => toast.error('Rescan failed'),
  });

  return (
    <Card className="lg:col-span-3">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center space-x-2">
            <FolderSync className="w-5 h-5" />
            <span>Auto Folder Upload</span>
          </span>
          {!!watches?.length && (
            <Button size="sm" variant="outline" onClick={() => rescanAll.mutate()} disabled={rescanAll.isPending}>
              {rescanAll.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              <span className="ml-1">Rescan all</span>
            </Button>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-slate-500">
          Add one or more folders on the machine running the backend (e.g. one per
          photographer). New photos in any folder are uploaded &amp; processed automatically.
          For cameramen on other machines, use the desktop agent instead.
        </p>

        {/* Add folder */}
        <div className="flex gap-2">
          <Input
            placeholder="D:\Wedding Photos\Cameraman 1"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && path) add.mutate(path); }}
          />
          <Button onClick={() => add.mutate(path)} disabled={!path || add.isPending}>
            {add.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            <span className="ml-1">Add Folder</span>
          </Button>
        </div>

        {/* Watched folders list */}
        {isLoading ? (
          <Loader2 className="w-5 h-5 animate-spin" />
        ) : !watches?.length ? (
          <p className="text-sm text-slate-400">No folders watched yet.</p>
        ) : (
          <div className="divide-y border rounded-lg">
            {watches.map((w) => (
              <div key={w.id} className="flex items-center justify-between gap-3 p-3">
                <div className="min-w-0 space-y-1">
                  <p className="font-mono text-sm break-all">{w.folder_path}</p>
                  <div className="flex items-center gap-3 text-xs text-slate-500">
                    <span className="flex items-center gap-1">
                      {w.watching ? (
                        <><CheckCircle2 className="w-3.5 h-3.5 text-green-600" /> Watching</>
                      ) : (
                        <><Square className="w-3.5 h-3.5 text-slate-400" /> Stopped</>
                      )}
                    </span>
                    <span>Photos: {w.photo_count}</span>
                    <span>Last scan: {w.last_scan_at ? new Date(w.last_scan_at).toLocaleTimeString() : '—'}</span>
                  </div>
                </div>
                <div className="flex gap-1 shrink-0">
                  <Button size="icon" variant="ghost" onClick={() => rescan.mutate(w.id)} disabled={rescan.isPending} title="Rescan">
                    <RefreshCw className="w-4 h-4" />
                  </Button>
                  <Button
                    size="icon" variant="ghost"
                    className="text-red-500 hover:text-red-600 hover:bg-red-50"
                    onClick={() => remove.mutate(w.id)} disabled={remove.isPending} title="Remove"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
