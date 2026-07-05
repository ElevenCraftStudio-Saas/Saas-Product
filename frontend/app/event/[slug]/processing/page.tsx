'use client';

import { useEffect, useState, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { GuestHeader } from '@/components/guest/guest-header';
import { MatchingTimeline, MATCH_STAGES } from '@/components/guest/matching-timeline';
import { useGuestFlow } from '@/components/guest/guest-flow-provider';
import { submitSelfie } from '@/services/guest';
import { useProcessingStream } from '@/lib/hooks/use-processing-stream';

// Map backend status to timeline stage index
const STATUS_TO_STAGE: Record<string, number> = {
  starting: 0,
  validating: 0,
  consenting: 1,
  uploading: 1,
  detecting: 2,
  matching: 3,
  completed: 4,
};

export default function ProcessingPage() {
  const router = useRouter();
  const { slug, selfie, setMatches } = useGuestFlow();
  const [error, setError] = useState<string | null>(null);
  const ran = useRef(false);
  const completedHandled = useRef(false);
  const errorHandled = useRef(false);

  // Generate unique request ID for this processing session
  const requestId = useMemo(() => crypto.randomUUID(), []);

  // SSE hook for real-time updates
  const { state: streamState, error: streamError } = useProcessingStream(slug, true, requestId);

  useEffect(() => {
    if (!selfie) { router.replace(`/event/${slug}/selfie`); return; }
    if (ran.current) return;
    ran.current = true;

    // Submit selfie and start processing
    (async () => {
      try {
        await submitSelfie(slug, selfie, requestId);
        // Processing started, SSE will handle updates
      } catch (e) {
        const err = e as Error;
        setError(err.message || 'Failed to submit selfie');
      }
    })();

    return () => {};
  }, [selfie, slug, requestId, router]);

  // Handle terminal SSE events (side effects only). Visual stage is derived below.
  useEffect(() => {
    if (streamError && !errorHandled.current) {
      errorHandled.current = true;
      setError(streamError);
      return;
    }
    if (!streamState) return;

    if (streamState.status === 'completed' && !completedHandled.current) {
      completedHandled.current = true;

      // Push matches into guest-flow context
      if (streamState.photos && streamState.photos.length > 0) {
        setMatches({
          count: streamState.count || streamState.photos.length,
          photos: streamState.photos.map(p => ({
            id: p.id,
            filename: p.filename,
            url: p.url,
            download_token: p.download_token,
          })),
        });
      }

      // Navigate to gallery after short delay
      const t = setTimeout(() => router.replace(`/event/${slug}/gallery`), 800);
      return () => clearTimeout(t);
    }

    if (streamState.status === 'error' && !errorHandled.current) {
      errorHandled.current = true;
      setError(streamState.message);
    }
  }, [streamState, streamError, slug, router, setMatches]);

  // Derive timeline stage from stream status — avoids setState-in-effect cascades
  const done = streamState?.status === 'completed';
  const stage = done
    ? MATCH_STAGES.length - 1
    : streamState
      ? STATUS_TO_STAGE[streamState.status] ?? 0
      : 0;

  if (error) {
    return (
      <>
        <GuestHeader />
        <main className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
          <AlertTriangle className="h-10 w-10 text-destructive" aria-hidden />
          <p className="max-w-xs text-sm">{error}</p>
          <Button className="h-12 w-full max-w-xs" onClick={() => router.replace(`/event/${slug}/selfie`)}>
            Retake selfie
          </Button>
        </main>
      </>
    );
  }

  return (
    <>
      <GuestHeader />
      <main className="flex flex-1 flex-col justify-center py-8">
        <h1 className="mb-6 text-center text-xl font-bold">Finding your photos…</h1>
        {streamState?.message && (
          <p className="mb-4 text-center text-sm text-muted-foreground">{streamState.message}</p>
        )}
        <div className="mx-auto w-full max-w-xs">
          <MatchingTimeline current={stage} done={done} />
        </div>
      </main>
    </>
  );
}
