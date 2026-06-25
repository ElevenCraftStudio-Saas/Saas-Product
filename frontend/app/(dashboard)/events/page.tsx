'use client';

import { useMemo, useState } from 'react';
import { Calendar } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { SearchToolbar } from '@/components/common/search-toolbar';
import { PaginationBar } from '@/components/common/pagination-bar';
import { EventTable } from '@/components/events/event-table';
import { EventCard } from '@/components/events/event-card';
import { EventFormDialog } from '@/components/events/event-form-dialog';
import { QRCard } from '@/components/events/qr-card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState, ErrorState } from '@/components/feedback/states';
import { useEvents, useDeleteEvent } from '@/lib/hooks/events';
import { deriveStatus, type EventStatus } from '@/lib/event-status';
import type { EventItem } from '@/types/models';

type SortKey = 'date_desc' | 'date_asc' | 'name';
const PAGE_SIZE = 10;

const SELECT = 'h-9 rounded-md border border-input bg-background px-2 text-sm';

export default function EventsPage() {
  const { data, isLoading, isError, refetch } = useEvents();
  const del = useDeleteEvent();

  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<SortKey>('date_desc');
  const [status, setStatus] = useState<EventStatus | 'all'>('all');
  const [page, setPage] = useState(1);
  const [qrEvent, setQrEvent] = useState<EventItem | null>(null);
  const [toDelete, setToDelete] = useState<EventItem | null>(null);

  const filtered = useMemo(() => {
    let list = data ?? [];
    const q = search.trim().toLowerCase();
    if (q) list = list.filter((e) => e.title.toLowerCase().includes(q));
    if (status !== 'all') list = list.filter((e) => deriveStatus(e.event_date) === status);
    const sorted = [...list].sort((a, b) => {
      if (sort === 'name') return a.title.localeCompare(b.title);
      const da = new Date(a.event_date).getTime();
      const db = new Date(b.event_date).getTime();
      return sort === 'date_asc' ? da - db : db - da;
    });
    return sorted;
  }, [data, search, status, sort]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pageCount);
  const paged = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);

  // Reset to page 1 whenever filters change the result set size meaningfully.
  function resetAndSet<T>(setter: (v: T) => void) {
    return (v: T) => { setter(v); setPage(1); };
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader
        title="Events"
        description="Create and manage your wedding galleries."
        actions={<EventFormDialog />}
      />

      <SearchToolbar value={search} onChange={resetAndSet(setSearch)} placeholder="Search events…">
        <select className={SELECT} value={status} onChange={(e) => resetAndSet(setStatus)(e.target.value as EventStatus | 'all')} aria-label="Filter by status">
          <option value="all">All statuses</option>
          <option value="upcoming">Upcoming</option>
          <option value="active">Active</option>
          <option value="past">Past</option>
        </select>
        <select className={SELECT} value={sort} onChange={(e) => setSort(e.target.value as SortKey)} aria-label="Sort">
          <option value="date_desc">Newest first</option>
          <option value="date_asc">Oldest first</option>
          <option value="name">Name (A–Z)</option>
        </select>
      </SearchToolbar>

      {isError ? (
        <ErrorState description="Couldn’t load your events." onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-14 w-full rounded-xl" />)}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Calendar}
          title={data?.length ? 'No events match your filters' : 'No events yet'}
          description={data?.length ? 'Try a different search or status.' : 'Create your first wedding event to generate a QR and start collecting photos.'}
          action={data?.length ? undefined : <EventFormDialog />}
        />
      ) : (
        <>
          <EventTable events={paged} onShowQr={setQrEvent} onDelete={setToDelete} />
          <div className="space-y-3 md:hidden">
            {paged.map((e) => <EventCard key={e.id} event={e} onShowQr={setQrEvent} onDelete={setToDelete} />)}
          </div>
          <PaginationBar page={current} pageCount={pageCount} total={filtered.length} onPage={setPage} />
        </>
      )}

      {/* QR dialog */}
      <Dialog open={!!qrEvent} onOpenChange={(o) => !o && setQrEvent(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Guest QR code</DialogTitle>
          </DialogHeader>
          {qrEvent ? <QRCard title={qrEvent.title} slug={qrEvent.event_slug} qrImageUrl={qrEvent.url} /> : null}
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <Dialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete event?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This permanently deletes <span className="font-medium text-foreground">{toDelete?.title}</span> and all its
            photos, matches and downloads. This can’t be undone.
          </p>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setToDelete(null)} disabled={del.isPending}>Cancel</Button>
            <Button
              className="bg-red-600 text-white hover:bg-red-700"
              disabled={del.isPending}
              onClick={async () => {
                if (!toDelete) return;
                await del.mutateAsync(toDelete.id);
                setToDelete(null);
              }}
            >
              {del.isPending ? 'Deleting…' : 'Delete'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
