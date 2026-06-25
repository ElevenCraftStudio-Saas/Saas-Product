'use client';

import { useParams } from 'next/navigation';
import { GuestFlowProvider } from '@/components/guest/guest-flow-provider';

/** The guest flow lives under one layout so the GuestFlowProvider (consent,
 *  selfie, matches) persists across client navigation between the steps. */
export default function GuestLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const slug = String(params.slug);
  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/40">
      <GuestFlowProvider slug={slug}>
        <div className="mx-auto flex min-h-screen max-w-md flex-col px-4">{children}</div>
      </GuestFlowProvider>
    </div>
  );
}
