'use client';

import { UploadQueueItem } from './upload-queue-item';
import type { UploadItem } from '@/lib/hooks/use-upload-queue';

export function UploadQueue({
  items,
  onRetry,
  onCancel,
  onRemove,
}: {
  items: UploadItem[];
  onRetry: (id: string) => void;
  onCancel: (id: string) => void;
  onRemove: (id: string) => void;
}) {
  if (!items.length) return null;
  return (
    <ul className="space-y-2" aria-label="Upload queue">
      {items.map((item) => (
        <UploadQueueItem key={item.id} item={item} onRetry={onRetry} onCancel={onCancel} onRemove={onRemove} />
      ))}
    </ul>
  );
}
