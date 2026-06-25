'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Camera, Sparkles, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { PageSpinner } from '@/components/feedback/states';
import { GuestHeader } from '@/components/guest/guest-header';
import { useGuestFlow } from '@/components/guest/guest-flow-provider';
import { formatDate } from '@/lib/format';

export default function GuestLandingPage() {
  const router = useRouter();
  const { slug, event, isLoading, isError } = useGuestFlow();

  useEffect(() => {
    if (isError) router.replace(`/event/${slug}/not-found`);
  }, [isError, slug, router]);

  if (isLoading) return <div className="flex flex-1 items-center justify-center"><PageSpinner /></div>;
  if (!event) return null;

  return (
    <>
      <GuestHeader />
      <main className="flex flex-1 flex-col items-center justify-center gap-6 py-10 text-center">
        <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <Camera className="h-8 w-8" aria-hidden />
        </span>
        <div>
          <h1 className="text-2xl font-bold">{event.title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{formatDate(event.event_date)}</p>
          {event.description ? <p className="mt-3 max-w-xs text-sm text-muted-foreground">{event.description}</p> : null}
        </div>
        <p className="flex items-center gap-1 text-sm text-muted-foreground">
          <Sparkles className="h-4 w-4" aria-hidden /> Find your photos with a quick selfie
        </p>
        <Button className="h-14 w-full max-w-xs rounded-full text-base" onClick={() => router.push(`/event/${slug}/consent`)}>
          Find My Photos <ArrowRight className="ml-2 h-5 w-5" />
        </Button>
      </main>
      <footer className="py-4 text-center text-xs text-muted-foreground">Powered by WedFind AI · No account needed</footer>
    </>
  );
}
