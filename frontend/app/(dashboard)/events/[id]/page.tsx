'use client';

/* eslint-disable @next/next/no-img-element -- presigned S3 thumbnails; url rotates. */
import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { ArrowLeft, ImageOff } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ErrorState, EmptyState } from '@/components/feedback/states';
import { DashboardSection } from '@/components/dashboard/dashboard-section';
import { EventWorkspaceHeader } from '@/components/events/event-workspace-header';
import { EventStatsGrid } from '@/components/events/event-stats-grid';
import { QRCard } from '@/components/events/qr-card';
import { UploadDropzone } from '@/components/photos/upload-dropzone';
import { UploadToolbar } from '@/components/photos/upload-toolbar';
import { UploadQueue } from '@/components/photos/upload-queue';
import { ProcessingBadge } from '@/components/photos/processing-badge';
import { useEvent, useDeleteEvent } from '@/lib/hooks/events';
import { useEventPhotos, photoKeys } from '@/lib/hooks/photos';
import { useUploadQueue } from '@/lib/hooks/use-upload-queue';
import { guestUrl } from '@/lib/format';

export default function EventWorkspacePage() {
  const params = useParams();
  const id = Number(params.id);
  const router = useRouter();
  const qc = useQueryClient();

  const event = useEvent(id);
  const photos = useEventPhotos(id);
  const del = useDeleteEvent();
  const queue = useUploadQueue(id, {
    onUploaded: () => void qc.invalidateQueries({ queryKey: photoKeys.forEvent(id) }),
  });

  const [showQr, setShowQr] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (event.isError) {
    return (
      <div className="mx-auto max-w-5xl">
        <ErrorState title="Event not found" description="It may have been deleted." onRetry={() => event.refetch()} />
      </div>
    );
  }

  const photoList = photos.data ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <Link href="/events" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Back to events
      </Link>

      {/* Header */}
      {event.isLoading || !event.data ? (
        <Skeleton className="h-24 w-full rounded-xl" />
      ) : (
        <EventWorkspaceHeader event={event.data} onShowQr={() => setShowQr(true)} onDelete={() => setConfirmDelete(true)} />
      )}

      {/* Overview */}
      <EventStatsGrid photos={photoList} isLoading={photos.isLoading} />

      {/* Upload workspace */}
      <section id="upload" className="space-y-4">
        <h2 className="text-lg font-semibold">Upload photos</h2>
        <UploadDropzone onFiles={queue.add} />
        {queue.items.length > 0 && (
          <>
            <UploadToolbar
              aggregate={queue.aggregate}
              onRetryFailed={queue.retryAllFailed}
              onClearCompleted={queue.clearCompleted}
              onCancelAll={queue.cancelAll}
            />
            <UploadQueue items={queue.items} onRetry={queue.retry} onCancel={queue.cancel} onRemove={queue.remove} />
          </>
        )}
      </section>

      {/* Recent uploads + QR */}
      <div className="grid gap-6 lg:grid-cols-3">
        <DashboardSection title="Recent Uploads" className="lg:col-span-2">
          {photos.isLoading ? (
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
              {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="aspect-square rounded-lg" />)}
            </div>
          ) : photoList.length ? (
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
              {photoList.slice(0, 12).map((p) => (
                <div key={p.id} className="group relative aspect-square overflow-hidden rounded-lg border bg-muted">
                  {p.url ? (
                    <img src={p.url} alt={p.filename} className="h-full w-full object-cover" loading="lazy" />
                  ) : (
                    <div className="flex h-full items-center justify-center"><ImageOff className="h-5 w-5 text-muted-foreground" /></div>
                  )}
                  <div className="absolute bottom-1 left-1">
                    <ProcessingBadge status={p.processing_status} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState icon={ImageOff} title="No photos yet" description="Upload photos above to start AI processing." />
          )}
        </DashboardSection>

        <DashboardSection title="Guest Sharing">
          {event.data ? (
            <QRCard title={event.data.title} slug={event.data.event_slug} qrImageUrl={event.data.url} />
          ) : (
            <Skeleton className="h-72 w-full rounded-xl" />
          )}
        </DashboardSection>
      </div>

      {/* QR dialog (large preview + mobile frame) */}
      <Dialog open={showQr} onOpenChange={setShowQr}>
        <DialogContent>
          <DialogHeader><DialogTitle>Share with guests</DialogTitle></DialogHeader>
          {event.data && (
            <div className="space-y-4">
              <QRCard title={event.data.title} slug={event.data.event_slug} qrImageUrl={event.data.url} />
              <div className="mx-auto w-40 rounded-[1.5rem] border-4 border-foreground/80 p-2">
                <div className="rounded-xl bg-muted p-3 text-center">
                  <p className="text-[10px] font-medium">Guests open</p>
                  <p className="mt-1 break-all text-[9px] text-muted-foreground">{guestUrl(event.data.event_slug)}</p>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent>
          <DialogHeader><DialogTitle>Delete event?</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">
            This permanently deletes <span className="font-medium text-foreground">{event.data?.title}</span> and all its
            photos, matches and downloads. This can’t be undone.
          </p>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setConfirmDelete(false)} disabled={del.isPending}>Cancel</Button>
            <Button
              className="bg-red-600 text-white hover:bg-red-700"
              disabled={del.isPending}
              onClick={async () => { await del.mutateAsync(id); router.replace('/events'); }}
            >
              {del.isPending ? 'Deleting…' : 'Delete'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
