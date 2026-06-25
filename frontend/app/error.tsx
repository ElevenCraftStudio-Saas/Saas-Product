'use client';

import { useEffect } from 'react';
import { ErrorState } from '@/components/feedback/states';

/** Route-segment error boundary (caught render/runtime errors). */
export default function RouteError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    // Surface to the console; Sentry (if wired on the frontend later) hooks here.
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg items-center p-8">
      <ErrorState
        title="Unexpected error"
        description={error.message || 'Please try again.'}
        onRetry={reset}
        className="w-full"
      />
    </div>
  );
}
