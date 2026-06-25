'use client';

/* eslint-disable @next/next/no-img-element -- presigned S3 images. */
import { useEffect, useRef } from 'react';
import { X, ChevronLeft, ChevronRight, Download } from 'lucide-react';
import type { GuestPhoto } from '@/types/models';

/** Fullscreen photo viewer with keyboard (←/→/Esc) + touch swipe. */
export function FullscreenViewer({
  photos,
  index,
  onClose,
  onIndex,
  onDownload,
}: {
  photos: GuestPhoto[];
  index: number;
  onClose: () => void;
  onIndex: (i: number) => void;
  onDownload: (p: GuestPhoto) => void;
}) {
  const startX = useRef(0);
  const prev = () => onIndex((index - 1 + photos.length) % photos.length);
  const next = () => onIndex((index + 1) % photos.length);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'ArrowLeft') prev();
      else if (e.key === 'ArrowRight') next();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const photo = photos[index];
  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-black/95"
      role="dialog"
      aria-modal="true"
      onTouchStart={(e) => { startX.current = e.touches[0].clientX; }}
      onTouchEnd={(e) => {
        const dx = e.changedTouches[0].clientX - startX.current;
        if (dx > 50) prev();
        else if (dx < -50) next();
      }}
    >
      <div className="flex items-center justify-between p-4 text-white">
        <span className="text-sm tabular-nums">{index + 1} / {photos.length}</span>
        <div className="flex gap-2">
          <button onClick={() => onDownload(photo)} aria-label="Download" className="rounded-full bg-white/10 p-2 hover:bg-white/20">
            <Download className="h-5 w-5" />
          </button>
          <button onClick={onClose} aria-label="Close" className="rounded-full bg-white/10 p-2 hover:bg-white/20">
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>
      <div className="relative flex flex-1 items-center justify-center p-4">
        <button onClick={prev} aria-label="Previous" className="absolute left-2 hidden rounded-full bg-white/10 p-3 text-white hover:bg-white/20 sm:block">
          <ChevronLeft className="h-6 w-6" />
        </button>
        <img src={photo.url} alt={photo.filename} className="max-h-full max-w-full object-contain" />
        <button onClick={next} aria-label="Next" className="absolute right-2 hidden rounded-full bg-white/10 p-3 text-white hover:bg-white/20 sm:block">
          <ChevronRight className="h-6 w-6" />
        </button>
      </div>
    </div>
  );
}
