'use client';

import { GalleryPhoto } from './gallery-photo';
import type { GuestPhoto } from '@/types/models';

/** Masonry layout via CSS columns (break-inside-avoid on items). */
export function GalleryGrid({
  photos,
  onOpen,
  onDownload,
}: {
  photos: GuestPhoto[];
  onOpen: (index: number) => void;
  onDownload: (photo: GuestPhoto) => void;
}) {
  return (
    <div className="columns-2 gap-3 sm:columns-3 md:columns-4">
      {photos.map((p, i) => (
        <GalleryPhoto key={p.id} photo={p} onOpen={() => onOpen(i)} onDownload={() => onDownload(p)} />
      ))}
    </div>
  );
}
