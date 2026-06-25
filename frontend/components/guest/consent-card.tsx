'use client';

import { useState } from 'react';
import { ScanFace, ShieldCheck, Trash2, Download, type LucideIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';

function Point({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <Icon className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden />
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="text-sm text-muted-foreground">{children}</p>
      </div>
    </div>
  );
}

export function ConsentCard({ onAccept, busy }: { onAccept: () => void; busy?: boolean }) {
  const [a, setA] = useState(false);
  const [b, setB] = useState(false);
  const ready = a && b;

  return (
    <div className="space-y-5">
      <Point icon={ScanFace} title="Why a selfie?">
        We use face recognition to find only the photos you appear in — nothing else.
      </Point>
      <Point icon={ShieldCheck} title="How it works">
        Your selfie becomes a numeric face signature, compared against this event’s photos, then discarded.
      </Point>
      <Point icon={Trash2} title="Your selfie isn’t stored">
        It’s processed in memory and deleted right after matching. Only the consent record is kept as proof.
      </Point>
      <Point icon={Download} title="Downloads & retention">
        You can download your matched photos. The studio may auto-delete photos after its retention period.
      </Point>

      <div className="space-y-3 rounded-xl border bg-muted/40 p-4">
        <label className="flex items-start gap-3 text-sm">
          <input type="checkbox" className="mt-0.5 h-4 w-4 accent-primary" checked={a} onChange={(e) => setA(e.target.checked)} />
          <span>I consent to facial recognition to find my photos.</span>
        </label>
        <label className="flex items-start gap-3 text-sm">
          <input type="checkbox" className="mt-0.5 h-4 w-4 accent-primary" checked={b} onChange={(e) => setB(e.target.checked)} />
          <span>I understand my biometric data is processed as described.</span>
        </label>
      </div>

      <Button className="h-12 w-full text-base" disabled={!ready || busy} onClick={onAccept}>
        Continue
      </Button>
    </div>
  );
}
