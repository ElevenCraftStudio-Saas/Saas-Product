'use client';

/* eslint-disable @next/next/no-img-element -- presigned S3 thumbnails. */
import { Download } from 'lucide-react';
import type { GuestPhoto } from '@/types/models';

export function GalleryPhoto({
  photo,
  onOpen,
  onDownload,
}: {
  photo: GuestPhoto;
  onOpen: () => void;
  onDownload: () => void;
}) {
  return (
    <div className="group relative mb-3 break-inside-avoid overflow-hidden rounded-xl border bg-muted">
      <button onClick={onOpen} className="block w-full" aria-label={`Open ${photo.filename}`}>
        <img src={photo.url} alt={photo.filename} loading="lazy" className="w-full object-cover transition-transform group-hover:scale-[1.02]" />
      </button>
      <button
        onClick={onDownload}
        aria-label={`Download ${photo.filename}`}
        className="absolute bottom-2 right-2 rounded-full bg-black/60 p-2 text-white opacity-100 transition-opacity focus-visible:opacity-100 sm:opacity-0 sm:group-hover:opacity-100"
      >
        <Download className="h-4 w-4" />
      </button>
    </div>
  );
}
