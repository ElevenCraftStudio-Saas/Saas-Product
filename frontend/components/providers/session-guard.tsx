'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { SESSION_EXPIRED_EVENT } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

/** Listens for the api layer's session-expired signal (a 401 that survived a
 *  token refresh) and signs the user out cleanly — no infinite 401 loops, no
 *  stale protected UI. Mounted once near the root. */
export function SessionGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { signOut } = useAuth();

  useEffect(() => {
    let handling = false;
    const onExpired = async () => {
      if (handling) return;
      handling = true;
      try {
        await signOut();
      } catch {
        /* already signed out */
      }
      toast.error('Your session expired. Please sign in again.');
      router.replace('/session-expired');
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, [router, signOut]);

  return <>{children}</>;
}
