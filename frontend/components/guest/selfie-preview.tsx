'use client';

/* eslint-disable @next/next/no-img-element -- local object URL preview. */
import { useEffect, useState } from 'react';
import { RotateCcw, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function SelfiePreview({
  blob,
  onRetake,
  onContinue,
  busy,
}: {
  blob: Blob;
  onRetake: () => void;
  onContinue: () => void;
  busy?: boolean;
}) {
  const [url, setUrl] = useState<string>('');
  // Manage the blob's object URL as an external resource (create on change,
  // revoke on cleanup). The synchronous setState is required to expose the URL.
  useEffect(() => {
    const u = URL.createObjectURL(blob);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- object URL lifecycle
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [blob]);

  return (
    <div className="space-y-4">
      <div className="mx-auto aspect-square w-full max-w-xs overflow-hidden rounded-3xl border bg-black">
        {url && <img src={url} alt="Your selfie" className="h-full w-full -scale-x-100 object-cover" />}
      </div>
      <div className="flex gap-2">
        <Button variant="outline" className="h-12 flex-1" onClick={onRetake} disabled={busy}>
          <RotateCcw className="mr-2 h-4 w-4" /> Retake
        </Button>
        <Button className="h-12 flex-1" onClick={onContinue} disabled={busy}>
          <Check className="mr-2 h-4 w-4" /> Find my photos
        </Button>
      </div>
    </div>
  );
}
