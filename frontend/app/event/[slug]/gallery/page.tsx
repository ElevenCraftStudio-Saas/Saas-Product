'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Download, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { GuestHeader } from '@/components/guest/guest-header';
import { GalleryGrid } from '@/components/guest/gallery-grid';
import { FullscreenViewer } from '@/components/guest/fullscreen-viewer';
import { EmptyGallery } from '@/components/guest/empty-gallery';
import { useGuestFlow } from '@/components/guest/guest-flow-provider';
import { getDownloadUrl, downloadAllZip } from '@/services/guest';
import type { GuestPhoto } from '@/types/models';

export default function GalleryPage() {
  const router = useRouter();
  const { slug, matches } = useGuestFlow();
  const [viewer, setViewer] = useState<number | null>(null);
  const [zipping, setZipping] = useState(false);

  useEffect(() => {
    if (!matches) router.replace(`/event/${slug}/selfie`);
  }, [matches, slug, router]);
  if (!matches) return null;

  const photos = matches.photos;

  const downloadOne = async (p: GuestPhoto) => {
    try {
      const url = await getDownloadUrl(slug, p.id, p.download_token);
      const a = document.createElement('a');
      a.href = url;
      a.download = p.filename;
      a.target = '_blank';
      a.rel = 'noreferrer';
      a.click();
    } catch {
      toast.error('Download failed');
    }
  };

  const downloadAll = async () => {
    setZipping(true);
    try {
      await downloadAllZip(slug, photos.map((p) => ({ id: p.id, token: p.download_token })));
    } catch {
      toast.error('Couldn’t prepare the download');
    } finally {
      setZipping(false);
    }
  };

  if (photos.length === 0) {
    return (
      <>
        <GuestHeader />
        <main className="flex-1">
          <EmptyGallery onRetake={() => router.replace(`/event/${slug}/selfie`)} />
        </main>
      </>
    );
  }

  return (
    <>
      <GuestHeader />
      <main className="flex-1 py-4">
        <div className="mb-4 flex items-center justify-between gap-2">
          <h1 className="text-xl font-bold">{photos.length} photo{photos.length === 1 ? '' : 's'} found</h1>
          <Button size="sm" onClick={downloadAll} disabled={zipping}>
            {zipping ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Download className="mr-1 h-4 w-4" />}
            Download all
          </Button>
        </div>
        <GalleryGrid photos={photos} onOpen={setViewer} onDownload={downloadOne} />
      </main>
      {viewer !== null && (
        <FullscreenViewer photos={photos} index={viewer} onClose={() => setViewer(null)} onIndex={setViewer} onDownload={downloadOne} />
      )}
    </>
  );
}
