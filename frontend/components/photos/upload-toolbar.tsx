'use client';

import { RotateCcw, Trash2, X } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { formatSpeed, formatDuration } from '@/lib/format';
import type { UploadAggregate } from '@/lib/hooks/use-upload-queue';

interface Props {
  aggregate: UploadAggregate;
  onRetryFailed: () => void;
  onClearCompleted: () => void;
  onCancelAll: () => void;
}

/** Summary bar + bulk controls for the upload queue. */
export function UploadToolbar({ aggregate: a, onRetryFailed, onClearCompleted, onCancelAll }: Props) {
  const busy = a.uploading > 0 || a.queued > 0;
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm">
          <span className="font-medium">{a.done}/{a.total} uploaded</span>
          {a.failed > 0 && <span className="ml-2 text-red-600 dark:text-red-400">{a.failed} failed</span>}
          {busy && (
            <span className="ml-2 text-muted-foreground">
              · {formatSpeed(a.speedBps)} · ETA {formatDuration(a.etaSeconds)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {a.failed > 0 && (
            <Button variant="outline" size="sm" onClick={onRetryFailed}>
              <RotateCcw className="mr-1 h-4 w-4" /> Retry failed
            </Button>
          )}
          {a.done > 0 && (
            <Button variant="ghost" size="sm" onClick={onClearCompleted}>
              <Trash2 className="mr-1 h-4 w-4" /> Clear completed
            </Button>
          )}
          {busy && (
            <Button variant="ghost" size="sm" onClick={onCancelAll}>
              <X className="mr-1 h-4 w-4" /> Cancel all
            </Button>
          )}
        </div>
      </div>
      {busy && <Progress value={a.overallProgress} className="mt-3 h-2" />}
    </div>
  );
}
