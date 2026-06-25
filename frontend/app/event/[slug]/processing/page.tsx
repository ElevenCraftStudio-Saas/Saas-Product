'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { GuestHeader } from '@/components/guest/guest-header';
import { MatchingTimeline, MATCH_STAGES } from '@/components/guest/matching-timeline';
import { useGuestFlow } from '@/components/guest/guest-flow-provider';
import { submitSelfie } from '@/services/guest';
import { toApiError } from '@/lib/errors';

export default function ProcessingPage() {
  const router = useRouter();
  const { slug, selfie, setMatches } = useGuestFlow();
  const [stage, setStage] = useState(0);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ran = useRef(false);

  useEffect(() => {
    if (!selfie) { router.replace(`/event/${slug}/selfie`); return; }
    if (ran.current) return;
    ran.current = true;

    // Advance the simulated stages up to the second-to-last while the single
    // match request is in flight; the result snaps to "done".
    let s = 0;
    const timer = setInterval(() => { s = Math.min(s + 1, MATCH_STAGES.length - 2); setStage(s); }, 700);

    (async () => {
      try {
        const result = await submitSelfie(slug, selfie);
        clearInterval(timer);
        setStage(MATCH_STAGES.length - 1);
        setDone(true);
        setMatches(result);
        setTimeout(() => router.replace(`/event/${slug}/gallery`), 600);
      } catch (e) {
        clearInterval(timer);
        setError(toApiError(e).message);
      }
    })();

    return () => clearInterval(timer);
  }, [selfie, slug, router, setMatches]);

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
        <div className="mx-auto w-full max-w-xs">
          <MatchingTimeline current={stage} done={done} />
        </div>
      </main>
    </>
  );
}
