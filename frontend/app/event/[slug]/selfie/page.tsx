'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { GuestHeader } from '@/components/guest/guest-header';
import { CameraView } from '@/components/guest/camera-view';
import { SelfiePreview } from '@/components/guest/selfie-preview';
import { useGuestFlow } from '@/components/guest/guest-flow-provider';

export default function SelfiePage() {
  const router = useRouter();
  const { slug, event, consent, setSelfie } = useGuestFlow();
  const [captured, setCaptured] = useState<Blob | null>(null);

  useEffect(() => {
    if (!consent) router.replace(`/event/${slug}/consent`);
  }, [consent, slug, router]);
  if (!consent) return null;

  return (
    <>
      <GuestHeader title={event?.title} />
      <main className="flex flex-1 flex-col justify-center py-4">
        <h1 className="mb-1 text-center text-xl font-bold">{captured ? 'Looking good?' : 'Take a selfie'}</h1>
        <p className="mb-6 text-center text-sm text-muted-foreground">
          {captured ? 'Use this photo or retake it.' : 'Face the camera in good light.'}
        </p>
        {captured ? (
          <SelfiePreview
            blob={captured}
            onRetake={() => setCaptured(null)}
            onContinue={() => { setSelfie(captured); router.push(`/event/${slug}/processing`); }}
          />
        ) : (
          <CameraView onCapture={setCaptured} />
        )}
      </main>
    </>
  );
}
