'use client';

import { useParams } from 'next/navigation';
import { useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Camera, Loader2, Sparkles, Image as ImageIcon, ShieldCheck } from 'lucide-react';
import { SelfieCapture } from '@/components/guest/selfie-capture';
import { PhotoGallery } from '@/components/guest/photo-gallery';
import {
  useGuestEvent,
  useSelfieMatch,
  fetchDownloadUrl,
  type GuestPhoto,
} from '@/lib/hooks/guest';

const CONSENT_TEXT =
  'I consent to face recognition processing for the purpose of finding my event photos.';

export default function GuestEventPage() {
  const params = useParams();
  const slug = String(params.slug);

  const { data: event, isLoading } = useGuestEvent(slug);
  const match = useSelfieMatch(slug);

  const [consented, setConsented] = useState(false);
  const [photos, setPhotos] = useState<GuestPhoto[] | null>(null);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  async function handleConfirm(blob: Blob) {
    try {
      const result = await match.mutateAsync(blob);
      setPhotos(result.photos);
      if (result.count === 0) toast.info('No matches found. Try another selfie.');
      else toast.success(`Found ${result.count} photo${result.count > 1 ? 's' : ''} of you!`);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      toast.error(detail || 'Matching failed. Please try again.');
    }
  }

  async function handleDownload(photoId: number) {
    try {
      setDownloadingId(photoId);
      const url = await fetchDownloadUrl(slug, photoId);
      window.open(url, '_blank', 'noopener');
    } catch {
      toast.error('Could not start download.');
    } finally {
      setDownloadingId(null);
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  const showGallery = photos !== null && photos.length > 0;
  const noMatches = photos !== null && photos.length === 0;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center py-10 px-4">
      <div className="max-w-4xl w-full space-y-8">
        {/* Banner */}
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-extrabold tracking-tight text-slate-900">
            {event?.title}
          </h1>
          <p className="text-xl text-slate-500">
            {event?.description || 'Find your photos instantly using AI'}
          </p>
        </div>

        {/* Capture / consent flow (hidden once gallery shown) */}
        {!showGallery && (
          <Card className="border-2 border-primary/20 shadow-xl overflow-hidden">
            <CardHeader className="bg-primary text-primary-foreground text-center py-8">
              <Sparkles className="w-10 h-10 mx-auto mb-3 opacity-80" />
              <CardTitle className="text-2xl">Find Your Photos</CardTitle>
              <p className="opacity-90">Give consent, take a selfie, and we&apos;ll find you</p>
            </CardHeader>
            <CardContent className="p-6 md:p-8 space-y-6">
              {/* Consent gate */}
              <label className="flex items-start gap-3 rounded-lg border bg-slate-50 p-4 cursor-pointer">
                <input
                  type="checkbox"
                  checked={consented}
                  onChange={(e) => setConsented(e.target.checked)}
                  className="mt-1 h-5 w-5 accent-primary"
                />
                <span className="text-sm text-slate-700 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-primary shrink-0" />
                  {CONSENT_TEXT}
                </span>
              </label>

              {consented ? (
                <SelfieCapture onConfirm={handleConfirm} busy={match.isPending} />
              ) : (
                <div className="flex flex-col items-center space-y-3 py-6 text-center">
                  <Camera className="w-10 h-10 text-slate-300" />
                  <p className="text-sm text-slate-400">
                    Tick the consent box above to enable the camera.
                  </p>
                </div>
              )}

              <p className="text-xs text-center text-slate-400">
                Your selfie is used only for matching and is not stored permanently.
              </p>

              {noMatches && (
                <div className="text-center pt-2">
                  <div className="bg-slate-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-3">
                    <ImageIcon className="w-8 h-8 text-slate-300" />
                  </div>
                  <h3 className="font-semibold">No matches found</h3>
                  <p className="text-slate-500 text-sm mt-1">
                    Make sure your face is clearly visible, then retake.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Gallery */}
        {showGallery && (
          <div className="space-y-6">
            <div className="flex items-center justify-between border-b pb-4">
              <h2 className="text-2xl font-bold">Your Gallery ({photos!.length})</h2>
              <Button variant="outline" size="sm" onClick={() => setPhotos(null)}>
                New Search
              </Button>
            </div>
            <PhotoGallery
              photos={photos!}
              onDownload={handleDownload}
              downloadingId={downloadingId}
            />
          </div>
        )}
      </div>

      <footer className="mt-20 text-slate-400 text-sm">Powered by WedFind AI</footer>
    </div>
  );
}
