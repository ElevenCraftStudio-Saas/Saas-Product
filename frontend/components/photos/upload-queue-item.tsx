'use client';

/* eslint-disable @next/next/no-img-element -- local object URL preview, no remote optimization. */
import { RotateCcw, X, Trash2, CheckCircle2, AlertCircle, Image as ImageIcon } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { formatBytes, formatSpeed } from '@/lib/format';
import type { UploadItem } from '@/lib/hooks/use-upload-queue';

interface Props {
  item: UploadItem;
  onRetry: (id: string) => void;
  onCancel: (id: string) => void;
  onRemove: (id: string) => void;
}

export function UploadQueueItem({ item, onRetry, onCancel, onRemove }: Props) {
  const inFlight = item.status === 'uploading' || item.status === 'queued';
  return (
    <li className="flex items-center gap-3 rounded-xl border bg-card p-3">
      <span className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-muted">
        {item.previewUrl ? (
          <img src={item.previewUrl} alt="" className="h-full w-full object-cover" />
        ) : (
          <ImageIcon className="h-5 w-5 text-muted-foreground" aria-hidden />
        )}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <p className="truncate text-sm font-medium">{item.name}</p>
          <span className="shrink-0 text-xs text-muted-foreground">{formatBytes(item.size)}</span>
        </div>

        {item.status === 'uploading' && (
          <div className="mt-1.5">
            <Progress value={item.progress} className="h-1.5" />
            <p className="mt-1 text-xs text-muted-foreground">{item.progress}% · {formatSpeed(item.speedBps)}</p>
          </div>
        )}
        {item.status === 'queued' && <p className="mt-1 text-xs text-muted-foreground">Queued…</p>}
        {item.status === 'done' && (
          <p className="mt-1 flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="h-3.5 w-3.5" /> Uploaded
          </p>
        )}
        {item.status === 'canceled' && <p className="mt-1 text-xs text-muted-foreground">Canceled</p>}
        {item.status === 'error' && (
          <p className="mt-1 flex items-center gap-1 truncate text-xs text-red-600 dark:text-red-400">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {item.error || 'Upload failed'}
          </p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-1">
        {item.status === 'error' && (
          <button onClick={() => onRetry(item.id)} aria-label="Retry" className="rounded-lg p-2 text-muted-foreground hover:bg-accent">
            <RotateCcw className="h-4 w-4" />
          </button>
        )}
        {inFlight ? (
          <button onClick={() => onCancel(item.id)} aria-label="Cancel" className="rounded-lg p-2 text-muted-foreground hover:bg-accent">
            <X className="h-4 w-4" />
          </button>
        ) : (
          <button onClick={() => onRemove(item.id)} aria-label="Remove" className={cn('rounded-lg p-2 text-muted-foreground hover:bg-accent')}>
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>
    </li>
  );
}
