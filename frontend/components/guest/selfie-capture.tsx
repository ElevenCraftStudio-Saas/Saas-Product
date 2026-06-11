'use client';

import { useRef, useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Camera, RefreshCw, Check, Loader2, AlertTriangle } from 'lucide-react';

interface Props {
  onConfirm: (blob: Blob) => void;
  busy?: boolean;
}

/**
 * Mobile-first live selfie capture via getUserMedia.
 * Works on Android Chrome + iOS Safari (playsInline). Requires HTTPS or
 * localhost — over plain http on a phone the browser blocks camera access.
 */
export function SelfieCapture({ onConfirm, busy }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const blobRef = useRef<Blob | null>(null);

  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const startCamera = useCallback(async () => {
    setError(null);
    setStarting(true);
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('unsupported');
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 1280 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch (e: unknown) {
      const name = (e as { name?: string })?.name;
      if (name === 'NotAllowedError' || name === 'SecurityError') {
        setError('Camera permission denied. Allow camera access in your browser and retry.');
      } else if (name === 'NotFoundError') {
        setError('No camera found on this device.');
      } else {
        setError('Cannot access camera. Open this page over HTTPS on a supported browser.');
      }
    } finally {
      setStarting(false);
    }
  }, []);

  useEffect(() => {
    startCamera();
    return stopCamera;
  }, [startCamera, stopCamera]);

  const capture = () => {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return;
    const canvas = document.createElement('canvas');
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(v, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(
      (b) => {
        if (!b) return;
        blobRef.current = b;
        setPreview(URL.createObjectURL(b));
        stopCamera();
      },
      'image/jpeg',
      0.92
    );
  };

  const retake = () => {
    if (preview) URL.revokeObjectURL(preview);
    setPreview(null);
    blobRef.current = null;
    startCamera();
  };

  const confirm = () => {
    if (blobRef.current) onConfirm(blobRef.current);
  };

  if (error) {
    return (
      <div className="flex flex-col items-center space-y-4 py-8 text-center">
        <AlertTriangle className="w-10 h-10 text-amber-500" />
        <p className="text-slate-600 max-w-sm">{error}</p>
        <Button onClick={startCamera} variant="outline" className="space-x-2">
          <RefreshCw className="w-4 h-4" />
          <span>Retry</span>
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center space-y-5 w-full">
      <div className="relative w-full max-w-sm aspect-square rounded-2xl overflow-hidden bg-black">
        {preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={preview} alt="Selfie preview" className="w-full h-full object-cover" />
        ) : (
          <video
            ref={videoRef}
            playsInline
            muted
            autoPlay
            className="w-full h-full object-cover [transform:scaleX(-1)]"
          />
        )}
        {starting && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/50">
            <Loader2 className="w-8 h-8 animate-spin text-white" />
          </div>
        )}
      </div>

      {preview ? (
        <div className="flex gap-3 w-full max-w-sm">
          <Button variant="outline" className="flex-1 space-x-2" onClick={retake} disabled={busy}>
            <RefreshCw className="w-4 h-4" />
            <span>Retake</span>
          </Button>
          <Button className="flex-1 space-x-2" onClick={confirm} disabled={busy}>
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
            <span>{busy ? 'Matching…' : 'Find my photos'}</span>
          </Button>
        </div>
      ) : (
        <Button
          className="w-full max-w-sm h-14 text-lg space-x-2 rounded-xl"
          onClick={capture}
          disabled={starting}
        >
          <Camera className="w-6 h-6" />
          <span>Capture</span>
        </Button>
      )}
    </div>
  );
}
