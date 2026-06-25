'use client';

import { createContext, useContext, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getGuestEvent } from '@/services/guest';
import type { GuestEvent, SelfieMatchResult } from '@/types/models';

interface GuestFlowValue {
  slug: string;
  event: GuestEvent | undefined;
  isLoading: boolean;
  isError: boolean;
  consent: boolean;
  acceptConsent: () => void;
  selfie: Blob | null;
  setSelfie: (b: Blob | null) => void;
  matches: SelfieMatchResult | null;
  setMatches: (m: SelfieMatchResult | null) => void;
  reset: () => void;
}

const GuestFlowContext = createContext<GuestFlowValue | undefined>(undefined);

/** Holds the guest journey state. Mounted in the [slug] layout so it persists
 *  across client navigation between the flow's sibling routes. */
export function GuestFlowProvider({ slug, children }: { slug: string; children: React.ReactNode }) {
  const q = useQuery({ queryKey: ['guest-event', slug], queryFn: () => getGuestEvent(slug), enabled: !!slug, retry: false });
  const [consent, setConsent] = useState(false);
  const [selfie, setSelfie] = useState<Blob | null>(null);
  const [matches, setMatches] = useState<SelfieMatchResult | null>(null);

  const value: GuestFlowValue = {
    slug,
    event: q.data,
    isLoading: q.isLoading,
    isError: q.isError,
    consent,
    acceptConsent: () => setConsent(true),
    selfie,
    setSelfie,
    matches,
    setMatches,
    reset: () => { setConsent(false); setSelfie(null); setMatches(null); },
  };

  return <GuestFlowContext.Provider value={value}>{children}</GuestFlowContext.Provider>;
}

export function useGuestFlow(): GuestFlowValue {
  const ctx = useContext(GuestFlowContext);
  if (!ctx) throw new Error('useGuestFlow must be used within GuestFlowProvider');
  return ctx;
}
