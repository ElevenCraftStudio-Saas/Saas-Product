'use client';

import { Pencil, Trash2, Link2, QrCode, Share2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { EventStatusBadge } from '@/components/events/event-status-badge';
import { deriveStatus } from '@/lib/event-status';
import { formatDate, guestUrl } from '@/lib/format';
import type { EventItem } from '@/types/models';

export function EventWorkspaceHeader({
  event,
  onShowQr,
  onDelete,
}: {
  event: EventItem;
  onShowQr: () => void;
  onDelete: () => void;
}) {
  const url = guestUrl(event.event_slug);
  const copy = async () => { await navigator.clipboard.writeText(url); toast.success('Guest link copied'); };
  const share = async () => {
    if (typeof navigator !== 'undefined' && navigator.share) {
      try { await navigator.share({ title: event.title, url }); } catch { /* dismissed */ }
    } else {
      void copy();
    }
  };

  return (
    <div className="flex flex-col gap-4 border-b pb-6 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="truncate text-2xl font-bold tracking-tight">{event.title}</h1>
          <EventStatusBadge status={deriveStatus(event.event_date)} />
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {formatDate(event.event_date)}
          {event.description ? ` · ${event.description}` : ''}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" onClick={copy}><Link2 className="mr-1 h-4 w-4" /> Copy link</Button>
        <Button variant="outline" size="sm" onClick={onShowQr}><QrCode className="mr-1 h-4 w-4" /> QR</Button>
        <Button variant="outline" size="sm" onClick={share}><Share2 className="mr-1 h-4 w-4" /> Share</Button>
        <Button variant="outline" size="sm" disabled title="Editing requires a backend update (PATCH /events)">
          <Pencil className="mr-1 h-4 w-4" /> Edit
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
          onClick={onDelete}
        >
          <Trash2 className="mr-1 h-4 w-4" /> Delete
        </Button>
      </div>
    </div>
  );
}
