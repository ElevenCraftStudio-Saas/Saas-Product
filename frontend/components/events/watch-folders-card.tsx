'use client';

import { useState } from 'react';
import { FolderSearch, FolderX, RefreshCw, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useWatchFolders, useAddWatchFolder, useRemoveWatchFolder, useRescan } from '@/lib/hooks/watch-folders';
import { cn } from '@/lib/utils';
import type { FolderWatch } from '@/types/models';

/** Auto-import folders for an event: list, add, remove, rescan.
 *  Folders live on the SERVER's filesystem — the hint below points studios
 *  with local folders at the desktop agent instead. */
export function WatchFoldersCard({ eventId }: { eventId: number }) {
  const watches = useWatchFolders(eventId);
  const add = useAddWatchFolder(eventId);
  const remove = useRemoveWatchFolder(eventId);
  const rescan = useRescan(eventId);
  const [path, setPath] = useState('');

  const list = watches.data ?? [];

  const onAdd = () => {
    const trimmed = path.trim();
    if (!trimmed) return;
    add.mutate(trimmed, { onSuccess: () => setPath('') });
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Auto-import folders</CardTitle>
        {list.length > 0 && (
          <Button size="sm" variant="outline" onClick={() => rescan.mutate(undefined)} disabled={rescan.isPending}>
            {rescan.isPending ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-1 h-4 w-4" />}
            Rescan all
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {watches.isLoading ? (
          <Skeleton className="h-14 w-full rounded-lg" />
        ) : list.length === 0 ? (
          <p className="text-sm text-muted-foreground">No folders watched yet. Add a server folder below to auto-import new photos.</p>
        ) : (
          <ul className="space-y-2">
            {list.map((w) => (
              <WatchRow
                key={w.id}
                watch={w}
                onRescan={() => rescan.mutate(w.id)}
                onRemove={() => remove.mutate(w.id)}
                busy={rescan.isPending || remove.isPending}
              />
            ))}
          </ul>
        )}

        <div className="flex flex-wrap gap-2">
          <input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onAdd()}
            placeholder="Absolute folder path on the server"
            aria-label="Folder path"
            className="h-9 min-w-0 flex-1 basis-56 rounded-md border border-input bg-background px-2 text-sm"
          />
          <Button size="sm" onClick={onAdd} disabled={!path.trim() || add.isPending}>
            {add.isPending ? 'Adding…' : 'Add'}
          </Button>
        </div>

        <p className="text-xs text-muted-foreground">
          Folders are watched on the server running WedFind. For folders on your own computer, use the desktop agent.
        </p>
      </CardContent>
    </Card>
  );
}

function WatchRow({
  watch: w,
  onRescan,
  onRemove,
  busy,
}: {
  watch: FolderWatch;
  onRescan: () => void;
  onRemove: () => void;
  busy: boolean;
}) {
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border p-3">
      <span
        className={cn('h-2 w-2 shrink-0 rounded-full', w.watching ? 'bg-green-500' : 'bg-muted-foreground/40')}
        aria-hidden
      />
      <div className="min-w-0 flex-1">
        <p className="truncate font-mono text-xs" title={w.folder_path}>{w.folder_path}</p>
        <p className="text-xs text-muted-foreground">
          {w.watching ? 'Watching' : 'Stopped'} · {w.photo_count} photo{w.photo_count === 1 ? '' : 's'}
          {w.last_scan_at ? ` · scanned ${new Date(w.last_scan_at).toLocaleString()}` : ''}
        </p>
      </div>
      <div className="flex gap-1">
        <Button size="sm" variant="ghost" onClick={onRescan} disabled={busy} aria-label={`Rescan ${w.folder_path}`}>
          <FolderSearch className="h-4 w-4" />
        </Button>
        <Button size="sm" variant="ghost" onClick={onRemove} disabled={busy} aria-label={`Remove ${w.folder_path}`}>
          <FolderX className="h-4 w-4 text-destructive" />
        </Button>
      </div>
    </li>
  );
}
