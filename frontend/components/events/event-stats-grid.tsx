'use client';

import { Image as ImageIcon, Loader2, ScanFace, Users, Download, HardDrive } from 'lucide-react';
import { StatGrid } from '@/components/dashboard/stat-grid';
import { MetricCard, MetricCardSkeleton } from '@/components/dashboard/metric-card';
import type { PhotoItem } from '@/types/models';

/** Event overview cards. Uploaded/Processing/Ready are real (derived from the
 *  photos list); guests/downloads/storage are placeholders until per-event
 *  aggregate endpoints exist (swap with no UI change). */
export function EventStatsGrid({ photos, isLoading }: { photos: PhotoItem[]; isLoading: boolean }) {
  if (isLoading) {
    return <StatGrid>{Array.from({ length: 6 }).map((_, i) => <MetricCardSkeleton key={i} />)}</StatGrid>;
  }
  const uploaded = photos.length;
  const processing = photos.filter((p) => p.processing_status === 'pending' || p.processing_status === 'processing').length;
  const ready = photos.filter((p) => p.processing_status === 'completed').length;

  return (
    <StatGrid>
      <MetricCard label="Photos Uploaded" value={uploaded} icon={ImageIcon} />
      <MetricCard label="Processing" value={processing} icon={Loader2} />
      <MetricCard label="Embeddings Ready" value={ready} icon={ScanFace} hint="faces indexed" />
      <MetricCard label="Guests Matched" value="—" icon={Users} hint="aggregate soon" />
      <MetricCard label="Downloads" value="—" icon={Download} hint="aggregate soon" />
      <MetricCard label="Storage Used" value="—" icon={HardDrive} hint="aggregate soon" />
    </StatGrid>
  );
}
