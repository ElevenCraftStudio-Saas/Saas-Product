'use client';

import { Button } from '@/components/ui/button';
import { Download, Loader2 } from 'lucide-react';
import { absoluteUrl, type GuestPhoto } from '@/lib/hooks/guest';

interface Props {
  photos: GuestPhoto[];
  onDownload: (photoId: number) => void;
  downloadingId?: number | null;
}

export function PhotoGallery({ photos, onDownload, downloadingId }: Props) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
      {photos.map((photo) => (
        <div
          key={photo.id}
          className="group relative aspect-square rounded-2xl overflow-hidden shadow-md border bg-white"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={absoluteUrl(photo.url)}
            alt={photo.filename}
            loading="lazy"
            decoding="async"
            className="w-full h-full object-cover transition-transform group-hover:scale-105"
          />
          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
            <Button
              variant="secondary"
              size="sm"
              className="space-x-2"
              onClick={() => onDownload(photo.id)}
              disabled={downloadingId === photo.id}
            >
              {downloadingId === photo.id ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4" />
              )}
              <span>Download</span>
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}
