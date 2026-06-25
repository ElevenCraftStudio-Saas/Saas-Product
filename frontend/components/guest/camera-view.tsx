'use client';

import { useRef, useState, useEffect, useCallback } from 'react';
import { Camera, AlertTriangle, ImageUp } from 'lucide-react';
import { Button } from '@/components/ui/button';

/** Mobile-first front-camera capture. Downscales to ~720px before handing back
 *  a JPEG blob (faster upload). Falls back to file upload if the camera is
 *  unavailable or permission is denied. Requires HTTPS/localhost. */
export function CameraView({ onCapture }: { onCapture: (blob: Blob) => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const start = useCallback(async () => {
    setError(null);
    setReady(false);
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('unsupported');
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 1080 }, height: { ideal: 1080 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setReady(true);
      }
    } catch (e: unknown) {
      const name = (e as { name?: string })?.name;
      if (name === 'NotAllowedError' || name === 'SecurityError') setError('Camera permission denied. Allow camera access and retry.');
      else if (name === 'NotFoundError') setError('No camera found on this device.');
      else setError('Camera unavailable — you can upload a selfie instead.');
    }
  }, []);

  // Start the camera (external device) on mount, stop on unmount. start() resets
  // error/ready synchronously — on mount these are no-ops; the rule flags the
  // synchronous setState path regardless.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- camera device lifecycle
    void start();
    return stop;
  }, [start, stop]);

  const capture = () => {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return;
    const max = 720;
    const scale = Math.min(1, max / Math.max(v.videoWidth, v.videoHeight));
    const w = Math.round(v.videoWidth * scale);
    const h = Math.round(v.videoHeight * scale);
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(v, 0, 0, w, h);
    canvas.toBlob((b) => { if (b) { stop(); onCapture(b); } }, 'image/jpeg', 0.9);
  };

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) onCapture(f);
  };

  if (error) {
    return (
      <div className="space-y-4 text-center">
        <div className="flex flex-col items-center gap-2 rounded-2xl border border-destructive/30 bg-destructive/5 p-6">
          <AlertTriangle className="h-8 w-8 text-destructive" aria-hidden />
          <p className="text-sm">{error}</p>
        </div>
        <div className="flex flex-col gap-2">
          <Button variant="outline" className="h-12" onClick={start}><Camera className="mr-2 h-4 w-4" /> Try camera again</Button>
          <Button className="h-12" onClick={() => fileRef.current?.click()}><ImageUp className="mr-2 h-4 w-4" /> Upload a selfie</Button>
        </div>
        <input ref={fileRef} type="file" accept="image/jpeg,image/png" hidden onChange={onFile} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="relative mx-auto aspect-square w-full max-w-xs overflow-hidden rounded-3xl border bg-black">
        {/* mirror the preview so it feels like a mirror */}
        <video ref={videoRef} playsInline muted className="h-full w-full -scale-x-100 object-cover" />
        <div className="pointer-events-none absolute inset-6 rounded-full border-2 border-white/60" />
      </div>
      <Button className="h-14 w-full rounded-full text-base" onClick={capture} disabled={!ready}>
        <Camera className="mr-2 h-5 w-5" /> Take selfie
      </Button>
      <button onClick={() => fileRef.current?.click()} className="block w-full text-center text-sm text-muted-foreground underline">
        Or upload a photo
      </button>
      <input ref={fileRef} type="file" accept="image/jpeg,image/png" hidden onChange={onFile} />
    </div>
  );
}
