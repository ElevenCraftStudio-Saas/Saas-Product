'use client';

import { SearchX, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';

/** Friendly no-match state — never make the guest feel the system failed. */
export function EmptyGallery({ onRetake }: { onRetake: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4 py-10 text-center">
      <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
        <SearchX className="h-8 w-8" aria-hidden />
      </span>
      <div>
        <h2 className="text-lg font-semibold">No photos found yet</h2>
        <p className="mt-1 max-w-xs text-sm text-muted-foreground">
          We couldn’t match your face in this event’s photos. A clearer, well-lit selfie facing the camera usually helps.
        </p>
      </div>
      <Button className="h-12 w-full max-w-xs" onClick={onRetake}>
        <RotateCcw className="mr-2 h-4 w-4" /> Try another selfie
      </Button>
      <p className="text-xs text-muted-foreground">Still missing photos? Contact the wedding studio.</p>
    </div>
  );
}
