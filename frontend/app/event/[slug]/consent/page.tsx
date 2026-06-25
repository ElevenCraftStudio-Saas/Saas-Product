'use client';

import { useRouter } from 'next/navigation';
import { GuestHeader } from '@/components/guest/guest-header';
import { ConsentCard } from '@/components/guest/consent-card';
import { useGuestFlow } from '@/components/guest/guest-flow-provider';

export default function ConsentPage() {
  const router = useRouter();
  const { slug, event, acceptConsent } = useGuestFlow();

  return (
    <>
      <GuestHeader title={event?.title} />
      <main className="flex-1 py-4">
        <h1 className="mb-1 text-xl font-bold">Before we start</h1>
        <p className="mb-6 text-sm text-muted-foreground">A quick consent for face matching.</p>
        <ConsentCard
          onAccept={() => {
            acceptConsent();
            router.push(`/event/${slug}/selfie`);
          }}
        />
      </main>
    </>
  );
}
