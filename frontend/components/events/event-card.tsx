'use client';

import Link from 'next/link';
import { Calendar } from 'lucide-react';
import { deriveStatus } from '@/lib/event-status';
import { formatDate } from '@/lib/format';
import { EventStatusBadge } from './event-status-badge';
import { EventActionMenu } from './event-action-menu';
import type { EventItem } from '@/types/models';

/** Mobile card representation of an event (shown < md). */
export function EventCard({
  event,
  onShowQr,
  onDelete,
}: {
  event: EventItem;
  onShowQr: (e: EventItem) => void;
  onDelete: (e: EventItem) => void;
}) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="flex items-start justify-between gap-2">
        <Link href={`/events/${event.id}`} className="font-medium hover:underline">{event.title}</Link>
        <EventActionMenu event={event} onShowQr={onShowQr} onDelete={onDelete} />
      </div>
      <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
        <Calendar className="h-4 w-4" aria-hidden />
        <span>{formatDate(event.event_date)}</span>
        <EventStatusBadge status={deriveStatus(event.event_date)} />
      </div>
    </div>
  );
}
