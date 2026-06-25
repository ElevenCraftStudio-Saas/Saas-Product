'use client';

import Link from 'next/link';
import { deriveStatus } from '@/lib/event-status';
import { formatDate } from '@/lib/format';
import { EventStatusBadge } from './event-status-badge';
import { EventActionMenu } from './event-action-menu';
import type { EventItem } from '@/types/models';

interface Props {
  events: EventItem[];
  onShowQr: (e: EventItem) => void;
  onDelete: (e: EventItem) => void;
}

/** Desktop table. Photos/Guests/Downloads show "—": the list endpoint returns
 *  no per-event counts (see report for the optional backend improvement). */
export function EventTable({ events, onShowQr, onDelete }: Props) {
  return (
    <div className="hidden overflow-x-auto rounded-xl border bg-card md:block">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="px-4 py-3 font-medium">Event</th>
            <th className="px-4 py-3 font-medium">Date</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium" title="Per-event counts not yet provided by the list API">Photos</th>
            <th className="px-4 py-3 font-medium">Guests</th>
            <th className="px-4 py-3 font-medium">Downloads</th>
            <th className="px-4 py-3 text-right font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e) => (
            <tr key={e.id} className="border-b last:border-0 hover:bg-muted/40">
              <td className="px-4 py-3">
                <Link href={`/events/${e.id}`} className="font-medium hover:underline">{e.title}</Link>
              </td>
              <td className="px-4 py-3 text-muted-foreground">{formatDate(e.event_date)}</td>
              <td className="px-4 py-3"><EventStatusBadge status={deriveStatus(e.event_date)} /></td>
              <td className="px-4 py-3 text-muted-foreground">—</td>
              <td className="px-4 py-3 text-muted-foreground">—</td>
              <td className="px-4 py-3 text-muted-foreground">—</td>
              <td className="px-4 py-3">
                <div className="flex justify-end">
                  <EventActionMenu event={e} onShowQr={onShowQr} onDelete={onDelete} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
