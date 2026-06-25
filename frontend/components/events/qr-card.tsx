'use client';

/* eslint-disable @next/next/no-img-element -- presigned S3 QR url; next/image
   needs stable remotePatterns + the url rotates, so a plain <img> is correct. */
import { Copy, Download, Printer } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { guestUrl } from '@/lib/format';

/** Reusable QR card — used in event actions and (future) sharing flows.
 *  The `.qr-printable` class isolates it for printing (see globals.css). */
export function QRCard({
  title,
  slug,
  qrImageUrl,
}: {
  title: string;
  slug: string;
  qrImageUrl: string | null;
}) {
  const url = guestUrl(slug);

  const copy = async () => {
    await navigator.clipboard.writeText(url);
    toast.success('Guest link copied');
  };

  const download = async () => {
    if (!qrImageUrl) return;
    try {
      const res = await fetch(qrImageUrl);
      const blob = await res.blob();
      const href = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = href;
      a.download = `${slug}-qr.png`;
      a.click();
      URL.revokeObjectURL(href);
    } catch {
      toast.error('Couldn’t download the QR code');
    }
  };

  return (
    <div className="qr-printable mx-auto w-full max-w-sm rounded-2xl border bg-card p-6 text-center shadow-sm">
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="mt-1 text-sm text-muted-foreground">Scan to find your photos</p>

      <div className="mx-auto mt-4 flex aspect-square w-56 items-center justify-center overflow-hidden rounded-xl border bg-white p-2">
        {qrImageUrl ? (
          <img src={qrImageUrl} alt={`QR code for ${title}`} className="h-full w-full object-contain" />
        ) : (
          <span className="text-sm text-muted-foreground">QR unavailable</span>
        )}
      </div>

      <p className="mt-4 break-all rounded-lg bg-muted px-3 py-2 text-xs">{url}</p>

      <div className="mt-4 flex justify-center gap-2 print:hidden">
        <Button variant="outline" size="sm" onClick={copy}>
          <Copy className="mr-1 h-4 w-4" /> Copy
        </Button>
        <Button variant="outline" size="sm" onClick={download} disabled={!qrImageUrl}>
          <Download className="mr-1 h-4 w-4" /> Download
        </Button>
        <Button variant="outline" size="sm" onClick={() => window.print()}>
          <Printer className="mr-1 h-4 w-4" /> Print
        </Button>
      </div>
    </div>
  );
}
